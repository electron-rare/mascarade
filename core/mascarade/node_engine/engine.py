"""Graph execution engine — topological sort and parallel scheduling.

Extends the Orchestrator's sequential/parallel/pipeline model
to arbitrary DAG execution with domain-aware scheduling.
"""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from mascarade.node_engine.graph import Graph, GraphNode
    from mascarade.node_engine.registry import NodeTypeRegistry, WorkerRegistry

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


class GraphExecutionEngine:
    """
    Executes a node graph respecting topological ordering and parallel branches.

    Modeled on Orchestrator (core/mascarade/orchestrator/engine.py) with
    extensions for DAG-aware scheduling, domain-specific worker dispatch,
    and cross-domain type adaptation.
    """

    def __init__(self, worker_registry: "WorkerRegistry", node_registry: "NodeTypeRegistry"):
        self._worker_registry = worker_registry
        self._node_registry = node_registry

    def _topological_sort(self, graph: "Graph") -> list[list[str]]:
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

    async def execute(self, graph: "Graph", run_id: str) -> list[NodeResult]:
        """
        Execute a graph by processing levels in order, parallelizing within levels.
        """
        levels = self._topological_sort(graph)
        all_results: list[NodeResult] = []
        port_data: dict[str, dict[str, Any]] = {}

        for level in levels:
            tasks = []
            node_ids = []
            for node_id in level:
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

            # Execute all nodes in this level in parallel
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Process results, maintaining association with node_ids
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    # Defensive: _execute_node should catch exceptions, but handle edge cases
                    logger.error("Unexpected exception for node %s: %s", node_ids[i], result)
                    all_results.append(
                        NodeResult(node_id=node_ids[i], error=str(result))
                    )
                else:
                    all_results.append(result)
                    port_data[result.node_id] = result.outputs

        return all_results

    def _collect_inputs(
        self, graph: "Graph", node_id: str, port_data: dict[str, dict[str, Any]]
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
        self, node: "GraphNode", inputs: dict[str, Any], ctx: ExecutionContext
    ) -> NodeResult:
        """Execute a single node using its registered worker."""
        import time

        start = time.monotonic()
        node_type = self._node_registry.get(node.node_type)
        worker = self._worker_registry.get(node_type.domain)

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
