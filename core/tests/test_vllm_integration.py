"""Tests for vLLM integration and PagedAttention."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mascarade.scheduler.paged_attention import PagedAttentionManager
from mascarade.scheduler.scheduler import ScheduledRequest
from mascarade.scheduler.vllm_integration import VLLMScheduler, VLLMWorker


@pytest.mark.asyncio
async def test_vllm_worker_initialization():
    """Test VLLM worker initialization."""
    worker = VLLMWorker(
        node_id="test-worker", model_path="test-model", tensor_parallel_size=1
    )

    # Mock the provider initialization
    worker.provider.initialize = AsyncMock()

    await worker.initialize()
    worker.provider.initialize.assert_awaited_once()


@pytest.mark.asyncio
async def test_vllm_worker_request_processing():
    """Test VLLM worker request processing."""
    worker = VLLMWorker(node_id="test-worker", model_path="test-model")

    # Mock dependencies
    worker.provider.generate = AsyncMock(return_value=MagicMock())

    request = ScheduledRequest(
        request_id="req-1",
        model="test-model",
        messages=[{"role": "user", "content": "test"}],
        max_tokens=100,
    )
    request.complete_callback = AsyncMock()

    await worker.add_request(request)

    # Process the batch
    await worker._process_batches()

    # Verify
    worker.provider.generate.assert_awaited_once()
    request.complete_callback.assert_awaited_once()


@pytest.mark.asyncio
async def test_vllm_scheduler_registration():
    """Test VLLM scheduler worker registration."""
    scheduler = VLLMScheduler()

    # Mock vLLM worker
    with patch("mascarade.scheduler.vllm_integration.VLLMWorker") as mock_worker:
        mock_instance = AsyncMock()
        mock_worker.return_value = mock_instance

        await scheduler.register_vllm_worker(
            node_id="worker-1", model_path="test-model"
        )

        # Verify worker was created and initialized
        mock_worker.assert_called_once()
        mock_instance.initialize.assert_awaited_once()

        # Verify regular worker was registered
        assert len(scheduler.workers) == 1
        assert "worker-1" in scheduler.workers


@pytest.mark.asyncio
async def test_vllm_scheduler_request_routing():
    """Test VLLM scheduler request routing."""
    scheduler = VLLMScheduler()

    # Create mock worker
    mock_worker = AsyncMock()
    mock_worker.provider.model_path = "test-model"
    scheduler.vllm_workers["worker-1"] = mock_worker

    request = ScheduledRequest(
        request_id="req-1",
        model="test-model",
        messages=[{"role": "user", "content": "test"}],
    )

    await scheduler.schedule_vllm_request(request)

    # Verify request was added to worker
    mock_worker.add_request.assert_awaited_once_with(request)


def test_paged_attention_allocation():
    """Test PagedAttention memory allocation."""
    manager = PagedAttentionManager(block_size=4, max_gpu_blocks=10, max_cpu_blocks=20)

    # Allocate a sequence
    seq_id = manager.allocate_sequence(10)  # 3 blocks needed

    # Verify allocation
    stats = manager.get_memory_stats()
    assert stats["gpu_blocks"]["used"] == 3
    assert stats["total_sequences"] == 1

    # Free the sequence
    manager.free_sequence(seq_id)

    # Verify cleanup
    stats = manager.get_memory_stats()
    assert stats["gpu_blocks"]["used"] == 0


def test_paged_attention_eviction():
    """Test PagedAttention block eviction."""
    manager = PagedAttentionManager(
        block_size=4, max_gpu_blocks=2, max_cpu_blocks=10  # Only 2 blocks
    )

    # Fill GPU
    manager.allocate_sequence(8)  # 2 blocks

    # This should trigger eviction
    manager.allocate_sequence(8)  # 2 blocks

    # Verify eviction happened
    stats = manager.get_memory_stats()
    assert stats["gpu_blocks"]["used"] == 2
    assert stats["cpu_blocks"]["used"] == 2


def test_paged_attention_retrieval():
    """Test sequence retrieval from PagedAttention."""
    import torch

    manager = PagedAttentionManager(block_size=4)

    # Allocate and set data
    seq_id = manager.allocate_sequence(10)

    # Get the sequence (simplified - in real usage this would be set by the model)
    retrieved = manager.get_sequence(seq_id, 10)

    assert isinstance(retrieved, torch.Tensor)
    assert retrieved.shape[0] == 10


@pytest.mark.asyncio
async def test_vllm_performance_benchmark():
    """Benchmark vLLM performance."""
    import time

    worker = VLLMWorker(node_id="benchmark-worker", model_path="benchmark-model")

    # Mock the provider
    worker.provider.generate = AsyncMock(
        return_value=MagicMock(content="test response")
    )

    # Create test requests
    requests = [
        ScheduledRequest(
            request_id=f"req-{i}",
            model="benchmark-model",
            messages=[{"role": "user", "content": f"test {i}"}],
            max_tokens=50,
        )
        for i in range(100)
    ]

    # Add all requests
    for req in requests:
        req.complete_callback = AsyncMock()
        await worker.add_request(req)

    # Measure processing time
    start_time = time.time()
    await worker._process_batches()
    end_time = time.time()

    # Calculate throughput
    throughput = len(requests) / (end_time - start_time)
    print("\nvLLM Benchmark Results:")
    print(f"  Requests: {len(requests)}")
    print(f"  Time: {end_time - start_time:.2f}s")
    print(f"  Throughput: {throughput:.1f} req/s")

    # Basic assertion
    assert throughput > 0


@pytest.mark.asyncio
async def test_paged_attention_performance():
    """Benchmark PagedAttention memory operations."""
    import time

    manager = PagedAttentionManager(
        block_size=16, max_gpu_blocks=100, max_cpu_blocks=1000
    )

    # Allocate many sequences
    num_sequences = 1000
    sequence_length = 128

    start_time = time.time()
    for _ in range(num_sequences):
        manager.allocate_sequence(sequence_length)
    end_time = time.time()

    # Calculate allocation rate
    alloc_rate = num_sequences / (end_time - start_time)

    # Get memory stats
    stats = manager.get_memory_stats()

    print("\nPagedAttention Benchmark Results:")
    print(f"  Sequences: {num_sequences}")
    print(f"  Sequence Length: {sequence_length}")
    print(f"  Allocation Time: {end_time - start_time:.2f}s")
    print(f"  Allocation Rate: {alloc_rate:.1f} seq/s")
    print(f"  GPU Blocks Used: {stats['gpu_blocks']['used']}")
    print(f"  CPU Blocks Used: {stats['cpu_blocks']['used']}")

    # Cleanup
    for i in range(num_sequences):
        manager.free_sequence(i)

    # Basic assertion
    assert alloc_rate > 0
