import httpx
import json
import re
import os
import asyncio
import boto3
from typing import List, Dict, Any, Optional
from fastmcp import FastMCP
from langchain_aws import ChatBedrock
from dotenv import load_dotenv

load_dotenv()

def load_config(config_path: str = "config.json") -> Dict[str, Any]:
    minimal_defaults = {
        "server": {"host": "0.0.0.0", "port": 8000, "name": "Generic MCP Gateway"},
        "llm": {"enabled": False}
    }
    
    if not os.path.exists(config_path):
        print(f"Warning: {config_path} not found. Using minimal defaults.")
        return minimal_defaults
    
    try:
        with open(config_path, "r") as f:
            config = json.load(f)
        
        if os.getenv("AWS_REGION"):
            if "llm" not in config:
                config["llm"] = {}
            config["llm"]["aws_region"] = os.getenv("AWS_REGION")
        
        if os.getenv("BEDROCK_MODEL_ID"):
            if "llm" not in config:
                config["llm"] = {}
            config["llm"]["model_id"] = os.getenv("BEDROCK_MODEL_ID")
        
        return config
    except Exception as e:
        print(f"Error loading config: {e}")
        return minimal_defaults

def load_server_configs(config: Dict[str, Any]) -> List[Dict]:
    if "servers" in config and isinstance(config["servers"], list):
        return config["servers"]
    
    servers_file = config.get("servers_config_file", "servers.json")
    if os.path.exists(servers_file):
        try:
            with open(servers_file, "r") as f:
                servers_data = json.load(f)
                if isinstance(servers_data, list):
                    return servers_data
                elif isinstance(servers_data, dict) and "servers" in servers_data:
                    return servers_data["servers"]
        except Exception as e:
            print(f" Warning: Could not load {servers_file}: {e}")
    
    return []

CONFIG = load_config()

class ModeSelector:
    def __init__(self, mounted_servers, server_configs, config=None, main_server=None):
        self.mounted_servers = mounted_servers
        self.server_configs = server_configs
        self.config = config or CONFIG
        self.main_server = main_server
        self.classification_llm = None
        self._init_llm()

    def _init_llm(self):
        if not self.config.get("llm", {}).get("enabled", False):
            return

        try:
            region = self.config.get("llm", {}).get("aws_region", "us-east-2")
            model_id = self.config.get("llm", {}).get("model_id", "us.amazon.nova-pro-v1:0")

            session = boto3.Session(region_name=region)
            client = session.client("bedrock-runtime", region_name=region)

            self.classification_llm = ChatBedrock(
                region_name=region,
                model_id=model_id,
                client=client
            )
            print(" Bedrock LLM Initialized")
        except Exception as e:
            print(" Bedrock Init Failed:", e)
            self.classification_llm = None

    async def _invoke_llm(self, prompt: str) -> str:
        try:
            if hasattr(self.classification_llm, "ainvoke"):
                res = await self.classification_llm.ainvoke(prompt)
            else:
                res = await asyncio.to_thread(self.classification_llm.invoke, prompt)
            return res.content.strip().lower()
        except:
            return ""

    async def analyze_prompt(self, prompt: str) -> str:
        prompt = prompt.strip()
        prompt_lower = prompt.lower()
        mode_cfg = self.config.get("mode_selection", {})
        keywords = mode_cfg.get("mode_2_keywords", ["and then", "then", "multiple", "chain"])
        
        range_pattern = r'\d+\s*(?:-|to|through|until)\s*\d+'
        quoted_list = r'"[^"]+"\s*,\s*"[^"]+"'
        comma_sep = r'\b\w+\s*,\s*\w+'
        
        if re.search(range_pattern, prompt_lower) or re.search(quoted_list, prompt) or re.search(comma_sep, prompt_lower):
            print(f"[ModeSelector] Parameter pattern detected, routing to mode_2")
            return "mode_2"
        
        if any(k in prompt_lower for k in keywords):
            print(f"[ModeSelector] Keywords detected, routing to mode_2")
            return "mode_2"

        if not self.classification_llm:
            print(f"[ModeSelector] No LLM available, defaulting to mode_1")
            return "mode_1"

        print(f"[ModeSelector] Using LLM for classification")
        classification_prompt = (
            "You are an expert API workflow classifier.\n"
            "Given the user request, classify whether it requires:\n"
            "- MODE 1: a single API call\n"
            "- MODE 2: multiple API calls, a workflow, iteration, or parallel/batch calls\n\n"
            "Important:\n"
            "- Do NOT explain your answer.\n"
            "- Do NOT justify.\n"
            "- Respond with EXACTLY one word: mode_1 or mode_2.\n"
            "Nothing more.\n\n"
            f"User request:\n{prompt}\n\n"
            "Your answer:"
        )

        try:
            response = await self._invoke_llm(classification_prompt)
            norm = response.replace(" ", "").replace("-", "").lower().strip()
            if "mode2" in norm:
                print(f"[ModeSelector] LLM classified as mode_2")
                return "mode_2"
            if "mode_1" in norm or "mode1" in norm:
                print(f"[ModeSelector] LLM classified as mode_1")
                return "mode_1"
            print(f"[ModeSelector] LLM response unclear, defaulting to mode_2")
            return "mode_2"
        except Exception as e:
            print(f"[ModeSelector] LLM error: {e}, defaulting to mode_1")
            return "mode_1"

    async def _find_mcp_tool_name(self, endpoint: Dict) -> Optional[str]:
        from workflow_core import _find_mcp_tool_name_generic
        return _find_mcp_tool_name_generic(endpoint, self.mounted_servers, self.main_server, enable_debug=True)

    async def _call_mcp_tool(self, endpoint: Dict, prompt: str, main_server) -> Dict[str, Any]:
        from workflow_core import _call_mcp_tool_workflow
        return await _call_mcp_tool_workflow(endpoint, main_server)

    async def handle_mode_1(self, prompt: str):
        print("[MODE 1] Single-step MCP tool call with LLM-based endpoint selection")

        from workflow_core import get_api_specs, _build_endpoint_catalog, _llm_plan_operation

        api_specs = await get_api_specs(self.server_configs, CONFIG)
        
        if not api_specs:
            return {"success": False, "error": "No API specs loaded"}
        
        endpoints = _build_endpoint_catalog(api_specs, CONFIG)
        
        if not endpoints:
            return {"success": False, "error": "No endpoints found in API specs"}
        
        ep = await _llm_plan_operation(prompt, endpoints, CONFIG)
        
        if not ep:
            return {"success": False, "error": "LLM planning failed - no endpoint selected"}
        
        if not self.main_server:
            return {
                "success": False,
                "error": "Main server not available for MCP tool calls"
            }
        
        result = await self._call_mcp_tool(ep, prompt, self.main_server)

        return {
            "query": prompt,
            "mode": "mode_1",
            "endpoint": ep["path"],
            "server": ep["server_name"],
            "success": result.get("success", False),
            "data": result.get("data"),
            "error": result.get("error")
        }

    async def handle_mode_2(self, prompt: str):
        print("[MODE 2] Multi-step workflow via LangGraph agent")

        from agent_graph import agent

        state = {
            "query": prompt,
            "context": {
                "servers": self.mounted_servers,
                "server_configs": self.server_configs,
                "main_server": self.main_server
            },
            "plan": "",
            "result": None
        }

        out = await agent.ainvoke(state)
        return out["result"]

    async def route(self, prompt: str):
        mode = await self.analyze_prompt(prompt)

        if mode == "mode_2":
            return await self.handle_mode_2(prompt)
        return await self.handle_mode_1(prompt)

def setup_fastmcp_server_from_openapi_spec(spec_url: str, base_url: str, name: str):
    try:
        print(f"Loading API: {name}")

        timeout = CONFIG.get("timeouts", {}).get("openapi_fetch", 5.0)
        spec = httpx.get(spec_url, timeout=timeout).json()

        if not base_url.startswith("http"):
            raise ValueError("base_url must start with http:// or https://")

        from workflow_core import _extract_base_url_from_spec
        base_url = _extract_base_url_from_spec(spec, base_url)

        client = httpx.AsyncClient(base_url=base_url)
        server = FastMCP.from_openapi(openapi_spec=spec, client=client, name=name)
        
        server._http_client = client
        server._base_url = base_url

        print(f"Loaded {name} [{base_url}]")
        return server
    except Exception as e:
        print(f"Failed loading {name}: {e}")
        return None

def main(config_path="config.json"):
    config = load_config(config_path)

    server_configs = load_server_configs(config)

    if not server_configs:
        print("No servers configured.")
        return

    servers = []
    for sc in server_configs:
        spec_url = sc.get("spec_url") or sc.get("spec_link")
        base_url = sc.get("base_url", "")
        name = sc.get("name", "Unknown API")

        server = setup_fastmcp_server_from_openapi_spec(spec_url, base_url, name)
        if server:
            servers.append(server)

    if not servers:
        print("No API servers loaded.")
        return

    master_name = config.get("server", {}).get("name", "Generic MCP Gateway")
    main_server = FastMCP(name=master_name)

    for s in servers:
        main_server.mount(s)
    
    # Store servers list on main_server for later access
    main_server._mounted_servers_list = servers

    mode_selector = ModeSelector(servers, server_configs, config, main_server)

    @main_server.tool()
    async def agent_orchestrate(query: str) -> str:
        result = await mode_selector.route(query)
        return json.dumps(result, indent=2)

    host = config.get("server", {}).get("host", "0.0.0.0")
    port = config.get("server", {}).get("port", 8000)
    sep = config.get("display", {}).get("separator_length", 60)

    print("\n" + "=" * sep)
    print(f" {master_name} Ready")
    print("=" * sep)
    print(f"Listening at http://{host}:{port}")
    print("=" * sep + "\n")

    main_server.run(
        transport="streamable-http",
        host=host,
        port=port
    )

if __name__ == "__main__":
    import sys
    cfg = sys.argv[1] if len(sys.argv) > 1 else "config.json"
    main(cfg)
