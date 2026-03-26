"""Performance control router — DAW, DMX lighting, OBS streaming.

Provides REST endpoints for the kxkm_clown multimodal performance system.
All endpoints are opt-in: they return 503 when the corresponding MCP server
is not configured.
"""

from __future__ import annotations

import logging
from dataclasses import asdict
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

logger = logging.getLogger("mascarade.routers.performance")

router = APIRouter(prefix="/v1/performance", tags=["performance"])


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------


class TransportRequest(BaseModel):
    action: str = Field(
        ...,
        description="Transport action: play, stop, pause, record, rewind",
        pattern="^(play|stop|pause|record|rewind)$",
    )
    bpm: float | None = Field(None, description="Optional BPM override", ge=20, le=999)


class SceneRequest(BaseModel):
    scene_name: str = Field(..., description="Name of the lighting scene to trigger")
    fade_ms: int = Field(0, description="Fade time in milliseconds", ge=0, le=30000)
    universe: int | None = Field(None, description="Target DMX universe", ge=0)


class BlackoutRequest(BaseModel):
    fade_ms: int = Field(0, description="Fade time in milliseconds", ge=0, le=5000)


class OBSSceneRequest(BaseModel):
    scene_name: str = Field(..., description="OBS scene name to switch to")


class OBSRecordRequest(BaseModel):
    action: str = Field(
        ...,
        description="start or stop",
        pattern="^(start|stop)$",
    )


class OBSStreamRequest(BaseModel):
    action: str = Field(
        ...,
        description="start or stop",
        pattern="^(start|stop)$",
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_perf_manager(request: Request):
    """Retrieve PerformanceMcpManager from app state or raise 503."""
    manager = getattr(request.app.state, "performance_mcp", None)
    if manager is None:
        raise HTTPException(
            status_code=503,
            detail="Performance MCP is not enabled (set PERFORMANCE_MCP_ENABLED=true)",
        )
    return manager


def _tool_result_to_dict(result) -> dict[str, Any]:
    return {
        "ok": not result.is_error,
        "server": result.server_key,
        "tool": result.tool_name,
        "message": result.message,
        "data": result.structured_content,
        "latency_ms": result.latency_ms,
    }


# ---------------------------------------------------------------------------
# DAW endpoints
# ---------------------------------------------------------------------------


@router.post("/daw/transport")
async def daw_transport(body: TransportRequest, request: Request):
    """Control DAW transport — play, stop, pause, record, rewind."""
    manager = _get_perf_manager(request)
    if not manager.is_available(manager.SERVER_KEY_DAW):
        raise HTTPException(status_code=503, detail="Reaper MCP server not configured")

    from mascarade.mcp.performance import TransportAction

    try:
        action = TransportAction(body.action)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Unknown action: {body.action}") from None

    result = await manager.daw_transport(action, bpm=body.bpm)
    return _tool_result_to_dict(result)


@router.get("/daw/tracks")
async def daw_tracks(request: Request):
    """List all tracks in the current Reaper project."""
    manager = _get_perf_manager(request)
    if not manager.is_available(manager.SERVER_KEY_DAW):
        raise HTTPException(status_code=503, detail="Reaper MCP server not configured")

    result = await manager.daw_get_tracks()
    return _tool_result_to_dict(result)


# ---------------------------------------------------------------------------
# DMX endpoints
# ---------------------------------------------------------------------------


@router.post("/dmx/scene")
async def dmx_scene(body: SceneRequest, request: Request):
    """Trigger a named lighting scene."""
    manager = _get_perf_manager(request)
    if not manager.is_available(manager.SERVER_KEY_DMX):
        raise HTTPException(status_code=503, detail="LacyLights MCP server not configured")

    result = await manager.dmx_trigger_scene(
        body.scene_name, fade_ms=body.fade_ms, universe=body.universe
    )
    return _tool_result_to_dict(result)


@router.post("/dmx/blackout")
async def dmx_blackout(body: BlackoutRequest, request: Request):
    """Emergency blackout — all DMX channels to zero."""
    manager = _get_perf_manager(request)
    if not manager.is_available(manager.SERVER_KEY_DMX):
        raise HTTPException(status_code=503, detail="LacyLights MCP server not configured")

    result = await manager.dmx_blackout(fade_ms=body.fade_ms)
    return _tool_result_to_dict(result)


@router.get("/dmx/scenes")
async def dmx_list_scenes(request: Request):
    """List all available lighting scenes."""
    manager = _get_perf_manager(request)
    if not manager.is_available(manager.SERVER_KEY_DMX):
        raise HTTPException(status_code=503, detail="LacyLights MCP server not configured")

    result = await manager.dmx_list_scenes()
    return _tool_result_to_dict(result)


# ---------------------------------------------------------------------------
# OBS endpoints (optional)
# ---------------------------------------------------------------------------


@router.post("/obs/scene")
async def obs_scene(body: OBSSceneRequest, request: Request):
    """Switch OBS to a named scene."""
    manager = _get_perf_manager(request)
    if not manager.is_available(manager.SERVER_KEY_OBS):
        raise HTTPException(status_code=503, detail="OBS MCP server not configured")

    result = await manager.obs_switch_scene(body.scene_name)
    return _tool_result_to_dict(result)


@router.post("/obs/record")
async def obs_record(body: OBSRecordRequest, request: Request):
    """Start or stop OBS recording."""
    manager = _get_perf_manager(request)
    if not manager.is_available(manager.SERVER_KEY_OBS):
        raise HTTPException(status_code=503, detail="OBS MCP server not configured")

    if body.action == "start":
        result = await manager.obs_start_recording()
    else:
        result = await manager.obs_stop_recording()
    return _tool_result_to_dict(result)


@router.post("/obs/stream")
async def obs_stream(body: OBSStreamRequest, request: Request):
    """Start or stop OBS streaming."""
    manager = _get_perf_manager(request)
    if not manager.is_available(manager.SERVER_KEY_OBS):
        raise HTTPException(status_code=503, detail="OBS MCP server not configured")

    if body.action == "start":
        result = await manager.obs_start_streaming()
    else:
        result = await manager.obs_stop_streaming()
    return _tool_result_to_dict(result)


# ---------------------------------------------------------------------------
# Aggregate status
# ---------------------------------------------------------------------------


@router.get("/status")
async def performance_status(request: Request):
    """Get status of all performance subsystems (DAW, DMX, OBS)."""
    manager = _get_perf_manager(request)
    status = await manager.get_full_status()
    return {
        "performance": asdict(status),
        "servers": manager.available_servers,
    }
