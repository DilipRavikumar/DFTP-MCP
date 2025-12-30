import json
import os
import asyncio
from typing import Any, Dict, Optional
from typing_extensions import TypedDict

from langgraph.graph import StateGraph, START, END
from langchain_aws import ChatBedrock
from langchain_mcp_adapters.client import MultiServerMCPClient


# -------------------------------------------------
# CONFIG
# -------------------------------------------------
MCP_GATEWAY_URL = "http://127.0.0.1:8000/mcp"
ROUTER_MODEL_ID = os.getenv("ROUTER_MODEL_ID", "us.amazon.nova-pro-v1:0")
AWS_REGION = os.getenv("AWS_REGION", "us-east-2")

ALLOWED_SCOPES = ["MutualFunds", "Assets", "Wealth", "General", "ACCOUNT_MANAGER"]


# -------------------------------------------------
# MCP HELPERS
# -------------------------------------------------
def build_mcp_client():
    return MultiServerMCPClient({
        "gateway": {"transport": "streamable_http", "url": MCP_GATEWAY_URL}
    })


async def get_mcp_tools(client):
    try:
        return await client.get_tools()
    except:
        return []


# -------------------------------------------------
# SCOPE HANDLING
# -------------------------------------------------
def extract_scope(request: str):
    """
    Format expected:
        SCOPE:Wealth | REQUEST:Get details for account X
    """
    scope = "unknown"
    actual = request

    if "SCOPE:" in request and "|REQUEST:" in request:
        parts = request.split("|")
        for p in parts:
            p = p.strip()
            if p.startswith("SCOPE:"):
                scope = p.replace("SCOPE:", "").strip()
            elif p.startswith("REQUEST:"):
                actual = p.replace("REQUEST:", "").strip()

    return scope, actual


def validate_scope(scope: str) -> bool:
    return scope in ALLOWED_SCOPES


# -------------------------------------------------
# LLM + TOOL FUNCTIONS
# -------------------------------------------------
def llm_invoke(model, prompt: str) -> str:
    """Simple synchronous wrapper."""
    try:
        res = asyncio.run(model.ainvoke(prompt))
        return getattr(res, "content", str(res))
    except:
        res = model.invoke(prompt)
        return getattr(res, "content", str(res))


def call_mcp_tool(tools, tool_name, args):
    tool_map = {t.name.lower(): t for t in tools}
    tool = tool_map.get(tool_name.lower())
    if not tool:
        return {"error": f"Tool '{tool_name}' not found"}

    try:
        return asyncio.run(tool.ainvoke(args))
    except Exception as e:
        return {"error": str(e)}


# -------------------------------------------------
# LANGGRAPH STATE
# -------------------------------------------------
class RouterState(TypedDict):
    user_input: str
    tool_name: Optional[str]
    arguments: Dict[str, Any]
    result: Optional[Any]
    message: Optional[str]


# -------------------------------------------------
# ROUTER GRAPH
# -------------------------------------------------
def build_router_graph(router_model, tools):
    def llm_node(state: RouterState):
        tool_list = "\n".join(f"- {t.name}" for t in tools)
        system_prompt = (
            "You are a TOOL ROUTER.\n"
            "Select EXACTLY ONE MCP tool.\n"
            "Respond ONLY in JSON:\n"
            '{ "tool_name": <string|null>, "arguments": { ... } }\n\n'
            "Available tools:\n" + tool_list
        )

        text = llm_invoke(router_model, system_prompt + "\n\nUser: " + state["user_input"])

        try:
            data = json.loads(text)
        except:
            return {"tool_name": None, "arguments": {}, "message": "Router JSON error"}

        return {
            "tool_name": data.get("tool_name"),
            "arguments": data.get("arguments", {}),
            "result": None,
            "message": None,
        }

    def tool_node(state: RouterState):
        if not state["tool_name"]:
            return {"result": None, "message": "No tool selected"}

        result = call_mcp_tool(tools, state["tool_name"], state["arguments"])
        return {"result": result, "message": f"Executed {state['tool_name']}"}

    def should_call_tool(state: RouterState):
        return "tool_node" if state.get("tool_name") else END

    graph = StateGraph(RouterState)
    graph.add_node("llm_node", llm_node)
    graph.add_node("tool_node", tool_node)
    graph.add_edge(START, "llm_node")
    graph.add_conditional_edges("llm_node", should_call_tool, ["tool_node", END])
    graph.add_edge("tool_node", END)

    return graph.compile()


# -------------------------------------------------
# MAIN REQUEST FUNCTION (public entry)
# -------------------------------------------------
def process_request(request: str) -> str:
    # ------------------------------------------
    # Extract & validate SCOPE
    # ------------------------------------------
    scope, actual_request = extract_scope(request)

    if not validate_scope(scope):
        return f"Unauthorized: Scope '{scope}' is not allowed."

    # ------------------------------------------
    # Load MCP tools
    # ------------------------------------------
    client = build_mcp_client()
    try:
        tools = asyncio.run(get_mcp_tools(client))
    except:
        tools = []

    # ------------------------------------------
    # Build router agent
    # ------------------------------------------
    router_model = ChatBedrock(model_id=ROUTER_MODEL_ID, region_name=AWS_REGION)
    agent = build_router_graph(router_model, tools)

    init_state: RouterState = {
        "user_input": actual_request,
        "tool_name": None,
        "arguments": {},
        "result": None,
        "message": None,
    }

    # ------------------------------------------
    # Run graph
    # ------------------------------------------
    final = agent.invoke(init_state)

    if final.get("result"):
        return json.dumps(final["result"], indent=2)
    return final.get("message", "No response")


# -------------------------------------------------
# OPTIONAL CLI
# -------------------------------------------------
if __name__ == "__main__":
    print("Agent Ready.\n")
    while True:
        text = input("You: ").strip()
        if text.lower() == "exit":
            break
        print("→", process_request(text))
