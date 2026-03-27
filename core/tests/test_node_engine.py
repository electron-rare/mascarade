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


# ---------------------------------------------------------------------------
# 7. AIWorker streaming support
# ---------------------------------------------------------------------------


class TestAIWorkerStreaming:
    """Verify AIWorker exposes execute_stream and returns an async generator."""

    def test_ai_worker_has_execute_stream(self):
        from mascarade.node_engine.workers.ai.worker import AIWorker

        assert hasattr(AIWorker, "execute_stream")
        assert callable(getattr(AIWorker, "execute_stream"))

    @pytest.mark.asyncio
    async def test_execute_stream_returns_async_generator(self):
        """execute_stream should return an async generator that yields chunks."""
        from unittest.mock import AsyncMock, MagicMock

        from mascarade.node_engine.workers.ai.worker import AIWorker

        # Build a mock router whose stream() is an async generator
        mock_router = MagicMock()

        async def _fake_stream(*args, **kwargs):
            for token in ["Hello", " ", "world"]:
                yield token

        mock_router.stream = _fake_stream

        mock_registry = MagicMock()

        worker = AIWorker(router=mock_router, registry=mock_registry)

        gen = worker.execute_stream(
            node_type="ai.llm-inference",
            inputs={"prompt": "Hi"},
            config={},
            context=None,
        )

        # Verify it is an async generator
        assert hasattr(gen, "__aiter__")
        assert hasattr(gen, "__anext__")

        chunks = []
        async for chunk in gen:
            chunks.append(chunk)

        # Should have 3 delta chunks + 1 final chunk
        assert len(chunks) == 4
        assert chunks[0] == {"delta": "Hello", "done": False}
        assert chunks[1] == {"delta": " ", "done": False}
        assert chunks[2] == {"delta": "world", "done": False}
        assert chunks[3]["done"] is True
        assert chunks[3]["content"] == "Hello world"

    def test_base_worker_execute_stream_raises(self):
        """NodeWorker.execute_stream should raise NotImplementedError by default."""
        from mascarade.node_engine.worker import NodeWorker

        assert hasattr(NodeWorker, "execute_stream")

    def test_ai_worker_capabilities_declares_streaming(self):
        from unittest.mock import MagicMock

        from mascarade.node_engine.workers.ai.worker import AIWorker

        worker = AIWorker(router=MagicMock(), registry=MagicMock())
        caps = worker.capabilities()
        assert caps["supports_streaming"] is True


# ---------------------------------------------------------------------------
# 8. CADWorker — pure calculation + sub-worker dispatch
# ---------------------------------------------------------------------------


class TestCADWorkerCapabilities:
    """Verify the CADWorker declares all node types from sub-workers."""

    def test_cad_worker_instantiation(self):
        from mascarade.node_engine.workers.cad.worker import CADWorker

        worker = CADWorker()
        assert worker.domain == "cad"
        assert worker.name == "cad-worker"

    def test_cad_worker_capabilities_has_all_node_types(self):
        from mascarade.node_engine.workers.cad.worker import CADWorker

        worker = CADWorker()
        caps = worker.capabilities()
        node_types = caps["node_types"]

        # Pure calculation nodes
        assert "cad.bom-generate" in node_types
        assert "cad.trace-width" in node_types
        assert "cad.thermal-via" in node_types
        assert "cad.stackup-calc" in node_types
        assert "cad.drc-check" in node_types
        assert "cad.footprint-lookup" in node_types

        # Mesh nodes
        assert "cad.mesh.import" in node_types
        assert "cad.mesh.export" in node_types
        assert "cad.mesh.simplify" in node_types
        assert "cad.mesh.boolean" in node_types
        assert "cad.mesh.validate" in node_types
        assert "cad.mesh.stats" in node_types

        # Toolpath nodes
        assert "cad.toolpath.generate_gcode" in node_types
        assert "cad.toolpath.optimize" in node_types
        assert "cad.toolpath.from_path" in node_types

        # FreeCAD nodes (MCP-dependent, but declared)
        assert "cad.freecad.create_document" in node_types
        assert "cad.freecad.export" in node_types

        # KiCad nodes (MCP-dependent, but declared)
        assert "cad.kicad.generate_schematic" in node_types
        assert "cad.kicad.perform_drc" in node_types


class TestCADWorkerPureCalculation:
    """Verify pure calculation nodes execute correctly through CADWorker."""

    @pytest.mark.asyncio
    async def test_trace_width(self):
        from mascarade.node_engine.workers.cad.worker import CADWorker

        worker = CADWorker()
        result = await worker.execute(
            "cad.trace-width",
            {"current": 1.0, "copper_thickness": 1.0, "temp_rise": 10.0, "layer": "external"},
            {},
        )
        assert "width_mm" in result
        assert result["width_mm"] > 0
        assert "width_mil" in result

    @pytest.mark.asyncio
    async def test_bom_generate(self):
        from mascarade.node_engine.workers.cad.worker import CADWorker

        worker = CADWorker()
        result = await worker.execute(
            "cad.bom-generate",
            {
                "components": [
                    {"ref": "R1", "value": "10k", "footprint": "0805", "qty": 1},
                    {"ref": "R2", "value": "10k", "footprint": "0805", "qty": 1},
                    {"ref": "C1", "value": "100nF", "footprint": "0402", "qty": 1},
                ]
            },
            {},
        )
        assert result["total_unique"] == 2
        assert result["total_qty"] == 3

    @pytest.mark.asyncio
    async def test_unsupported_node_type_raises(self):
        from mascarade.node_engine.workers.cad.worker import CADWorker

        worker = CADWorker()
        with pytest.raises(ValueError, match="Unsupported CAD node type"):
            await worker.execute("cad.nonexistent", {}, {})


# ---------------------------------------------------------------------------
# 9. MeshWorker — pure-Python mesh operations
# ---------------------------------------------------------------------------


class TestMeshWorker:
    """Test MeshWorker STL parsing, validation, stats, and export."""

    CUBE_STL = """solid cube
  facet normal 0 0 -1
    outer loop
      vertex 0 0 0
      vertex 1 0 0
      vertex 1 1 0
    endloop
  endfacet
  facet normal 0 0 -1
    outer loop
      vertex 0 0 0
      vertex 1 1 0
      vertex 0 1 0
    endloop
  endfacet
  facet normal 0 0 1
    outer loop
      vertex 0 0 1
      vertex 1 1 1
      vertex 1 0 1
    endloop
  endfacet
  facet normal 0 0 1
    outer loop
      vertex 0 0 1
      vertex 0 1 1
      vertex 1 1 1
    endloop
  endfacet
endsolid cube"""

    @pytest.mark.asyncio
    async def test_mesh_import_stl(self):
        from mascarade.node_engine.workers.cad.mesh_worker import MeshWorker

        worker = MeshWorker()
        result = await worker.execute("cad.mesh.import", {"data": self.CUBE_STL, "format": "stl"})
        assert "mesh" in result
        assert "stats" in result
        mesh = result["mesh"]
        assert len(mesh["vertices"]) > 0
        assert len(mesh["faces"]) == 4
        assert mesh["format"] == "stl"

    @pytest.mark.asyncio
    async def test_mesh_validate_valid(self):
        from mascarade.node_engine.workers.cad.mesh_worker import MeshWorker

        worker = MeshWorker()
        result = await worker.execute(
            "cad.mesh.validate", {"data": self.CUBE_STL, "format": "stl"}
        )
        assert result["valid"] is True
        assert result["triangle_count"] == 4
        assert result["vertex_count"] > 0
        assert "bounding_box" in result

    @pytest.mark.asyncio
    async def test_mesh_validate_empty(self):
        from mascarade.node_engine.workers.cad.mesh_worker import MeshWorker

        worker = MeshWorker()
        result = await worker.execute("cad.mesh.validate", {})
        assert result["valid"] is False

    @pytest.mark.asyncio
    async def test_mesh_stats(self):
        from mascarade.node_engine.workers.cad.mesh_worker import MeshWorker

        worker = MeshWorker()
        mesh = {
            "vertices": [[0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0]],
            "faces": [[0, 1, 2], [0, 2, 3]],
            "normals": [],
            "format": "stl",
        }
        result = await worker.execute("cad.mesh.stats", {"mesh": mesh})
        assert result["vertex_count"] == 4
        assert result["face_count"] == 2
        assert result["bounding_box"]["min"] == [0, 0, 0]
        assert result["bounding_box"]["max"] == [1, 1, 0]
        assert result["surface_area"] > 0

    @pytest.mark.asyncio
    async def test_mesh_export_stl(self):
        from mascarade.node_engine.workers.cad.mesh_worker import MeshWorker

        worker = MeshWorker()
        mesh = {
            "vertices": [[0, 0, 0], [1, 0, 0], [0, 1, 0]],
            "faces": [[0, 1, 2]],
            "normals": [],
            "format": "stl",
        }
        result = await worker.execute("cad.mesh.export", {"mesh": mesh, "format": "stl"})
        assert "data" in result
        assert "solid mesh" in result["data"]
        assert "endsolid mesh" in result["data"]

    @pytest.mark.asyncio
    async def test_mesh_boolean_union(self):
        from mascarade.node_engine.workers.cad.mesh_worker import MeshWorker

        worker = MeshWorker()
        mesh_a = {
            "vertices": [[0, 0, 0], [1, 0, 0], [0, 1, 0]],
            "faces": [[0, 1, 2]],
            "normals": [],
            "format": "stl",
        }
        mesh_b = {
            "vertices": [[2, 0, 0], [3, 0, 0], [2, 1, 0]],
            "faces": [[0, 1, 2]],
            "normals": [],
            "format": "stl",
        }
        result = await worker.execute(
            "cad.mesh.boolean", {"mesh_a": mesh_a, "mesh_b": mesh_b, "operation": "union"}
        )
        assert len(result["mesh"]["vertices"]) == 6
        assert len(result["mesh"]["faces"]) == 2

    @pytest.mark.asyncio
    async def test_mesh_dispatch_from_cad_worker(self):
        """Verify mesh operations dispatch through the main CADWorker."""
        from mascarade.node_engine.workers.cad.worker import CADWorker

        worker = CADWorker()
        mesh = {
            "vertices": [[0, 0, 0], [1, 0, 0], [0, 1, 0]],
            "faces": [[0, 1, 2]],
            "normals": [],
            "format": "stl",
        }
        result = await worker.execute("cad.mesh.stats", {"mesh": mesh}, {})
        assert result["vertex_count"] == 3
        assert result["face_count"] == 1


# ---------------------------------------------------------------------------
# 10. ToolpathWorker — G-code generation
# ---------------------------------------------------------------------------


class TestToolpathWorker:
    """Test ToolpathWorker G-code generation."""

    @pytest.mark.asyncio
    async def test_generate_gcode_adaptive(self):
        from mascarade.node_engine.workers.cad.toolpath_worker import ToolpathWorker

        worker = ToolpathWorker()
        mesh = {
            "vertices": [[0, 0, 0], [50, 0, 0], [50, 30, 0], [0, 30, 0]],
            "faces": [[0, 1, 2], [0, 2, 3]],
            "normals": [],
            "format": "stl",
        }
        result = await worker.execute(
            "cad.toolpath.generate_gcode",
            {
                "mesh": mesh,
                "tool": {"diameter": 6.0, "material": "carbide"},
                "strategy": "adaptive",
            },
        )
        assert "gcode" in result
        assert "toolpath" in result
        program = result["gcode"]["program"]
        assert "G21" in program  # mm units
        assert "G90" in program  # absolute positioning
        assert "M30" in program  # end program

    @pytest.mark.asyncio
    async def test_from_path_rectangle(self):
        from mascarade.node_engine.workers.cad.toolpath_worker import ToolpathWorker

        worker = ToolpathWorker()
        result = await worker.execute(
            "cad.toolpath.from_path",
            {"path": "rectangle 50x30", "feed_rate": 1000, "depth": 2.0},
        )
        assert "gcode" in result
        program = result["gcode"]["program"]
        assert "G21" in program
        # Rectangle should have 5 cutting moves (closed rectangle)
        assert result["gcode"]["estimated_time_s"] > 0

    @pytest.mark.asyncio
    async def test_from_path_point_list(self):
        from mascarade.node_engine.workers.cad.toolpath_worker import ToolpathWorker

        worker = ToolpathWorker()
        result = await worker.execute(
            "cad.toolpath.from_path",
            {
                "path": [
                    {"x": 0, "y": 0, "z": -1},
                    {"x": 10, "y": 0, "z": -1},
                    {"x": 10, "y": 10, "z": -1},
                ],
                "feed_rate": 500,
            },
        )
        assert len(result["toolpath"]["moves"]) >= 3

    @pytest.mark.asyncio
    async def test_toolpath_dispatch_from_cad_worker(self):
        """Verify toolpath operations dispatch through the main CADWorker."""
        from mascarade.node_engine.workers.cad.worker import CADWorker

        worker = CADWorker()
        result = await worker.execute(
            "cad.toolpath.from_path",
            {"path": "rectangle 20x10"},
            {},
        )
        assert "gcode" in result
        assert "G21" in result["gcode"]["program"]

    @pytest.mark.asyncio
    async def test_invalid_strategy_raises(self):
        from mascarade.node_engine.workers.cad.toolpath_worker import ToolpathWorker

        worker = ToolpathWorker()
        with pytest.raises(ValueError, match="Invalid strategy"):
            await worker.execute(
                "cad.toolpath.generate_gcode",
                {
                    "mesh": {"vertices": [[0, 0, 0]], "faces": [], "format": "stl"},
                    "tool": {"diameter": 6.0},
                    "strategy": "invalid_strategy",
                },
            )


# ---------------------------------------------------------------------------
# 11. Sub-worker imports
# ---------------------------------------------------------------------------


class TestCADSubWorkerImports:
    """Verify all CAD sub-workers are importable without errors."""

    def test_import_mesh_worker(self):
        from mascarade.node_engine.workers.cad.mesh_worker import MeshWorker

        w = MeshWorker()
        assert len(w.node_types) >= 4

    def test_import_toolpath_worker(self):
        from mascarade.node_engine.workers.cad.toolpath_worker import ToolpathWorker

        w = ToolpathWorker()
        assert len(w.node_types) >= 2

    def test_import_freecad_worker(self):
        from mascarade.node_engine.workers.cad.freecad_worker import FreeCADWorker

        w = FreeCADWorker()
        assert len(w.node_types) == 4

    def test_import_kicad_worker(self):
        from mascarade.node_engine.workers.cad.kicad_worker import KiCadWorker

        w = KiCadWorker()
        assert len(w.node_types) == 5


# ---------------------------------------------------------------------------
# 12. AIWorker function-call node
# ---------------------------------------------------------------------------


class TestAIWorkerFunctionCall:
    """Verify the ai.function-call node type."""

    def test_function_call_in_capabilities(self):
        from unittest.mock import MagicMock

        from mascarade.node_engine.workers.ai.worker import AIWorker

        worker = AIWorker(router=MagicMock(), registry=MagicMock())
        caps = worker.capabilities()
        assert "ai.function-call" in caps["node_types"]

    @pytest.mark.asyncio
    async def test_function_call_validation_missing_prompt(self):
        from unittest.mock import MagicMock

        from mascarade.node_engine.workers.ai.worker import AIWorker

        worker = AIWorker(router=MagicMock(), registry=MagicMock())
        errors = await worker.validate(
            "ai.function-call",
            {"tools": [{"function": {"name": "test"}}]},
            {},
        )
        assert any("prompt" in e for e in errors)

    @pytest.mark.asyncio
    async def test_function_call_validation_missing_tools(self):
        from unittest.mock import MagicMock

        from mascarade.node_engine.workers.ai.worker import AIWorker

        worker = AIWorker(router=MagicMock(), registry=MagicMock())
        errors = await worker.validate(
            "ai.function-call",
            {"prompt": "test"},
            {},
        )
        assert any("tools" in e for e in errors)

    @pytest.mark.asyncio
    async def test_function_call_validation_empty_tools(self):
        from unittest.mock import MagicMock

        from mascarade.node_engine.workers.ai.worker import AIWorker

        worker = AIWorker(router=MagicMock(), registry=MagicMock())
        errors = await worker.validate(
            "ai.function-call",
            {"prompt": "test", "tools": []},
            {},
        )
        assert any("empty" in e for e in errors)

    @pytest.mark.asyncio
    async def test_function_call_validation_tool_missing_name(self):
        from unittest.mock import MagicMock

        from mascarade.node_engine.workers.ai.worker import AIWorker

        worker = AIWorker(router=MagicMock(), registry=MagicMock())
        errors = await worker.validate(
            "ai.function-call",
            {"prompt": "test", "tools": [{"function": {"description": "no name"}}]},
            {},
        )
        assert any("name" in e for e in errors)

    @pytest.mark.asyncio
    async def test_function_call_validation_valid(self):
        from unittest.mock import MagicMock

        from mascarade.node_engine.workers.ai.worker import AIWorker

        worker = AIWorker(router=MagicMock(), registry=MagicMock())
        errors = await worker.validate(
            "ai.function-call",
            {
                "prompt": "What is the weather?",
                "tools": [
                    {
                        "type": "function",
                        "function": {
                            "name": "get_weather",
                            "description": "Get weather",
                            "parameters": {
                                "type": "object",
                                "properties": {"location": {"type": "string"}},
                            },
                        },
                    }
                ],
            },
            {},
        )
        assert errors == []

    @pytest.mark.asyncio
    async def test_function_call_execute_parses_json(self):
        """execute() should parse the LLM response and extract function name + args."""
        from unittest.mock import AsyncMock, MagicMock

        from mascarade.node_engine.workers.ai.worker import AIWorker

        # Mock router that returns a JSON function call
        mock_response = MagicMock()
        mock_response.content = '{"function_name": "get_weather", "arguments": {"location": "Paris"}}'

        mock_router = MagicMock()
        mock_router.send = AsyncMock(return_value=mock_response)

        worker = AIWorker(router=mock_router, registry=MagicMock())
        result = await worker.execute(
            "ai.function-call",
            {
                "prompt": "What is the weather in Paris?",
                "tools": [
                    {
                        "type": "function",
                        "function": {
                            "name": "get_weather",
                            "description": "Get weather",
                            "parameters": {},
                        },
                    }
                ],
            },
            {},
            None,
        )

        assert result["function_name"] == "get_weather"
        assert result["arguments"] == {"location": "Paris"}
        assert "raw_response" in result

    @pytest.mark.asyncio
    async def test_function_call_execute_parses_fenced_json(self):
        """execute() should handle LLM responses wrapped in markdown code blocks."""
        from unittest.mock import AsyncMock, MagicMock

        from mascarade.node_engine.workers.ai.worker import AIWorker

        mock_response = MagicMock()
        mock_response.content = (
            'Here is the function call:\n```json\n'
            '{"function_name": "search", "arguments": {"query": "test"}}\n```'
        )

        mock_router = MagicMock()
        mock_router.send = AsyncMock(return_value=mock_response)

        worker = AIWorker(router=mock_router, registry=MagicMock())
        result = await worker.execute(
            "ai.function-call",
            {
                "prompt": "Search for test",
                "tools": [{"function": {"name": "search", "parameters": {}}}],
            },
            {},
            None,
        )

        assert result["function_name"] == "search"
        assert result["arguments"] == {"query": "test"}


# ---------------------------------------------------------------------------
# 13. CrossDomainOrchestrator
# ---------------------------------------------------------------------------


class TestCrossDomainOrchestrator:
    """Test the CrossDomainOrchestrator for multi-domain graph execution."""

    def test_orchestrator_import(self):
        from mascarade.node_engine.cross_domain.orchestrator import (
            CrossDomainOrchestrator,
            OrchestrationResult,
        )

        assert CrossDomainOrchestrator is not None
        assert OrchestrationResult is not None

    def test_orchestrator_construction(self):
        from mascarade.node_engine.cross_domain.orchestrator import CrossDomainOrchestrator
        from mascarade.node_engine.cross_domain.register import AdapterRegistry
        from mascarade.node_engine.runtime import GraphRuntime

        runtime = GraphRuntime()
        registry = AdapterRegistry()
        orchestrator = CrossDomainOrchestrator(runtime, registry)
        assert orchestrator.runtime is runtime
        assert orchestrator.adapter_registry is registry

    def test_analyze_no_transitions_same_domain(self):
        """Graph with all nodes in the same domain should have no transitions."""
        from mascarade.node_engine.cross_domain.orchestrator import CrossDomainOrchestrator
        from mascarade.node_engine.cross_domain.register import AdapterRegistry
        from mascarade.node_engine.graph import Edge, Graph, Node
        from mascarade.node_engine.runtime import GraphRuntime

        nodes = [
            Node(id="n1", type="ai.llm-inference"),
            Node(id="n2", type="ai.summarize"),
        ]
        edges = [Edge(from_node="n1", from_port="out", to_node="n2", to_port="in")]
        graph = Graph(id="same-domain", nodes=nodes, edges=edges)

        orchestrator = CrossDomainOrchestrator(GraphRuntime(), AdapterRegistry())
        transitions = orchestrator.analyze_domain_transitions(graph)
        assert transitions == []

    def test_analyze_detects_cross_domain_transition(self):
        """Graph with AI -> CAD edge should detect one transition."""
        from mascarade.node_engine.cross_domain.orchestrator import CrossDomainOrchestrator
        from mascarade.node_engine.cross_domain.register import AdapterRegistry
        from mascarade.node_engine.graph import Edge, Graph, Node
        from mascarade.node_engine.runtime import GraphRuntime

        nodes = [
            Node(id="n1", type="ai.llm-inference"),
            Node(id="n2", type="cad.bom-generate"),
        ]
        edges = [Edge(from_node="n1", from_port="response", to_node="n2", to_port="components")]
        graph = Graph(id="cross-domain", nodes=nodes, edges=edges)

        orchestrator = CrossDomainOrchestrator(GraphRuntime(), AdapterRegistry())
        transitions = orchestrator.analyze_domain_transitions(graph)
        assert len(transitions) == 1
        assert transitions[0]["source_domain"] == "ai"
        assert transitions[0]["target_domain"] == "cad"

    def test_insert_adapter_nodes(self):
        """insert_adapter_nodes should add an adapter node and rewire edges."""
        from mascarade.node_engine.cross_domain.orchestrator import CrossDomainOrchestrator
        from mascarade.node_engine.cross_domain.register import (
            AdapterRegistry,
            register_all_adapters,
        )
        from mascarade.node_engine.graph import Edge, Graph, Node
        from mascarade.node_engine.runtime import GraphRuntime

        nodes = [
            Node(id="n1", type="ai.llm-inference"),
            Node(id="n2", type="cad.bom-generate"),
        ]
        edges = [Edge(from_node="n1", from_port="response", to_node="n2", to_port="components")]
        graph = Graph(id="cross-domain", nodes=nodes, edges=edges)

        adapter_registry = AdapterRegistry()
        register_all_adapters(adapter_registry)

        orchestrator = CrossDomainOrchestrator(GraphRuntime(), adapter_registry)
        transitions = orchestrator.analyze_domain_transitions(graph)

        augmented, records = orchestrator.insert_adapter_nodes(graph, transitions)

        # Should have 3 nodes: original 2 + 1 adapter
        assert augmented.node_count == 3
        # Should have 2 edges: n1 -> adapter, adapter -> n2
        assert augmented.edge_count == 2
        # Should have one insertion record
        assert len(records) == 1
        assert records[0].source_domain == "ai"
        assert records[0].target_domain == "cad"
        assert records[0].source_node_id == "n1"
        assert records[0].target_node_id == "n2"

    def test_insert_no_adapter_raises_for_unknown_transition(self):
        """insert_adapter_nodes should raise KeyError if no adapter exists."""
        from mascarade.node_engine.cross_domain.orchestrator import CrossDomainOrchestrator
        from mascarade.node_engine.cross_domain.register import AdapterRegistry
        from mascarade.node_engine.graph import Edge, Graph, Node
        from mascarade.node_engine.runtime import GraphRuntime

        nodes = [
            Node(id="n1", type="unknown.foo"),
            Node(id="n2", type="other.bar"),
        ]
        edges = [Edge(from_node="n1", from_port="out", to_node="n2", to_port="in")]
        graph = Graph(id="missing-adapter", nodes=nodes, edges=edges)

        orchestrator = CrossDomainOrchestrator(GraphRuntime(), AdapterRegistry())
        transitions = orchestrator.analyze_domain_transitions(graph)

        with pytest.raises(KeyError, match="No adapter registered"):
            orchestrator.insert_adapter_nodes(graph, transitions)

    def test_orchestration_result_conversion_metadata(self):
        """OrchestrationResult.conversion_metadata returns correct structure."""
        from mascarade.node_engine.cross_domain.orchestrator import (
            AdapterInsertionRecord,
            OrchestrationResult,
        )
        from mascarade.node_engine.runtime import ExecutionStatus, GraphExecutionContext

        ctx = GraphExecutionContext(
            graph_id="test",
            status=ExecutionStatus.COMPLETED,
        )
        record = AdapterInsertionRecord(
            adapter_node_id="_adapter_ai_to_cad_abc",
            mapping_id="ai.LLMResponse->cad.CADDocument",
            source_node_id="n1",
            source_port="response",
            target_node_id="n2",
            target_port="components",
            source_domain="ai",
            target_domain="cad",
            lossy=True,
        )
        result = OrchestrationResult(
            execution_context=ctx,
            adapter_insertions=[record],
            original_node_count=2,
            augmented_node_count=3,
        )

        assert result.status == ExecutionStatus.COMPLETED
        meta = result.conversion_metadata
        assert len(meta) == 1
        assert meta[0]["mapping_id"] == "ai.LLMResponse->cad.CADDocument"
        assert meta[0]["lossy"] is True
        assert meta[0]["source_domain"] == "ai"
        assert meta[0]["target_domain"] == "cad"

    def test_no_transitions_returns_original_graph(self):
        """insert_adapter_nodes with empty transitions returns the original graph."""
        from mascarade.node_engine.cross_domain.orchestrator import CrossDomainOrchestrator
        from mascarade.node_engine.cross_domain.register import AdapterRegistry
        from mascarade.node_engine.graph import Edge, Graph, Node
        from mascarade.node_engine.runtime import GraphRuntime

        nodes = [
            Node(id="n1", type="ai.llm-inference"),
            Node(id="n2", type="ai.summarize"),
        ]
        edges = [Edge(from_node="n1", from_port="out", to_node="n2", to_port="in")]
        graph = Graph(id="same-domain", nodes=nodes, edges=edges)

        orchestrator = CrossDomainOrchestrator(GraphRuntime(), AdapterRegistry())
        augmented, records = orchestrator.insert_adapter_nodes(graph, [])

        assert augmented is graph  # Same object, not copied
        assert records == []


# ---------------------------------------------------------------------------
# 14. Phase 2 — CAD Worker registration with GraphRuntime
# ---------------------------------------------------------------------------


class TestCADWorkerRegistration:
    """Verify register_cad_worker registers CADWorker with GraphRuntime."""

    def test_register_cad_worker_with_runtime(self):
        from mascarade.node_engine.runtime import GraphRuntime
        from mascarade.node_engine.workers.cad.register import register_cad_worker

        runtime = GraphRuntime()
        cad_worker = register_cad_worker(runtime)

        assert cad_worker is not None
        assert cad_worker.domain == "cad"
        assert cad_worker.name == "cad-worker"

        # Verify it's registered in the runtime
        worker = runtime.get_worker("cad")
        assert worker is cad_worker

    def test_register_cad_worker_listed(self):
        from mascarade.node_engine.runtime import GraphRuntime
        from mascarade.node_engine.workers.cad.register import register_cad_worker

        runtime = GraphRuntime()
        register_cad_worker(runtime)

        workers = runtime.list_workers()
        domains = [w["domain"] for w in workers]
        assert "cad" in domains

    @pytest.mark.asyncio
    async def test_execute_mesh_node_through_runtime(self):
        """Register CAD worker and execute a mesh.stats node via runtime.execute_node."""
        from mascarade.node_engine.runtime import GraphRuntime
        from mascarade.node_engine.workers.cad.register import register_cad_worker

        runtime = GraphRuntime()
        register_cad_worker(runtime)

        mesh = {
            "vertices": [[0, 0, 0], [1, 0, 0], [0, 1, 0]],
            "faces": [[0, 1, 2]],
            "normals": [],
            "format": "stl",
        }
        result = await runtime.execute_node(
            "cad.mesh.stats",
            {"mesh": mesh},
        )
        assert result["vertex_count"] == 3
        assert result["face_count"] == 1

    @pytest.mark.asyncio
    async def test_execute_trace_width_through_runtime(self):
        """Register CAD worker and execute a pure calculation node."""
        from mascarade.node_engine.runtime import GraphRuntime
        from mascarade.node_engine.workers.cad.register import register_cad_worker

        runtime = GraphRuntime()
        register_cad_worker(runtime)

        result = await runtime.execute_node(
            "cad.trace-width",
            {"current": 1.0, "copper_thickness": 1.0, "temp_rise": 10.0, "layer": "external"},
        )
        assert "width_mm" in result
        assert result["width_mm"] > 0

    def test_cad_worker_exported_from_init(self):
        """Verify register_cad_worker is exported from node_engine __init__."""
        from mascarade.node_engine import register_cad_worker

        assert callable(register_cad_worker)


# ---------------------------------------------------------------------------
# 15. Phase 4 — MIDI dispatch through HardwareWorker + safety interlocks
# ---------------------------------------------------------------------------


class TestHardwareWorkerMIDIDispatch:
    """Verify HardwareWorker delegates hardware.midi.* to MIDIWorker."""

    @pytest.mark.asyncio
    async def test_midi_note_sequence_via_hardware(self):
        from mascarade.node_engine.workers.hardware.worker import HardwareWorker

        worker = HardwareWorker()
        result = await worker.execute(
            "hardware.midi.note-sequence",
            {
                "notes": [
                    {"note": 60, "velocity": 100, "duration": 0.5},
                    {"note": 64, "velocity": 80, "duration": 0.25},
                ],
                "tempo": 120,
            },
            {},
        )
        assert "sequence" in result
        assert result["sequence"]["note_count"] == 2
        assert result["sequence"]["tempo"] == 120

    @pytest.mark.asyncio
    async def test_midi_pattern_generate_via_hardware(self):
        from mascarade.node_engine.workers.hardware.worker import HardwareWorker

        worker = HardwareWorker()
        result = await worker.execute(
            "hardware.midi.pattern-generate",
            {"scale": "pentatonic", "root": 48, "steps": 5},
            {},
        )
        assert "sequence" in result
        assert result["sequence"]["note_count"] == 5

    @pytest.mark.asyncio
    async def test_midi_cc_map_via_hardware(self):
        from mascarade.node_engine.workers.hardware.worker import HardwareWorker

        worker = HardwareWorker()
        result = await worker.execute(
            "hardware.midi.cc-map",
            {
                "mappings": [
                    {"name": "volume", "controller": 7, "channel": 0},
                    {"name": "pan", "controller": 10, "channel": 0},
                ]
            },
            {},
        )
        assert "cc_map" in result
        assert len(result["cc_map"]) == 2

    @pytest.mark.asyncio
    async def test_midi_transform_via_hardware(self):
        from mascarade.node_engine.workers.hardware.worker import HardwareWorker

        worker = HardwareWorker()
        seq = {
            "name": "test",
            "tempo": 120,
            "notes": [{"note": 60, "velocity": 100, "channel": 0, "duration": 0.5, "time": 0.0}],
        }
        result = await worker.execute(
            "hardware.midi.transform",
            {"sequence": seq, "transpose": 12},
            {},
        )
        assert result["sequence"]["notes"][0]["note"] == 72

    @pytest.mark.asyncio
    async def test_bare_midi_type_dispatches(self):
        """Bare midi.* types should also dispatch through HardwareWorker."""
        from mascarade.node_engine.workers.hardware.worker import HardwareWorker

        worker = HardwareWorker()
        result = await worker.execute(
            "midi.note-sequence",
            {"notes": [{"note": 60}], "tempo": 90},
            {},
        )
        assert "sequence" in result
        assert result["sequence"]["tempo"] == 90

    def test_hardware_capabilities_include_midi(self):
        from mascarade.node_engine.workers.hardware.worker import HardwareWorker

        worker = HardwareWorker()
        caps = worker.capabilities()
        node_types = [c["node_type"] for c in caps]
        assert "hardware.midi.note-sequence" in node_types
        assert "hardware.midi.cc-map" in node_types
        assert "hardware.midi.pattern-generate" in node_types
        assert "hardware.midi.transform" in node_types

    def test_hardware_capabilities_include_safety(self):
        from mascarade.node_engine.workers.hardware.worker import HardwareWorker

        worker = HardwareWorker()
        caps = worker.capabilities()
        node_types = [c["node_type"] for c in caps]
        assert "hardware.safety.check" in node_types


class TestHardwareWorkerSafetyInterlocks:
    """Verify safety interlock logic in HardwareWorker."""

    @pytest.mark.asyncio
    async def test_safety_check_all_pass(self):
        from mascarade.node_engine.workers.hardware.worker import HardwareWorker

        worker = HardwareWorker()
        result = await worker.execute(
            "hardware.safety.check",
            {
                "checks": [
                    {"type": "gpio", "value": 1, "label": "LED"},
                    {"type": "dmx", "value": 128, "label": "Par Light"},
                    {"type": "midi", "value": 64, "label": "CC Volume"},
                ]
            },
            {},
        )
        assert result["passed"] is True
        assert len(result["errors"]) == 0
        assert result["checks_performed"] == 3

    @pytest.mark.asyncio
    async def test_safety_check_gpio_out_of_range(self):
        from mascarade.node_engine.workers.hardware.worker import HardwareWorker

        worker = HardwareWorker()
        result = await worker.execute(
            "hardware.safety.check",
            {
                "checks": [
                    {"type": "gpio", "value": 5, "label": "Bad GPIO"},
                ]
            },
            {},
        )
        assert result["passed"] is False
        assert any("Bad GPIO" in e and "exceeds maximum" in e for e in result["errors"])

    @pytest.mark.asyncio
    async def test_safety_check_dmx_below_min(self):
        from mascarade.node_engine.workers.hardware.worker import HardwareWorker

        worker = HardwareWorker()
        result = await worker.execute(
            "hardware.safety.check",
            {
                "checks": [
                    {"type": "dmx", "value": -1, "label": "Underflow DMX"},
                ]
            },
            {},
        )
        assert result["passed"] is False
        assert any("below minimum" in e for e in result["errors"])

    @pytest.mark.asyncio
    async def test_safety_check_midi_out_of_range(self):
        from mascarade.node_engine.workers.hardware.worker import HardwareWorker

        worker = HardwareWorker()
        result = await worker.execute(
            "hardware.safety.check",
            {
                "checks": [
                    {"type": "midi", "value": 200, "label": "Velocity"},
                ]
            },
            {},
        )
        assert result["passed"] is False
        assert any("exceeds maximum" in e for e in result["errors"])

    @pytest.mark.asyncio
    async def test_safety_check_boundary_warning(self):
        from mascarade.node_engine.workers.hardware.worker import HardwareWorker

        worker = HardwareWorker()
        result = await worker.execute(
            "hardware.safety.check",
            {
                "checks": [
                    {"type": "dmx", "value": 254, "label": "Near Max DMX"},
                ]
            },
            {},
        )
        assert result["passed"] is True
        assert any("near maximum" in w for w in result["warnings"])

    @pytest.mark.asyncio
    async def test_safety_check_custom_range(self):
        from mascarade.node_engine.workers.hardware.worker import HardwareWorker

        worker = HardwareWorker()
        result = await worker.execute(
            "hardware.safety.check",
            {
                "checks": [
                    {"type": "dmx", "value": 100, "min": 0, "max": 50, "label": "Custom Max"},
                ]
            },
            {},
        )
        assert result["passed"] is False
        assert any("exceeds maximum 50" in e for e in result["errors"])

    @pytest.mark.asyncio
    async def test_safety_check_unknown_type_warns(self):
        from mascarade.node_engine.workers.hardware.worker import HardwareWorker

        worker = HardwareWorker()
        result = await worker.execute(
            "hardware.safety.check",
            {
                "checks": [
                    {"type": "unknown_device", "value": 42},
                ]
            },
            {},
        )
        assert result["passed"] is True  # no errors, just warnings
        assert any("unknown check type" in w for w in result["warnings"])

    @pytest.mark.asyncio
    async def test_safety_check_missing_value_errors(self):
        from mascarade.node_engine.workers.hardware.worker import HardwareWorker

        worker = HardwareWorker()
        result = await worker.execute(
            "hardware.safety.check",
            {
                "checks": [
                    {"type": "gpio", "label": "No Value"},
                ]
            },
            {},
        )
        assert result["passed"] is False
        assert any("value is required" in e for e in result["errors"])

    @pytest.mark.asyncio
    async def test_safety_check_analog_gpio(self):
        from mascarade.node_engine.workers.hardware.worker import HardwareWorker

        worker = HardwareWorker()
        result = await worker.execute(
            "hardware.safety.check",
            {
                "checks": [
                    {"type": "gpio_analog", "value": 2048, "label": "ADC Mid"},
                    {"type": "gpio_analog", "value": 5000, "label": "ADC Over"},
                ]
            },
            {},
        )
        assert result["passed"] is False
        assert any("ADC Over" in e and "exceeds maximum" in e for e in result["errors"])

    @pytest.mark.asyncio
    async def test_register_hardware_worker_with_runtime(self):
        """Register hardware worker with runtime and execute safety check."""
        from mascarade.node_engine.runtime import GraphRuntime
        from mascarade.node_engine.workers.hardware.register import register_hardware_worker

        runtime = GraphRuntime()
        hw_worker = register_hardware_worker(runtime)

        assert hw_worker is not None
        assert hw_worker.domain == "hardware"

        worker = runtime.get_worker("hardware")
        assert worker is hw_worker

        # Execute safety check through runtime
        result = await runtime.execute_node(
            "hardware.safety.check",
            {"checks": [{"type": "dmx", "value": 128}]},
        )
        assert result["passed"] is True


# ---------------------------------------------------------------------------
# 16. Phase 1 — ai.agent-dispatch with task input
# ---------------------------------------------------------------------------


class TestAIAgentDispatchTaskInput:
    """Verify ai.agent-dispatch accepts 'task' as an alias for 'message'."""

    @pytest.mark.asyncio
    async def test_dispatch_validate_accepts_task(self):
        """Validation should pass when 'task' is provided instead of 'message'."""
        from unittest.mock import MagicMock

        from mascarade.node_engine.workers.ai.worker import AIWorker

        mock_registry = MagicMock()
        mock_registry.get.return_value = MagicMock()  # Agent exists

        worker = AIWorker(router=MagicMock(), registry=mock_registry)
        errors = await worker.validate(
            "ai.agent-dispatch",
            {"agent_name": "test-agent", "task": "Summarize this document"},
            {},
        )
        assert errors == []

    @pytest.mark.asyncio
    async def test_dispatch_validate_accepts_message(self):
        """Validation should still pass with the legacy 'message' input."""
        from unittest.mock import MagicMock

        from mascarade.node_engine.workers.ai.worker import AIWorker

        mock_registry = MagicMock()
        mock_registry.get.return_value = MagicMock()

        worker = AIWorker(router=MagicMock(), registry=mock_registry)
        errors = await worker.validate(
            "ai.agent-dispatch",
            {"agent_name": "test-agent", "message": "Hello"},
            {},
        )
        assert errors == []

    @pytest.mark.asyncio
    async def test_dispatch_validate_missing_task_and_message(self):
        """Validation should fail when neither 'task' nor 'message' is provided."""
        from unittest.mock import MagicMock

        from mascarade.node_engine.workers.ai.worker import AIWorker

        mock_registry = MagicMock()
        mock_registry.get.return_value = MagicMock()

        worker = AIWorker(router=MagicMock(), registry=mock_registry)
        errors = await worker.validate(
            "ai.agent-dispatch",
            {"agent_name": "test-agent"},
            {},
        )
        assert any("task" in e for e in errors)

    @pytest.mark.asyncio
    async def test_dispatch_validate_missing_agent_name(self):
        from unittest.mock import MagicMock

        from mascarade.node_engine.workers.ai.worker import AIWorker

        worker = AIWorker(router=MagicMock(), registry=MagicMock())
        errors = await worker.validate(
            "ai.agent-dispatch",
            {"task": "Do something"},
            {},
        )
        assert any("agent_name" in e for e in errors)

    @pytest.mark.asyncio
    async def test_dispatch_validate_agent_not_found(self):
        from unittest.mock import MagicMock

        from mascarade.node_engine.workers.ai.worker import AIWorker

        mock_registry = MagicMock()
        mock_registry.get.side_effect = KeyError("not found")

        worker = AIWorker(router=MagicMock(), registry=mock_registry)
        errors = await worker.validate(
            "ai.agent-dispatch",
            {"agent_name": "nonexistent", "task": "Test"},
            {},
        )
        assert any("not found" in e for e in errors)

    @pytest.mark.asyncio
    async def test_dispatch_execute_with_task_input(self):
        """execute() should use 'task' input as the prompt for the agent."""
        from unittest.mock import AsyncMock, MagicMock

        from mascarade.node_engine.workers.ai.worker import AIWorker

        mock_response = MagicMock()
        mock_response.content = "Agent result"

        mock_agent = MagicMock()
        mock_agent.run = AsyncMock(return_value=mock_response)

        mock_registry = MagicMock()
        mock_registry.get.return_value = mock_agent

        worker = AIWorker(router=MagicMock(), registry=mock_registry)
        result = await worker.execute(
            "ai.agent-dispatch",
            {"agent_name": "test-agent", "task": "Analyze this data", "context": {"key": "value"}},
            {},
            None,
        )

        assert result["response"] == mock_response
        mock_agent.run.assert_called_once()
        # Verify 'task' was passed as the prompt
        call_kwargs = mock_agent.run.call_args
        assert call_kwargs.kwargs["prompt"] == "Analyze this data"

    @pytest.mark.asyncio
    async def test_dispatch_execute_with_optional_context(self):
        """execute() should pass optional JSON context to the agent."""
        from unittest.mock import AsyncMock, MagicMock

        from mascarade.node_engine.workers.ai.worker import AIWorker

        mock_response = MagicMock()
        mock_agent = MagicMock()
        mock_agent.run = AsyncMock(return_value=mock_response)

        mock_registry = MagicMock()
        mock_registry.get.return_value = mock_agent

        worker = AIWorker(router=MagicMock(), registry=mock_registry)
        ctx = {"document_id": "doc-123", "format": "pdf"}
        result = await worker.execute(
            "ai.agent-dispatch",
            {"agent_name": "summarizer", "task": "Summarize", "context": ctx},
            {},
            None,
        )

        call_kwargs = mock_agent.run.call_args
        assert call_kwargs.kwargs["context"] == ctx


# ---------------------------------------------------------------------------
# 17. Phase 1 — ai.classify node tests
# ---------------------------------------------------------------------------


class TestAIClassifyNode:
    """Verify ai.classify node validation and execution."""

    @pytest.mark.asyncio
    async def test_classify_validate_valid(self):
        from unittest.mock import MagicMock

        from mascarade.node_engine.workers.ai.worker import AIWorker

        worker = AIWorker(router=MagicMock(), registry=MagicMock())
        errors = await worker.validate(
            "ai.classify",
            {"text": "This is a bug report", "categories": ["bug", "feature", "question"]},
            {},
        )
        assert errors == []

    @pytest.mark.asyncio
    async def test_classify_validate_missing_text(self):
        from unittest.mock import MagicMock

        from mascarade.node_engine.workers.ai.worker import AIWorker

        worker = AIWorker(router=MagicMock(), registry=MagicMock())
        errors = await worker.validate(
            "ai.classify",
            {"categories": ["a", "b"]},
            {},
        )
        assert any("text" in e for e in errors)

    @pytest.mark.asyncio
    async def test_classify_validate_missing_categories(self):
        from unittest.mock import MagicMock

        from mascarade.node_engine.workers.ai.worker import AIWorker

        worker = AIWorker(router=MagicMock(), registry=MagicMock())
        errors = await worker.validate(
            "ai.classify",
            {"text": "Hello"},
            {},
        )
        assert any("categories" in e for e in errors)

    @pytest.mark.asyncio
    async def test_classify_validate_empty_categories(self):
        from unittest.mock import MagicMock

        from mascarade.node_engine.workers.ai.worker import AIWorker

        worker = AIWorker(router=MagicMock(), registry=MagicMock())
        errors = await worker.validate(
            "ai.classify",
            {"text": "Hello", "categories": []},
            {},
        )
        assert any("empty" in e for e in errors)

    @pytest.mark.asyncio
    async def test_classify_validate_text_not_string(self):
        from unittest.mock import MagicMock

        from mascarade.node_engine.workers.ai.worker import AIWorker

        worker = AIWorker(router=MagicMock(), registry=MagicMock())
        errors = await worker.validate(
            "ai.classify",
            {"text": 123, "categories": ["a"]},
            {},
        )
        assert any("string" in e for e in errors)

    @pytest.mark.asyncio
    async def test_classify_execute(self):
        """execute() should return a category and confidence."""
        from unittest.mock import AsyncMock, MagicMock

        from mascarade.node_engine.workers.ai.worker import AIWorker

        mock_response = MagicMock()
        mock_response.content = "bug"

        mock_router = MagicMock()
        mock_router.send = AsyncMock(return_value=mock_response)

        worker = AIWorker(router=mock_router, registry=MagicMock())
        result = await worker.execute(
            "ai.classify",
            {"text": "The app crashes on login", "categories": ["bug", "feature", "question"]},
            {},
            None,
        )

        assert result["category"] == "bug"
        assert isinstance(result["confidence"], float)
        assert 0.0 <= result["confidence"] <= 1.0

    @pytest.mark.asyncio
    async def test_classify_uses_low_temperature(self):
        """classify should force temperature to 0.1 for deterministic results."""
        from unittest.mock import AsyncMock, MagicMock

        from mascarade.node_engine.workers.ai.worker import AIWorker

        mock_response = MagicMock()
        mock_response.content = "feature"

        mock_router = MagicMock()
        mock_router.send = AsyncMock(return_value=mock_response)

        worker = AIWorker(router=mock_router, registry=MagicMock())
        await worker.execute(
            "ai.classify",
            {"text": "Add dark mode", "categories": ["bug", "feature"]},
            {"temperature": 0.9},  # User config should be overridden
            None,
        )

        # Check the temperature passed to router.send
        call_kwargs = mock_router.send.call_args
        assert call_kwargs.kwargs["temperature"] == 0.1

    def test_classify_in_capabilities(self):
        from unittest.mock import MagicMock

        from mascarade.node_engine.workers.ai.worker import AIWorker

        worker = AIWorker(router=MagicMock(), registry=MagicMock())
        caps = worker.capabilities()
        assert "ai.classify" in caps["node_types"]


# ---------------------------------------------------------------------------
# 18. Phase 1 — ai.summarize node tests
# ---------------------------------------------------------------------------


class TestAISummarizeNode:
    """Verify ai.summarize node validation and execution."""

    @pytest.mark.asyncio
    async def test_summarize_validate_valid(self):
        from unittest.mock import MagicMock

        from mascarade.node_engine.workers.ai.worker import AIWorker

        worker = AIWorker(router=MagicMock(), registry=MagicMock())
        errors = await worker.validate(
            "ai.summarize",
            {"text": "A long document..."},
            {},
        )
        assert errors == []

    @pytest.mark.asyncio
    async def test_summarize_validate_with_max_length(self):
        from unittest.mock import MagicMock

        from mascarade.node_engine.workers.ai.worker import AIWorker

        worker = AIWorker(router=MagicMock(), registry=MagicMock())
        errors = await worker.validate(
            "ai.summarize",
            {"text": "Some text", "max_length": 50},
            {},
        )
        assert errors == []

    @pytest.mark.asyncio
    async def test_summarize_validate_missing_text(self):
        from unittest.mock import MagicMock

        from mascarade.node_engine.workers.ai.worker import AIWorker

        worker = AIWorker(router=MagicMock(), registry=MagicMock())
        errors = await worker.validate(
            "ai.summarize",
            {},
            {},
        )
        assert any("text" in e for e in errors)

    @pytest.mark.asyncio
    async def test_summarize_validate_text_not_string(self):
        from unittest.mock import MagicMock

        from mascarade.node_engine.workers.ai.worker import AIWorker

        worker = AIWorker(router=MagicMock(), registry=MagicMock())
        errors = await worker.validate(
            "ai.summarize",
            {"text": 42},
            {},
        )
        assert any("string" in e for e in errors)

    @pytest.mark.asyncio
    async def test_summarize_validate_bad_max_length(self):
        from unittest.mock import MagicMock

        from mascarade.node_engine.workers.ai.worker import AIWorker

        worker = AIWorker(router=MagicMock(), registry=MagicMock())
        errors = await worker.validate(
            "ai.summarize",
            {"text": "Some text", "max_length": 0},
            {},
        )
        assert any("max_length" in e for e in errors)

    @pytest.mark.asyncio
    async def test_summarize_execute(self):
        """execute() should return a summary string."""
        from unittest.mock import AsyncMock, MagicMock

        from mascarade.node_engine.workers.ai.worker import AIWorker

        mock_response = MagicMock()
        mock_response.content = "This is a concise summary of the document."

        mock_router = MagicMock()
        mock_router.send = AsyncMock(return_value=mock_response)

        worker = AIWorker(router=mock_router, registry=MagicMock())
        result = await worker.execute(
            "ai.summarize",
            {"text": "A very long document with many details...", "max_length": 50},
            {},
            None,
        )

        assert "summary" in result
        assert isinstance(result["summary"], str)
        assert len(result["summary"]) > 0

    @pytest.mark.asyncio
    async def test_summarize_execute_default_max_length(self):
        """execute() should use default max_length of 200 when not specified."""
        from unittest.mock import AsyncMock, MagicMock

        from mascarade.node_engine.workers.ai.worker import AIWorker

        mock_response = MagicMock()
        mock_response.content = "Summary."

        mock_router = MagicMock()
        mock_router.send = AsyncMock(return_value=mock_response)

        worker = AIWorker(router=mock_router, registry=MagicMock())
        await worker.execute(
            "ai.summarize",
            {"text": "Some text"},
            {},
            None,
        )

        # Verify the prompt mentions 200 words
        call_args = mock_router.send.call_args
        prompt = call_args.args[0][0]["content"]
        assert "200" in prompt

    def test_summarize_in_capabilities(self):
        from unittest.mock import MagicMock

        from mascarade.node_engine.workers.ai.worker import AIWorker

        worker = AIWorker(router=MagicMock(), registry=MagicMock())
        caps = worker.capabilities()
        assert "ai.summarize" in caps["node_types"]


# ---------------------------------------------------------------------------
# 19. Phase 5 — FederatedExecutor planner
# ---------------------------------------------------------------------------


class TestFederatedExecutor:
    """Test the FederatedExecutor planner for multi-machine graph execution."""

    def test_import_federation_module(self):
        from mascarade.node_engine.cross_domain.federation import (
            ExecutionPlan,
            FederatedExecutor,
            MachineProfile,
        )

        assert FederatedExecutor is not None
        assert ExecutionPlan is not None
        assert MachineProfile is not None

    def test_machine_profile_from_dict(self):
        from mascarade.node_engine.cross_domain.federation import MachineProfile

        data = {
            "id": "tower",
            "name": "Tower",
            "capabilities": ["gpu-inference", "docker-runtime"],
            "gpu_vram_gb": 5.0,
            "ram_gb": 32.0,
        }
        profile = MachineProfile.from_dict(data)
        assert profile.id == "tower"
        assert profile.name == "Tower"
        assert profile.has_capability("gpu-inference")
        assert not profile.has_capability("kicad-host")

    def test_plan_single_domain_graph(self):
        """All AI nodes should be assigned to the GPU machine."""
        from mascarade.node_engine.cross_domain.federation import (
            FederatedExecutor,
            MachineProfile,
        )
        from mascarade.node_engine.graph import Edge, Graph, Node

        nodes = [
            Node(id="n1", type="ai.llm-inference"),
            Node(id="n2", type="ai.classify"),
            Node(id="n3", type="ai.summarize"),
        ]
        edges = [
            Edge(from_node="n1", from_port="out", to_node="n2", to_port="in"),
            Edge(from_node="n2", from_port="out", to_node="n3", to_port="in"),
        ]
        graph = Graph(id="ai-only", nodes=nodes, edges=edges)

        profiles = [
            MachineProfile(
                id="gpu-box", name="GPU Box",
                capabilities=["gpu-inference"],
                gpu_vram_gb=24.0, priority=10,
            ),
            MachineProfile(
                id="cpu-box", name="CPU Box",
                capabilities=["cpu-compute"],
                priority=1,
            ),
        ]

        executor = FederatedExecutor()
        plan = executor.plan(graph, profiles)

        assert plan.is_complete
        assert len(plan.assignments) == 3
        # All AI nodes should go to GPU box
        for a in plan.assignments:
            assert a.machine_id == "gpu-box"
        assert plan.resource_estimate.cross_machine_edges == 0

    def test_plan_multi_domain_graph(self):
        """Nodes should be distributed across machines by domain."""
        from mascarade.node_engine.cross_domain.federation import (
            FederatedExecutor,
            MachineProfile,
        )
        from mascarade.node_engine.graph import Edge, Graph, Node

        nodes = [
            Node(id="ai-node", type="ai.llm-inference"),
            Node(id="cad-node", type="cad.bom-generate"),
            Node(id="hw-node", type="hardware.esp32.ota"),
        ]
        edges = [
            Edge(from_node="ai-node", from_port="out", to_node="cad-node", to_port="in"),
            Edge(from_node="cad-node", from_port="out", to_node="hw-node", to_port="in"),
        ]
        graph = Graph(id="multi-domain", nodes=nodes, edges=edges)

        profiles = [
            MachineProfile(
                id="tower", name="Tower",
                capabilities=["gpu-inference", "docker-runtime"],
                gpu_vram_gb=5.0, priority=10,
            ),
            MachineProfile(
                id="mac", name="Mac",
                capabilities=["hardware-connected", "cpu-compute"],
                priority=5,
            ),
        ]

        executor = FederatedExecutor()
        plan = executor.plan(graph, profiles)

        assert plan.is_complete
        assignment_map = {a.node_id: a.machine_id for a in plan.assignments}
        assert assignment_map["ai-node"] == "tower"
        assert assignment_map["cad-node"] == "tower"  # docker-runtime
        assert assignment_map["hw-node"] == "mac"  # hardware-connected
        assert plan.resource_estimate.cross_machine_edges >= 1

    def test_plan_unassigned_nodes(self):
        """Nodes with no eligible machine should be listed as unassigned."""
        from mascarade.node_engine.cross_domain.federation import (
            FederatedExecutor,
            MachineProfile,
        )
        from mascarade.node_engine.graph import Graph, Node

        nodes = [
            Node(id="hw-node", type="hardware.esp32.ota"),
        ]
        graph = Graph(id="no-hw", nodes=nodes, edges=[])

        profiles = [
            MachineProfile(
                id="cloud", name="Cloud",
                capabilities=["llm-api"],
            ),
        ]

        executor = FederatedExecutor()
        plan = executor.plan(graph, profiles)

        assert not plan.is_complete
        assert "hw-node" in plan.unassigned_nodes
        assert len(plan.warnings) > 0

    def test_plan_empty_profiles(self):
        """With no machine profiles, all nodes should be unassigned."""
        from mascarade.node_engine.cross_domain.federation import FederatedExecutor
        from mascarade.node_engine.graph import Graph, Node

        nodes = [Node(id="n1", type="ai.llm-inference")]
        graph = Graph(id="empty-profiles", nodes=nodes, edges=[])

        executor = FederatedExecutor()
        plan = executor.plan(graph, [])

        assert not plan.is_complete
        assert "n1" in plan.unassigned_nodes

    def test_plan_dict_profiles(self):
        """plan() should accept dicts as machine profiles (from JSON)."""
        from mascarade.node_engine.cross_domain.federation import FederatedExecutor
        from mascarade.node_engine.graph import Graph, Node

        nodes = [Node(id="n1", type="ai.llm-inference")]
        graph = Graph(id="dict-profiles", nodes=nodes, edges=[])

        profiles = [
            {"id": "gpu", "name": "GPU Box", "capabilities": ["gpu-inference"]},
        ]

        executor = FederatedExecutor()
        plan = executor.plan(graph, profiles)

        assert plan.is_complete
        assert plan.assignments[0].machine_id == "gpu"

    def test_plan_prefers_higher_priority(self):
        """When multiple machines qualify, prefer higher priority."""
        from mascarade.node_engine.cross_domain.federation import (
            FederatedExecutor,
            MachineProfile,
        )
        from mascarade.node_engine.graph import Graph, Node

        nodes = [Node(id="n1", type="ai.llm-inference")]
        graph = Graph(id="priority-test", nodes=nodes, edges=[])

        profiles = [
            MachineProfile(
                id="low", name="Low Priority",
                capabilities=["gpu-inference"],
                gpu_vram_gb=24.0, priority=1,
            ),
            MachineProfile(
                id="high", name="High Priority",
                capabilities=["gpu-inference"],
                gpu_vram_gb=8.0, priority=10,
            ),
        ]

        executor = FederatedExecutor()
        plan = executor.plan(graph, profiles)

        assert plan.assignments[0].machine_id == "high"

    def test_plan_network_flag_on_cross_machine_edges(self):
        """Target nodes on different machines should have requires_network=True."""
        from mascarade.node_engine.cross_domain.federation import (
            FederatedExecutor,
            MachineProfile,
        )
        from mascarade.node_engine.graph import Edge, Graph, Node

        nodes = [
            Node(id="ai-node", type="ai.llm-inference"),
            Node(id="hw-node", type="hardware.esp32.ota"),
        ]
        edges = [
            Edge(from_node="ai-node", from_port="out", to_node="hw-node", to_port="in"),
        ]
        graph = Graph(id="net-test", nodes=nodes, edges=edges)

        profiles = [
            MachineProfile(id="gpu", name="GPU", capabilities=["gpu-inference"], priority=10),
            MachineProfile(id="hw", name="HW", capabilities=["hardware-connected"], priority=5),
        ]

        executor = FederatedExecutor()
        plan = executor.plan(graph, profiles)

        assignment_map = {a.node_id: a for a in plan.assignments}
        assert assignment_map["hw-node"].requires_network is True
        assert assignment_map["ai-node"].requires_network is False

    def test_execution_plan_to_dict(self):
        """to_dict() should return a JSON-serializable dictionary."""
        from mascarade.node_engine.cross_domain.federation import (
            ExecutionPlan,
            NodeAssignment,
            ResourceEstimate,
        )

        plan = ExecutionPlan(
            graph_id="test",
            assignments=[
                NodeAssignment(
                    node_id="n1", node_type="ai.llm", machine_id="m1",
                    machine_name="Machine 1", reason="test",
                ),
            ],
            resource_estimate=ResourceEstimate(total_nodes=1, machines_used=1),
        )

        d = plan.to_dict()
        assert d["graph_id"] == "test"
        assert len(d["assignments"]) == 1
        assert d["is_complete"] is True

        # Should be JSON-serializable
        json.dumps(d)

    def test_execution_plan_machine_summary(self):
        from mascarade.node_engine.cross_domain.federation import (
            ExecutionPlan,
            NodeAssignment,
        )

        plan = ExecutionPlan(
            graph_id="test",
            assignments=[
                NodeAssignment(node_id="n1", node_type="ai.llm", machine_id="m1",
                               machine_name="M1", reason="t"),
                NodeAssignment(node_id="n2", node_type="ai.classify", machine_id="m1",
                               machine_name="M1", reason="t"),
                NodeAssignment(node_id="n3", node_type="cad.bom", machine_id="m2",
                               machine_name="M2", reason="t"),
            ],
        )

        summary = plan.machine_summary
        assert len(summary["m1"]) == 2
        assert len(summary["m2"]) == 1

    def test_federation_exported_from_cross_domain(self):
        """Verify federation types are exported from cross_domain __init__."""
        from mascarade.node_engine.cross_domain import (
            ExecutionPlan,
            FederatedExecutor,
            MachineProfile,
        )

        assert FederatedExecutor is not None
        assert ExecutionPlan is not None
        assert MachineProfile is not None
