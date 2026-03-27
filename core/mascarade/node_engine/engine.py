"""Graph execution engine — topological sort and parallel scheduling.

Extends the Orchestrator's sequential/parallel/pipeline model
to arbitrary DAG execution with domain-aware scheduling.
"""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from mascarade.node_engine.graph import Graph, GraphNode
    from mascarade.node_engine.registry import NodeTypeRegistry, WorkerRegistry

from mascarade.node_engine.runtime import ExecutionMode

logger = logging.getLogger("mascarade.node_engine")


class CycleDetectedError(Exception):
    """Raised when the graph contains a cycle."""


class ValidationError(Exception):
    """Raised when the graph fails static validation."""


@dataclass
class ExecutionContext:
    """Runtime context passed to each node during execution."""

    graph_id: str
    run_id: str
    node_id: str
    config: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    cancel_event: asyncio.Event = field(default_factory=asyncio.Event)

    def is_cancelled(self) -> bool:
        return self.cancel_event.is_set()


@dataclass
class NodeResult:
    """Result from a single node execution."""

    node_id: str
    outputs: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    duration_ms: float = 0.0
    worker_name: str = ""


@dataclass
class GraphExecutionEngine:
    """
    Executes a node graph respecting topological ordering and parallel branches.

    Modeled on Orchestrator (core/mascarade/orchestrator/engine.py) with
    extensions for DAG-aware scheduling, domain-specific worker dispatch,
    and cross-domain type adaptation.
    """

    worker_registry: WorkerRegistry = field(default_factory=lambda: None)
    node_registry: NodeTypeRegistry = field(default_factory=lambda: None)

    def __post_init__(self) -> None:
        """Initialize registries if not provided."""
        if self.worker_registry is None:
            from mascarade.node_engine.registry import WorkerRegistry

            self.worker_registry = WorkerRegistry()
        if self.node_registry is None:
            from mascarade.node_engine.registry import NodeTypeRegistry

            self.node_registry = NodeTypeRegistry()

    def _topological_sort(self, graph: Graph) -> list[list[str]]:
        """
        Compute execution levels via Kahn's algorithm.

        Returns a list of levels, where each level contains node IDs
        that can execute in parallel. Raises CycleDetectedError if
        the graph contains cycles.
        """
        in_degree: dict[str, int] = defaultdict(int)
        adjacency: dict[str, list[str]] = defaultdict(list)

        # Initialize in-degree for all nodes
        for node in graph.nodes:
            in_degree.setdefault(node.id, 0)

        # Build adjacency list and in-degree counts
        for edge in graph.edges:
            adjacency[edge.source_node].append(edge.target_node)
            in_degree[edge.target_node] += 1

        # Start with nodes that have no dependencies
        queue = [nid for nid, deg in in_degree.items() if deg == 0]
        levels: list[list[str]] = []
        processed = 0

        while queue:
            # All nodes in current queue can execute in parallel (same level)
            levels.append(list(queue))
            next_queue: list[str] = []
            for nid in queue:
                processed += 1
                # Reduce in-degree for neighbors
                for neighbor in adjacency[nid]:
                    in_degree[neighbor] -= 1
                    if in_degree[neighbor] == 0:
                        next_queue.append(neighbor)
            queue = next_queue

        # If not all nodes were processed, there's a cycle
        if processed != len(graph.nodes):
            raise CycleDetectedError(
                f"Graph contains a cycle: processed {processed}/{len(graph.nodes)} nodes"
            )

        return levels

    def _find_required_nodes(self, graph: Graph, target_node_ids: set[str]) -> set[str]:
        """Trace backwards from target nodes to find all required upstream nodes.

        Args:
            graph: Graph to analyze
            target_node_ids: Set of node IDs whose outputs are needed

        Returns:
            Set of node IDs that must be executed.
        """
        required: set[str] = set()
        worklist = list(target_node_ids)

        # Build reverse adjacency for fast lookup
        reverse_adj: dict[str, list[str]] = defaultdict(list)
        for edge in graph.edges:
            reverse_adj[edge.target_node].append(edge.source_node)

        while worklist:
            node_id = worklist.pop()
            if node_id in required:
                continue
            required.add(node_id)
            for upstream in reverse_adj.get(node_id, []):
                if upstream not in required:
                    worklist.append(upstream)

        return required

    def _find_sink_nodes(self, graph: Graph) -> set[str]:
        """Find sink nodes (nodes with no outgoing edges)."""
        has_outgoing: set[str] = set()
        for edge in graph.edges:
            has_outgoing.add(edge.source_node)

        all_ids = {n.id for n in graph.nodes}
        return all_ids - has_outgoing

    async def execute(
        self,
        graph: Graph,
        run_id: str,
        *,
        mode: ExecutionMode = ExecutionMode.EAGER,
        target_nodes: set[str] | None = None,
    ) -> list[NodeResult]:
        """Execute a graph respecting topological ordering.

        Args:
            graph: Graph to execute
            run_id: Unique run identifier
            mode: Execution mode. EAGER (default) parallelizes within levels,
                  LAZY only executes nodes required by target/sink nodes,
                  STEPPED executes sequentially one node at a time.
            target_nodes: Optional target nodes for LAZY mode. If None,
                          sink nodes are used.

        Returns:
            List of NodeResult for each executed node.
        """
        levels = self._topological_sort(graph)
        all_results: list[NodeResult] = []
        port_data: dict[str, dict[str, Any]] = {}

        # For LAZY mode, determine required node set
        required_nodes: set[str] | None = None
        if mode == ExecutionMode.LAZY:
            targets = target_nodes or self._find_sink_nodes(graph)
            required_nodes = self._find_required_nodes(graph, targets)
            logger.info(
                "Lazy mode: %d/%d nodes required (targets: %s)",
                len(required_nodes),
                len(graph.nodes),
                ", ".join(sorted(targets)),
            )

        for level in levels:
            # Filter level to required nodes if in lazy mode
            level_ids = level
            if required_nodes is not None:
                level_ids = [nid for nid in level if nid in required_nodes]
                if not level_ids:
                    continue

            if mode == ExecutionMode.STEPPED:
                # Sequential: one node at a time within each level
                for node_id in level_ids:
                    node = next(n for n in graph.nodes if n.id == node_id)
                    inputs = self._collect_inputs(graph, node_id, port_data)
                    ctx = ExecutionContext(
                        graph_id=graph.id,
                        run_id=run_id,
                        node_id=node_id,
                        config=node.config,
                    )
                    result = await self._execute_node(node, inputs, ctx)
                    all_results.append(result)
                    port_data[result.node_id] = result.outputs
            else:
                # EAGER and LAZY: parallelize within levels
                tasks = []
                node_ids = []
                for node_id in level_ids:
                    node = next(n for n in graph.nodes if n.id == node_id)
                    inputs = self._collect_inputs(graph, node_id, port_data)
                    ctx = ExecutionContext(
                        graph_id=graph.id,
                        run_id=run_id,
                        node_id=node_id,
                        config=node.config,
                    )
                    tasks.append(self._execute_node(node, inputs, ctx))
                    node_ids.append(node_id)

                results = await asyncio.gather(*tasks, return_exceptions=True)

                for i, result in enumerate(results):
                    if isinstance(result, Exception):
                        logger.error("Unexpected exception for node %s: %s", node_ids[i], result)
                        all_results.append(NodeResult(node_id=node_ids[i], error=str(result)))
                    else:
                        all_results.append(result)
                        port_data[result.node_id] = result.outputs

        return all_results

    async def execute_stepped(
        self,
        graph: Graph,
        run_id: str,
        *,
        mode: ExecutionMode = ExecutionMode.EAGER,
        target_nodes: set[str] | None = None,
    ) -> AsyncIterator[NodeResult]:
        """Execute a graph one node at a time, yielding after each step.

        Yields NodeResult after each node execution, giving the caller
        control over pacing. Useful for debugging UIs and step-through.

        Args:
            graph: Graph to execute
            run_id: Unique run identifier
            mode: EAGER or LAZY (controls which nodes are included)
            target_nodes: Optional target nodes for LAZY filtering

        Yields:
            NodeResult after each node execution
        """
        levels = self._topological_sort(graph)
        port_data: dict[str, dict[str, Any]] = {}

        # For LAZY mode, determine required node set
        required_nodes: set[str] | None = None
        if mode == ExecutionMode.LAZY:
            targets = target_nodes or self._find_sink_nodes(graph)
            required_nodes = self._find_required_nodes(graph, targets)

        for level in levels:
            level_ids = level
            if required_nodes is not None:
                level_ids = [nid for nid in level if nid in required_nodes]

            for node_id in level_ids:
                node = next(n for n in graph.nodes if n.id == node_id)
                inputs = self._collect_inputs(graph, node_id, port_data)
                ctx = ExecutionContext(
                    graph_id=graph.id,
                    run_id=run_id,
                    node_id=node_id,
                    config=node.config,
                )
                result = await self._execute_node(node, inputs, ctx)
                port_data[result.node_id] = result.outputs
                yield result

    def _collect_inputs(
        self, graph: Graph, node_id: str, port_data: dict[str, dict[str, Any]]
    ) -> dict[str, Any]:
        """Gather input values from upstream node outputs."""
        inputs: dict[str, Any] = {}
        for edge in graph.edges:
            if edge.target_node == node_id:
                source_outputs = port_data.get(edge.source_node, {})
                if edge.source_port in source_outputs:
                    inputs[edge.target_port] = source_outputs[edge.source_port]
        return inputs

    async def _execute_node(
        self, node: GraphNode, inputs: dict[str, Any], ctx: ExecutionContext
    ) -> NodeResult:
        """Execute a single node using its registered worker."""
        import time

        start = time.monotonic()
        node_type = self.node_registry.get(node.node_type)
        worker = self.worker_registry.get(node_type.domain)

        try:
            outputs = await worker.execute(
                node_type=node.node_type,
                inputs=inputs,
                config=node.config,
                context=ctx,
            )
            duration = (time.monotonic() - start) * 1000
            return NodeResult(
                node_id=node.id,
                outputs=outputs,
                duration_ms=duration,
                worker_name=worker.name,
            )
        except Exception as exc:
            duration = (time.monotonic() - start) * 1000
            logger.error("Node %s failed: %s", node.id, exc)
            return NodeResult(
                node_id=node.id,
                error=str(exc),
                duration_ms=duration,
                worker_name=worker.name,
            )
