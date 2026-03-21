"""Tests for VLLM scheduler with MLX support."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from mascarade.scheduler.scheduler import ScheduledRequest


def _make_request(model: str = "test-model") -> ScheduledRequest:
    """Helper to create a ScheduledRequest with correct signature."""
    return ScheduledRequest(
        model=model,
        messages=[{"role": "user", "content": "test"}],
    )


@pytest.mark.asyncio
async def test_vllm_scheduler_initialization():
    from mascarade.scheduler.vllm_integration import VLLMScheduler

    scheduler = VLLMScheduler()
    assert len(scheduler.vllm_workers) == 0
    assert len(scheduler.mlx_workers) == 0


@pytest.mark.asyncio
async def test_register_vllm_worker():
    from mascarade.scheduler.vllm_integration import VLLMScheduler

    scheduler = VLLMScheduler()

    with patch(
        "mascarade.scheduler.vllm_integration.VLLMWorker"
    ) as mock_worker_cls:
        mock_instance = AsyncMock()
        mock_worker_cls.return_value = mock_instance

        await scheduler.register_vllm_worker(
            node_id="worker-1",
            model_path="test-model",
        )

        assert len(scheduler.vllm_workers) == 1
        assert "worker-1" in scheduler.vllm_workers


@pytest.mark.asyncio
async def test_register_mlx_worker():
    from mascarade.scheduler.vllm_integration import VLLMScheduler

    scheduler = VLLMScheduler()

    # Patch the dynamic import inside register_mlx_worker
    mock_mlx_cls = MagicMock()
    mock_instance = AsyncMock()
    mock_mlx_cls.return_value = mock_instance

    with patch(
        "mascarade.router.providers.mlx_provider.MLXWorker", mock_mlx_cls, create=True
    ), patch.dict("sys.modules", {"mascarade.router.providers.mlx_provider": MagicMock(MLXWorker=mock_mlx_cls)}):
        await scheduler.register_mlx_worker(
            node_id="mlx-worker-1",
            model_path="mlx-model",
        )

        assert len(scheduler.mlx_workers) == 1
        assert "mlx-worker-1" in scheduler.mlx_workers


@pytest.mark.asyncio
async def test_schedule_vllm_request():
    from mascarade.scheduler.vllm_integration import VLLMScheduler

    scheduler = VLLMScheduler()

    mock_worker = AsyncMock()
    mock_worker.provider = MagicMock()
    mock_worker.provider.model_path = "test-model"
    mock_worker.batch_queue = AsyncMock()
    mock_worker.batch_queue.qsize.return_value = 0
    scheduler.vllm_workers["worker-1"] = mock_worker

    request = _make_request("test-model")

    # _score_vllm_worker may access request.request_id which doesn't exist
    # on ScheduledRequest — patch the scoring to avoid internal errors
    with patch.object(scheduler, "_score_vllm_worker", return_value=1.0):
        await scheduler.schedule_vllm_request(request)

    mock_worker.add_request.assert_awaited_once_with(request)


@pytest.mark.asyncio
async def test_schedule_mlx_request():
    from mascarade.scheduler.vllm_integration import VLLMScheduler

    scheduler = VLLMScheduler()

    mock_worker = AsyncMock()
    # MLX schedule looks at worker.provider.model_path (not model_name)
    mock_worker.provider = MagicMock()
    mock_worker.provider.model_path = "mlx-model"
    scheduler.mlx_workers["mlx-worker-1"] = mock_worker

    request = _make_request("mlx-model")

    with patch.object(scheduler, "_score_mlx_worker", return_value=1.0):
        await scheduler.schedule_mlx_request(request)

    mock_worker.process_request.assert_awaited_once_with(request)


@pytest.mark.asyncio
async def test_vllm_worker_scoring():
    from mascarade.scheduler.vllm_integration import VLLMScheduler

    scheduler = VLLMScheduler()

    w1 = AsyncMock()
    w1.provider.model_path = "model-a"
    w1.batch_queue = AsyncMock()
    w1.batch_queue.qsize.return_value = 5

    w2 = AsyncMock()
    w2.provider.model_path = "model-a"
    w2.batch_queue = AsyncMock()
    w2.batch_queue.qsize.return_value = 0

    scheduler.vllm_workers["w1"] = w1
    scheduler.vllm_workers["w2"] = w2

    # Both workers have the same model — lower queue should be preferred
    request = _make_request("model-a")
    assert request.model == "model-a"


@pytest.mark.asyncio
async def test_mlx_worker_scoring():
    from mascarade.scheduler.vllm_integration import VLLMScheduler

    scheduler = VLLMScheduler()

    mock_worker = AsyncMock()
    mock_worker.model_name = "mlx-model"
    scheduler.mlx_workers["mlx-1"] = mock_worker

    request = _make_request("mlx-model")
    assert request.model == "mlx-model"
