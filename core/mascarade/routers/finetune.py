"""Fine-tuning job management endpoints."""

from __future__ import annotations

import time
import uuid
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from pydantic import BaseModel, Field

from mascarade.auth import require_auth
from mascarade.finetune.registry import FinetuneRegistry, RunEntry

router = APIRouter(
    prefix="/v1/api", dependencies=[Depends(require_auth)], tags=["finetune"]
)


# --- Models ---


JobStatus = Literal["pending", "training", "completed", "failed", "cancelled"]


class JobCreate(BaseModel):
    """Request model for creating a new fine-tuning job."""

    dataset: str = Field(min_length=1, max_length=500, description="Dataset path or ID")
    model: str = Field(min_length=1, max_length=200, description="Base model ID")
    method: str = Field(default="lora", max_length=50, description="Training method")
    node: str | None = Field(default=None, max_length=100, description="Target node ID")


class JobUpdate(BaseModel):
    """Request model for updating a job status."""

    status: JobStatus
    metrics: dict | None = Field(default=None)
    output_model: str | None = Field(default=None, max_length=500)


# --- Helper functions ---


def _serialize_job(entry: RunEntry) -> dict[str, object]:
    """
    Serialize a RunEntry to a dictionary for API response.

    Args:
        entry: RunEntry instance to serialize

    Returns:
        Dictionary containing job configuration and status
    """
    return {
        "job_id": entry.run_id,
        "base_model": entry.base_model,
        "dataset": entry.dataset,
        "method": entry.method,
        "node": entry.node,
        "status": entry.status,
        "metrics": entry.metrics,
        "output_model": entry.output_model,
        "started_at": entry.started_at,
        "completed_at": entry.completed_at,
    }


def _get_registry(request: Request) -> FinetuneRegistry:
    """
    Get or create the FinetuneRegistry from app state.

    Args:
        request: FastAPI request object

    Returns:
        FinetuneRegistry instance
    """
    if not hasattr(request.app.state, "finetune_registry"):
        request.app.state.finetune_registry = FinetuneRegistry()
    return request.app.state.finetune_registry


# --- Endpoints ---


@router.post("/finetune/jobs", status_code=201)
async def create_job(req: JobCreate, request: Request, response: Response):
    """
    Create a new fine-tuning job.

    Args:
        req: Job creation parameters including dataset and model
        request: FastAPI request object for accessing app state
        response: FastAPI response object for setting status code

    Returns:
        Serialized job object with status 201

    Raises:
        HTTPException: If job creation fails
    """
    registry = _get_registry(request)

    # Generate unique job ID
    job_id = f"job-{uuid.uuid4().hex[:12]}"

    # Create job entry
    entry = RunEntry(
        run_id=job_id,
        base_model=req.model,
        dataset=req.dataset,
        method=req.method,
        node=req.node or "auto",
        status="pending",
        metrics={},
        output_model="",
        started_at=time.time(),
        completed_at=None,
    )

    registry.add_run(entry)
    return _serialize_job(entry)


@router.get("/finetune/jobs")
async def list_jobs(
    request: Request,
    limit: int = Query(default=50, ge=1, le=200, description="Max items to return"),
    offset: int = Query(default=0, ge=0, description="Number of items to skip"),
):
    """
    List all fine-tuning jobs in the system with pagination.

    Args:
        request: FastAPI request object for accessing app state
        limit: Maximum number of jobs to return (1-200, default 50)
        offset: Number of jobs to skip (default 0)

    Returns:
        Dictionary with jobs list and pagination metadata
    """
    registry = _get_registry(request)
    all_jobs = list(registry.runs.values())
    total = len(all_jobs)
    page = all_jobs[offset : offset + limit]
    return {
        "jobs": [_serialize_job(entry) for entry in page],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/finetune/jobs/{job_id}")
async def get_job(job_id: str, request: Request):
    """
    Get a specific fine-tuning job by ID.

    Args:
        job_id: Job ID to retrieve
        request: FastAPI request object for accessing app state

    Returns:
        Serialized job object with all configuration and status details

    Raises:
        HTTPException: If job with the specified ID is not found (404)
    """
    registry = _get_registry(request)
    entry = registry.runs.get(job_id)

    if entry is None:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")

    return _serialize_job(entry)


@router.put("/finetune/jobs/{job_id}")
async def update_job(job_id: str, req: JobUpdate, request: Request):
    """
    Update a fine-tuning job's status and metadata.

    Args:
        job_id: Job ID to update
        req: Updated job status and optional metrics
        request: FastAPI request object for accessing app state

    Returns:
        Serialized job object with updated configuration

    Raises:
        HTTPException: If job is not found (404)
    """
    registry = _get_registry(request)
    entry = registry.runs.get(job_id)

    if entry is None:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")

    # Update job fields
    entry.status = req.status
    if req.metrics is not None:
        entry.metrics.update(req.metrics)
    if req.output_model is not None:
        entry.output_model = req.output_model

    # Set completion time if job is in terminal state
    if req.status in ("completed", "failed", "cancelled"):
        entry.completed_at = time.time()

    registry.add_run(entry)
    return _serialize_job(entry)


@router.delete("/finetune/jobs/{job_id}")
async def delete_job(job_id: str, request: Request):
    """
    Cancel and remove a fine-tuning job.

    Args:
        job_id: Job ID to delete
        request: FastAPI request object for accessing app state

    Returns:
        Success message confirming deletion

    Raises:
        HTTPException: If job is not found (404) or is already completed (400)
    """
    registry = _get_registry(request)
    entry = registry.runs.get(job_id)

    if entry is None:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")

    # Only allow deletion of non-completed jobs
    if entry.status in ("completed", "failed"):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot delete job in '{entry.status}' state. Job is already finished.",
        )

    # Mark as cancelled before deletion
    entry.status = "cancelled"
    entry.completed_at = time.time()
    registry.add_run(entry)

    return {"message": f"Job '{job_id}' cancelled successfully"}
