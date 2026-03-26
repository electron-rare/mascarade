"""API router for lm-evaluation-harness integration.

Provides endpoints to start, list, and inspect evaluation runs that use
EleutherAI's lm-evaluation-harness routed through Mascarade's LLM router.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel, Field

from mascarade.config import settings

logger = logging.getLogger("mascarade.routers.eval")

router = APIRouter(prefix="/v1/eval", tags=["eval"])

# ---------------------------------------------------------------------------
# Lazy singleton — created on first request so the import cost of
# lm-evaluation-harness is not paid at startup.
# ---------------------------------------------------------------------------
_runner = None


def _get_runner():  # noqa: ANN202
    global _runner  # noqa: PLW0603
    if not getattr(settings, "eval_harness_enabled", False):
        raise HTTPException(
            status_code=503,
            detail="Eval harness is disabled. Set EVAL_HARNESS_ENABLED=true.",
        )
    if _runner is None:
        try:
            from mascarade.benchmarks.eval_harness import EvalHarnessRunner

            _runner = EvalHarnessRunner()
        except ImportError as exc:
            raise HTTPException(
                status_code=503,
                detail=(
                    "lm-evaluation-harness is not installed. "
                    "Install with: pip install 'mascarade-core[eval]'"
                ),
            ) from exc
    return _runner


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------
class EvalRunRequest(BaseModel):
    task: str = Field(
        ...,
        description="Task name (hellaswag, mmlu, arc_easy, arc_challenge, truthfulqa_mc2, gsm8k)",
    )
    provider: str | None = Field(None, description="Provider to route to (optional)")
    model: str | None = Field(None, description="Model to use (optional)")
    num_samples: int | None = Field(
        None, ge=1, le=5000, description="Limit number of samples (optional)"
    )


class EvalRunResponse(BaseModel):
    run_id: str
    task: str
    provider: str
    model: str
    status: str
    message: str = ""


class EvalRunDetail(BaseModel):
    run_id: str
    task: str
    provider: str
    model: str
    status: str
    num_samples: int | None = None
    scores: dict[str, float] = {}
    error: str | None = None
    started_at: str | None = None
    completed_at: str | None = None
    duration_seconds: float = 0.0


# ---------------------------------------------------------------------------
# Background task wrapper
# ---------------------------------------------------------------------------
async def _run_eval_background(
    task: str,
    provider: str | None,
    model: str | None,
    num_samples: int | None,
    run_id: str,
) -> None:
    """Execute an eval run as a background task."""
    runner = _get_runner()
    result = await runner.run_eval(task, provider=provider, model=model, num_samples=num_samples)
    # The runner already stores the result internally; just log completion.
    logger.info(
        "Eval run %s completed: status=%s scores=%s",
        result.run_id,
        result.status,
        result.scores,
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@router.post("/run", response_model=EvalRunResponse)
async def start_eval_run(
    body: EvalRunRequest, background_tasks: BackgroundTasks
) -> EvalRunResponse:
    """Start a new evaluation run (executes in background)."""
    runner = _get_runner()

    from mascarade.benchmarks.eval_harness import (
        SUPPORTED_TASKS,
        EvalRunResult,
        EvalRunStatus,
    )

    if body.task not in SUPPORTED_TASKS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported task '{body.task}'. Supported: {sorted(SUPPORTED_TASKS)}",
        )

    # Pre-register the run so GET /runs shows it immediately as pending.
    run_id = runner._generate_run_id()
    pending = EvalRunResult(
        run_id=run_id,
        task=body.task,
        provider=body.provider or "best",
        model=body.model or "default",
        num_samples=body.num_samples,
        status=EvalRunStatus.PENDING,
    )
    runner.runs[run_id] = pending

    background_tasks.add_task(
        _run_eval_background,
        body.task,
        body.provider,
        body.model,
        body.num_samples,
        run_id,
    )

    return EvalRunResponse(
        run_id=run_id,
        task=body.task,
        provider=body.provider or "best",
        model=body.model or "default",
        status="pending",
        message="Eval run queued. Poll GET /v1/eval/runs/{run_id} for results.",
    )


@router.get("/runs", response_model=list[EvalRunDetail])
async def list_eval_runs() -> list[dict[str, Any]]:
    """List all evaluation runs."""
    runner = _get_runner()
    return runner.list_runs()


@router.get("/runs/{run_id}", response_model=EvalRunDetail)
async def get_eval_run(run_id: str) -> dict[str, Any]:
    """Get details and results of a specific evaluation run."""
    runner = _get_runner()
    result = runner.get_run(run_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Eval run '{run_id}' not found")
    return result.to_dict()
