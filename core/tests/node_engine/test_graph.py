"""Tests for graph data model."""

import pytest
from pydantic import ValidationError

from mascarade.node_engine.graph import Edge, Graph, Node


def test_node_creation():
    """Test basic node creation."""
    node = Node(
        id="llm1",
        type="ai.llm-inference",
        inputs={"prompt": "Hello"},
        config={"temperature": 0.7},
    )
    assert node.id == "llm1"
    assert node.type == "ai.llm-inference"
    assert node.inputs["prompt"] == "Hello"
    assert node.config["temperature"] == 0.7


def test_node_defaults():
    """Test node default values."""
    node = Node(id="n1", type="ai.test")
    assert node.inputs == {}
    assert node.config == {}


def test_node_domain_property():
    """Test node domain extraction."""
    node = Node(id="n1", type="ai.llm-inference")
    assert node.domain == "ai"

    node2 = Node(id="n2", type="cad.sketch")
    assert node2.domain == "cad"


def test_node_validation_empty_id():
    """Test validation rejects empty node ID."""
    with pytest.raises(ValidationError) as exc_info:
        Node(id="", type="ai.test")
    assert "Node ID cannot be empty" in str(exc_info.value)


def test_node_validation_invalid_id_characters():
    """Test validation rejects invalid ID characters."""
    with pytest.raises(ValidationError) as exc_info:
        Node(id="node with spaces", type="ai.test")
    assert "alphanumeric" in str(exc_info.value)

    with pytest.raises(ValidationError):
        Node(id="node@special", type="ai.test")


def test_node_validation_valid_id_characters():
    """Test validation accepts valid ID characters."""
    # Should not raise
    Node(id="node-1", type="ai.test")
    Node(id="node_2", type="ai.test")
    Node(id="node123", type="ai.test")


def test_node_validation_empty_type():
    """Test validation rejects empty node type."""
    with pytest.raises(ValidationError) as exc_info:
        Node(id="n1", type="")
    assert "Node type cannot be empty" in str(exc_info.value)


def test_node_validation_unqualified_type():
    """Test validation rejects unqualified node type."""
    with pytest.raises(ValidationError) as exc_info:
        Node(id="n1", type="llm-inference")
    assert "fully qualified" in str(exc_info.value)
    assert "domain.typename" in str(exc_info.value)


def test_node_immutable():
    """Test that Node instances are immutable."""
    node = Node(id="n1", type="ai.test")
    with pytest.raises(ValidationError):
        node.id = "changed"


def test_edge_creation():
    """Test basic edge creation."""
    edge = Edge(
        from_node="n1",
        from_port="output",
        to_node="n2",
        to_port="input",
    )
    assert edge.from_node == "n1"
    assert edge.from_port == "output"
    assert edge.to_node == "n2"
    assert edge.to_port == "input"


def test_edge_source_property():
    """Test edge source tuple property."""
    edge = Edge(from_node="n1", from_port="out", to_node="n2", to_port="in")
    assert edge.source == ("n1", "out")


def test_edge_destination_property():
    """Test edge destination tuple property."""
    edge = Edge(from_node="n1", from_port="out", to_node="n2", to_port="in")
    assert edge.destination == ("n2", "in")


def test_edge_validation_self_loop():
    """Test validation rejects self-loops."""
    with pytest.raises(ValidationError) as exc_info:
        Edge(from_node="n1", from_port="out", to_node="n1", to_port="in")
    assert "Self-loop" in str(exc_info.value)


def test_edge_immutable():
    """Test that Edge instances are immutable."""
    edge = Edge(from_node="n1", from_port="out", to_node="n2", to_port="in")
    with pytest.raises(ValidationError):
        edge.from_node = "changed"


def test_graph_creation():
    """Test basic graph creation."""
    nodes = [
        Node(id="n1", type="ai.template"),
        Node(id="n2", type="ai.llm"),
    ]
    edges = [
        Edge(from_node="n1", from_port="output", to_node="n2", to_port="input"),
    ]
    graph = Graph(nodes=nodes, edges=edges)

    assert len(graph.nodes) == 2
    assert len(graph.edges) == 1
    assert graph.node_count == 2
    assert graph.edge_count == 1


def test_graph_defaults():
    """Test graph default values."""
    graph = Graph()
    assert graph.nodes == []
    assert graph.edges == []
    assert graph.metadata == {}


def test_graph_validation_duplicate_node_ids():
    """Test validation rejects duplicate node IDs."""
    nodes = [
        Node(id="n1", type="ai.test"),
        Node(id="n1", type="ai.test2"),  # Duplicate ID
    ]
    with pytest.raises(ValidationError) as exc_info:
        Graph(nodes=nodes)
    assert "Duplicate node IDs" in str(exc_info.value)
    assert "n1" in str(exc_info.value)


def test_graph_validation_edge_missing_source_node():
    """Test validation rejects edges with missing source nodes."""
    nodes = [Node(id="n1", type="ai.test")]
    edges = [Edge(from_node="missing", from_port="out", to_node="n1", to_port="in")]

    with pytest.raises(ValidationError) as exc_info:
        Graph(nodes=nodes, edges=edges)
    assert "non-existent source node" in str(exc_info.value)
    assert "missing" in str(exc_info.value)


def test_graph_validation_edge_missing_destination_node():
    """Test validation rejects edges with missing destination nodes."""
    nodes = [Node(id="n1", type="ai.test")]
    edges = [Edge(from_node="n1", from_port="out", to_node="missing", to_port="in")]

    with pytest.raises(ValidationError) as exc_info:
        Graph(nodes=nodes, edges=edges)
    assert "non-existent destination node" in str(exc_info.value)
    assert "missing" in str(exc_info.value)


def test_graph_validation_cycle_detection():
    """Test validation detects cycles."""
    nodes = [
        Node(id="n1", type="ai.test"),
        Node(id="n2", type="ai.test"),
        Node(id="n3", type="ai.test"),
    ]
    edges = [
        Edge(from_node="n1", from_port="out", to_node="n2", to_port="in"),
        Edge(from_node="n2", from_port="out", to_node="n3", to_port="in"),
        Edge(from_node="n3", from_port="out", to_node="n1", to_port="in"),  # Cycle!
    ]

    with pytest.raises(ValidationError) as exc_info:
        Graph(nodes=nodes, edges=edges)
    assert "cycle" in str(exc_info.value).lower()
    assert "DAG" in str(exc_info.value)


def test_graph_get_node():
    """Test getting a node by ID."""
    node1 = Node(id="n1", type="ai.test")
    node2 = Node(id="n2", type="ai.test")
    graph = Graph(nodes=[node1, node2])

    retrieved = graph.get_node("n1")
    assert retrieved is not None
    assert retrieved.id == "n1"

    missing = graph.get_node("missing")
    assert missing is None


def test_graph_get_incoming_edges():
    """Test getting incoming edges for a node."""
    nodes = [
        Node(id="n1", type="ai.test"),
        Node(id="n2", type="ai.test"),
        Node(id="n3", type="ai.test"),
    ]
    edges = [
        Edge(from_node="n1", from_port="out", to_node="n3", to_port="in1"),
        Edge(from_node="n2", from_port="out", to_node="n3", to_port="in2"),
    ]
    graph = Graph(nodes=nodes, edges=edges)

    incoming = graph.get_incoming_edges("n3")
    assert len(incoming) == 2
    assert all(e.to_node == "n3" for e in incoming)

    incoming_n1 = graph.get_incoming_edges("n1")
    assert len(incoming_n1) == 0


def test_graph_get_outgoing_edges():
    """Test getting outgoing edges for a node."""
    nodes = [
        Node(id="n1", type="ai.test"),
        Node(id="n2", type="ai.test"),
        Node(id="n3", type="ai.test"),
    ]
    edges = [
        Edge(from_node="n1", from_port="out1", to_node="n2", to_port="in"),
        Edge(from_node="n1", from_port="out2", to_node="n3", to_port="in"),
    ]
    graph = Graph(nodes=nodes, edges=edges)

    outgoing = graph.get_outgoing_edges("n1")
    assert len(outgoing) == 2
    assert all(e.from_node == "n1" for e in outgoing)

    outgoing_n3 = graph.get_outgoing_edges("n3")
    assert len(outgoing_n3) == 0


def test_graph_topological_sort():
    """Test topological sorting of nodes."""
    nodes = [
        Node(id="n1", type="ai.test"),
        Node(id="n2", type="ai.test"),
        Node(id="n3", type="ai.test"),
    ]
    edges = [
        Edge(from_node="n1", from_port="out", to_node="n2", to_port="in"),
        Edge(from_node="n2", from_port="out", to_node="n3", to_port="in"),
    ]
    graph = Graph(nodes=nodes, edges=edges)

    sorted_nodes = graph.topological_sort()
    assert len(sorted_nodes) == 3

    # n1 should come before n2, n2 before n3
    ids = [n.id for n in sorted_nodes]
    assert ids.index("n1") < ids.index("n2")
    assert ids.index("n2") < ids.index("n3")


def test_graph_topological_sort_multiple_roots():
    """Test topological sort with multiple root nodes."""
    nodes = [
        Node(id="n1", type="ai.test"),
        Node(id="n2", type="ai.test"),
        Node(id="n3", type="ai.test"),
    ]
    edges = [
        Edge(from_node="n1", from_port="out", to_node="n3", to_port="in1"),
        Edge(from_node="n2", from_port="out", to_node="n3", to_port="in2"),
    ]
    graph = Graph(nodes=nodes, edges=edges)

    sorted_nodes = graph.topological_sort()
    assert len(sorted_nodes) == 3

    # n3 should come after both n1 and n2
    ids = [n.id for n in sorted_nodes]
    assert ids.index("n1") < ids.index("n3")
    assert ids.index("n2") < ids.index("n3")


def test_graph_topological_sort_empty():
    """Test topological sort on empty graph."""
    graph = Graph()
    sorted_nodes = graph.topological_sort()
    assert sorted_nodes == []


def test_graph_topological_sort_single_node():
    """Test topological sort on graph with single node."""
    graph = Graph(nodes=[Node(id="n1", type="ai.test")])
    sorted_nodes = graph.topological_sort()
    assert len(sorted_nodes) == 1
    assert sorted_nodes[0].id == "n1"


def test_graph_with_metadata():
    """Test graph with metadata."""
    graph = Graph(
        nodes=[Node(id="n1", type="ai.test")],
        metadata={
            "id": "workflow-123",
            "name": "Test Workflow",
            "version": "1.0",
        },
    )
    assert graph.metadata["id"] == "workflow-123"
    assert graph.metadata["name"] == "Test Workflow"
    assert graph.metadata["version"] == "1.0"
