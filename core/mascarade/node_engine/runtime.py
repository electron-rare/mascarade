"""Graph runtime for executing node graphs.

Executes graphs in topological order, resolving dependencies and dispatching
nodes to domain workers.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from mascarade.node_engine.graph import Graph
from mascarade.node_engine.worker import NodeWorker

logger = logging.getLogger("mascarade.node_engine")


class ExecutionMode(StrEnum):
    """Execution mode for graph runs.

    EAGER:   Execute all nodes as fast as possible, running parallel branches
             concurrently. This is the default behavior.
    LAZY:    Only execute nodes whose outputs are actually needed. Traces
             backwards from output (sink) nodes to determine the minimal
             required execution set.
    STEPPED: Execute one node at a time, yielding control after each step.
             Returns an async iterator of (NodeResult, GraphExecutionContext)
             pairs for debugging and UI integration.
    """

    EAGER = "eager"
    LAZY = "lazy"
    STEPPED = "stepped"


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

            # Build effective inputs: explicit inputs + ports that will be
            # filled by incoming edges (so validation doesn't flag them as missing).
            effective_inputs = dict(node.inputs)
            for edge in graph.edges:
                if edge.to_node == node.id:
                    effective_inputs.setdefault(edge.to_port, "__edge__")

            # Delegate to worker-specific validation
            try:
                validation_errors = await worker.validate(
                    node.type,
                    effective_inputs,
                    node.config,
                )
                for error in validation_errors:
                    errors.append(f"Node '{node.id}': {error}")
            except Exception as exc:
                errors.append(f"Node '{node.id}': validation failed with exception: {exc}")

        return errors

    def _find_required_nodes(self, graph: Graph, target_node_ids: set[str]) -> set[str]:
        """Trace backwards from target nodes to find all required upstream nodes.

        Used by lazy execution to determine the minimal execution set.

        Args:
            graph: Graph to analyze
            target_node_ids: Set of node IDs whose outputs are needed

        Returns:
            Set of node IDs that must be executed (includes targets and all
            transitive dependencies).
        """
        required: set[str] = set()
        worklist = list(target_node_ids)

        while worklist:
            node_id = worklist.pop()
            if node_id in required:
                continue
            required.add(node_id)

            # Walk backwards through incoming edges
            incoming = graph.get_incoming_edges(node_id)
            for edge in incoming:
                source = getattr(edge, "from_node", None) or getattr(edge, "source_node", "")
                if source and source not in required:
                    worklist.append(source)

        return required

    def _find_sink_nodes(self, graph: Graph) -> set[str]:
        """Find output (sink) nodes -- nodes with no outgoing edges.

        These are the nodes whose outputs are the final results of the graph.
        """
        sink_nodes: set[str] = set()
        for node in graph.nodes:
            nid = getattr(node, "id", getattr(node, "node_id", ""))
            outgoing = graph.get_outgoing_edges(nid)
            if not outgoing:
                sink_nodes.add(nid)
        return sink_nodes

    async def _execute_node_in_graph(
        self,
        node: Any,
        graph: Graph,
        node_outputs: dict[str, dict[str, Any]],
        context: GraphExecutionContext,
    ) -> NodeResult:
        """Execute a single node within a graph, resolving edge inputs.

        Shared logic used by all three execution modes.

        Args:
            node: The node to execute (Pydantic Node model)
            graph: The full graph (for edge resolution)
            node_outputs: Accumulated outputs from previously executed nodes
            context: Current execution context

        Returns:
            NodeResult for this node

        Raises:
            RuntimeError: If a dependency has not been executed or a port is missing
        """
        import time

        logger.debug("Executing node: %s (type: %s)", node.id, node.type)

        # Resolve inputs from edges
        resolved_inputs = dict(node.inputs)  # Start with literal inputs

        # Override with edge-connected inputs
        incoming_edges = graph.get_incoming_edges(node.id)
        for edge in incoming_edges:
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

            resolved_inputs[edge.to_port] = source_outputs[edge.from_port]

        # Get worker for this node's domain
        worker = self.get_worker(node.domain)
        if worker is None:
            raise RuntimeError(
                f"No worker registered for domain '{node.domain}' (node: {node.id})"
            )

        # Execute node
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

            result = NodeResult(
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
            return result

        except Exception as exc:
            execution_time_ms = (time.perf_counter() - start_time) * 1000
            error_msg = f"{type(exc).__name__}: {exc}"

            result = NodeResult(
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
            return result

    async def execute(
        self,
        graph: Graph,
        *,
        initial_inputs: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
        mode: ExecutionMode = ExecutionMode.EAGER,
        target_nodes: set[str] | None = None,
    ) -> GraphExecutionContext:
        """Execute a graph.

        Args:
            graph: Graph to execute
            initial_inputs: Optional initial inputs for the graph (injected into first nodes)
            metadata: Optional metadata to attach to the execution context
            mode: Execution mode (EAGER, LAZY, or STEPPED). Defaults to EAGER.
                  For STEPPED mode, prefer ``execute_stepped()`` which returns an
                  async iterator. When called here with STEPPED, it runs to
                  completion without yielding.
            target_nodes: Optional set of node IDs whose outputs are needed.
                          Used with LAZY mode to specify demand. If None in LAZY
                          mode, sink nodes (no outgoing edges) are used.

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
            "Starting graph execution: %s (%d nodes, %d edges, mode=%s)",
            context.graph_id,
            graph.node_count,
            graph.edge_count,
            mode,
        )

        try:
            # Get topological execution order
            execution_order = graph.topological_sort()

            # For LAZY mode, filter to only required nodes
            if mode == ExecutionMode.LAZY:
                targets = target_nodes or self._find_sink_nodes(graph)
                required = self._find_required_nodes(graph, targets)
                original_count = len(execution_order)
                execution_order = [n for n in execution_order if n.id in required]
                logger.info(
                    "Lazy mode: executing %d/%d nodes (targets: %s)",
                    len(execution_order),
                    original_count,
                    ", ".join(sorted(targets)),
                )

            # Storage for node outputs (used to resolve edge connections)
            node_outputs: dict[str, dict[str, Any]] = {}

            # Execute nodes in order
            for node in execution_order:
                result = await self._execute_node_in_graph(
                    node, graph, node_outputs, context
                )
                context.node_results[node.id] = result

                if result.status == ExecutionStatus.FAILED:
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

    async def execute_stepped(
        self,
        graph: Graph,
        *,
        initial_inputs: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
        mode: ExecutionMode = ExecutionMode.EAGER,
        target_nodes: set[str] | None = None,
    ) -> AsyncIterator[tuple[NodeResult, GraphExecutionContext]]:
        """Execute a graph one node at a time, yielding after each step.

        This is the primary interface for STEPPED execution. It returns an
        async iterator that yields a ``(NodeResult, GraphExecutionContext)``
        pair after each node completes, giving the caller full control over
        pacing (useful for debugging UIs, breakpoints, and step-through).

        The caller can stop iteration early to cancel remaining execution.

        Works with any mode: in LAZY mode, only required nodes are yielded.
        In EAGER mode, all nodes are yielded in topological order.

        Args:
            graph: Graph to execute
            initial_inputs: Optional initial inputs
            metadata: Optional metadata
            mode: Execution mode (EAGER or LAZY — controls which nodes run).
                  STEPPED is implied by using this method.
            target_nodes: Optional target nodes for LAZY filtering

        Yields:
            Tuple of (NodeResult, GraphExecutionContext) after each node

        Raises:
            ValueError: If graph validation fails
            RuntimeError: If a node dependency is missing

        Example:
            >>> async for result, ctx in runtime.execute_stepped(graph):
            ...     print(f"Node {result.node_id}: {result.status}")
            ...     if result.status == ExecutionStatus.FAILED:
            ...         break  # Stop on first failure
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
            "Starting stepped graph execution: %s (%d nodes, %d edges)",
            context.graph_id,
            graph.node_count,
            graph.edge_count,
        )

        # Get topological execution order
        execution_order = graph.topological_sort()

        # For LAZY filtering, reduce to required nodes
        if mode == ExecutionMode.LAZY:
            targets = target_nodes or self._find_sink_nodes(graph)
            required = self._find_required_nodes(graph, targets)
            execution_order = [n for n in execution_order if n.id in required]

        node_outputs: dict[str, dict[str, Any]] = {}

        for node in execution_order:
            result = await self._execute_node_in_graph(
                node, graph, node_outputs, context
            )
            context.node_results[node.id] = result

            if result.status == ExecutionStatus.FAILED:
                context.status = ExecutionStatus.FAILED
                yield result, context
                return

            yield result, context

        context.status = ExecutionStatus.COMPLETED
        logger.info("Stepped graph execution completed: %s", context.graph_id)

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
                "Node validation failed:\n" + "\n".join(f"  - {e}" for e in validation_errors)
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
