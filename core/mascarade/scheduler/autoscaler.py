"""Auto-scaling manager for distributed workers.

Monitors system metrics and automatically scales worker pool up/down
based on load, resource usage, and queue depth.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any

from mascarade.config import settings
from mascarade.scheduler.scheduler import ResourceAwareScheduler

logger = logging.getLogger("mascarade.scheduler.autoscaler")


@dataclass
class ScalingDecision:
    """Decision to scale worker pool."""
    action: str  # "scale_up", "scale_down", or "no_op"
    target_workers: int  # Target number of workers
    reason: str  # Human-readable reason
    timestamp: float = 0.0  # When decision was made


class AutoScaler:
    """
    Auto-scaling manager for distributed workers.

    Monitors system metrics and makes scaling decisions based on:
    - CPU usage
    - Memory usage
    - Queue depth
    - Worker health
    """

    def __init__(self, scheduler: ResourceAwareScheduler) -> None:
        """
        Initialize the auto-scaler.

        Args:
            scheduler: The resource-aware scheduler to manage
        """
        self.scheduler = scheduler
        self.last_scale_time = 0.0
        self.cooldown_seconds = settings.autoscaling_cooldown_seconds
        self.min_workers = settings.autoscaling_min_workers
        self.max_workers = settings.autoscaling_max_workers

        logger.info(
            "AutoScaler initialized: min=%d, max=%d, cooldown=%ds",
            self.min_workers,
            self.max_workers,
            self.cooldown_seconds,
        )

    def should_scale(self) -> bool:
        """
        Check if scaling is allowed based on cooldown period.

        Returns:
            True if scaling is allowed, False otherwise
        """
        current_time = time.time()
        if current_time - self.last_scale_time < self.cooldown_seconds:
            logger.debug(
                "Scaling cooldown active (%d/%ds remaining)",
                int(self.cooldown_seconds - (current_time - self.last_scale_time)),
                self.cooldown_seconds,
            )
            return False
        return True

    def get_current_worker_count(self) -> int:
        """
        Get the current number of alive workers.

        Returns:
            Number of alive workers
        """
        return len([w for w in self.scheduler.workers.values() if w.alive])

    def make_scaling_decision(self) -> ScalingDecision:
        """
        Make a scaling decision based on current system state.

        Returns:
            ScalingDecision with action and reasoning
        """
        if not self.should_scale():
            return ScalingDecision(
                action="no_op",
                target_workers=self.get_current_worker_count(),
                reason="Cooldown period active",
            )

        current_workers = self.get_current_worker_count()
        total_queue = self.scheduler.total_queue_depth

        # Check if we need to scale up
        if current_workers < self.max_workers:
            # Scale up based on queue depth
            if total_queue >= settings.autoscaling_scale_up_queue_threshold:
                return ScalingDecision(
                    action="scale_up",
                    target_workers=min(current_workers + 1, self.max_workers),
                    reason=f"Queue depth {total_queue} exceeds threshold {settings.autoscaling_scale_up_queue_threshold}",
                )

            # Scale up based on worker load (CPU/Memory)
            avg_cpu = self._get_average_cpu_usage()
            avg_memory = self._get_average_memory_usage()

            if (
                avg_cpu >= settings.autoscaling_scale_up_cpu_threshold
                or avg_memory >= settings.autoscaling_scale_up_memory_threshold
            ):
                return ScalingDecision(
                    action="scale_up",
                    target_workers=min(current_workers + 1, self.max_workers),
                    reason=f"High resource usage: CPU={avg_cpu:.2f}, Memory={avg_memory:.2f}",
                )

        # Check if we need to scale down
        if current_workers > self.min_workers:
            # Scale down based on low queue depth
            if total_queue <= settings.autoscaling_scale_down_queue_threshold:
                return ScalingDecision(
                    action="scale_down",
                    target_workers=max(current_workers - 1, self.min_workers),
                    reason=f"Queue depth {total_queue} below threshold {settings.autoscaling_scale_down_queue_threshold}",
                )

            # Scale down based on low worker load (CPU/Memory)
            avg_cpu = self._get_average_cpu_usage()
            avg_memory = self._get_average_memory_usage()

            if (
                avg_cpu <= settings.autoscaling_scale_down_cpu_threshold
                and avg_memory <= settings.autoscaling_scale_down_memory_threshold
            ):
                return ScalingDecision(
                    action="scale_down",
                    target_workers=max(current_workers - 1, self.min_workers),
                    reason=f"Low resource usage: CPU={avg_cpu:.2f}, Memory={avg_memory:.2f}",
                )

        # No scaling needed
        return ScalingDecision(
            action="no_op",
            target_workers=current_workers,
            reason="System within optimal range",
        )

    def _get_average_cpu_usage(self) -> float:
        """
        Get average CPU usage across all workers.

        Returns:
            Average CPU usage (0-1)
        """
        alive_workers = [w for w in self.scheduler.workers.values() if w.alive]
        if not alive_workers:
            return 0.0

        total_cpu = sum(w.cpu_percent for w in alive_workers)
        return total_cpu / len(alive_workers)

    def _get_average_memory_usage(self) -> float:
        """
        Get average memory usage across all workers.

        Returns:
            Average memory usage (0-1)
        """
        alive_workers = [w for w in self.scheduler.workers.values() if w.alive]
        if not alive_workers:
            return 0.0

        total_memory = sum(w.gpu_percent for w in alive_workers)
        return total_memory / len(alive_workers)

    def apply_scaling_decision(self, decision: ScalingDecision) -> bool:
        """
        Apply a scaling decision to the worker pool.

        Args:
            decision: The scaling decision to apply

        Returns:
            True if scaling was applied, False otherwise
        """
        if decision.action == "no_op":
            logger.debug("No scaling action needed: %s", decision.reason)
            return False

        current_workers = self.get_current_worker_count()

        if decision.action == "scale_up":
            if decision.target_workers <= current_workers:
                logger.warning("Cannot scale up: target (%d) <= current (%d)",
                             decision.target_workers, current_workers)
                return False

            # Add new workers
            workers_to_add = decision.target_workers - current_workers
            for _i in range(workers_to_add):
                self._add_worker()

            logger.info("Scaled up from %d to %d workers: %s",
                       current_workers, decision.target_workers, decision.reason)

        elif decision.action == "scale_down":
            if decision.target_workers >= current_workers:
                logger.warning("Cannot scale down: target (%d) >= current (%d)",
                             decision.target_workers, current_workers)
                return False

            # Remove workers
            workers_to_remove = current_workers - decision.target_workers
            for _i in range(workers_to_remove):
                self._remove_worker()

            logger.info("Scaled down from %d to %d workers: %s",
                       current_workers, decision.target_workers, decision.reason)

        # Update last scale time
        self.last_scale_time = time.time()
        return True

    def _add_worker(self) -> None:
        """
        Add a new worker to the pool.

        This is a placeholder - actual implementation would depend on
        the deployment environment (Kubernetes, Docker, etc.)
        """
        # In a real implementation, this would:
        # 1. Launch a new worker instance
        # 2. Wait for it to become healthy
        # 3. Register it with the scheduler

        # For now, we'll simulate by adding a dummy worker
        worker_id = f"auto-worker-{len(self.scheduler.workers) + 1}"
        from mascarade.scheduler.worker_state import WorkerState, WorkerStatus

        dummy_worker = WorkerState(
            node_id=worker_id,
            url=f"http://{worker_id}:8201",
            max_concurrent=4,
            vram_total_mb=24000,
            status=WorkerStatus.ALIVE,
        )

        self.scheduler.register_worker(dummy_worker)
        logger.info("Added worker: %s", worker_id)

    def _remove_worker(self) -> None:
        """
        Remove a worker from the pool.

        This is a placeholder - actual implementation would depend on
        the deployment environment (Kubernetes, Docker, etc.)
        """
        # Find a worker to remove (prefer least loaded)
        alive_workers = [w for w in self.scheduler.workers.values() if w.alive]
        if not alive_workers:
            return

        # Sort by load (ascending) and pick the least loaded
        alive_workers.sort(key=lambda w: w.current_load)
        worker_to_remove = alive_workers[0]

        # Remove from scheduler
        self.scheduler.remove_worker(worker_to_remove.node_id)
        logger.info("Removed worker: %s", worker_to_remove.node_id)

    def monitor_and_scale(self) -> None:
        """
        Monitor system and make scaling decisions.

        This would typically be called periodically from a background task.
        """
        decision = self.make_scaling_decision()
        self.apply_scaling_decision(decision)

    def get_status(self) -> dict[str, Any]:
        """
        Get auto-scaler status.

        Returns:
            Dictionary with auto-scaler status information
        """
        return {
            "enabled": settings.autoscaling_enabled,
            "min_workers": self.min_workers,
            "max_workers": self.max_workers,
            "current_workers": self.get_current_worker_count(),
            "cooldown_seconds": self.cooldown_seconds,
            "last_scale_time": self.last_scale_time,
            "time_since_last_scale": time.time() - self.last_scale_time,
        }
