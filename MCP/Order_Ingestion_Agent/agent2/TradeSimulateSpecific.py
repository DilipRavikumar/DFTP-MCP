import os
import re
import json
import traceback
import httpx
import asyncio
from typing import Any, Dict, Optional
from typing_extensions import TypedDict

from langgraph.graph import StateGraph, START, END
from langchain_aws import ChatBedrock
from langchain_mcp_adapters.client import MultiServerMCPClient


# --------------------------------------------------------
# ENVIRONMENT VARIABLES + ALLOWED SCOPES
# --------------------------------------------------------
MCP_GATEWAY_URL = os.getenv("MCP_GATEWAY_URL", "http://127.0.0.1:8000/mcp")
ROUTER_MODEL_ID = os.getenv("ROUTER_MODEL_ID", "us.amazon.nova-pro-v1:0")
AWS_REGION = os.getenv("AWS_REGION", "us-east-2")
TRADE_SIM_URL = os.getenv("TRADE_SIMULATOR_URL", "http://localhost:8081")

ALLOWED_SCOPES = ["MutualFunds", "Assets", "ACCOUNT_MANAGER"]


# --------------------------------------------------------
# STATE DEFINITION
# --------------------------------------------------------
class CheckUploadState(TypedDict):
    user_input: str
    file_path: Optional[str]
    upload_requested: bool
    check_requested: bool
    exists_result: Optional[Any]
    upload_result: Optional[Any]
    message: Optional[str]


# --------------------------------------------------------
# SCOPE EXTRACTION & VALIDATION
# --------------------------------------------------------
def extract_scope_and_request(text: str):
    scope = "unknown"
    request = text

    if "SCOPE:" in text and "REQUEST:" in text:
        for part in text.split("|"):
            part = part.strip()
            if part.startswith("SCOPE:"):
                scope = part.replace("SCOPE:", "").strip()
            elif part.startswith("REQUEST:"):
                request = part.replace("REQUEST:", "").strip()

    return scope, request


def validate_scope(scope: str):
    return scope in ALLOWED_SCOPES


# --------------------------------------------------------
# MCP CLIENT
# --------------------------------------------------------
def build_mcp_client():
    return MultiServerMCPClient(
        {"gateway": {"transport": "streamable_http", "url": MCP_GATEWAY_URL}}
    )


# --------------------------------------------------------
# SIMPLE REQUEST PARSER
# --------------------------------------------------------
def parse_request(text: str):
    file_match = re.search(r'([\w./-]+\.(csv|txt|zip|json|xml|dat))', text)
    file_path = file_match.group(1) if file_match else None

    upload_flag = "upload" in text.lower()
    check_flag = "check" in text.lower() or "exists" in text.lower()

    return {
        "file_path": file_path,
        "upload_requested": upload_flag,
        "check_requested": check_flag,
    }


# --------------------------------------------------------
# EXISTENCE CHECK
# --------------------------------------------------------
def check_exists(tools, file_path: str):
    tool = next((t for t in tools if "exist" in t.name.lower()), None)
    if not tool:
        return {"error": "fileExists tool not found"}

    try:
        return asyncio.run(tool.ainvoke({"fileId": file_path}))
    except:
        return {"error": "fileExists tool failed"}


# --------------------------------------------------------
# UPLOAD TO /simulate/upload
# --------------------------------------------------------
def upload_file(file_path: str):
    file_key = os.path.basename(file_path)

    if os.path.exists(file_path):
        with open(file_path, "rb") as f:
            content = f.read()
    else:
        content = file_path.encode()

    try:
        with httpx.Client() as client:
            res = client.post(
                f"{TRADE_SIM_URL}/simulate/upload",
                params={"key": file_key},
                files={"file": (file_key, content)}
            )

        if res.status_code == 200:
            return {"s3_url": res.text.strip()}
        return {"error": res.text}

    except Exception as e:
        return {"error": str(e)}


# --------------------------------------------------------
# BUILD LANGGRAPH AGENT
# --------------------------------------------------------
def build_agent(model, tools):

    def parse_node(state):
        parsed = parse_request(state["user_input"])
        return {**parsed, "message": None}

    def exists_node(state):
        if not state["file_path"]:
            return {"exists_result": None, "message": "No file path detected"}
        return {"exists_result": check_exists(tools, state["file_path"])}

    def upload_node(state):
        if not state["file_path"]:
            return {"upload_result": None, "message": "Missing file path"}
        return {"upload_result": upload_file(state["file_path"])}

    # -------- FIXED LOGIC (NO MORE list.get() ERROR) --------
    def parse_exists_result(exists_result):
        """
        Normalizes exists_result to a boolean.
        Handles:
          - dict
          - list of dicts
          - missing values
        """
        if isinstance(exists_result, dict):
            return exists_result.get("result") is True or exists_result.get("exists") is True

        if isinstance(exists_result, list) and len(exists_result) > 0:
            first = exists_result[0]
            if isinstance(first, dict):
                return first.get("result") is True or first.get("exists") is True

        return False

    def go_exists(state):
        if state["upload_requested"] or state["check_requested"]:
            return "exists_node"
        return END

    def go_upload(state):
        exists_result = state.get("exists_result")
        exists_flag = parse_exists_result(exists_result)

        if state["upload_requested"] and not exists_flag:
            return "upload_node"
        return END
    # ---------------------------------------------------------

    graph = StateGraph(CheckUploadState)

    graph.add_node("parse_node", parse_node)
    graph.add_node("exists_node", exists_node)
    graph.add_node("upload_node", upload_node)

    graph.add_edge(START, "parse_node")
    graph.add_conditional_edges("parse_node", go_exists, ["exists_node", END])
    graph.add_conditional_edges("exists_node", go_upload, ["upload_node", END])
    graph.add_edge("upload_node", END)

    return graph.compile()


# --------------------------------------------------------
# PUBLIC FUNCTION — MAIN ENTRYPOINT FOR AGENT
# --------------------------------------------------------
def process_request(request: str) -> str:
    # Extract scope
    scope, actual_request = extract_scope_and_request(request)

    # Validate scope
    if not validate_scope(scope):
        return f"Unauthorized: Scope '{scope}' is not allowed. Allowed: {', '.join(ALLOWED_SCOPES)}"

    # Load tools
    try:
        client = build_mcp_client()
        tools = asyncio.run(client.get_tools())
    except:
        tools = []

    # Model (not heavily used)
    model = ChatBedrock(model_id=ROUTER_MODEL_ID, region_name=AWS_REGION)

    # Build graph
    agent = build_agent(model, tools)

    init_state: CheckUploadState = {
        "user_input": actual_request,
        "file_path": None,
        "upload_requested": False,
        "check_requested": False,
        "exists_result": None,
        "upload_result": None,
        "message": None,
    }

    try:
        final = agent.invoke(init_state)
    except Exception:
        return traceback.format_exc()

    # Build clean output
    out = []
    if final.get("message"): out.append(final["message"])
    if final.get("file_path"): out.append(f"File: {final['file_path']}")
    if final.get("exists_result"): out.append(f"Exists: {final['exists_result']}")
    if final.get("upload_result"): out.append(f"Upload: {final['upload_result']}")

    return "\n".join(out) or "Done."
