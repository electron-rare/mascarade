"""MCP clients and server for Mascarade core."""

from mascarade.mcp.client import (
    McpCallError,
    McpRuntimeClient,
    McpServerUnavailable,
    McpToolResult,
)
from mascarade.mcp.kicad_servers import (
    KICAD_MCP_SERVERS,
    discover_installed as discover_kicad_servers,
    get_server_config as get_kicad_server_config,
)
from mascarade.mcp.server import McpServer

__all__ = [
    "KICAD_MCP_SERVERS",
    "McpCallError",
    "McpRuntimeClient",
    "McpServer",
    "McpServerUnavailable",
    "McpToolResult",
    "discover_kicad_servers",
    "get_kicad_server_config",
]
