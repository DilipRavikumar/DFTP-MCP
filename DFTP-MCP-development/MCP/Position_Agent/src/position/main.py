#!/usr/bin/env python3
from typing import Any, Dict
import re
import json
import os
import asyncio
import traceback
import sys
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain.tools import BaseTool
from langchain_aws import ChatBedrock

def get_auth_service():
    try:
        current_dir = os.path.dirname(os.path.abspath(__file__))
        mcp_root = os.path.abspath(os.path.join(current_dir, "..", "..", ".."))
        if mcp_root not in sys.path:
            sys.path.append(mcp_root)
        from Authorization_Agent.auth_service import get_roles_from_token
        return get_roles_from_token
    except Exception:
        return None

def check_distributor_role() -> bool:
    return False

ALLOWED_SCOPES = ["MutualFunds", "Assets", "Wealth"]

def extract_scope_from_request(request: str) -> tuple[str, str]:
    if request.startswith("SCOPE:"):
        parts = request.split("|REQUEST:", 1)
        if len(parts) == 2:
            scope = parts[0].replace("SCOPE:", "").split("|ROLES:")[0]
            return scope, parts[1]
    return "unauthorized", request

def validate_scope(scope: str) -> bool:
    return scope in ALLOWED_SCOPES

def build_mcp_client() -> MultiServerMCPClient:
    mcp_url = os.getenv("MCP_URL", "http://127.0.0.1:8000/mcp")
    return MultiServerMCPClient(
        {
            "positions_gateway": {
                "transport": "streamable_http",
                "url": mcp_url,
            }
        }
    )

def call_mcp_tool_sync(tools, keyword: str, payload: Dict[str, Any]) -> Any:
    for t in tools:
        name = getattr(t, "name", None) or getattr(t, "tool_name", None) or t.__class__.__name__
        if keyword.lower() in name.lower():
            if hasattr(t, "ainvoke"):
                return asyncio.run(t.ainvoke(payload))
            return t.invoke(payload)
    raise RuntimeError(f"MCP tool '{keyword}' not found")

def normalize_mcp_response(obj: Any) -> Dict[str, Any]:
    """
    Converts LangChain/MCP tool outputs into plain JSON dicts
    so Spring Boot can deserialize them correctly.
    """

    if isinstance(obj, list) and len(obj) > 0:
        first = obj[0]
        if isinstance(first, dict) and "text" in first:
            return json.loads(first["text"])

    if isinstance(obj, dict):
        if "text" in obj:
            return json.loads(obj["text"])
        if "content" in obj:
            return json.loads(obj["content"])
        return obj

    if isinstance(obj, str):
        return json.loads(obj)

    raise ValueError(f"Unable to normalize MCP response: {obj}")

def parse_user_input(text: str) -> Dict[str, Any]:
    client = fund = amount = date = None

    m = re.search(r"\bfund(?:\s*number|\s*no)?\s*(\d{1,6})\b", text, re.I)
    if m:
        fund = int(m.group(1))

    m = re.search(
        r"(?:amount|invest|investing|put|₹|\$|rs\.?|inr)\s*[:\-]?\s*([\d,]+(?:\.\d+)?)",
        text,
        re.I,
    )
    if m:
        amount = float(m.group(1).replace(",", ""))

    if amount is None:
        nums = re.findall(r"\d+(?:\.\d+)?", text)
        for n in nums:
            if "." in n:
                amount = float(n)
                break

    m = re.search(r"(?:client|for)\s+([A-Z][a-zA-Z]{1,30})", text)
    if m:
        client = m.group(1)
    else:
        m = re.search(r"\b([A-Z][a-z]{2,30})\b", text)
        if m:
            client = m.group(1)

    m = re.search(r"(\d{4}-\d{2}-\d{2})", text)
    if m:
        date = m.group(1)

    return {
        "clientName": client,
        "fundNumber": fund,
        "dollarAmount": amount,
        "asOfDate": date,
    }

def llm_invoke_sync(model, prompt: str) -> str:
    if hasattr(model, "ainvoke"):
        resp = asyncio.run(
            model.ainvoke({"messages": [{"role": "user", "content": prompt}]})
        )
        return resp.content
    return model.invoke(prompt).content

def parse_with_llm_fallback(text: str, model) -> Dict[str, Any]:
    parsed = parse_user_input(text)

    if (
        parsed["clientName"]
        and parsed["fundNumber"] is not None
        and parsed["dollarAmount"] is not None
    ):
        return parsed

    prompt = (
        "Extract exactly this JSON. Use null if missing. Return JSON only.\n\n"
        "{\n"
        '  "clientName": string | null,\n'
        '  "fundNumber": number | null,\n'
        '  "dollarAmount": number | null,\n'
        '  "asOfDate": string | null\n'
        "}\n\n"
        f"User request: {text}"
    )

    raw = llm_invoke_sync(model, prompt)
    start = raw.find("{")
    end = raw.rfind("}") + 1
    return json.loads(raw[start:end])

class ProcessOrderTool(BaseTool):
    name: str = "process_position_request"
    description: str = (
        "Parses request with LLM, submits order, "
        "fetches NAV, and calculates position using MCP tools."
    )

    def _run(self, request: str) -> str:
        scope, actual_request = extract_scope_from_request(request)

        if not validate_scope(scope):
            return f"Unauthorized: invalid scope '{scope}'"

        model = ChatBedrock(
            model_id=os.getenv("BEDROCK_MODEL_ID", "us.amazon.nova-pro-v1:0"),
            region_name=os.getenv("AWS_REGION", "us-east-2"),
        )

        parsed = parse_with_llm_fallback(actual_request, model)

        client = build_mcp_client()
        tools = asyncio.run(client.get_tools())

        submit_raw = call_mcp_tool_sync(tools, "receive", parsed)
        submit = normalize_mcp_response(submit_raw)

        nav_raw = call_mcp_tool_sync(
            tools,
            "nav",
            {"fundNumber": parsed["fundNumber"], "asOfDate": parsed.get("asOfDate")}
        )
        nav = normalize_mcp_response(nav_raw)

        position_raw = call_mcp_tool_sync(
            tools,
            "calculate",
            {"order": submit, "nav": nav}
        )
        position = normalize_mcp_response(position_raw)

        return json.dumps(
            {
                "submit_result": submit,
                "nav_result": nav,
                "position_result": position,
            },
            indent=2,
        )

    async def _arun(self, request: str) -> str:
        raise NotImplementedError

def process_request(request: str) -> str:
    try:
        return ProcessOrderTool().run(request)
    except Exception:
        return traceback.format_exc()

if __name__ == "__main__":
    print("Type your request, or 'exit' to quit.\n")

    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nBye!")
            break

        if not user_input:
            continue

        if user_input.lower() in ("exit", "quit"):
            print("Bye!")
            break

        result = process_request(user_input)
        print("\nAgent response:")
        print(result)
        print("\n" + "-" * 60 + "\n")

