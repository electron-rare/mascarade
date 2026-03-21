"""Tests for MLX provider."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from mascarade.router.providers.mlx_provider import MLXProvider, MLXWorker
from mascarade.scheduler.scheduler import ScheduledRequest


@pytest.mark.asyncio
async def test_mlx_provider_initialization():
    """Test MLX provider initialization."""
    with patch('mlx_lm.load') as mock_load:
        mock_load.return_value = (MagicMock(), MagicMock())
        
        provider = MLXProvider(
            model_path="test-model",
            device="mps"
        )
        
        await provider.initialize()
        mock_load.assert_called_once()


@pytest.mark.asyncio
async def test_mlx_provider_generate():
    """Test MLX provider generation."""
    with patch('mlx_lm.load') as mock_load, \
         patch('mlx_lm.generate') as mock_generate:
        
        mock_load.return_value = (MagicMock(), MagicMock())
        mock_generate.return_value = "test response"
        
        provider = MLXProvider(
            model_path="test-model",
            device="mps"
        )
        
        request = ScheduledRequest(
            request_id="req-1",
            model="test-model",
            messages=[{"role": "user", "content": "test"}],
            max_tokens=100
        )
        
        response = await provider.generate(request)
        
        assert response.content == "test response"
        assert response.model == "test-model"


@pytest.mark.asyncio
async def test_mlx_worker_processing():
    """Test MLX worker request processing."""
    with patch('mlx_lm.load') as mock_load, \
         patch('mlx_lm.generate') as mock_generate:
        
        mock_load.return_value = (MagicMock(), MagicMock())
        mock_generate.return_value = "test response"
        
        worker = MLXWorker(
            node_id="test-worker",
            model_path="test-model"
        )
        
        request = ScheduledRequest(
            request_id="req-1",
            model="test-model",
            messages=[{"role": "user", "content": "test"}]
        )
        request.complete_callback = AsyncMock()
        
        response = await worker.process_request(request)
        
        assert response.content == "test response"
        request.complete_callback.assert_awaited_once_with(response)


@pytest.mark.asyncio
async def test_mlx_worker_status():
    """Test MLX worker status."""
    worker = MLXWorker(
        node_id="test-worker",
        model_path="test-model"
    )
    
    status = await worker.get_status()
    
    assert status["node_id"] == "test-worker"
    assert status["model"] == "test-model"
    assert status["device"] == "mps"
    assert status["current_load"] == 0


def test_mlx_provider_without_mlx():
    """Test MLX provider when MLX is not available."""
    # Test that the provider can be imported even without MLX
    from mascarade.router.providers.mlx_provider import MLXProvider
    
    # Test that instantiation fails appropriately
    # We need to patch before import to avoid the RuntimeError during import
    import importlib
    import mascarade.router.providers.mlx_provider as mlx_module
    
    # Temporarily set MLX_AVAILABLE to False
    original_value = mlx_module.MLX_AVAILABLE
    mlx_module.MLX_AVAILABLE = False
    
    try:
        with pytest.raises(RuntimeError, match="MLX is not installed"):
            MLXProvider(model_path="test-model")
    finally:
        mlx_module.MLX_AVAILABLE = original_value
