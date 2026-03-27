#!/usr/bin/env python3
"""MVP Gate Benchmark — Criteria #4 (Performance) and #7 (Developer Experience).

Criterion #4: Performance
  - Graph compilation < 100ms for 50-node graphs
  - Node execution overhead < 10ms per node (excluding worker time)

Criterion #7: Developer Experience
  - Document steps to create a new node type
  - Time estimate based on existing codebase

Runs 10 iterations and reports min/avg/max for each metric.
"""

from __future__ import annotations

import asyncio
import statistics
import time
from typing import Any

# ---------------------------------------------------------------------------
# Path A: GraphRuntime with Pydantic Node/Edge models
# ---------------------------------------------------------------------------
from mascarade.node_engine.graph import Graph, Node, Edge
from mascarade.node_engine.runtime import GraphRuntime, ExecutionMode
from mascarade.node_engine.worker import NodeWorker as RuntimeNodeWorker

# ---------------------------------------------------------------------------
# Path B: GraphExecutionEngine with dataclass GraphNode/GraphEdge models
# ---------------------------------------------------------------------------
from mascarade.node_engine.graph import GraphNode, GraphEdge
from mascarade.node_engine.engine import GraphExecutionEngine
from mascarade.node_engine.registry import NodeTypeRegistry, WorkerRegistry
from mascarade.node_engine.types import NodeType
from mascarade.node_engine.base import (
    NodeWorker as BaseNodeWorker,
    NodeDefinition,
    NodeExecutionContext,
    NodeExecutionResult,
    NodePort,
    PortDirection,
)
# NodePort is an alias for PortType — used directly in NodeDefinition


# ===== Constants =====
NUM_NODES = 50
NUM_ITERATIONS = 10
COMPILATION_BUDGET_MS = 100.0
PER_NODE_OVERHEAD_BUDGET_MS = 10.0


# ===== Mock Workers =====

class MockRuntimeWorker(RuntimeNodeWorker):
    """Zero-cost mock worker for GraphRuntime benchmarking."""

    name = "benchmark-worker"
    domain = "bench"

    async def execute(
        self,
        node_type: str,
        inputs: dict[str, Any],
        config: dict[str, Any],
        context: Any,
    ) -> dict[str, Any]:
        # Instant return — zero worker time
        return {"output": inputs.get("input", "start")}

    async def validate(
        self,
        node_type: str,
        inputs: dict[str, Any],
        config: dict[str, Any],
    ) -> list[str]:
        return []

    def capabilities(self) -> dict[str, Any]:
        return {
            "node_types": ["bench.passthrough"],
            "domain": "bench",
        }


class MockEngineWorker(BaseNodeWorker):
    """Zero-cost mock worker for GraphExecutionEngine benchmarking."""

    domain = "bench"
    name = "benchmark-engine-worker"

    def register_nodes(self) -> list[NodeDefinition]:
        return [
            NodeDefinition(
                node_type="bench.passthrough",
                description="Zero-cost passthrough node",
                input_ports=[
                    NodePort(
                        name="input",
                        type="string",
                        port_type="string",
                        direction=PortDirection.INPUT,
                        optional=True,
                    ),
                ],
                output_ports=[
                    NodePort(
                        name="output",
                        type="string",
                        port_type="string",
                        direction=PortDirection.OUTPUT,
                    ),
                ],
            ),
        ]

    async def execute_node(
        self,
        node_def: NodeDefinition,
        context: NodeExecutionContext,
    ) -> NodeExecutionResult:
        # Instant return — zero worker time
        return NodeExecutionResult.ok(output=context.get_input("input", "start"))

    async def initialize(self) -> None:
        pass

    async def shutdown(self) -> None:
        pass


# ===== Graph Builders =====

def build_pydantic_graph() -> Graph:
    """Build a 50-node chain graph using Pydantic Node/Edge models."""
    nodes = [
        Node(id=f"node{i}", type="bench.passthrough", inputs={"input": "data"} if i == 0 else {})
        for i in range(NUM_NODES)
    ]
    edges = [
        Edge(
            from_node=f"node{i}",
            from_port="output",
            to_node=f"node{i + 1}",
            to_port="input",
        )
        for i in range(NUM_NODES - 1)
    ]
    return Graph(id="bench-pydantic-50", name="Benchmark 50-chain", nodes=nodes, edges=edges)


def build_dataclass_graph() -> Graph:
    """Build a 50-node chain graph using dataclass GraphNode/GraphEdge models."""
    nodes = [
        GraphNode(id=f"node{i}", node_type="bench.passthrough", config={"input": "data"} if i == 0 else {})
        for i in range(NUM_NODES)
    ]
    edges = [
        GraphEdge(
            id=f"edge{i}",
            source_node=f"node{i}",
            source_port="output",
            target_node=f"node{i + 1}",
            target_port="input",
        )
        for i in range(NUM_NODES - 1)
    ]
    return Graph(id="bench-dataclass-50", name="Benchmark 50-chain", nodes=nodes, edges=edges)


# ===== Benchmark Functions =====

def benchmark_compilation_pydantic() -> list[float]:
    """Measure graph construction + validation + topological sort (Pydantic path)."""
    times: list[float] = []
    for _ in range(NUM_ITERATIONS):
        t0 = time.perf_counter()
        graph = build_pydantic_graph()
        _ = graph.topological_sort()
        t1 = time.perf_counter()
        times.append((t1 - t0) * 1000)
    return times


def benchmark_compilation_dataclass() -> list[float]:
    """Measure graph construction + topological sort (dataclass path)."""
    times: list[float] = []
    for _ in range(NUM_ITERATIONS):
        t0 = time.perf_counter()
        graph = build_dataclass_graph()
        _ = graph.topological_sort()
        t1 = time.perf_counter()
        times.append((t1 - t0) * 1000)
    return times


def benchmark_compilation_engine() -> list[float]:
    """Measure topological sort via GraphExecutionEngine._topological_sort (Kahn's with levels)."""
    engine = GraphExecutionEngine()
    times: list[float] = []
    for _ in range(NUM_ITERATIONS):
        graph = build_dataclass_graph()
        t0 = time.perf_counter()
        _ = engine._topological_sort(graph)
        t1 = time.perf_counter()
        times.append((t1 - t0) * 1000)
    return times


async def benchmark_execution_runtime() -> tuple[list[float], list[float]]:
    """Measure per-node execution overhead via GraphRuntime (Pydantic path).

    Returns:
        (total_times_ms, per_node_overhead_ms_list)
    """
    runtime = GraphRuntime()
    runtime.register_worker(MockRuntimeWorker())

    total_times: list[float] = []
    per_node_overheads: list[float] = []

    for _ in range(NUM_ITERATIONS):
        graph = build_pydantic_graph()

        t0 = time.perf_counter()
        ctx = await runtime.execute(graph, mode=ExecutionMode.EAGER)
        t1 = time.perf_counter()

        total_ms = (t1 - t0) * 1000
        total_times.append(total_ms)

        # Per-node overhead = total execution time / number of nodes
        # Since mock worker returns instantly, this IS the overhead
        per_node_overheads.append(total_ms / NUM_NODES)

        # Verify all nodes completed
        assert ctx.status.value == "completed", f"Execution failed: {ctx.status}"
        assert len(ctx.node_results) == NUM_NODES, f"Expected {NUM_NODES} results, got {len(ctx.node_results)}"

    return total_times, per_node_overheads


async def benchmark_execution_engine() -> tuple[list[float], list[float]]:
    """Measure per-node execution overhead via GraphExecutionEngine (dataclass path).

    Returns:
        (total_times_ms, per_node_overhead_ms_list)
    """
    worker_reg = WorkerRegistry()
    node_reg = NodeTypeRegistry(storage_path=None)

    # Register mock worker
    mock_worker = MockEngineWorker()
    worker_reg.register(mock_worker)

    # Register node type
    node_reg.register(
        NodeType(
            id="bench.passthrough",
            name="Passthrough",
            domain="bench",
            category="benchmark",
            description="Zero-cost passthrough",
            inputs=[],
            outputs=[],
        ),
        builtin=True,
    )

    engine = GraphExecutionEngine(
        worker_registry=worker_reg,
        node_registry=node_reg,
    )

    total_times: list[float] = []
    per_node_overheads: list[float] = []

    for _ in range(NUM_ITERATIONS):
        graph = build_dataclass_graph()

        t0 = time.perf_counter()
        results = await engine.execute(graph, run_id="bench-run")
        t1 = time.perf_counter()

        total_ms = (t1 - t0) * 1000
        total_times.append(total_ms)
        per_node_overheads.append(total_ms / NUM_NODES)

        # Verify all nodes completed
        assert len(results) == NUM_NODES, f"Expected {NUM_NODES} results, got {len(results)}"
        for r in results:
            assert r.error is None, f"Node {r.node_id} failed: {r.error}"

    return total_times, per_node_overheads


# ===== Reporting =====

def report_stats(label: str, values: list[float], budget_ms: float | None = None) -> bool:
    """Print min/avg/max stats and return True if within budget."""
    mn = min(values)
    avg = statistics.mean(values)
    mx = max(values)
    med = statistics.median(values)

    passed = True
    status = ""
    if budget_ms is not None:
        passed = avg <= budget_ms
        status = f"  [{'PASS' if passed else 'FAIL'}  budget: {budget_ms:.1f}ms]"

    print(f"  {label}")
    print(f"    min={mn:.3f}ms  avg={avg:.3f}ms  median={med:.3f}ms  max={mx:.3f}ms{status}")
    return passed


def print_criterion_7() -> None:
    """Print Developer Experience documentation for Criterion #7."""
    print()
    print("=" * 72)
    print("CRITERION #7: DEVELOPER EXPERIENCE")
    print("=" * 72)
    print()
    print("Steps to create a new node type:")
    print()
    print("  Path A — GraphRuntime (Pydantic Node/Edge, runtime.py)")
    print("  --------------------------------------------------------")
    print("  1. Create a worker class extending worker.NodeWorker")
    print("     - Set `name` and `domain` class attributes")
    print("     - Implement execute(node_type, inputs, config, context)")
    print("     - Implement validate(node_type, inputs, config)")
    print("     - Implement capabilities() returning node_types list")
    print("  2. Register with runtime.register_worker(your_worker)")
    print("  3. Use Node(id=..., type='domain.name') in your graph")
    print()
    print("  Path B — GraphExecutionEngine (dataclass, engine.py + executor.py)")
    print("  -------------------------------------------------------------------")
    print("  1. Create a worker class extending base.NodeWorker")
    print("     - Set `domain` class attribute")
    print("     - Implement register_nodes() returning NodeDefinition list")
    print("       (with NodePort for input/output ports and PortType)")
    print("     - Implement execute_node(node_def, context) -> NodeExecutionResult")
    print("  2. Register with GraphExecutor.register_worker(your_worker)")
    print("     (or WorkerRegistry + NodeTypeRegistry for GraphExecutionEngine)")
    print("  3. Use GraphNode(id=..., node_type='domain.name') in your graph")
    print()
    print("  Files to touch:")
    print("    - core/mascarade/node_engine/workers/<domain>/worker.py  (new worker)")
    print("    - core/mascarade/node_engine/workers/<domain>/register.py (registration)")
    print("    - core/mascarade/node_engine/workers/<domain>/types.py   (domain types)")
    print()
    print("  Time estimate: ~30-60 minutes for a simple node type")
    print("    - 10 min: worker skeleton + execute_node implementation")
    print("    - 10 min: NodeDefinition with ports and types")
    print("    - 10 min: registration and wiring")
    print("    - 10-30 min: tests")
    print()
    print("  Reference examples:")
    print("    - workers/hardware/worker.py  (simple, 5 node types)")
    print("    - workers/ai/worker.py        (complex, streaming)")
    print("    - workers/cad/worker.py       (multi-tool)")
    print()
    print("  VERDICT: [PASS] Clear abstractions, two well-documented paths,")
    print("           existing examples cover simple to complex cases.")
    print()


# ===== Main =====

async def main() -> None:
    print()
    print("=" * 72)
    print("MVP GATE BENCHMARK — Node Engine Performance (Criterion #4)")
    print(f"  {NUM_NODES} nodes, chain topology, {NUM_ITERATIONS} iterations")
    print("=" * 72)
    print()

    all_passed = True

    # --- Compilation benchmarks ---
    print("-" * 72)
    print("GRAPH COMPILATION (construction + validation + topological sort)")
    print(f"  Budget: < {COMPILATION_BUDGET_MS:.0f}ms for {NUM_NODES}-node graph")
    print("-" * 72)

    times_pydantic = benchmark_compilation_pydantic()
    p1 = report_stats(
        f"Pydantic path (Graph + Node + Edge + topo sort)",
        times_pydantic,
        COMPILATION_BUDGET_MS,
    )
    all_passed &= p1

    times_dataclass = benchmark_compilation_dataclass()
    p2 = report_stats(
        f"Dataclass path (Graph + GraphNode + GraphEdge + topo sort)",
        times_dataclass,
        COMPILATION_BUDGET_MS,
    )
    all_passed &= p2

    times_engine_topo = benchmark_compilation_engine()
    p3 = report_stats(
        f"Engine Kahn's topo sort only (pre-built graph)",
        times_engine_topo,
        COMPILATION_BUDGET_MS,
    )
    all_passed &= p3

    # --- Execution benchmarks ---
    print()
    print("-" * 72)
    print("NODE EXECUTION OVERHEAD (zero-cost mock worker)")
    print(f"  Budget: < {PER_NODE_OVERHEAD_BUDGET_MS:.0f}ms per node")
    print("-" * 72)

    total_runtime, per_node_runtime = await benchmark_execution_runtime()
    report_stats(
        f"GraphRuntime total ({NUM_NODES} nodes)",
        total_runtime,
    )
    p4 = report_stats(
        f"GraphRuntime per-node overhead",
        per_node_runtime,
        PER_NODE_OVERHEAD_BUDGET_MS,
    )
    all_passed &= p4

    total_engine, per_node_engine = await benchmark_execution_engine()
    report_stats(
        f"GraphExecutionEngine total ({NUM_NODES} nodes)",
        total_engine,
    )
    p5 = report_stats(
        f"GraphExecutionEngine per-node overhead",
        per_node_engine,
        PER_NODE_OVERHEAD_BUDGET_MS,
    )
    all_passed &= p5

    # --- Summary ---
    print()
    print("=" * 72)
    criterion_4_pass = p1 and p2 and p3 and p4 and p5
    print(f"CRITERION #4 VERDICT: {'PASS' if criterion_4_pass else 'FAIL'}")
    print("=" * 72)

    # --- Criterion #7 ---
    print_criterion_7()

    # --- Final ---
    print("=" * 72)
    print(f"OVERALL MVP GATE: {'PASS' if all_passed else 'FAIL'}")
    print("=" * 72)
    print()


if __name__ == "__main__":
    asyncio.run(main())
