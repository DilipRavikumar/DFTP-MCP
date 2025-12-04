# agent_graph.py

from langgraph.graph import StateGraph, END
from typing import TypedDict, Dict, Any


# --------------------------------------------------------------
# Agent State Structure
# --------------------------------------------------------------
class AgentState(TypedDict):
    query: str
    context: Dict[str, Any]     # servers + server_configs
    plan: str                   # planning text
    result: Any                 # final workflow result


# --------------------------------------------------------------
# Node 1: PLAN
# NOTE: This plan node just sets a plan string that's never used.
# The actual planning happens in execute_multi_stage_workflow in workflow_core.py.
# Keeping it for graph structure but it's not functional.
# --------------------------------------------------------------
async def plan(state: AgentState) -> Dict[str, Any]:
    query = state["query"]
    # NOTE: This plan string is set but never actually used
    return {
        "plan": f"Planning workflow for query: {query}"
    }


# --------------------------------------------------------------
# Node 2: ACT
# --------------------------------------------------------------
async def act(state: AgentState) -> Dict[str, Any]:
    # Import workflow logic (NO CIRCULAR IMPORT)
    from workflow_core import execute_multi_stage_workflow, CONFIG

    result = await execute_multi_stage_workflow(
        state["query"],
        state["context"]["servers"],          # mounted FastMCP servers
        state["context"]["server_configs"],   # entries from servers.json
        CONFIG
    )

    return {"result": result}


# --------------------------------------------------------------
# Build the LangGraph Agent
# --------------------------------------------------------------
graph = StateGraph(AgentState)

# Add nodes
graph.add_node("plan", plan)
graph.add_node("act", act)

# Entry point
graph.set_entry_point("plan")

# Workflow edges
graph.add_edge("plan", "act")
graph.add_edge("act", END)

# Compile final graph
agent = graph.compile()
