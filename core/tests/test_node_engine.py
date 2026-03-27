"""Consolidated node engine test suite.

Tests the key integration points across ExecutionMode, domain workers,
cross-domain adapter registry, graph creation/validation, and persistence.
"""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from mascarade.node_engine.runtime import ExecutionMode

# ---------------------------------------------------------------------------
# 1. ExecutionMode import and values
# ---------------------------------------------------------------------------


class TestExecutionMode:
    """Verify ExecutionMode enum is importable and has correct values."""

    def test_execution_mode_values(self):
        assert ExecutionMode.EAGER == "eager"
        assert ExecutionMode.LAZY == "lazy"
        assert ExecutionMode.STEPPED == "stepped"

    def test_execution_mode_is_str_enum(self):
        assert isinstance(ExecutionMode.EAGER, str)
        assert len(list(ExecutionMode)) == 3


# ---------------------------------------------------------------------------
# 2. ElectronicsWorker dispatch table
# ---------------------------------------------------------------------------


class TestElectronicsWorkerDispatch:
    """Verify the ElectronicsWorker dispatch table and node class map."""

    def test_dispatch_table_has_all_subdomain_prefixes(self):
        from mascarade.node_engine.workers.electronics.worker import _NODE_CLASSES

        prefixes = {k.rsplit(".", 1)[0] for k in _NODE_CLASSES}
        assert "electronics.spice" in prefixes
        assert "electronics.pcb" in prefixes
        assert "electronics.firmware" in prefixes
        assert "electronics.component" in prefixes

    def test_dispatch_table_node_count(self):
        from mascarade.node_engine.workers.electronics.worker import _NODE_CLASSES

        # 4 spice + 3 pcb + 3 firmware + 8 component = 18 node types
        assert len(_NODE_CLASSES) >= 18

    def test_tool_requirements_map_consistency(self):
        from mascarade.node_engine.workers.electronics.worker import (
            _NODE_CLASSES,
            _TOOL_REQUIREMENTS,
        )

        # Every node in _TOOL_REQUIREMENTS must exist in _NODE_CLASSES
        for node_type in _TOOL_REQUIREMENTS:
            assert node_type in _NODE_CLASSES, (
                f"Tool requirement for {node_type} has no dispatch entry"
            )

    def test_electronics_worker_instantiation(self):
        from mascarade.node_engine.workers.electronics.worker import ElectronicsWorker

        worker = ElectronicsWorker()
        assert worker.domain == "electronics"

    def test_electronics_worker_capabilities_shape(self):
        from mascarade.node_engine.workers.electronics.worker import ElectronicsWorker

        worker = ElectronicsWorker()
        caps = worker.capabilities()
        # capabilities is a NodeCapability dataclass (may have extended fields)
        assert caps is not None
        assert caps.max_concurrent >= 1
        assert caps.requires_gpu is False


# ---------------------------------------------------------------------------
# 3. HardwareWorker capabilities
# ---------------------------------------------------------------------------


class TestHardwareWorkerCapabilities:
    """Verify the HardwareWorker declares expected node types."""

    def test_hardware_worker_domain(self):
        from mascarade.node_engine.workers.hardware.worker import HardwareWorker

        worker = HardwareWorker()
        assert worker.domain == "hardware"
        assert worker.name == "hardware-worker"

    def test_hardware_worker_capabilities_list(self):
        from mascarade.node_engine.workers.hardware.worker import HardwareWorker

        worker = HardwareWorker()
        caps = worker.capabilities()
        assert isinstance(caps, list)
        assert len(caps) > 0

        # Each capability should declare node_type and description
        for cap in caps:
            assert "node_type" in cap
            assert "description" in cap

    def test_hardware_worker_node_type_prefixes(self):
        from mascarade.node_engine.workers.hardware.worker import HardwareWorker

        worker = HardwareWorker()
        caps = worker.capabilities()
        node_types = [cap["node_type"] for cap in caps]

        # Should include ESP32 and DMX node types at minimum
        prefixes = {nt.rsplit(".", 1)[0] for nt in node_types}
        assert "hardware.esp32" in prefixes or "hardware.dmx" in prefixes


# ---------------------------------------------------------------------------
# 4. Cross-domain adapter registry
# ---------------------------------------------------------------------------


class TestCrossDomainAdapterRegistry:
    """Test the adapter registry registration and lookup."""

    def test_adapter_registry_creation(self):
        from mascarade.node_engine.cross_domain.register import AdapterRegistry

        registry = AdapterRegistry()
        assert len(registry) == 0

    def test_register_all_adapters_populates_registry(self):
        from mascarade.node_engine.cross_domain.register import (
            AdapterRegistry,
            register_all_adapters,
        )

        registry = AdapterRegistry()
        register_all_adapters(registry)

        assert len(registry) > 0
        mappings = registry.list_mappings()
        assert len(mappings) > 0

    def test_adapter_registry_lookup_known_mapping(self):
        from mascarade.node_engine.cross_domain.register import (
            AdapterRegistry,
            register_all_adapters,
        )

        registry = AdapterRegistry()
        register_all_adapters(registry)

        # AIToCADAdapter registers ai.LLMResponse->cad.CADDocument
        expected_id = "ai.LLMResponse->cad.CADDocument"
        assert expected_id in registry

        adapter, mapping = registry.lookup(expected_id)
        assert mapping.source_domain == "ai"
        assert mapping.target_domain == "cad"

    def test_adapter_registry_lookup_missing_raises(self):
        from mascarade.node_engine.cross_domain.register import AdapterRegistry

        registry = AdapterRegistry()
        with pytest.raises(KeyError, match="No adapter registered"):
            registry.lookup("nonexistent.Type->missing.Type")

    def test_adapter_registry_contains_protocol(self):
        from mascarade.node_engine.cross_domain.register import (
            AdapterRegistry,
            register_all_adapters,
        )

        registry = AdapterRegistry()
        register_all_adapters(registry)

        assert ("ai.LLMResponse->cad.CADDocument" in registry) is True
        assert ("fake.Missing->nope.Gone" in registry) is False

    def test_all_adapters_list_is_nonempty(self):
        from mascarade.node_engine.cross_domain.adapters import ALL_ADAPTERS

        assert len(ALL_ADAPTERS) >= 3  # AI->CAD, AI->Electronics, CAD->Electronics

    def test_adapter_registry_idempotent_registration(self):
        from mascarade.node_engine.cross_domain.register import (
            AdapterRegistry,
            register_all_adapters,
        )

        registry = AdapterRegistry()
        register_all_adapters(registry)
        count_first = len(registry)
        register_all_adapters(registry)  # second call should not raise
        assert len(registry) == count_first


# ---------------------------------------------------------------------------
# 5. Graph creation and validation
# ---------------------------------------------------------------------------


class TestGraphCreationAndValidation:
    """Test Graph construction, node/edge validation, and structure queries."""

    def test_graph_creation_minimal(self):
        from mascarade.node_engine.graph import Graph

        graph = Graph(id="test-g", name="Test")
        assert graph.id == "test-g"
        assert graph.name == "Test"
        assert len(graph.nodes) == 0
        assert len(graph.edges) == 0

    def test_graph_with_nodes_and_edges(self):
        from mascarade.node_engine.graph import Graph, GraphEdge, GraphNode

        nodes = [
            GraphNode(id="n1", node_type="ai.chat", label="Chat"),
            GraphNode(id="n2", node_type="ai.embed", label="Embed"),
        ]
        edges = [
            GraphEdge(
                id="e1",
                source_node="n1",
                source_port="out",
                target_node="n2",
                target_port="in",
            ),
        ]
        graph = Graph(id="g-full", name="Full", nodes=nodes, edges=edges)
        assert graph.node_count == 2
        assert graph.edge_count == 1

    def test_graph_duplicate_node_ids_rejected(self):
        from mascarade.node_engine.graph import Graph, Node

        n1 = Node(id="dup", type="ai.chat")
        n2 = Node(id="dup", type="ai.embed")
        with pytest.raises(ValidationError):
            Graph(id="g", nodes=[n1, n2], edges=[])

    def test_graph_cycle_rejected(self):
        from mascarade.node_engine.graph import Edge, Graph, Node

        n1 = Node(id="a", type="ai.x")
        n2 = Node(id="b", type="ai.y")
        e1 = Edge(from_node="a", from_port="o", to_node="b", to_port="i")
        e2 = Edge(from_node="b", from_port="o", to_node="a", to_port="i")
        with pytest.raises(ValidationError, match="cycle"):
            Graph(id="g", nodes=[n1, n2], edges=[e1, e2])

    def test_self_loop_edge_rejected(self):
        from mascarade.node_engine.graph import Edge

        with pytest.raises(ValidationError, match="Self-loop"):
            Edge(from_node="n1", from_port="out", to_node="n1", to_port="in")

    def test_topological_sort(self):
        from mascarade.node_engine.graph import Graph, GraphEdge, GraphNode

        nodes = [
            GraphNode(id="src", node_type="x"),
            GraphNode(id="mid", node_type="x"),
            GraphNode(id="dst", node_type="x"),
        ]
        edges = [
            GraphEdge(
                id="e1",
                source_node="src",
                source_port="o",
                target_node="mid",
                target_port="i",
            ),
            GraphEdge(
                id="e2",
                source_node="mid",
                source_port="o",
                target_node="dst",
                target_port="i",
            ),
        ]
        graph = Graph(id="linear", name="Linear", nodes=nodes, edges=edges)
        order = graph.topological_sort()
        ids = [n.id for n in order]
        assert ids == ["src", "mid", "dst"]


# ---------------------------------------------------------------------------
# 6. Persistence round-trip
# ---------------------------------------------------------------------------


class TestPersistenceRoundTrip:
    """Test serialize -> deserialize and file save/load round-trips."""

    def test_serialize_deserialize_roundtrip(self):
        from mascarade.node_engine.graph import Graph, GraphEdge, GraphNode, GraphStatus
        from mascarade.node_engine.persistence import GraphSerializer

        nodes = [
            GraphNode(id="n1", node_type="ai.llm", label="LLM", config={"model": "gpt-4"}),
            GraphNode(id="n2", node_type="ai.embed", label="Embed"),
        ]
        edges = [
            GraphEdge(
                id="e1",
                source_node="n1",
                source_port="out",
                target_node="n2",
                target_port="in",
            ),
        ]
        original = Graph(
            id="roundtrip",
            name="Roundtrip",
            version=2,
            status=GraphStatus.VALIDATED,
            nodes=nodes,
            edges=edges,
            metadata={"author": "test"},
        )

        serializer = GraphSerializer()
        data = serializer.serialize(original)
        restored = serializer.deserialize(data)

        assert restored.id == original.id
        assert restored.name == original.name
        assert restored.version == original.version
        assert restored.status == original.status
        assert len(restored.nodes) == 2
        assert len(restored.edges) == 1
        assert restored.nodes[0].config["model"] == "gpt-4"

    def test_file_save_load_roundtrip(self, tmp_path):
        from mascarade.node_engine.graph import Graph, GraphNode
        from mascarade.node_engine.persistence import GraphSerializer

        graph = Graph(
            id="file-test",
            name="File Test",
            nodes=[GraphNode(id="n1", node_type="test", label="N1")],
        )
        path = tmp_path / "graph.json"

        serializer = GraphSerializer()
        serializer.save(graph, path)

        assert path.exists()
        loaded = serializer.load(path)
        assert loaded.id == "file-test"
        assert len(loaded.nodes) == 1

    def test_serialized_json_is_valid(self):
        from mascarade.node_engine.graph import Graph
        from mascarade.node_engine.persistence import (
            CURRENT_SCHEMA_VERSION,
            SCHEMA_NAME,
            GraphSerializer,
        )

        graph = Graph(id="json-test", name="JSON Test")
        serializer = GraphSerializer()
        data = serializer.serialize(graph)

        # Should be JSON-serializable
        json_str = json.dumps(data)
        parsed = json.loads(json_str)

        assert parsed["version"] == CURRENT_SCHEMA_VERSION
        assert parsed["schema"] == SCHEMA_NAME
        assert parsed["graph"]["id"] == "json-test"

    def test_deserialization_missing_graph_key_raises(self):
        from mascarade.node_engine.persistence import (
            CURRENT_SCHEMA_VERSION,
            SCHEMA_NAME,
            GraphSerializer,
        )

        serializer = GraphSerializer()
        with pytest.raises(ValueError, match="graph"):
            serializer.deserialize({"version": CURRENT_SCHEMA_VERSION, "schema": SCHEMA_NAME})
