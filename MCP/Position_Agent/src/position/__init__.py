"""
Position package - Orchestration and management of positions and orders.

This package provides tools for:
- Order orchestration using LangGraph
- MCP (Model Context Protocol) integration
- Position calculations and management
"""

__version__ = "0.1.0"
__all__ = [
    "main",
]

from . import main
# server is not imported by default to avoid connection side-effects

