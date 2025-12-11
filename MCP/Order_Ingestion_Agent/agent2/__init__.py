"""Order Ingestion Agent - Agent2 Package with MCP and LangGraph Integration."""

__version__ = "0.1.0"
__description__ = "Order Ingestion Agent with File Check and Upload Capability"

# Import key functions from TradeSimulateSpecific
from .TradeSimulateSpecific import (
    build_mcp_client,
    llm_invoke_sync,
    call_mcp_tool_sync,
    build_check_and_upload_graph,
    CheckUploadState,
    process_request,
    main,
)

__all__ = [
    "build_mcp_client",
    "llm_invoke_sync",
    "call_mcp_tool_sync",
    "build_check_and_upload_graph",
    "CheckUploadState",
    "process_request",
    "main",
]