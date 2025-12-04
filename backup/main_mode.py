    import httpx
    import json
    import re
    import os
    from typing import List, Dict, Any, Optional
    from fastmcp import FastMCP
    import asyncio

    try:
        from langchain_aws import ChatBedrock
    except ImportError:
        from langchain_community.chat_models import ChatBedrock

    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass


    def _deep_merge(default: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
        """Recursively merge two dictionaries, with override taking precedence"""
        result = default.copy()
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = _deep_merge(result[key], value)
            else:
                result[key] = value
        return result


    def load_config(config_path: str = "config.json") -> Dict[str, Any]:
        default_config = {
            "server": {"host": "0.0.0.0", "port": 8000, "name": "Generic MCP Gateway Server"},
            "endpoints": {
                "max_id_based_endpoints": 50,
                "max_other_endpoints": 5,
                "default_endpoint_limit": 10,
                "allowed_methods": ["GET"]
            },
            "timeouts": {"api_spec_load": 10.0, "api_call": 30.0, "openapi_fetch": 5.0},
            "llm": {"aws_region": "us-east-2", "model_id": "us.amazon.nova-pro-v1:0", "enabled": True},
            "limits": {
                "max_extract_depth": 3,
                "max_extract_items": 10,
                "error_message_truncate": 150,
                "error_text_truncate": 200,
                "max_range_size": 1000
            },
            "matching": {
                "exact_match_score": 3,
                "partial_match_score": 2
            },
            "mode_selection": {
                "mode_2_keywords": ["and then", "then", "multiple", "chain"],
                "classification_prompt": "Analyze the following user prompt and determine if it requires:\nMODE 1 (mode_1): A single-step API action - a simple, direct API call.\nMODE 2 (mode_2): A multi-step workflow - requires multiple API operations.\n\nUser prompt: \"{prompt}\"\n\nRespond with ONLY \"mode_1\" or \"mode_2\" - nothing else."
            },
            "display": {
                "separator_length": 60
            },
            "servers_config_file": "servers.json"
        }
        
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r') as f:
                    file_config = json.load(f)
                    default_config = _deep_merge(default_config, file_config)
            except Exception as e:
                print(f"Warning: Failed to load config: {e}")
        
        if os.getenv("AWS_REGION"):
            default_config["llm"]["aws_region"] = os.getenv("AWS_REGION")
        if os.getenv("BEDROCK_MODEL_ID"):
            default_config["llm"]["model_id"] = os.getenv("BEDROCK_MODEL_ID")
        
        return default_config


    def load_server_configs(config_file: str) -> List[Dict]:
        if not os.path.exists(config_file):
            return []
        try:
            with open(config_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading server configs: {e}")
            return []


    CONFIG = load_config()


    class ModeSelector:
        def __init__(self, mounted_servers: List[FastMCP] = None, server_configs: List[Dict] = None, config: Dict = None):
            self.mounted_servers = mounted_servers or []
            self.server_configs = server_configs or []
            self.config = config or CONFIG
            self.classification_llm: Optional[ChatBedrock] = None
            self._initialize_llm()
        
        def _initialize_llm(self):
            if not self.config.get("llm", {}).get("enabled", True):
                return
            
            import boto3
            llm_config = self.config.get("llm", {})
            region_name = llm_config.get("aws_region", "us-east-2")
            model_id = llm_config.get("model_id", "us.amazon.nova-pro-v1:0")
            
            try:
                session = boto3.Session(region_name=region_name)
                client = session.client("bedrock-runtime", region_name=region_name)
                self.classification_llm = ChatBedrock(region_name=region_name, model_id=model_id, client=client)
                print(f"✓ ChatBedrock initialized")
            except Exception as e:
                error_truncate = self.config.get("limits", {}).get("error_message_truncate", 150)
                print(f"✗ ChatBedrock init failed: {str(e)[:error_truncate]}")
                self.classification_llm = None
        
        async def _safe_llm_invoke(self, llm, prompt: str):
            if hasattr(llm, 'ainvoke'):
                return await llm.ainvoke(prompt)
            elif hasattr(llm, 'invoke'):
                return await asyncio.to_thread(llm.invoke, prompt)
            else:
                raise AttributeError("LLM has neither ainvoke nor invoke method")
        
        async def analyze_prompt(self, prompt: str) -> str:
            if not prompt or not prompt.strip():
                return "mode_1"
            
            mode_config = self.config.get("mode_selection", {})
            mode_2_keywords = mode_config.get("mode_2_keywords", ["and then", "then", "multiple", "chain"])
            classification_prompt_template = mode_config.get(
                "classification_prompt",
                "Analyze the following user prompt and determine if it requires:\nMODE 1 (mode_1): A single-step API action - a simple, direct API call.\nMODE 2 (mode_2): A multi-step workflow - requires multiple API operations.\n\nUser prompt: \"{prompt}\"\n\nRespond with ONLY \"mode_1\" or \"mode_2\" - nothing else."
            )
            
            if not self.classification_llm:
                return "mode_2" if any(kw in prompt.lower() for kw in mode_2_keywords) else "mode_1"
            
            prompt_text = classification_prompt_template.format(prompt=prompt)

            try:
                response = await self._safe_llm_invoke(self.classification_llm, prompt_text)
                result = response.content.strip().lower()
                return "mode_2" if "mode_2" in result else "mode_1"
            except Exception:
                return "mode_2" if any(kw in prompt.lower() for kw in mode_2_keywords) else "mode_1"
        
        async def handle_mode_1(self, prompt: str) -> Dict[str, Any]:
            print(f"[MODE 1] Single API call: {prompt}")
            api_specs = await get_api_specs(self.server_configs, self.config)
            endpoints = await find_matching_endpoints(prompt, api_specs, self.config)
            
            if not endpoints:
                return {"success": False, "error": "No matching endpoint found", "query": prompt, "mode": "mode_1"}
            
            best_endpoint = endpoints[0]
            result = await execute_api_call(best_endpoint, prompt, None, self.config)
            
            return {
                "success": result.get("success", False),
                "query": prompt,
                "mode": "mode_1",
                "endpoint": f"{best_endpoint['method']} {best_endpoint['path']}",
                "server": best_endpoint.get("server_name", ""),
                "data": result.get("data") if result.get("success") else None,
                "error": result.get("error") if not result.get("success") else None
            }
        
        async def handle_mode_2(self, prompt: str) -> Dict[str, Any]:
            print(f"[MODE 2] Using LangGraph agent workflow")

            # Import agent from separate file
            from agent_graph import agent

            # Prepare agent input
            state = {
                "query": prompt,
                "context": {
                    "servers": self.mounted_servers,
                    "server_configs": self.server_configs
                },
                "plan": "",
                "result": None
            }

            # Run LangGraph agent
            output = await agent.ainvoke(state)

            # Return only the final result component
            return output["result"]
        
        async def route(self, prompt: str) -> Dict[str, Any]:
            """Analyze prompt and route to appropriate mode handler"""
            mode = await self.analyze_prompt(prompt)
            print(f"[ModeSelector] Detected mode: {mode} for query: {prompt}")
            
            if mode == "mode_2":
                return await self.handle_mode_2(prompt)
            else:
                return await self.handle_mode_1(prompt)


    def _extract_base_url_from_spec(spec: Dict, config_base_url: str) -> str:
        if config_base_url and (config_base_url.startswith("http://") or config_base_url.startswith("https://")):
            return config_base_url.rstrip("/")
        servers = spec.get("servers", [])
        if servers and len(servers) > 0:
            server_url = servers[0].get("url", "")
            if server_url and (server_url.startswith("http://") or server_url.startswith("https://")):
                return server_url.rstrip("/")
        raise ValueError(f"No valid base_url found")


    async def get_api_specs(server_configs: List[Dict], config: Dict = None) -> Dict[str, Dict]:
        config = config or CONFIG
        timeout = config.get("timeouts", {}).get("api_spec_load", 10.0)
        specs = {}
        
        async with httpx.AsyncClient(timeout=timeout) as client:
            for server_config in server_configs:
                spec_url = server_config.get("spec_url") or server_config.get("spec_link")
                if spec_url and spec_url not in specs:
                    try:
                        response = await client.get(spec_url)
                        if response.status_code == 200:
                            spec_data = response.json()
                            base_url = _extract_base_url_from_spec(spec_data, server_config.get("base_url", ""))
                            specs[spec_url] = {"spec": spec_data, "base_url": base_url, "name": server_config.get("name", "Unknown API")}
                            print(f"✓ Loaded {server_config.get('name', 'Unknown API')}")
                    except Exception as e:
                        error_truncate = config.get("limits", {}).get("error_message_truncate", 150)
                        print(f"✗ Failed to load {server_config.get('name', 'Unknown API')}: {str(e)[:error_truncate]}")
        return specs


    def expand_id_ranges(query: str, config: Dict = None) -> List[str]:
        """Extract and expand ID ranges from query (e.g., 'until 50' -> ['1', '2', ..., '50'])"""
        config = config or CONFIG
        max_range_size = config.get("limits", {}).get("max_range_size", 1000)
        query_lower = query.lower()
        
        # Pattern 1: "X to Y" or "X through Y" or "X until Y"
        range_pattern = re.search(r'\b(\d+)\s+(?:to|through|until)\s+(\d+)\b', query_lower)
        if range_pattern:
            start, end = int(range_pattern.group(1)), int(range_pattern.group(2))
            if start <= end and (end - start) <= max_range_size:
                return [str(i) for i in range(start, end + 1)]
        
        # Pattern 2: "until Y" or "up to Y" (assumes starting from 1)
        until_pattern = re.search(r'\b(?:until|up\s+to)\s+(\d+)\b', query_lower)
        if until_pattern:
            end = int(until_pattern.group(1))
            if end > 0 and end <= max_range_size:
                return [str(i) for i in range(1, end + 1)]
        
        # Pattern 3: "X-Y" (hyphen range)
        hyphen_range = re.search(r'\b(\d+)-(\d+)\b', query)
        if hyphen_range:
            start, end = int(hyphen_range.group(1)), int(hyphen_range.group(2))
            if start <= end and (end - start) <= max_range_size:
                return [str(i) for i in range(start, end + 1)]
        
        # Pattern 4: Comma-separated list
        comma_list = re.findall(r'\b(\d+)\b', query)
        if len(comma_list) > 1 and (',' in query or ' and ' in query_lower):
            return comma_list
        
        # Pattern 5: Fallback - extract all numbers
        return re.findall(r'\b([0-9]+)\b', query)


    async def find_matching_endpoints(query: str, api_specs: Dict[str, Dict], config: Dict = None) -> List[Dict]:
        config = config or CONFIG
        query_lower = query.lower()
        query_words = set(query_lower.split())
        matched = []
        seen_paths = set()
        numbers_in_query = expand_id_ranges(query, config)
        
        for spec_url, spec_data in api_specs.items():
            paths = spec_data["spec"].get("paths", {})
            base_url = spec_data["base_url"]
            server_name = spec_data["name"]
            
            allowed_methods = config.get("endpoints", {}).get("allowed_methods", ["GET"])
            matching_config = config.get("matching", {})
            exact_match_score = matching_config.get("exact_match_score", 3)
            partial_match_score = matching_config.get("partial_match_score", 2)
            
            for path, methods in paths.items():
                for method, operation in methods.items():
                    if method.upper() not in [m.upper() for m in allowed_methods]:
                        continue
                    
                    operation_id = operation.get("operationId", "").lower()
                    summary = operation.get("summary", "").lower()
                    description = operation.get("description", "").lower()
                    tags = [t.lower() for t in operation.get("tags", [])]
                    path_lower = path.lower()
                    all_keywords = [operation_id, summary, description, path_lower] + tags
                    
                    score = 0
                    matched_keywords = set()
                    for word in query_words:
                        for kw in all_keywords:
                            if kw and kw not in matched_keywords:
                                if word == kw:
                                    score += exact_match_score
                                    matched_keywords.add(kw)
                                    break
                                elif word in kw or kw in word:
                                    score += partial_match_score
                                    matched_keywords.add(kw)
                                    break
                    
                    if score > 0:
                        path_key = f"{base_url}{path}"
                        if path_key not in seen_paths:
                            seen_paths.add(path_key)
                            path_params = re.findall(r'\{(\w+)\}', path)
                            
                            if path_params and len(numbers_in_query) > 1:
                                for param_value in numbers_in_query:
                                    matched.append({
                                        "method": method.upper(),
                                        "path": path,
                                        "base_url": base_url,
                                        "server_name": server_name,
                                        "operation_id": operation.get("operationId", ""),
                                        "score": score,
                                        "path_params": path_params,
                                        "param_value": param_value
                                    })
                            else:
                                matched.append({
                                    "method": method.upper(),
                                    "path": path,
                                    "base_url": base_url,
                                    "server_name": server_name,
                                    "operation_id": operation.get("operationId", ""),
                                    "score": score,
                                    "path_params": path_params,
                                    "param_value": None
                                })
        
        matched.sort(key=lambda x: x.get("score", 0), reverse=True)
        max_id_based = config.get("endpoints", {}).get("max_id_based_endpoints", 50)
        max_other = config.get("endpoints", {}).get("max_other_endpoints", 5)
        default_limit = config.get("endpoints", {}).get("default_endpoint_limit", 10)
        
        id_based = [ep for ep in matched if ep.get("param_value") is not None]
        if id_based:
            other_endpoints = [ep for ep in matched if ep.get("param_value") is None]
            return id_based[:max_id_based] + other_endpoints[:max_other] if len(id_based) <= max_id_based else id_based[:max_id_based]
        
        return matched[:default_limit]


    async def execute_api_call(endpoint: Dict, query: str = "", previous_data: Any = None, config: Dict = None) -> Dict[str, Any]:
        path = endpoint['path']
        base_url = endpoint['base_url']
        config = config or CONFIG
        
        if endpoint.get("param_value") is not None:
            path_params = endpoint.get("path_params", re.findall(r'\{(\w+)\}', path))
            param_value = endpoint["param_value"]
            if path_params:
                for param_name in path_params:
                    if f"{{{param_name}}}" in path:
                        path = path.replace(f"{{{param_name}}}", param_value)
                        break
        else:
            path_params = re.findall(r'\{(\w+)\}', path)
            all_values = []
            if previous_data:
                limits_config = config.get("limits", {})
                max_depth = limits_config.get("max_extract_depth", 3)
                max_items = limits_config.get("max_extract_items", 10)
                
                def extract_values(data, depth=0):
                    if depth > max_depth:
                        return
                    if isinstance(data, dict):
                        for value in data.values():
                            if isinstance(value, (int, str)) and str(value).isdigit():
                                all_values.append(str(value))
                            elif isinstance(value, (list, dict)):
                                extract_values(value, depth + 1)
                    elif isinstance(data, list):
                        for item in data[:max_items]:
                            extract_values(item, depth + 1)
                extract_values(previous_data)
            
            if not all_values:
                all_values = re.findall(r'\b([0-9]+)\b', query)
            
            if path_params and all_values:
                for i, param_name in enumerate(path_params):
                    if i < len(all_values):
                        path = path.replace(f"{{{param_name}}}", all_values[i])
        
        full_url = base_url.rstrip("/") + path
        timeout = config.get("timeouts", {}).get("api_call", 30.0)
        
        try:
            async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
                response = await client.get(full_url)
                if response.status_code == 200:
                    try:
                        return {"success": True, "data": response.json()}
                    except:
                        return {"success": True, "data": response.text}
                else:
                    error_text_truncate = config.get("limits", {}).get("error_text_truncate", 200)
                    error_msg_truncate = config.get("limits", {}).get("error_message_truncate", 150)
                    return {"success": False, "error": f"HTTP {response.status_code}: {response.text[:error_text_truncate]}"}
        except Exception as e:
            error_msg_truncate = config.get("limits", {}).get("error_message_truncate", 150)
            return {"success": False, "error": str(e)[:error_msg_truncate]}


    def are_endpoints_independent(endpoints: List[Dict]) -> bool:
        """Check if endpoints can be executed in parallel"""
        if len(endpoints) <= 1:
            return False
        
        id_based_endpoints = [ep for ep in endpoints if ep.get("param_value") is not None]
        if len(id_based_endpoints) < 2:
            return False
        
        first_path = id_based_endpoints[0].get("path", "")
        if not all(ep.get("path", "") == first_path for ep in id_based_endpoints):
            return False
        
        param_values = [ep.get("param_value") for ep in id_based_endpoints]
        return len(param_values) == len(set(param_values))


    async def execute_multi_stage_workflow(query: str, mounted_servers: List[FastMCP], server_configs: List[Dict], config: Dict = None) -> Dict[str, Any]:
        config = config or CONFIG
        results = {"query": query, "stages": [], "final_result": None, "errors": []}
        
        api_specs = await get_api_specs(server_configs, config)
        endpoints = await find_matching_endpoints(query, api_specs, config)
        
        if not endpoints:
            results["errors"].append({"message": "No matching endpoints found"})
            results["final_result"] = {"summary": "No matching API endpoints found"}
            return results
        
        stage_results = []
        all_results = []
        
        id_based_endpoints = [ep for ep in endpoints if ep.get("param_value") is not None]
        other_endpoints = [ep for ep in endpoints if ep.get("param_value") is None]
        
        can_parallelize = are_endpoints_independent(id_based_endpoints) if id_based_endpoints else False
        execution_mode = "parallel" if can_parallelize else "sequential"
        
        print(f"[MODE 2] Execution mode: {execution_mode} ({len(id_based_endpoints)} ID-based endpoints, {len(other_endpoints)} other endpoints)")
        
        # Execute other endpoints sequentially
        other_stage_idx = 0
        for endpoint in other_endpoints:
            other_stage_idx += 1
            try:
                api_result = await execute_api_call(endpoint, query, None, config)
                stage_info = {
                    "stage": other_stage_idx,
                    "name": endpoint.get("operation_id", "api_call"),
                    "status": "completed" if api_result.get("success") else "failed",
                    "api": endpoint.get("server_name"),
                    "endpoint": f"{endpoint['method']} {endpoint['path']}",
                    "result": api_result
                }
                if api_result.get("success"):
                    all_results.append(api_result.get("data"))
                    stage_info["data_passed_to_next"] = True
                stage_results.append(stage_info)
            except Exception as e:
                results["errors"].append({"stage": other_stage_idx, "error": str(e)})
        
        # Execute ID-based endpoints
        if id_based_endpoints and can_parallelize:
            print(f"[MODE 2] Executing {len(id_based_endpoints)} ID-based operations in parallel...")
            
            async def execute_with_stage_info(base_idx: int, endpoint: Dict) -> Dict:
                try:
                    api_result = await execute_api_call(endpoint, query, None, config)
                    endpoint_desc = f"{endpoint['method']} {endpoint['path']}"
                    if endpoint.get("param_value") is not None:
                        endpoint_desc += f" (ID: {endpoint['param_value']})"
                    
                    return {
                        "stage": base_idx,
                        "name": endpoint.get("operation_id", "api_call"),
                        "status": "completed" if api_result.get("success") else "failed",
                        "api": endpoint.get("server_name"),
                        "endpoint": endpoint_desc,
                        "result": api_result,
                        "success": api_result.get("success", False),
                        "data": api_result.get("data") if api_result.get("success") else None
                    }
                except Exception as e:
                    return {
                        "stage": base_idx,
                        "name": endpoint.get("operation_id", "api_call"),
                        "status": "failed",
                        "api": endpoint.get("server_name"),
                        "endpoint": f"{endpoint['method']} {endpoint['path']}",
                        "result": {"success": False, "error": str(e)},
                        "success": False,
                        "data": None
                    }
            
            stage_tasks = [execute_with_stage_info(other_stage_idx + idx + 1, endpoint) for idx, endpoint in enumerate(id_based_endpoints)]
            stage_infos = await asyncio.gather(*stage_tasks, return_exceptions=True)
            
            for stage_info in stage_infos:
                if isinstance(stage_info, Exception):
                    results["errors"].append({"error": str(stage_info)})
                    continue
                stage_results.append(stage_info)
                if stage_info.get("success"):
                    all_results.append(stage_info["data"])
                    stage_info["data_passed_to_next"] = True
            
            successful = len([s for s in stage_results if s.get("status") == "completed"])
            print(f"[MODE 2] Parallel execution completed: {successful}/{len(id_based_endpoints)} successful")
        
        elif id_based_endpoints:
            print(f"[MODE 2] Executing {len(id_based_endpoints)} ID-based operations sequentially...")
            for idx, endpoint in enumerate(id_based_endpoints):
                stage_num = other_stage_idx + idx + 1
                try:
                    api_result = await execute_api_call(endpoint, query, None, config)
                    endpoint_desc = f"{endpoint['method']} {endpoint['path']}"
                    if endpoint.get("param_value") is not None:
                        endpoint_desc += f" (ID: {endpoint['param_value']})"
                    
                    stage_info = {
                        "stage": stage_num,
                        "name": endpoint.get("operation_id", "api_call"),
                        "status": "completed" if api_result.get("success") else "failed",
                        "api": endpoint.get("server_name"),
                        "endpoint": endpoint_desc,
                        "result": api_result
                    }
                    if api_result.get("success"):
                        all_results.append(api_result.get("data"))
                        stage_info["data_passed_to_next"] = True
                    stage_results.append(stage_info)
                except Exception as e:
                    results["errors"].append({"stage": stage_num, "error": str(e)})
        
        report_summary = None
        if len(all_results) > 1:
            report_summary = {
                "total_requests": len(stage_results),
                "successful": len(all_results),
                "failed": len(stage_results) - len(all_results),
                "results": all_results,
                "execution_mode": execution_mode
            }
        
        results["stages"] = stage_results
        results["final_result"] = {
            "combined": True,
            "stages_completed": len([s for s in stage_results if s.get("status") == "completed"]),
            "stages_total": len(stage_results),
            "summary": f"Executed {len(stage_results)} stage(s) in {execution_mode} mode",
            "execution_mode": execution_mode,
            "report": report_summary
        }
        
        return results


    _fastmcp_clients: List[httpx.AsyncClient] = []


    def setup_fastmcp_server_from_openapi_spec(spec_link: str, base_url: str, server_name: str, config: Dict = None) -> Optional[FastMCP]:
        config = config or CONFIG
        timeout = config.get("timeouts", {}).get("openapi_fetch", 5.0)
        
        try:
            print(f"Loading {server_name}...")
            open_api_spec = httpx.get(spec_link, timeout=timeout).json()
            
            if not base_url.startswith("http://") and not base_url.startswith("https://"):
                raise ValueError(f"base_url must start with http:// or https://: {base_url}")
            
            extracted_base_url = _extract_base_url_from_spec(open_api_spec, base_url)
            print(f"  Base URL: {extracted_base_url}")
            
            client = httpx.AsyncClient(base_url=extracted_base_url)
            _fastmcp_clients.append(client)
            
            server = FastMCP.from_openapi(openapi_spec=open_api_spec, client=client, name=server_name)
            print(f"✓ {server_name} loaded")
            return server
        except Exception as e:
            error_truncate = config.get("limits", {}).get("error_message_truncate", 150)
            print(f"✗ Failed to load {server_name}: {str(e)[:error_truncate]}")
            return None


    def main(config_path: str = "config.json"):
        config = load_config(config_path)
        servers_config_file = config.get("servers_config_file", "servers.json")
        server_configs = load_server_configs(servers_config_file)
        
        if not server_configs:
            print("✗ No servers configured")
            return
        
        servers = []
        for server_config in server_configs:
            spec_url = server_config.get("spec_url") or server_config.get("spec_link")
            base_url = server_config.get("base_url", "")
            server_name = server_config.get("name", "Unknown API")
            
            if not spec_url:
                print(f"✗ Skipping {server_name}: No spec_url specified")
                continue
            
            server = setup_fastmcp_server_from_openapi_spec(spec_url, base_url, server_name, config)
            if server:
                servers.append(server)
        
        if not servers:
            print("✗ No servers loaded successfully")
            return
        
        server_config = config.get("server", {})
        server_name = server_config.get("name", "Generic MCP Gateway Server")
        main_server: FastMCP = FastMCP(name=server_name)
        
        for server in servers:
            main_server.mount(server)
        
        mode_selector = ModeSelector(mounted_servers=servers, server_configs=server_configs, config=config)
        
        @main_server.tool()
        async def agent_orchestrate(query: str) -> str:
            """Orchestrate API calls - routes to Mode 1 (single) or Mode 2 (multi-step/parallel)"""
            result = await mode_selector.route(query)
            return json.dumps(result, indent=2, default=str) if result else json.dumps({"mode": "mode_1"}, indent=2)
        
        host = server_config.get("host", "0.0.0.0")
        port = server_config.get("port", 8000)
        separator_length = config.get("display", {}).get("separator_length", 60)
        
        print("\n" + "="*separator_length)
        print(f"✓ {server_name} Ready")
        print("="*separator_length)
        print(f"Listening on http://{host}:{port}")
        print("="*separator_length + "\n")
        
        main_server.run(transport="streamable-http", host=host, port=port)


    if __name__ == "__main__":
        import sys
        config_file = sys.argv[1] if len(sys.argv) > 1 else "config.json"
        main(config_path=config_file)
