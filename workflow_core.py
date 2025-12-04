# workflow_core.py - LLM-Driven Workflow Engine

import httpx
import re
import asyncio
import json
from typing import Dict, Any, List, Optional
from fastmcp import FastMCP
from urllib.parse import quote

# Optional Bedrock imports
try:
    from langchain_aws import ChatBedrock
except ImportError:
    try:
        from langchain_community.chat_models import ChatBedrock
    except ImportError:
        ChatBedrock = None

# Import CONFIG safely (no circular import)
from main import CONFIG

# Global LLM instance
_llm: Optional[Any] = None


# --------------------------------------------------------------
# Initialize LLM
# --------------------------------------------------------------
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
        print("[workflow_core] ✓ LLM initialized")
        return _llm
    except Exception as e:
        print(f"[workflow_core] ✗ LLM init failed: {e}")
        return None


# --------------------------------------------------------------
# Call LLM with prompt
# --------------------------------------------------------------
async def _call_llm(prompt: str, config: Dict = None) -> str:
    """Call LLM and return response text"""
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


# --------------------------------------------------------------
# Extract base_url from OpenAPI spec
# --------------------------------------------------------------
def _extract_base_url_from_spec(spec: Dict, configured_base_url: str) -> str:
    if configured_base_url.startswith("http://") or configured_base_url.startswith("https://"):
        return configured_base_url.rstrip("/")

    servers = spec.get("servers", [])
    if servers:
        url = servers[0].get("url", "")
        if url.startswith("http://") or url.startswith("https://"):
            return url.rstrip("/")

    raise ValueError("No valid base_url in OpenAPI spec")


# --------------------------------------------------------------
# Load & cache API specs from external servers
# --------------------------------------------------------------
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


# --------------------------------------------------------------
# Expand ID ranges from query (helper for find_matching_endpoints)
# --------------------------------------------------------------
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


# --------------------------------------------------------------
# Find matching endpoints (keyword-based matching for Mode 1)
# --------------------------------------------------------------
async def find_matching_endpoints(query: str, api_specs: Dict[str, Dict], config: Dict = None) -> List[Dict]:
    """Find endpoints matching the query using keyword-based scoring"""
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
    # NOTE: max_id_based_endpoints not in default config, using default value
    max_id_based = config.get("endpoints", {}).get("max_id_based_endpoints", 50)
    max_other = config.get("endpoints", {}).get("max_other_endpoints", 5)
    default_limit = config.get("endpoints", {}).get("default_endpoint_limit", 10)
    
    id_based = [ep for ep in matched if ep.get("param_value") is not None]
    if id_based:
        other_endpoints = [ep for ep in matched if ep.get("param_value") is None]
        return id_based[:max_id_based] + other_endpoints[:max_other] if len(id_based) <= max_id_based else id_based[:max_id_based]
    
    return matched[:default_limit]


# --------------------------------------------------------------
# LLM: Parse sequential query into operations
# --------------------------------------------------------------
async def parse_sequential_query(query: str, config: Dict = None) -> List[str]:
    """Use LLM to parse query into sequential operations"""
    config = config or CONFIG
    
    prompt = f"""Parse this user query into separate sequential operations.

Query: "{query}"

Return ONLY a JSON array of operation strings. Example: ["Get inventory", "Get pet with ID 1"]

JSON array:"""
    
    try:
        response = await _call_llm(prompt, config)
        json_match = re.search(r'\[.*?\]', response, re.DOTALL)
        if json_match:
            operations = json.loads(json_match.group())
        else:
            operations = json.loads(response)
        
        if isinstance(operations, list) and all(isinstance(op, str) for op in operations):
            print(f"[workflow_core] Parsed {len(operations)} operation(s)")
            return [op.strip() for op in operations if op.strip()]
    except Exception as e:
        print(f"[workflow_core] LLM parsing error: {e}")
    
    # Fallback: treat as single operation
    return [query]


# --------------------------------------------------------------
# Build endpoint catalog from API specs
# --------------------------------------------------------------
def _build_endpoint_catalog(api_specs: Dict[str, Dict], config: Dict) -> List[Dict]:
    """Build a flat list of all available endpoints"""
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
                
                # Extract request body schema for POST/PUT requests
                request_body_schema = None
                request_body = op.get("requestBody", {})
                if request_body:
                    content = request_body.get("content", {})
                    # Get the first content type (usually application/json)
                    for content_type, content_schema in content.items():
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


# --------------------------------------------------------------
# LLM: Select endpoint and extract parameters for an operation
# --------------------------------------------------------------
async def _llm_plan_operation(operation: str, endpoints: List[Dict], config: Dict) -> Optional[Dict]:
    """Use LLM to select endpoint and extract all parameters for an operation"""
    
    # Build endpoint descriptions with full context
    endpoint_list = []
    for ep in endpoints:
        desc = f"{ep['idx']}: {ep['method']} {ep['path']}"
        if ep['operation_id']:
            desc += f"\n   Operation ID: {ep['operation_id']}"
        if ep['summary']:
            desc += f"\n   Summary: {ep['summary']}"
        if ep['description']:
            # Truncate long descriptions
            desc_text = ep['description'][:200] + "..." if len(ep['description']) > 200 else ep['description']
            desc += f"\n   Description: {desc_text}"
        if ep['path_params']:
            desc += f"\n   Path Parameters: {', '.join(ep['path_params'])}"
        if ep['query_params']:
            desc += f"\n   Query Parameters: {', '.join(ep['query_params'])}"
        if ep.get('request_body_schema'):
            # Include request body schema info
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
3. Extract path parameter values:
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
        
        # Clean response: remove markdown code blocks if present
        response = response.strip()
        if response.startswith("```"):
            # Remove markdown code blocks
            response = re.sub(r'^```(?:json)?\s*', '', response)
            response = re.sub(r'\s*```$', '', response)
            response = response.strip()
        
        # Try multiple strategies to extract JSON
        plan = None
        
        # Strategy 1: Try parsing the whole response
        try:
            plan = json.loads(response)
        except json.JSONDecodeError:
            pass
        
        # Strategy 2: Extract JSON from markdown code blocks
        if plan is None:
            code_block_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', response, re.DOTALL)
            if code_block_match:
                try:
                    plan = json.loads(code_block_match.group(1))
                except json.JSONDecodeError:
                    pass
        
        # Strategy 3: Find first complete JSON object (handle nested braces)
        if plan is None:
            # Count braces to find complete JSON object
            start_idx = response.find('{')
            if start_idx != -1:
                brace_count = 0
                end_idx = start_idx
                for i in range(start_idx, len(response)):
                    if response[i] == '{':
                        brace_count += 1
                    elif response[i] == '}':
                        brace_count -= 1
                        if brace_count == 0:
                            end_idx = i + 1
                            break
                
                if end_idx > start_idx:
                    try:
                        json_str = response[start_idx:end_idx]
                        plan = json.loads(json_str)
                    except json.JSONDecodeError:
                        pass
        
        # Strategy 4: Last resort - try to fix common JSON issues
        if plan is None:
            # Remove common non-JSON prefixes/suffixes
            cleaned = re.sub(r'^[^{]*', '', response)
            cleaned = re.sub(r'[^}]*$', '', cleaned)
            if cleaned.startswith('{') and cleaned.endswith('}'):
                try:
                    plan = json.loads(cleaned)
                except json.JSONDecodeError:
                    pass
        
        if plan is None:
            raise ValueError("Could not parse JSON from LLM response")
        
        if not isinstance(plan, dict):
            print(f"[workflow_core] LLM returned non-dict: {type(plan)}")
            return None
        
        if plan.get("endpoint_idx") is None:
            return None
        
        idx = plan.get("endpoint_idx")
        if isinstance(idx, int) and 0 <= idx < len(endpoints):
            endpoint = endpoints[idx].copy()
            endpoint["path_params_values"] = plan.get("path_params", {})
            endpoint["query_params_values"] = plan.get("query_params", {})
            endpoint["body_values"] = plan.get("body", {})
            
            # Convert all values to strings (except arrays and objects)
            endpoint["path_params_values"] = {
                k: str(v) for k, v in endpoint["path_params_values"].items()
            }
            processed_query = {}
            for k, v in endpoint["query_params_values"].items():
                if isinstance(v, list):
                    processed_query[k] = [str(item) for item in v]
                else:
                    processed_query[k] = str(v)
            endpoint["query_params_values"] = processed_query
            
            # Body values should preserve their structure (objects, arrays, etc.)
            # No conversion needed for body_values - keep as is
            
            print(f"[workflow_core] Planned: {endpoint['method']} {endpoint['path']}")
            print(f"  Path params: {endpoint['path_params_values']}")
            print(f"  Query params: {endpoint['query_params_values']}")
            if endpoint.get("body_values"):
                print(f"  Body: {json.dumps(endpoint['body_values'], indent=2)}")
            return endpoint
        else:
            print(f"[workflow_core] Invalid endpoint index: {idx} (valid range: 0-{len(endpoints)-1})")
        
    except json.JSONDecodeError as e:
        print(f"[workflow_core] JSON decode error: {e}")
        print(f"[workflow_core] LLM response was: {response[:200]}...")
    except Exception as e:
        print(f"[workflow_core] LLM planning error: {e}")
        import traceback
        traceback.print_exc()
    
    return None


# --------------------------------------------------------------
# Execute a single API call
# --------------------------------------------------------------
async def execute_api_call(endpoint: Dict, query: str = "", previous_data: Any = None, config: Dict = None) -> Dict[str, Any]:
    """Execute API call with planned endpoint and parameters
    
    Supports both LLM-based planning (path_params_values/query_params_values) 
    and keyword-based matching (param_value/path_params) endpoint structures
    """
    config = config or CONFIG
    path = endpoint["path"]
    base_url = endpoint.get("base_url", "")
    
    # Handle LLM-based planning structure (Mode 2)
    if "path_params_values" in endpoint or "query_params_values" in endpoint or "body_values" in endpoint:
        # Replace path parameters
        path_params = endpoint.get("path_params_values", {})
        for param_name, param_value in path_params.items():
            path = path.replace(f"{{{param_name}}}", str(param_value))
        
        # Build URL
        url = base_url.rstrip("/") + path
        
        # Add query parameters
        query_params = endpoint.get("query_params_values", {})
        if query_params:
            query_parts = []
            for param_name, param_value in query_params.items():
                if isinstance(param_value, list):
                    for val in param_value:
                        query_parts.append(f"{param_name}={quote(str(val))}")
                else:
                    query_parts.append(f"{param_name}={quote(str(param_value))}")
            url += "?" + "&".join(query_parts)
        
        method = endpoint.get("method", "GET").upper()
        body_data = endpoint.get("body_values", {})
        
    else:
        # Handle keyword-based matching structure (Mode 1)
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
        body_data = None  # No body for keyword-based matching (Mode 1)
    
    timeout = config.get("timeouts", {}).get("api_call", 30.0)
    
    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            # Only send body if it's not None and not empty
            has_body = body_data is not None and body_data != {}
            headers = {"Content-Type": "application/json"} if has_body else {}
            
            if method == "GET":
                response = await client.get(url)
            elif method == "POST":
                if has_body:
                    response = await client.post(url, json=body_data, headers=headers)
                else:
                    response = await client.post(url)
            elif method == "PUT":
                if has_body:
                    response = await client.put(url, json=body_data, headers=headers)
                else:
                    response = await client.put(url)
            elif method == "DELETE":
                response = await client.delete(url)
            else:
                response = await client.get(url)  # Default to GET
            
            if response.status_code == 200:
                try:
                    return {"success": True, "data": response.json()}
                except:
                    return {"success": True, "data": response.text}
            else:
                error_text_truncate = config.get("limits", {}).get("error_text_truncate", 200)
                error_msg_truncate = config.get("limits", {}).get("error_message_truncate", 150)
                error_text = response.text[:error_text_truncate] if response.text else ""
                return {"success": False, "error": f"HTTP {response.status_code}: {error_text}"}
    except Exception as e:
        error_msg_truncate = config.get("limits", {}).get("error_message_truncate", 150)
        return {"success": False, "error": str(e)[:error_msg_truncate]}


# --------------------------------------------------------------
# MAIN WORKFLOW ENGINE - LLM-Driven
# --------------------------------------------------------------
async def execute_multi_stage_workflow(query: str, mounted_servers: List[FastMCP],
                                       server_configs: List[Dict], config: Dict = None) -> Dict[str, Any]:
    """Execute workflow using LLM for all planning and parameter extraction"""
    
    config = config or CONFIG
    
    results = {
        "query": query,
        "stages": [],
        "final_result": None,
        "errors": []
    }
    
    # Load API specs
    api_specs = await get_api_specs(server_configs, config)
    if not api_specs:
        results["final_result"] = {"summary": "No API specs loaded"}
        return results
    
    # Build endpoint catalog
    endpoints = _build_endpoint_catalog(api_specs, config)
    if not endpoints:
        results["final_result"] = {"summary": "No endpoints found"}
        return results
    
    # Parse query into operations (LLM)
    operations = await parse_sequential_query(query, config)
    
    # Execute each operation sequentially
    combined_data = []
    previous_data = None
    
    for stage_num, operation in enumerate(operations, 1):
        # Plan operation: select endpoint and extract parameters (LLM)
        planned_endpoint = await _llm_plan_operation(operation, endpoints, config)
        
        if not planned_endpoint:
            results["stages"].append({
                "stage": stage_num,
                "operation": operation,
                "status": "failed",
                "result": {"success": False, "error": "No matching endpoint found"}
            })
            results["errors"].append(f"Operation '{operation}': No matching endpoint")
            continue
        
        # Execute API call
        # FIXED: Added missing parameters (operation and previous_data)
        result = await execute_api_call(planned_endpoint, operation, previous_data, config)
        
        results["stages"].append({
            "stage": stage_num,
            "operation": operation,
            "endpoint": planned_endpoint["path"],
            "api": planned_endpoint["server_name"],
            "status": "completed" if result["success"] else "failed",
            "result": result
        })
        
        if result["success"]:
            combined_data.append(result["data"])
            previous_data = result["data"]
        else:
            results["errors"].append(f"Operation '{operation}': {result.get('error', 'Unknown error')}")
    
    # Final result
    results["final_result"] = {
        "combined": True,
        "execution_mode": "sequential",
        "success_count": len(combined_data),
        "failed_count": len(results["stages"]) - len(combined_data),
        "results": combined_data
    }
    
    return results
