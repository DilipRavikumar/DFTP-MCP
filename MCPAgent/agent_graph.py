from langgraph.graph import StateGraph, END
from typing import TypedDict, Dict, Any


class AgentState(TypedDict):
    query: str
    context: Dict[str, Any]
    plan: str
    result: Any


async def plan(state: AgentState) -> Dict[str, Any]:
    query = state["query"]
    return {
        "plan": f"Planning workflow for query: {query}"
    }


async def act(state: AgentState) -> Dict[str, Any]:
    from workflow_core import execute_multi_stage_workflow, CONFIG

    result = await execute_multi_stage_workflow(
        state["query"],
        state["context"]["servers"],
        state["context"]["server_configs"],
        CONFIG
    )

    return {"result": result}


graph = StateGraph(AgentState)

graph.add_node("plan", plan)
graph.add_node("act", act)

graph.set_entry_point("plan")

graph.add_edge("plan", "act")
graph.add_edge("act", END)

agent = graph.compile()
