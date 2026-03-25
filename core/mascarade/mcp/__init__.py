"""MCP clients and server for Mascarade core."""

from mascarade.mcp.client import (
    McpCallError,
    McpRuntimeClient,
    McpServerUnavailable,
    McpToolResult,
)
from mascarade.mcp.kicad_servers import (
    KICAD_MCP_SERVERS,
)
from mascarade.mcp.kicad_servers import (
    discover_installed as discover_kicad_servers,
)
from mascarade.mcp.kicad_servers import (
    get_server_config as get_kicad_server_config,
)
from mascarade.mcp.kicad_seeed import (
    SEEED_TOOLS,
    is_available as is_seeed_kicad_available,
    get_server_config as get_seeed_kicad_config,
    resolve_tool as resolve_seeed_kicad_tool,
)
from mascarade.mcp.server import McpServer

__all__ = [
    "KICAD_MCP_SERVERS",
    "McpCallError",
    "McpRuntimeClient",
    "McpServer",
    "McpServerUnavailable",
    "McpToolResult",
    "SEEED_TOOLS",
    "discover_kicad_servers",
    "get_kicad_server_config",
    "get_seeed_kicad_config",
    "is_seeed_kicad_available",
    "resolve_seeed_kicad_tool",
]
