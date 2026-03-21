"""Scheduler status and worker management endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from mascarade.auth import require_auth

router = APIRouter(prefix="/api", dependencies=[Depends(require_auth)], tags=["scheduler"])


@router.get("/scheduler/status")
async def scheduler_status(request: Request):
    """Get distributed scheduler status with all worker states."""
    scheduler = getattr(request.app.state, "scheduler", None)
    if scheduler is None or not scheduler.workers:
        return {"enabled": False, "workers": {}}

    return {"enabled": True, **scheduler.get_status()}


@router.get("/scheduler/workers")
async def list_workers(request: Request):
    """List all registered workers with health metrics."""
    scheduler = getattr(request.app.state, "scheduler", None)
    if scheduler is None:
        return {"workers": []}

    return {
        "workers": [w.to_dict() for w in scheduler.workers.values()],
    }


@router.get("/scheduler/workers/{node_id}")
async def get_worker(node_id: str, request: Request):
    """Get detailed state for a specific worker."""
    scheduler = getattr(request.app.state, "scheduler", None)
    if scheduler is None or node_id not in scheduler.workers:
        return {"error": f"Worker '{node_id}' not found"}, 404

    return scheduler.workers[node_id].to_dict()
