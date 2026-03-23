"""Abstract interface for Node Engine domain workers.

Each domain worker (AI, CAD, Electronics, Hardware) implements this interface
to provide graph-executable node types within their domain.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

if TYPE_CHECKING:
    from aiobreaker import CircuitBreaker

    from mascarade.node_engine.graph import ExecutionContext

logger = logging.getLogger("mascarade.node_engine")

RETRYABLE_WORKER_EXCEPTIONS = (ConnectionError, TimeoutError, OSError)


def make_worker_retry(*extra_exceptions: type[BaseException]):
    """Create a retry decorator with worker-specific exceptions."""
    return retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type(RETRYABLE_WORKER_EXCEPTIONS + tuple(extra_exceptions)),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )


@dataclass
class NodeCapability:
    """Declares what a worker can do -- used for routing and scheduling."""

    node_types: list[str]
    domain: str
    supports_streaming: bool = False
    supports_cancellation: bool = True
    max_concurrent: int = 10
    requires_gpu: bool = False
    requires_hardware: bool = False
    estimated_memory_mb: int = 256


class NodeWorker(ABC):
    """Abstract interface for domain-specific node workers.

    Domain workers execute nodes within the graph runtime. Each worker is responsible
    for a specific domain (e.g., "ai", "cad", "electronics") and provides a set of
    node types that can be composed into graphs.
    """

    name: str
    domain: str

    circuit_breaker: "CircuitBreaker | None" = None

    @abstractmethod
    async def execute(
        self,
        node_type: str,
        inputs: dict[str, Any],
        config: dict[str, Any],
        context: "ExecutionContext",
    ) -> dict[str, Any]:
        """Execute a node of the given type with provided inputs and configuration.

        Args:
            node_type: Fully qualified node type (e.g., "ai.llm-inference")
            inputs: Dictionary of input port values keyed by port name
            config: Node configuration parameters
            context: Execution context for the current graph run

        Returns:
            Dictionary of output port values keyed by port name
        """
        ...

    @abstractmethod
    async def validate(
        self,
        node_type: str,
        inputs: dict[str, Any],
        config: dict[str, Any],
    ) -> list[str]:
        """Validate node inputs and configuration before execution.

        Returns:
            List of validation error messages. Empty list if validation passes.
        """
        ...

    @abstractmethod
    def capabilities(self) -> NodeCapability:
        """Declare worker capabilities for the registry."""
        ...

    @property
    def is_available(self) -> bool:
        """Check if the worker is available for execution."""
        return True

    def on_init(self, context: "ExecutionContext") -> None:
        """Lifecycle hook: called when a graph execution starts."""
        pass

    def on_destroy(self, context: "ExecutionContext") -> None:
        """Lifecycle hook: called when a graph execution completes."""
        pass
