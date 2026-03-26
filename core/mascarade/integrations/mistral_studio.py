"""Mistral Studio integration — datasets, fine-tuning jobs, model management.

Uses the Mistral fine-tuning API endpoints:
- POST /v1/files — Upload training files (JSONL)
- POST /v1/fine_tuning/jobs — Create fine-tuning job
- GET /v1/fine_tuning/jobs — List jobs
- GET /v1/fine_tuning/jobs/{job_id} — Get job status
- POST /v1/fine_tuning/jobs/{job_id}/cancel — Cancel job
- GET /v1/models — List models (includes fine-tuned)
- DELETE /v1/models/{model_id} — Delete model

Reference: https://docs.mistral.ai/capabilities/finetuning/
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import httpx

from mascarade.config import is_secret_configured, secret_value, settings

logger = logging.getLogger("mascarade.integrations.mistral_studio")

_API_BASE = "https://api.mistral.ai/v1"
_TIMEOUT = httpx.Timeout(300.0, connect=15.0)


def _get_api_key() -> str:
    """Resolve the Mistral API key or raise."""
    api_key = secret_value(settings.mistral_api_key).strip()
    if not is_secret_configured(api_key):
        raise RuntimeError("MISTRAL_API_KEY not configured")
    return api_key


def _auth_headers(api_key: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {api_key}"}


class MistralStudio:
    """Client for Mistral fine-tuning and model management API."""

    def __init__(self, *, api_key: str | None = None, base_url: str = _API_BASE):
        self._api_key = api_key or _get_api_key()
        self._base_url = base_url.rstrip("/")

    def _headers(self) -> dict[str, str]:
        return _auth_headers(self._api_key)

    # ------------------------------------------------------------------
    # Datasets
    # ------------------------------------------------------------------

    async def upload_dataset(
        self,
        file_path: str,
        purpose: str = "fine-tune",
    ) -> dict[str, Any]:
        """Upload a JSONL dataset file for fine-tuning.

        POST /v1/files with multipart/form-data.

        Args:
            file_path: Local path to a JSONL file.
            purpose: Upload purpose, typically ``"fine-tune"``.

        Returns:
            Mistral file object (id, filename, bytes, purpose, ...).
        """
        p = Path(file_path)
        if not p.exists():
            raise FileNotFoundError(f"Dataset file not found: {file_path}")

        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            with p.open("rb") as f:
                resp = await client.post(
                    f"{self._base_url}/files",
                    headers=self._headers(),
                    files={"file": (p.name, f, "application/jsonl")},
                    data={"purpose": purpose},
                )
            resp.raise_for_status()
            result: dict[str, Any] = resp.json()
            logger.info("Uploaded dataset %s -> file_id=%s", p.name, result.get("id"))
            return result

    # ------------------------------------------------------------------
    # Fine-tuning jobs
    # ------------------------------------------------------------------

    async def create_finetune_job(
        self,
        model: str,
        training_file_id: str,
        hyperparameters: dict[str, Any] | None = None,
        suffix: str | None = None,
        validation_file_id: str | None = None,
    ) -> dict[str, Any]:
        """Create a fine-tuning job.

        POST /v1/fine_tuning/jobs

        Args:
            model: Base model id (e.g. ``"open-mistral-7b"``).
            training_file_id: File id returned by ``upload_dataset``.
            hyperparameters: Optional dict with training_steps, learning_rate, etc.
            suffix: Optional suffix for the fine-tuned model name.
            validation_file_id: Optional validation file id.

        Returns:
            Fine-tuning job object.
        """
        payload: dict[str, Any] = {
            "model": model,
            "training_files": [{"file_id": training_file_id, "weight": 1}],
        }
        if hyperparameters:
            payload["hyperparameters"] = hyperparameters
        if suffix:
            payload["suffix"] = suffix
        if validation_file_id:
            payload["validation_files"] = [{"file_id": validation_file_id, "weight": 1}]

        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.post(
                f"{self._base_url}/fine_tuning/jobs",
                headers={**self._headers(), "Content-Type": "application/json"},
                json=payload,
            )
            resp.raise_for_status()
            result: dict[str, Any] = resp.json()
            logger.info("Created fine-tuning job %s for model %s", result.get("id"), model)
            return result

    async def list_finetune_jobs(self) -> list[dict[str, Any]]:
        """List all fine-tuning jobs.

        GET /v1/fine_tuning/jobs

        Returns:
            List of fine-tuning job objects.
        """
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(
                f"{self._base_url}/fine_tuning/jobs",
                headers=self._headers(),
            )
            resp.raise_for_status()
            data: dict[str, Any] = resp.json()
            return data.get("data", [])

    async def get_finetune_job(self, job_id: str) -> dict[str, Any]:
        """Get fine-tuning job details.

        GET /v1/fine_tuning/jobs/{job_id}

        Args:
            job_id: The fine-tuning job id.

        Returns:
            Fine-tuning job object with status, metrics, etc.
        """
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(
                f"{self._base_url}/fine_tuning/jobs/{job_id}",
                headers=self._headers(),
            )
            resp.raise_for_status()
            return resp.json()

    async def cancel_finetune_job(self, job_id: str) -> dict[str, Any]:
        """Cancel a running fine-tuning job.

        POST /v1/fine_tuning/jobs/{job_id}/cancel

        Args:
            job_id: The fine-tuning job id to cancel.

        Returns:
            Updated job object with cancelled status.
        """
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.post(
                f"{self._base_url}/fine_tuning/jobs/{job_id}/cancel",
                headers=self._headers(),
            )
            resp.raise_for_status()
            return resp.json()

    # ------------------------------------------------------------------
    # Models
    # ------------------------------------------------------------------

    async def list_models(self) -> list[dict[str, Any]]:
        """List all models including fine-tuned.

        GET /v1/models

        Returns:
            List of model objects.
        """
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(
                f"{self._base_url}/models",
                headers=self._headers(),
            )
            resp.raise_for_status()
            data: dict[str, Any] = resp.json()
            return data.get("data", [])

    async def delete_model(self, model_id: str) -> dict[str, Any]:
        """Delete a fine-tuned model.

        DELETE /v1/models/{model_id}

        Args:
            model_id: The model id to delete.

        Returns:
            Deletion confirmation object.
        """
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.delete(
                f"{self._base_url}/models/{model_id}",
                headers=self._headers(),
            )
            resp.raise_for_status()
            return resp.json()
