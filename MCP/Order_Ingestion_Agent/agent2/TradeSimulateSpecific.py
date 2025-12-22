import os
import re
import json
import asyncio
import base64
from typing import Any, Dict, Optional
from typing_extensions import TypedDict

from langgraph.graph import StateGraph, START, END
from langchain_aws import ChatBedrock
from langchain_mcp_adapters.client import MultiServerMCPClient

# =====================================================
# CONFIG
# =====================================================
MCP_GATEWAY_URL = "http://127.0.0.1:8000/mcp"
ROUTER_MODEL_ID = os.getenv("ROUTER_MODEL_ID", "us.amazon.nova-pro-v1:0")
AWS_REGION = os.getenv("AWS_REGION", "us-east-2")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FILES_DIR = os.path.join(BASE_DIR, "..", "files")
os.makedirs(FILES_DIR, exist_ok=True)

# 🔐 HARD TOOL ALLOW-LIST
ALLOWED_TOOLS = {"uploadSingleFile", "runSimulation"}

# =====================================================
# MCP HELPERS
# =====================================================
def build_mcp_client():
    return MultiServerMCPClient(
        {"gateway": {"transport": "streamable_http", "url": MCP_GATEWAY_URL}}
    )

async def get_mcp_tools(client):
    return await client.get_tools()

def call_mcp_tool(tools, tool_name, args):
    tool_map = {t.name: t for t in tools}
    tool = tool_map.get(tool_name)

    if not tool:
        return {"error": f"Tool '{tool_name}' not found"}

    try:
        return asyncio.run(tool.ainvoke(args))
    except Exception as e:
        return {"error": str(e)}

# =====================================================
# STATE
# =====================================================
class AgentState(TypedDict):
    user_input: str
    prepared_payload: Optional[Dict[str, Any]]
    tool_name: Optional[str]
    arguments: Dict[str, Any]
    result: Optional[Any]
    message: Optional[str]

# =====================================================
# FILE PREPARATION (DETERMINISTIC)
# =====================================================
def prepare_file_payload(user_input: str) -> Optional[Dict[str, Any]]:
    match = re.search(
        r'([A-Za-z0-9_\-./\\]+\.(csv|txt|json|xml|zip|dat))',
        user_input,
        re.I,
    )
    if not match:
        return None

    filename = os.path.basename(match.group(1))
    path = os.path.join(FILES_DIR, filename)

    if not os.path.exists(path):
        return None

    with open(path, "rb") as f:
        encoded = base64.b64encode(f.read()).decode("utf-8")

    return {
        "filename": filename,
        "fileBase64": encoded,
        "key": filename,
    }

# =====================================================
# AGENT GRAPH
# =====================================================
def build_agent_graph(router_model, tools):

    # ----------------------------
    # FILE PREP NODE
    # ----------------------------
    def prepare_node(state: AgentState):
        payload = prepare_file_payload(state["user_input"])
        return {"prepared_payload": payload}

    # ----------------------------
    # ROUTER NODE (LLM)
    # ----------------------------
    def router_node(state: AgentState):
        tool_list = "\n".join(f"- {t.name}" for t in tools if t.name in ALLOWED_TOOLS)

        prompt = (
            "You are a TOOL ROUTER.\n"
            "Select EXACTLY ONE tool.\n\n"
            "RULES:\n"
            "- Respond with VALID JSON ONLY\n"
            "- NO markdown\n"
            "- NO explanation\n"
            "- If no tool applies, return {\"tool_name\": null}\n"
            "- Use uploadSingleFile ONLY if file payload exists\n\n"
            f"Available tools:\n{tool_list}\n\n"
            f"User request:\n{state['user_input']}\n\n"
            f"Prepared payload present: {state['prepared_payload'] is not None}\n\n"
            'Return JSON:\n{ "tool_name": "<string|null>" }'
        )

        response = router_model.invoke(prompt)
        raw = response.content.strip()

        # Defensive cleanup
        if raw.startswith("```"):
            raw = raw.split("```")[1]

        try:
            data = json.loads(raw)
        except Exception:
            return {
                "tool_name": None,
                "arguments": {},
                "message": "Invalid router output"
            }

        tool_name = data.get("tool_name")

        if tool_name not in ALLOWED_TOOLS:
            return {
                "tool_name": None,
                "arguments": {},
                "message": "Tool not allowed"
            }

        return {
            "tool_name": tool_name,
            "arguments": {}
        }

    # ----------------------------
    # TOOL EXECUTION NODE
    # ----------------------------
    def tool_node(state: AgentState):
        if not state["tool_name"]:
            return {"message": "No tool selected"}

        if state["tool_name"] == "uploadSingleFile":
            if not state["prepared_payload"]:
                return {"message": "No file payload available"}
            args = state["prepared_payload"]
        else:
            args = state["arguments"]

        result = call_mcp_tool(tools, state["tool_name"], args)
        return {"result": result, "message": f"Executed {state['tool_name']}"}

    # ----------------------------
    # GRAPH WIRING
    # ----------------------------
    graph = StateGraph(AgentState)

    graph.add_node("prepare", prepare_node)
    graph.add_node("router", router_node)
    graph.add_node("tool", tool_node)

    graph.add_edge(START, "prepare")
    graph.add_edge("prepare", "router")

    graph.add_conditional_edges(
        "router",
        lambda s: "tool" if s.get("tool_name") else END,
        ["tool", END],
    )

    graph.add_edge("tool", END)

    return graph.compile()

# =====================================================
# PUBLIC ENTRY
# =====================================================
def process_request(text: str) -> str:
    client = build_mcp_client()
    tools = asyncio.run(get_mcp_tools(client))

    router_model = ChatBedrock(
        model_id=ROUTER_MODEL_ID,
        region_name=AWS_REGION,
        temperature=0.2,  # low but non-deterministic
    )

    agent = build_agent_graph(router_model, tools)

    state: AgentState = {
        "user_input": text,
        "prepared_payload": None,
        "tool_name": None,
        "arguments": {},
        "result": None,
        "message": None,
    }

    final = agent.invoke(state)

    if final.get("result"):
        return json.dumps(final["result"], indent=2)

    return final.get("message", "No response")

# =====================================================
# CLI (OPTIONAL)
# =====================================================
if __name__ == "__main__":
    print("✅ Non-Deterministic Order Ingestion Agent Ready\n")
    while True:
        user = input("You: ").strip()
        if user.lower() in ("exit", "quit"):
            break
        print(process_request(user))
