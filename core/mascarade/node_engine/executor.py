"""Graph execution runtime for the Universal Node Engine.

The GraphExecutor executes graphs by:
1. Topologically sorting nodes
2. Executing nodes in dependency order
3. Passing outputs to connected inputs
4. Handling errors and timeouts
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from mascarade.node_engine.base import (
    NodeDefinition,
    NodeExecutionContext,
    NodeExecutionResult,
    NodeWorker,
)
from mascarade.node_engine.graph import Graph, GraphValidator

logger = logging.getLogger("mascarade.node_engine")


class ExecutionStatus(StrEnum):
    """Status of a graph execution."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"


@dataclass
class NodeExecutionRecord:
    """Record of a single node execution within a graph run.

    Tracks:
    - Node instance ID
    - Execution status
    - Inputs provided
    - Outputs produced
    - Errors encountered
    - Timing information
    """

    node_id: str
    node_type: str
    status: ExecutionStatus = ExecutionStatus.PENDING
    inputs: dict[str, Any] = field(default_factory=dict)
    outputs: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    error_type: str | None = None
    start_time_ms: int = 0
    end_time_ms: int = 0
    execution_time_ms: int = 0


@dataclass
class GraphExecutionResult:
    """Result of a graph execution.

    Contains:
    - Overall status
    - Per-node execution records
    - Final outputs (from terminal nodes)
    - Timing information
    """

    graph_id: str
    status: ExecutionStatus
    node_records: list[NodeExecutionRecord] = field(default_factory=list)
    outputs: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    start_time_ms: int = 0
    end_time_ms: int = 0
    total_time_ms: int = 0

    def get_node_record(self, node_id: str) -> NodeExecutionRecord | None:
        """Get execution record for a specific node.

        Args:
            node_id: Node instance ID

        Returns:
            NodeExecutionRecord if found, None otherwise
        """
        for record in self.node_records:
            if record.node_id == node_id:
                return record
        return None


class GraphExecutor:
    """Executes node graphs asynchronously.

    The executor:
    - Validates graphs before execution
    - Resolves node dependencies via topological sort
    - Executes nodes in parallel where possible
    - Routes data through connections
    - Handles errors and timeouts
    - Enforces capability grants
    """

    def __init__(self) -> None:
        """Initialize the graph executor."""
        self._workers: dict[str, NodeWorker] = {}
        self._node_definitions: dict[str, NodeDefinition] = {}
        self._validator = GraphValidator()

    def register_worker(self, worker: NodeWorker) -> None:
        """Register a node worker with the executor.

        Args:
            worker: NodeWorker instance to register
        """
        self._workers[worker.domain] = worker

        # Register node definitions from this worker
        for node_def in worker.register_nodes():
            self._node_definitions[node_def.node_type] = node_def
            logger.debug(
                "Registered node type: %s (domain: %s)", node_def.node_type, worker.domain
            )

    async def initialize_workers(self) -> None:
        """Initialize all registered workers."""
        for domain, worker in self._workers.items():
            try:
                await worker.initialize()
                logger.info("Initialized worker: %s", domain)
            except Exception as e:
                logger.error("Failed to initialize worker %s: %s", domain, e)
                raise

    async def shutdown_workers(self) -> None:
        """Shutdown all registered workers."""
        for domain, worker in self._workers.items():
            try:
                await worker.shutdown()
                logger.info("Shutdown worker: %s", domain)
            except Exception as e:
                logger.warning("Error shutting down worker %s: %s", domain, e)

    def validate_graph(self, graph: Graph) -> list[str]:
        """Validate a graph before execution.

        Args:
            graph: Graph to validate

        Returns:
            List of validation errors (empty if valid)
        """
        return self._validator.validate(graph, self._node_definitions)

    async def execute_graph(
        self,
        graph: Graph,
        *,
        capabilities: set[str] | None = None,
        timeout_seconds: float = 120.0,
    ) -> GraphExecutionResult:
        """Execute a graph asynchronously.

        Args:
            graph: Graph to execute
            capabilities: Set of granted capabilities for this execution
            timeout_seconds: Maximum execution time in seconds

        Returns:
            GraphExecutionResult with execution status and outputs

        Raises:
            ValueError: If graph validation fails
            asyncio.TimeoutError: If execution exceeds timeout
        """
        loop = asyncio.get_event_loop()
        start_time_ms = int(loop.time() * 1000)

        # Validate graph
        validation_errors = self.validate_graph(graph)
        if validation_errors:
            error_msg = "; ".join(validation_errors)
            logger.error("Graph validation failed: %s", error_msg)
            return GraphExecutionResult(
                graph_id=graph.graph_id,
                status=ExecutionStatus.FAILED,
                error=f"Validation failed: {error_msg}",
                start_time_ms=start_time_ms,
                end_time_ms=int(loop.time() * 1000),
                total_time_ms=int(loop.time() * 1000) - start_time_ms,
            )

        logger.info("Executing graph: %s (%d nodes)", graph.graph_id, len(graph.nodes))

        # Initialize execution result
        result = GraphExecutionResult(
            graph_id=graph.graph_id,
            status=ExecutionStatus.RUNNING,
            start_time_ms=start_time_ms,
        )

        # Create node execution records
        node_records: dict[str, NodeExecutionRecord] = {}
        for node in graph.nodes:
            record = NodeExecutionRecord(
                node_id=node.node_id,
                node_type=node.node_type,
                status=ExecutionStatus.PENDING,
            )
            node_records[node.node_id] = record
            result.node_records.append(record)

        try:
            # Execute with timeout
            await asyncio.wait_for(
                self._execute_graph_internal(
                    graph, result, node_records, capabilities or set()
                ),
                timeout=timeout_seconds,
            )
            result.status = ExecutionStatus.COMPLETED
        except asyncio.TimeoutError:
            result.status = ExecutionStatus.TIMEOUT
            result.error = f"Graph execution timed out after {timeout_seconds}s"
            logger.error("Graph %s execution timeout", graph.graph_id)
        except Exception as e:
            result.status = ExecutionStatus.FAILED
            result.error = str(e)
            logger.error("Graph %s execution failed: %s", graph.graph_id, e)

        end_time_ms = int(loop.time() * 1000)
        result.end_time_ms = end_time_ms
        result.total_time_ms = end_time_ms - start_time_ms

        logger.info(
            "Graph %s execution %s (%.2fs)",
            graph.graph_id,
            result.status,
            result.total_time_ms / 1000.0,
        )

        return result

    async def _execute_graph_internal(
        self,
        graph: Graph,
        result: GraphExecutionResult,
        node_records: dict[str, NodeExecutionRecord],
        capabilities: set[str],
    ) -> None:
        """Internal graph execution logic.

        Args:
            graph: Graph to execute
            result: Result object to populate
            node_records: Mapping of node ID to execution record
            capabilities: Granted capabilities
        """
        loop = asyncio.get_event_loop()

        # Topologically sort nodes
        sorted_nodes = self._topological_sort(graph)
        logger.debug("Execution order: %s", [node.node_id for node in sorted_nodes])

        # Storage for node outputs
        node_outputs: dict[str, dict[str, Any]] = {}

        # Execute nodes in order
        for node_instance in sorted_nodes:
            record = node_records[node_instance.node_id]
            record.status = ExecutionStatus.RUNNING
            record.start_time_ms = int(loop.time() * 1000)

            try:
                # Get node definition
                node_def = self._node_definitions[node_instance.node_type]

                # Get worker for this node's domain
                domain = node_instance.node_type.split(".")[0]
                worker = self._workers.get(domain)
                if worker is None:
                    raise RuntimeError(f"No worker registered for domain: {domain}")

                # Collect inputs for this node
                inputs = self._collect_node_inputs(
                    graph, node_instance, node_outputs, node_def
                )
                record.inputs = inputs.copy()

                # Create execution context
                context = NodeExecutionContext(
                    node_id=node_instance.node_id,
                    graph_id=graph.graph_id,
                    inputs=inputs,
                    config=node_instance.config,
                    capabilities=capabilities,
                    metadata=node_instance.metadata,
                )

                # Execute node
                logger.debug("Executing node: %s (%s)", node_instance.node_id, node_def.node_type)
                exec_result = await worker.execute_node(node_def, context)

                if exec_result.success:
                    record.status = ExecutionStatus.COMPLETED
                    record.outputs = exec_result.outputs.copy()
                    node_outputs[node_instance.node_id] = exec_result.outputs
                    logger.debug(
                        "Node %s completed with outputs: %s",
                        node_instance.node_id,
                        list(exec_result.outputs.keys()),
                    )
                else:
                    record.status = ExecutionStatus.FAILED
                    record.error = exec_result.error
                    record.error_type = exec_result.error_type
                    logger.error(
                        "Node %s failed: %s", node_instance.node_id, exec_result.error
                    )
                    # Propagate failure
                    raise RuntimeError(
                        f"Node {node_instance.node_id} failed: {exec_result.error}"
                    )

            except Exception as e:
                record.status = ExecutionStatus.FAILED
                record.error = str(e)
                record.error_type = type(e).__name__
                logger.error("Node %s execution error: %s", node_instance.node_id, e)
                raise

            finally:
                record.end_time_ms = int(loop.time() * 1000)
                record.execution_time_ms = record.end_time_ms - record.start_time_ms

        # Collect final outputs from terminal nodes (nodes with no outgoing connections)
        terminal_nodes = [
            node for node in graph.nodes if not graph.get_connections_from_node(node.node_id)
        ]
        for node in terminal_nodes:
            if node.node_id in node_outputs:
                result.outputs[node.node_id] = node_outputs[node.node_id]

    def _collect_node_inputs(
        self,
        graph: Graph,
        node_instance: Any,
        node_outputs: dict[str, dict[str, Any]],
        node_def: NodeDefinition,
    ) -> dict[str, Any]:
        """Collect input values for a node from connected outputs and config defaults.

        Args:
            graph: The graph being executed
            node_instance: Node instance to collect inputs for
            node_outputs: Map of node ID to output values
            node_def: Node definition

        Returns:
            Dictionary of input port names to values
        """
        inputs: dict[str, Any] = {}

        # Collect inputs from connections
        for conn in graph.get_connections_to_node(node_instance.node_id):
            if conn.source_node_id in node_outputs:
                source_outputs = node_outputs[conn.source_node_id]
                if conn.source_port in source_outputs:
                    inputs[conn.target_port] = source_outputs[conn.source_port]

        # Add config defaults for missing inputs
        for input_port in node_def.input_ports:
            if input_port.name not in inputs:
                # Check node config
                if input_port.name in node_instance.config:
                    inputs[input_port.name] = node_instance.config[input_port.name]
                # Check port default
                elif input_port.default_value is not None:
                    inputs[input_port.name] = input_port.default_value

        return inputs

    def _topological_sort(self, graph: Graph) -> list[Any]:
        """Topologically sort nodes for execution order.

        Uses Kahn's algorithm to produce a topological ordering.

        Args:
            graph: Graph to sort

        Returns:
            List of NodeInstance objects in execution order

        Raises:
            RuntimeError: If graph contains cycles (should be caught by validator)
        """
        # Calculate in-degree for each node
        in_degree: dict[str, int] = {node.node_id: 0 for node in graph.nodes}
        for conn in graph.connections:
            in_degree[conn.target_node_id] += 1

        # Queue of nodes with no incoming edges
        queue: list[str] = [
            node_id for node_id, degree in in_degree.items() if degree == 0
        ]
        sorted_nodes: list[Any] = []

        while queue:
            # Pop node with no dependencies
            node_id = queue.pop(0)
            node = graph.get_node(node_id)
            sorted_nodes.append(node)

            # Reduce in-degree for downstream nodes
            for conn in graph.get_connections_from_node(node_id):
                in_degree[conn.target_node_id] -= 1
                if in_degree[conn.target_node_id] == 0:
                    queue.append(conn.target_node_id)

        if len(sorted_nodes) != len(graph.nodes):
            raise RuntimeError(
                "Graph contains cycles - topological sort failed "
                "(this should have been caught by validation)"
            )

        return sorted_nodes
