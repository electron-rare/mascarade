"""Distributed scheduler for multi-machine inference."""

from mascarade.scheduler.worker_state import WorkerState
from mascarade.scheduler.heartbeat import HeartbeatMonitor
from mascarade.scheduler.scheduler import ResourceAwareScheduler

# vLLM support is optional in this workspace. Importing the scheduler package
# must not break the core API surface when the extra dependency is absent.
try:
    from mascarade.scheduler.vllm_integration import VLLMScheduler
except ModuleNotFoundError:
    VLLMScheduler = None  # type: ignore[assignment]

__all__ = ["WorkerState", "HeartbeatMonitor", "ResourceAwareScheduler", "VLLMScheduler"]
