"""MCP server definitions, registration helpers, and discovery."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from mascarade.mcp.errors import McpServerUnavailable

logger = logging.getLogger("mascarade.mcp.server_registry")


@dataclass(slots=True)
class McpServerDefinition:
    key: str
    launcher: Path | None = None
    command: tuple[str, ...] | None = None
    cwd: Path | None = None
    timeout_s: float = 45.0
    transport: str = "stdio"
    label: str | None = None
    description: str | None = None
    url: str | None = None


@dataclass(slots=True)
class McpToolResult:
    server_key: str
    tool_name: str
    structured_content: dict[str, Any]
    message: str
    protocol_version: str | None
    server_name: str | None
    is_error: bool
    latency_ms: float
    transport: str = "stdio"


def register_industrial_servers(
    servers: dict[str, McpServerDefinition],
    agent_factory_cockpit_dir: Path,
) -> None:
    if not agent_factory_cockpit_dir.exists():
        return
    industrial_metadata = {
        "cockpit-ops": (
            "Industrial Cockpit Ops",
            "Operator control plane for runs, alerts, topology, vendor contracts, and governance signals.",
        ),
        "plm": (
            "PLM MCP",
            "Product lifecycle management contract surface for governed product records and release traces.",
        ),
        "qms": (
            "QMS MCP",
            "Quality management surface for validation packs, deviations, and sign-off posture.",
        ),
        "mes": (
            "MES MCP",
            "Manufacturing execution surface for build dispatch and work-order status contracts.",
        ),
        "erp": (
            "ERP MCP",
            "Enterprise release surface for release publication and governed change-order contracts.",
        ),
        "wms": (
            "WMS MCP",
            "Warehouse logistics surface for pick waves, shipment release, and inventory holds.",
        ),
        "dcs": (
            "DCS MCP",
            "Critical-boundary surface for governed read snapshots and write-request escalation paths.",
        ),
    }
    for key, (label, description) in industrial_metadata.items():
        servers[key] = McpServerDefinition(
            key=key,
            command=(
                "python3",
                "-m",
                "agent_factory_cockpit.cli",
                "mcp-stdio",
                key,
                "--actor",
                "mascarade-mcp",
                "--auth-mode",
                "token",
            ),
            cwd=agent_factory_cockpit_dir,
            timeout_s=45.0,
            label=label,
            description=description,
        )


def register_graphiti_server(servers: dict[str, McpServerDefinition]) -> None:
    if os.getenv("GRAPHITI_ENABLED", "").lower() not in ("true", "1", "yes"):
        return
    graphiti_url = os.getenv("GRAPHITI_MCP_URL", "http://mascarade-graphiti-mcp:8000")
    servers["graphiti"] = McpServerDefinition(
        key="graphiti",
        transport="http",
        url=graphiti_url,
        timeout_s=30.0,
        label="Graphiti Knowledge Graph",
        description="Semantic knowledge graph for entity relationships and episodic memory.",
    )


def register_n8n_server(servers: dict[str, McpServerDefinition]) -> None:
    """Register n8n MCP server if N8N_BASE_URL is set."""
    n8n_url = os.getenv("N8N_BASE_URL", "")
    if not n8n_url:
        return
    servers["n8n"] = McpServerDefinition(
        key="n8n",
        transport="http",
        url=n8n_url.rstrip("/"),
        timeout_s=30.0,
        label="n8n Workflow Automation",
        description="Trigger and manage n8n workflows for lead processing, notifications, and data pipelines.",
    )


def register_erpnext_server(servers: dict[str, McpServerDefinition]) -> None:
    """Register ERPNext MCP server if FRAPPE_URL is set."""
    frappe_url = os.getenv("FRAPPE_URL", "")
    if not frappe_url:
        return
    servers["erpnext"] = McpServerDefinition(
        key="erpnext",
        transport="http",
        url=frappe_url.rstrip("/"),
        timeout_s=30.0,
        label="ERPNext CRM",
        description="CRM and ERP operations: leads, quotations, invoices via Frappe REST API.",
    )


def register_searxng_server(servers: dict[str, McpServerDefinition]) -> None:
    """Register SearXNG MCP server if SEARXNG_URL is set."""
    searxng_url = os.getenv("SEARXNG_URL", "")
    if not searxng_url:
        return
    servers["searxng"] = McpServerDefinition(
        key="searxng",
        transport="http",
        url=searxng_url.rstrip("/"),
        timeout_s=15.0,
        label="SearXNG Web Search",
        description="Privacy-respecting metasearch engine for web, news, science, IT, and file search.",
    )


def register_outline_server(servers: dict[str, McpServerDefinition]) -> None:
    """Register Outline MCP server if OUTLINE_URL and OUTLINE_API_KEY are set."""
    outline_url = os.getenv("OUTLINE_URL", "")
    outline_key = os.getenv("OUTLINE_API_KEY", "")
    if not outline_url or not outline_key:
        return
    servers["outline"] = McpServerDefinition(
        key="outline",
        transport="http",
        url=outline_url.rstrip("/"),
        timeout_s=15.0,
        label="Outline Wiki",
        description="Search and retrieve documents from Outline knowledge base (GitHub-connected).",
    )


def register_docling_server(servers: dict[str, McpServerDefinition]) -> None:
    """Register Docling MCP server if DOCLING_URL is set."""
    docling_url = os.getenv("DOCLING_URL", "")
    if not docling_url:
        return
    servers["docling"] = McpServerDefinition(
        key="docling",
        transport="http",
        url=docling_url.rstrip("/"),
        timeout_s=120.0,
        label="Docling Document Parser",
        description="Parse and convert PDFs, DOCX, HTML to markdown/JSON via docling-serve.",
    )


def register_kicad_mcp_servers(servers: dict[str, McpServerDefinition]) -> None:
    """Auto-discover and register installed KiCad MCP servers.

    The Seeed KiCad MCP v2 server (39 tools) is registered first when
    available.  Legacy KiCad MCP servers from ``kicad_servers.py`` are
    registered afterwards; duplicates are skipped.
    """
    # --- Seeed KiCad MCP v2 (preferred) ---
    from mascarade.mcp.kicad_seeed import (
        get_server as get_seeed_server,
    )
    from mascarade.mcp.kicad_seeed import (
        is_available as seeed_available,
    )
    from mascarade.mcp.kicad_seeed import (
        log_status as seeed_log_status,
    )

    if seeed_available():
        srv = get_seeed_server()
        if srv.key not in servers:
            servers[srv.key] = McpServerDefinition(
                key=srv.key,
                command=srv.command,
                timeout_s=srv.timeout_s,
                transport=srv.transport,
                label=srv.description,
                description=f"KiCad MCP: {srv.description} ({srv.repo})",
            )
    seeed_log_status()

    # --- Legacy KiCad MCP servers ---
    from mascarade.mcp.kicad_servers import (
        KICAD_MCP_SERVERS,
        discover_installed,
        log_available,
    )

    installed = discover_installed()
    for key in installed:
        if key in servers:
            continue
        srv_legacy = KICAD_MCP_SERVERS[key]
        servers[key] = McpServerDefinition(
            key=key,
            command=srv_legacy.command,
            timeout_s=45.0,
            transport=srv_legacy.transport,
            label=srv_legacy.description,
            description=f"KiCad MCP: {srv_legacy.description} ({srv_legacy.repo})",
        )
    log_available()


def _server(servers: dict[str, McpServerDefinition], server_key: str) -> McpServerDefinition:
    try:
        return servers[server_key]
    except KeyError as exc:  # pragma: no cover - programming error
        raise McpServerUnavailable(
            f"Unknown MCP server '{server_key}'",
            server_key=server_key,
        ) from exc


def _server_command(
    server: McpServerDefinition, mascarade_dir: Path
) -> tuple[tuple[str, ...], Path]:
    if server.command:
        return tuple(server.command), (server.cwd or mascarade_dir)
    launcher = server.launcher
    if launcher is None or not launcher.exists():
        raise McpServerUnavailable(
            f"MCP launcher missing for {server.key}: {launcher}",
            server_key=server.key,
            transport=server.transport,
        )
    return ("bash", str(launcher)), (server.cwd or launcher.parent)


def list_servers(servers: dict[str, McpServerDefinition]) -> list[dict[str, Any]]:
    items = []
    for key, server in sorted(servers.items()):
        items.append(
            {
                "key": key,
                "label": server.label or key,
                "description": server.description or "",
                "transport": server.transport,
                "timeout_s": server.timeout_s,
                "cwd": str(server.cwd or ""),
                "command": list(server.command) if server.command else [],
                "launcher": str(server.launcher) if server.launcher else "",
            }
        )
    return items
