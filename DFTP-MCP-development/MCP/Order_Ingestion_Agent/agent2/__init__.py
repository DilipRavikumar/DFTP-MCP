"""
Order Ingestion Agent with Non-Deterministic Tool Routing
"""

__version__ = "0.2.0"
__description__ = "Order Ingestion Agent with LLM-based Tool Selection and File Upload Capability"

# Public API exports
from .TradeSimulateSpecific import (
    build_mcp_client,
    process_request,
)

__all__ = [
    "build_mcp_client",
    "process_request",
]
