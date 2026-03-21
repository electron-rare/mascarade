"""Worker state tracking for distributed scheduling."""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field
from enum import StrEnum


class WorkerStatus(StrEnum):
    ALIVE = "alive"
    SLOW = "slow"
    DEAD = "dead"
    DRAINING = "draining"


class WorkerRuntime(StrEnum):
    MLX_LM = "mlx_lm"
    OLLAMA = "ollama"
    VLLM = "vllm"
    LLAMA_CPP = "llama_cpp"
    UNKNOWN = "unknown"


@dataclass
class WorkerState:
    """State of a remote inference worker."""

    node_id: str
    url: str
    runtime: WorkerRuntime = WorkerRuntime.UNKNOWN
    status: WorkerStatus = WorkerStatus.DEAD

    # Resource metrics (updated via heartbeat)
    vram_total_mb: int = 0
    vram_free_mb: int = 0
    ram_total_mb: int = 0
    ram_free_mb: int = 0
    cpu_percent: float = 0.0
    gpu_percent: float = 0.0

    # Load metrics
    current_load: int = 0
    max_concurrent: int = 1
    queue_depth: int = 0
    loaded_models: list[str] = field(default_factory=list)

    # Performance tracking
    response_times_ms: deque = field(default_factory=lambda: deque(maxlen=100))
    error_count: int = 0
    total_requests: int = 0
    missed_heartbeats: int = 0
    last_heartbeat: float = 0.0
    last_used: float = 0.0

    # Capabilities
    supports_batching: bool = False
    supports_streaming: bool = True
    max_batch_size: int = 1
    max_context_length: int = 4096

    @property
    def alive(self) -> bool:
        return self.status in (WorkerStatus.ALIVE, WorkerStatus.SLOW)

    @property
    def avg_latency_ms(self) -> float:
        if not self.response_times_ms:
            return 1000.0  # default 1s
        return sum(self.response_times_ms) / len(self.response_times_ms)

    @property
    def p95_latency_ms(self) -> float:
        if not self.response_times_ms:
            return 5000.0
        sorted_times = sorted(self.response_times_ms)
        idx = int(len(sorted_times) * 0.95)
        return sorted_times[min(idx, len(sorted_times) - 1)]

    @property
    def error_rate(self) -> float:
        if self.total_requests == 0:
            return 0.0
        return self.error_count / self.total_requests

    @property
    def vram_usage_pct(self) -> float:
        if self.vram_total_mb == 0:
            return 0.0
        return (self.vram_total_mb - self.vram_free_mb) / self.vram_total_mb * 100

    def can_fit_model(self, model: str, estimated_vram_mb: int = 0) -> bool:
        """Check if this worker can fit a model in memory."""
        if model in self.loaded_models:
            return True
        if estimated_vram_mb == 0:
            return True  # optimistic if unknown
        return self.vram_free_mb >= estimated_vram_mb

    def has_capacity(self) -> bool:
        """Check if this worker can accept more requests."""
        return self.current_load < self.max_concurrent and self.status != WorkerStatus.DRAINING

    def request_started(self) -> None:
        self.current_load += 1
        self.total_requests += 1
        self.queue_depth = max(0, self.queue_depth)
        self.last_used = time.monotonic()

    def request_completed(self, latency_ms: float, success: bool) -> None:
        self.current_load = max(0, self.current_load - 1)
        self.response_times_ms.append(latency_ms)
        if not success:
            self.error_count += 1

    def update_from_health(self, data: dict) -> None:
        """Update state from a /health response."""
        self.vram_total_mb = data.get("vram_total_mb", self.vram_total_mb)
        self.vram_free_mb = data.get("vram_free_mb", self.vram_free_mb)
        self.ram_total_mb = data.get("ram_total_mb", self.ram_total_mb)
        self.ram_free_mb = data.get("ram_free_mb", self.ram_free_mb)
        self.cpu_percent = data.get("cpu_percent", self.cpu_percent)
        self.gpu_percent = data.get("gpu_percent", self.gpu_percent)
        self.loaded_models = data.get("loaded_models", self.loaded_models)
        self.max_concurrent = data.get("max_concurrent", self.max_concurrent)
        self.supports_batching = data.get("supports_batching", self.supports_batching)
        self.max_batch_size = data.get("max_batch_size", self.max_batch_size)
        self.max_context_length = data.get("max_context_length", self.max_context_length)

        runtime = data.get("runtime", "")
        if runtime:
            try:
                self.runtime = WorkerRuntime(runtime)
            except ValueError:
                self.runtime = WorkerRuntime.UNKNOWN

        self.missed_heartbeats = 0
        self.last_heartbeat = time.monotonic()

    def to_dict(self) -> dict:
        return {
            "node_id": self.node_id,
            "url": self.url,
            "runtime": self.runtime.value,
            "status": self.status.value,
            "vram_total_mb": self.vram_total_mb,
            "vram_free_mb": self.vram_free_mb,
            "vram_usage_pct": round(self.vram_usage_pct, 1),
            "ram_total_mb": self.ram_total_mb,
            "ram_free_mb": self.ram_free_mb,
            "cpu_percent": round(self.cpu_percent, 1),
            "gpu_percent": round(self.gpu_percent, 1),
            "current_load": self.current_load,
            "max_concurrent": self.max_concurrent,
            "queue_depth": self.queue_depth,
            "loaded_models": self.loaded_models,
            "avg_latency_ms": round(self.avg_latency_ms, 1),
            "p95_latency_ms": round(self.p95_latency_ms, 1),
            "error_rate": round(self.error_rate, 3),
            "total_requests": self.total_requests,
            "alive": self.alive,
        }
