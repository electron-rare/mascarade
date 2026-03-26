"""Cluster and P2P mesh networking endpoints."""

from __future__ import annotations

import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from mascarade.auth import require_auth
from mascarade.observability import iso_utc_now

logger = logging.getLogger("mascarade.routers.cluster")

router = APIRouter(
    prefix="/api/cluster",
    dependencies=[Depends(require_auth)],
    tags=["cluster"],
)


class ClusterForwardRequest(BaseModel):
    messages: list[dict] = Field(max_length=200)
    strategy: str = "best"
    routing_policy: str = "auto"
    provider: str | None = None
    model: str | None = None
    system: str | None = None
    temperature: float = 0.7
    max_tokens: int = 4096
    project_id: str | None = Field(default=None, max_length=256)
    federation_scope: list[str] | None = None
    knowledge_scope: str = "project"
    peer_id: str | None = None
    preferred_role: str | None = None
    allow_local: bool = True


class P2PTaskRequest(BaseModel):
    capability: str = Field(min_length=1, max_length=200)
    payload: dict = Field(default_factory=dict)
    timeout: float = Field(default=120.0, ge=1.0, le=600.0)
    target_peer: str | None = None


# --- Identity & Peers ---


@router.get("/identity")
async def cluster_identity(request: Request):
    """Get this node's cluster identity."""
    cluster = request.app.state.cluster
    return cluster.local_identity().to_dict()


@router.get("/peers")
async def cluster_peers(request: Request):
    """Probe and list all known cluster peers."""
    cluster = request.app.state.cluster
    peers = await cluster.probe_peers()
    return {
        "node": cluster.local_identity().to_dict(),
        "peers": [peer.to_dict() for peer in peers],
    }


@router.post("/forward/send")
async def cluster_forward_send(req: ClusterForwardRequest, request: Request):
    """Forward a send request to a specific peer or role in the cluster."""
    cluster = request.app.state.cluster
    payload = req.model_dump(exclude={"peer_id", "preferred_role", "allow_local"})
    return await cluster.forward_send(
        peer_id=req.peer_id,
        preferred_role=req.preferred_role,
        allow_local=req.allow_local,
        payload=payload,
    )


# --- P2P Network ---


@router.get("/p2p/status")
async def cluster_p2p_status(request: Request):
    """Get P2P mesh network status."""
    cluster = request.app.state.cluster
    return cluster.p2p_status()


@router.get("/p2p/topology")
async def cluster_p2p_topology(request: Request):
    """JSON snapshot of the P2P network topology."""
    node = getattr(request.app.state.cluster, "_p2p_node", None)
    if node is None or not hasattr(node, "capabilities"):
        raise HTTPException(status_code=503, detail="P2P node not available")

    nodes = []
    edges = []
    all_caps = node.capabilities.all_capabilities()

    # Local node
    local_caps = node.capabilities._local_caps
    nodes.append(
        {
            "peer_id": node.peer_id,
            "label": local_caps.label if local_caps else "",
            "role": local_caps.role if local_caps else "general",
            "capabilities": local_caps.capabilities if local_caps else [],
            "http_base_url": local_caps.http_base_url if local_caps else None,
            "is_local": True,
        }
    )

    # Remote peers
    for pid, caps in all_caps.items():
        nodes.append(
            {
                "peer_id": pid,
                "label": caps.label,
                "role": caps.role,
                "capabilities": caps.capabilities,
                "http_base_url": caps.http_base_url,
                "is_local": False,
            }
        )
        edges.append(
            {
                "from": node.peer_id,
                "to": pid,
                "connected": pid in node.transport.peers and node.transport.peers[pid].connected,
            }
        )

    return {"nodes": nodes, "edges": edges}


@router.post("/p2p/task")
async def cluster_p2p_task(req: P2PTaskRequest, request: Request):
    """Distribute a task via P2P to a capable peer."""
    cluster = request.app.state.cluster
    return await cluster.p2p_distribute_task(
        capability=req.capability,
        payload=req.payload,
        timeout=req.timeout,
        target_peer=req.target_peer,
    )


@router.get("/p2p/stream")
async def cluster_p2p_stream(
    request: Request,
    limit: int = Query(default=20, ge=0, le=200),
):
    """SSE stream of real-time P2P events."""
    import asyncio

    async def event_stream():
        node = getattr(request.app.state.cluster, "_p2p_node", None)
        if node is None or not hasattr(node, "events"):
            yield f"event: error\ndata: {json.dumps({'error': 'P2P node not available'})}\n\n"
            return

        bus = node.events
        queue = bus.subscribe()
        try:
            if limit > 0:
                for event in bus.recent(limit=limit):
                    yield f"event: p2p\ndata: {json.dumps(event.to_dict())}\n\n"

            while True:
                if await request.is_disconnected():
                    break
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=15)
                except TimeoutError:
                    yield f"event: heartbeat\ndata: {json.dumps({'ts': iso_utc_now()})}\n\n"
                    continue
                yield f"event: p2p\ndata: {json.dumps(event.to_dict())}\n\n"
        finally:
            bus.unsubscribe(queue)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
