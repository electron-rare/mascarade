"""End-to-end integration tests for Universal Node Engine."""

import asyncio
from pathlib import Path

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
            a = inputs.get("a", 0)
            b = inputs.get("b", 0)
            return {"result": a + b}

        if node_type == "math.multiply":
            a = inputs.get("a", 1)
            b = inputs.get("b", 1)
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
            a = inputs.get("a", "")
            b = inputs.get("b", "")
            return {"result": a + b}

        if node_type == "text.upper":
            text = inputs.get("text", "")
            return {"result": text.upper()}

        if node_type == "text.repeat":
            text = inputs.get("text", "")
            count = inputs.get("count", 1)
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
            NodeType(id="math.constant", domain="math", label="Constant", description="")
        )
        node_registry.register(
            NodeType(id="math.add", domain="math", label="Add", description="")
        )
        node_registry.register(
            NodeType(id="math.multiply", domain="math", label="Multiply", description="")
        )

        # Build graph: 5 -> +3 -> *2 = 16
        graph = Graph(
            id="linear",
            name="Linear Pipeline",
            nodes=[
                GraphNode(id="n1", node_type="math.constant", label="Five", config={"value": 5}),
                GraphNode(id="n2", node_type="math.add", label="Add 3", config={"b": 3}),
                GraphNode(id="n3", node_type="math.multiply", label="Times 2", config={"b": 2}),
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
            NodeType(id="math.constant", domain="math", label="Constant", description="")
        )
        node_registry.register(
            NodeType(id="math.add", domain="math", label="Add", description="")
        )
        node_registry.register(
            NodeType(id="math.multiply", domain="math", label="Multiply", description="")
        )

        # Build diamond: 10 -> (+5, *2) -> add branches = 35
        graph = Graph(
            id="diamond",
            name="Diamond Pattern",
            nodes=[
                GraphNode(id="source", node_type="math.constant", label="Ten", config={"value": 10}),
                GraphNode(id="left", node_type="math.add", label="Add 5", config={"b": 5}),
                GraphNode(id="right", node_type="math.multiply", label="Times 2", config={"b": 2}),
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
            NodeType(id="math.constant", domain="math", label="Constant", description="")
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
                GraphNode(id="n1", node_type="math.constant", label="Three", config={"value": 3}),
                GraphNode(id="n2", node_type="text.repeat", label="Repeat Hello", config={}),
                GraphNode(id="n3", node_type="text.upper", label="Uppercase", config={}),
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
                GraphNode(id="n1", node_type="math.constant", label="C1", config={"value": 10}),
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
            NodeType(id="math.constant", domain="math", label="Constant", description="")
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
            NodeType(id="math.mul", domain="math", label="Multiply", description="Multiplication")
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
