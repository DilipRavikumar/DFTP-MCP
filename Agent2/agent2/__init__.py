"""Top-level package for agent2.

A package for trading simulation and MCP server functionality.
"""

__version__ = "0.1.0"
__author__ = "Agent2 Team"

# Import from mcpserver
from .mcpserver import (
    main as run_mcp_server,
    ResponseCleaningAsyncClient,
    setup_fastmcp_server_from_openapi_spec,
    remove_none_values,
)

# Import from TradeSimulateSpecific
from .TradeSimulateSpecific import (
    main as run_trade_simulate,
    build_check_and_upload_graph,
    build_mcp_client,
    call_mcp_tool_sync,
    llm_invoke_sync,
    CheckUploadState,
)

# Define public API
__all__ = [
    # mcpserver exports
    "run_mcp_server",
    "ResponseCleaningAsyncClient",
    "setup_fastmcp_server_from_openapi_spec",
    "remove_none_values",
    # TradeSimulateSpecific exports
    "run_trade_simulate",
    "build_check_and_upload_graph",
    "build_mcp_client",
    "call_mcp_tool_sync",
    "llm_invoke_sync",
    "CheckUploadState",
    # Package metadata
    "__version__",
    "__author__",
]