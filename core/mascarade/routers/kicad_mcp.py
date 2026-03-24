"""KiCad MCP routes -- expose KiCad and SPICE servers through the REST API."""

from __future__ import annotations

import secrets
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from mascarade.auth import require_auth
from mascarade.mcp.kicad_servers import (
    KICAD_MCP_SERVERS,
    discover_installed,
    get_server_config,
)

router = APIRouter(
    prefix="/v1/api/kicad",
    tags=["kicad"],
    dependencies=[Depends(require_auth)],
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _require_mcp(request: Request):
    mcp = getattr(request.app.state, "mcp", None)
    if mcp is None:
        raise HTTPException(status_code=503, detail="MCP client not available")
    return mcp


def _best_server(candidates: list[str]) -> str:
    """Return the first installed candidate, or raise 503."""
    installed = set(discover_installed())
    for c in candidates:
        if c in installed:
            return c
    raise HTTPException(
        status_code=503,
        detail=f"No KiCad MCP server installed. Candidates: {candidates}",
    )


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class AnalyzeRequest(BaseModel):
    project_path: str = Field(..., description="Path to KiCad project (.kicad_pro or directory)")
    run_id: str | None = None


class DrcRequest(BaseModel):
    project_path: str = Field(..., description="Path to KiCad project")
    run_id: str | None = None


class SpiceRequest(BaseModel):
    netlist: str | None = Field(None, description="SPICE netlist content or path")
    analysis: str = Field("transient", description="Analysis type: transient, ac, dc, monte_carlo")
    parameters: dict[str, Any] = Field(default_factory=dict)
    run_id: str | None = None


# ---------------------------------------------------------------------------
# GET /v1/api/kicad/servers
# ---------------------------------------------------------------------------

@router.get("/servers")
async def list_servers():
    """List available KiCad MCP servers and their install status."""
    installed = set(discover_installed())
    result = []
    for key, srv in KICAD_MCP_SERVERS.items():
        result.append({
            "key": key,
            "description": srv.description,
            "repo": srv.repo,
            "installed": key in installed,
            "tools": srv.tools,
            "install_cmd": srv.install_cmd,
        })
    return {"servers": result, "installed_count": len(installed), "total": len(KICAD_MCP_SERVERS)}


# ---------------------------------------------------------------------------
# GET /v1/api/kicad/tools
# ---------------------------------------------------------------------------

@router.get("/tools")
async def list_tools():
    """List all available tools across all installed KiCad MCP servers."""
    installed = set(discover_installed())
    tools: list[dict[str, str]] = []
    for key, srv in KICAD_MCP_SERVERS.items():
        if key not in installed:
            continue
        for tool_name in srv.tools:
            tools.append({"server": key, "tool": tool_name})
    return {"tools": tools, "count": len(tools)}


# ---------------------------------------------------------------------------
# POST /v1/api/kicad/analyze
# ---------------------------------------------------------------------------

@router.post("/analyze")
async def analyze_project(req: AnalyzeRequest, request: Request):
    """Analyze a KiCad project -- delegates to seeed-kicad or kicad-happy."""
    mcp = _require_mcp(request)
    server_key = _best_server(["seeed-kicad", "kicad-happy", "mixelpixx-kicad"])
    run_id = req.run_id or f"kicad-{secrets.token_hex(6)}"

    tool_map = {
        "seeed-kicad": "analyze_schematic",
        "kicad-happy": "review_schematic",
        "mixelpixx-kicad": "open_project",
    }
    tool_name = tool_map[server_key]

    result = await mcp.call_tool(
        server_key,
        tool_name,
        {"project_path": req.project_path},
        run_id=run_id,
        mode="kicad",
        agent_name="kicad",
    )
    return {
        "run_id": run_id,
        "server": server_key,
        "tool": tool_name,
        "result": result.content if hasattr(result, "content") else result,
    }


# ---------------------------------------------------------------------------
# POST /v1/api/kicad/drc
# ---------------------------------------------------------------------------

@router.post("/drc")
async def run_drc(req: DrcRequest, request: Request):
    """Run Design Rule Check on a KiCad project."""
    mcp = _require_mcp(request)
    server_key = _best_server(["seeed-kicad", "mixelpixx-kicad", "kicad-happy"])
    run_id = req.run_id or f"drc-{secrets.token_hex(6)}"

    tool_map = {
        "seeed-kicad": "check_drc",
        "mixelpixx-kicad": "run_drc",
        "kicad-happy": "suggest_drc_fixes",
    }
    tool_name = tool_map[server_key]

    result = await mcp.call_tool(
        server_key,
        tool_name,
        {"project_path": req.project_path},
        run_id=run_id,
        mode="kicad",
        agent_name="kicad",
    )
    return {
        "run_id": run_id,
        "server": server_key,
        "tool": tool_name,
        "result": result.content if hasattr(result, "content") else result,
    }


# ---------------------------------------------------------------------------
# POST /v1/api/kicad/spice
# ---------------------------------------------------------------------------

@router.post("/spice")
async def run_spice(req: SpiceRequest, request: Request):
    """Run SPICE simulation via SPICEBridge MCP server."""
    mcp = _require_mcp(request)
    server_key = _best_server(["spicebridge"])
    run_id = req.run_id or f"spice-{secrets.token_hex(6)}"

    analysis_tool_map = {
        "transient": "run_transient_analysis",
        "ac": "run_ac_analysis",
        "dc": "run_dc_analysis",
        "monte_carlo": "monte_carlo_analysis",
    }
    tool_name = analysis_tool_map.get(req.analysis)
    if tool_name is None:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown analysis type '{req.analysis}'. Choose from: {list(analysis_tool_map.keys())}",
        )

    arguments: dict[str, Any] = {**req.parameters}
    if req.netlist:
        arguments["netlist"] = req.netlist

    result = await mcp.call_tool(
        server_key,
        tool_name,
        arguments,
        run_id=run_id,
        mode="spice",
        agent_name="spicebridge",
    )
    return {
        "run_id": run_id,
        "server": server_key,
        "tool": tool_name,
        "analysis": req.analysis,
        "result": result.content if hasattr(result, "content") else result,
    }
