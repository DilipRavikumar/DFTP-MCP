"""
Trade Agent with MCP Gateway Server + LangGraph Router
"""

__version__ = "0.1.0"
__description__ = "Trade Agent with MCP Server and LangGraph-based Tool Router"

# -------------------------------------------------
# MCP Gateway Server (FastMCP)
# -------------------------------------------------
from .mcpserver import (
    setup_fastmcp_server_from_openapi_spec,
    main as run_mcp_server,
)

# -------------------------------------------------
# Trade / General Agent (LangGraph Router)
# -------------------------------------------------
from .TradeGeneralAgent import (
    build_mcp_client,
    process_request,
    RouterState,
)

__all__ = [
    # MCP server
    "setup_fastmcp_server_from_openapi_spec",
    "run_mcp_server",

    # Agent
    "build_mcp_client",
    "process_request",
    "RouterState",
]
