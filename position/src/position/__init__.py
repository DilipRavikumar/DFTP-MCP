"""
Position package - Orchestration and management of positions and orders.

This package provides tools for:
- Order orchestration using LangGraph
- MCP (Model Context Protocol) integration
- Position calculations and management
- FastMCP HTTP server for API-based position management
"""

__version__ = "0.1.0"
__all__ = [
    "main",
    "server",
]

from . import main, server

__doc__ = """
The position package contains:

- main: LangGraph-based order orchestration agent with MCP integration
- server: FastMCP HTTP server for position management APIs
"""
