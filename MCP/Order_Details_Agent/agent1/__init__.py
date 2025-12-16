__version__ = "0.1.0"
__description__ = "Trade Agent with MCP Server + LangGraph Router"

# MCP server exports
from .mcpserver import (
    setup_fastmcp_server_from_openapi_spec,
    main as run_mcp_server,
)

# Trade Agent exports
from .TradeGeneralAgent import (
    build_mcp_client,
    process_request,
)

__all__ = [
    "setup_fastmcp_server_from_openapi_spec",
    "run_mcp_server",
    "build_mcp_client",
    "process_request",
]
