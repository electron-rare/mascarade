"""Abstract interface for Node Engine domain workers.

Each domain worker (AI, CAD, Electronics, Hardware) implements this interface
to provide graph-executable node types within their domain.

Circuit Breaker Support:
    Worker execute() methods are protected by a circuit breaker to prevent
    cascading failures. The circuit breaker is automatically applied by the
    Node Engine when calling workers.

    Circuit breaker states:
    - CLOSED: Normal operation
    - OPEN: Repeated failures, calls rejected immediately
    - HALF_OPEN: Recovery testing

    Default configuration: fail_max=5, timeout=60s
"""

from __future__ import annotations

import asyncio
import logging
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

# Retryable transient exceptions common to workers
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


# --- NodeCapability dataclass ---


@dataclass
class NodeCapability:
    """Capability descriptor returned by worker.capabilities()."""

    node_types: list[str] = field(default_factory=list)
    domain: str = ""
    supports_streaming: bool = False
    supports_cancellation: bool = True
    max_concurrent: int = 10
    requires_gpu: bool = False
    requires_hardware: bool = False
    estimated_memory_mb: int = 256


# --- WorkerCapabilities (extended version used by electronics workers) ---


@dataclass
class WorkerCapabilities:
    """Extended capability descriptor for electronics workers."""

    node_prefixes: list[str] = field(default_factory=list)
    max_concurrent: int = 4
    requires_gpu: bool = False
    estimated_memory_mb: int = 512
    external_tools: list[str] = field(default_factory=list)


# --- NodeWorker abstract base class ---


class NodeWorker:
    """
    Base class for domain-specific node workers.

    Domain workers execute nodes within the graph runtime. Each worker is responsible
    for a specific domain (e.g., "ai", "cad", "electronics") and provides a set of
    node types that can be composed into graphs.

    Workers are registered with the GraphRuntime via the WorkerRegistry.
    At execution time, the runtime dispatches node execution requests to the
    appropriate worker based on the node's domain.

    Subclasses should override execute(), validate(), capabilities(),
    initialize(), and shutdown() as needed.

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
                return {
                    "node_types": ["ai.llm-inference", "ai.llm-stream"],
                    "domain": "ai",
                    "supports_streaming": True,
                    "max_concurrent": 10,
                }
        ```
    """

    name: str = ""
    domain: str = ""
    version: str = "1.0.0"
    registry: Any = None

    # Circuit breaker instance (set by Node Engine or CircuitBreakerManager)
    circuit_breaker: CircuitBreaker | None = None

    async def execute(
        self,
        node_type: str,
        inputs: dict[str, Any],
        config: dict[str, Any],
        context: Any,
    ) -> dict[str, Any]:
        """Execute a node of the given type.

        This is the primary entry point for node execution. The runtime calls this
        method when a node of this worker's domain needs to be executed.

        Note: This method is protected by a circuit breaker at the Node Engine level
        to prevent cascading failures. The circuit opens after 5 consecutive failures
        and rejects calls for 60s before testing recovery.

        Args:
            node_type: Fully qualified node type (e.g., "ai.llm-inference")
            inputs: Dictionary of input port values keyed by port name
            config: Node configuration parameters (e.g., temperature, model)
            context: Execution context for the current graph run

        Returns:
            Dictionary of output port values keyed by port name

        Raises:
            ValueError: If node_type is not supported by this worker
            RuntimeError: If execution fails due to worker-specific errors
            CircuitBreakerError: If the circuit breaker is open
        """
        raise NotImplementedError(f"execute() not implemented for {self.__class__.__name__}")

    async def validate(
        self,
        node_type: str,
        inputs: dict[str, Any],
        config: dict[str, Any],
    ) -> list[str]:
        """Validate node inputs and configuration before execution.

        Called during graph validation to catch errors early. This allows
        validation errors to be reported before execution begins.

        Args:
            node_type: Fully qualified node type (e.g., "ai.agent-dispatch")
            inputs: Dictionary of input port values to validate
            config: Node configuration parameters to validate

        Returns:
            List of validation error messages. Empty list if validation passes.
        """
        return []

    def capabilities(self) -> NodeCapability | WorkerCapabilities | dict[str, Any]:
        """Declare worker capabilities for the registry.

        The runtime uses this information for scheduling, resource management,
        and feature discovery.

        Returns:
            NodeCapability, WorkerCapabilities, or dict with capability metadata.
            Required keys (if dict): node_types (list[str]), domain (str).
        """
        raise NotImplementedError(f"capabilities() not implemented for {self.__class__.__name__}")

    @property
    def is_available(self) -> bool:
        """Check if the worker is available for execution.

        The runtime uses this to determine whether to include this worker
        in the active worker pool. Workers may be unavailable due to
        missing API keys, required services being offline, or hardware
        not connected.

        Returns:
            True if worker is ready to execute nodes, False otherwise.
        """
        return True

    def on_init(self, context: Any) -> None:
        """Lifecycle hook: called when a graph execution starts.

        Optional override for workers that need to initialize resources,
        establish connections, or load models at the start of execution.

        Args:
            context: Execution context with graph/run metadata
        """
        pass

    def on_destroy(self, context: Any) -> None:
        """Lifecycle hook: called when a graph execution completes.

        Optional override for workers that need to release resources,
        close connections, or flush buffers at the end of execution.

        Args:
            context: Execution context with graph/run metadata
        """
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
                "which", tool_name,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await proc.wait()
            return proc.returncode == 0
        except Exception:
            return False


# Re-export ExecutionContext and NodeResult for convenience
# (some code imports them from worker module)
