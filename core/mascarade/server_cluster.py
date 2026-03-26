"""Cluster-internal routes (/v1/cluster/node/*) authenticated via cluster secret."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, FastAPI, HTTPException

from mascarade.cluster import require_cluster_auth
from mascarade.config import settings
from mascarade.server_models import SendRequest

logger = logging.getLogger("mascarade.server")


def create_cluster_router(app: FastAPI) -> APIRouter:
    """Create and populate the cluster-protected APIRouter."""

    cluster_protected = APIRouter(
        prefix="/v1/cluster/node",
        dependencies=[Depends(require_cluster_auth)],
    )

    @cluster_protected.get("/identity")
    async def cluster_node_identity():
        return app.state.cluster.local_identity().to_dict()

    @cluster_protected.post("/send")
    async def cluster_node_send(req: SendRequest):
        messages = [m.model_dump() for m in req.messages]
        try:
            response = await app.state.router.send(
                messages,
                strategy=req.strategy,
                routing_policy=req.routing_policy,
                provider=req.provider,
                model=req.model,
                system=req.system,
                response_format=req.response_format,
                temperature=req.temperature,
                max_tokens=req.max_tokens,
            )
        except ValueError as exc:
            logger.warning("Cluster send request rejected: %s", exc)
            raise HTTPException(status_code=400, detail="Invalid request parameters") from exc

        return {
            "node_id": settings.node_id,
            "content": response.content,
            "model": response.model,
            "provider": response.provider,
            "usage": response.usage,
        }

    return cluster_protected
