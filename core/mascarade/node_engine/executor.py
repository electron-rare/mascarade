"""Node Executor — graph execution with worker dispatch, validation, and topological ordering."""

from __future__ import annotations

import asyncio
import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from mascarade.node_engine.types import NodeType, PortType

logger = logging.getLogger("mascarade.node_engine")


class ExecutionStatus(str, Enum):
    """Execution status enum."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"


@dataclass
class NodeExecutionRecord:
    """Record of a single node's execution."""

    node_id: str
    status: ExecutionStatus = ExecutionStatus.PENDING
    outputs: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    error_type: str | None = None
    execution_time_ms: float = 0.0


@dataclass
class GraphExecutionResult:
    """Result of executing an entire graph."""

    graph_id: str = ""
    status: ExecutionStatus = ExecutionStatus.PENDING
    outputs: dict[str, dict[str, Any]] = field(default_factory=dict)
    error: str | None = None
    node_records: list[NodeExecutionRecord] = field(default_factory=list)
    start_time_ms: float = 0.0
    end_time_ms: float = 0.0
    total_time_ms: float = 0.0

    def get_node_record(self, node_id: str) -> NodeExecutionRecord | None:
        """Get execution record for a specific node."""
        for record in self.node_records:
            if record.node_id == node_id:
                return record
        return None


@dataclass
class NodeExecutionResult:
    """Result of executing a single node (used by executor internals)."""

    success: bool
    outputs: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    execution_time_ms: float = 0.0
    warnings: list[str] = field(default_factory=list)


class GraphExecutor:
    """Graph executor with worker dispatch, validation, and topological ordering."""

    def __init__(self) -> None:
        self._workers: dict[str, Any] = {}
        self._node_definitions: dict[str, Any] = {}

    def register_worker(self, worker: Any) -> None:
        """Register a worker and its node definitions."""
        domain = worker.domain
        self._workers[domain] = worker

        for node_def in worker.register_nodes():
            self._node_definitions[node_def.node_type] = node_def

    async def initialize_workers(self) -> None:
        """Initialize all registered workers."""
        for worker in self._workers.values():
            await worker.initialize()

    async def shutdown_workers(self) -> None:
        """Shutdown all registered workers."""
        for worker in self._workers.values():
            await worker.shutdown()

    def validate_graph(self, graph: Any) -> list[str]:
        """Validate a graph before execution.

        Returns list of error messages. Empty list means valid.
        """
        errors: list[str] = []

        # Check all node types are known
        for node in graph.nodes:
            node_type = getattr(node, 'node_type', '')
            if node_type not in self._node_definitions:
                errors.append(f"Node '{getattr(node, 'node_id', getattr(node, 'id', ''))}' has unknown type '{node_type}'")

        # Check required inputs are provided (via connections or config)
        connections = getattr(graph, 'connections', [])
        for node in graph.nodes:
            node_id = getattr(node, 'node_id', getattr(node, 'id', ''))
            node_type = getattr(node, 'node_type', '')
            node_def = self._node_definitions.get(node_type)
            if not node_def:
                continue

            config = getattr(node, 'config', {})

            # Check for required inputs
            for port in node_def.input_ports:
                if getattr(port, 'optional', False):
                    continue
                if not getattr(port, 'required', True):
                    continue
                port_name = port.name

                # Check if provided via connection
                has_connection = any(
                    getattr(conn, 'target_node_id', '') == node_id and
                    getattr(conn, 'target_port', '') == port_name
                    for conn in connections
                )

                # Check if provided via config
                has_config = port_name in config

                if not has_connection and not has_config:
                    errors.append(f"Node '{node_id}': missing required input '{port_name}'")

        # Check for cycles
        try:
            self._topological_sort(graph)
        except ValueError as e:
            errors.append(f"Graph contains a cycle: {e}")

        return errors

    def _topological_sort(self, graph: Any) -> list[Any]:
        """Sort nodes in topological order."""
        in_degree: dict[str, int] = {}
        adjacency: dict[str, list[str]] = defaultdict(list)

        for node in graph.nodes:
            node_id = getattr(node, 'node_id', getattr(node, 'id', ''))
            in_degree[node_id] = 0

        connections = getattr(graph, 'connections', [])
        for conn in connections:
            src = getattr(conn, 'source_node_id', '')
            tgt = getattr(conn, 'target_node_id', '')
            adjacency[src].append(tgt)
            in_degree[tgt] = in_degree.get(tgt, 0) + 1

        edges = getattr(graph, 'edges', [])
        for edge in edges:
            src = getattr(edge, 'source_node', '')
            tgt = getattr(edge, 'target_node', '')
            adjacency[src].append(tgt)
            in_degree[tgt] = in_degree.get(tgt, 0) + 1

        queue = [nid for nid, deg in in_degree.items() if deg == 0]
        result = []

        while queue:
            node_id = queue.pop(0)
            node = graph.get_node(node_id)
            if node:
                result.append(node)
            for neighbor in adjacency[node_id]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        if len(result) != len(graph.nodes):
            raise ValueError("Graph contains a cycle")

        return result

    async def execute_graph(
        self,
        graph: Any,
        *,
        timeout_seconds: float | None = None,
        capabilities: set[str] | None = None,
    ) -> GraphExecutionResult:
        """Execute a graph with topological ordering."""
        result = GraphExecutionResult(
            graph_id=getattr(graph, 'graph_id', getattr(graph, 'id', '')),
            status=ExecutionStatus.RUNNING,
            start_time_ms=time.monotonic() * 1000,
        )

        try:
            if timeout_seconds is not None:
                try:
                    await asyncio.wait_for(
                        self._execute_graph_inner(graph, result, capabilities),
                        timeout=timeout_seconds,
                    )
                except asyncio.TimeoutError:
                    result.status = ExecutionStatus.TIMEOUT
                    result.error = f"Graph execution timed out after {timeout_seconds}s"
            else:
                await self._execute_graph_inner(graph, result, capabilities)
        except Exception as e:
            result.status = ExecutionStatus.FAILED
            result.error = str(e)

        result.end_time_ms = time.monotonic() * 1000
        result.total_time_ms = result.end_time_ms - result.start_time_ms
        return result

    async def _execute_graph_inner(
        self,
        graph: Any,
        result: GraphExecutionResult,
        capabilities: set[str] | None,
    ) -> None:
        """Inner graph execution logic."""
        sorted_nodes = self._topological_sort(graph)
        node_outputs: dict[str, dict[str, Any]] = {}
        connections = getattr(graph, 'connections', [])

        for node in sorted_nodes:
            node_id = getattr(node, 'node_id', getattr(node, 'id', ''))
            node_type = getattr(node, 'node_type', '')
            node_def = self._node_definitions.get(node_type)

            if not node_def:
                record = NodeExecutionRecord(
                    node_id=node_id,
                    status=ExecutionStatus.FAILED,
                    error=f"Unknown node type: {node_type}",
                    error_type="RuntimeError",
                )
                result.node_records.append(record)
                result.status = ExecutionStatus.FAILED
                result.error = f"Unknown node type: {node_type}"
                return

            # Collect inputs
            inputs = self._collect_node_inputs(graph, node, node_outputs, node_def)

            # Find worker
            domain = node_type.split(".")[0] if "." in node_type else node_type
            worker = self._workers.get(domain)

            if not worker:
                record = NodeExecutionRecord(
                    node_id=node_id,
                    status=ExecutionStatus.FAILED,
                    error=f"No worker for domain: {domain}",
                    error_type="RuntimeError",
                )
                result.node_records.append(record)
                result.status = ExecutionStatus.FAILED
                result.error = f"No worker for domain: {domain}"
                return

            # Build execution context
            from mascarade.node_engine.base import NodeExecutionContext
            ctx = NodeExecutionContext(
                node_id=node_id,
                graph_id=result.graph_id,
                inputs=inputs,
                config=getattr(node, 'config', {}),
                capabilities=capabilities or set(),
            )

            # Execute
            start = time.monotonic()
            try:
                exec_result = await worker.execute_node(node_def, ctx)
                exec_time = (time.monotonic() - start) * 1000

                if exec_result.success:
                    record = NodeExecutionRecord(
                        node_id=node_id,
                        status=ExecutionStatus.COMPLETED,
                        outputs=exec_result.outputs,
                        execution_time_ms=exec_time,
                    )
                    node_outputs[node_id] = exec_result.outputs
                    result.outputs[node_id] = exec_result.outputs
                else:
                    record = NodeExecutionRecord(
                        node_id=node_id,
                        status=ExecutionStatus.FAILED,
                        error=exec_result.error,
                        error_type=getattr(exec_result, 'error_type', 'RuntimeError'),
                        execution_time_ms=exec_time,
                    )
                    result.status = ExecutionStatus.FAILED
                    result.error = exec_result.error
                    result.node_records.append(record)
                    return

            except PermissionError as e:
                exec_time = (time.monotonic() - start) * 1000
                record = NodeExecutionRecord(
                    node_id=node_id,
                    status=ExecutionStatus.FAILED,
                    error=str(e),
                    error_type="PermissionError",
                    execution_time_ms=exec_time,
                )
                result.status = ExecutionStatus.FAILED
                result.error = str(e)
                result.node_records.append(record)
                return

            except Exception as e:
                exec_time = (time.monotonic() - start) * 1000
                record = NodeExecutionRecord(
                    node_id=node_id,
                    status=ExecutionStatus.FAILED,
                    error=str(e),
                    error_type=type(e).__name__,
                    execution_time_ms=exec_time,
                )
                result.status = ExecutionStatus.FAILED
                result.error = str(e)
                result.node_records.append(record)
                return

            result.node_records.append(record)

        if result.status == ExecutionStatus.RUNNING:
            result.status = ExecutionStatus.COMPLETED

    def _collect_node_inputs(
        self,
        graph: Any,
        node: Any,
        node_outputs: dict[str, dict[str, Any]],
        node_def: Any,
    ) -> dict[str, Any]:
        """Collect inputs for a node from connections and config."""
        inputs: dict[str, Any] = {}
        node_id = getattr(node, 'node_id', getattr(node, 'id', ''))
        config = getattr(node, 'config', {})

        # First, apply config values as defaults
        for port in node_def.input_ports:
            port_name = port.name
            if port_name in config:
                inputs[port_name] = config[port_name]
            elif getattr(port, 'default_value', None) is not None:
                inputs[port_name] = port.default_value

        # Then, apply connected values (override defaults)
        connections = getattr(graph, 'connections', [])
        for conn in connections:
            if getattr(conn, 'target_node_id', '') == node_id:
                src_id = getattr(conn, 'source_node_id', '')
                src_port = getattr(conn, 'source_port', '')
                tgt_port = getattr(conn, 'target_port', '')
                if src_id in node_outputs and src_port in node_outputs[src_id]:
                    inputs[tgt_port] = node_outputs[src_id][src_port]

        return inputs
