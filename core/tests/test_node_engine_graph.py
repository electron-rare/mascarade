"""Tests for graph representation in the Universal Node Engine."""

import pytest
from pydantic import ValidationError

from mascarade.node_engine.graph import (
    Connection,
    Edge,
    ExecutionContext,
    Graph,
    GraphEdge,
    GraphNode,
    GraphStatus,
    Node,
    NodeInstance,
    NodeResult,
)


class TestGraphStatus:
    """Test suite for graph status enum."""

    def test_graph_status_values(self):
        """Graph status should have all lifecycle states."""
        assert GraphStatus.DRAFT == "draft"
        assert GraphStatus.VALIDATED == "validated"
        assert GraphStatus.COMPILED == "compiled"
        assert GraphStatus.RUNNING == "running"
        assert GraphStatus.COMPLETED == "completed"
        assert GraphStatus.FAILED == "failed"
        assert GraphStatus.CANCELLED == "cancelled"

    def test_graph_status_enum(self):
        """Graph status should be string enum."""
        assert isinstance(GraphStatus.DRAFT, str)
        assert GraphStatus.DRAFT.value == "draft"


class TestGraphNode:
    """Test suite for graph node dataclass."""

    def test_graph_node_minimal(self):
        """GraphNode should work with minimal fields."""
        node = GraphNode(id="n1", node_type="test-node", label="Test Node")
        assert node.id == "n1"
        assert node.node_type == "test-node"
        assert node.label == "Test Node"
        assert node.config == {}
        assert node.position == (0.0, 0.0)
        assert node.domain is None

    def test_graph_node_with_config(self):
        """GraphNode should support config dict."""
        node = GraphNode(
            id="n2",
            node_type="ai.llm",
            label="LLM Node",
            config={"model": "gpt-4", "temperature": 0.7},
        )
        assert node.config["model"] == "gpt-4"
        assert node.config["temperature"] == 0.7

    def test_graph_node_with_position(self):
        """GraphNode should support visual position."""
        node = GraphNode(
            id="n3", node_type="test", label="Positioned", position=(100.5, 200.3)
        )
        assert node.position == (100.5, 200.3)

    def test_graph_node_with_domain(self):
        """GraphNode should support domain specification."""
        node = GraphNode(
            id="n4", node_type="ai.llm", label="AI Node", domain="ai"
        )
        assert node.domain == "ai"

    def test_graph_node_defaults(self):
        """GraphNode should have sensible defaults."""
        node = GraphNode(id="default", node_type="type", label="Default")
        assert isinstance(node.config, dict)
        assert len(node.config) == 0
        assert isinstance(node.position, tuple)
        assert len(node.position) == 2


class TestGraphEdge:
    """Test suite for graph edge dataclass."""

    def test_graph_edge_creation(self):
        """GraphEdge should connect two node ports."""
        edge = GraphEdge(
            id="e1",
            source_node="n1",
            source_port="output",
            target_node="n2",
            target_port="input",
        )
        assert edge.id == "e1"
        assert edge.source_node == "n1"
        assert edge.source_port == "output"
        assert edge.target_node == "n2"
        assert edge.target_port == "input"

    def test_graph_edge_multiple_ports(self):
        """GraphEdge should support different port names."""
        edge = GraphEdge(
            id="e2",
            source_node="analyzer",
            source_port="result",
            target_node="formatter",
            target_port="data",
        )
        assert edge.source_port == "result"
        assert edge.target_port == "data"


class TestGraph:
    """Test suite for graph dataclass."""

    def test_graph_minimal(self):
        """Graph should work with minimal fields."""
        graph = Graph(id="g1", name="Test Graph")
        assert graph.id == "g1"
        assert graph.name == "Test Graph"
        assert graph.version == 1
        assert graph.status == GraphStatus.DRAFT
        assert graph.nodes == []
        assert graph.edges == []
        assert graph.metadata == {}

    def test_graph_with_nodes(self):
        """Graph should store nodes."""
        nodes = [
            GraphNode(id="n1", node_type="test", label="Node 1"),
            GraphNode(id="n2", node_type="test", label="Node 2"),
        ]
        graph = Graph(id="g2", name="With Nodes", nodes=nodes)
        assert len(graph.nodes) == 2
        assert graph.nodes[0].id == "n1"
        assert graph.nodes[1].id == "n2"

    def test_graph_with_edges(self):
        """Graph should store edges."""
        edges = [
            GraphEdge(
                id="e1",
                source_node="n1",
                source_port="out",
                target_node="n2",
                target_port="in",
            ),
        ]
        graph = Graph(id="g3", name="With Edges", edges=edges)
        assert len(graph.edges) == 1
        assert graph.edges[0].source_node == "n1"

    def test_graph_complete(self):
        """Graph with nodes and edges."""
        nodes = [
            GraphNode(id="n1", node_type="source", label="Source"),
            GraphNode(id="n2", node_type="sink", label="Sink"),
        ]
        edges = [
            GraphEdge(
                id="e1",
                source_node="n1",
                source_port="output",
                target_node="n2",
                target_port="input",
            ),
        ]
        graph = Graph(
            id="g4",
            name="Complete Graph",
            version=2,
            status=GraphStatus.VALIDATED,
            nodes=nodes,
            edges=edges,
            metadata={"created_by": "test", "description": "A complete graph"},
        )
        assert len(graph.nodes) == 2
        assert len(graph.edges) == 1
        assert graph.version == 2
        assert graph.status == GraphStatus.VALIDATED
        assert graph.metadata["created_by"] == "test"

    def test_graph_status_transitions(self):
        """Graph should support status transitions."""
        graph = Graph(id="g5", name="Status Test")
        assert graph.status == GraphStatus.DRAFT

        graph.status = GraphStatus.VALIDATED
        assert graph.status == GraphStatus.VALIDATED

        graph.status = GraphStatus.COMPILED
        assert graph.status == GraphStatus.COMPILED

        graph.status = GraphStatus.RUNNING
        assert graph.status == GraphStatus.RUNNING

        graph.status = GraphStatus.COMPLETED
        assert graph.status == GraphStatus.COMPLETED

    def test_graph_metadata(self):
        """Graph should support arbitrary metadata."""
        graph = Graph(
            id="g6",
            name="Metadata Test",
            metadata={
                "author": "test-user",
                "tags": ["test", "demo"],
                "created_at": "2026-03-16T00:00:00Z",
                "custom_field": 123,
            },
        )
        assert graph.metadata["author"] == "test-user"
        assert "test" in graph.metadata["tags"]
        assert graph.metadata["custom_field"] == 123


class TestExecutionContext:
    """Test suite for execution context."""

    def test_execution_context_minimal(self):
        """ExecutionContext should work with minimal fields."""
        ctx = ExecutionContext(graph_id="g1", run_id="r1", node_id="n1")
        assert ctx.graph_id == "g1"
        assert ctx.run_id == "r1"
        assert ctx.node_id == "n1"
        assert ctx.inputs == {}
        assert ctx.metadata == {}

    def test_execution_context_with_inputs(self):
        """ExecutionContext should store inputs."""
        ctx = ExecutionContext(
            graph_id="g2",
            run_id="r2",
            node_id="n2",
            inputs={"value": 42, "name": "test"},
        )
        assert ctx.inputs["value"] == 42
        assert ctx.inputs["name"] == "test"

    def test_execution_context_with_metadata(self):
        """ExecutionContext should store metadata."""
        ctx = ExecutionContext(
            graph_id="g3",
            run_id="r3",
            node_id="n3",
            metadata={"user": "test-user", "timestamp": "2026-03-16"},
        )
        assert ctx.metadata["user"] == "test-user"
        assert ctx.metadata["timestamp"] == "2026-03-16"


class TestNodeResult:
    """Test suite for node execution results."""

    def test_node_result_success(self):
        """NodeResult should capture successful execution."""
        result = NodeResult(
            node_id="n1",
            status="success",
            outputs={"result": 42, "message": "done"},
            execution_time_ms=123.45,
        )
        assert result.node_id == "n1"
        assert result.status == "success"
        assert result.outputs["result"] == 42
        assert result.error is None
        assert result.execution_time_ms == 123.45

    def test_node_result_failure(self):
        """NodeResult should capture execution errors."""
        result = NodeResult(
            node_id="n2",
            status="failed",
            error="Connection timeout",
            execution_time_ms=5000.0,
        )
        assert result.node_id == "n2"
        assert result.status == "failed"
        assert result.error == "Connection timeout"
        assert result.outputs == {}

    def test_node_result_minimal(self):
        """NodeResult should work with minimal fields."""
        result = NodeResult(node_id="n3", status="pending")
        assert result.node_id == "n3"
        assert result.status == "pending"
        assert result.outputs == {}
        assert result.error is None
        assert result.execution_time_ms is None
        assert result.metadata == {}

    def test_node_result_with_metadata(self):
        """NodeResult should support metadata."""
        result = NodeResult(
            node_id="n4",
            status="success",
            outputs={"data": [1, 2, 3]},
            metadata={"worker": "test-worker", "retries": 2},
        )
        assert result.metadata["worker"] == "test-worker"
        assert result.metadata["retries"] == 2


class TestGraphStructures:
    """Integration tests for graph structures."""

    def test_diamond_graph(self):
        """Build a diamond-shaped graph."""
        nodes = [
            GraphNode(id="source", node_type="gen", label="Source"),
            GraphNode(id="left", node_type="proc", label="Left"),
            GraphNode(id="right", node_type="proc", label="Right"),
            GraphNode(id="sink", node_type="agg", label="Sink"),
        ]
        edges = [
            GraphEdge(
                id="e1",
                source_node="source",
                source_port="out",
                target_node="left",
                target_port="in",
            ),
            GraphEdge(
                id="e2",
                source_node="source",
                source_port="out",
                target_node="right",
                target_port="in",
            ),
            GraphEdge(
                id="e3",
                source_node="left",
                source_port="out",
                target_node="sink",
                target_port="left_in",
            ),
            GraphEdge(
                id="e4",
                source_node="right",
                source_port="out",
                target_node="sink",
                target_port="right_in",
            ),
        ]
        graph = Graph(id="diamond", name="Diamond Graph", nodes=nodes, edges=edges)

        assert len(graph.nodes) == 4
        assert len(graph.edges) == 4

        # Verify structure
        source_edges = [e for e in graph.edges if e.source_node == "source"]
        assert len(source_edges) == 2

        sink_edges = [e for e in graph.edges if e.target_node == "sink"]
        assert len(sink_edges) == 2

    def test_linear_pipeline(self):
        """Build a linear pipeline graph."""
        nodes = [
            GraphNode(id=f"n{i}", node_type="step", label=f"Step {i}")
            for i in range(5)
        ]
        edges = [
            GraphEdge(
                id=f"e{i}",
                source_node=f"n{i}",
                source_port="out",
                target_node=f"n{i+1}",
                target_port="in",
            )
            for i in range(4)
        ]
        graph = Graph(id="pipeline", name="Linear Pipeline", nodes=nodes, edges=edges)

        assert len(graph.nodes) == 5
        assert len(graph.edges) == 4

        # Verify linear structure
        for i in range(4):
            edge = graph.edges[i]
            assert edge.source_node == f"n{i}"
            assert edge.target_node == f"n{i+1}"

    def test_multi_output_graph(self):
        """Build a graph with multiple outputs."""
        nodes = [
            GraphNode(id="input", node_type="source", label="Input"),
            GraphNode(id="processor", node_type="proc", label="Processor"),
            GraphNode(id="out1", node_type="sink", label="Output 1"),
            GraphNode(id="out2", node_type="sink", label="Output 2"),
            GraphNode(id="out3", node_type="sink", label="Output 3"),
        ]
        edges = [
            GraphEdge(
                id="e1",
                source_node="input",
                source_port="data",
                target_node="processor",
                target_port="in",
            ),
            GraphEdge(
                id="e2",
                source_node="processor",
                source_port="result1",
                target_node="out1",
                target_port="in",
            ),
            GraphEdge(
                id="e3",
                source_node="processor",
                source_port="result2",
                target_node="out2",
                target_port="in",
            ),
            GraphEdge(
                id="e4",
                source_node="processor",
                source_port="result3",
                target_node="out3",
                target_port="in",
            ),
        ]
        graph = Graph(id="multi-out", name="Multi Output", nodes=nodes, edges=edges)

        # Verify processor has 3 output connections
        proc_outputs = [e for e in graph.edges if e.source_node == "processor"]
        assert len(proc_outputs) == 3

        # Each output is different
        output_nodes = {e.target_node for e in proc_outputs}
        assert len(output_nodes) == 3


class TestPydanticNode:
    """Test suite for Pydantic Node model."""

    def test_valid_node(self):
        n = Node(id="node-1", type="ai.chat")
        assert n.id == "node-1"
        assert n.domain == "ai"

    def test_empty_id_rejected(self):
        with pytest.raises(ValidationError):
            Node(id="", type="ai.chat")

    def test_invalid_id_chars(self):
        with pytest.raises(ValidationError):
            Node(id="node 1!", type="ai.chat")

    def test_unqualified_type_rejected(self):
        with pytest.raises(ValidationError):
            Node(id="n1", type="chat")

    def test_empty_type_rejected(self):
        with pytest.raises(ValidationError):
            Node(id="n1", type="")

    def test_node_with_inputs_and_config(self):
        n = Node(id="n1", type="ai.embed", inputs={"text": "hello"}, config={"dim": 768})
        assert n.inputs["text"] == "hello"
        assert n.config["dim"] == 768


class TestPydanticEdge:
    """Test suite for Pydantic Edge model."""

    def test_valid_edge(self):
        e = Edge(from_node="n1", from_port="out", to_node="n2", to_port="in")
        assert e.source == ("n1", "out")
        assert e.destination == ("n2", "in")

    def test_self_loop_rejected(self):
        with pytest.raises(ValidationError, match="Self-loop"):
            Edge(from_node="n1", from_port="out", to_node="n1", to_port="in")


class TestGraphValidation:
    """Pydantic graph-level validation (duplicates, bad refs, cycles)."""

    def test_duplicate_node_ids_rejected(self):
        n1 = Node(id="dup", type="ai.chat")
        n2 = Node(id="dup", type="ai.embed")
        with pytest.raises(ValidationError):
            Graph(id="g", nodes=[n1, n2], edges=[])

    def test_edge_bad_reference_rejected(self):
        n1 = Node(id="a", type="ai.chat")
        e = Edge(from_node="a", from_port="out", to_node="missing", to_port="in")
        with pytest.raises(ValidationError):
            Graph(id="g", nodes=[n1], edges=[e])

    def test_cycle_detection(self):
        n1 = Node(id="a", type="ai.x")
        n2 = Node(id="b", type="ai.y")
        e1 = Edge(from_node="a", from_port="o", to_node="b", to_port="i")
        e2 = Edge(from_node="b", from_port="o", to_node="a", to_port="i")
        with pytest.raises(ValidationError, match="cycle"):
            Graph(id="g", nodes=[n1, n2], edges=[e1, e2])


class TestGraphMethods:
    """Test Graph helper methods (get_node, edges, topological sort)."""

    def test_get_node(self):
        nodes = [GraphNode(id="x", node_type="ai.chat")]
        g = Graph(id="g", nodes=nodes)
        assert g.get_node("x") is not None
        assert g.get_node("missing") is None

    def test_get_incoming_edges(self):
        nodes = [GraphNode(id="a", node_type="ai.x"), GraphNode(id="b", node_type="ai.y")]
        edges = [GraphEdge(id="e1", source_node="a", source_port="o", target_node="b", target_port="i")]
        g = Graph(id="g", nodes=nodes, edges=edges)
        assert len(g.get_incoming_edges("b")) == 1
        assert len(g.get_incoming_edges("a")) == 0

    def test_get_outgoing_edges(self):
        nodes = [GraphNode(id="a", node_type="ai.x"), GraphNode(id="b", node_type="ai.y")]
        edges = [GraphEdge(id="e1", source_node="a", source_port="o", target_node="b", target_port="i")]
        g = Graph(id="g", nodes=nodes, edges=edges)
        assert len(g.get_outgoing_edges("a")) == 1
        assert len(g.get_outgoing_edges("b")) == 0

    def test_topological_sort_order(self):
        nodes = [GraphNode(id="a", node_type="ai.x"), GraphNode(id="b", node_type="ai.y")]
        edges = [GraphEdge(id="e1", source_node="a", source_port="o", target_node="b", target_port="i")]
        g = Graph(id="g", nodes=nodes, edges=edges)
        order = g.topological_sort()
        ids = [n.id for n in order]
        assert ids.index("a") < ids.index("b")

    def test_topological_sort_diamond(self):
        nodes = [
            GraphNode(id="s", node_type="x"),
            GraphNode(id="l", node_type="x"),
            GraphNode(id="r", node_type="x"),
            GraphNode(id="t", node_type="x"),
        ]
        edges = [
            GraphEdge(id="e1", source_node="s", source_port="o", target_node="l", target_port="i"),
            GraphEdge(id="e2", source_node="s", source_port="o", target_node="r", target_port="i"),
            GraphEdge(id="e3", source_node="l", source_port="o", target_node="t", target_port="i"),
            GraphEdge(id="e4", source_node="r", source_port="o", target_node="t", target_port="i"),
        ]
        g = Graph(id="g", nodes=nodes, edges=edges)
        order = g.topological_sort()
        ids = [n.id for n in order]
        assert ids[0] == "s"
        assert ids[-1] == "t"

    def test_node_count_and_edge_count(self):
        nodes = [GraphNode(id="a", node_type="x"), GraphNode(id="b", node_type="y")]
        edges = [GraphEdge(id="e1", source_node="a", source_port="o", target_node="b", target_port="i")]
        g = Graph(id="g", nodes=nodes, edges=edges)
        assert g.node_count == 2
        assert g.edge_count == 1

    def test_graph_id_alias(self):
        g = Graph(graph_id="gx", name="alias")
        assert g.graph_id == "gx"
        assert g.id == "gx"


class TestConnection:
    """Test Connection dataclass."""

    def test_aliases(self):
        c = Connection(source_node_id="a", source_port="o", target_node_id="b", target_port="i")
        assert c.source_node == "a"
        assert c.target_node == "b"


class TestNodeInstance:
    """Test NodeInstance dataclass."""

    def test_id_alias(self):
        ni = NodeInstance(node_id="n1", node_type="ai.chat")
        assert ni.id == "n1"
