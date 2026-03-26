"""Prometheus metrics exporter for the MascaradeGrid distributed scheduler.

Exposes scheduler and worker state as Prometheus metrics at /metrics.
Uses the standard prometheus_client library.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from fastapi import APIRouter, Request, Response
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
    Counter,
    Gauge,
    generate_latest,
)

if TYPE_CHECKING:
    from mascarade.scheduler.scheduler import ResourceAwareScheduler

logger = logging.getLogger("mascarade.scheduler.metrics")

# ---------------------------------------------------------------------------
# Registry & metrics
# ---------------------------------------------------------------------------
REGISTRY = CollectorRegistry()

# -- Scheduler-level metrics ------------------------------------------------
SCHEDULER_ALIVE_WORKERS = Gauge(
    "mascarade_scheduler_alive_workers",
    "Number of alive workers in the cluster",
    registry=REGISTRY,
)
SCHEDULER_DEAD_WORKERS = Gauge(
    "mascarade_scheduler_dead_workers",
    "Number of dead workers in the cluster",
    registry=REGISTRY,
)
SCHEDULER_TOTAL_QUEUE_DEPTH = Gauge(
    "mascarade_scheduler_total_queue_depth",
    "Total queue depth across all workers",
    registry=REGISTRY,
)
SCHEDULER_TOTAL_DISPATCHED = Counter(
    "mascarade_scheduler_total_dispatched",
    "Total requests dispatched since startup",
    registry=REGISTRY,
)
SCHEDULER_CLUSTER_ERROR_RATE = Gauge(
    "mascarade_scheduler_cluster_error_rate",
    "Cluster-wide error rate (0-1)",
    registry=REGISTRY,
)

# -- Worker-level metrics ---------------------------------------------------
WORKER_STATUS = Gauge(
    "mascarade_worker_status",
    "Worker status (1=alive, 0.5=slow, 0=dead)",
    ["node_id", "runtime"],
    registry=REGISTRY,
)
WORKER_VRAM_USAGE_PCT = Gauge(
    "mascarade_worker_vram_usage_pct",
    "VRAM usage percentage",
    ["node_id"],
    registry=REGISTRY,
)
WORKER_VRAM_TOTAL_MB = Gauge(
    "mascarade_worker_vram_total_mb",
    "Total VRAM in MB",
    ["node_id"],
    registry=REGISTRY,
)
WORKER_VRAM_FREE_MB = Gauge(
    "mascarade_worker_vram_free_mb",
    "Free VRAM in MB",
    ["node_id"],
    registry=REGISTRY,
)
WORKER_CPU_PERCENT = Gauge(
    "mascarade_worker_cpu_percent",
    "CPU usage percentage",
    ["node_id"],
    registry=REGISTRY,
)
WORKER_RAM_TOTAL_MB = Gauge(
    "mascarade_worker_ram_total_mb",
    "Total RAM in MB",
    ["node_id"],
    registry=REGISTRY,
)
WORKER_RAM_FREE_MB = Gauge(
    "mascarade_worker_ram_free_mb",
    "Free RAM in MB",
    ["node_id"],
    registry=REGISTRY,
)
WORKER_RAM_USAGE_PCT = Gauge(
    "mascarade_worker_ram_usage_pct",
    "RAM usage percentage",
    ["node_id"],
    registry=REGISTRY,
)
WORKER_GPU_PERCENT = Gauge(
    "mascarade_worker_gpu_percent",
    "GPU utilization percentage",
    ["node_id"],
    registry=REGISTRY,
)
WORKER_CURRENT_LOAD = Gauge(
    "mascarade_worker_current_load",
    "Current concurrent requests on worker",
    ["node_id"],
    registry=REGISTRY,
)
WORKER_QUEUE_DEPTH = Gauge(
    "mascarade_worker_queue_depth",
    "Queue depth on worker",
    ["node_id"],
    registry=REGISTRY,
)
WORKER_AVG_LATENCY_MS = Gauge(
    "mascarade_worker_avg_latency_ms",
    "Average response latency in ms",
    ["node_id"],
    registry=REGISTRY,
)
WORKER_P95_LATENCY_MS = Gauge(
    "mascarade_worker_p95_latency_ms",
    "P95 response latency in ms",
    ["node_id"],
    registry=REGISTRY,
)
WORKER_P99_LATENCY_MS = Gauge(
    "mascarade_worker_p99_latency_ms",
    "P99 response latency in ms",
    ["node_id"],
    registry=REGISTRY,
)
WORKER_P50_LATENCY_MS = Gauge(
    "mascarade_worker_p50_latency_ms",
    "P50 (median) response latency in ms",
    ["node_id"],
    registry=REGISTRY,
)
WORKER_ERROR_RATE = Gauge(
    "mascarade_worker_error_rate",
    "Per-worker error rate (0-1)",
    ["node_id"],
    registry=REGISTRY,
)
WORKER_TOTAL_REQUESTS = Gauge(
    "mascarade_worker_total_requests",
    "Total requests served by worker",
    ["node_id"],
    registry=REGISTRY,
)
WORKER_LOADED_MODELS = Gauge(
    "mascarade_worker_loaded_models_count",
    "Number of models loaded on worker",
    ["node_id"],
    registry=REGISTRY,
)
WORKER_MODEL_LOADED = Gauge(
    "mascarade_worker_model_loaded",
    "Whether a specific model is loaded on a worker (1=yes)",
    ["node_id", "model"],
    registry=REGISTRY,
)

# ---------------------------------------------------------------------------
# State -> metrics sync
# ---------------------------------------------------------------------------
# Track previous dispatch count to compute counter increments
_last_dispatch_count: int = 0


def update_metrics(scheduler: ResourceAwareScheduler) -> None:
    """Refresh all Prometheus gauges from the current scheduler state."""
    global _last_dispatch_count

    status = scheduler.get_status()
    workers = scheduler.workers

    # Scheduler-level
    SCHEDULER_ALIVE_WORKERS.set(status["alive_workers"])
    SCHEDULER_DEAD_WORKERS.set(status["dead_workers"])
    SCHEDULER_TOTAL_QUEUE_DEPTH.set(status["total_queue_depth"])

    # Update counter (only increment by delta)
    current_dispatched = status["total_dispatched"]
    delta = current_dispatched - _last_dispatch_count
    if delta > 0:
        SCHEDULER_TOTAL_DISPATCHED.inc(delta)
    _last_dispatch_count = current_dispatched

    # Compute cluster-wide error rate
    total_reqs = sum(w.total_requests for w in workers.values())
    total_errs = sum(w.error_count for w in workers.values())
    cluster_err = total_errs / total_reqs if total_reqs > 0 else 0.0
    SCHEDULER_CLUSTER_ERROR_RATE.set(cluster_err)

    # Worker-level
    for node_id, w in workers.items():
        rt = w.runtime.value

        # Status gauge
        status_val = {"alive": 1.0, "slow": 0.5, "dead": 0.0, "draining": 0.25}
        WORKER_STATUS.labels(node_id=node_id, runtime=rt).set(status_val.get(w.status.value, 0.0))

        # Resource metrics
        WORKER_VRAM_USAGE_PCT.labels(node_id=node_id).set(w.vram_usage_pct)
        WORKER_VRAM_TOTAL_MB.labels(node_id=node_id).set(w.vram_total_mb)
        WORKER_VRAM_FREE_MB.labels(node_id=node_id).set(w.vram_free_mb)
        WORKER_CPU_PERCENT.labels(node_id=node_id).set(w.cpu_percent)
        WORKER_RAM_TOTAL_MB.labels(node_id=node_id).set(w.ram_total_mb)
        WORKER_RAM_FREE_MB.labels(node_id=node_id).set(w.ram_free_mb)
        WORKER_GPU_PERCENT.labels(node_id=node_id).set(w.gpu_percent)

        # Compute RAM usage %
        ram_pct = 0.0
        if w.ram_total_mb > 0:
            ram_pct = (w.ram_total_mb - w.ram_free_mb) / w.ram_total_mb * 100
        WORKER_RAM_USAGE_PCT.labels(node_id=node_id).set(ram_pct)

        # Load metrics
        WORKER_CURRENT_LOAD.labels(node_id=node_id).set(w.current_load)
        WORKER_QUEUE_DEPTH.labels(node_id=node_id).set(w.queue_depth)
        WORKER_TOTAL_REQUESTS.labels(node_id=node_id).set(w.total_requests)

        # Latency metrics
        WORKER_AVG_LATENCY_MS.labels(node_id=node_id).set(w.avg_latency_ms)
        WORKER_P95_LATENCY_MS.labels(node_id=node_id).set(w.p95_latency_ms)

        # P50 and P99
        if w.response_times_ms:
            sorted_times = sorted(w.response_times_ms)
            p50_idx = int(len(sorted_times) * 0.50)
            p99_idx = int(len(sorted_times) * 0.99)
            WORKER_P50_LATENCY_MS.labels(node_id=node_id).set(
                sorted_times[min(p50_idx, len(sorted_times) - 1)]
            )
            WORKER_P99_LATENCY_MS.labels(node_id=node_id).set(
                sorted_times[min(p99_idx, len(sorted_times) - 1)]
            )
        else:
            WORKER_P50_LATENCY_MS.labels(node_id=node_id).set(1000.0)
            WORKER_P99_LATENCY_MS.labels(node_id=node_id).set(5000.0)

        # Error rate
        WORKER_ERROR_RATE.labels(node_id=node_id).set(w.error_rate)

        # Model info
        WORKER_LOADED_MODELS.labels(node_id=node_id).set(len(w.loaded_models))
        for model in w.loaded_models:
            WORKER_MODEL_LOADED.labels(node_id=node_id, model=model).set(1)


# ---------------------------------------------------------------------------
# FastAPI router for /metrics
# ---------------------------------------------------------------------------
router = APIRouter(tags=["metrics"])


@router.get("/metrics")
async def metrics_endpoint(request: Request) -> Response:
    """Prometheus-compatible metrics endpoint."""
    scheduler = getattr(request.app.state, "scheduler", None)
    if scheduler is not None:
        update_metrics(scheduler)
    return Response(
        content=generate_latest(REGISTRY),
        media_type=CONTENT_TYPE_LATEST,
    )
