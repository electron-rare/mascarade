"""KiCad + SPICE MCP server definitions for external tool integration."""

from __future__ import annotations

import logging
import shutil
from dataclasses import dataclass, field

logger = logging.getLogger("mascarade.mcp.kicad_servers")


@dataclass
class KiCadMcpServer:
    key: str
    description: str
    repo: str
    command: tuple[str, ...]
    tools: list[str] = field(default_factory=list)
    transport: str = "stdio"
    install_cmd: str = ""


KICAD_MCP_SERVERS: dict[str, KiCadMcpServer] = {
    "seeed-kicad": KiCadMcpServer(
        key="seeed-kicad",
        description="Seeed Studio KiCad MCP",
        repo="https://github.com/Seeed-Studio/kicad-mcp-server",
        command=("npx", "-y", "@anthropic-ai/kicad-mcp-server"),
        install_cmd="npm install -g @anthropic-ai/kicad-mcp-server",
        tools=["analyze_schematic", "trace_connections", "list_components", "check_drc", "export_bom"],
    ),
    "circuit-synth": KiCadMcpServer(
        key="circuit-synth",
        description="Circuit Synth KiCad Schematic API",
        repo="https://github.com/circuit-synth/mcp-kicad-sch-api",
        command=("npx", "-y", "mcp-kicad-sch-api"),
        install_cmd="npm install -g mcp-kicad-sch-api",
        tools=["read_schematic", "write_schematic", "add_component", "add_wire", "validate_schematic"],
    ),
    "kicad-happy": KiCadMcpServer(
        key="kicad-happy",
        description="AI-powered KiCad skills",
        repo="https://github.com/aklofas/kicad-happy",
        command=("python3", "-m", "kicad_happy.mcp_server"),
        install_cmd="pip install kicad-happy",
        tools=["analyze_pcb_layout", "review_schematic", "suggest_drc_fixes", "check_manufacturing_constraints"],
    ),
    "mixelpixx-kicad": KiCadMcpServer(
        key="mixelpixx-kicad",
        description="KiCAD MCP Server bridge",
        repo="https://github.com/mixelpixx/KiCAD-MCP-Server",
        command=("python3", "-m", "kicad_mcp_server"),
        install_cmd="pip install kicad-mcp-server",
        tools=["open_project", "run_drc", "export_gerbers", "place_component", "route_trace"],
    ),
    "spicebridge": KiCadMcpServer(
        key="spicebridge",
        description="SPICEBridge — 28 tools for ngspice simulation, netlist creation, analysis, Monte Carlo",
        repo="https://github.com/clanker-lover/spicebridge",
        command=("python3", "-m", "spicebridge.server"),
        install_cmd="pip install spicebridge",
        tools=[
            "create_circuit", "validate_netlist", "run_ac_analysis", "run_dc_analysis",
            "run_transient_analysis", "measure_bandwidth", "measure_gain",
            "measure_power", "measure_time_domain", "monte_carlo_analysis",
            "worst_case_analysis", "export_kicad", "export_png", "export_svg",
            "connect_stages", "create_from_template",
        ],
    ),
}


def discover_installed() -> list[str]:
    installed = []
    for key, server in KICAD_MCP_SERVERS.items():
        cmd = server.command[0]
        if cmd == "npx" and shutil.which("npx"):
            installed.append(key)
        elif shutil.which(cmd):
            installed.append(key)
    return installed


def get_server_config(key: str, project_path: str | None = None) -> dict:
    server = KICAD_MCP_SERVERS[key]
    env = {}
    if project_path:
        env["KICAD_PROJECT_PATH"] = project_path
    return {"key": server.key, "command": server.command, "transport": server.transport, "env": env, "timeout_s": 45.0}


def log_available() -> None:
    installed = discover_installed()
    if installed:
        logger.info("KiCad MCP servers: %s/%s — %s", len(installed), len(KICAD_MCP_SERVERS), installed)
    else:
        logger.info("No KiCad MCP servers installed. Available: %s", list(KICAD_MCP_SERVERS.keys()))
