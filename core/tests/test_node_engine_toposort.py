"""Tests for topological sort with Kahn's algorithm in the Node Engine."""

import pytest

from mascarade.node_engine.engine import CycleDetectedError, GraphExecutionEngine
from mascarade.node_engine.graph import Graph, GraphEdge, GraphNode
from mascarade.node_engine.registry import NodeTypeRegistry, WorkerRegistry


class TestTopologicalSort:
    """Test suite for topological sort and cycle detection."""

    def test_empty_graph(self):
        """Empty graph should return empty levels."""
        engine = GraphExecutionEngine(WorkerRegistry(), NodeTypeRegistry())
        graph = Graph(id="test", name="Empty Graph")
        levels = engine._topological_sort(graph)
        assert levels == []

    def test_single_node(self):
        """Single node should return one level with that node."""
        engine = GraphExecutionEngine(WorkerRegistry(), NodeTypeRegistry())
        graph = Graph(
            id="test",
            name="Single Node",
            nodes=[GraphNode(id="n1", node_type="test", label="Node 1")],
        )
        levels = engine._topological_sort(graph)
        assert levels == [["n1"]]

    def test_linear_chain(self):
        """Linear chain should return sequential levels."""
        engine = GraphExecutionEngine(WorkerRegistry(), NodeTypeRegistry())
        graph = Graph(
            id="test",
            name="Linear Chain",
            nodes=[
                GraphNode(id="n1", node_type="test", label="Node 1"),
                GraphNode(id="n2", node_type="test", label="Node 2"),
                GraphNode(id="n3", node_type="test", label="Node 3"),
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
                    source_node="n2",
                    source_port="out",
                    target_node="n3",
                    target_port="in",
                ),
            ],
        )
        levels = engine._topological_sort(graph)
        assert levels == [["n1"], ["n2"], ["n3"]]

    def test_parallel_branches(self):
        """Independent nodes should be in the same level."""
        engine = GraphExecutionEngine(WorkerRegistry(), NodeTypeRegistry())
        graph = Graph(
            id="test",
            name="Parallel Branches",
            nodes=[
                GraphNode(id="n1", node_type="test", label="Node 1"),
                GraphNode(id="n2", node_type="test", label="Node 2"),
                GraphNode(id="n3", node_type="test", label="Node 3"),
                GraphNode(id="n4", node_type="test", label="Node 4"),
            ],
            edges=[
                GraphEdge(
                    id="e1",
                    source_node="n1",
                    source_port="out",
                    target_node="n3",
                    target_port="in",
                ),
                GraphEdge(
                    id="e2",
                    source_node="n2",
                    source_port="out",
                    target_node="n4",
                    target_port="in",
                ),
            ],
        )
        levels = engine._topological_sort(graph)
        # n1 and n2 should be in level 0, n3 and n4 in level 1
        assert len(levels) == 2
        assert set(levels[0]) == {"n1", "n2"}
        assert set(levels[1]) == {"n3", "n4"}

    def test_diamond_pattern(self):
        """Diamond pattern: one source, two parallel middle, one sink."""
        engine = GraphExecutionEngine(WorkerRegistry(), NodeTypeRegistry())
        graph = Graph(
            id="test",
            name="Diamond",
            nodes=[
                GraphNode(id="n1", node_type="test", label="Source"),
                GraphNode(id="n2", node_type="test", label="Left"),
                GraphNode(id="n3", node_type="test", label="Right"),
                GraphNode(id="n4", node_type="test", label="Sink"),
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
        levels = engine._topological_sort(graph)
        assert len(levels) == 3
        assert levels[0] == ["n1"]
        assert set(levels[1]) == {"n2", "n3"}
        assert levels[2] == ["n4"]

    def test_simple_cycle_detection(self):
        """Simple cycle: n1 -> n2 -> n1 should raise CycleDetectedError."""
        engine = GraphExecutionEngine(WorkerRegistry(), NodeTypeRegistry())
        graph = Graph(
            id="test",
            name="Simple Cycle",
            nodes=[
                GraphNode(id="n1", node_type="test", label="Node 1"),
                GraphNode(id="n2", node_type="test", label="Node 2"),
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
                    source_node="n2",
                    source_port="out",
                    target_node="n1",
                    target_port="in",
                ),
            ],
        )
        with pytest.raises(CycleDetectedError) as exc_info:
            engine._topological_sort(graph)
        assert "cycle" in str(exc_info.value).lower()

    def test_self_loop_detection(self):
        """Self-loop: n1 -> n1 should raise CycleDetectedError."""
        engine = GraphExecutionEngine(WorkerRegistry(), NodeTypeRegistry())
        graph = Graph(
            id="test",
            name="Self Loop",
            nodes=[GraphNode(id="n1", node_type="test", label="Node 1")],
            edges=[
                GraphEdge(
                    id="e1",
                    source_node="n1",
                    source_port="out",
                    target_node="n1",
                    target_port="in",
                ),
            ],
        )
        with pytest.raises(CycleDetectedError):
            engine._topological_sort(graph)

    def test_complex_cycle_detection(self):
        """Complex cycle in larger graph should be detected."""
        engine = GraphExecutionEngine(WorkerRegistry(), NodeTypeRegistry())
        graph = Graph(
            id="test",
            name="Complex Cycle",
            nodes=[
                GraphNode(id="n1", node_type="test", label="Node 1"),
                GraphNode(id="n2", node_type="test", label="Node 2"),
                GraphNode(id="n3", node_type="test", label="Node 3"),
                GraphNode(id="n4", node_type="test", label="Node 4"),
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
                    source_node="n2",
                    source_port="out",
                    target_node="n3",
                    target_port="in",
                ),
                GraphEdge(
                    id="e3",
                    source_node="n3",
                    source_port="out",
                    target_node="n4",
                    target_port="in",
                ),
                GraphEdge(
                    id="e4",
                    source_node="n4",
                    source_port="out",
                    target_node="n2",
                    target_port="in",
                ),
            ],
        )
        with pytest.raises(CycleDetectedError):
            engine._topological_sort(graph)

    def test_multiple_disconnected_components(self):
        """Multiple disconnected subgraphs should all be sorted."""
        engine = GraphExecutionEngine(WorkerRegistry(), NodeTypeRegistry())
        graph = Graph(
            id="test",
            name="Disconnected",
            nodes=[
                GraphNode(id="n1", node_type="test", label="Node 1"),
                GraphNode(id="n2", node_type="test", label="Node 2"),
                GraphNode(id="n3", node_type="test", label="Node 3"),
                GraphNode(id="n4", node_type="test", label="Node 4"),
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
                    source_node="n3",
                    source_port="out",
                    target_node="n4",
                    target_port="in",
                ),
            ],
        )
        levels = engine._topological_sort(graph)
        assert len(levels) == 2
        assert set(levels[0]) == {"n1", "n3"}
        assert set(levels[1]) == {"n2", "n4"}
