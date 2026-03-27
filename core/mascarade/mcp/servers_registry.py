"""Central MCP server registry for all external tool integrations.

Consolidates KiCad, Outline, Grafana, n8n, Docker, Excalidraw
and other MCP servers into a single discoverable registry.
"""

from __future__ import annotations

import logging
import os
import shutil
from dataclasses import dataclass, field

logger = logging.getLogger("mascarade.mcp.servers_registry")


def _env(name: str, default: str = "") -> str:
    """Resolve environment variables at call time, not import time."""
    return os.environ.get(name, default)


@dataclass
class McpServerDef:
    """Definition of an MCP server that mascarade can connect to."""

    key: str
    name: str
    description: str
    category: str  # kicad, wiki, monitoring, automation, cad, collaboration
    command: tuple[str, ...]
    transport: str = "stdio"
    env_vars: dict[str, str] = field(default_factory=dict)
    tools: list[str] = field(default_factory=list)
    install_cmd: str = ""
    repo: str = ""
    docker_image: str = ""
    docker_network: str = ""
    enabled: bool = True


# ── KiCad MCP Servers ──────────────────────────────────────────────

KICAD_SERVERS: dict[str, McpServerDef] = {
    "seeed-kicad": McpServerDef(
        key="seeed-kicad",
        name="Seeed Studio KiCad",
        description="Seeed Studio KiCad MCP — schematic analysis, DRC, BOM",
        category="kicad",
        repo="https://github.com/Seeed-Studio/kicad-mcp-server",
        command=("npx", "-y", "@anthropic-ai/kicad-mcp-server"),
        install_cmd="npm install -g @anthropic-ai/kicad-mcp-server",
        tools=[
            "analyze_schematic",
            "trace_connections",
            "list_components",
            "check_drc",
            "export_bom",
        ],
    ),
    "circuit-synth": McpServerDef(
        key="circuit-synth",
        name="Circuit Synth",
        description="Circuit Synth KiCad Schematic API — read/write schematics",
        category="kicad",
        repo="https://github.com/circuit-synth/mcp-kicad-sch-api",
        command=("npx", "-y", "mcp-kicad-sch-api"),
        install_cmd="npm install -g mcp-kicad-sch-api",
        tools=[
            "read_schematic",
            "write_schematic",
            "add_component",
            "add_wire",
            "validate_schematic",
        ],
    ),
    "kicad-happy": McpServerDef(
        key="kicad-happy",
        name="KiCad Happy",
        description="AI-powered KiCad skills — layout analysis, DRC fixes",
        category="kicad",
        repo="https://github.com/aklofas/kicad-happy",
        command=("python3", "-m", "kicad_happy.mcp_server"),
        install_cmd="pip install kicad-happy",
        tools=[
            "analyze_pcb_layout",
            "review_schematic",
            "suggest_drc_fixes",
            "check_manufacturing_constraints",
        ],
    ),
    "mixelpixx-kicad": McpServerDef(
        key="mixelpixx-kicad",
        name="KiCAD MCP Bridge",
        description="KiCAD MCP Server bridge — project management, routing",
        category="kicad",
        repo="https://github.com/mixelpixx/KiCAD-MCP-Server",
        command=("python3", "-m", "kicad_mcp_server"),
        install_cmd="pip install kicad-mcp-server",
        tools=[
            "open_project",
            "run_drc",
            "export_gerbers",
            "place_component",
            "route_trace",
        ],
    ),
}

# ── Wiki & Knowledge Base ──────────────────────────────────────────

WIKI_SERVERS: dict[str, McpServerDef] = {
    "outline": McpServerDef(
        key="outline",
        name="Outline Wiki",
        description="Outline wiki — search, CRUD documents, collections, export, batch ops",
        category="wiki",
        repo="https://github.com/Vortiago/mcp-outline",
        command=("uvx", "mcp-outline"),
        install_cmd="pip install mcp-outline",
        env_vars={
            "OUTLINE_API_KEY": "env:OUTLINE_API_KEY",
            "OUTLINE_BASE_URL": "env:OUTLINE_BASE_URL|https://wiki.saillant.cc",
        },
        tools=[
            "search_documents",
            "create_document",
            "read_document",
            "update_document",
            "move_document",
            "archive_document",
            "delete_document",
            "export_document",
            "list_collections",
            "create_collection",
            "batch_create",
            "batch_update",
            "batch_move",
            "batch_archive",
        ],
    ),
}

# ── Monitoring ─────────────────────────────────────────────────────

MONITORING_SERVERS: dict[str, McpServerDef] = {
    "grafana": McpServerDef(
        key="grafana",
        name="Grafana",
        description="Grafana — dashboards, alerting, oncall, datasource queries",
        category="monitoring",
        repo="https://github.com/grafana/mcp-grafana",
        command=(
            "docker",
            "run",
            "--rm",
            "-i",
            "--network",
            "zacus-stack_default",
            "-e",
            "GRAFANA_URL",
            "-e",
            "GRAFANA_API_KEY",
            "mcp/grafana",
        ),
        docker_image="mcp/grafana",
        docker_network="zacus-stack_default",
        env_vars={
            "GRAFANA_URL": "env:GRAFANA_URL|http://zacus-grafana:3000",
            "GRAFANA_API_KEY": "env:GRAFANA_API_KEY",
        },
        tools=[
            "search_dashboards",
            "get_dashboard",
            "render_panel",
            "list_alert_rules",
            "list_contact_points",
            "query_prometheus",
            "query_loki",
        ],
    ),
}

# ── Automation ─────────────────────────────────────────────────────

AUTOMATION_SERVERS: dict[str, McpServerDef] = {
    "n8n": McpServerDef(
        key="n8n",
        name="n8n Workflows",
        description="n8n — list, create, update workflows, start executions, webhooks",
        category="automation",
        repo="https://github.com/leonardsellem/n8n-mcp-server",
        command=("npx", "-y", "n8n-mcp-server"),
        install_cmd="npm install -g n8n-mcp-server",
        env_vars={
            "N8N_API_URL": "env:N8N_API_URL|http://localhost:5678",
            "N8N_API_KEY": "env:N8N_API_KEY",
        },
        tools=[
            "list_workflows",
            "get_workflow",
            "create_workflow",
            "update_workflow",
            "start_execution",
            "get_execution",
            "trigger_webhook",
        ],
    ),
}

# ── Infrastructure ─────────────────────────────────────────────────

INFRA_SERVERS: dict[str, McpServerDef] = {
    "docker": McpServerDef(
        key="docker",
        name="Docker",
        description="Docker — create containers, deploy compose, logs, list",
        category="infra",
        repo="https://github.com/QuantGeekDev/docker-mcp",
        command=("python3", "-m", "docker_mcp"),
        install_cmd="pip install docker-mcp",
        tools=["create_container", "deploy_compose", "get_logs", "list_containers"],
    ),
}

# ── Collaboration ──────────────────────────────────────────────────

COLLAB_SERVERS: dict[str, McpServerDef] = {
    "excalidraw": McpServerDef(
        key="excalidraw",
        name="Excalidraw",
        description="Excalidraw — create interactive diagrams",
        category="collaboration",
        repo="https://github.com/excalidraw/excalidraw-mcp",
        command=("npx", "-y", "excalidraw-mcp"),
        install_cmd="npm install -g excalidraw-mcp",
        tools=["read_me", "create_view"],
    ),
}


# ── Unified Registry ──────────────────────────────────────────────

ALL_SERVERS: dict[str, McpServerDef] = {
    **KICAD_SERVERS,
    **WIKI_SERVERS,
    **MONITORING_SERVERS,
    **AUTOMATION_SERVERS,
    **INFRA_SERVERS,
    **COLLAB_SERVERS,
}


def discover_installed() -> list[str]:
    """Return keys of servers whose commands are available."""
    installed = []
    for key, server in ALL_SERVERS.items():
        if not server.enabled:
            continue
        cmd = server.command[0]
        if cmd == "npx" and shutil.which("npx"):
            installed.append(key)
        elif cmd == "uvx" and shutil.which("uvx"):
            installed.append(key)
        elif cmd == "docker" and shutil.which("docker"):
            installed.append(key)
        elif shutil.which(cmd):
            installed.append(key)
    return installed


def get_by_category(category: str) -> dict[str, McpServerDef]:
    """Return all servers in a category."""
    return {k: v for k, v in ALL_SERVERS.items() if v.category == category}


def get_server(key: str) -> McpServerDef:
    """Get a server definition by key."""
    if key not in ALL_SERVERS:
        raise KeyError(f"MCP server '{key}' not found. Available: {list(ALL_SERVERS.keys())}")
    return ALL_SERVERS[key]


def get_server_config(key: str, extra_env: dict[str, str] | None = None) -> dict:
    """Get runtime config for launching an MCP server."""
    server = get_server(key)
    env: dict[str, str] = {}
    for env_key, env_value in server.env_vars.items():
        if isinstance(env_value, str) and env_value.startswith("env:"):
            spec = env_value[4:]
            if "|" in spec:
                source_name, default = spec.split("|", 1)
            else:
                source_name, default = spec, ""
            env[env_key] = _env(source_name, default)
        else:
            env[env_key] = env_value
    if extra_env:
        env.update(extra_env)
    return {
        "key": server.key,
        "name": server.name,
        "command": server.command,
        "transport": server.transport,
        "env": env,
        "timeout_s": 45.0,
    }


def log_available() -> None:
    """Log discovered MCP servers."""
    installed = discover_installed()
    categories = {}
    for key in installed:
        cat = ALL_SERVERS[key].category
        categories.setdefault(cat, []).append(key)

    if installed:
        logger.info(
            "MCP servers: %s/%s installed — %s",
            len(installed),
            len(ALL_SERVERS),
            dict(categories),
        )
    else:
        logger.info("No MCP servers installed. Available: %s", list(ALL_SERVERS.keys()))
