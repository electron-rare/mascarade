"""Phase 0 - NodeWorker interface for Universal Node Engine.

Stub implementation for Phase 5 cross-domain adapter development.
Full implementation TBD in Phase 0.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ExecutionContext:
    """Context passed to NodeWorker.execute().

    Contains inputs, configuration, and execution metadata.
    """

    inputs: dict[str, Any] = field(default_factory=dict)
    config: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class NodeResult:
    """Result returned from NodeWorker.execute().

    Contains outputs and optional execution metadata.
    """

    outputs: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


class NodeWorker(ABC):
    """Base interface for all node workers.

    All domain workers (AI, CAD, Electronics, Hardware) and cross-domain
    adapters implement this interface for graph execution.
    """

    @abstractmethod
    async def execute(self, context: ExecutionContext) -> NodeResult:
        """Execute the node with the given context.

        Args:
            context: Execution context with inputs and configuration

        Returns:
            NodeResult with outputs

        Raises:
            Various domain-specific exceptions
        """
        ...
