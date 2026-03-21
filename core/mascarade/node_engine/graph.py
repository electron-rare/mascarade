"""Graph data model and validation for the Universal Node Engine.

Defines Graph, Node/GraphNode, Edge/GraphEdge, GraphStatus, and ExecutionContext models
with type compatibility validation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, ValidationError, field_validator, model_validator


# --- GraphStatus enum ---


class GraphStatus(str, Enum):
    """Lifecycle status for a graph."""

    DRAFT = "draft"
    VALIDATED = "validated"
    COMPILED = "compiled"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


# --- GraphNode dataclass (used by persistence, E2E tests, engine) ---


@dataclass
class GraphNode:
    """A node in the execution graph (dataclass version).

    Used by the engine, persistence, and E2E tests.
    """

    id: str
    node_type: str
    label: str = ""
    config: dict[str, Any] = field(default_factory=dict)
    position: tuple[float, float] = (0.0, 0.0)
    domain: str | None = None


# --- GraphEdge dataclass (used by persistence, E2E tests, engine) ---


@dataclass
class GraphEdge:
    """A directed edge connecting two nodes (dataclass version).

    Used by the engine, persistence, and E2E tests.
    """

    id: str
    source_node: str
    source_port: str
    target_node: str
    target_port: str


# --- ExecutionContext dataclass (used by some workers) ---


@dataclass
class ExecutionContext:
    """Runtime context passed to each node during execution.

    This is the graph-level execution context. The engine.py module
    also has its own ExecutionContext dataclass used by GraphExecutionEngine.
    """

    graph_id: str
    run_id: str
    node_id: str
    inputs: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


# --- NodeResult dataclass (used by test_node_engine_graph) ---


@dataclass
class NodeResult:
    """Result from a single node execution."""

    node_id: str
    status: str = "pending"
    outputs: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    execution_time_ms: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


# --- Graph dataclass (used by persistence, E2E tests, engine) ---


class Graph:
    """A directed acyclic graph (DAG) of nodes and edges.

    Supports two construction patterns:
    - Graph(id=..., name=..., nodes=[GraphNode(...)], edges=[GraphEdge(...)])
    - Graph(graph_id=..., nodes=[NodeInstance(...)], connections=[Connection(...)])
    """

    def __init__(
        self,
        id: str = "",
        name: str = "",
        version: int = 1,
        status: GraphStatus = GraphStatus.DRAFT,
        nodes: list | None = None,
        edges: list | None = None,
        metadata: dict[str, Any] | None = None,
        *,
        graph_id: str = "",
        connections: list | None = None,
    ):
        self.id = graph_id or id
        self.name = name
        self.version = version
        self.status = status
        self.nodes: list = nodes or []
        self.edges: list = edges or []
        self.connections: list = connections or []
        self.metadata: dict[str, Any] = metadata or {}

        # Validate if using Pydantic models (Node/Edge)
        if self.nodes and isinstance(self.nodes[0], Node):
            self._validate_pydantic_graph()

    def _validate_pydantic_graph(self) -> None:
        """Validate when using Pydantic Node/Edge models."""
        from pydantic import ValidationError as PydanticValidationError

        errors = []

        # Check duplicate node IDs
        ids = [node.id for node in self.nodes if isinstance(node, Node)]
        seen = set()
        duplicates = set()
        for nid in ids:
            if nid in seen:
                duplicates.add(nid)
            seen.add(nid)
        if duplicates:
            errors.append({
                'type': 'value_error',
                'loc': ('nodes',),
                'msg': f"Duplicate node IDs found: {', '.join(duplicates)}",
                'input': ids,
            })

        # Check edge references
        node_ids = set(ids)
        for edge in self.edges:
            if isinstance(edge, Edge):
                if edge.from_node not in node_ids:
                    errors.append({
                        'type': 'value_error',
                        'loc': ('edges',),
                        'msg': f"Edge references non-existent source node: {edge.from_node}",
                        'input': edge.from_node,
                    })
                if edge.to_node not in node_ids:
                    errors.append({
                        'type': 'value_error',
                        'loc': ('edges',),
                        'msg': f"Edge references non-existent destination node: {edge.to_node}",
                        'input': edge.to_node,
                    })

        # Detect cycles
        if not errors and self.edges:
            adjacency: dict[str, list[str]] = {nid: [] for nid in node_ids}
            for edge in self.edges:
                if isinstance(edge, Edge):
                    adjacency.setdefault(edge.from_node, []).append(edge.to_node)

            visited: set[str] = set()
            rec_stack: set[str] = set()

            def has_cycle(nid: str) -> bool:
                visited.add(nid)
                rec_stack.add(nid)
                for neighbor in adjacency.get(nid, []):
                    if neighbor not in visited:
                        if has_cycle(neighbor):
                            return True
                    elif neighbor in rec_stack:
                        return True
                rec_stack.remove(nid)
                return False

            for nid in node_ids:
                if nid not in visited:
                    if has_cycle(nid):
                        errors.append({
                            'type': 'value_error',
                            'loc': ('edges',),
                            'msg': "Graph contains a cycle — DAG constraint violated",
                            'input': None,
                        })
                        break

        if errors:
            raise PydanticValidationError.from_exception_data(
                title='Graph',
                line_errors=[
                    {
                        'type': 'value_error',
                        'loc': err.get('loc', ()),
                        'msg': err['msg'],
                        'input': err.get('input'),
                        'ctx': {'error': ValueError(err['msg'])},
                    }
                    for err in errors
                ],
            )

    @property
    def graph_id(self) -> str:
        return self.id

    def get_node(self, node_id: str) -> Any:
        """Get a node by ID."""
        for node in self.nodes:
            if getattr(node, 'id', getattr(node, 'node_id', None)) == node_id:
                return node
        return None

    def get_incoming_edges(self, node_id: str) -> list:
        """Get all edges that connect to a given node."""
        result = []
        for edge in self.edges:
            # Handle both Edge (Pydantic: to_node) and GraphEdge (dataclass: target_node)
            target = getattr(edge, 'to_node', None) or getattr(edge, 'target_node', None)
            if target == node_id:
                result.append(edge)
        for conn in self.connections:
            if conn.target_node_id == node_id:
                result.append(conn)
        return result

    def get_outgoing_edges(self, node_id: str) -> list:
        """Get all edges originating from a given node."""
        result = []
        for edge in self.edges:
            # Handle both Edge (Pydantic: from_node) and GraphEdge (dataclass: source_node)
            source = getattr(edge, 'from_node', None) or getattr(edge, 'source_node', None)
            if source == node_id:
                result.append(edge)
        for conn in self.connections:
            if conn.source_node_id == node_id:
                result.append(conn)
        return result

    def topological_sort(self) -> list:
        """Return nodes in topological order (dependencies first)."""
        in_degree: dict[str, int] = {}
        adjacency: dict[str, list[str]] = {}
        for node in self.nodes:
            nid = getattr(node, 'id', getattr(node, 'node_id', ''))
            in_degree[nid] = 0
            adjacency[nid] = []

        for edge in self.edges:
            src = getattr(edge, 'from_node', None) or getattr(edge, 'source_node', '')
            tgt = getattr(edge, 'to_node', None) or getattr(edge, 'target_node', '')
            adjacency[src].append(tgt)
            in_degree[tgt] += 1
        for conn in self.connections:
            adjacency[conn.source_node_id].append(conn.target_node_id)
            in_degree[conn.target_node_id] += 1

        queue = [nid for nid, deg in in_degree.items() if deg == 0]
        result = []

        while queue:
            node_id = queue.pop(0)
            node = self.get_node(node_id)
            if node:
                result.append(node)
            for neighbor in adjacency[node_id]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        if len(result) != len(self.nodes):
            raise ValueError("Graph contains a cycle")

        return result

    @property
    def node_count(self) -> int:
        return len(self.nodes)

    @property
    def edge_count(self) -> int:
        return len(self.edges) + len(self.connections)


# --- Pydantic-based models (legacy, used by some code that imports Node/Edge) ---


class Node(BaseModel):
    """A node in the execution graph (Pydantic version)."""

    id: str = Field(...)
    type: str = Field(...)
    inputs: dict[str, Any] = Field(default_factory=dict)
    config: dict[str, Any] = Field(default_factory=dict)

    @field_validator("id")
    @classmethod
    def validate_id(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Node ID cannot be empty")
        if not all(c.isalnum() or c in ("_", "-") for c in v):
            raise ValueError(
                "Node ID must contain only alphanumeric characters, underscores, and hyphens"
            )
        return v.strip()

    @field_validator("type")
    @classmethod
    def validate_type(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Node type cannot be empty")
        if "." not in v:
            raise ValueError(
                "Node type must be fully qualified (domain.typename)"
            )
        return v.strip()

    @property
    def domain(self) -> str:
        return self.type.split(".")[0]

    model_config = {"frozen": True}


class Edge(BaseModel):
    """A directed edge connecting two nodes (Pydantic version)."""

    from_node: str = Field(...)
    from_port: str = Field(...)
    to_node: str = Field(...)
    to_port: str = Field(...)

    @model_validator(mode="after")
    def validate_no_self_loop(self) -> Edge:
        if self.from_node == self.to_node:
            raise ValueError(
                f"Self-loop detected: node '{self.from_node}' cannot connect to itself"
            )
        return self

    @property
    def source(self) -> tuple[str, str]:
        return (self.from_node, self.from_port)

    @property
    def destination(self) -> tuple[str, str]:
        return (self.to_node, self.to_port)

    model_config = {"frozen": True}


# --- Executor-level types (used by executor.py test imports) ---


@dataclass
class Connection:
    """A connection between two node ports in the graph."""

    source_node_id: str = ""
    source_port: str = ""
    target_node_id: str = ""
    target_port: str = ""
    connection_id: str = ""

    # Aliases for engine compatibility
    @property
    def source_node(self) -> str:
        return self.source_node_id

    @property
    def target_node(self) -> str:
        return self.target_node_id


@dataclass
class NodeInstance:
    """A node instance in the graph with its configuration."""

    node_id: str = ""
    node_type: str = ""
    config: dict[str, Any] = field(default_factory=dict)

    @property
    def id(self) -> str:
        return self.node_id
