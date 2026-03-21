"""Tests for VLLM scheduler with MLX support."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from mascarade.scheduler.vllm_integration import VLLMScheduler, VLLMWorker
from mascarade.scheduler.scheduler import ScheduledRequest


@pytest.mark.asyncio
async def test_vllm_scheduler_initialization():
    """Test VLLM scheduler initialization."""
    scheduler = VLLMScheduler()
    assert len(scheduler.vllm_workers) == 0
    assert len(scheduler.mlx_workers) == 0


@pytest.mark.asyncio
async def test_register_vllm_worker():
    """Test registering a vLLM worker."""
    scheduler = VLLMScheduler()
    
    with patch('mascarade.scheduler.vllm_integration.VLLMWorker') as mock_worker:
        mock_instance = AsyncMock()
        mock_worker.return_value = mock_instance
        
        await scheduler.register_vllm_worker(
            node_id="worker-1",
            model_path="test-model"
        )
        
        assert len(scheduler.vllm_workers) == 1
        assert "worker-1" in scheduler.vllm_workers
        assert len(scheduler.workers) == 1


@pytest.mark.asyncio
async def test_register_mlx_worker():
    """Test registering an MLX worker."""
    scheduler = VLLMScheduler()
    
    with patch('mascarade.scheduler.vllm_integration.MLXWorker') as mock_worker:
        mock_instance = AsyncMock()
        mock_worker.return_value = mock_instance
        
        await scheduler.register_mlx_worker(
            node_id="mlx-worker-1",
            model_path="mlx-model"
        )
        
        assert len(scheduler.mlx_workers) == 1
        assert "mlx-worker-1" in scheduler.mlx_workers
        assert len(scheduler.workers) == 1


@pytest.mark.asyncio
async def test_schedule_vllm_request():
    """Test scheduling a vLLM request."""
    scheduler = VLLMScheduler()
    
    # Create mock worker
    mock_worker = AsyncMock()
    mock_worker.provider.model_path = "test-model"
    scheduler.vllm_workers["worker-1"] = mock_worker
    
    request = ScheduledRequest(
        request_id="req-1",
        model="test-model",
        messages=[{"role": "user", "content": "test"}]
    )
    
    await scheduler.schedule_vllm_request(request)
    
    mock_worker.add_request.assert_awaited_once_with(request)


@pytest.mark.asyncio
async def test_schedule_mlx_request():
    """Test scheduling an MLX request."""
    scheduler = VLLMScheduler()
    
    # Create mock worker
    mock_worker = AsyncMock()
    mock_worker.provider.model_path = "mlx-model"
    scheduler.mlx_workers["mlx-worker-1"] = mock_worker
    
    request = ScheduledRequest(
        request_id="req-1",
        model="mlx-model",
        messages=[{"role": "user", "content": "test"}]
    )
    
    await scheduler.schedule_mlx_request(request)
    
    mock_worker.process_request.assert_awaited_once_with(request)


@pytest.mark.asyncio
async def test_vllm_worker_scoring():
    """Test vLLM worker scoring."""
    scheduler = VLLMScheduler()
    
    # Create worker
    worker = AsyncMock()
    worker.provider.model_path = "test-model"
    worker.batch_queue.qsize.return_value = 2
    worker.provider.gpu_memory_utilization = 0.9
    
    request = ScheduledRequest(
        request_id="req-1",
        model="test-model",
        messages=[{"role": "user", "content": "test"}]
    )
    
    score = scheduler._score_vllm_worker(worker, request)
    
    # Should have high score (model affinity + low load + high GPU utilization)
    assert score > 80


@pytest.mark.asyncio
async def test_mlx_worker_scoring():
    """Test MLX worker scoring."""
    from mascarade.router.providers.mlx_provider import MLXWorker
    
    scheduler = VLLMScheduler()
    
    # Create worker
    worker = AsyncMock()
    worker.provider.model_path = "mlx-model"
    worker.provider.device = "mps"
    worker.current_requests = {}
    
    request = ScheduledRequest(
        request_id="req-1",
        model="mlx-model",
        messages=[{"role": "user", "content": "test"}]
    )
    
    score = scheduler._score_mlx_worker(worker, request)
    
    # Should have high score (model affinity + no load + MPS device)
    assert score > 90


@pytest.mark.asyncio
async def test_get_worker_statuses():
    """Test getting worker statuses."""
    scheduler = VLLMScheduler()
    
    # Create mock workers
    vllm_worker = AsyncMock()
    vllm_worker.get_status.return_value = {"status": "ready"}
    scheduler.vllm_workers["vllm-1"] = vllm_worker
    
    mlx_worker = AsyncMock()
    mlx_worker.get_status.return_value = {"status": "ready"}
    scheduler.mlx_workers["mlx-1"] = mlx_worker
    
    vllm_status = await scheduler.get_vllm_status()
    mlx_status = await scheduler.get_mlx_status()
    
    assert "vllm-1" in vllm_status
    assert "mlx-1" in mlx_status


@pytest.mark.asyncio
async def test_close_all_workers():
    """Test closing all workers."""
    scheduler = VLLMScheduler()
    
    # Create mock workers
    vllm_worker = AsyncMock()
    mlx_worker = AsyncMock()
    
    scheduler.vllm_workers["vllm-1"] = vllm_worker
    scheduler.mlx_workers["mlx-1"] = mlx_worker
    
    await scheduler.close_all()
    
    vllm_worker.close.assert_awaited_once()
    mlx_worker.close.assert_awaited_once()
    assert len(scheduler.vllm_workers) == 0
    assert len(scheduler.mlx_workers) == 0
