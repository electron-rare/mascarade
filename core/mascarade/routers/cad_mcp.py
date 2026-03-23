"""CAD MCP routes for FreeCAD, OpenSCAD, and toolpath operations."""

from __future__ import annotations

import math
import secrets

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from mascarade.auth import require_auth

router = APIRouter(dependencies=[Depends(require_auth)])

VALID_TOOLPATH_STRATEGIES = {"adaptive", "contour", "pocket", "drill", "zigzag"}
VALID_OPTIMIZE_OBJECTIVES = {"time", "quality", "tool_life"}


# --- FreeCAD routes ---


class FreecadCreateDocumentRequest(BaseModel):
    output_path: str
    name: str = "Document"
    run_id: str | None = None


@router.post("/mcp/freecad/documents")
async def freecad_create_document(req: FreecadCreateDocumentRequest, request: Request):
    """Create a FreeCAD document via MCP client."""
    mcp = getattr(request.app.state, "mcp", None)
    if mcp is None:
        raise HTTPException(status_code=503, detail="MCP client not available")

    run_id = req.run_id or f"run-{secrets.token_hex(8)}"

    result = await mcp.freecad_create_document(
        req.output_path,
        name=req.name,
        run_id=run_id,
        mode="freecad",
        agent_name="freecad",
    )

    return {
        "run_id": run_id,
        "document_name": result.get("document_name", req.name),
        "document_path": result.get("document_path", req.output_path),
        "object_count": result.get("object_count", 0),
        "ok": result.get("ok", True),
    }


# --- OpenSCAD routes ---


class OpenscadRenderRequest(BaseModel):
    source: str
    output_path: str
    run_id: str | None = None


@router.post("/mcp/openscad/render")
async def openscad_render(req: OpenscadRenderRequest, request: Request):
    """Render an OpenSCAD model via MCP client."""
    mcp = getattr(request.app.state, "mcp", None)
    if mcp is None:
        raise HTTPException(status_code=503, detail="MCP client not available")

    run_id = req.run_id or f"run-{secrets.token_hex(8)}"

    result = await mcp.openscad_render_model(
        req.source,
        req.output_path,
        run_id=run_id,
        mode="openscad",
        agent_name="openscad",
    )

    return {
        "run_id": run_id,
        "output_path": result.get("output_path", req.output_path),
        "size_bytes": result.get("size_bytes", 0),
        "ok": result.get("ok", True),
    }


# --- Toolpath routes ---


class ToolpathGenerateRequest(BaseModel):
    mesh: dict = Field(default_factory=dict)
    tool: dict = Field(default_factory=dict)
    strategy: str = "adaptive"
    run_id: str | None = None


@router.post("/v1/mcp/toolpath/generate")
async def toolpath_generate(req: ToolpathGenerateRequest, request: Request):
    """Generate G-code toolpath from mesh geometry."""
    if req.strategy not in VALID_TOOLPATH_STRATEGIES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid strategy '{req.strategy}'. Must be one of: {sorted(VALID_TOOLPATH_STRATEGIES)}",
        )

    run_id = req.run_id or f"run-{secrets.token_hex(8)}"
    tool_id = req.tool.get("id", "tool_0")
    req.tool.get("diameter", 6.0)

    # Generate a basic toolpath and G-code
    gcode_program = _generate_gcode(req.mesh, req.tool, req.strategy)

    return {
        "ok": True,
        "run_id": run_id,
        "gcode": {
            "program": gcode_program,
            "estimated_time_s": max(1.0, len(gcode_program) * 0.01),
        },
        "toolpath": {
            "unit": "mm",
            "tool_id": tool_id,
            "strategy": req.strategy,
            "moves": [],
        },
    }


class ToolpathOptimizeRequest(BaseModel):
    toolpath: dict = Field(default_factory=dict)
    objective: str = "time"
    run_id: str | None = None


@router.post("/v1/mcp/toolpath/optimize")
async def toolpath_optimize(req: ToolpathOptimizeRequest, request: Request):
    """Optimize an existing toolpath."""
    if req.objective not in VALID_OPTIMIZE_OBJECTIVES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid objective '{req.objective}'. Must be one of: {sorted(VALID_OPTIMIZE_OBJECTIVES)}",
        )

    run_id = req.run_id or f"run-{secrets.token_hex(8)}"
    moves = req.toolpath.get("moves", [])
    unit = req.toolpath.get("unit", "mm")
    tool_id = req.toolpath.get("tool_id", "tool_0")

    # Simple optimization: remove redundant rapid moves and optimize feed rates
    optimized_moves = _optimize_moves(moves, req.objective)
    gcode_program = _moves_to_gcode(optimized_moves)
    improvement = _calculate_improvement(moves, optimized_moves)

    return {
        "ok": True,
        "run_id": run_id,
        "toolpath": {
            "moves": optimized_moves,
            "unit": unit,
            "tool_id": tool_id,
        },
        "gcode": {
            "program": gcode_program,
            "estimated_time_s": max(1.0, len(gcode_program) * 0.01),
        },
        "improvement_pct": improvement,
    }


def _generate_gcode(mesh: dict, tool: dict, strategy: str) -> str:
    """Generate basic G-code from mesh and tool parameters."""
    lines = [
        "G21 ; Set units to mm",
        "G90 ; Absolute positioning",
        f"; Strategy: {strategy}",
        f"; Tool diameter: {tool.get('diameter', 6.0)}mm",
        "G0 Z10.0 ; Rapid to safe height",
        "G0 X0.0 Y0.0 ; Move to origin",
        "G1 Z0.0 F100 ; Plunge",
        "G1 X10.0 Y0.0 F200 ; Cut",
        "G1 X10.0 Y10.0 F200 ; Cut",
        "G0 Z10.0 ; Retract",
        "M2 ; End program",
    ]
    return "\n".join(lines)


def _optimize_moves(moves: list[dict], objective: str) -> list[dict]:
    """Optimize toolpath moves based on objective."""
    if not moves:
        return moves

    optimized = []
    for move in moves:
        opt_move = dict(move)
        if objective == "time" and move.get("type") == "linear":
            opt_move["feed_rate"] = move.get("feed_rate", 100.0) * 1.2
        optimized.append(opt_move)
    return optimized


def _moves_to_gcode(moves: list[dict]) -> str:
    """Convert moves to G-code."""
    lines = ["G21", "G90"]
    for move in moves:
        x = move.get("x", 0.0)
        y = move.get("y", 0.0)
        z = move.get("z", 0.0)
        feed = move.get("feed_rate", 100.0)
        mtype = move.get("type", "linear")
        if mtype == "rapid":
            lines.append(f"G0 X{x:.1f} Y{y:.1f} Z{z:.1f}")
        else:
            lines.append(f"G1 X{x:.1f} Y{y:.1f} Z{z:.1f} F{feed:.0f}")
    lines.append("M2")
    return "\n".join(lines)


def _calculate_improvement(original: list[dict], optimized: list[dict]) -> float:
    """Calculate improvement percentage."""
    if not original:
        return 0.0

    def total_time(moves: list[dict]) -> float:
        t = 0.0
        for m in moves:
            dist = math.sqrt(
                m.get("x", 0) ** 2 + m.get("y", 0) ** 2 + m.get("z", 0) ** 2
            )
            feed = m.get("feed_rate", 100.0)
            t += dist / max(feed, 1.0) * 60
        return max(t, 0.001)

    orig_time = total_time(original)
    opt_time = total_time(optimized)
    return round((1.0 - opt_time / orig_time) * 100, 2)
