"""Tests for the auto-scaler functionality."""

import pytest
from unittest.mock import Mock
from mascarade.scheduler.scheduler import ResourceAwareScheduler
from mascarade.scheduler.autoscaler import AutoScaler, ScalingDecision
from mascarade.scheduler.worker_state import WorkerState, WorkerStatus


@pytest.fixture
def mock_scheduler():
    """Create a mock scheduler with some workers."""
    scheduler = ResourceAwareScheduler()
    
    # Add some initial workers
    for i in range(3):
        worker = WorkerState(
            node_id=f"worker-{i}",
            url=f"http://worker-{i}:8201",
            max_concurrent=4,
            vram_total_mb=24000,
            status=WorkerStatus.ALIVE,
            cpu_percent=0.5,
            gpu_percent=0.6,
        )
        scheduler.register_worker(worker)
    
    return scheduler


@pytest.fixture
def autoscaler(mock_scheduler):
    """Create an auto-scaler instance."""
    # Mock the settings
    from mascarade.config import settings
    original_values = {
        "autoscaling_enabled": settings.autoscaling_enabled,
        "autoscaling_min_workers": settings.autoscaling_min_workers,
        "autoscaling_max_workers": settings.autoscaling_max_workers,
        "autoscaling_scale_up_cpu_threshold": settings.autoscaling_scale_up_cpu_threshold,
        "autoscaling_scale_down_cpu_threshold": settings.autoscaling_scale_down_cpu_threshold,
        "autoscaling_scale_up_memory_threshold": settings.autoscaling_scale_up_memory_threshold,
        "autoscaling_scale_down_memory_threshold": settings.autoscaling_scale_down_memory_threshold,
        "autoscaling_scale_up_queue_threshold": settings.autoscaling_scale_up_queue_threshold,
        "autoscaling_scale_down_queue_threshold": settings.autoscaling_scale_down_queue_threshold,
        "autoscaling_cooldown_seconds": settings.autoscaling_cooldown_seconds,
    }
    
    # Set test values
    settings.autoscaling_enabled = True
    settings.autoscaling_min_workers = 1
    settings.autoscaling_max_workers = 10
    settings.autoscaling_scale_up_cpu_threshold = 0.7
    settings.autoscaling_scale_down_cpu_threshold = 0.3
    settings.autoscaling_scale_up_memory_threshold = 0.8
    settings.autoscaling_scale_down_memory_threshold = 0.4
    settings.autoscaling_scale_up_queue_threshold = 50
    settings.autoscaling_scale_down_queue_threshold = 10
    settings.autoscaling_cooldown_seconds = 300
    
    yield AutoScaler(mock_scheduler)
    
    # Restore original values
    for key, value in original_values.items():
        setattr(settings, key, value)


def test_autoscaler_initialization(autoscaler, mock_scheduler):
    """Test that auto-scaler initializes correctly."""
    assert autoscaler is not None
    assert autoscaler.scheduler == mock_scheduler
    assert autoscaler.min_workers == 1
    assert autoscaler.max_workers == 10
    assert autoscaler.cooldown_seconds == 300


def test_get_current_worker_count(autoscaler):
    """Test getting current worker count."""
    count = autoscaler.get_current_worker_count()
    assert count == 3  # We added 3 workers in the fixture


def test_should_scale_cooldown(autoscaler):
    """Test that scaling respects cooldown period."""
    # Initially should allow scaling
    assert autoscaler.should_scale() is True
    
    # Simulate a recent scale operation
    import time
    autoscaler.last_scale_time = time.time() - 10  # 10 seconds ago
    
    # With 300 second cooldown, should not allow scaling yet
    assert autoscaler.should_scale() is False


def test_make_scaling_decision_no_op(autoscaler):
    """Test making scaling decision when no scaling is needed."""
    # Set workers to have moderate load
    for worker in autoscaler.scheduler.workers.values():
        worker.cpu_percent = 0.5
        worker.gpu_percent = 0.5
    
    # Set moderate queue depth by modifying worker queue depths
    for worker in autoscaler.scheduler.workers.values():
        worker.queue_depth = 8  # 3 workers * 8 = 24 total
    
    decision = autoscaler.make_scaling_decision()
    
    assert decision.action == "no_op"
    assert decision.target_workers == 3
    assert "optimal range" in decision.reason


def test_make_scaling_decision_scale_up_queue(autoscaler):
    """Test making scaling decision to scale up based on queue depth."""
    # Set high queue depth by modifying worker queue depths
    for worker in autoscaler.scheduler.workers.values():
        worker.queue_depth = 20  # 3 workers * 20 = 60 total
    
    decision = autoscaler.make_scaling_decision()
    
    assert decision.action == "scale_up"
    assert decision.target_workers == 4  # Current 3 + 1
    assert "Queue depth" in decision.reason


def test_make_scaling_decision_scale_up_resource(autoscaler):
    """Test making scaling decision to scale up based on resource usage."""
    # Set high resource usage
    for worker in autoscaler.scheduler.workers.values():
        worker.cpu_percent = 0.8  # Above CPU threshold of 0.7
        worker.gpu_percent = 0.5
    
    # Set moderate queue depth by modifying worker queue depths
    for worker in autoscaler.scheduler.workers.values():
        worker.queue_depth = 8  # 3 workers * 8 = 24 total
    
    decision = autoscaler.make_scaling_decision()
    
    assert decision.action == "scale_up"
    assert decision.target_workers == 4  # Current 3 + 1
    assert "High resource usage" in decision.reason


def test_make_scaling_decision_scale_down_queue(autoscaler):
    """Test making scaling decision to scale down based on queue depth."""
    # Set low queue depth by modifying worker queue depths
    for worker in autoscaler.scheduler.workers.values():
        worker.queue_depth = 1  # 3 workers * 1 = 3 total
    
    decision = autoscaler.make_scaling_decision()
    
    assert decision.action == "scale_down"
    assert decision.target_workers == 2  # Current 3 - 1
    assert "Queue depth" in decision.reason


def test_make_scaling_decision_scale_down_resource(autoscaler):
    """Test making scaling decision to scale down based on resource usage."""
    # Set low resource usage
    for worker in autoscaler.scheduler.workers.values():
        worker.cpu_percent = 0.2  # Below CPU threshold of 0.3
        worker.gpu_percent = 0.3  # Below memory threshold of 0.4
    
    # Set low queue depth by modifying worker queue depths
    for worker in autoscaler.scheduler.workers.values():
        worker.queue_depth = 1  # 3 workers * 1 = 3 total
    
    decision = autoscaler.make_scaling_decision()
    
    assert decision.action == "scale_down"
    assert decision.target_workers == 2  # Current 3 - 1
    # The decision will be based on queue depth since it's also low
    # Both conditions are met, but queue depth is checked first
    assert "below threshold" in decision.reason


def test_apply_scaling_decision_scale_up(autoscaler):
    """Test applying a scale-up decision."""
    initial_count = autoscaler.get_current_worker_count()
    
    decision = ScalingDecision(
        action="scale_up",
        target_workers=initial_count + 1,
        reason="Test scale up"
    )
    
    result = autoscaler.apply_scaling_decision(decision)
    
    assert result is True
    assert autoscaler.get_current_worker_count() == initial_count + 1


def test_apply_scaling_decision_scale_down(autoscaler):
    """Test applying a scale-down decision."""
    initial_count = autoscaler.get_current_worker_count()
    
    decision = ScalingDecision(
        action="scale_down",
        target_workers=initial_count - 1,
        reason="Test scale down"
    )
    
    result = autoscaler.apply_scaling_decision(decision)
    
    assert result is True
    assert autoscaler.get_current_worker_count() == initial_count - 1


def test_apply_scaling_decision_no_op(autoscaler):
    """Test applying a no-op decision."""
    initial_count = autoscaler.get_current_worker_count()
    
    decision = ScalingDecision(
        action="no_op",
        target_workers=initial_count,
        reason="Test no-op"
    )
    
    result = autoscaler.apply_scaling_decision(decision)
    
    assert result is False
    assert autoscaler.get_current_worker_count() == initial_count


def test_get_average_cpu_usage(autoscaler):
    """Test calculating average CPU usage."""
    # Set specific CPU values
    workers = list(autoscaler.scheduler.workers.values())
    workers[0].cpu_percent = 0.4
    workers[1].cpu_percent = 0.6
    workers[2].cpu_percent = 0.8
    
    avg_cpu = autoscaler._get_average_cpu_usage()
    
    assert avg_cpu == pytest.approx(0.6)  # (0.4 + 0.6 + 0.8) / 3


def test_get_average_memory_usage(autoscaler):
    """Test calculating average memory usage."""
    # Set specific memory values
    workers = list(autoscaler.scheduler.workers.values())
    workers[0].gpu_percent = 0.3
    workers[1].gpu_percent = 0.5
    workers[2].gpu_percent = 0.7
    
    avg_memory = autoscaler._get_average_memory_usage()
    
    assert avg_memory == pytest.approx(0.5)  # (0.3 + 0.5 + 0.7) / 3


def test_get_status(autoscaler):
    """Test getting auto-scaler status."""
    status = autoscaler.get_status()
    
    assert status["enabled"] is True
    assert status["min_workers"] == 1
    assert status["max_workers"] == 10
    assert status["current_workers"] == 3
    assert status["cooldown_seconds"] == 300
    assert "last_scale_time" in status
    assert "time_since_last_scale" in status