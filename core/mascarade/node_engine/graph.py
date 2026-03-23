"""Graph data model and validation for the Universal Node Engine.

Defines Graph, Node, and Edge models with type compatibility validation.
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
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator


class Node(BaseModel):
    """A node in the execution graph.

    Each node represents a unit of computation with typed inputs and outputs.
    Nodes are executed by domain workers based on their node_type.

    Example:
        >>> node = Node(
        ...     id="llm1",
        ...     type="ai.llm-inference",
        ...     inputs={"prompt": "Hello, world!"},
        ...     config={"temperature": 0.7, "model": "gpt-4"},
        ... )
    """

    id: str = Field(
        ...,
        description="Unique identifier for this node within the graph",
        min_length=1,
    )
    type: str = Field(
        ...,
        description="Fully qualified node type (e.g., 'ai.llm-inference', 'cad.sketch')",
        min_length=1,
    )
    inputs: dict[str, Any] = Field(
        default_factory=dict,
        description="Input port values. Keys are port names, values are literal values or None (if connected via Edge)",
    )
    config: dict[str, Any] = Field(
        default_factory=dict,
        description="Node configuration parameters (e.g., temperature, max_tokens)",
    )

    @field_validator("id")
    @classmethod
    def validate_id(cls, v: str) -> str:
        """Validate node ID format."""
        if not v or not v.strip():
            raise ValueError("Node ID cannot be empty")
        # Ensure ID is a valid identifier (alphanumeric + underscore/hyphen)
        if not all(c.isalnum() or c in ("_", "-") for c in v):
            raise ValueError(
                "Node ID must contain only alphanumeric characters, underscores, and hyphens"
            )
        return v.strip()

    @field_validator("type")
    @classmethod
    def validate_type(cls, v: str) -> str:
        """Validate node type format."""
        if not v or not v.strip():
            raise ValueError("Node type cannot be empty")
        # Must be domain.typename format
        if "." not in v:
            raise ValueError(
                "Node type must be fully qualified (domain.typename, e.g., 'ai.llm-inference')"
            )
        return v.strip()

    @property
    def domain(self) -> str:
        """Extract domain from node type."""
        return self.type.split(".")[0]

    model_config = {"frozen": True}  # Make instances immutable


class Edge(BaseModel):
    """A directed edge connecting two nodes in the graph.

    Edges define data flow between nodes. The output port of the source node
    is connected to the input port of the destination node.

    Example:
        >>> edge = Edge(
        ...     from_node="template1",
        ...     from_port="prompt",
        ...     to_node="llm1",
        ...     to_port="prompt",
        ... )
    """

    from_node: str = Field(
        ...,
        description="Source node ID",
        min_length=1,
    )
    from_port: str = Field(
        ...,
        description="Source node output port name",
        min_length=1,
    )
    to_node: str = Field(
        ...,
        description="Destination node ID",
        min_length=1,
    )
    to_port: str = Field(
        ...,
        description="Destination node input port name",
        min_length=1,
    )

    @model_validator(mode="after")
    def validate_no_self_loop(self) -> Edge:
        """Ensure edge does not connect a node to itself."""
        if self.from_node == self.to_node:
            raise ValueError(
                f"Self-loop detected: node '{self.from_node}' cannot connect to itself"
            )
        return self

    @property
    def source(self) -> tuple[str, str]:
        """Return (node_id, port_name) tuple for source."""
        return (self.from_node, self.from_port)

    @property
    def destination(self) -> tuple[str, str]:
        """Return (node_id, port_name) tuple for destination."""
        return (self.to_node, self.to_port)

    model_config = {"frozen": True}  # Make instances immutable


class Graph(BaseModel):
    """A directed acyclic graph (DAG) of nodes and edges.

    Represents a complete executable workflow. The graph validates:
    - All edge references point to existing nodes
    - No cycles exist (DAG constraint)
    - Type compatibility between connected ports (when type registry is available)

    Example:
        >>> graph = Graph(
        ...     nodes=[
        ...         Node(id="n1", type="ai.prompt-template", inputs={"template": "Hello {{name}}"}),
        ...         Node(id="n2", type="ai.llm-inference", config={"temperature": 0.7}),
        ...     ],
        ...     edges=[
        ...         Edge(from_node="n1", from_port="prompt", to_node="n2", to_port="prompt"),
        ...     ],
        ... )
    """

    nodes: list[Node] = Field(
        default_factory=list,
        description="List of nodes in the graph",
    )
    edges: list[Edge] = Field(
        default_factory=list,
        description="List of directed edges connecting nodes",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Optional metadata (name, description, version, etc.)",
    )

    @field_validator("nodes")
    @classmethod
    def validate_unique_node_ids(cls, v: list[Node]) -> list[Node]:
        """Ensure all node IDs are unique."""
        ids = [node.id for node in v]
        duplicates = [nid for nid in ids if ids.count(nid) > 1]
        if duplicates:
            raise ValueError(
                f"Duplicate node IDs found: {', '.join(set(duplicates))}"
            )
        return v

    @model_validator(mode="after")
    def validate_edges(self) -> Graph:
        """Validate that all edges reference existing nodes."""
        node_ids = {node.id for node in self.nodes}

        for edge in self.edges:
            if edge.from_node not in node_ids:
                raise ValueError(
                    f"Edge references non-existent source node: {edge.from_node}"
                )
            if edge.to_node not in node_ids:
                raise ValueError(
                    f"Edge references non-existent destination node: {edge.to_node}"
                )

        return self

    @model_validator(mode="after")
    def validate_no_cycles(self) -> Graph:
        """Ensure the graph is acyclic (DAG constraint)."""
        # Build adjacency list
        adjacency: dict[str, list[str]] = {node.id: [] for node in self.nodes}
        for edge in self.edges:
            adjacency[edge.from_node].append(edge.to_node)

        # Detect cycles using DFS
        visited: set[str] = set()
        rec_stack: set[str] = set()

        def has_cycle(node_id: str) -> bool:
            visited.add(node_id)
            rec_stack.add(node_id)

            for neighbor in adjacency[node_id]:
                if neighbor not in visited:
                    if has_cycle(neighbor):
                        return True
                elif neighbor in rec_stack:
                    return True

            rec_stack.remove(node_id)
            return False

        for node in self.nodes:
            if node.id not in visited:
                if has_cycle(node.id):
                    raise ValueError(
                        "Graph contains a cycle — DAG constraint violated"
                    )

        return self

    def get_node(self, node_id: str) -> Node | None:
        """Get a node by ID."""
        for node in self.nodes:
            if node.id == node_id:
                return node
        return None

    def get_incoming_edges(self, node_id: str) -> list[Edge]:
        """Get all edges that connect to a given node."""
        return [edge for edge in self.edges if edge.to_node == node_id]

    def get_outgoing_edges(self, node_id: str) -> list[Edge]:
        """Get all edges originating from a given node."""
        return [edge for edge in self.edges if edge.from_node == node_id]

    def topological_sort(self) -> list[Node]:
        """Return nodes in topological order (dependencies first).

        Raises:
            ValueError: If graph contains cycles (should be caught by validation)
        """
        # Build in-degree map
        in_degree: dict[str, int] = {node.id: 0 for node in self.nodes}
        adjacency: dict[str, list[str]] = {node.id: [] for node in self.nodes}

        for edge in self.edges:
            adjacency[edge.from_node].append(edge.to_node)
            in_degree[edge.to_node] += 1

        # Queue nodes with no incoming edges
        queue: list[str] = [
            node_id for node_id, degree in in_degree.items() if degree == 0
        ]
        result: list[Node] = []

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
        """Return the number of nodes in the graph."""
        return len(self.nodes)

    @property
    def edge_count(self) -> int:
        """Return the number of edges in the graph."""
        return len(self.edges)

    model_config = {"frozen": False}  # Allow mutation for graph construction
