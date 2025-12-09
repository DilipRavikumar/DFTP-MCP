"""Agent1 - Trade Agent Package with MCP and LangGraph Integration."""

__version__ = "0.1.0"
__description__ = "Trade Agent with MCP Server and LangGraph Router"

# Import from mcpserver module
from .mcpserver import (
    remove_none_values,
    ResponseCleaningAsyncClient,
    setup_fastmcp_server_from_openapi_spec,
    main as run_mcp_server,
)

# Import from TradeGeneralAgent module
from .TradeGeneralAgent import (
    build_mcp_client,
    llm_invoke_sync,
    call_mcp_tool_raw,
    build_langgraph_router_graph,
    RouterState,
    main as run_trade_agent,
)

__all__ = [
    # MCP Server exports
    "remove_none_values",
    "ResponseCleaningAsyncClient",
    "setup_fastmcp_server_from_openapi_spec",
    "run_mcp_server",
    # Trade Agent exports
    "build_mcp_client",
    "llm_invoke_sync",
    "call_mcp_tool_raw",
    "build_langgraph_router_graph",
    "RouterState",
    "run_trade_agent",
]