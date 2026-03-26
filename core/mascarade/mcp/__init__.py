"""MCP clients and server for Mascarade core."""

from mascarade.mcp.client import McpRuntimeClient
from mascarade.mcp.errors import McpCallError, McpError, McpServerUnavailable
from mascarade.mcp.kicad_seeed import (
    SEEED_TOOLS,
)
from mascarade.mcp.kicad_seeed import (
    get_server_config as get_seeed_kicad_config,
)
from mascarade.mcp.kicad_seeed import (
    is_available as is_seeed_kicad_available,
)
from mascarade.mcp.kicad_seeed import (
    resolve_tool as resolve_seeed_kicad_tool,
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
from mascarade.mcp.server import McpServer
from mascarade.mcp.server_registry import McpToolResult

__all__ = [
    "KICAD_MCP_SERVERS",
    "McpCallError",
    "McpError",
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
