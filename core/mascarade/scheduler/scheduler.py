"""Resource-aware distributed scheduler for multi-machine inference."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass

from fastapi import HTTPException

from mascarade.scheduler.worker_state import WorkerState, WorkerStatus

logger = logging.getLogger("mascarade.scheduler")

# Scoring weights
W_AFFINITY = 30.0  # model already loaded
W_LOAD = 20.0  # inverse load
W_SPEED = 15.0  # inverse latency
W_QUEUE = 10.0  # inverse queue depth
W_VRAM = 5.0  # available VRAM

# Backpressure thresholds
MAX_TOTAL_QUEUE = 200
MAX_ESTIMATED_WAIT_S = 30


@dataclass
class ScheduledRequest:
    """A request ready to be dispatched to a worker."""

    model: str
    messages: list[dict]
    max_tokens: int = 4096
    temperature: float = 0.7
    stream: bool = False
    estimated_tokens: int = 0


class ResourceAwareScheduler:
    """Scores and selects the best worker for each inference request."""

    def __init__(self) -> None:
        self.workers: dict[str, WorkerState] = {}
        self._dispatch_count = 0

    def register_worker(self, worker: WorkerState) -> None:
        self.workers[worker.node_id] = worker
        logger.info("Registered worker %s at %s", worker.node_id, worker.url)

    def remove_worker(self, node_id: str) -> None:
        self.workers.pop(node_id, None)

    @property
    def total_queue_depth(self) -> int:
        return sum(w.queue_depth for w in self.workers.values())

    def workers_for_model(self, model: str) -> list[WorkerState]:
        """Get alive workers that can serve a model."""
        return [
            w
            for w in self.workers.values()
            if w.alive and (model in w.loaded_models or w.has_capacity())
        ]

    def estimate_wait(self, request: ScheduledRequest) -> float:
        """Estimate wait time in seconds for a request."""
        candidates = self.workers_for_model(request.model)
        if not candidates:
            return float("inf")
        # Rough estimate: queue_depth * avg_latency / num_workers
        total_queue = sum(w.queue_depth for w in candidates)
        avg_lat = sum(w.avg_latency_ms for w in candidates) / len(candidates)
        return (total_queue * avg_lat / 1000) / len(candidates)

    def admit(self, request: ScheduledRequest) -> None:
        """Check if the system can accept this request. Raises HTTPException if not."""
        # Queue overflow
        if self.total_queue_depth >= MAX_TOTAL_QUEUE:
            raise HTTPException(429, "System overloaded, retry later")

        # No capable worker
        capable = self.workers_for_model(request.model)
        if not capable:
            raise HTTPException(
                503, f"No worker available for model '{request.model}'"
            )

        # Wait time too long
        est_wait = self.estimate_wait(request)
        if est_wait > MAX_ESTIMATED_WAIT_S:
            raise HTTPException(
                429,
                f"Estimated wait {est_wait:.0f}s exceeds {MAX_ESTIMATED_WAIT_S}s limit",
            )

    def select_worker(self, request: ScheduledRequest) -> WorkerState:
        """Select the best worker for a request based on scoring."""
        self.admit(request)

        candidates = [
            w
            for w in self.workers.values()
            if w.alive and w.has_capacity()
        ]

        if not candidates:
            # Fallback: pick any alive worker even if at capacity
            candidates = [w for w in self.workers.values() if w.alive]

        if not candidates:
            raise HTTPException(503, "No alive workers")

        scored = [(self._score(w, request), w) for w in candidates]
        scored.sort(key=lambda x: x[0], reverse=True)

        best = scored[0][1]
        self._dispatch_count += 1

        logger.debug(
            "Dispatch #%d → %s (score=%.1f, load=%d/%d, models=%s)",
            self._dispatch_count,
            best.node_id,
            scored[0][0],
            best.current_load,
            best.max_concurrent,
            best.loaded_models,
        )

        return best

    def _score(self, worker: WorkerState, request: ScheduledRequest) -> float:
        score = 0.0

        # Affinity: model already loaded → avoid 10-30s reload
        if request.model in worker.loaded_models:
            score += W_AFFINITY

        # Load: prefer less loaded workers
        if worker.max_concurrent > 0:
            load_ratio = worker.current_load / worker.max_concurrent
            score += W_LOAD * (1.0 - load_ratio)

        # Speed: prefer faster workers (inverse avg latency)
        score += W_SPEED * (1000.0 / max(worker.avg_latency_ms, 1.0))

        # Queue: prefer shorter queues
        score += W_QUEUE * (1.0 / (worker.queue_depth + 1))

        # VRAM: prefer workers with more free VRAM
        if worker.vram_total_mb > 0:
            vram_free_ratio = worker.vram_free_mb / worker.vram_total_mb
            score += W_VRAM * vram_free_ratio

        # Penalty for slow workers
        if worker.status == WorkerStatus.SLOW:
            score *= 0.5

        # Penalty for high error rate
        if worker.error_rate > 0.1:
            score *= (1.0 - worker.error_rate)

        return score

    def get_status(self) -> dict:
        """Get scheduler status for the API."""
        return {
            "workers": {
                node_id: w.to_dict() for node_id, w in self.workers.items()
            },
            "total_queue_depth": self.total_queue_depth,
            "total_dispatched": self._dispatch_count,
            "alive_workers": len([w for w in self.workers.values() if w.alive]),
            "dead_workers": len(
                [w for w in self.workers.values() if w.status == WorkerStatus.DEAD]
            ),
        }
