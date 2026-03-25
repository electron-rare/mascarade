"""Seeed Studio KiCad MCP server integration (39 tools).

This module configures the Seeed KiCad MCP server as a subprocess-based
MCP server connected via stdio transport.  It exposes all 39 tools
(analysis, validation, pin analysis, code generation, editing, project
management) and provides a fallback path to the legacy kicad_servers.py
entry when the Seeed server is unavailable.

Launch command:  ``uvx kicad-mcp-server``  (or ``python -m kicad_mcp_server``)
Repository:      https://github.com/Seeed-Studio/kicad-mcp-server
"""

from __future__ import annotations

import logging
import os
import shutil
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger("mascarade.mcp.kicad_seeed")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

_ENV_ENABLED = "KICAD_MCP_SEEED_ENABLED"
_ENV_COMMAND = "KICAD_MCP_SEEED_COMMAND"
_DEFAULT_COMMAND = "uvx kicad-mcp-server"


def _is_enabled() -> bool:
    """Return True when the Seeed KiCad MCP server integration is enabled."""
    return os.getenv(_ENV_ENABLED, "true").strip().lower() in ("1", "true", "yes")


def _resolve_command() -> tuple[str, ...]:
    """Return the shell command tokens used to start the Seeed KiCad MCP server."""
    raw = os.getenv(_ENV_COMMAND, _DEFAULT_COMMAND).strip()
    return tuple(raw.split())


# ---------------------------------------------------------------------------
# Tool catalogue — 7 categories, 39 tools
# ---------------------------------------------------------------------------

SEEED_TOOL_CATEGORIES: dict[str, list[str]] = {
    "schematic_analysis": [
        "list_schematic_components",
        "get_symbol_details",
        "search_symbols",
        "list_schematic_nets",
        "get_schematic_info",
        "search_components_by_type",
    ],
    "hierarchical_analysis": [
        "trace_hierarchical_connection",
        "analyze_hierarchical_nets",
    ],
    "pcb_analysis": [
        "list_pcb_footprints",
        "get_pcb_statistics",
        "analyze_pcb_nets",
        "find_tracks_by_net",
    ],
    "netlist_analysis": [
        "generate_netlist",
        "trace_netlist_connection",
        "get_netlist_nets",
        "get_netlist_components",
    ],
    "validation": [
        "run_erc",
        "run_drc",
        "get_erc_violations",
        "get_drc_violations",
        "export_erc_report",
        "export_drc_report",
    ],
    "pin_analysis": [
        "analyze_pin_functions",
        "detect_pin_conflicts",
        "extract_pinmux_config",
    ],
    "device_tree": [
        "generate_device_tree",
        "extract_gpio_config",
        "extract_i2c_devices",
        "extract_spi_devices",
        "extract_power_domains",
        "validate_pin_configuration",
    ],
    "editing": [
        "add_component_from_library",
        "add_wire",
        "add_label",
    ],
    "pcb_layout": [
        "setup_pcb_layout",
        "export_gerber",
    ],
    "project_management": [
        "create_kicad_project",
    ],
}

SEEED_TOOLS: list[str] = [
    tool for tools in SEEED_TOOL_CATEGORIES.values() for tool in tools
]

# Subset of tools that overlap with the legacy ``seeed-kicad`` entry
# in ``kicad_servers.py``.  When the Seeed server is available these
# should be preferred.
LEGACY_OVERLAP_TOOLS = {
    "analyze_schematic": "list_schematic_components",
    "trace_connections": "trace_netlist_connection",
    "list_components": "list_schematic_components",
    "check_drc": "run_drc",
    "export_bom": "list_schematic_components",
}


# ---------------------------------------------------------------------------
# Server descriptor
# ---------------------------------------------------------------------------

@dataclass
class SeeedKicadServer:
    """Runtime descriptor for the Seeed KiCad MCP server."""

    key: str = "seeed-kicad-v2"
    description: str = "Seeed Studio KiCad MCP — 39 tools (analysis, validation, pin, devicetree, editing)"
    repo: str = "https://github.com/Seeed-Studio/kicad-mcp-server"
    command: tuple[str, ...] = field(default_factory=_resolve_command)
    tools: list[str] = field(default_factory=lambda: list(SEEED_TOOLS))
    transport: str = "stdio"
    install_cmd: str = "pip install kicad-mcp-server"
    timeout_s: float = 60.0


# Singleton (lazy)
_server: SeeedKicadServer | None = None


def get_server() -> SeeedKicadServer:
    global _server
    if _server is None:
        _server = SeeedKicadServer()
    return _server


# ---------------------------------------------------------------------------
# Availability check
# ---------------------------------------------------------------------------

def is_available() -> bool:
    """Return True if the Seeed KiCad MCP server can be launched.

    Checks that:
    1. The feature is enabled via environment variable.
    2. The first token in the command (``uvx``, ``python3``, etc.) is on PATH.
    """
    if not _is_enabled():
        return False
    cmd_tokens = _resolve_command()
    if not cmd_tokens:
        return False
    return shutil.which(cmd_tokens[0]) is not None


def get_server_config(project_path: str | None = None) -> dict[str, Any]:
    """Return a config dict compatible with ``McpServerDefinition`` construction.

    Parameters
    ----------
    project_path:
        Optional KiCad project directory injected as ``KICAD_PROJECT_PATH``
        in the subprocess environment.
    """
    srv = get_server()
    env: dict[str, str] = {}
    if project_path:
        env["KICAD_PROJECT_PATH"] = project_path
    return {
        "key": srv.key,
        "command": srv.command,
        "transport": srv.transport,
        "env": env,
        "timeout_s": srv.timeout_s,
    }


# ---------------------------------------------------------------------------
# Tool resolution helpers
# ---------------------------------------------------------------------------

def resolve_tool(tool_name: str) -> str | None:
    """Map a legacy or canonical tool name to its Seeed equivalent.

    Returns the Seeed tool name if a mapping exists, otherwise *None*.
    """
    if tool_name in SEEED_TOOLS:
        return tool_name
    return LEGACY_OVERLAP_TOOLS.get(tool_name)


def get_tools_by_category(category: str) -> list[str]:
    """Return tool names belonging to *category*, or an empty list."""
    return list(SEEED_TOOL_CATEGORIES.get(category, []))


# ---------------------------------------------------------------------------
# Logging helper
# ---------------------------------------------------------------------------

def log_status() -> None:
    """Log availability of the Seeed KiCad MCP server."""
    if is_available():
        srv = get_server()
        logger.info(
            "Seeed KiCad MCP server: enabled (%d tools) — command=%s",
            len(srv.tools),
            " ".join(srv.command),
        )
    elif _is_enabled():
        logger.warning(
            "Seeed KiCad MCP server: enabled but command not found (%s). "
            "Install with: %s",
            " ".join(_resolve_command()),
            "pip install kicad-mcp-server",
        )
    else:
        logger.info("Seeed KiCad MCP server: disabled (set %s=true to enable)", _ENV_ENABLED)
