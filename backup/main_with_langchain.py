import httpx
import json
import os
import re
from typing import List, Dict, Optional, Any
from fastmcp import FastMCP
from langchain_core.tools import Tool


def setup_fastmcp_server_from_openapi_spec(
    spec_link: str,
    base_url: str,
    server_name: str,
) -> FastMCP:
    open_api_spec = httpx.get(spec_link).json()
    client = httpx.AsyncClient(base_url=base_url)

    return FastMCP.from_openapi(
        openapi_spec=open_api_spec,
        client=client,
        name=server_name,
    )


def load_servers_from_config(config_path: str = "servers.json") -> List[Dict]:
    if not os.path.exists(config_path):
        return []
    
    with open(config_path, 'r') as f:
        servers = json.load(f)
    return servers


async def get_api_specs(server_configs: List[Dict]) -> Dict[str, Dict]:
    specs = {}
    async with httpx.AsyncClient(timeout=10.0) as client:
        for config in server_configs:
            spec_url = config.get("spec_url") or config.get("spec_link")
            if spec_url and spec_url not in specs:
                try:
                    response = await client.get(spec_url)
                    if response.status_code == 200:
                        specs[spec_url] = {
                            "spec": response.json(),
                            "base_url": config.get("base_url"),
                            "name": config.get("name")
                        }
                except:
                    pass
    return specs


async def find_matching_endpoints(query: str, api_specs: Dict[str, Dict]) -> List[Dict]:
    query_lower = query.lower()
    query_words = set(query_lower.split())
    matched = []
    seen_paths = set()
    
    for spec_url, spec_data in api_specs.items():
        paths = spec_data["spec"].get("paths", {})
        base_url = spec_data["base_url"]
        server_name = spec_data["name"]
        
        for path, methods in paths.items():
            for method, operation in methods.items():
                if method.upper() != "GET":
                    continue
                
                operation_id = operation.get("operationId", "").lower()
                summary = operation.get("summary", "").lower()
                description = operation.get("description", "").lower()
                tags = [t.lower() for t in operation.get("tags", [])]
                path_lower = path.lower()
                
                all_keywords = [operation_id, summary, description, path_lower] + tags
                
                score = 0
                for word in query_words:
                    for kw in all_keywords:
                        if kw:
                            if word == kw:
                                score += 3
                            elif word in kw or kw in word:
                                score += 2
                            break
                
                if score > 0:
                    path_key = f"{base_url}{path}"
                    if path_key not in seen_paths:
                        seen_paths.add(path_key)
                        matched.append({
                            "method": method.upper(),
                            "path": path,
                            "base_url": base_url,
                            "server_name": server_name,
                            "operation_id": operation.get("operationId", ""),
                            "summary": operation.get("summary", ""),
                            "score": score,
                            "parameters": operation.get("parameters", [])
                        })
    
    matched.sort(key=lambda x: x.get("score", 0), reverse=True)
    return matched[:5]


async def execute_api_call(endpoint: Dict, query: str = "", previous_data: Any = None) -> Dict[str, Any]:
    path = endpoint['path']
    base_url = endpoint['base_url']
    
    path_params = re.findall(r'\{(\w+)\}', path)
    all_values = []
    
    if previous_data:
        def extract_values(data, depth=0):
            if depth > 3:
                return
            if isinstance(data, dict):
                for key, value in data.items():
                    if isinstance(value, (int, str)) and str(value).isdigit():
                        all_values.append(str(value))
                    elif isinstance(value, (list, dict)):
                        extract_values(value, depth + 1)
            elif isinstance(data, list):
                for item in data[:10]:
                    extract_values(item, depth + 1)
        
        extract_values(previous_data)
    
    if not all_values:
        numbers_in_query = re.findall(r'\b([0-9]+)\b', query)
        all_values.extend(numbers_in_query)
    
    if path_params and all_values:
        for i, param_name in enumerate(path_params):
            if i < len(all_values):
                param_value = all_values[i]
                path = path.replace(f"{{{param_name}}}", param_value)
    
    url = f"{base_url}{path}"
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.get(url)
            if response.status_code == 200:
                try:
                    data = response.json()
                    return {"success": True, "data": data}
                except:
                    return {"success": True, "data": response.text}
            else:
                return {"success": False, "error": f"HTTP {response.status_code}: {response.text[:200]}"}
        except Exception as e:
            return {"success": False, "error": str(e)}


async def execute_multi_stage_workflow(
    query: str,
    mounted_servers: List[FastMCP],
    server_configs: List[Dict],
) -> Dict[str, Any]:
    results = {
        "query": query,
        "stages": [],
        "final_result": None,
        "errors": []
    }
    
    api_specs = await get_api_specs(server_configs)
    endpoints = await find_matching_endpoints(query, api_specs)
    
    if not endpoints:
        results["errors"].append({"message": "No matching endpoints found"})
        results["final_result"] = {"summary": "No matching API endpoints found"}
        return results
    
    stage_results = []
    stage_data = {}
    
    all_previous_data = {}
    
    for idx, endpoint in enumerate(endpoints, 1):
        try:
            previous_data = all_previous_data if idx > 1 else None
            api_result = await execute_api_call(endpoint, query, previous_data)
            
            stage_info = {
                "stage": idx,
                "name": endpoint.get("operation_id", "api_call"),
                "status": "completed" if api_result.get("success") else "failed",
                "api": endpoint.get("server_name"),
                "endpoint": f"{endpoint['method']} {endpoint['path']}",
                "result": api_result
            }
            
            if api_result.get("success"):
                stage_data[f"stage_{idx}"] = api_result.get("data")
                all_previous_data[f"stage_{idx}"] = api_result.get("data")
                all_previous_data["combined"] = list(stage_data.values())
                stage_info["data_passed_to_next"] = True
            
            stage_results.append(stage_info)
            
        except Exception as e:
            results["errors"].append({"stage": idx, "error": str(e)})
    
    results["stages"] = stage_results
    results["final_result"] = {
        "combined": True,
        "stages_completed": len([s for s in stage_results if s.get("status") == "completed"]),
        "stages_total": len(stage_results),
        "summary": f"Executed {len(stage_results)} stage(s)"
    }
    
    return results


def create_langchain_tools(mounted_servers: List[FastMCP], server_configs: List[Dict]):
    async def orchestrate_multi_stage_func(query: str) -> str:
        try:
            result = await execute_multi_stage_workflow(
                query=query,
                mounted_servers=mounted_servers,
                server_configs=server_configs
            )
            return json.dumps(result, indent=2)
        except Exception as e:
            return json.dumps({"error": str(e)}, indent=2)
    
    tools = [
        Tool(
            name="orchestrate_multi_stage",
            description="""Orchestrate multi-stage workflows across all available APIs.
            Use this for complex queries that require chaining multiple API calls together.
            The agent will automatically discover and use available APIs.
            
            This tool will:
            1. Parse your query to identify required API calls
            2. Execute API calls in sequence
            3. Pass results from one stage to the next
            4. Combine and return all results""",
            func=orchestrate_multi_stage_func,
        ),
    ]
    
    return tools


def main(config_path: Optional[str] = None):
    config_file = config_path or os.getenv("SERVERS_CONFIG", "servers.json")
    server_configs = load_servers_from_config (config_file)
    
    if not server_configs:
        print(f"Warning: No servers found in {config_file}. Starting with empty gateway.")
    
    main_server = FastMCP(name="Generic Gateway MCP Server with LangChain Agent")
    
    mounted_servers = []
    
    for server_config in server_configs:
        try:
            server = setup_fastmcp_server_from_openapi_spec(
                spec_link=server_config.get("spec_url") or server_config.get("spec_link"),
                base_url=server_config.get("base_url"),
                server_name=server_config.get("name", "API Server"),
            )
            
            prefix = server_config.get("prefix")
            as_proxy = server_config.get("as_proxy", False)
            
            if prefix:
                main_server.mount(server, as_proxy=as_proxy, prefix=prefix)
            else:
                main_server.mount(server, as_proxy=as_proxy)
            
            mounted_servers.append(server)
            print(f"Mounted server: {server_config.get('name')}")
            
        except Exception as e:
            print(f"Error mounting server {server_config.get('name')}: {e}")
    
    @main_server.tool()
    async def agent_orchestrate(query: str) -> str:
        try:
            result = await execute_multi_stage_workflow(
                query=query,
                mounted_servers=mounted_servers,
                server_configs=server_configs
            )
            return json.dumps(result, indent=2, default=str)
        except Exception as e:
            error_result = {
                "query": query,
                "stages": [],
                "final_result": None,
                "errors": [{"message": f"Agent orchestration failed: {str(e)}", "exception": type(e).__name__}]
            }
            return json.dumps(error_result, indent=2, default=str)
    
    @main_server.tool()
    async def list_available_apis() -> str:
        api_info = []
        for server_config in server_configs:
            api_info.append({
                "name": server_config.get("name"),
                "base_url": server_config.get("base_url"),
                "prefix": server_config.get("prefix"),
            })
        return json.dumps({"apis": api_info}, indent=2)

    port = int(os.getenv("PORT", 8000))
    host = os.getenv("HOST", "0.0.0.0")
    
    print(f"Starting gateway on {host}:{port}")
    main_server.run(transport="streamable-http", host=host, port=port)


if __name__ == "__main__":
    import sys
    config_path = sys.argv[1] if len(sys.argv) > 1 else None
    main(config_path=config_path)
