"""Optional vLLM import tests for the scheduler package."""

from mascarade import scheduler
from mascarade.scheduler import HeartbeatMonitor, ResourceAwareScheduler, WorkerState


def test_scheduler_package_imports_without_vllm_dependency():
    assert WorkerState is scheduler.WorkerState
    assert HeartbeatMonitor is scheduler.HeartbeatMonitor
    assert ResourceAwareScheduler is scheduler.ResourceAwareScheduler
    assert hasattr(scheduler, "VLLMScheduler")
