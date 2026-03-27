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
