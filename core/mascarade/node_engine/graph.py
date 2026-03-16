"""Graph representation for the Universal Node Engine.

A graph consists of nodes (instances of node types) connected by edges
(connections between output and input ports).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel, Field

from mascarade.node_engine.base import NodeDefinition
from mascarade.node_engine.types import NodePort

logger = logging.getLogger("mascarade.node_engine")


class NodeInstance(BaseModel):
    """Instance of a node in a graph.

    A node instance has:
    - A unique ID within the graph
    - A reference to its node type (NodeDefinition)
    - Configuration parameters
    - Input/output port values during execution
    """

    node_id: str = Field(description="Unique node instance ID within the graph")
    node_type: str = Field(description="Fully qualified node type (e.g., hardware.esp32.gpio)")
    config: dict[str, Any] = Field(
        default_factory=dict, description="Configuration parameters for this instance"
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Additional metadata (tags, position, etc.)"
    )


class Connection(BaseModel):
    """Connection between two nodes in a graph.

    Connects an output port of one node to an input port of another node.
    """

    connection_id: str = Field(description="Unique connection ID within the graph")
    source_node_id: str = Field(description="ID of the source node")
    source_port: str = Field(description="Name of the output port on source node")
    target_node_id: str = Field(description="ID of the target node")
    target_port: str = Field(description="Name of the input port on target node")


class Graph(BaseModel):
    """Graph representation for node-based workflow execution.

    A graph contains:
    - Nodes (instances of node types)
    - Connections (edges between nodes)
    - Metadata (description, tags, version)
    """

    graph_id: str = Field(description="Unique graph identifier")
    name: str = Field("", description="Human-readable graph name")
    description: str = Field("", description="Graph description")
    nodes: list[NodeInstance] = Field(default_factory=list, description="Nodes in the graph")
    connections: list[Connection] = Field(
        default_factory=list, description="Connections between nodes"
    )
    metadata: dict[str, Any] = Field(default_factory=dict, description="Graph metadata")
    version: str = Field("1.0.0", description="Graph version")

    def get_node(self, node_id: str) -> NodeInstance:
        """Get a node by ID.

        Args:
            node_id: Node instance ID

        Returns:
            NodeInstance with the given ID

        Raises:
            KeyError: If node not found
        """
        for node in self.nodes:
            if node.node_id == node_id:
                return node
        raise KeyError(f"Node '{node_id}' not found in graph '{self.graph_id}'")

    def get_connections_from_node(self, node_id: str) -> list[Connection]:
        """Get all outgoing connections from a node.

        Args:
            node_id: Source node ID

        Returns:
            List of connections originating from this node
        """
        return [conn for conn in self.connections if conn.source_node_id == node_id]

    def get_connections_to_node(self, node_id: str) -> list[Connection]:
        """Get all incoming connections to a node.

        Args:
            node_id: Target node ID

        Returns:
            List of connections targeting this node
        """
        return [conn for conn in self.connections if conn.target_node_id == node_id]

    def get_input_connections(self, node_id: str, port_name: str) -> list[Connection]:
        """Get connections providing input to a specific port.

        Args:
            node_id: Target node ID
            port_name: Input port name

        Returns:
            List of connections targeting this specific port
        """
        return [
            conn
            for conn in self.connections
            if conn.target_node_id == node_id and conn.target_port == port_name
        ]

    def add_node(self, node: NodeInstance) -> None:
        """Add a node to the graph.

        Args:
            node: Node instance to add

        Raises:
            ValueError: If node ID already exists
        """
        if any(n.node_id == node.node_id for n in self.nodes):
            raise ValueError(f"Node ID '{node.node_id}' already exists in graph")
        self.nodes.append(node)

    def add_connection(self, connection: Connection) -> None:
        """Add a connection to the graph.

        Args:
            connection: Connection to add

        Raises:
            ValueError: If connection ID already exists or nodes not found
        """
        if any(c.connection_id == connection.connection_id for c in self.connections):
            raise ValueError(f"Connection ID '{connection.connection_id}' already exists")

        # Verify nodes exist
        self.get_node(connection.source_node_id)
        self.get_node(connection.target_node_id)

        self.connections.append(connection)


@dataclass
class GraphValidator:
    """Validator for graph structure and node connections.

    Validates:
    - Node type references are valid
    - Connections are type-compatible
    - No cyclic dependencies (for non-streaming graphs)
    - Required inputs are connected
    - No dangling connections
    """

    def validate(
        self, graph: Graph, node_definitions: dict[str, NodeDefinition]
    ) -> list[str]:
        """Validate a graph and return list of errors.

        Args:
            graph: Graph to validate
            node_definitions: Available node type definitions

        Returns:
            List of error messages (empty if valid)
        """
        errors: list[str] = []

        # Validate node types exist
        for node in graph.nodes:
            if node.node_type not in node_definitions:
                errors.append(
                    f"Node '{node.node_id}' references unknown type '{node.node_type}'"
                )

        # Validate connections
        for conn in graph.connections:
            # Check source node and port exist
            try:
                source_node = graph.get_node(conn.source_node_id)
                if source_node.node_type in node_definitions:
                    source_def = node_definitions[source_node.node_type]
                    try:
                        source_def.get_output_port(conn.source_port)
                    except KeyError:
                        errors.append(
                            f"Connection '{conn.connection_id}' references unknown "
                            f"output port '{conn.source_port}' on node '{conn.source_node_id}'"
                        )
            except KeyError as e:
                errors.append(f"Connection '{conn.connection_id}' has invalid source: {e}")

            # Check target node and port exist
            try:
                target_node = graph.get_node(conn.target_node_id)
                if target_node.node_type in node_definitions:
                    target_def = node_definitions[target_node.node_type]
                    try:
                        target_def.get_input_port(conn.target_port)
                    except KeyError:
                        errors.append(
                            f"Connection '{conn.connection_id}' references unknown "
                            f"input port '{conn.target_port}' on node '{conn.target_node_id}'"
                        )
            except KeyError as e:
                errors.append(f"Connection '{conn.connection_id}' has invalid target: {e}")

            # Check type compatibility if both nodes are valid
            try:
                source_node = graph.get_node(conn.source_node_id)
                target_node = graph.get_node(conn.target_node_id)
                if (
                    source_node.node_type in node_definitions
                    and target_node.node_type in node_definitions
                ):
                    source_def = node_definitions[source_node.node_type]
                    target_def = node_definitions[target_node.node_type]
                    try:
                        source_port = source_def.get_output_port(conn.source_port)
                        target_port = target_def.get_input_port(conn.target_port)
                        if not source_port.is_compatible_with(target_port):
                            errors.append(
                                f"Connection '{conn.connection_id}' has incompatible types: "
                                f"{source_port.port_type.kind}/{source_port.port_type.name} -> "
                                f"{target_port.port_type.kind}/{target_port.port_type.name}"
                            )
                    except KeyError:
                        pass  # Already reported port not found above
            except KeyError:
                pass  # Already reported node not found above

        # Check required inputs are connected
        for node in graph.nodes:
            if node.node_type not in node_definitions:
                continue
            node_def = node_definitions[node.node_type]
            for input_port in node_def.input_ports:
                if input_port.required:
                    connections = graph.get_input_connections(node.node_id, input_port.name)
                    if not connections:
                        # Check if default value exists in config
                        if input_port.name not in node.config:
                            errors.append(
                                f"Node '{node.node_id}' missing required input '{input_port.name}' "
                                f"(no connection and no config default)"
                            )

        # Detect cycles (simple DFS-based cycle detection)
        cycle_errors = self._check_cycles(graph)
        errors.extend(cycle_errors)

        return errors

    def _check_cycles(self, graph: Graph) -> list[str]:
        """Check for cycles in the graph using DFS.

        Args:
            graph: Graph to check

        Returns:
            List of error messages describing cycles found
        """
        errors: list[str] = []
        visited: set[str] = set()
        rec_stack: set[str] = set()

        def visit(node_id: str, path: list[str]) -> bool:
            """Visit a node in DFS traversal.

            Returns True if cycle detected.
            """
            if node_id in rec_stack:
                cycle_path = " -> ".join(path + [node_id])
                errors.append(f"Cycle detected: {cycle_path}")
                return True

            if node_id in visited:
                return False

            visited.add(node_id)
            rec_stack.add(node_id)

            # Visit all downstream nodes
            for conn in graph.get_connections_from_node(node_id):
                if visit(conn.target_node_id, path + [node_id]):
                    pass  # Continue checking for more cycles

            rec_stack.remove(node_id)
            return False

        # Check from each node
        for node in graph.nodes:
            if node.node_id not in visited:
                visit(node.node_id, [])

        return errors
