"""Graph representation for the Universal Node Engine.

Modeled on the Orchestrator's TaskResult/OrchestrationRun pattern
but extended for arbitrary DAG execution.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class GraphStatus(StrEnum):
    """Status of a graph during its lifecycle."""

    DRAFT = "draft"
    VALIDATED = "validated"
    COMPILED = "compiled"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class GraphNode:
    """A node instance within a graph."""

    id: str
    node_type: str
    label: str
    config: dict[str, Any] = field(default_factory=dict)
    position: tuple[float, float] = (0.0, 0.0)
    domain: str | None = None


@dataclass
class GraphEdge:
    """A typed connection between two node ports."""

    id: str
    source_node: str
    source_port: str
    target_node: str
    target_port: str


@dataclass
class Graph:
    """A complete node graph ready for execution."""

    id: str
    name: str
    version: int = 1
    status: GraphStatus = GraphStatus.DRAFT
    nodes: list[GraphNode] = field(default_factory=list)
    edges: list[GraphEdge] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ExecutionContext:
    """Runtime context for executing a single node."""

    graph_id: str
    run_id: str
    node_id: str
    inputs: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class NodeResult:
    """Result of executing a single node."""

    node_id: str
    status: str
    outputs: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    execution_time_ms: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
