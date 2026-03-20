"""Tests for graph runtime execution."""

import asyncio

import pytest

from mascarade.node_engine.graph import Edge, Graph, Node
from mascarade.node_engine.runtime import (
    ExecutionStatus,
    GraphExecutionContext,
    GraphRuntime,
    NodeResult,
)
from mascarade.node_engine.worker import NodeWorker


class MockWorker(NodeWorker):
    """Mock worker for testing."""

    name = "mock-worker"
    domain = "test"

    def __init__(self, node_types=None, should_fail=False):
        self.node_types = node_types or ["test.echo", "test.transform"]
        self.should_fail = should_fail
        self.execution_count = 0
        self.validation_count = 0

    async def execute(self, node_type, inputs, config, context):
        """Execute a test node."""
        self.execution_count += 1

        if self.should_fail:
            raise RuntimeError("Mock worker failure")

        # Echo node: pass through input
        if node_type == "test.echo":
            return {"output": inputs.get("input", "")}

        # Transform node: uppercase the input
        if node_type == "test.transform":
            return {"output": inputs.get("input", "").upper()}

        raise ValueError(f"Unknown node type: {node_type}")

    async def validate(self, node_type, inputs, config):
        """Validate test node inputs."""
        self.validation_count += 1
        errors = []

        if node_type not in self.node_types:
            errors.append(f"Unsupported node type: {node_type}")

        if node_type == "test.echo" and "input" not in inputs:
            errors.append("Missing required input: input")

        if node_type == "test.transform" and "input" not in inputs:
            errors.append("Missing required input: input")

        return errors

    def capabilities(self):
        """Return worker capabilities."""
        return {
            "node_types": self.node_types,
            "domain": self.domain,
            "supports_streaming": False,
            "max_concurrent": 10,
        }

    @property
    def is_available(self):
        """Worker is always available for testing."""
        return True


class UnavailableWorker(MockWorker):
    """Mock worker that is unavailable."""

    @property
    def is_available(self):
        return False


def test_runtime_initialization():
    """Test runtime initialization."""
    runtime = GraphRuntime()
    assert len(runtime.workers) == 0
    assert runtime.max_concurrent == 10
    assert runtime.execution_timeout_s == 300.0


def test_register_worker():
    """Test registering a worker."""
    runtime = GraphRuntime()
    worker = MockWorker()

    runtime.register_worker(worker)
    assert "test" in runtime.workers
    assert runtime.get_worker("test") == worker


def test_register_worker_overwrite():
    """Test overwriting a worker registration."""
    runtime = GraphRuntime()
    worker1 = MockWorker()
    worker2 = MockWorker()

    runtime.register_worker(worker1)
    runtime.register_worker(worker2)  # Should overwrite

    assert runtime.get_worker("test") == worker2


def test_get_worker():
    """Test getting a worker by domain."""
    runtime = GraphRuntime()
    worker = MockWorker()
    runtime.register_worker(worker)

    assert runtime.get_worker("test") == worker
    assert runtime.get_worker("nonexistent") is None


def test_list_workers():
    """Test listing all workers."""
    runtime = GraphRuntime()
    worker1 = MockWorker()
    worker1.domain = "test1"
    worker2 = MockWorker()
    worker2.domain = "test2"

    runtime.register_worker(worker1)
    runtime.register_worker(worker2)

    workers = runtime.list_workers()
    assert len(workers) == 2
    domains = {w["domain"] for w in workers}
    assert domains == {"test1", "test2"}


def test_validate_graph_missing_worker():
    """Test validation fails when worker is missing."""
    runtime = GraphRuntime()
    graph = Graph(nodes=[Node(id="n1", type="test.echo")])

    errors = asyncio.run(runtime.validate_graph(graph))
    assert len(errors) > 0
    assert any("no worker registered" in e.lower() for e in errors)


def test_validate_graph_unavailable_worker():
    """Test validation fails when worker is unavailable."""
    runtime = GraphRuntime()
    worker = UnavailableWorker()
    runtime.register_worker(worker)

    graph = Graph(nodes=[Node(id="n1", type="test.echo")])

    errors = asyncio.run(runtime.validate_graph(graph))
    assert len(errors) > 0
    assert any("not available" in e.lower() for e in errors)


def test_validate_graph_unsupported_node_type():
    """Test validation fails when worker doesn't support node type."""
    runtime = GraphRuntime()
    worker = MockWorker(node_types=["test.echo"])
    runtime.register_worker(worker)

    graph = Graph(nodes=[Node(id="n1", type="test.unsupported")])

    errors = asyncio.run(runtime.validate_graph(graph))
    assert len(errors) > 0
    assert any("does not support it" in e for e in errors)


def test_validate_graph_missing_input():
    """Test validation fails when required inputs are missing."""
    runtime = GraphRuntime()
    worker = MockWorker()
    runtime.register_worker(worker)

    graph = Graph(nodes=[Node(id="n1", type="test.echo", inputs={})])

    errors = asyncio.run(runtime.validate_graph(graph))
    assert len(errors) > 0
    assert any("Missing required input" in e for e in errors)


def test_validate_graph_success():
    """Test validation succeeds for valid graph."""
    runtime = GraphRuntime()
    worker = MockWorker()
    runtime.register_worker(worker)

    graph = Graph(nodes=[Node(id="n1", type="test.echo", inputs={"input": "hello"})])

    errors = asyncio.run(runtime.validate_graph(graph))
    assert len(errors) == 0


def test_execute_single_node():
    """Test executing a single node."""
    runtime = GraphRuntime()
    worker = MockWorker()
    runtime.register_worker(worker)

    graph = Graph(
        nodes=[Node(id="n1", type="test.echo", inputs={"input": "hello"})],
        metadata={"id": "test-graph"},
    )

    context = asyncio.run(runtime.execute(graph))

    assert context.status == ExecutionStatus.COMPLETED
    assert len(context.node_results) == 1
    assert context.node_results["n1"].status == ExecutionStatus.COMPLETED
    assert context.node_results["n1"].outputs["output"] == "hello"
    assert worker.execution_count == 1


def test_execute_chain():
    """Test executing a chain of nodes."""
    runtime = GraphRuntime()
    worker = MockWorker()
    runtime.register_worker(worker)

    graph = Graph(
        nodes=[
            Node(id="n1", type="test.echo", inputs={"input": "hello"}),
            Node(id="n2", type="test.transform", inputs={}),  # Input from edge
        ],
        edges=[
            Edge(from_node="n1", from_port="output", to_node="n2", to_port="input"),
        ],
    )

    context = asyncio.run(runtime.execute(graph))

    assert context.status == ExecutionStatus.COMPLETED
    assert len(context.node_results) == 2
    assert context.node_results["n1"].outputs["output"] == "hello"
    assert context.node_results["n2"].outputs["output"] == "HELLO"
    assert worker.execution_count == 2


def test_execute_topological_order():
    """Test nodes are executed in topological order."""
    runtime = GraphRuntime()
    worker = MockWorker()
    runtime.register_worker(worker)

    graph = Graph(
        nodes=[
            Node(id="n3", type="test.transform", inputs={}),
            Node(id="n1", type="test.echo", inputs={"input": "start"}),
            Node(id="n2", type="test.echo", inputs={}),
        ],
        edges=[
            Edge(from_node="n1", from_port="output", to_node="n2", to_port="input"),
            Edge(from_node="n2", from_port="output", to_node="n3", to_port="input"),
        ],
    )

    context = asyncio.run(runtime.execute(graph))

    assert context.status == ExecutionStatus.COMPLETED
    # All nodes should execute successfully
    assert all(
        r.status == ExecutionStatus.COMPLETED for r in context.node_results.values()
    )


def test_execute_validation_error():
    """Test execution fails on validation error."""
    runtime = GraphRuntime()
    worker = MockWorker()
    runtime.register_worker(worker)

    graph = Graph(nodes=[Node(id="n1", type="test.echo", inputs={})])  # Missing input

    with pytest.raises(ValueError) as exc_info:
        asyncio.run(runtime.execute(graph))
    assert "validation failed" in str(exc_info.value).lower()


def test_execute_node_failure():
    """Test execution fails when a node fails."""
    runtime = GraphRuntime()
    worker = MockWorker(should_fail=True)
    runtime.register_worker(worker)

    graph = Graph(nodes=[Node(id="n1", type="test.echo", inputs={"input": "test"})])

    context = asyncio.run(runtime.execute(graph))

    assert context.status == ExecutionStatus.FAILED
    assert context.node_results["n1"].status == ExecutionStatus.FAILED
    assert "Mock worker failure" in context.node_results["n1"].error


def test_execute_node_standalone():
    """Test execute_node convenience method."""
    runtime = GraphRuntime()
    worker = MockWorker()
    runtime.register_worker(worker)

    outputs = asyncio.run(
        runtime.execute_node(
            node_type="test.echo",
            inputs={"input": "hello"},
            config={},
        )
    )

    assert outputs["output"] == "hello"
    assert worker.execution_count == 1


def test_execute_node_invalid_type():
    """Test execute_node fails with invalid node type."""
    runtime = GraphRuntime()

    with pytest.raises(ValueError) as exc_info:
        asyncio.run(
            runtime.execute_node(
                node_type="invalid",  # No domain
                inputs={},
            )
        )
    assert "fully qualified" in str(exc_info.value)


def test_execute_node_no_worker():
    """Test execute_node fails when worker is missing."""
    runtime = GraphRuntime()

    with pytest.raises(ValueError) as exc_info:
        asyncio.run(
            runtime.execute_node(
                node_type="test.echo",
                inputs={"input": "hello"},
            )
        )
    assert "No worker registered" in str(exc_info.value)


def test_execute_node_validation_failure():
    """Test execute_node fails on validation error."""
    runtime = GraphRuntime()
    worker = MockWorker()
    runtime.register_worker(worker)

    with pytest.raises(ValueError) as exc_info:
        asyncio.run(
            runtime.execute_node(
                node_type="test.echo",
                inputs={},  # Missing required input
            )
        )
    assert "validation failed" in str(exc_info.value).lower()


def test_node_result_dataclass():
    """Test NodeResult dataclass."""
    result = NodeResult(
        node_id="n1",
        status=ExecutionStatus.COMPLETED,
        outputs={"output": "test"},
        worker_name="test-worker",
        execution_time_ms=123.45,
    )

    assert result.node_id == "n1"
    assert result.status == ExecutionStatus.COMPLETED
    assert result.outputs["output"] == "test"
    assert result.worker_name == "test-worker"
    assert result.execution_time_ms == 123.45
    assert result.error is None


def test_graph_execution_context_dataclass():
    """Test GraphExecutionContext dataclass."""
    context = GraphExecutionContext(
        graph_id="test-graph",
        status=ExecutionStatus.RUNNING,
        metadata={"version": "1.0"},
    )

    assert context.graph_id == "test-graph"
    assert context.status == ExecutionStatus.RUNNING
    assert context.metadata["version"] == "1.0"
    assert len(context.node_results) == 0


def test_execution_status_enum():
    """Test ExecutionStatus enum values."""
    assert ExecutionStatus.PENDING == "pending"
    assert ExecutionStatus.RUNNING == "running"
    assert ExecutionStatus.COMPLETED == "completed"
    assert ExecutionStatus.FAILED == "failed"
    assert ExecutionStatus.CANCELLED == "cancelled"


def test_execute_multiple_incoming_edges():
    """Test node with multiple incoming edges."""
    runtime = GraphRuntime()

    class JoinWorker(NodeWorker):
        name = "join-worker"
        domain = "test"

        async def execute(self, node_type, inputs, config, context):
            # Concatenate inputs
            return {"output": inputs.get("in1", "") + inputs.get("in2", "")}

        async def validate(self, node_type, inputs, config):
            return []

        def capabilities(self):
            return {"node_types": ["test.join"], "domain": "test"}

    runtime.register_worker(JoinWorker())

    graph = Graph(
        nodes=[
            Node(id="n1", type="test.join", inputs={"in1": "A"}),
            Node(id="n2", type="test.join", inputs={"in1": "B"}),
            Node(id="n3", type="test.join", inputs={}),
        ],
        edges=[
            Edge(from_node="n1", from_port="output", to_node="n3", to_port="in1"),
            Edge(from_node="n2", from_port="output", to_node="n3", to_port="in2"),
        ],
    )

    context = asyncio.run(runtime.execute(graph))

    assert context.status == ExecutionStatus.COMPLETED
    assert context.node_results["n3"].outputs["output"] == "AB"
