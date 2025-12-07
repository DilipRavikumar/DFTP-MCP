from langgraph.graph import StateGraph, END
from agents import MCPAgent_Node, extract_token_and_scope
from typing import TypedDict, Optional
from schema import State


def authorization_node(state: State) -> State: 
    _, scope = extract_token_and_scope(state["prompt"])
    print(f"Extracted scope: {scope}")
    return {**state, "scope": scope}

def mcp_agent_node_wrapper(state: State) -> State:
    new_result = MCPAgent_Node(state) 
    print("MCP Node: Request Processed")
    return new_result

def build_graph() -> StateGraph:
    graph = StateGraph(State)
    graph.add_node("authorization_node", authorization_node)
    graph.add_node("mcp_agent_node", mcp_agent_node_wrapper)

    graph.set_entry_point("authorization_node")
    graph.add_edge("authorization_node", "mcp_agent_node")
    graph.add_edge("mcp_agent_node", END)

    return graph.compile()