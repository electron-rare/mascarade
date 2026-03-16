"""Graph runtime for executing node graphs.

Executes graphs in topological order, resolving dependencies and dispatching
nodes to domain workers.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from mascarade.node_engine.graph import Graph
from mascarade.node_engine.worker import NodeWorker

logger = logging.getLogger("mascarade.node_engine")


class ExecutionStatus(StrEnum):
    """Execution status for graph runs."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class NodeResult:
    """Result of a single node execution.

    Captures outputs, errors, and metadata for a single node execution.
    """

    node_id: str
    status: ExecutionStatus
    outputs: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    worker_name: str | None = None
    execution_time_ms: float | None = None


@dataclass
class GraphExecutionContext:
    """Execution context for a graph run.

    Tracks state and results across the entire graph execution.
    """

    graph_id: str
    status: ExecutionStatus = ExecutionStatus.PENDING
    node_results: dict[str, NodeResult] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class GraphRuntime:
    """Runtime for executing node graphs.

    Orchestrates graph execution by:
    1. Validating the graph structure and node inputs
    2. Computing topological execution order
    3. Resolving edge-connected inputs from previous node outputs
    4. Dispatching nodes to appropriate domain workers
    5. Tracking execution state and results

    Example:
        >>> from mascarade.node_engine.workers.ai.worker import AIWorker
        >>> from mascarade.router import Router
        >>> from mascarade.agents.registry import AgentRegistry
        >>>
        >>> runtime = GraphRuntime()
        >>> ai_worker = AIWorker(router=Router(), registry=AgentRegistry())
        >>> runtime.register_worker(ai_worker)
        >>>
        >>> graph = Graph(nodes=[...], edges=[...])
        >>> context = await runtime.execute(graph)
    """

    workers: dict[str, NodeWorker] = field(default_factory=dict)
    max_concurrent: int = field(default=10)
    execution_timeout_s: float = field(default=300.0)

    def register_worker(self, worker: NodeWorker) -> None:
        """Register a domain worker with the runtime.

        Args:
            worker: NodeWorker instance to register

        Raises:
            ValueError: If a worker for this domain is already registered
        """
        if worker.domain in self.workers:
            logger.warning(
                "Overwriting existing worker for domain '%s': %s -> %s",
                worker.domain,
                self.workers[worker.domain].name,
                worker.name,
            )
        self.workers[worker.domain] = worker
        logger.info(
            "Registered worker '%s' for domain '%s'",
            worker.name,
            worker.domain,
        )

    def get_worker(self, domain: str) -> NodeWorker | None:
        """Get the worker for a specific domain.

        Args:
            domain: Domain identifier (e.g., "ai", "cad")

        Returns:
            NodeWorker instance if registered, None otherwise
        """
        return self.workers.get(domain)

    async def validate_graph(self, graph: Graph) -> list[str]:
        """Validate graph before execution.

        Checks:
        - Graph structure (DAG constraint, edge validity) — handled by Graph model
        - All referenced node types have registered workers
        - Node inputs pass worker-specific validation

        Args:
            graph: Graph to validate

        Returns:
            List of validation error messages. Empty if validation passes.
        """
        errors: list[str] = []

        # Validate that all node types have registered workers
        for node in graph.nodes:
            domain = node.domain
            worker = self.get_worker(domain)

            if worker is None:
                errors.append(
                    f"Node '{node.id}' has type '{node.type}' but no worker registered for domain '{domain}'"
                )
                continue

            # Check if worker is available
            if not worker.is_available:
                errors.append(
                    f"Node '{node.id}' requires worker '{worker.name}' but it is not available"
                )
                continue

            # Check if worker supports this node type
            capabilities = worker.capabilities()
            node_types = capabilities.get("node_types", [])
            if node.type not in node_types:
                errors.append(
                    f"Node '{node.id}' has type '{node.type}' but worker '{worker.name}' "
                    f"does not support it (supports: {', '.join(node_types)})"
                )
                continue

            # Delegate to worker-specific validation
            try:
                validation_errors = await worker.validate(
                    node.type,
                    node.inputs,
                    node.config,
                )
                for error in validation_errors:
                    errors.append(f"Node '{node.id}': {error}")
            except Exception as exc:
                errors.append(
                    f"Node '{node.id}': validation failed with exception: {exc}"
                )

        return errors

    async def execute(
        self,
        graph: Graph,
        *,
        initial_inputs: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> GraphExecutionContext:
        """Execute a graph.

        Args:
            graph: Graph to execute
            initial_inputs: Optional initial inputs for the graph (injected into first nodes)
            metadata: Optional metadata to attach to the execution context

        Returns:
            GraphExecutionContext with execution results

        Raises:
            ValueError: If graph validation fails
            RuntimeError: If execution fails
        """
        # Validate graph
        validation_errors = await self.validate_graph(graph)
        if validation_errors:
            error_msg = "Graph validation failed:\n" + "\n".join(
                f"  - {e}" for e in validation_errors
            )
            raise ValueError(error_msg)

        # Initialize execution context
        context = GraphExecutionContext(
            graph_id=graph.metadata.get("id", "unknown"),
            status=ExecutionStatus.RUNNING,
            metadata=metadata or {},
        )

        logger.info(
            "Starting graph execution: %s (%d nodes, %d edges)",
            context.graph_id,
            graph.node_count,
            graph.edge_count,
        )

        try:
            # Get topological execution order
            execution_order = graph.topological_sort()

            # Storage for node outputs (used to resolve edge connections)
            node_outputs: dict[str, dict[str, Any]] = {}

            # Execute nodes in order
            for node in execution_order:
                logger.debug("Executing node: %s (type: %s)", node.id, node.type)

                # Resolve inputs from edges
                resolved_inputs = dict(node.inputs)  # Start with literal inputs

                # Override with edge-connected inputs
                incoming_edges = graph.get_incoming_edges(node.id)
                for edge in incoming_edges:
                    # Get output from source node
                    if edge.from_node not in node_outputs:
                        raise RuntimeError(
                            f"Node '{node.id}' depends on '{edge.from_node}' "
                            f"but it has not been executed yet (execution order bug)"
                        )

                    source_outputs = node_outputs[edge.from_node]
                    if edge.from_port not in source_outputs:
                        raise RuntimeError(
                            f"Node '{node.id}' expects input from "
                            f"'{edge.from_node}.{edge.from_port}' but that port "
                            f"did not produce an output (available: {list(source_outputs.keys())})"
                        )

                    # Connect source output to destination input
                    resolved_inputs[edge.to_port] = source_outputs[edge.from_port]

                # Get worker for this node's domain
                worker = self.get_worker(node.domain)
                if worker is None:
                    raise RuntimeError(
                        f"No worker registered for domain '{node.domain}' (node: {node.id})"
                    )

                # Execute node
                import time

                start_time = time.perf_counter()
                try:
                    outputs = await worker.execute(
                        node.type,
                        resolved_inputs,
                        node.config,
                        context,
                    )
                    execution_time_ms = (time.perf_counter() - start_time) * 1000

                    # Store outputs for edge resolution
                    node_outputs[node.id] = outputs

                    # Record result
                    context.node_results[node.id] = NodeResult(
                        node_id=node.id,
                        status=ExecutionStatus.COMPLETED,
                        outputs=outputs,
                        worker_name=worker.name,
                        execution_time_ms=execution_time_ms,
                    )

                    logger.debug(
                        "Node '%s' completed in %.2fms",
                        node.id,
                        execution_time_ms,
                    )

                except Exception as exc:
                    execution_time_ms = (time.perf_counter() - start_time) * 1000
                    error_msg = f"{type(exc).__name__}: {exc}"

                    context.node_results[node.id] = NodeResult(
                        node_id=node.id,
                        status=ExecutionStatus.FAILED,
                        error=error_msg,
                        worker_name=worker.name,
                        execution_time_ms=execution_time_ms,
                    )

                    logger.error(
                        "Node '%s' failed after %.2fms: %s",
                        node.id,
                        execution_time_ms,
                        error_msg,
                    )

                    # Fail fast — stop execution on first error
                    context.status = ExecutionStatus.FAILED
                    return context

            # All nodes completed successfully
            context.status = ExecutionStatus.COMPLETED
            logger.info("Graph execution completed: %s", context.graph_id)

        except Exception as exc:
            logger.error("Graph execution failed: %s", exc, exc_info=True)
            context.status = ExecutionStatus.FAILED
            raise RuntimeError(f"Graph execution failed: {exc}") from exc

        return context

    async def execute_node(
        self,
        node_type: str,
        inputs: dict[str, Any],
        config: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Execute a single node without a graph.

        Convenience method for executing a single node in isolation.
        Useful for testing or simple workflows.

        Args:
            node_type: Fully qualified node type (e.g., "ai.llm-inference")
            inputs: Input port values
            config: Optional node configuration

        Returns:
            Output port values

        Raises:
            ValueError: If node type is not supported
            RuntimeError: If execution fails
        """
        # Extract domain from node type
        if "." not in node_type:
            raise ValueError(
                f"Invalid node type '{node_type}' — must be fully qualified (domain.typename)"
            )

        domain = node_type.split(".")[0]
        worker = self.get_worker(domain)

        if worker is None:
            raise ValueError(
                f"No worker registered for domain '{domain}' (available: {list(self.workers.keys())})"
            )

        # Validate inputs
        validation_errors = await worker.validate(
            node_type,
            inputs,
            config or {},
        )
        if validation_errors:
            raise ValueError(
                f"Node validation failed:\n" + "\n".join(f"  - {e}" for e in validation_errors)
            )

        # Execute
        context = GraphExecutionContext(
            graph_id="single-node",
            status=ExecutionStatus.RUNNING,
        )

        return await worker.execute(
            node_type,
            inputs,
            config or {},
            context,
        )

    def list_workers(self) -> list[dict[str, Any]]:
        """List all registered workers with their capabilities.

        Returns:
            List of worker metadata dictionaries
        """
        result = []
        for domain, worker in self.workers.items():
            capabilities = worker.capabilities()
            result.append(
                {
                    "domain": domain,
                    "name": worker.name,
                    "is_available": worker.is_available,
                    "capabilities": capabilities,
                }
            )
        return result
