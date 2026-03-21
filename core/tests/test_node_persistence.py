"""Tests for graph persistence and serialization."""

import json
from pathlib import Path

import pytest

from mascarade.node_engine.graph import Graph, GraphEdge, GraphNode, GraphStatus
from mascarade.node_engine.persistence import (
    CURRENT_SCHEMA_VERSION,
    SCHEMA_NAME,
    GraphSerializer,
    MigrationRegistry,
)


class TestGraphSerializer:
    """Test suite for graph serialization."""

    def test_serialize_minimal_graph(self):
        """Serialize a minimal graph to dict."""
        graph = Graph(id="g1", name="Minimal")
        serializer = GraphSerializer()
        data = serializer.serialize(graph)

        assert data["version"] == CURRENT_SCHEMA_VERSION
        assert data["schema"] == SCHEMA_NAME
        assert data["graph"]["id"] == "g1"
        assert data["graph"]["name"] == "Minimal"
        assert data["graph"]["status"] == "draft"

    def test_serialize_graph_with_nodes(self):
        """Serialize graph with nodes."""
        nodes = [
            GraphNode(id="n1", node_type="test", label="Node 1"),
            GraphNode(id="n2", node_type="test", label="Node 2", config={"key": "value"}),
        ]
        graph = Graph(id="g2", name="With Nodes", nodes=nodes)
        serializer = GraphSerializer()
        data = serializer.serialize(graph)

        assert len(data["graph"]["nodes"]) == 2
        assert data["graph"]["nodes"][0]["id"] == "n1"
        assert data["graph"]["nodes"][1]["config"]["key"] == "value"

    def test_serialize_graph_with_edges(self):
        """Serialize graph with edges."""
        nodes = [
            GraphNode(id="n1", node_type="test", label="N1"),
            GraphNode(id="n2", node_type="test", label="N2"),
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
        graph = Graph(id="g3", name="With Edges", nodes=nodes, edges=edges)
        serializer = GraphSerializer()
        data = serializer.serialize(graph)

        assert len(data["graph"]["edges"]) == 1
        assert data["graph"]["edges"][0]["source_node"] == "n1"
        assert data["graph"]["edges"][0]["target_port"] == "in"

    def test_serialize_adds_timestamps(self):
        """Serialization should add created_at and updated_at."""
        graph = Graph(id="g4", name="Timestamps")
        serializer = GraphSerializer()
        data = serializer.serialize(graph)

        assert "created_at" in data["graph"]["metadata"]
        assert "updated_at" in data["graph"]["metadata"]
        assert data["graph"]["metadata"]["created_at"].endswith("Z")
        assert data["graph"]["metadata"]["updated_at"].endswith("Z")

    def test_serialize_preserves_existing_created_at(self):
        """Serialization should not overwrite existing created_at."""
        graph = Graph(
            id="g5",
            name="Preserve Timestamp",
            metadata={"created_at": "2026-01-01T00:00:00Z"},
        )
        serializer = GraphSerializer()
        data = serializer.serialize(graph)

        assert data["graph"]["metadata"]["created_at"] == "2026-01-01T00:00:00Z"
        assert "updated_at" in data["graph"]["metadata"]

    def test_deserialize_minimal_graph(self):
        """Deserialize a minimal graph from dict."""
        data = {
            "version": CURRENT_SCHEMA_VERSION,
            "schema": SCHEMA_NAME,
            "graph": {
                "id": "g1",
                "name": "Minimal",
                "version": 1,
                "status": "draft",
                "nodes": [],
                "edges": [],
                "metadata": {},
            },
        }
        serializer = GraphSerializer()
        graph = serializer.deserialize(data)

        assert graph.id == "g1"
        assert graph.name == "Minimal"
        assert graph.status == GraphStatus.DRAFT
        assert len(graph.nodes) == 0
        assert len(graph.edges) == 0

    def test_deserialize_graph_with_nodes(self):
        """Deserialize graph with nodes."""
        data = {
            "version": CURRENT_SCHEMA_VERSION,
            "schema": SCHEMA_NAME,
            "graph": {
                "id": "g2",
                "name": "With Nodes",
                "version": 1,
                "status": "validated",
                "nodes": [
                    {"id": "n1", "node_type": "test", "label": "N1", "config": {}, "position": (0.0, 0.0), "domain": None},
                    {"id": "n2", "node_type": "test", "label": "N2", "config": {"x": 10}, "position": (1.0, 2.0), "domain": "ai"},
                ],
                "edges": [],
                "metadata": {},
            },
        }
        serializer = GraphSerializer()
        graph = serializer.deserialize(data)

        assert len(graph.nodes) == 2
        assert graph.nodes[0].id == "n1"
        assert graph.nodes[1].config["x"] == 10
        assert graph.nodes[1].domain == "ai"

    def test_deserialize_graph_with_edges(self):
        """Deserialize graph with edges."""
        data = {
            "version": CURRENT_SCHEMA_VERSION,
            "schema": SCHEMA_NAME,
            "graph": {
                "id": "g3",
                "name": "With Edges",
                "version": 1,
                "status": "compiled",
                "nodes": [
                    {"id": "n1", "node_type": "t", "label": "N1", "config": {}, "position": (0.0, 0.0), "domain": None},
                    {"id": "n2", "node_type": "t", "label": "N2", "config": {}, "position": (0.0, 0.0), "domain": None},
                ],
                "edges": [
                    {
                        "id": "e1",
                        "source_node": "n1",
                        "source_port": "output",
                        "target_node": "n2",
                        "target_port": "input",
                    },
                ],
                "metadata": {},
            },
        }
        serializer = GraphSerializer()
        graph = serializer.deserialize(data)

        assert len(graph.edges) == 1
        assert graph.edges[0].source_node == "n1"
        assert graph.edges[0].target_port == "input"

    def test_deserialize_missing_graph_key(self):
        """Deserialize should raise ValueError if 'graph' key missing."""
        data = {"version": CURRENT_SCHEMA_VERSION, "schema": SCHEMA_NAME}
        serializer = GraphSerializer()

        with pytest.raises(ValueError) as exc_info:
            serializer.deserialize(data)
        assert "graph" in str(exc_info.value).lower()

    def test_roundtrip_serialization(self):
        """Serialize then deserialize should preserve graph."""
        nodes = [
            GraphNode(id="n1", node_type="test", label="Node 1", position=(10.0, 20.0)),
            GraphNode(id="n2", node_type="test", label="Node 2", config={"param": "value"}),
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
            name="Roundtrip Test",
            version=3,
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
        assert len(restored.nodes) == len(original.nodes)
        assert len(restored.edges) == len(original.edges)
        assert restored.nodes[0].position == (10.0, 20.0)
        assert restored.nodes[1].config["param"] == "value"


class TestGraphSerializerFileOperations:
    """Test suite for file save/load operations."""

    def test_save_minimal_graph(self, tmp_path):
        """Save a minimal graph to JSON file."""
        graph = Graph(id="file1", name="File Test")
        path = tmp_path / "graph.json"

        serializer = GraphSerializer()
        serializer.save(graph, path)

        assert path.exists()
        data = json.loads(path.read_text())
        assert data["version"] == CURRENT_SCHEMA_VERSION
        assert data["graph"]["id"] == "file1"

    def test_save_creates_parent_directory(self, tmp_path):
        """Save should create parent directories if needed."""
        graph = Graph(id="nested", name="Nested")
        path = tmp_path / "deep" / "nested" / "graph.json"

        serializer = GraphSerializer()
        serializer.save(graph, path)

        assert path.exists()
        assert path.parent.exists()

    def test_load_graph_from_file(self, tmp_path):
        """Load a graph from JSON file."""
        data = {
            "version": CURRENT_SCHEMA_VERSION,
            "schema": SCHEMA_NAME,
            "graph": {
                "id": "loaded",
                "name": "Loaded Graph",
                "version": 1,
                "status": "draft",
                "nodes": [],
                "edges": [],
                "metadata": {},
            },
        }
        path = tmp_path / "graph.json"
        path.write_text(json.dumps(data))

        serializer = GraphSerializer()
        graph = serializer.load(path)

        assert graph.id == "loaded"
        assert graph.name == "Loaded Graph"

    def test_load_nonexistent_file(self, tmp_path):
        """Load should raise FileNotFoundError for missing file."""
        path = tmp_path / "missing.json"
        serializer = GraphSerializer()

        with pytest.raises(FileNotFoundError):
            serializer.load(path)

    def test_load_invalid_json(self, tmp_path):
        """Load should raise ValueError for invalid JSON."""
        path = tmp_path / "invalid.json"
        path.write_text("{invalid json")

        serializer = GraphSerializer()

        with pytest.raises(ValueError) as exc_info:
            serializer.load(path)
        assert "parse" in str(exc_info.value).lower()

    def test_save_load_roundtrip(self, tmp_path):
        """Save then load should preserve graph."""
        nodes = [
            GraphNode(id="n1", node_type="test", label="Node 1"),
            GraphNode(id="n2", node_type="test", label="Node 2"),
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
            id="roundtrip-file",
            name="Roundtrip File Test",
            nodes=nodes,
            edges=edges,
            metadata={"test": "data"},
        )

        path = tmp_path / "roundtrip.json"
        serializer = GraphSerializer()
        serializer.save(original, path)
        loaded = serializer.load(path)

        assert loaded.id == original.id
        assert loaded.name == original.name
        assert len(loaded.nodes) == 2
        assert len(loaded.edges) == 1
        assert loaded.metadata["test"] == "data"

    def test_save_overwrites_existing_file(self, tmp_path):
        """Save should overwrite existing file."""
        path = tmp_path / "overwrite.json"

        graph1 = Graph(id="v1", name="Version 1")
        serializer = GraphSerializer()
        serializer.save(graph1, path)

        graph2 = Graph(id="v2", name="Version 2")
        serializer.save(graph2, path)

        loaded = serializer.load(path)
        assert loaded.id == "v2"
        assert loaded.name == "Version 2"


class TestMigrationRegistry:
    """Test suite for migration registry."""

    def test_register_migration(self):
        """Register a migration function."""
        registry = MigrationRegistry()

        def migrate_1_to_2(data):
            data["new_field"] = "added"
            return data

        registry.register("1.0.0", "2.0.0", migrate_1_to_2)

        assert ("1.0.0", "2.0.0") in registry
        assert len(registry) == 1

    def test_get_migration(self):
        """Get a registered migration function."""
        registry = MigrationRegistry()

        def migrate_1_to_2(data):
            return data

        registry.register("1.0.0", "2.0.0", migrate_1_to_2)

        func = registry.get("1.0.0", "2.0.0")
        assert func is migrate_1_to_2

    def test_get_missing_migration(self):
        """Get should raise KeyError for missing migration."""
        registry = MigrationRegistry()

        with pytest.raises(KeyError) as exc_info:
            registry.get("1.0.0", "2.0.0")
        assert "1.0.0" in str(exc_info.value)
        assert "2.0.0" in str(exc_info.value)

    def test_migrate_same_version(self):
        """Migrate should be no-op for same version."""
        registry = MigrationRegistry()
        data = {"version": "1.0.0", "field": "value"}

        result = registry.migrate(data, "1.0.0")
        assert result == data

    def test_migrate_transforms_data(self):
        """Migrate should apply migration function."""
        registry = MigrationRegistry()

        def migrate_1_to_2(data):
            data["graph"]["new_field"] = "migrated"
            return data

        registry.register("1.0.0", "2.0.0", migrate_1_to_2)

        data = {"version": "1.0.0", "graph": {"id": "test"}}
        result = registry.migrate(data, "2.0.0")

        assert result["version"] == "2.0.0"
        assert result["graph"]["new_field"] == "migrated"

    def test_migrate_missing_version_key(self):
        """Migrate should raise ValueError if version key missing."""
        registry = MigrationRegistry()
        data = {"no_version": "oops"}

        with pytest.raises(ValueError) as exc_info:
            registry.migrate(data, "2.0.0")
        assert "version" in str(exc_info.value).lower()

    def test_list_migrations(self):
        """List all registered migrations."""
        registry = MigrationRegistry()

        registry.register("1.0.0", "2.0.0", lambda d: d)
        registry.register("2.0.0", "3.0.0", lambda d: d)

        migrations = registry.list_migrations()
        assert len(migrations) == 2
        assert ("1.0.0", "2.0.0") in migrations
        assert ("2.0.0", "3.0.0") in migrations

    def test_register_replaces_existing(self):
        """Registering same migration twice should replace."""
        registry = MigrationRegistry()

        def migrate_v1(data):
            data["v"] = 1
            return data

        def migrate_v2(data):
            data["v"] = 2
            return data

        registry.register("1.0.0", "2.0.0", migrate_v1)
        registry.register("1.0.0", "2.0.0", migrate_v2)

        func = registry.get("1.0.0", "2.0.0")
        assert func is migrate_v2

    def test_migration_chain_example(self):
        """Example of chaining migrations."""
        registry = MigrationRegistry()

        def migrate_1_to_2(data):
            # Add field in version 2
            data["graph"]["status"] = "draft"
            return data

        def migrate_2_to_3(data):
            # Add metadata in version 3
            data["graph"].setdefault("metadata", {})
            data["graph"]["metadata"]["migrated_to_v3"] = True
            return data

        registry.register("1.0.0", "2.0.0", migrate_1_to_2)
        registry.register("2.0.0", "3.0.0", migrate_2_to_3)

        # Migrate 1.0.0 -> 2.0.0
        data_v1 = {"version": "1.0.0", "graph": {"id": "test"}}
        data_v2 = registry.migrate(data_v1, "2.0.0")
        assert data_v2["graph"]["status"] == "draft"

        # Migrate 2.0.0 -> 3.0.0
        data_v3 = registry.migrate(data_v2, "3.0.0")
        assert data_v3["graph"]["metadata"]["migrated_to_v3"] is True
