"""Abstract interface for Node Engine domain workers.

Each domain worker (AI, CAD, Electronics, Hardware) implements this interface
to provide graph-executable node types within their domain.
"""

from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
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


logger = logging.getLogger("mascarade.node_engine")

# Exceptions transitoires communes pour workers
RETRYABLE_WORKER_EXCEPTIONS = (ConnectionError, TimeoutError, OSError)


def make_worker_retry(*extra_exceptions: type[BaseException]):
    """Créer un décorateur retry avec exceptions spécifiques au worker."""
    return retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type(RETRYABLE_WORKER_EXCEPTIONS + tuple(extra_exceptions)),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )


@dataclass
class NodeCapability:
    """Declares what a worker can do — used for routing and scheduling."""

    node_types: list[str] = field(default_factory=list)
    domain: str = ""
    supports_streaming: bool = False
    supports_cancellation: bool = True
    max_concurrent: int = 10
    requires_gpu: bool = False
    requires_hardware: bool = False
    estimated_memory_mb: int = 256


class NodeWorker(ABC):
    """Abstract interface for domain-specific node workers.

    Domain workers execute nodes within the graph runtime. Each worker is
    responsible for a specific domain (e.g., "ai", "cad", "electronics")
    and provides a set of node types that can be composed into graphs.

    Workers are registered with the GraphRuntime via the NodeWorkerRegistry.
    At execution time, the runtime dispatches node execution requests to the
    appropriate worker based on the node's domain.

    Circuit Breaker Support:
        Les méthodes execute() sont protégées par un circuit breaker
        pour prévenir les pannes en cascade. Le circuit breaker est
        automatiquement appliqué par le Node Engine.

        États: CLOSED (normal) → OPEN (échecs, rejet 60s) → HALF_OPEN (test)
        Configuration: fail_max=5, timeout=60s

    Example:
        ```python
        class AIWorker(NodeWorker):
            name = "ai-worker"
            domain = "ai"

            async def execute(self, node_type, inputs, config, context):
                if node_type == "ai.llm-inference":
                    return await self._llm_inference(inputs, config)
                raise ValueError(f"Unknown node type: {node_type}")

            async def validate(self, node_type, inputs, config):
                errors = []
                if node_type == "ai.llm-inference" and "prompt" not in inputs:
                    errors.append("Missing required input: prompt")
                return errors

            def capabilities(self):
                return NodeCapability(
                    node_types=["ai.llm-inference", "ai.llm-stream"],
                    domain="ai",
                    supports_streaming=True,
                    max_concurrent=10,
                )
        ```
    """

    name: str
    domain: str

    # Circuit breaker instance (set by Node Engine or CircuitBreakerManager)
    circuit_breaker: CircuitBreaker | None = None

    @abstractmethod
    async def execute(
        self,
        node_type: str,
        inputs: dict[str, Any],
        config: dict[str, Any],
        context: Any,
    ) -> dict[str, Any]:
        """Execute a node with the given inputs.

        Protected by a circuit breaker at the Node Engine level.

        Args:
            node_type: Fully qualified node type identifier
            inputs: Input port values (by port ID)
            config: Node-specific configuration
            context: Execution context with metadata and cancellation

        Returns:
            Output port values (by port ID)

        Raises:
            CircuitBreakerError: If the circuit breaker is open
            ConnectionError: Connection error
            TimeoutError: Execution timeout
            ValueError: Invalid inputs or configuration
        """
        raise NotImplementedError(f"execute() not implemented for {self.__class__.__name__}")

    async def execute_stream(
        self,
        node_type: str,
        inputs: dict[str, Any],
        config: dict[str, Any],
        context: Any,
    ) -> AsyncIterator[dict[str, Any]]:
        """Execute a node with streaming output.

        Returns an async iterator that yields partial result chunks.
        Workers that support streaming should override this method.

        Args:
            node_type: Fully qualified node type identifier
            inputs: Input port values (by port ID)
            config: Node-specific configuration
            context: Execution context for the current graph run

        Yields:
            Partial output dictionaries (chunk format is worker-defined)

        Raises:
            NotImplementedError: If the worker does not support streaming
        """
        raise NotImplementedError(
            f"execute_stream() not implemented for {self.__class__.__name__}"
        )
        # Make this an async generator (yield is needed for the type signature)
        yield  # pragma: no cover

    async def validate(
        self,
        node_type: str,
        inputs: dict[str, Any],
        config: dict[str, Any],
    ) -> list[str]:
        """Validate node inputs and configuration before execution.

        Called during graph validation to catch errors early.

        Args:
            node_type: Fully qualified node type (e.g., "ai.agent-dispatch")
            inputs: Dictionary of input port values to validate
            config: Node configuration parameters to validate

        Returns:
            List of validation error messages. Empty list if validation passes.
        """
        return []

    def capabilities(self) -> NodeCapability | dict[str, Any]:
        """Declare worker capabilities for the registry.

        The runtime uses this information for scheduling, resource management,
        and feature discovery.

        Returns:
            NodeCapability or dict with capability metadata.
            Required keys (if dict): node_types (list[str]), domain (str).
        """
        raise NotImplementedError(f"capabilities() not implemented for {self.__class__.__name__}")

    @property
    def is_available(self) -> bool:
        """Check if the worker is available for execution."""
        return True

    def on_init(self, context: Any) -> None:
        """Lifecycle hook: called when a graph execution starts."""
        pass

    def on_destroy(self, context: Any) -> None:
        """Lifecycle hook: called when a graph execution completes."""
        pass

    async def initialize(self) -> None:
        """Initialize the worker (optional override)."""
        raise NotImplementedError(f"initialize() not implemented for {self.__class__.__name__}")

    async def shutdown(self) -> None:
        """Shutdown the worker (optional override)."""
        raise NotImplementedError(f"shutdown() not implemented for {self.__class__.__name__}")

    async def _check_tool(self, tool_name: str) -> bool:
        """Check if an external tool is available in PATH."""
        try:
            proc = await asyncio.create_subprocess_exec(
                "which",
                tool_name,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await proc.wait()
            return proc.returncode == 0
        except Exception:
            return False
