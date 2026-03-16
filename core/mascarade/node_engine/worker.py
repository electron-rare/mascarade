"""NodeWorker — minimal stub for Phase 3 testing.

Full implementation in Phase 4 (subtask-4-1).
This stub provides just enough for parallel execution tests.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from mascarade.node_engine.graph import ExecutionContext


@dataclass
class NodeCapability:
    """Declares what a worker can do — used for routing and scheduling."""

    node_types: list[str]
    domain: str
    supports_streaming: bool = False
    supports_cancellation: bool = True
    max_concurrent: int = 10
    requires_gpu: bool = False
    requires_hardware: bool = False
    estimated_memory_mb: int = 256


class NodeWorker(ABC):
    """
    Abstract base class for all domain workers (minimal stub for Phase 3).

    Full implementation with circuit breaker integration and retry
    support will be added in Phase 4.
    """

    name: str
    domain: str

    @abstractmethod
    async def execute(
        self,
        node_type: str,
        inputs: dict[str, Any],
        config: dict[str, Any],
        context: "ExecutionContext",
    ) -> dict[str, Any]:
        """
        Execute a node of the given type with the provided inputs.

        Args:
            node_type: The registered node type identifier
            inputs: Input port values (keyed by port ID)
            config: Node-specific configuration
            context: Execution context with run metadata and cancellation

        Returns:
            Output port values (keyed by port ID)
        """
        ...

    @abstractmethod
    async def validate(
        self,
        node_type: str,
        inputs: dict[str, Any],
        config: dict[str, Any],
    ) -> list[str]:
        """
        Validate inputs and configuration before execution.

        Returns a list of validation error messages (empty if valid).

        Args:
            node_type: The registered node type identifier
            inputs: Input port values to validate
            config: Node-specific configuration to validate

        Returns:
            List of validation error messages (empty = valid)
        """
        ...

    @abstractmethod
    def capabilities(self) -> NodeCapability:
        """Declare this worker's capabilities."""
        ...
