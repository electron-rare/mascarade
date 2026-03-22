"""FastAPI router for Mistral Studio — datasets, fine-tuning jobs, model management."""

from __future__ import annotations

import logging
import tempfile
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field

from mascarade.auth import require_auth

logger = logging.getLogger("mascarade.routers.mistral_studio")

router = APIRouter(
    prefix="/v1/api/mistral-studio",
    dependencies=[Depends(require_auth)],
    tags=["mistral-studio"],
)


# ---------------------------------------------------------------------------
# Request / response schemas
# ---------------------------------------------------------------------------


class CreateFinetuneJobRequest(BaseModel):
    model: str = Field(..., description="Base model id (e.g. 'open-mistral-7b')")
    training_file_id: str = Field(..., description="Uploaded file id for training data")
    hyperparameters: dict[str, Any] | None = Field(
        default=None,
        description="Optional hyperparameters (training_steps, learning_rate, ...)",
    )
    suffix: str | None = Field(
        default=None,
        description="Optional suffix for the fine-tuned model name",
    )
    validation_file_id: str | None = Field(
        default=None,
        description="Optional validation file id",
    )


# ---------------------------------------------------------------------------
# Datasets
# ---------------------------------------------------------------------------


@router.post("/datasets")
async def upload_dataset(
    file: UploadFile = File(..., description="JSONL training dataset"),
    purpose: str = Form(default="fine-tune", description="Upload purpose"),
) -> dict[str, Any]:
    """Upload a JSONL dataset file for fine-tuning via Mistral API."""
    from mascarade.integrations.mistral_studio import MistralStudio

    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename is required")

    suffix = Path(file.filename).suffix
    if suffix.lower() not in (".jsonl", ".json"):
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{suffix}'. Expected .jsonl or .json",
        )

    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name

    try:
        studio = MistralStudio()
        return await studio.upload_dataset(tmp_path, purpose=purpose)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Failed to upload dataset")
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    finally:
        Path(tmp_path).unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Fine-tuning jobs
# ---------------------------------------------------------------------------


@router.post("/jobs")
async def create_finetune_job(body: CreateFinetuneJobRequest) -> dict[str, Any]:
    """Create a fine-tuning job on Mistral."""
    from mascarade.integrations.mistral_studio import MistralStudio

    try:
        studio = MistralStudio()
        return await studio.create_finetune_job(
            model=body.model,
            training_file_id=body.training_file_id,
            hyperparameters=body.hyperparameters,
            suffix=body.suffix,
            validation_file_id=body.validation_file_id,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Failed to create fine-tuning job")
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/jobs")
async def list_finetune_jobs() -> list[dict[str, Any]]:
    """List all fine-tuning jobs."""
    from mascarade.integrations.mistral_studio import MistralStudio

    try:
        studio = MistralStudio()
        return await studio.list_finetune_jobs()
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Failed to list fine-tuning jobs")
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/jobs/{job_id}")
async def get_finetune_job(job_id: str) -> dict[str, Any]:
    """Get fine-tuning job details."""
    from mascarade.integrations.mistral_studio import MistralStudio

    try:
        studio = MistralStudio()
        return await studio.get_finetune_job(job_id)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Failed to get fine-tuning job %s", job_id)
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post("/jobs/{job_id}/cancel")
async def cancel_finetune_job(job_id: str) -> dict[str, Any]:
    """Cancel a running fine-tuning job."""
    from mascarade.integrations.mistral_studio import MistralStudio

    try:
        studio = MistralStudio()
        return await studio.cancel_finetune_job(job_id)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Failed to cancel fine-tuning job %s", job_id)
        raise HTTPException(status_code=502, detail=str(exc)) from exc


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


@router.get("/models")
async def list_models() -> list[dict[str, Any]]:
    """List all models including fine-tuned."""
    from mascarade.integrations.mistral_studio import MistralStudio

    try:
        studio = MistralStudio()
        return await studio.list_models()
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Failed to list models")
        raise HTTPException(status_code=502, detail=str(exc)) from exc
