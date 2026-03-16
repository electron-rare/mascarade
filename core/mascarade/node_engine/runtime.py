"""Graph runtime — node execution engine for the Universal Node Engine."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from mascarade.node_engine.registry import NodeRegistry
    from mascarade.node_engine.types import PortType

logger = logging.getLogger("mascarade.node_engine.runtime")


class NodeStatus(str, Enum):
    """Execution status of a node."""

    PENDING = "pending"
    READY = "ready"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class NodeInstance:
    """A node instance in the graph with runtime state.

    Attributes:
        node_id: Unique identifier for this node instance
        node_type: Type identifier (e.g., "electronics.spice.simulate")
        inputs: Input port definitions
        outputs: Output port definitions
        config: Node configuration parameters
        status: Current execution status
        input_values: Values received on input ports
        output_values: Values produced on output ports
        error: Error message if status is FAILED
    """

    node_id: str
    node_type: str
    inputs: list[PortType] = field(default_factory=list)
    outputs: list[PortType] = field(default_factory=list)
    config: dict[str, Any] = field(default_factory=dict)
    status: NodeStatus = NodeStatus.PENDING
    input_values: dict[str, Any] = field(default_factory=dict)
    output_values: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


@dataclass
class Connection:
    """A connection between two node ports.

    Attributes:
        from_node: Source node ID
        from_port: Source output port name
        to_node: Destination node ID
        to_port: Destination input port name
    """

    from_node: str
    from_port: str
    to_node: str
    to_port: str


@dataclass
class GraphDefinition:
    """Definition of a node graph.

    Attributes:
        graph_id: Unique identifier for this graph
        nodes: Node instances in the graph
        connections: Connections between nodes
        metadata: Additional graph metadata
    """

    graph_id: str
    nodes: list[NodeInstance] = field(default_factory=list)
    connections: list[Connection] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class GraphRuntime:
    """Runtime engine for executing node graphs.

    The GraphRuntime orchestrates the execution of node graphs:
    - Validates graph topology and type compatibility
    - Determines execution order based on dependencies
    - Executes nodes with proper data flow
    - Tracks execution state and handles errors

    Example:
        >>> from mascarade.node_engine.runtime import GraphRuntime, GraphDefinition
        >>> from mascarade.node_engine.registry import NodeRegistry
        >>> registry = NodeRegistry()
        >>> runtime = GraphRuntime(registry=registry)
        >>> graph = GraphDefinition(graph_id="test-graph")
        >>> # Add nodes and connections
        >>> result = await runtime.execute(graph)
    """

    def __init__(self, registry: NodeRegistry) -> None:
        """Initialize the graph runtime.

        Args:
            registry: NodeRegistry for type validation and worker lookup
        """
        self._registry = registry
        self._execution_history: list[dict[str, Any]] = []

    async def execute(self, graph: GraphDefinition) -> dict[str, Any]:
        """Execute a node graph.

        Args:
            graph: Graph definition to execute

        Returns:
            Execution result with status, outputs, and metrics

        Raises:
            ValueError: If graph is invalid
        """
        logger.info("Starting graph execution: %s", graph.graph_id)

        # Validate graph topology
        validation_result = self._validate_graph(graph)
        if not validation_result["valid"]:
            error_msg = f"Graph validation failed: {validation_result['errors']}"
            logger.error(error_msg)
            raise ValueError(error_msg)

        # Determine execution order
        execution_order = self._compute_execution_order(graph)
        logger.debug("Execution order: %s", [n.node_id for n in execution_order])

        # Execute nodes in order
        failed_nodes = []
        completed_nodes = []

        for node in execution_order:
            try:
                # Mark node as ready
                node.status = NodeStatus.READY

                # Collect input values from connections
                self._collect_inputs(node, graph)

                # Validate input values
                validation_errors = self._validate_inputs(node)
                if validation_errors:
                    node.status = NodeStatus.FAILED
                    node.error = f"Input validation failed: {', '.join(validation_errors)}"
                    logger.error("Node %s input validation failed: %s", node.node_id, node.error)
                    failed_nodes.append(node.node_id)
                    continue

                # Execute node
                node.status = NodeStatus.RUNNING
                logger.debug("Executing node: %s (type: %s)", node.node_id, node.node_type)

                # For now, this is a placeholder for actual node execution
                # In the full implementation, this would dispatch to the appropriate worker
                await self._execute_node(node)

                node.status = NodeStatus.COMPLETED
                completed_nodes.append(node.node_id)
                logger.debug("Node %s completed", node.node_id)

            except Exception as e:
                node.status = NodeStatus.FAILED
                node.error = str(e)
                logger.exception("Node %s execution failed", node.node_id)
                failed_nodes.append(node.node_id)

        # Compile results
        result = {
            "graph_id": graph.graph_id,
            "status": "failed" if failed_nodes else "completed",
            "completed_nodes": completed_nodes,
            "failed_nodes": failed_nodes,
            "outputs": self._collect_graph_outputs(graph),
        }

        # Record execution history
        self._execution_history.append(result)

        logger.info(
            "Graph %s execution %s: %d/%d nodes completed",
            graph.graph_id,
            result["status"],
            len(completed_nodes),
            len(graph.nodes),
        )

        return result

    def _validate_graph(self, graph: GraphDefinition) -> dict[str, Any]:
        """Validate graph topology and type compatibility.

        Args:
            graph: Graph to validate

        Returns:
            Validation result with valid flag and errors list
        """
        errors = []

        # Check for duplicate node IDs
        node_ids = [n.node_id for n in graph.nodes]
        if len(node_ids) != len(set(node_ids)):
            errors.append("Duplicate node IDs found")

        # Validate connections
        node_map = {n.node_id: n for n in graph.nodes}
        for conn in graph.connections:
            # Check if source node exists
            if conn.from_node not in node_map:
                errors.append(f"Connection references non-existent source node: {conn.from_node}")
                continue

            # Check if destination node exists
            if conn.to_node not in node_map:
                errors.append(f"Connection references non-existent destination node: {conn.to_node}")
                continue

            # Check if source port exists
            from_node = node_map[conn.from_node]
            from_port = next((p for p in from_node.outputs if p.name == conn.from_port), None)
            if not from_port:
                errors.append(
                    f"Connection references non-existent output port: {conn.from_node}.{conn.from_port}"
                )
                continue

            # Check if destination port exists
            to_node = node_map[conn.to_node]
            to_port = next((p for p in to_node.inputs if p.name == conn.to_port), None)
            if not to_port:
                errors.append(
                    f"Connection references non-existent input port: {conn.to_node}.{conn.to_port}"
                )
                continue

            # Check port type compatibility
            if not from_port.is_compatible_with(to_port):
                errors.append(
                    f"Incompatible port types: {conn.from_node}.{conn.from_port} "
                    f"({from_port.port_type}) -> {conn.to_node}.{conn.to_port} ({to_port.port_type})"
                )

        # Check for cycles (basic cycle detection)
        if self._has_cycles(graph):
            errors.append("Graph contains cycles")

        return {
            "valid": len(errors) == 0,
            "errors": errors,
        }

    def _has_cycles(self, graph: GraphDefinition) -> bool:
        """Check if graph contains cycles using DFS.

        Args:
            graph: Graph to check

        Returns:
            True if cycles are detected, False otherwise
        """
        # Build adjacency list
        adjacency: dict[str, list[str]] = {n.node_id: [] for n in graph.nodes}
        for conn in graph.connections:
            adjacency[conn.from_node].append(conn.to_node)

        # DFS cycle detection
        visited = set()
        rec_stack = set()

        def dfs(node_id: str) -> bool:
            visited.add(node_id)
            rec_stack.add(node_id)

            for neighbor in adjacency.get(node_id, []):
                if neighbor not in visited:
                    if dfs(neighbor):
                        return True
                elif neighbor in rec_stack:
                    return True

            rec_stack.remove(node_id)
            return False

        for node in graph.nodes:
            if node.node_id not in visited:
                if dfs(node.node_id):
                    return True

        return False

    def _compute_execution_order(self, graph: GraphDefinition) -> list[NodeInstance]:
        """Compute topological execution order for nodes.

        Args:
            graph: Graph to compute order for

        Returns:
            List of nodes in execution order
        """
        # Build adjacency list and in-degree map
        adjacency: dict[str, list[str]] = {n.node_id: [] for n in graph.nodes}
        in_degree: dict[str, int] = {n.node_id: 0 for n in graph.nodes}

        for conn in graph.connections:
            adjacency[conn.from_node].append(conn.to_node)
            in_degree[conn.to_node] = in_degree.get(conn.to_node, 0) + 1

        # Topological sort using Kahn's algorithm
        queue = [node_id for node_id, degree in in_degree.items() if degree == 0]
        result = []
        node_map = {n.node_id: n for n in graph.nodes}

        while queue:
            node_id = queue.pop(0)
            result.append(node_map[node_id])

            for neighbor in adjacency.get(node_id, []):
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        return result

    def _collect_inputs(self, node: NodeInstance, graph: GraphDefinition) -> None:
        """Collect input values from connected output ports.

        Args:
            node: Node to collect inputs for
            graph: Graph containing the connections
        """
        # Find all connections that target this node
        for conn in graph.connections:
            if conn.to_node == node.node_id:
                # Find source node
                source_node = next((n for n in graph.nodes if n.node_id == conn.from_node), None)
                if source_node and conn.from_port in source_node.output_values:
                    # Copy value from source output to this input
                    node.input_values[conn.to_port] = source_node.output_values[conn.from_port]

    def _validate_inputs(self, node: NodeInstance) -> list[str]:
        """Validate input values against port definitions.

        Args:
            node: Node to validate inputs for

        Returns:
            List of validation error messages (empty if valid)
        """
        errors = []

        # Get domain types from registry
        domain_types = {dt.full_name: dt for dt in self._registry.list_types()}

        for input_port in node.inputs:
            value = node.input_values.get(input_port.name)

            # Validate value against port type
            is_valid, error_msg = input_port.validate_value(value, domain_types)
            if not is_valid:
                errors.append(f"{input_port.name}: {error_msg}")

        return errors

    async def _execute_node(self, node: NodeInstance) -> None:
        """Execute a single node.

        This is a placeholder for actual node execution. In the full implementation,
        this would dispatch to the appropriate worker based on node_type.

        Args:
            node: Node to execute
        """
        # For now, just log the execution
        # In the full implementation, this would:
        # 1. Extract domain from node_type (e.g., "electronics" from "electronics.spice.simulate")
        # 2. Get the appropriate worker from registry
        # 3. Call the worker's execute method with the node
        logger.debug("Node %s execution (placeholder)", node.node_id)

        # Placeholder: set empty outputs
        for output_port in node.outputs:
            if output_port.name not in node.output_values:
                node.output_values[output_port.name] = None

    def _collect_graph_outputs(self, graph: GraphDefinition) -> dict[str, Any]:
        """Collect all output values from graph nodes.

        Args:
            graph: Graph to collect outputs from

        Returns:
            Dictionary mapping node_id.port_name to output values
        """
        outputs = {}
        for node in graph.nodes:
            for port_name, value in node.output_values.items():
                key = f"{node.node_id}.{port_name}"
                outputs[key] = value
        return outputs

    def get_execution_history(self) -> list[dict[str, Any]]:
        """Get the execution history.

        Returns:
            List of execution results
        """
        return self._execution_history

    def clear_history(self) -> None:
        """Clear the execution history."""
        self._execution_history.clear()

    def __repr__(self) -> str:
        """Return a readable representation of the runtime."""
        return f"GraphRuntime(executions={len(self._execution_history)})"
