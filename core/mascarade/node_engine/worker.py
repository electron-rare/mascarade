"""Abstract interface for Node Engine domain workers.

Each domain worker (AI, CAD, Electronics, Hardware) implements this interface
to provide graph-executable node types within their domain.
"""

from __future__ import annotations

import asyncio
import logging
from abc import ABC
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

logger = logging.getLogger("mascarade.node_engine")


# --- NodeCapability dataclass ---


@dataclass
class NodeCapability:
    """Capability descriptor returned by worker.capabilities()."""

    node_types: list[str] = field(default_factory=list)
    domain: str = ""
    supports_streaming: bool = False
    supports_cancellation: bool = False
    max_concurrent: int = 10
    requires_gpu: bool = False
    requires_hardware: bool = False
    estimated_memory_mb: int = 128


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
    """

    name: str = ""
    domain: str = ""
    version: str = "1.0.0"
    registry: Any = None

    async def execute(
        self,
        node_type: str,
        inputs: dict[str, Any],
        config: dict[str, Any],
        context: Any,
    ) -> dict[str, Any]:
        """Execute a node of the given type."""
        raise NotImplementedError(f"execute() not implemented for {self.__class__.__name__}")

    async def validate(
        self,
        node_type: str,
        inputs: dict[str, Any],
        config: dict[str, Any],
    ) -> list[str]:
        """Validate node inputs and configuration."""
        return []

    def capabilities(self) -> NodeCapability | WorkerCapabilities | dict[str, Any]:
        """Declare worker capabilities."""
        raise NotImplementedError(f"capabilities() not implemented for {self.__class__.__name__}")

    @property
    def is_available(self) -> bool:
        """Check if the worker is available for execution."""
        return True

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
from mascarade.node_engine.graph import ExecutionContext, NodeResult  # noqa: E402
