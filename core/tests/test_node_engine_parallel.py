"""Tests for parallel execution within levels using asyncio.gather in the Node Engine."""

import asyncio
import time

import pytest

from mascarade.node_engine.engine import GraphExecutionEngine
from mascarade.node_engine.graph import ExecutionContext, Graph, GraphEdge, GraphNode
from mascarade.node_engine.registry import NodeType, NodeTypeRegistry, WorkerRegistry
from mascarade.node_engine.worker import NodeCapability, NodeWorker


class MockWorker(NodeWorker):
    """Mock worker for testing parallel execution."""

    def __init__(
        self,
        name: str = "mock-worker",
        domain: str = "test",
        execution_delay: float = 0.0,
    ):
        self.name = name
        self.domain = domain
        self._execution_delay = execution_delay
        self._execution_order = []
        self._execution_times = {}

    async def execute(
        self,
        node_type: str,
        inputs: dict,
        config: dict,
        context: ExecutionContext,
    ) -> dict:
        """Execute a node with optional delay to test parallel execution."""
        start = time.monotonic()
        self._execution_order.append(context.node_id)

        if self._execution_delay > 0:
            await asyncio.sleep(self._execution_delay)

        # Simple pass-through: output = input + config
        outputs = {
            "result": inputs.get("value", 0) + config.get("add", 0),
            "node_id": context.node_id,
        }

        self._execution_times[context.node_id] = time.monotonic() - start
        return outputs

    async def validate(self, node_type: str, inputs: dict, config: dict) -> list[str]:
        """Validation always passes for mock worker."""
        return []

    def capabilities(self) -> NodeCapability:
        """Return basic capabilities."""
        return NodeCapability(
            node_types=["test-node"],
            domain=self.domain,
            supports_streaming=False,
            supports_cancellation=True,
            max_concurrent=10,
        )


class FailingMockWorker(NodeWorker):
    """Mock worker that always fails, for error handling tests."""

    def __init__(self, fail_nodes: set[str] | None = None):
        self.name = "failing-worker"
        self.domain = "test"
        self._fail_nodes = fail_nodes or set()

    async def execute(
        self,
        node_type: str,
        inputs: dict,
        config: dict,
        context: ExecutionContext,
    ) -> dict:
        """Execute with conditional failure based on node ID."""
        if context.node_id in self._fail_nodes:
            raise RuntimeError(f"Simulated failure for node {context.node_id}")
        return {"result": "success", "node_id": context.node_id}

    async def validate(self, node_type: str, inputs: dict, config: dict) -> list[str]:
        return []

    def capabilities(self) -> NodeCapability:
        return NodeCapability(
            node_types=["test-node"],
            domain=self.domain,
            supports_streaming=False,
            supports_cancellation=True,
            max_concurrent=10,
        )


class TestParallelExecution:
    """Test suite for parallel execution within levels."""

    @pytest.mark.asyncio
    async def test_parallel_execution_within_level(self):
        """Nodes in the same level should execute in parallel using asyncio.gather."""
        worker = MockWorker(execution_delay=0.1)
        worker_registry = WorkerRegistry()
        worker_registry.register(worker)

        node_registry = NodeTypeRegistry()
        node_registry.register(
            NodeType(
                id="test-node",
                domain="test",
                label="Test Node",
                description="Mock test node",
            )
        )

        engine = GraphExecutionEngine(worker_registry, node_registry)

        # Create graph with 3 parallel nodes (no dependencies)
        graph = Graph(
            id="test",
            name="Parallel Test",
            nodes=[
                GraphNode(id="n1", node_type="test-node", label="Node 1"),
                GraphNode(id="n2", node_type="test-node", label="Node 2"),
                GraphNode(id="n3", node_type="test-node", label="Node 3"),
            ],
        )

        start = time.monotonic()
        results = await engine.execute(graph, run_id="run-1")
        duration = time.monotonic() - start

        # All 3 nodes executed
        assert len(results) == 3
        assert all(r.error is None for r in results)

        # If parallel, total time should be ~0.1s (one delay)
        # If sequential, it would be ~0.3s (three delays)
        # Allow some overhead, but it should be much closer to 0.1s
        assert duration < 0.2, f"Expected parallel execution (~0.1s), got {duration}s"

        # All nodes should have executed
        assert set(worker._execution_order) == {"n1", "n2", "n3"}

    @pytest.mark.asyncio
    async def test_sequential_level_execution(self):
        """Levels should execute sequentially, but nodes within each level in parallel."""
        worker = MockWorker(execution_delay=0.05)
        worker_registry = WorkerRegistry()
        worker_registry.register(worker)

        node_registry = NodeTypeRegistry()
        node_registry.register(
            NodeType(
                id="test-node",
                domain="test",
                label="Test Node",
                description="Mock test node",
            )
        )

        engine = GraphExecutionEngine(worker_registry, node_registry)

        # Diamond pattern: n1 -> (n2, n3) -> n4
        # Level 0: [n1]
        # Level 1: [n2, n3] (parallel)
        # Level 2: [n4]
        graph = Graph(
            id="test",
            name="Diamond Test",
            nodes=[
                GraphNode(id="n1", node_type="test-node", label="Source"),
                GraphNode(id="n2", node_type="test-node", label="Left"),
                GraphNode(id="n3", node_type="test-node", label="Right"),
                GraphNode(id="n4", node_type="test-node", label="Sink"),
            ],
            edges=[
                GraphEdge(
                    id="e1",
                    source_node="n1",
                    source_port="out",
                    target_node="n2",
                    target_port="in",
                ),
                GraphEdge(
                    id="e2",
                    source_node="n1",
                    source_port="out",
                    target_node="n3",
                    target_port="in",
                ),
                GraphEdge(
                    id="e3",
                    source_node="n2",
                    source_port="out",
                    target_node="n4",
                    target_port="in",
                ),
                GraphEdge(
                    id="e4",
                    source_node="n3",
                    source_port="out",
                    target_node="n4",
                    target_port="in",
                ),
            ],
        )

        start = time.monotonic()
        results = await engine.execute(graph, run_id="run-1")
        duration = time.monotonic() - start

        # All 4 nodes executed
        assert len(results) == 4
        assert all(r.error is None for r in results)

        # Expected time: 3 levels * 0.05s = ~0.15s (parallel within level 1)
        # Sequential would be 4 * 0.05s = 0.2s
        assert duration < 0.18, f"Expected ~0.15s with parallel middle level, got {duration}s"

        # Verify execution order: n1 before n2/n3, n2/n3 before n4
        order = worker._execution_order
        assert order[0] == "n1"
        assert set(order[1:3]) == {"n2", "n3"}
        assert order[3] == "n4"

    @pytest.mark.asyncio
    async def test_data_flow_through_parallel_branches(self):
        """Data should flow correctly through parallel branches."""
        worker = MockWorker()
        worker_registry = WorkerRegistry()
        worker_registry.register(worker)

        node_registry = NodeTypeRegistry()
        node_registry.register(
            NodeType(
                id="test-node",
                domain="test",
                label="Test Node",
                description="Mock test node",
            )
        )

        engine = GraphExecutionEngine(worker_registry, node_registry)

        # n1 -> (n2, n3) with data flow
        graph = Graph(
            id="test",
            name="Data Flow Test",
            nodes=[
                GraphNode(id="n1", node_type="test-node", label="Source", config={"add": 10}),
                GraphNode(id="n2", node_type="test-node", label="Left", config={"add": 5}),
                GraphNode(id="n3", node_type="test-node", label="Right", config={"add": 3}),
            ],
            edges=[
                GraphEdge(
                    id="e1",
                    source_node="n1",
                    source_port="result",
                    target_node="n2",
                    target_port="value",
                ),
                GraphEdge(
                    id="e2",
                    source_node="n1",
                    source_port="result",
                    target_node="n3",
                    target_port="value",
                ),
            ],
        )

        results = await engine.execute(graph, run_id="run-1")

        # Find results by node_id
        result_map = {r.node_id: r for r in results}

        # n1: 0 + 10 = 10
        assert result_map["n1"].outputs["result"] == 10

        # n2: 10 + 5 = 15
        assert result_map["n2"].outputs["result"] == 15

        # n3: 10 + 3 = 13
        assert result_map["n3"].outputs["result"] == 13

    @pytest.mark.asyncio
    async def test_error_handling_in_parallel_execution(self):
        """Errors in one parallel node should not stop other parallel nodes."""
        worker = FailingMockWorker(fail_nodes={"n2"})
        worker_registry = WorkerRegistry()
        worker_registry.register(worker)

        node_registry = NodeTypeRegistry()
        node_registry.register(
            NodeType(
                id="test-node",
                domain="test",
                label="Test Node",
                description="Mock test node",
            )
        )

        engine = GraphExecutionEngine(worker_registry, node_registry)

        # 3 parallel nodes, n2 will fail
        graph = Graph(
            id="test",
            name="Error Test",
            nodes=[
                GraphNode(id="n1", node_type="test-node", label="Node 1"),
                GraphNode(id="n2", node_type="test-node", label="Node 2 (fails)"),
                GraphNode(id="n3", node_type="test-node", label="Node 3"),
            ],
        )

        results = await engine.execute(graph, run_id="run-1")

        # All 3 nodes should have results
        assert len(results) == 3

        result_map = {r.node_id: r for r in results}

        # n1 and n3 should succeed
        assert result_map["n1"].error is None
        assert result_map["n1"].outputs["result"] == "success"

        assert result_map["n3"].error is None
        assert result_map["n3"].outputs["result"] == "success"

        # n2 should have error
        assert result_map["n2"].error is not None
        assert "Simulated failure" in result_map["n2"].error

    @pytest.mark.asyncio
    async def test_asyncio_gather_return_exceptions(self):
        """Verify asyncio.gather with return_exceptions=True handles failures correctly."""
        worker = FailingMockWorker(fail_nodes={"n1", "n3"})
        worker_registry = WorkerRegistry()
        worker_registry.register(worker)

        node_registry = NodeTypeRegistry()
        node_registry.register(
            NodeType(
                id="test-node",
                domain="test",
                label="Test Node",
                description="Mock test node",
            )
        )

        engine = GraphExecutionEngine(worker_registry, node_registry)

        # 3 parallel nodes, n1 and n3 will fail
        graph = Graph(
            id="test",
            name="Multiple Errors Test",
            nodes=[
                GraphNode(id="n1", node_type="test-node", label="Node 1 (fails)"),
                GraphNode(id="n2", node_type="test-node", label="Node 2"),
                GraphNode(id="n3", node_type="test-node", label="Node 3 (fails)"),
            ],
        )

        results = await engine.execute(graph, run_id="run-1")

        # All 3 nodes should have results
        assert len(results) == 3

        result_map = {r.node_id: r for r in results}

        # n2 should succeed
        assert result_map["n2"].error is None

        # n1 and n3 should have errors
        assert result_map["n1"].error is not None
        assert result_map["n3"].error is not None

    @pytest.mark.asyncio
    async def test_empty_level_handling(self):
        """Engine should handle empty levels gracefully."""
        worker = MockWorker()
        worker_registry = WorkerRegistry()
        worker_registry.register(worker)

        node_registry = NodeTypeRegistry()
        node_registry.register(
            NodeType(
                id="test-node",
                domain="test",
                label="Test Node",
                description="Mock test node",
            )
        )

        engine = GraphExecutionEngine(worker_registry, node_registry)

        # Empty graph
        graph = Graph(id="test", name="Empty Graph")

        results = await engine.execute(graph, run_id="run-1")

        assert results == []

    @pytest.mark.asyncio
    async def test_single_node_execution(self):
        """Single node should execute correctly (single-item gather)."""
        worker = MockWorker()
        worker_registry = WorkerRegistry()
        worker_registry.register(worker)

        node_registry = NodeTypeRegistry()
        node_registry.register(
            NodeType(
                id="test-node",
                domain="test",
                label="Test Node",
                description="Mock test node",
            )
        )

        engine = GraphExecutionEngine(worker_registry, node_registry)

        graph = Graph(
            id="test",
            name="Single Node",
            nodes=[GraphNode(id="n1", node_type="test-node", label="Only Node")],
        )

        results = await engine.execute(graph, run_id="run-1")

        assert len(results) == 1
        assert results[0].node_id == "n1"
        assert results[0].error is None

    @pytest.mark.asyncio
    async def test_large_parallel_level(self):
        """Large number of parallel nodes should execute efficiently."""
        worker = MockWorker(execution_delay=0.05)
        worker_registry = WorkerRegistry()
        worker_registry.register(worker)

        node_registry = NodeTypeRegistry()
        node_registry.register(
            NodeType(
                id="test-node",
                domain="test",
                label="Test Node",
                description="Mock test node",
            )
        )

        engine = GraphExecutionEngine(worker_registry, node_registry)

        # 20 parallel nodes
        num_nodes = 20
        graph = Graph(
            id="test",
            name="Large Parallel",
            nodes=[
                GraphNode(id=f"n{i}", node_type="test-node", label=f"Node {i}")
                for i in range(num_nodes)
            ],
        )

        start = time.monotonic()
        results = await engine.execute(graph, run_id="run-1")
        duration = time.monotonic() - start

        # All nodes executed
        assert len(results) == num_nodes
        assert all(r.error is None for r in results)

        # Should take ~0.05s (parallel), not ~1.0s (sequential)
        assert duration < 0.15, f"Expected parallel execution (~0.05s), got {duration}s"
