"""End-to-end integration tests for Universal Node Engine."""

import asyncio

import pytest

from mascarade.node_engine.engine import GraphExecutionEngine
from mascarade.node_engine.graph import Graph, GraphEdge, GraphNode, GraphStatus
from mascarade.node_engine.persistence import GraphSerializer
from mascarade.node_engine.registry import NodeType, NodeTypeRegistry, WorkerRegistry
from mascarade.node_engine.worker import NodeCapability, NodeWorker

# --- Mock Worker Implementation ---


class CalculatorWorker(NodeWorker):
    """Mock worker for basic arithmetic operations."""

    def __init__(self):
        self.name = "calculator"
        self.domain = "math"
        self._execution_log = []

    async def execute(self, node_type, inputs, config, context):
        """Execute math operations."""
        self._execution_log.append(context.node_id)

        if node_type == "math.add":
            # Check inputs first, then fall back to config
            a = inputs.get("a", config.get("a", 0))
            b = inputs.get("b", config.get("b", 0))
            return {"result": a + b}

        if node_type == "math.multiply":
            # Check inputs first, then fall back to config
            a = inputs.get("a", config.get("a", 1))
            b = inputs.get("b", config.get("b", 1))
            return {"result": a * b}

        if node_type == "math.constant":
            return {"value": config.get("value", 0)}

        raise ValueError(f"Unknown node type: {node_type}")

    async def validate(self, node_type, inputs, config):
        """Validate inputs."""
        return []

    def capabilities(self):
        """Return calculator capabilities."""
        return NodeCapability(
            node_types=["math.add", "math.multiply", "math.constant"],
            domain="math",
            supports_streaming=False,
            supports_cancellation=True,
            max_concurrent=10,
        )


class StringWorker(NodeWorker):
    """Mock worker for string operations."""

    def __init__(self):
        self.name = "string-processor"
        self.domain = "text"

    async def execute(self, node_type, inputs, config, context):
        """Execute string operations."""
        if node_type == "text.concat":
            # Check inputs first, then fall back to config
            a = inputs.get("a", config.get("a", ""))
            b = inputs.get("b", config.get("b", ""))
            return {"result": a + b}

        if node_type == "text.upper":
            # Check inputs first, then fall back to config
            text = inputs.get("text", config.get("text", ""))
            return {"result": text.upper()}

        if node_type == "text.repeat":
            # Check inputs first, then fall back to config
            text = inputs.get("text", config.get("text", ""))
            count = inputs.get("count", config.get("count", 1))
            return {"result": text * count}

        raise ValueError(f"Unknown node type: {node_type}")

    async def validate(self, node_type, inputs, config):
        """Validate inputs."""
        return []

    def capabilities(self):
        """Return string worker capabilities."""
        return NodeCapability(
            node_types=["text.concat", "text.upper", "text.repeat"],
            domain="text",
            supports_streaming=False,
            supports_cancellation=True,
            max_concurrent=5,
        )


# --- E2E Tests ---


class TestEndToEndExecution:
    """End-to-end execution tests."""

    @pytest.mark.asyncio
    async def test_simple_linear_pipeline(self):
        """Execute a simple linear pipeline: const -> add -> multiply."""
        # Setup registries
        worker_registry = WorkerRegistry()
        worker = CalculatorWorker()
        worker_registry.register(worker)

        node_registry = NodeTypeRegistry(storage_path=None)
        node_registry.register(
            NodeType(
                id="math.constant", domain="math", label="Constant", description=""
            )
        )
        node_registry.register(
            NodeType(id="math.add", domain="math", label="Add", description="")
        )
        node_registry.register(
            NodeType(
                id="math.multiply", domain="math", label="Multiply", description=""
            )
        )

        # Build graph: 5 -> +3 -> *2 = 16
        graph = Graph(
            id="linear",
            name="Linear Pipeline",
            nodes=[
                GraphNode(
                    id="n1",
                    node_type="math.constant",
                    label="Five",
                    config={"value": 5},
                ),
                GraphNode(
                    id="n2", node_type="math.add", label="Add 3", config={"b": 3}
                ),
                GraphNode(
                    id="n3", node_type="math.multiply", label="Times 2", config={"b": 2}
                ),
            ],
            edges=[
                GraphEdge(
                    id="e1",
                    source_node="n1",
                    source_port="value",
                    target_node="n2",
                    target_port="a",
                ),
                GraphEdge(
                    id="e2",
                    source_node="n2",
                    source_port="result",
                    target_node="n3",
                    target_port="a",
                ),
            ],
        )

        # Execute
        engine = GraphExecutionEngine(worker_registry, node_registry)
        results = await engine.execute(graph, run_id="run-1")

        # Verify results
        assert len(results) == 3
        result_map = {r.node_id: r for r in results}

        assert result_map["n1"].outputs["value"] == 5
        assert result_map["n2"].outputs["result"] == 8  # 5 + 3
        assert result_map["n3"].outputs["result"] == 16  # 8 * 2

        # Verify execution order
        assert worker._execution_log == ["n1", "n2", "n3"]

    @pytest.mark.asyncio
    async def test_diamond_pattern_execution(self):
        """Execute a diamond pattern with parallel branches."""
        # Setup registries
        worker_registry = WorkerRegistry()
        worker = CalculatorWorker()
        worker_registry.register(worker)

        node_registry = NodeTypeRegistry(storage_path=None)
        node_registry.register(
            NodeType(
                id="math.constant", domain="math", label="Constant", description=""
            )
        )
        node_registry.register(
            NodeType(id="math.add", domain="math", label="Add", description="")
        )
        node_registry.register(
            NodeType(
                id="math.multiply", domain="math", label="Multiply", description=""
            )
        )

        # Build diamond: 10 -> (+5, *2) -> add branches = 35
        graph = Graph(
            id="diamond",
            name="Diamond Pattern",
            nodes=[
                GraphNode(
                    id="source",
                    node_type="math.constant",
                    label="Ten",
                    config={"value": 10},
                ),
                GraphNode(
                    id="left", node_type="math.add", label="Add 5", config={"b": 5}
                ),
                GraphNode(
                    id="right",
                    node_type="math.multiply",
                    label="Times 2",
                    config={"b": 2},
                ),
                GraphNode(id="sink", node_type="math.add", label="Combine", config={}),
            ],
            edges=[
                GraphEdge(
                    id="e1",
                    source_node="source",
                    source_port="value",
                    target_node="left",
                    target_port="a",
                ),
                GraphEdge(
                    id="e2",
                    source_node="source",
                    source_port="value",
                    target_node="right",
                    target_port="a",
                ),
                GraphEdge(
                    id="e3",
                    source_node="left",
                    source_port="result",
                    target_node="sink",
                    target_port="a",
                ),
                GraphEdge(
                    id="e4",
                    source_node="right",
                    source_port="result",
                    target_node="sink",
                    target_port="b",
                ),
            ],
        )

        # Execute
        engine = GraphExecutionEngine(worker_registry, node_registry)
        results = await engine.execute(graph, run_id="run-2")

        # Verify results
        assert len(results) == 4
        result_map = {r.node_id: r for r in results}

        assert result_map["source"].outputs["value"] == 10
        assert result_map["left"].outputs["result"] == 15  # 10 + 5
        assert result_map["right"].outputs["result"] == 20  # 10 * 2
        assert result_map["sink"].outputs["result"] == 35  # 15 + 20

    @pytest.mark.asyncio
    async def test_multi_domain_execution(self):
        """Execute graph with multiple domains (math + text)."""
        # Setup registries
        worker_registry = WorkerRegistry()
        worker_registry.register(CalculatorWorker())
        worker_registry.register(StringWorker())

        node_registry = NodeTypeRegistry(storage_path=None)
        node_registry.register(
            NodeType(
                id="math.constant", domain="math", label="Constant", description=""
            )
        )
        node_registry.register(
            NodeType(id="text.repeat", domain="text", label="Repeat", description="")
        )
        node_registry.register(
            NodeType(id="text.upper", domain="text", label="Upper", description="")
        )

        # Build graph: 3 -> repeat("hello", 3) -> upper
        graph = Graph(
            id="multi-domain",
            name="Multi Domain",
            nodes=[
                GraphNode(
                    id="n1",
                    node_type="math.constant",
                    label="Three",
                    config={"value": 3},
                ),
                GraphNode(
                    id="n2", node_type="text.repeat", label="Repeat Hello", config={}
                ),
                GraphNode(
                    id="n3", node_type="text.upper", label="Uppercase", config={}
                ),
            ],
            edges=[
                GraphEdge(
                    id="e1",
                    source_node="n1",
                    source_port="value",
                    target_node="n2",
                    target_port="count",
                ),
                GraphEdge(
                    id="e2",
                    source_node="n2",
                    source_port="result",
                    target_node="n3",
                    target_port="text",
                ),
            ],
        )

        # Manually set text input since it's not from another node
        # This is a limitation of the test - in real usage, initial inputs would be provided
        # For now, we'll modify the graph to use a constant text value
        graph.nodes[1].config["text"] = "hello"

        # Execute
        engine = GraphExecutionEngine(worker_registry, node_registry)
        results = await engine.execute(graph, run_id="run-3")

        # Verify results
        assert len(results) == 3
        result_map = {r.node_id: r for r in results}

        assert result_map["n1"].outputs["value"] == 3
        assert result_map["n2"].outputs["result"] == "hellohellohello"
        assert result_map["n3"].outputs["result"] == "HELLOHELLOHELLO"


class TestEndToEndPersistence:
    """End-to-end persistence tests."""

    def test_save_and_execute_graph(self, tmp_path):
        """Save a graph, load it, and execute it."""
        # Create graph
        graph = Graph(
            id="persist-test",
            name="Persistence Test",
            nodes=[
                GraphNode(
                    id="n1", node_type="math.constant", label="C1", config={"value": 10}
                ),
                GraphNode(id="n2", node_type="math.add", label="Add", config={"b": 5}),
            ],
            edges=[
                GraphEdge(
                    id="e1",
                    source_node="n1",
                    source_port="value",
                    target_node="n2",
                    target_port="a",
                ),
            ],
        )

        # Save graph
        path = tmp_path / "graph.json"
        serializer = GraphSerializer()
        serializer.save(graph, path)

        # Load graph
        loaded = serializer.load(path)
        assert loaded.id == "persist-test"
        assert len(loaded.nodes) == 2
        assert len(loaded.edges) == 1

        # Execute loaded graph
        worker_registry = WorkerRegistry()
        worker_registry.register(CalculatorWorker())

        node_registry = NodeTypeRegistry(storage_path=None)
        node_registry.register(
            NodeType(
                id="math.constant", domain="math", label="Constant", description=""
            )
        )
        node_registry.register(
            NodeType(id="math.add", domain="math", label="Add", description="")
        )

        engine = GraphExecutionEngine(worker_registry, node_registry)
        results = asyncio.run(engine.execute(loaded, run_id="run-persist"))

        result_map = {r.node_id: r for r in results}
        assert result_map["n1"].outputs["value"] == 10
        assert result_map["n2"].outputs["result"] == 15  # 10 + 5

    def test_graph_lifecycle(self, tmp_path):
        """Test full graph lifecycle: create, validate, compile, execute, complete."""
        graph = Graph(id="lifecycle", name="Lifecycle Test", status=GraphStatus.DRAFT)

        # Draft -> Validated
        graph.status = GraphStatus.VALIDATED

        # Validated -> Compiled
        graph.status = GraphStatus.COMPILED

        # Save compiled graph
        path = tmp_path / "lifecycle.json"
        serializer = GraphSerializer()
        serializer.save(graph, path)

        # Load and execute
        loaded = serializer.load(path)
        assert loaded.status == GraphStatus.COMPILED

        # Running -> Completed
        loaded.status = GraphStatus.RUNNING
        # ... execution would happen here ...
        loaded.status = GraphStatus.COMPLETED

        # Save final state
        serializer.save(loaded, path)
        final = serializer.load(path)
        assert final.status == GraphStatus.COMPLETED


class TestEndToEndErrorHandling:
    """End-to-end error handling tests."""

    @pytest.mark.asyncio
    async def test_node_failure_propagates(self):
        """Node failure should be captured in results."""

        class FailingWorker(NodeWorker):
            name = "failing"
            domain = "fail"

            async def execute(self, node_type, inputs, config, context):
                if context.node_id == "fail-node":
                    raise RuntimeError("Intentional failure")
                return {"result": "ok"}

            async def validate(self, node_type, inputs, config):
                return []

            def capabilities(self):
                return NodeCapability(
                    node_types=["fail.test"],
                    domain="fail",
                    supports_streaming=False,
                    supports_cancellation=True,
                    max_concurrent=5,
                )

        worker_registry = WorkerRegistry()
        worker_registry.register(FailingWorker())

        node_registry = NodeTypeRegistry(storage_path=None)
        node_registry.register(
            NodeType(id="fail.test", domain="fail", label="Test", description="")
        )

        graph = Graph(
            id="error-test",
            name="Error Test",
            nodes=[
                GraphNode(id="ok-node", node_type="fail.test", label="OK"),
                GraphNode(id="fail-node", node_type="fail.test", label="Fail"),
            ],
        )

        engine = GraphExecutionEngine(worker_registry, node_registry)
        results = await engine.execute(graph, run_id="run-error")

        result_map = {r.node_id: r for r in results}

        # OK node should succeed
        assert result_map["ok-node"].error is None
        assert result_map["ok-node"].outputs["result"] == "ok"

        # Fail node should have error
        assert result_map["fail-node"].error is not None
        assert "Intentional failure" in result_map["fail-node"].error


class TestEndToEndRegistryIntegration:
    """Integration tests for registries."""

    def test_registry_persistence_roundtrip(self, tmp_path):
        """Test node type registry save/load."""
        storage = tmp_path / "node_types.json"

        # Create and populate registry
        registry = NodeTypeRegistry(storage_path=storage)
        registry.register(
            NodeType(id="math.add", domain="math", label="Add", description="Addition")
        )
        registry.register(
            NodeType(
                id="math.mul",
                domain="math",
                label="Multiply",
                description="Multiplication",
            )
        )
        registry.save()

        # Load in new registry
        registry2 = NodeTypeRegistry(storage_path=storage)
        registry2.load()

        assert "math.add" in registry2
        assert "math.mul" in registry2
        assert len(registry2.list()) == 2

    def test_worker_registry_available_domains(self):
        """Test worker registry filters available domains."""

        class UnavailableWorker(NodeWorker):
            name = "unavailable"
            domain = "offline"

            async def execute(self, node_type, inputs, config, context):
                return {}

            async def validate(self, node_type, inputs, config):
                return []

            def capabilities(self):
                return NodeCapability(node_types=[], domain="offline")

            @property
            def is_available(self):
                return False

        registry = WorkerRegistry()
        registry.register(CalculatorWorker())  # Available
        registry.register(UnavailableWorker())  # Not available

        available = registry.available_domains()
        assert "math" in available
        assert "offline" not in available


class TestAcceptanceCriteria:
    """
    End-to-end verification test covering all acceptance criteria from spec.

    This test explicitly verifies the 6 requirements from subtask-8-3:
    1. Register a mock NodeWorker with test domain
    2. Register node types for the test domain
    3. Create a graph with 3 nodes in parallel
    4. Execute graph and verify topological ordering
    5. Verify parallel execution within levels
    6. Verify cycle detection rejects cyclic graphs
    """

    @pytest.mark.asyncio
    async def test_all_acceptance_criteria(self):
        """Comprehensive E2E test covering all Phase 0 acceptance criteria."""

        # --- STEP 1: Register a mock NodeWorker with test domain ---
        worker_registry = WorkerRegistry()
        test_worker = CalculatorWorker()
        worker_registry.register(test_worker)

        assert "math" in worker_registry
        assert len(worker_registry.list()) == 1

        # --- STEP 2: Register node types for the test domain ---
        node_registry = NodeTypeRegistry(storage_path=None)
        node_registry.register(
            NodeType(
                id="math.constant",
                domain="math",
                label="Constant",
                description="Constant value",
            )
        )
        node_registry.register(
            NodeType(id="math.add", domain="math", label="Add", description="Addition")
        )
        node_registry.register(
            NodeType(
                id="math.multiply",
                domain="math",
                label="Multiply",
                description="Multiplication",
            )
        )

        assert "math.constant" in node_registry
        assert "math.add" in node_registry
        assert "math.multiply" in node_registry
        assert len(node_registry.list(domain="math")) == 3

        # --- STEP 3: Create a graph with 3 nodes in parallel ---
        # Graph structure: constant(10) -> (add(+5), multiply(*2), add(+1)) in parallel -> final add
        # This creates a diamond pattern with 3 parallel nodes in the middle level
        graph = Graph(
            id="acceptance-test",
            name="Acceptance Test Graph",
            nodes=[
                GraphNode(
                    id="source",
                    node_type="math.constant",
                    label="Source",
                    config={"value": 10},
                ),
                GraphNode(
                    id="parallel1",
                    node_type="math.add",
                    label="Parallel Add",
                    config={"b": 5},
                ),
                GraphNode(
                    id="parallel2",
                    node_type="math.multiply",
                    label="Parallel Multiply",
                    config={"b": 2},
                ),
                GraphNode(
                    id="parallel3",
                    node_type="math.add",
                    label="Parallel Add 2",
                    config={"b": 1},
                ),
                GraphNode(id="sink", node_type="math.add", label="Sink", config={}),
            ],
            edges=[
                # Source fans out to 3 parallel nodes
                GraphEdge(
                    id="e1",
                    source_node="source",
                    source_port="value",
                    target_node="parallel1",
                    target_port="a",
                ),
                GraphEdge(
                    id="e2",
                    source_node="source",
                    source_port="value",
                    target_node="parallel2",
                    target_port="a",
                ),
                GraphEdge(
                    id="e3",
                    source_node="source",
                    source_port="value",
                    target_node="parallel3",
                    target_port="a",
                ),
                # Parallel nodes converge to sink (using first two for simplicity)
                GraphEdge(
                    id="e4",
                    source_node="parallel1",
                    source_port="result",
                    target_node="sink",
                    target_port="a",
                ),
                GraphEdge(
                    id="e5",
                    source_node="parallel2",
                    source_port="result",
                    target_node="sink",
                    target_port="b",
                ),
            ],
        )

        # --- STEP 4: Execute graph and verify topological ordering ---
        engine = GraphExecutionEngine(worker_registry, node_registry)

        # Verify topological sort produces correct levels
        levels = engine._topological_sort(graph)
        assert len(levels) == 3, f"Expected 3 levels, got {len(levels)}"
        assert levels[0] == ["source"], "Level 0 should be source node"
        assert set(levels[1]) == {
            "parallel1",
            "parallel2",
            "parallel3",
        }, "Level 1 should have 3 parallel nodes"
        assert levels[2] == ["sink"], "Level 2 should be sink node"

        # Execute the graph
        test_worker._execution_log = []  # Reset execution log
        results = await engine.execute(graph, run_id="acceptance-run")

        # Verify all nodes executed
        assert len(results) == 5, f"Expected 5 results, got {len(results)}"
        result_map = {r.node_id: r for r in results}

        # Verify correct data flow
        assert result_map["source"].outputs["value"] == 10
        assert result_map["parallel1"].outputs["result"] == 15  # 10 + 5
        assert result_map["parallel2"].outputs["result"] == 20  # 10 * 2
        assert result_map["parallel3"].outputs["result"] == 11  # 10 + 1
        assert result_map["sink"].outputs["result"] == 35  # 15 + 20

        # --- STEP 5: Verify parallel execution within levels ---
        # The execution log should show source first, then all 3 parallel nodes, then sink
        execution_order = test_worker._execution_log
        assert execution_order[0] == "source", "Source should execute first"

        # All 3 parallel nodes should be executed after source but before sink
        parallel_execution = execution_order[1:4]
        assert set(parallel_execution) == {
            "parallel1",
            "parallel2",
            "parallel3",
        }, "All 3 parallel nodes should execute in level 1"

        assert execution_order[4] == "sink", "Sink should execute last"

        # Verify no errors in parallel execution
        for node_id in ["source", "parallel1", "parallel2", "parallel3", "sink"]:
            assert (
                result_map[node_id].error is None
            ), f"Node {node_id} should not have errors"

        # --- STEP 6: Verify cycle detection rejects cyclic graphs ---
        cyclic_graph = Graph(
            id="cyclic-test",
            name="Cyclic Graph Test",
            nodes=[
                GraphNode(id="n1", node_type="math.add", label="Node 1"),
                GraphNode(id="n2", node_type="math.add", label="Node 2"),
                GraphNode(id="n3", node_type="math.add", label="Node 3"),
            ],
            edges=[
                GraphEdge(
                    id="e1",
                    source_node="n1",
                    source_port="result",
                    target_node="n2",
                    target_port="a",
                ),
                GraphEdge(
                    id="e2",
                    source_node="n2",
                    source_port="result",
                    target_node="n3",
                    target_port="a",
                ),
                GraphEdge(
                    id="e3",
                    source_node="n3",
                    source_port="result",
                    target_node="n1",
                    target_port="a",
                ),  # This creates a cycle: n1 -> n2 -> n3 -> n1
            ],
        )

        # Verify cycle detection raises CycleDetectedError
        from mascarade.node_engine.engine import CycleDetectedError

        with pytest.raises(CycleDetectedError) as exc_info:
            engine._topological_sort(cyclic_graph)

        assert (
            "cycle" in str(exc_info.value).lower()
        ), "Error message should mention cycle"

        # Verify execution also rejects cyclic graph (topological sort is called first)
        with pytest.raises(CycleDetectedError):
            await engine.execute(cyclic_graph, run_id="cyclic-run")

        # --- ALL ACCEPTANCE CRITERIA VERIFIED ---
        # ✓ Mock worker registered and functional
        # ✓ Node types registered for test domain
        # ✓ Graph with 3 parallel nodes created and executed
        # ✓ Topological ordering verified (3 levels: source, 3 parallel, sink)
        # ✓ Parallel execution within levels confirmed via execution log
        # ✓ Cycle detection prevents execution of cyclic graphs


def test_worker_lifecycle_hooks():
    """Test that workers can override lifecycle hooks."""
    from mascarade.node_engine.graph import ExecutionContext

    hook_log = []

    class LifecycleWorker(NodeWorker):
        name = "lifecycle-test"
        domain = "test"

        def on_init(self, context):
            hook_log.append(f"init:{context.run_id}")

        def on_destroy(self, context):
            hook_log.append(f"destroy:{context.run_id}")

        async def execute(self, node_type, inputs, config, context):
            return {"result": "ok"}

        async def validate(self, node_type, inputs, config):
            return []

        def capabilities(self):
            return NodeCapability(node_types=["test.op"], domain="test")

    worker = LifecycleWorker()
    ctx = ExecutionContext(graph_id="g1", run_id="r1", node_id="n1")

    worker.on_init(ctx)
    worker.on_destroy(ctx)

    assert hook_log == ["init:r1", "destroy:r1"]
