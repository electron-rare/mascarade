"""WebSocket endpoints for real-time event streaming.

Provides low-latency bidirectional WebSocket alternatives to existing SSE
endpoints.  Existing SSE endpoints are preserved for backward compatibility.
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import asdict
from datetime import UTC, datetime

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from mascarade.auth import get_active_api_keys

logger = logging.getLogger("mascarade.ws")

router = APIRouter(tags=["websocket"])

# ---------------------------------------------------------------------------
# Auth helper
# ---------------------------------------------------------------------------

async def _ws_auth(websocket: WebSocket) -> bool:
    """Validate an optional bearer token supplied as a query parameter.

    Returns ``True`` when the connection is authorized (or when no API keys
    are configured, meaning auth is effectively disabled).  Returns ``False``
    when a token is required but missing / invalid.
    """
    active_keys = get_active_api_keys()
    if not active_keys:
        # No keys configured — auth not enforced.
        return True

    token = websocket.query_params.get("token")
    if not token:
        return False
    return token in active_keys


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_HEARTBEAT_INTERVAL: float = 15.0  # seconds


def _json_payload(event_type: str, data: object) -> str:
    """Serialize a WebSocket message envelope as JSON."""
    return json.dumps({"type": event_type, "data": data}, default=str)


# ---------------------------------------------------------------------------
# WS /ws/traces — real-time agent trace events
# ---------------------------------------------------------------------------

@router.websocket("/ws/traces")
async def ws_traces(
    websocket: WebSocket,
    run_id: str | None = None,
    agent_name: str | None = None,
    event_type: str | None = None,
):
    """Stream agent trace events over WebSocket.

    Query parameters:
      - ``run_id``: filter to a specific orchestration run
      - ``agent_name``: filter to a specific agent
      - ``event_type``: filter to a specific event type
    """
    if not await _ws_auth(websocket):
        await websocket.close(code=4003, reason="Unauthorized")
        return

    await websocket.accept()
    logger.info("WS /ws/traces connected (run_id=%s agent=%s type=%s)", run_id, agent_name, event_type)

    trace_buffer = websocket.app.state.trace_buffer
    if trace_buffer is None:
        await websocket.send_text(_json_payload("error", {"detail": "Trace buffer not initialized"}))
        await websocket.close(code=1011)
        return

    # Send recent events as initial burst.
    recent = trace_buffer.recent(limit=20, run_id=run_id, agent_name=agent_name, event_type=event_type)
    for evt in recent:
        await websocket.send_text(_json_payload("trace", evt.to_dict()))

    # Subscribe for live events.
    queue, unsubscribe = trace_buffer.subscribe(
        run_id=run_id,
        agent_name=agent_name,
        event_type=event_type,
    )

    try:
        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=_HEARTBEAT_INTERVAL)
                await websocket.send_text(_json_payload("trace", event.to_dict()))
            except asyncio.TimeoutError:
                # No event within the heartbeat window — send a keepalive ping.
                await websocket.send_text(_json_payload("ping", {"ts": datetime.now(UTC).isoformat()}))
    except WebSocketDisconnect:
        logger.info("WS /ws/traces disconnected")
    except Exception:
        logger.exception("WS /ws/traces unexpected error")
    finally:
        unsubscribe()


# ---------------------------------------------------------------------------
# WS /ws/p2p — real-time P2P mesh events
# ---------------------------------------------------------------------------

@router.websocket("/ws/p2p")
async def ws_p2p(websocket: WebSocket):
    """Stream P2P cluster events (peer list, status changes) over WebSocket."""
    if not await _ws_auth(websocket):
        await websocket.close(code=4003, reason="Unauthorized")
        return

    await websocket.accept()
    logger.info("WS /ws/p2p connected")

    cluster: object | None = getattr(websocket.app.state, "cluster", None)
    if cluster is None:
        await websocket.send_text(_json_payload("error", {"detail": "Cluster manager not initialized"}))
        await websocket.close(code=1011)
        return

    # Send initial peer snapshot.
    try:
        peers = [asdict(p) for p in cluster.peers]
        p2p_status = cluster.p2p_status()
        await websocket.send_text(_json_payload("p2p_snapshot", {
            "peers": peers,
            "p2p_status": p2p_status,
            "node_id": cluster.node_id,
        }))
    except Exception:
        logger.exception("WS /ws/p2p failed to build initial snapshot")

    # Poll for changes periodically (the cluster manager does not expose a
    # subscription mechanism, so we diff on a short interval).
    _POLL_INTERVAL: float = 5.0
    last_peer_ids: set[str] = {p.peer_id for p in cluster.peers}

    try:
        while True:
            await asyncio.sleep(_POLL_INTERVAL)

            current_peers = cluster.peers
            current_ids = {p.peer_id for p in current_peers}

            joined = current_ids - last_peer_ids
            left = last_peer_ids - current_ids

            if joined or left:
                await websocket.send_text(_json_payload("p2p_update", {
                    "peers": [asdict(p) for p in current_peers],
                    "joined": list(joined),
                    "left": list(left),
                }))
                last_peer_ids = current_ids
            else:
                # Keepalive
                await websocket.send_text(_json_payload("ping", {"ts": datetime.now(UTC).isoformat()}))
    except WebSocketDisconnect:
        logger.info("WS /ws/p2p disconnected")
    except Exception:
        logger.exception("WS /ws/p2p unexpected error")


# ---------------------------------------------------------------------------
# WS /ws/health — periodic health updates
# ---------------------------------------------------------------------------

@router.websocket("/ws/health")
async def ws_health(websocket: WebSocket):
    """Push periodic health snapshots every ~5 seconds."""
    if not await _ws_auth(websocket):
        await websocket.close(code=4003, reason="Unauthorized")
        return

    await websocket.accept()
    logger.info("WS /ws/health connected")

    _HEALTH_INTERVAL: float = 5.0

    try:
        while True:
            health_data: dict = {"status": "ok"}

            app_state = websocket.app.state

            # Provider status
            if hasattr(app_state, "router") and app_state.router is not None:
                health_data["providers"] = app_state.router.available_providers
                try:
                    hm = app_state.router.health_monitor
                    all_health = hm.get_all_health()
                    cb = app_state.router.circuit_breaker
                    providers_detail: dict = {}
                    for name, ph in all_health.items():
                        d = asdict(ph)
                        d["circuit_breaker_state"] = cb.get_state(name)
                        providers_detail[name] = d
                    health_data["provider_details"] = providers_detail
                except Exception:
                    pass  # health monitor may not be ready

            # Agent count
            if hasattr(app_state, "registry") and app_state.registry is not None:
                health_data["agents"] = len(app_state.registry)

            # Scheduler state
            if hasattr(app_state, "scheduler") and app_state.scheduler is not None:
                scheduler = app_state.scheduler
                health_data["scheduler"] = {
                    "workers": len(getattr(scheduler, "workers", [])),
                    "enabled": True,
                }

            # Cluster / P2P
            if hasattr(app_state, "cluster") and app_state.cluster is not None:
                try:
                    health_data["p2p"] = app_state.cluster.p2p_status()
                    health_data["peers"] = len(app_state.cluster.peers)
                except Exception:
                    pass

            health_data["ts"] = datetime.now(UTC).isoformat()

            await websocket.send_text(_json_payload("health", health_data))
            await asyncio.sleep(_HEALTH_INTERVAL)
    except WebSocketDisconnect:
        logger.info("WS /ws/health disconnected")
    except Exception:
        logger.exception("WS /ws/health unexpected error")
