"""Tests for the Graph Executor."""

import asyncio

from mascarade.node_engine.base import (
    NodeDefinition,
    NodeExecutionContext,
    NodeExecutionResult,
    NodeWorker,
)
from mascarade.node_engine.executor import (
    ExecutionStatus,
    GraphExecutor,
)
from mascarade.node_engine.graph import (
    Connection,
    Graph,
    NodeInstance,
)
from mascarade.node_engine.types import (
    PortDirection,
    PrimitiveType,
    primitive_port,
)


class MockWorker(NodeWorker):
    """Mock worker for testing."""

    domain = "test"

    def __init__(self, nodes: list[NodeDefinition] | None = None):
        self.nodes = nodes or []
        self.execution_log: list[str] = []
        self.initialized = False
        self.shutdown_called = False

    def register_nodes(self) -> list[NodeDefinition]:
        return self.nodes

    async def execute_node(
        self,
        node_def: NodeDefinition,
        context: NodeExecutionContext,
    ) -> NodeExecutionResult:
        self.execution_log.append(context.node_id)

        if node_def.node_type == "test.simple.add":
            a = context.get_input("a", 0)
            b = context.get_input("b", 0)
            return NodeExecutionResult.ok(sum=a + b)

        if node_def.node_type == "test.simple.multiply":
            value = context.get_input("value", 1)
            factor = context.get_input("factor", 1)
            return NodeExecutionResult.ok(result=value * factor)

        if node_def.node_type == "test.simple.constant":
            value = context.config.get("value", 42)
            return NodeExecutionResult.ok(output=value)

        if node_def.node_type == "test.error.fail":
            return NodeExecutionResult.error("Test error", "TestError")

        if node_def.node_type == "test.capability.requires":
            context.require_capability("test_capability")
            return NodeExecutionResult.ok(output="ok")

        return NodeExecutionResult.error(f"Unknown node type: {node_def.node_type}")

    async def initialize(self) -> None:
        self.initialized = True

    async def shutdown(self) -> None:
        self.shutdown_called = True


def _make_simple_add_node() -> NodeDefinition:
    """Create a simple addition node definition."""
    return NodeDefinition(
        node_type="test.simple.add",
        description="Add two numbers",
        input_ports=[
            primitive_port(
                "a",
                PortDirection.INPUT,
                PrimitiveType.INTEGER,
                optional=True,
                default_value=0,
            ),
            primitive_port(
                "b",
                PortDirection.INPUT,
                PrimitiveType.INTEGER,
                optional=True,
                default_value=0,
            ),
        ],
        output_ports=[
            primitive_port("sum", PortDirection.OUTPUT, PrimitiveType.INTEGER),
        ],
    )


def _make_multiply_node() -> NodeDefinition:
    """Create a simple multiplication node definition."""
    return NodeDefinition(
        node_type="test.simple.multiply",
        description="Multiply value by factor",
        input_ports=[
            primitive_port("value", PortDirection.INPUT, PrimitiveType.INTEGER),
            primitive_port("factor", PortDirection.INPUT, PrimitiveType.INTEGER),
        ],
        output_ports=[
            primitive_port("result", PortDirection.OUTPUT, PrimitiveType.INTEGER),
        ],
    )


def _make_constant_node() -> NodeDefinition:
    """Create a constant output node definition."""
    return NodeDefinition(
        node_type="test.simple.constant",
        description="Output a constant value",
        input_ports=[],
        output_ports=[
            primitive_port("output", PortDirection.OUTPUT, PrimitiveType.INTEGER),
        ],
    )


def _make_executor_with_worker(worker: MockWorker) -> GraphExecutor:
    """Create an executor with a mock worker."""
    executor = GraphExecutor()
    executor.register_worker(worker)
    return executor


def test_register_worker():
    """Test registering a worker with the executor."""
    node_def = _make_simple_add_node()
    worker = MockWorker(nodes=[node_def])
    executor = GraphExecutor()

    executor.register_worker(worker)

    assert "test" in executor._workers
    assert "test.simple.add" in executor._node_definitions


def test_initialize_workers():
    """Test initializing all registered workers."""
    worker = MockWorker()
    executor = _make_executor_with_worker(worker)

    asyncio.run(executor.initialize_workers())

    assert worker.initialized


def test_shutdown_workers():
    """Test shutting down all registered workers."""
    worker = MockWorker()
    executor = _make_executor_with_worker(worker)

    asyncio.run(executor.shutdown_workers())

    assert worker.shutdown_called


def test_validate_graph_success():
    """Test validating a valid graph."""
    node_def = _make_simple_add_node()
    worker = MockWorker(nodes=[node_def])
    executor = _make_executor_with_worker(worker)

    graph = Graph(
        graph_id="test-graph",
        nodes=[
            NodeInstance(node_id="add1", node_type="test.simple.add"),
        ],
    )

    errors = executor.validate_graph(graph)

    assert len(errors) == 0


def test_validate_graph_unknown_node_type():
    """Test validating a graph with unknown node type."""
    worker = MockWorker(nodes=[])
    executor = _make_executor_with_worker(worker)

    graph = Graph(
        graph_id="test-graph",
        nodes=[
            NodeInstance(node_id="unknown", node_type="unknown.node.type"),
        ],
    )

    errors = executor.validate_graph(graph)

    assert len(errors) > 0
    assert any("unknown type" in err for err in errors)


def test_validate_graph_missing_required_input():
    """Test validating a graph with missing required input."""
    node_def = _make_multiply_node()
    worker = MockWorker(nodes=[node_def])
    executor = _make_executor_with_worker(worker)

    graph = Graph(
        graph_id="test-graph",
        nodes=[
            NodeInstance(node_id="mult1", node_type="test.simple.multiply"),
        ],
    )

    errors = executor.validate_graph(graph)

    assert len(errors) > 0
    assert any("missing required input" in err.lower() for err in errors)


def test_execute_single_node():
    """Test executing a graph with a single node."""
    node_def = _make_constant_node()
    worker = MockWorker(nodes=[node_def])
    executor = _make_executor_with_worker(worker)

    graph = Graph(
        graph_id="test-graph",
        nodes=[
            NodeInstance(
                node_id="const1",
                node_type="test.simple.constant",
                config={"value": 100},
            ),
        ],
    )

    result = asyncio.run(executor.execute_graph(graph))

    assert result.status == ExecutionStatus.COMPLETED
    assert result.graph_id == "test-graph"
    assert "const1" in result.outputs
    assert result.outputs["const1"]["output"] == 100


def test_execute_linear_chain():
    """Test executing a linear chain of nodes."""
    add_node = _make_simple_add_node()
    multiply_node = _make_multiply_node()
    worker = MockWorker(nodes=[add_node, multiply_node])
    executor = _make_executor_with_worker(worker)

    # Graph: add(5, 3) -> multiply(result, 2)
    graph = Graph(
        graph_id="test-graph",
        nodes=[
            NodeInstance(
                node_id="add1",
                node_type="test.simple.add",
                config={"a": 5, "b": 3},
            ),
            NodeInstance(
                node_id="mult1",
                node_type="test.simple.multiply",
                config={"factor": 2},
            ),
        ],
        connections=[
            Connection(
                connection_id="conn1",
                source_node_id="add1",
                source_port="sum",
                target_node_id="mult1",
                target_port="value",
            ),
        ],
    )

    result = asyncio.run(executor.execute_graph(graph))

    assert result.status == ExecutionStatus.COMPLETED
    assert worker.execution_log == ["add1", "mult1"]

    # Check node execution records
    add_record = result.get_node_record("add1")
    assert add_record is not None
    assert add_record.status == ExecutionStatus.COMPLETED
    assert add_record.outputs["sum"] == 8

    mult_record = result.get_node_record("mult1")
    assert mult_record is not None
    assert mult_record.status == ExecutionStatus.COMPLETED
    assert mult_record.outputs["result"] == 16


def test_execute_parallel_nodes():
    """Test executing independent nodes in parallel."""
    add_node = _make_simple_add_node()
    worker = MockWorker(nodes=[add_node])
    executor = _make_executor_with_worker(worker)

    # Two independent add nodes
    graph = Graph(
        graph_id="test-graph",
        nodes=[
            NodeInstance(
                node_id="add1",
                node_type="test.simple.add",
                config={"a": 1, "b": 2},
            ),
            NodeInstance(
                node_id="add2",
                node_type="test.simple.add",
                config={"a": 10, "b": 20},
            ),
        ],
    )

    result = asyncio.run(executor.execute_graph(graph))

    assert result.status == ExecutionStatus.COMPLETED
    assert len(worker.execution_log) == 2
    assert "add1" in worker.execution_log
    assert "add2" in worker.execution_log


def test_execute_node_with_error():
    """Test executing a node that returns an error."""
    error_node = NodeDefinition(
        node_type="test.error.fail",
        description="Always fails",
        input_ports=[],
        output_ports=[],
    )
    worker = MockWorker(nodes=[error_node])
    executor = _make_executor_with_worker(worker)

    graph = Graph(
        graph_id="test-graph",
        nodes=[
            NodeInstance(node_id="fail1", node_type="test.error.fail"),
        ],
    )

    result = asyncio.run(executor.execute_graph(graph))

    assert result.status == ExecutionStatus.FAILED
    assert result.error is not None

    fail_record = result.get_node_record("fail1")
    assert fail_record is not None
    assert fail_record.status == ExecutionStatus.FAILED
    assert "Test error" in fail_record.error
    assert fail_record.error_type == "TestError"


def test_execute_with_timeout():
    """Test executing a graph with timeout."""

    class SlowWorker(MockWorker):
        async def execute_node(self, node_def, context):
            await asyncio.sleep(5.0)  # Sleep longer than timeout
            return NodeExecutionResult.ok(output="done")

    node_def = _make_constant_node()
    worker = SlowWorker(nodes=[node_def])
    executor = _make_executor_with_worker(worker)

    graph = Graph(
        graph_id="test-graph",
        nodes=[
            NodeInstance(node_id="slow1", node_type="test.simple.constant"),
        ],
    )

    result = asyncio.run(executor.execute_graph(graph, timeout_seconds=0.1))

    assert result.status == ExecutionStatus.TIMEOUT
    assert "timed out" in result.error.lower()


def test_execute_with_capabilities():
    """Test executing a node that requires capabilities."""
    capability_node = NodeDefinition(
        node_type="test.capability.requires",
        description="Requires capability",
        input_ports=[],
        output_ports=[
            primitive_port("output", PortDirection.OUTPUT, PrimitiveType.STRING),
        ],
    )
    worker = MockWorker(nodes=[capability_node])
    executor = _make_executor_with_worker(worker)

    graph = Graph(
        graph_id="test-graph",
        nodes=[
            NodeInstance(node_id="cap1", node_type="test.capability.requires"),
        ],
    )

    # Execute with capability granted
    result = asyncio.run(
        executor.execute_graph(graph, capabilities={"test_capability"})
    )

    assert result.status == ExecutionStatus.COMPLETED


def test_execute_without_required_capability():
    """Test executing a node that requires capabilities without granting them."""
    capability_node = NodeDefinition(
        node_type="test.capability.requires",
        description="Requires capability",
        input_ports=[],
        output_ports=[],
    )
    worker = MockWorker(nodes=[capability_node])
    executor = _make_executor_with_worker(worker)

    graph = Graph(
        graph_id="test-graph",
        nodes=[
            NodeInstance(node_id="cap1", node_type="test.capability.requires"),
        ],
    )

    # Execute without capability
    result = asyncio.run(executor.execute_graph(graph, capabilities=set()))

    assert result.status == ExecutionStatus.FAILED
    assert "test_capability" in str(result.error)


def test_topological_sort():
    """Test topological sorting of nodes."""
    add_node = _make_simple_add_node()
    multiply_node = _make_multiply_node()
    worker = MockWorker(nodes=[add_node, multiply_node])
    executor = _make_executor_with_worker(worker)

    # Graph: mult1 depends on add1
    graph = Graph(
        graph_id="test-graph",
        nodes=[
            NodeInstance(node_id="mult1", node_type="test.simple.multiply"),
            NodeInstance(node_id="add1", node_type="test.simple.add"),
        ],
        connections=[
            Connection(
                connection_id="conn1",
                source_node_id="add1",
                source_port="sum",
                target_node_id="mult1",
                target_port="value",
            ),
        ],
    )

    sorted_nodes = executor._topological_sort(graph)

    # add1 should come before mult1
    node_ids = [node.node_id for node in sorted_nodes]
    assert node_ids.index("add1") < node_ids.index("mult1")


def test_topological_sort_with_cycle():
    """Test topological sort detects cycles."""
    add_node = _make_simple_add_node()
    worker = MockWorker(nodes=[add_node])
    executor = _make_executor_with_worker(worker)

    # Create a cycle: node1 -> node2 -> node1
    graph = Graph(
        graph_id="test-graph",
        nodes=[
            NodeInstance(node_id="node1", node_type="test.simple.add"),
            NodeInstance(node_id="node2", node_type="test.simple.add"),
        ],
        connections=[
            Connection(
                connection_id="conn1",
                source_node_id="node1",
                source_port="sum",
                target_node_id="node2",
                target_port="a",
            ),
            Connection(
                connection_id="conn2",
                source_node_id="node2",
                source_port="sum",
                target_node_id="node1",
                target_port="a",
            ),
        ],
    )

    # Should detect cycle during validation
    errors = executor.validate_graph(graph)
    assert any("cycle" in err.lower() for err in errors)


def test_collect_node_inputs_from_connections():
    """Test collecting node inputs from connections."""
    add_node = _make_simple_add_node()
    worker = MockWorker(nodes=[add_node])
    executor = _make_executor_with_worker(worker)

    graph = Graph(
        graph_id="test-graph",
        nodes=[
            NodeInstance(node_id="src", node_type="test.simple.add"),
            NodeInstance(node_id="dst", node_type="test.simple.add"),
        ],
        connections=[
            Connection(
                connection_id="conn1",
                source_node_id="src",
                source_port="sum",
                target_node_id="dst",
                target_port="a",
            ),
        ],
    )

    node_outputs = {"src": {"sum": 42}}
    node_def = add_node
    node_instance = graph.get_node("dst")

    inputs = executor._collect_node_inputs(graph, node_instance, node_outputs, node_def)

    assert inputs["a"] == 42


def test_collect_node_inputs_from_config():
    """Test collecting node inputs from config defaults."""
    add_node = _make_simple_add_node()
    worker = MockWorker(nodes=[add_node])
    executor = _make_executor_with_worker(worker)

    graph = Graph(
        graph_id="test-graph",
        nodes=[
            NodeInstance(
                node_id="add1",
                node_type="test.simple.add",
                config={"a": 10, "b": 20},
            ),
        ],
    )

    node_outputs = {}
    node_def = add_node
    node_instance = graph.get_node("add1")

    inputs = executor._collect_node_inputs(graph, node_instance, node_outputs, node_def)

    assert inputs["a"] == 10
    assert inputs["b"] == 20


def test_execution_timing():
    """Test that execution records include timing information."""
    node_def = _make_constant_node()
    worker = MockWorker(nodes=[node_def])
    executor = _make_executor_with_worker(worker)

    graph = Graph(
        graph_id="test-graph",
        nodes=[
            NodeInstance(node_id="const1", node_type="test.simple.constant"),
        ],
    )

    result = asyncio.run(executor.execute_graph(graph))

    assert result.start_time_ms > 0
    assert result.end_time_ms >= result.start_time_ms
    assert result.total_time_ms >= 0

    node_record = result.get_node_record("const1")
    assert node_record.execution_time_ms >= 0


def test_get_node_record_missing():
    """Test getting a non-existent node record."""
    node_def = _make_constant_node()
    worker = MockWorker(nodes=[node_def])
    executor = _make_executor_with_worker(worker)

    graph = Graph(
        graph_id="test-graph",
        nodes=[
            NodeInstance(node_id="const1", node_type="test.simple.constant"),
        ],
    )

    result = asyncio.run(executor.execute_graph(graph))

    assert result.get_node_record("nonexistent") is None
