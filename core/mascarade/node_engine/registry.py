"""Node type and worker registries (minimal stub for Phase 3).

Full implementation in Phase 5.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from mascarade.node_engine.worker import NodeWorker


@dataclass
class NodeType:
    """Minimal node type definition stub for Phase 3."""

    id: str
    domain: str
    label: str
    description: str
    version: str = "1.0.0"
    inputs: list[dict[str, Any]] = field(default_factory=list)
    outputs: list[dict[str, Any]] = field(default_factory=list)
    config_schema: dict[str, Any] = field(default_factory=dict)


class NodeTypeRegistry:
    """Stub registry for node types. Full implementation in Phase 5."""

    def __init__(self) -> None:
        self._types: dict[str, NodeType] = {}

    def register(self, node_type: NodeType) -> None:
        """Register a node type."""
        self._types[node_type.id] = node_type

    def get(self, type_id: str) -> NodeType:
        """Get a node type by ID."""
        if type_id not in self._types:
            raise KeyError(f"Node type '{type_id}' not found")
        return self._types[type_id]


class WorkerRegistry:
    """Stub registry for workers. Full implementation in Phase 5."""

    def __init__(self) -> None:
        self._workers: dict[str, "NodeWorker"] = {}

    def register(self, worker: "NodeWorker") -> None:
        """Register a worker for its domain."""
        self._workers[worker.domain] = worker

    def get(self, domain: str) -> "NodeWorker":
        """Get the worker for a domain."""
        if domain not in self._workers:
            raise KeyError(f"No worker registered for domain '{domain}'")
        return self._workers[domain]
