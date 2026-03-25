"""Tests for Mistral Studio integration — datasets, fine-tuning jobs, model management.

Lot 24: T-MS-002 to T-MS-033
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import httpx
import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_studio(api_key: str = "test-key"):
    """Create a MistralStudio with a test key (bypasses settings lookup)."""
    from mascarade.integrations.mistral_studio import MistralStudio

    return MistralStudio(api_key=api_key)


def _mock_response(json_data: dict, status_code: int = 200) -> httpx.Response:
    """Build a fake httpx.Response."""
    return httpx.Response(
        status_code=status_code,
        json=json_data,
        request=httpx.Request("GET", "https://api.mistral.ai/v1/test"),
    )


# ---------------------------------------------------------------------------
# 1. upload_dataset
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_upload_dataset_success(tmp_path):
    """T-MS-002: upload a JSONL file and get back a file object."""
    dataset = tmp_path / "train.jsonl"
    dataset.write_text('{"messages": [{"role": "user", "content": "hi"}]}\n')

    fake_resp = _mock_response(
        {
            "id": "file-abc123",
            "filename": "train.jsonl",
            "bytes": 55,
            "purpose": "fine-tune",
        }
    )

    with patch(
        "httpx.AsyncClient.post", new_callable=AsyncMock, return_value=fake_resp
    ):
        studio = _make_studio()
        result = await studio.upload_dataset(str(dataset))

    assert result["id"] == "file-abc123"
    assert result["purpose"] == "fine-tune"


@pytest.mark.asyncio
async def test_upload_dataset_file_not_found():
    """T-MS-003: uploading a non-existent file raises FileNotFoundError."""
    studio = _make_studio()
    with pytest.raises(FileNotFoundError):
        await studio.upload_dataset("/tmp/does_not_exist_xyz.jsonl")


# ---------------------------------------------------------------------------
# 2. create_finetune_job
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_finetune_job_success():
    """T-MS-010: create a fine-tuning job with minimal parameters."""
    fake_resp = _mock_response(
        {
            "id": "ftjob-001",
            "model": "open-mistral-7b",
            "status": "queued",
            "training_files": [{"file_id": "file-abc123", "weight": 1}],
        }
    )

    with patch(
        "httpx.AsyncClient.post", new_callable=AsyncMock, return_value=fake_resp
    ):
        studio = _make_studio()
        result = await studio.create_finetune_job(
            model="open-mistral-7b",
            training_file_id="file-abc123",
        )

    assert result["id"] == "ftjob-001"
    assert result["status"] == "queued"


@pytest.mark.asyncio
async def test_create_finetune_job_with_hyperparameters():
    """T-MS-011: create a fine-tuning job with hyperparameters and suffix."""
    fake_resp = _mock_response(
        {
            "id": "ftjob-002",
            "model": "open-mistral-7b",
            "status": "queued",
            "hyperparameters": {"training_steps": 100, "learning_rate": 1e-5},
            "suffix": "my-model",
        }
    )

    with patch(
        "httpx.AsyncClient.post", new_callable=AsyncMock, return_value=fake_resp
    ) as mock_post:
        studio = _make_studio()
        result = await studio.create_finetune_job(
            model="open-mistral-7b",
            training_file_id="file-abc123",
            hyperparameters={"training_steps": 100, "learning_rate": 1e-5},
            suffix="my-model",
        )

    assert result["suffix"] == "my-model"
    # Verify the payload included hyperparameters
    call_kwargs = mock_post.call_args
    sent_json = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
    assert sent_json["hyperparameters"]["training_steps"] == 100


# ---------------------------------------------------------------------------
# 3. list_finetune_jobs
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_finetune_jobs():
    """T-MS-015: list all fine-tuning jobs."""
    fake_resp = _mock_response(
        {
            "data": [
                {"id": "ftjob-001", "status": "succeeded"},
                {"id": "ftjob-002", "status": "running"},
            ],
        }
    )

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=fake_resp):
        studio = _make_studio()
        jobs = await studio.list_finetune_jobs()

    assert len(jobs) == 2
    assert jobs[0]["id"] == "ftjob-001"


# ---------------------------------------------------------------------------
# 4. get_finetune_job
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_finetune_job():
    """T-MS-020: get a specific job by id."""
    fake_resp = _mock_response(
        {
            "id": "ftjob-001",
            "status": "running",
            "trained_tokens": 50000,
        }
    )

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=fake_resp):
        studio = _make_studio()
        job = await studio.get_finetune_job("ftjob-001")

    assert job["id"] == "ftjob-001"
    assert job["trained_tokens"] == 50000


# ---------------------------------------------------------------------------
# 5. cancel_finetune_job
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cancel_finetune_job():
    """T-MS-025: cancel a running job."""
    fake_resp = _mock_response({"id": "ftjob-001", "status": "cancelled"})

    with patch(
        "httpx.AsyncClient.post", new_callable=AsyncMock, return_value=fake_resp
    ):
        studio = _make_studio()
        result = await studio.cancel_finetune_job("ftjob-001")

    assert result["status"] == "cancelled"


# ---------------------------------------------------------------------------
# 6. list_models
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_models():
    """T-MS-028: list models including fine-tuned ones."""
    fake_resp = _mock_response(
        {
            "data": [
                {"id": "open-mistral-7b", "object": "model"},
                {"id": "ft:open-mistral-7b:my-model:ftjob-001", "object": "model"},
            ],
        }
    )

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=fake_resp):
        studio = _make_studio()
        models = await studio.list_models()

    assert len(models) == 2
    assert any("ft:" in m["id"] for m in models)


# ---------------------------------------------------------------------------
# 7. delete_model
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_model():
    """T-MS-030: delete a fine-tuned model."""
    fake_resp = _mock_response(
        {"id": "ft:open-mistral-7b:my-model:ftjob-001", "deleted": True}
    )

    with patch(
        "httpx.AsyncClient.delete", new_callable=AsyncMock, return_value=fake_resp
    ):
        studio = _make_studio()
        result = await studio.delete_model("ft:open-mistral-7b:my-model:ftjob-001")

    assert result["deleted"] is True


# ---------------------------------------------------------------------------
# 8. API key not configured
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_api_key_not_configured():
    """T-MS-033: MistralStudio raises when API key is missing."""
    from mascarade.integrations.mistral_studio import MistralStudio

    with patch("mascarade.integrations.mistral_studio.settings") as mock_settings:
        mock_settings.mistral_api_key = ""
        with pytest.raises(RuntimeError, match="MISTRAL_API_KEY not configured"):
            MistralStudio()


# ---------------------------------------------------------------------------
# 9. HTTP error propagation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_http_error_propagation():
    """Fine-tuning API errors are propagated as httpx.HTTPStatusError."""
    error_resp = httpx.Response(
        status_code=422,
        json={"error": {"message": "Invalid training file"}},
        request=httpx.Request("POST", "https://api.mistral.ai/v1/fine_tuning/jobs"),
    )

    with patch(
        "httpx.AsyncClient.post", new_callable=AsyncMock, return_value=error_resp
    ):
        studio = _make_studio()
        with pytest.raises(httpx.HTTPStatusError):
            await studio.create_finetune_job(
                model="open-mistral-7b",
                training_file_id="file-invalid",
            )


# ---------------------------------------------------------------------------
# 10. Router endpoint integration (upload_dataset via TestClient)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_router_upload_dataset():
    """T-MS-005: router upload endpoint validates file extension."""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from mascarade.routers.mistral_studio import router

    app = FastAPI()
    app.include_router(router)

    # Bypass auth
    from mascarade.auth import require_auth

    app.dependency_overrides[require_auth] = lambda: None

    client = TestClient(app)

    # Upload a .txt file should fail with 400
    resp = client.post(
        "/v1/api/mistral-studio/datasets",
        files={"file": ("bad.txt", b"not jsonl", "text/plain")},
        data={"purpose": "fine-tune"},
    )
    assert resp.status_code == 400
    assert "Unsupported file type" in resp.json()["detail"]
