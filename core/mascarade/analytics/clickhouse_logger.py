"""Best-effort ClickHouse async logger for cost event tracking."""

from __future__ import annotations

import asyncio
import logging
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from functools import lru_cache
from typing import Any

from mascarade.config import settings

logger = logging.getLogger("mascarade.analytics.clickhouse_logger")

try:  # pragma: no cover - optional dependency at import time
    import clickhouse_connect
    from clickhouse_connect.driver.asyncclient import AsyncClient
except ImportError:  # pragma: no cover - handled at runtime
    clickhouse_connect = None  # type: ignore[assignment]
    AsyncClient = None  # type: ignore[assignment]


@dataclass
class CostEvent:
    """Cost event data structure for tracking LLM usage."""

    timestamp: datetime
    provider: str
    model: str
    agent: str | None
    input_tokens: int
    output_tokens: int
    cost: float
    strategy: str | None
    success: bool

    def to_row(self) -> tuple[Any, ...]:
        """Convert to tuple for ClickHouse insertion."""
        return (
            self.timestamp,
            self.provider,
            self.model,
            self.agent or "",
            self.input_tokens,
            self.output_tokens,
            self.cost,
            self.strategy or "",
            self.success,
        )


def _resolve_clickhouse_url() -> str:
    """Resolve ClickHouse URL from settings or environment."""
    return getattr(settings, "clickhouse_url", "").strip() or "http://clickhouse:8123"


def _resolve_clickhouse_user() -> str:
    """Resolve ClickHouse user from settings or environment."""
    return getattr(settings, "clickhouse_user", "").strip() or "langfuse"


def _resolve_clickhouse_password() -> str:
    """Resolve ClickHouse password from settings or environment."""
    return getattr(settings, "clickhouse_password", "").strip() or ""


def _resolve_clickhouse_database() -> str:
    """Resolve ClickHouse database from settings or environment."""
    return getattr(settings, "clickhouse_database", "").strip() or "mascarade"


def clickhouse_configured() -> bool:
    """Check if ClickHouse is configured and available."""
    if clickhouse_connect is None:
        return False
    if not _resolve_clickhouse_url():
        return False
    # Password can be empty for local dev, so we don't check it
    return True


class CostEventLogger:
    """Async logger for cost events to ClickHouse with batching."""

    def __init__(
        self,
        batch_size: int = 100,
        flush_interval: float = 5.0,
    ) -> None:
        """
        Initialize the cost event logger.

        Args:
            batch_size: Number of events to batch before writing
            flush_interval: Seconds between automatic flushes
        """
        self.batch_size = batch_size
        self.flush_interval = flush_interval
        self._client: AsyncClient | None = None
        self._event_queue: deque[CostEvent] = deque()
        self._flush_task: asyncio.Task | None = None
        self._lock = asyncio.Lock()
        self._initialized = False

    async def _get_client(self) -> AsyncClient | None:
        """Get or create async ClickHouse client."""
        if not clickhouse_configured():
            return None

        if self._client is not None:
            return self._client

        try:
            # Parse URL to extract host and port
            url = _resolve_clickhouse_url()
            # Simple URL parsing (http://host:port)
            url = url.replace("http://", "").replace("https://", "")
            if ":" in url:
                host, port_str = url.split(":", 1)
                port = int(port_str.split("/")[0])
            else:
                host = url
                port = 8123

            self._client = await clickhouse_connect.get_async_client(
                host=host,
                port=port,
                username=_resolve_clickhouse_user(),
                password=_resolve_clickhouse_password(),
                database=_resolve_clickhouse_database(),
            )
            logger.info(
                "ClickHouse cost logger initialized: %s@%s:%s/%s",
                _resolve_clickhouse_user(),
                host,
                port,
                _resolve_clickhouse_database(),
            )
            return self._client
        except Exception as exc:  # pragma: no cover - best effort only
            logger.warning("ClickHouse client disabled: %s", exc)
            return None

    async def _start_flush_task(self) -> None:
        """Start the background flush task."""
        if self._flush_task is None or self._flush_task.done():
            self._flush_task = asyncio.create_task(self._periodic_flush())

    async def _periodic_flush(self) -> None:
        """Periodically flush events to ClickHouse."""
        while True:
            try:
                await asyncio.sleep(self.flush_interval)
                await self._flush()
            except asyncio.CancelledError:  # pragma: no cover
                break
            except Exception as exc:  # pragma: no cover - best effort only
                logger.debug("Periodic flush error: %s", exc)

    async def _flush(self) -> None:
        """Flush queued events to ClickHouse."""
        async with self._lock:
            if not self._event_queue:
                return

            client = await self._get_client()
            if client is None:
                # Clear queue if client unavailable to prevent memory buildup
                self._event_queue.clear()
                return

            # Get all events from queue
            events = list(self._event_queue)
            self._event_queue.clear()

            if not events:
                return

            try:
                # Convert events to rows
                rows = [event.to_row() for event in events]

                # Insert into ClickHouse
                await client.insert(
                    table="cost_events",
                    data=rows,
                    column_names=[
                        "timestamp",
                        "provider",
                        "model",
                        "agent",
                        "input_tokens",
                        "output_tokens",
                        "cost",
                        "strategy",
                        "success",
                    ],
                )
                logger.debug("Flushed %d cost events to ClickHouse", len(events))
            except Exception as exc:  # pragma: no cover - best effort only
                logger.warning("Failed to flush cost events: %s", exc)

    async def log_event(
        self,
        *,
        provider: str,
        model: str,
        agent: str | None = None,
        input_tokens: int,
        output_tokens: int,
        cost: float,
        strategy: str | None = None,
        success: bool = True,
    ) -> None:
        """
        Log a cost event asynchronously.

        Args:
            provider: LLM provider name (e.g., "openai", "anthropic")
            model: Model identifier (e.g., "gpt-4", "claude-sonnet-4")
            agent: Optional agent name
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            cost: Estimated cost in USD
            strategy: Routing strategy used (e.g., "cheapest", "fastest")
            success: Whether the request succeeded
        """
        if not clickhouse_configured():
            return

        # Ensure flush task is running
        if not self._initialized:
            self._initialized = True
            await self._start_flush_task()

        # Create event
        event = CostEvent(
            timestamp=datetime.now(),
            provider=provider,
            model=model,
            agent=agent,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost=cost,
            strategy=strategy,
            success=success,
        )

        # Add to queue
        async with self._lock:
            self._event_queue.append(event)

            # Flush if batch size reached
            if len(self._event_queue) >= self.batch_size:
                asyncio.create_task(self._flush())

    async def close(self) -> None:
        """Close the logger and flush remaining events."""
        if self._flush_task is not None:
            self._flush_task.cancel()
            try:
                await self._flush_task
            except asyncio.CancelledError:  # pragma: no cover
                pass

        # Final flush
        await self._flush()

        if self._client is not None:
            try:
                await self._client.close()
            except Exception as exc:  # pragma: no cover - best effort only
                logger.debug("Error closing ClickHouse client: %s", exc)


@lru_cache(maxsize=1)
def get_cost_logger() -> CostEventLogger | None:
    """Get or create the global cost event logger instance."""
    if not clickhouse_configured():
        return None

    try:
        return CostEventLogger()
    except Exception as exc:  # pragma: no cover - best effort only
        logger.warning("Cost logger disabled: %s", exc)
        return None


def reset_cost_logger() -> None:
    """Reset the cached cost logger instance."""
    get_cost_logger.cache_clear()
