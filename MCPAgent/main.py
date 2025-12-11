import httpx
import json
import re
import os
import asyncio
from typing import List, Dict, Any, Optional
from fastmcp import FastMCP

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
    result = default.copy()
    for k, v in override.items():
        if k in result and isinstance(result[k], dict) and isinstance(v, dict):
            result[k] = _deep_merge(result[k], v)
        else:
            result[k] = v
    return result

def load_config(config_path: str = "config.json") -> Dict[str, Any]:
    default_config = {
        "server": {"host": "0.0.0.0", "port": 8000, "name": "Generic MCP Gateway"},
        "endpoints": {
            "max_parameterized_endpoints": 50,
            "max_other_endpoints": 5,
            "default_endpoint_limit": 10,
            "allowed_methods": ["GET"]
        },
        "timeouts": {
            "api_spec_load": 10.0,
            "api_call": 30.0,
            "openapi_fetch": 5.0
        },
        "llm": {
            "aws_region": "us-east-2",
            "model_id": "us.amazon.nova-pro-v1:0",
            "enabled": True
        },
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
        },
        "display": {"separator_length": 60},
        "servers_config_file": "servers.json"
    }

    if os.path.exists(config_path):
        try:
            with open(config_path, "r") as f:
                user_cfg = json.load(f)
                default_config = _deep_merge(default_config, user_cfg)
        except:
            pass

    if os.getenv("AWS_REGION"):
        default_config["llm"]["aws_region"] = os.getenv("AWS_REGION")

    if os.getenv("BEDROCK_MODEL_ID"):
        default_config["llm"]["model_id"] = os.getenv("BEDROCK_MODEL_ID")

    return default_config

def load_server_configs(path: str) -> List[Dict]:
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r") as f:
            return json.load(f)
    except:
        return []

CONFIG = load_config()

class ModeSelector:
    def __init__(self, mounted_servers, server_configs, config=None):
        self.mounted_servers = mounted_servers
        self.server_configs = server_configs
        self.config = config or CONFIG
        self.classification_llm = None
        self._init_llm()

    def _init_llm(self):
        if not self.config["llm"]["enabled"]:
            return

        import boto3
        try:
            region = self.config["llm"]["aws_region"]
            model_id = self.config["llm"]["model_id"]

            session = boto3.Session(region_name=region)
            client = session.client("bedrock-runtime", region_name=region)

            self.classification_llm = ChatBedrock(
                region_name=region,
                model_id=model_id,
                client=client
            )
            print("✓ Bedrock LLM Initialized")
        except Exception as e:
            print("✗ Bedrock Init Failed:", e)
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
        mode_cfg = self.config["mode_selection"]
        keywords = mode_cfg["mode_2_keywords"]
        
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

    async def handle_mode_1(self, prompt: str):
        print("[MODE 1] Single-step API call")

        from workflow_core import get_api_specs, find_matching_endpoints, execute_api_call

        api_specs = await get_api_specs(self.server_configs, CONFIG)
        endpoints = await find_matching_endpoints(prompt, api_specs, CONFIG)

        if not endpoints:
            return {"success": False, "error": "No endpoint matched"}

        ep = endpoints[0]
        result = await execute_api_call(ep, prompt, None, CONFIG)

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
                "server_configs": self.server_configs
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

        spec = httpx.get(spec_url, timeout=CONFIG["timeouts"]["openapi_fetch"]).json()

        if not base_url.startswith("http"):
            raise ValueError("base_url must start with http:// or https://")

        from workflow_core import _extract_base_url_from_spec
        base_url = _extract_base_url_from_spec(spec, base_url)

        client = httpx.AsyncClient(base_url=base_url)
        server = FastMCP.from_openapi(openapi_spec=spec, client=client, name=name)

        print(f"✓ Loaded {name} [{base_url}]")
        return server
    except Exception as e:
        print(f"✗ Failed loading {name}: {e}")
        return None

def main(config_path="config.json"):
    config = load_config(config_path)

    server_cfg_path = config["servers_config_file"]
    server_configs = load_server_configs(server_cfg_path)

    if not server_configs:
        print("✗ No servers configured.")
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
        print("✗ No API servers loaded.")
        return

    master_name = config["server"]["name"]
    main_server = FastMCP(name=master_name)

    for s in servers:
        main_server.mount(s)

    mode_selector = ModeSelector(servers, server_configs, config)

    @main_server.tool()
    async def agent_orchestrate(query: str) -> str:
        """Master MCP Tool – Decides Mode 1 vs Mode 2"""
        result = await mode_selector.route(query)
        return json.dumps(result, indent=2)

    host = config["server"]["host"]
    port = config["server"]["port"]
    sep = config["display"]["separator_length"]

    print("\n" + "=" * sep)
    print(f"✓ {master_name} Ready")
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
