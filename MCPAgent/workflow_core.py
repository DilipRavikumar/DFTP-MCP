import httpx
import re
import asyncio
import json
from typing import Dict, Any, List, Optional
from fastmcp import FastMCP
from urllib.parse import quote

try:
    from langchain_aws import ChatBedrock
except ImportError:
    try:
        from langchain_community.chat_models import ChatBedrock
    except ImportError:
        ChatBedrock = None

from main import CONFIG

_llm: Optional[Any] = None


def _init_llm(config: Dict = None) -> Optional[Any]:
    global _llm

    if _llm is not None:
        return _llm

    config = config or CONFIG

    if not config.get("llm", {}).get("enabled", True):
        return None

    if ChatBedrock is None:
        return None

    try:
        import boto3
        region = config["llm"]["aws_region"]
        model_id = config["llm"]["model_id"]

        session = boto3.Session(region_name=region)
        client = session.client("bedrock-runtime", region_name=region)

        _llm = ChatBedrock(
            region_name=region,
            model_id=model_id,
            client=client
        )
        print("[workflow_core]  LLM initialized")
        return _llm
    except Exception as e:
        print(f"[workflow_core]  LLM init failed: {e}")
        return None


async def _call_llm(prompt: str, config: Dict = None) -> str:
    llm = _init_llm(config)
    if not llm:
        raise ValueError("LLM not available")

    try:
        if hasattr(llm, "ainvoke"):
            response = await llm.ainvoke(prompt)
        else:
            response = await asyncio.to_thread(llm.invoke, prompt)
        return response.content.strip()
    except Exception as e:
        raise Exception(f"LLM call failed: {e}")


def _extract_base_url_from_spec(spec: Dict, configured_base_url: str) -> str:
    if configured_base_url.startswith(("http://", "https://")):
        return configured_base_url.rstrip("/")
    servers = spec.get("servers", [])
    if servers and (url := servers[0].get("url", "")).startswith(("http://", "https://")):
        return url.rstrip("/")
    raise ValueError("No valid base_url in OpenAPI spec")


async def get_api_specs(server_configs: List[Dict], config: Dict = None) -> Dict[str, Dict]:
    config = config or CONFIG
    timeout = config["timeouts"]["api_spec_load"]

    specs = {}

    async with httpx.AsyncClient(timeout=timeout) as client:
        for sc in server_configs:
            spec_url = sc.get("spec_url") or sc.get("spec_link")
            if not spec_url:
                continue

            try:
                res = await client.get(spec_url)
                if res.status_code == 200:
                    spec_data = res.json()
                    base_url = _extract_base_url_from_spec(spec_data, sc.get("base_url", ""))

                    specs[spec_url] = {
                        "spec": spec_data,
                        "base_url": base_url,
                        "name": sc.get("name", "Unknown API")
                    }
            except Exception as e:
                print(f"[workflow_core] Failed to load {sc.get('name')}: {e}")

    return specs


def expand_id_ranges(query: str, config: Dict = None) -> List[str]:
    config = config or CONFIG
    max_range_size = config.get("limits", {}).get("max_range_size", 1000)
    query_lower = query.lower()
    
    for pattern, handler in [
        (r'\b(\d+)\s+(?:to|through|until)\s+(\d+)\b', lambda m: range(int(m.group(1)), int(m.group(2)) + 1)),
        (r'\b(?:until|up\s+to)\s+(\d+)\b', lambda m: range(1, int(m.group(1)) + 1)),
        (r'\b(\d+)-(\d+)\b', lambda m: range(int(m.group(1)), int(m.group(2)) + 1))
    ]:
        match = re.search(pattern, query_lower if 'until' in pattern else query)
        if match:
            r = handler(match)
            if 0 < len(r) <= max_range_size:
                return [str(i) for i in r]
    
    comma_list = re.findall(r'\b(\d+)\b', query)
    return comma_list if len(comma_list) > 1 and (',' in query or ' and ' in query_lower) else re.findall(r'\b([0-9]+)\b', query)


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
                
                path_params = re.findall(r'\{(\w+)\}', path)
                path_params_lower = [p.lower() for p in path_params]
                
                has_id_in_query = "id" in query_words
                has_id_param = any("id" in param.lower() for param in path_params)
                has_id_in_operation = "id" in operation_id or "byid" in operation_id or "by_id" in operation_id
                
                id_bonus = 0
                if has_id_in_query and (has_id_param or has_id_in_operation) and numbers_in_query:
                    id_bonus = 10
                elif (has_id_param or has_id_in_operation) and numbers_in_query:
                    id_bonus = 5
                
                generic_words = {"find", "get", "search", "list", "show", "fetch", "retrieve"}
                
                penalty = 0
                if numbers_in_query and has_id_in_query and not path_params:
                    penalty = -10
                
                for word in query_words:
                    if word in generic_words:
                        if word not in operation_id:
                            continue
                    
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
                
                score += id_bonus
                score += penalty
                
                if numbers_in_query and (has_id_param or has_id_in_operation) and path_params:
                    if score <= 0:
                        score = 15
                    else:
                        score += 10
                
                if "pet" in query_words and "pet" in path_lower and path_params and numbers_in_query:
                    score += 5
                
                has_pet_in_query = "pet" in query_words
                has_pet_in_path = "pet" in path_lower
                has_pet_in_operation = "pet" in operation_id
                if has_pet_in_query and has_id_in_query and (has_pet_in_path or has_pet_in_operation) and (has_id_param or has_id_in_operation) and numbers_in_query:
                    score += 15
                
                if score > 0:
                    path_key = f"{base_url}{path}"
                    if path_key not in seen_paths:
                        seen_paths.add(path_key)
                        
                        if path_params and len(numbers_in_query) >= 1:
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
        if numbers_in_query:
            return id_based[:max_id_based]
        else:
            return id_based[:max_id_based] + other_endpoints[:max_other] if len(id_based) <= max_id_based else id_based[:max_id_based]
    
    return matched[:default_limit]


async def parse_sequential_query(query: str, config: Dict = None) -> List[str]:
    config = config or CONFIG
    try:
        response = await _call_llm(f'Parse this user query into separate sequential operations.\n\nQuery: "{query}"\n\nReturn ONLY a JSON array of operation strings. Example: ["Get inventory", "Get pet with ID 1"]\n\nJSON array:', config)
        json_match = re.search(r'\[.*?\]', response, re.DOTALL)
        operations = json.loads(json_match.group() if json_match else response)
        if isinstance(operations, list) and all(isinstance(op, str) for op in operations):
            return [op.strip() for op in operations if op.strip()]
    except Exception:
        pass
    return [query]


def _build_endpoint_catalog(api_specs: Dict[str, Dict], config: Dict) -> List[Dict]:
    endpoints = []

    for spec_url, data in api_specs.items():
        spec = data["spec"]
        base_url = data["base_url"]
        server_name = data["name"]

        for path, methods in spec.get("paths", {}).items():
            for method, op in methods.items():
                if method.upper() not in config["endpoints"]["allowed_methods"]:
                    continue

                path_params = re.findall(r"{(\w+)}", path)
                query_params = []
                for param in op.get("parameters", []):
                    if param.get("in") == "query":
                        query_params.append(param.get("name"))
                
                request_body_schema = None
                if request_body := op.get("requestBody", {}):
                    for content_type, content_schema in request_body.get("content", {}).items():
                        if "json" in content_type.lower():
                            request_body_schema = content_schema.get("schema", {})
                            break

                endpoints.append({
                    "idx": len(endpoints),
                    "method": method.upper(),
                    "path": path,
                    "base_url": base_url,
                    "server_name": server_name,
                    "operation_id": op.get("operationId", ""),
                    "summary": op.get("summary", ""),
                    "description": op.get("description", ""),
                    "path_params": path_params,
                    "query_params": query_params,
                    "request_body_schema": request_body_schema
                })

    return endpoints


async def _llm_plan_operation(operation: str, endpoints: List[Dict], config: Dict) -> Optional[Dict]:
    endpoint_list = []
    for ep in endpoints:
        desc = f"{ep['idx']}: {ep['method']} {ep['path']}"
        if ep['operation_id']:
            desc += f"\n   Operation ID: {ep['operation_id']}"
        if ep['summary']:
            desc += f"\n   Summary: {ep['summary']}"
        if ep['description']:
            desc_text = ep['description'][:200] + "..." if len(ep['description']) > 200 else ep['description']
            desc += f"\n   Description: {desc_text}"
        if ep['path_params']:
            desc += f"\n   Path Parameters: {', '.join(ep['path_params'])}"
        if ep['query_params']:
            desc += f"\n   Query Parameters: {', '.join(ep['query_params'])}"
        if ep.get('request_body_schema'):
            schema = ep['request_body_schema']
            required_fields = schema.get('required', [])
            properties = schema.get('properties', {})
            if properties:
                body_fields = []
                for field_name, field_schema in properties.items():
                    field_type = field_schema.get('type', 'unknown')
                    is_required = field_name in required_fields
                    req_marker = " (required)" if is_required else ""
                    body_fields.append(f"{field_name} ({field_type}){req_marker}")
                desc += f"\n   Request Body Fields: {', '.join(body_fields)}"
        endpoint_list.append(desc)
    
    endpoints_text = "\n".join(endpoint_list)
    
    prompt = f"""You are an API planner. Match the user operation to the best endpoint and extract all parameters.

User Operation: "{operation}"

Available Endpoints:
{endpoints_text}

Instructions:
1. Understand the semantic intent of the user operation
2. Find the endpoint that best matches the operation's intent by analyzing:
   - Endpoint path structure and naming
   - Operation ID, summary, and description
   - Parameter requirements
3. IMPORTANT: If the user operation mentions an ID or specific identifier (like "pet id 1", "id 1", "pet 1"), 
   STRONGLY prefer endpoints with path parameters (like /pet/{{petId}}) over endpoints without path parameters.
   For example, "fetch pet id 1" should match GET /pet/{{petId}} with petId=1, NOT GET /pet/findByStatus.
4. Extract path parameter values:
   - Identify values in the operation that map to path parameters
   - Match values to parameter names semantically
   - Preserve value types (numbers, strings, quoted text)
4. Extract query parameter values:
   - Identify values that correspond to query parameters
   - Return arrays when the parameter context indicates multiple values
   - Preserve original value formats
5. Extract request body values (for POST/PUT requests):
   - Identify all body fields mentioned in the operation
   - Match values to body field names semantically
   - For nested objects (like category), create proper nested structure
   - For arrays (like photoUrls, tags), create proper arrays
   - Include all required fields from the schema
   - Use appropriate data types (strings, numbers, booleans, objects, arrays)
6. Use empty objects if the endpoint has no parameters

Return ONLY a valid JSON object with no markdown, no code blocks, no explanation. Example format:
{{
  "endpoint_idx": 5,
  "path_params": {{"petId": "1"}},
  "query_params": {{"tags": ["tag2"]}},
  "body": {{
    "name": "doggie",
    "photoUrls": ["string"],
    "status": "available",
    "category": {{"id": 1, "name": "Dogs"}},
    "tags": [{{"id": 0, "name": "string"}}]
  }}
}}

If no endpoint matches, return: {{"endpoint_idx": null}}

IMPORTANT: Return ONLY the JSON object, nothing else. No markdown, no code blocks, no text before or after.

JSON:"""
    
    try:
        response = await _call_llm(prompt, config)
        
        response = re.sub(r'^```(?:json)?\s*|\s*```$', '', response.strip())
        plan = None
        try:
            plan = json.loads(response)
        except json.JSONDecodeError:
            if m := re.search(r'```(?:json)?\s*(\{.*?\})\s*```', response, re.DOTALL):
                try:
                    plan = json.loads(m.group(1))
                except json.JSONDecodeError:
                    pass
            if not plan and '{' in response:
                start_idx = response.find('{')
                brace_count = 0
                for i in range(start_idx, len(response)):
                    if response[i] == '{':
                        brace_count += 1
                    elif response[i] == '}':
                        brace_count -= 1
                        if brace_count == 0:
                            try:
                                plan = json.loads(response[start_idx:i+1])
                                break
                            except json.JSONDecodeError:
                                pass
            if not plan:
                cleaned = re.sub(r'^[^{]*|[^}]*$', '', response)
                if cleaned.startswith('{') and cleaned.endswith('}'):
                    try:
                        plan = json.loads(cleaned)
                    except json.JSONDecodeError:
                        pass
        if not plan:
            raise ValueError("Could not parse JSON from LLM response")
        
        if not isinstance(plan, dict):
            return None
        
        if plan.get("endpoint_idx") is None:
            return None
        
        idx = plan.get("endpoint_idx")
        if isinstance(idx, int) and 0 <= idx < len(endpoints):
            endpoint = endpoints[idx].copy()
            endpoint["path_params_values"] = plan.get("path_params", {})
            endpoint["query_params_values"] = plan.get("query_params", {})
            endpoint["body_values"] = plan.get("body", {})
            
            endpoint["path_params_values"] = {k: str(v) for k, v in endpoint["path_params_values"].items()}
            endpoint["query_params_values"] = {k: [str(i) for i in v] if isinstance(v, list) else str(v) for k, v in endpoint["query_params_values"].items()}
            
            return endpoint
    except Exception:
        pass

    return None


async def _call_mcp_tool_workflow(endpoint: Dict, main_server: FastMCP):
    try:
        operation_id = endpoint.get("operation_id", "")
        path = endpoint.get("path", "")
        method = endpoint.get("method", "GET")
        
        if not (tool_name := operation_id):
            if path_parts := path.strip("/").split("/"):
                tool_name = f"{method.lower()}{path_parts[-1].replace('{', '').replace('}', '').capitalize()}"
        if not tool_name:
            return {"success": False, "error": "Could not determine MCP tool name"}
        
        available_tool_names = []
        try:
            if hasattr(main_server, 'list_tools') and (all_tools := await main_server.list_tools()):
                available_tool_names = [getattr(t, 'name', getattr(t, '__name__', str(t))) for t in all_tools]
                for api_tool in all_tools:
                    api_tool_name = getattr(api_tool, 'name', str(api_tool))
                    if tool_name.lower() == api_tool_name.lower() or tool_name.lower() in api_tool_name.lower() or api_tool_name.lower() in tool_name.lower():
                        tool_name = api_tool_name
                        break
        except Exception:
            pass
        
        tool_args = {**endpoint.get("path_params_values", {}), **endpoint.get("query_params_values", {})}
        if method.upper() in ["POST", "PUT"] and (body_values := endpoint.get("body_values", {})):
            tool_args.update(body_values)
        
        try:
            call_tool_method = None
            if hasattr(main_server, 'call_tool'):
                call_tool_method = getattr(main_server, 'call_tool')
                if callable(call_tool_method):
                    try:
                        result = await call_tool_method(
                            name=tool_name,
                            arguments=tool_args,
                            raise_on_error=False
                        )
                        
                        if hasattr(result, 'isError') and result.isError:
                            error_text = (result.content[0].text if hasattr(result.content[0], 'text') else str(result.content[0])) if (hasattr(result, 'content') and result.content) else ""
                            return {"success": False, "error": error_text or "Tool execution failed"}
                        
                        if hasattr(result, 'structuredContent') and result.structuredContent:
                            return {"success": True, "data": result.structuredContent}
                        elif hasattr(result, 'content') and result.content:
                            content_text = result.content[0].text if hasattr(result.content[0], 'text') else str(result.content[0])
                            try:
                                return {"success": True, "data": json.loads(content_text)}
                            except:
                                return {"success": True, "data": content_text}
                        return {"success": True, "data": str(result)}
                        
                    except Exception as call_error:
                        pass
            
            if hasattr(main_server, 'get_tools'):
                try:
                    tools_dict = main_server.get_tools()
                    if asyncio.iscoroutine(tools_dict):
                        tools_dict = await tools_dict
                    if isinstance(tools_dict, dict):
                        tool_obj = (tools_dict.get(tool_name) or 
                                   next((tools_dict[k] for k in tools_dict if k.lower() == tool_name.lower()), None) or
                                   (next((tools_dict[n] for n in available_tool_names if n in tools_dict), None) if available_tool_names else None))
                        if tool_obj:
                            tool_result = tool_obj.run(tool_args) if hasattr(tool_obj, 'run') else (tool_obj(**tool_args) if callable(tool_obj) else None)
                            if asyncio.iscoroutine(tool_result):
                                tool_result = await tool_result
                            if tool_result:
                                if hasattr(tool_result, 'content') and tool_result.content:
                                    text = tool_result.content[0].text if hasattr(tool_result.content[0], 'text') else str(tool_result.content[0])
                                    try:
                                        return {"success": True, "data": json.loads(text)}
                                    except:
                                        return {"success": True, "data": text}
                                return {"success": True, "data": str(tool_result)}
                except Exception:
                    pass
            
            error_msg = f"MCP tool '{tool_name}' not found or could not be called"
            if available_tool_names:
                error_msg += f". Available tools: {available_tool_names[:10]}"
            return {"success": False, "error": error_msg}
        
        except Exception as tool_error:
            return {"success": False, "error": f"MCP tool call failed: {str(tool_error)}"}
    
    except Exception as e:
        return {"success": False, "error": str(e)}


async def execute_api_call(endpoint: Dict, query: str = "", previous_data: Any = None, config: Dict = None) -> Dict[str, Any]:
    config = config or CONFIG
    path = endpoint["path"]
    base_url = endpoint.get("base_url", "")
    
    if "path_params_values" in endpoint or "query_params_values" in endpoint or "body_values" in endpoint:
        path_params = endpoint.get("path_params_values", {})
        for param_name, param_value in path_params.items():
            path = path.replace(f"{{{param_name}}}", str(param_value))
        
        url = base_url.rstrip("/") + path
        if query_params := endpoint.get("query_params_values", {}):
            query_parts = [f"{k}={quote(str(v))}" for k, v in query_params.items() for v in ([v] if not isinstance(v, list) else v)]
            url += "?" + "&".join(query_parts)
        method = endpoint.get("method", "GET").upper()
        body_data = endpoint.get("body_values", {})
        
    else:
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
        
        url = base_url.rstrip("/") + path
        method = endpoint.get("method", "GET").upper()
        body_data = None
    
    timeout = config.get("timeouts", {}).get("api_call", 30.0)
    
    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            has_body = body_data is not None and body_data != {}
            headers = {"Content-Type": "application/json"} if has_body else {}
            method_map = {"GET": client.get, "POST": client.post, "PUT": client.put, "DELETE": client.delete}
            http_method = method_map.get(method, client.get)
            response = await (http_method(url, json=body_data, headers=headers) if has_body and method in ["POST", "PUT"] else http_method(url))
            
            if response.status_code == 200:
                try:
                    return {"success": True, "data": response.json()}
                except:
                    return {"success": True, "data": response.text}
            error_text_truncate = config.get("limits", {}).get("error_text_truncate", 200)
            error_text = (response.text[:error_text_truncate] if response.text else "")
            return {"success": False, "error": f"HTTP {response.status_code}: {error_text}"}
    except Exception as e:
        error_msg_truncate = config.get("limits", {}).get("error_message_truncate", 150)
        return {"success": False, "error": str(e)[:error_msg_truncate]}


async def execute_multi_stage_workflow(query: str, server_configs: List[Dict],
                                       main_server: Optional[FastMCP] = None,
                                       config: Optional[Dict] = None) -> Dict[str, Any]:
    config = config or CONFIG
    
    error_response = lambda msg: {"query": query, "endpoint": None, "method": None, "server": None, "result": {"success": False, "error": msg}}
    if not main_server:
        return error_response("No main_server provided - MCP tools require FastMCP instance")
    
    try:
        if not (api_specs := await get_api_specs(server_configs, config)):
            return error_response("No API specs loaded")
        if not (endpoints := _build_endpoint_catalog(api_specs, config)):
            return error_response("No endpoints found in API specs")
        
        operations = await parse_sequential_query(query, config)
        
        stages = []
        combined_data = []
        previous_data = None
        
        for i, operation in enumerate(operations):
            ep = await _llm_plan_operation(operation, endpoints, config)
            if not ep:
                stages.append({
                    "stage": i + 1,
                    "operation": operation,
                    "endpoint": None,
                    "status": "failed",
                    "error": "LLM planning failed - no endpoint selected"
                })
                continue
            
            result = await _call_mcp_tool_workflow(ep, main_server)
            
            stage_result = {
                "stage": i + 1,
                "operation": operation,
                "endpoint": ep["path"],
                "method": ep["method"],
                "server": ep["server_name"],
                "status": "success" if result.get("success") else "failed",
                "data": result.get("data"),
                "error": result.get("error")
            }
            stages.append(stage_result)
            
            if result.get("success") and result.get("data"):
                combined_data.append(result["data"])
                previous_data = result["data"]
        
        failed_stages = [s for s in stages if s["status"] == "failed"]
        return {"query": query, "endpoint": None, "method": None, "server": None, "result": {
            "success": len(failed_stages) == 0,
            "stages": stages,
            "stages_completed": len([s for s in stages if s["status"] == "success"]),
            "stages_failed": len(failed_stages),
            "combined_data": combined_data if combined_data else None,
            "error": f"{len(failed_stages)} stage(s) failed" if failed_stages else None
        }}
    except Exception as e:
        return error_response(str(e))
