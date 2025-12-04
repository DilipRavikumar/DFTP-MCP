from langgraph.graph import StateGraph, END
from agents import llm_agent
from typing import TypedDict, Optional

class State(TypedDict):
    prompt: str
    result: Optional[str]

def build_graph():
    graph = StateGraph(State)

    def router_node(state: State) -> State:
        result = llm_agent(state["prompt"])
        return {**state, "result": result}

    graph.add_node("router", router_node)
    graph.set_entry_point("router")
    graph.add_edge("router", END)

    return graph.compile()
