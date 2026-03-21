"""Analytics routes — benchmark leaderboard and provider statistics."""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from mascarade.benchmarks.storage import BenchmarkStorage

logger = logging.getLogger("mascarade.routers.analytics")

router = APIRouter(prefix="/v1/analytics", tags=["analytics"])

VALID_ORDER_BY = {"quality_score", "latency_p50", "latency_p95", "cost", "error_rate"}


@router.get("/benchmarks")
async def get_benchmarks(
    domain: Optional[str] = Query(None, description="Filter by domain"),
    limit: int = Query(10, ge=1, le=100, description="Max results"),
    order_by: str = Query("quality_score", description="Column to order by"),
):
    """Query benchmark leaderboard."""
    if order_by not in VALID_ORDER_BY:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid order_by parameter: '{order_by}'. "
            f"Valid options: {', '.join(sorted(VALID_ORDER_BY))}",
        )

    storage = BenchmarkStorage()
    results = storage.query_leaderboard(
        domain=domain,
        limit=limit,
        order_by=order_by,
    )

    return {
        "results": results,
        "count": len(results),
        "filters": {
            "domain": domain,
            "limit": limit,
            "order_by": order_by,
        },
    }
