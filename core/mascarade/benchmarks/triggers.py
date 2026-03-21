"""Model deployment trigger system for automatic benchmark execution."""

from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from mascarade.benchmarks.runner import BenchmarkRunner
from mascarade.benchmarks.storage import BenchmarkStorage
from mascarade.router import Router

logger = logging.getLogger("mascarade.benchmarks.triggers")

DEFAULT_AUTO_BENCHMARK_ENABLED = os.getenv("AUTO_BENCHMARK_ENABLED", "true").lower() in {
    "true",
    "1",
    "yes",
}
DEFAULT_BENCHMARK_DOMAIN = os.getenv("DEFAULT_BENCHMARK_DOMAIN", "").strip()
DEFAULT_BENCHMARK_LIMIT = int(os.getenv("DEFAULT_BENCHMARK_LIMIT", "10"))


class BenchmarkTriggerError(RuntimeError):
    """Base error for benchmark trigger failures."""


class ModelDeploymentTriggerError(BenchmarkTriggerError):
    """Raised when model deployment trigger fails."""


@dataclass
class DeploymentEvent:
    """Represents a model deployment event."""

    provider: str
    model: str
    event_type: str = "deployment"
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate deployment event fields."""
        if not self.provider or not isinstance(self.provider, str):
            raise ValueError("provider must be a non-empty string")
        if not self.model or not isinstance(self.model, str):
            raise ValueError("model must be a non-empty string")


class ModelDeploymentTrigger:
    """Trigger benchmark execution on model deployment events."""

    def __init__(
        self,
        *,
        router: Router | None = None,
        storage: BenchmarkStorage | None = None,
        auto_benchmark_enabled: bool = DEFAULT_AUTO_BENCHMARK_ENABLED,
        default_domain: str | None = DEFAULT_BENCHMARK_DOMAIN or None,
        default_limit: int = DEFAULT_BENCHMARK_LIMIT,
    ) -> None:
        """
        Initialize model deployment trigger.

        Args:
            router: Router instance for LLM calls
            storage: Storage instance for persisting results
            auto_benchmark_enabled: Whether to automatically run benchmarks on deployment
            default_domain: Default domain for benchmarks
            default_limit: Default number of prompts per benchmark
        """
        self.router = router or Router()
        self.storage = storage or BenchmarkStorage()
        self.auto_benchmark_enabled = auto_benchmark_enabled
        self.default_domain = default_domain
        self.default_limit = default_limit
        self._pending_tasks: set[asyncio.Task] = set()

    async def handle_deployment(
        self,
        event: DeploymentEvent,
        *,
        domain: str | None = None,
        limit: int | None = None,
        background: bool = True,
    ) -> dict[str, Any]:
        """
        Handle a model deployment event.

        Args:
            event: Deployment event to process
            domain: Domain for benchmark (overrides default)
            limit: Number of prompts to test (overrides default)
            background: Whether to run benchmark in background

        Returns:
            Trigger response with status and metadata

        Raises:
            ModelDeploymentTriggerError: If trigger processing fails
        """
        if not self.auto_benchmark_enabled:
            logger.info("Auto-benchmark disabled, skipping deployment event for %s/%s",
                       event.provider, event.model)
            return {
                "status": "skipped",
                "reason": "auto_benchmark_disabled",
                "provider": event.provider,
                "model": event.model,
            }

        logger.info(
            "Processing deployment event for %s/%s (type=%s)",
            event.provider,
            event.model,
            event.event_type,
        )

        # Validate provider is available
        if event.provider not in self.router.available_providers:
            raise ModelDeploymentTriggerError(
                f"Provider '{event.provider}' not available. "
                f"Available: {self.router.available_providers}"
            )

        # Determine benchmark parameters
        benchmark_domain = domain or self.default_domain
        benchmark_limit = limit or self.default_limit

        # Run benchmark in background or foreground
        if background:
            task = asyncio.create_task(
                self._run_benchmark_async(
                    event=event,
                    domain=benchmark_domain,
                    limit=benchmark_limit,
                )
            )
            # Track task to prevent garbage collection
            self._pending_tasks.add(task)
            task.add_done_callback(self._pending_tasks.discard)

            return {
                "status": "triggered",
                "mode": "background",
                "provider": event.provider,
                "model": event.model,
                "domain": benchmark_domain,
                "limit": benchmark_limit,
                "timestamp": event.timestamp.isoformat(),
            }
        else:
            results = await self._run_benchmark_async(
                event=event,
                domain=benchmark_domain,
                limit=benchmark_limit,
            )
            return {
                "status": "completed",
                "mode": "foreground",
                "provider": event.provider,
                "model": event.model,
                "domain": benchmark_domain,
                "limit": benchmark_limit,
                "results": results,
                "timestamp": event.timestamp.isoformat(),
            }

    async def _run_benchmark_async(
        self,
        event: DeploymentEvent,
        domain: str | None,
        limit: int,
    ) -> dict[str, Any]:
        """
        Run benchmark asynchronously for deployed model.

        Args:
            event: Deployment event
            domain: Domain for benchmark
            limit: Number of prompts to test

        Returns:
            Benchmark results summary
        """
        runner = BenchmarkRunner(router=self.router)

        try:
            logger.info(
                "Starting benchmark for %s/%s (domain=%s, limit=%d)",
                event.provider,
                event.model,
                domain or "all",
                limit,
            )

            # Run benchmark
            results = await runner.run_provider_benchmark(
                provider_name=event.provider,
                domain=domain,
                model=event.model,
                limit=limit,
            )

            # Get summary
            summary = runner.get_summary()
            provider_stats = summary.get("providers", {}).get(event.provider, {})

            # Store results if storage is available
            if self.storage.client is not None and results:
                # Calculate percentiles
                latencies = [r.latency for r in results if r.success]
                if latencies:
                    latencies_sorted = sorted(latencies)
                    p50_idx = len(latencies_sorted) // 2
                    p95_idx = int(len(latencies_sorted) * 0.95)
                    latency_p50 = latencies_sorted[p50_idx]
                    latency_p95 = latencies_sorted[p95_idx]

                    # Calculate quality score (based on success rate)
                    success_rate = provider_stats.get("success_rate", 0.0)
                    quality_score = success_rate

                    # Write to storage
                    self.storage.write_result(
                        provider=event.provider,
                        model=event.model,
                        domain=domain or "all",
                        latency_p50=latency_p50,
                        latency_p95=latency_p95,
                        quality_score=quality_score,
                        cost=provider_stats.get("total_cost", 0.0),
                        request_count=len(results),
                        error_rate=(100.0 - success_rate) / 100.0,
                        notes=f"Triggered by deployment event: {event.event_type}",
                    )

            logger.info(
                "Benchmark completed for %s/%s: %d/%d successful",
                event.provider,
                event.model,
                provider_stats.get("successful_runs", 0),
                provider_stats.get("total_runs", 0),
            )

            return {
                "successful_runs": provider_stats.get("successful_runs", 0),
                "total_runs": provider_stats.get("total_runs", 0),
                "success_rate": provider_stats.get("success_rate", 0.0),
                "avg_latency": provider_stats.get("avg_latency", 0.0),
                "total_cost": provider_stats.get("total_cost", 0.0),
            }

        except Exception as exc:
            logger.error(
                "Benchmark failed for %s/%s: %s",
                event.provider,
                event.model,
                exc,
                exc_info=True,
            )
            raise ModelDeploymentTriggerError(
                f"Benchmark execution failed for {event.provider}/{event.model}: {exc}"
            ) from exc

    async def handle_webhook(
        self,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Handle incoming webhook payload and trigger benchmark.

        Args:
            payload: Webhook payload containing deployment information

        Returns:
            Webhook processing result

        Raises:
            BenchmarkTriggerError: If webhook processing fails
        """
        try:
            # Parse webhook payload
            provider = payload.get("provider", "").strip()
            model = payload.get("model", "").strip()
            event_type = payload.get("event_type", "deployment").strip()

            if not provider:
                raise BenchmarkTriggerError("Missing 'provider' in webhook payload")
            if not model:
                raise BenchmarkTriggerError("Missing 'model' in webhook payload")

            # Create deployment event
            event = DeploymentEvent(
                provider=provider,
                model=model,
                event_type=event_type,
                metadata=payload.get("metadata", {}),
            )

            # Extract optional parameters
            domain = payload.get("domain")
            limit = payload.get("limit")
            background = payload.get("background", True)

            # Handle deployment
            result = await self.handle_deployment(
                event=event,
                domain=domain,
                limit=limit,
                background=background,
            )

            return {
                "webhook_status": "processed",
                "trigger_result": result,
            }

        except ValueError as exc:
            raise BenchmarkTriggerError(f"Invalid webhook payload: {exc}") from exc
        except Exception as exc:
            logger.error("Webhook processing failed: %s", exc, exc_info=True)
            raise BenchmarkTriggerError(f"Webhook processing error: {exc}") from exc

    async def close(self) -> None:
        """Clean up pending tasks."""
        if self._pending_tasks:
            logger.info("Waiting for %d pending benchmark tasks", len(self._pending_tasks))
            await asyncio.gather(*self._pending_tasks, return_exceptions=True)
            self._pending_tasks.clear()


def create_deployment_event(
    provider: str,
    model: str,
    event_type: str = "deployment",
    **metadata: Any,
) -> DeploymentEvent:
    """
    Helper function to create a deployment event.

    Args:
        provider: Provider name
        model: Model identifier
        event_type: Type of deployment event
        **metadata: Additional event metadata

    Returns:
        DeploymentEvent instance
    """
    return DeploymentEvent(
        provider=provider,
        model=model,
        event_type=event_type,
        metadata=metadata,
    )
