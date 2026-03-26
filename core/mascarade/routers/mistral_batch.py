"""Mistral Batch API integration — submit, poll, and retrieve batch inference jobs."""

from __future__ import annotations

import json
import logging
import time
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from mascarade.auth import require_auth
from mascarade.config import is_secret_configured, secret_value, settings

logger = logging.getLogger("mascarade.routers.mistral_batch")

router = APIRouter(
    prefix="/v1/api/mistral-batch",
    dependencies=[Depends(require_auth)],
    tags=["mistral-batch"],
)

# In-memory job tracker (lightweight — no DB needed)
_jobs: dict[str, dict[str, Any]] = {}


def _get_client():
    """Lazy-load Mistral client."""
    if not is_secret_configured(settings.mistral_api_key):
        raise HTTPException(status_code=503, detail="MISTRAL_API_KEY not configured")
    try:
        from mistralai.client import Mistral
    except ImportError:
        from mistralai import Mistral
    return Mistral(api_key=secret_value(settings.mistral_api_key))


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class BatchMessage(BaseModel):
    role: Literal["system", "user", "assistant"] = "user"
    content: str


class BatchRequest(BaseModel):
    custom_id: str = Field(max_length=100)
    body: dict[str, Any]


class BatchSubmitRequest(BaseModel):
    """Submit a batch of chat completion requests."""

    requests: list[BatchRequest] = Field(min_length=1, max_length=1000)
    model: str = Field(default="mistral-large-latest", max_length=100)
    endpoint: str = Field(default="/v1/chat/completions")
    metadata: dict[str, str] = Field(default_factory=dict)


class BatchJobResponse(BaseModel):
    job_id: str
    status: str
    model: str
    total_requests: int
    succeeded_requests: int = 0
    failed_requests: int = 0
    output_file: str | None = None
    created_at: str | None = None


# ---------------------------------------------------------------------------
# Presets — reusable batch templates
# ---------------------------------------------------------------------------

_PRESETS: dict[str, list[dict]] = {
    "ane-priority-models": [
        {
            "custom_id": "outline",
            "body": {
                "max_tokens": 256,
                "temperature": 0.3,
                "messages": [
                    {
                        "role": "system",
                        "content": "You are a story planner. Create a concise outline for a short story.",
                    },
                    {
                        "role": "user",
                        "content": "Create an outline for a 3-chapter mystery story set in a lighthouse. Include: premise, main character, and a brief summary of each chapter. Be concise — max 200 words.",
                    },
                ],
            },
        },
        {
            "custom_id": "structure",
            "body": {
                "max_tokens": 512,
                "temperature": 0.2,
                "messages": [
                    {
                        "role": "system",
                        "content": "You are a story structure assistant. Output valid JSON only, no markdown fences.",
                    },
                    {
                        "role": "user",
                        "content": "Create a structured JSON for a 3-chapter mystery story set in a lighthouse. Keys: title, premise, protagonist (name, trait), chapters (array of {number, title, summary}).",
                    },
                ],
            },
        },
        {
            "custom_id": "rewrite",
            "body": {
                "max_tokens": 256,
                "temperature": 0.7,
                "messages": [
                    {
                        "role": "system",
                        "content": "You are a literary prose writer. Write vivid, engaging prose. Preserve meaning while elevating the language.",
                    },
                    {
                        "role": "user",
                        "content": "Rewrite this opening paragraph into rich, literary prose:\n\n'The lighthouse keeper walked up the spiral stairs. The light was broken. He needed to fix it before the storm. The wind was getting stronger.'",
                    },
                ],
            },
        },
        {
            "custom_id": "gate",
            "body": {
                "max_tokens": 256,
                "temperature": 0.2,
                "messages": [
                    {
                        "role": "system",
                        "content": "You are a quality reviewer for creative writing. Evaluate the prose below on: clarity (1-5), engagement (1-5), originality (1-5). Output JSON: {clarity: N, engagement: N, originality: N, verdict: 'pass'|'revise', notes: '...'}",
                    },
                    {
                        "role": "user",
                        "content": "Evaluate this prose:\n\nThe keeper climbed the spiral stairs as wind howled outside, each step a percussion against the stone, each gust a whispered threat. Above, the great lens sat dark and cold — a dead eye staring out to sea.",
                    },
                ],
            },
        },
    ],
}


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/submit", response_model=BatchJobResponse)
async def submit_batch(req: BatchSubmitRequest):
    """Submit a batch of requests to Mistral Batch API."""
    client = _get_client()

    # Inject model into each request body if not set
    requests = []
    for r in req.requests:
        body = dict(r.body)
        if "model" not in body:
            body["model"] = req.model
        requests.append({"custom_id": r.custom_id, "body": body})

    try:
        job = client.batch.jobs.create(
            requests=requests,
            model=req.model,
            endpoint=req.endpoint,
            metadata=req.metadata,
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Mistral batch API error: {exc}") from exc

    # Track locally
    _jobs[job.id] = {
        "model": req.model,
        "created": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "request_count": len(requests),
    }

    return BatchJobResponse(
        job_id=job.id,
        status=job.status,
        model=req.model,
        total_requests=job.total_requests or len(requests),
        created_at=_jobs[job.id]["created"],
    )


@router.post("/presets/{preset_name}", response_model=BatchJobResponse)
async def submit_preset(preset_name: str, model: str = "mistral-large-latest"):
    """Submit a preset batch (e.g. 'ane-priority-models')."""
    if preset_name not in _PRESETS:
        raise HTTPException(
            status_code=404,
            detail=f"Preset '{preset_name}' not found. Available: {list(_PRESETS.keys())}",
        )

    client = _get_client()
    stages = _PRESETS[preset_name]

    # Inject model
    requests = []
    for stage in stages:
        body = dict(stage["body"])
        body["model"] = model
        requests.append({"custom_id": stage["custom_id"], "body": body})

    try:
        job = client.batch.jobs.create(
            requests=requests,
            model=model,
            endpoint="/v1/chat/completions",
            metadata={"preset": preset_name},
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Mistral batch API error: {exc}") from exc

    _jobs[job.id] = {
        "model": model,
        "preset": preset_name,
        "created": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "request_count": len(requests),
    }

    return BatchJobResponse(
        job_id=job.id,
        status=job.status,
        model=model,
        total_requests=job.total_requests or len(requests),
        created_at=_jobs[job.id]["created"],
    )


@router.get("/jobs/{job_id}", response_model=BatchJobResponse)
async def get_job_status(job_id: str):
    """Check the status of a batch job."""
    client = _get_client()
    try:
        job = client.batch.jobs.get(job_id=job_id)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Mistral API error: {exc}") from exc

    return BatchJobResponse(
        job_id=job.id,
        status=job.status,
        model=_jobs.get(job.id, {}).get("model", "unknown"),
        total_requests=job.total_requests or 0,
        succeeded_requests=job.succeeded_requests or 0,
        failed_requests=job.failed_requests or 0,
        output_file=job.output_file,
        created_at=_jobs.get(job.id, {}).get("created"),
    )


@router.get("/jobs/{job_id}/results")
async def get_job_results(job_id: str):
    """Download and parse batch job results."""
    client = _get_client()
    try:
        job = client.batch.jobs.get(job_id=job_id)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Mistral API error: {exc}") from exc

    if job.status != "SUCCESS":
        raise HTTPException(status_code=409, detail=f"Job not complete: {job.status}")

    if not job.output_file:
        raise HTTPException(status_code=404, detail="No output file available")

    try:
        content = client.files.download(file_id=job.output_file)
        raw = b""
        for chunk in content.stream:
            raw += chunk
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Failed to download results: {exc}") from exc

    # Parse JSONL
    results = []
    for line in raw.decode().strip().split("\n"):
        if not line.strip():
            continue
        entry = json.loads(line)
        cid = entry.get("custom_id", "?")
        resp = entry.get("response", {})
        body = resp.get("body", {})
        choices = body.get("choices", [])
        usage = body.get("usage", {})
        content_text = choices[0]["message"]["content"] if choices else ""

        results.append(
            {
                "custom_id": cid,
                "content": content_text,
                "usage": {
                    "prompt_tokens": usage.get("prompt_tokens", 0),
                    "completion_tokens": usage.get("completion_tokens", 0),
                },
            }
        )

    return {
        "job_id": job_id,
        "model": _jobs.get(job_id, {}).get("model", "unknown"),
        "status": job.status,
        "results": results,
    }


@router.post("/jobs/{job_id}/cancel")
async def cancel_job(job_id: str):
    """Cancel a batch job."""
    client = _get_client()
    try:
        job = client.batch.jobs.cancel(job_id=job_id)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Mistral API error: {exc}") from exc

    return {"job_id": job.id, "status": job.status}


@router.get("/presets")
async def list_presets():
    """List available batch presets."""
    return {
        name: {"stages": len(stages), "stage_ids": [s["custom_id"] for s in stages]}
        for name, stages in _PRESETS.items()
    }
