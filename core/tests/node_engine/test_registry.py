"""Tests for the Node Type Registry."""

import json
import tempfile
from pathlib import Path

import pytest

from mascarade.node_engine.base import NodeDefinition
from mascarade.node_engine.registry import NodeTypeRegistry
from mascarade.node_engine.types import (
    NodePort,
    PortDirection,
    PortKind,
    PortType,
    PrimitiveType,
    primitive_port,
)


def _make_sample_node_def(node_type: str = "hardware.test.node") -> NodeDefinition:
    """Create a sample node definition for testing."""
    return NodeDefinition(
        node_type=node_type,
        description="Test node",
        input_ports=[
            primitive_port("input1", PortDirection.INPUT, PrimitiveType.STRING)
        ],
        output_ports=[
            primitive_port("output1", PortDirection.OUTPUT, PrimitiveType.INTEGER)
        ],
        tags=["test"],
        version="1.0.0",
    )


def test_register_node():
    """Test registering a node type."""
    registry = NodeTypeRegistry(storage_path=None)
    node_def = _make_sample_node_def()

    registry.register(node_def)

    assert "hardware.test.node" in registry
    assert len(registry) == 1


def test_register_builtin_node():
    """Test registering a builtin node type."""
    registry = NodeTypeRegistry(storage_path=None)
    node_def = _make_sample_node_def()

    registry.register(node_def, builtin=True)

    assert registry.is_builtin("hardware.test.node")
    assert "hardware.test.node" in registry


def test_get_node():
    """Test retrieving a registered node type."""
    registry = NodeTypeRegistry(storage_path=None)
    node_def = _make_sample_node_def()
    registry.register(node_def)

    retrieved = registry.get("hardware.test.node")

    assert retrieved.node_type == "hardware.test.node"
    assert retrieved.description == "Test node"


def test_get_missing_node():
    """Test retrieving a non-existent node type."""
    registry = NodeTypeRegistry(storage_path=None)

    try:
        registry.get("nonexistent.node")
        assert False, "Should have raised KeyError"
    except KeyError as e:
        assert "nonexistent.node" in str(e)


def test_list_nodes():
    """Test listing all registered nodes."""
    registry = NodeTypeRegistry(storage_path=None)
    node1 = _make_sample_node_def("hardware.test.node1")
    node2 = _make_sample_node_def("hardware.test.node2")

    registry.register(node1)
    registry.register(node2)

    nodes = registry.list()

    assert len(nodes) == 2
    assert any(n.node_type == "hardware.test.node1" for n in nodes)
    assert any(n.node_type == "hardware.test.node2" for n in nodes)


def test_list_by_domain():
    """Test listing nodes by domain."""
    registry = NodeTypeRegistry(storage_path=None)
    node1 = _make_sample_node_def("hardware.test.node1")
    node2 = _make_sample_node_def("hardware.test.node2")
    node3 = _make_sample_node_def("llm.test.node")

    registry.register(node1)
    registry.register(node2)
    registry.register(node3)

    hardware_nodes = registry.list_by_domain("hardware")
    llm_nodes = registry.list_by_domain("llm")

    assert len(hardware_nodes) == 2
    assert len(llm_nodes) == 1
    assert all(n.node_type.startswith("hardware.") for n in hardware_nodes)
    assert all(n.node_type.startswith("llm.") for n in llm_nodes)


def test_remove_node():
    """Test removing a node type."""
    registry = NodeTypeRegistry(storage_path=None)
    node_def = _make_sample_node_def()
    registry.register(node_def)

    assert "hardware.test.node" in registry

    registry.remove("hardware.test.node")

    assert "hardware.test.node" not in registry
    assert len(registry) == 0


def test_remove_builtin_node():
    """Test removing a builtin node type."""
    registry = NodeTypeRegistry(storage_path=None)
    node_def = _make_sample_node_def()
    registry.register(node_def, builtin=True)

    registry.remove("hardware.test.node")

    assert "hardware.test.node" not in registry
    assert not registry.is_builtin("hardware.test.node")


def test_validate_empty_node_type():
    """Test validation rejects empty node type."""
    registry = NodeTypeRegistry(storage_path=None)
    node_def = NodeDefinition(node_type="")

    try:
        registry.register(node_def)
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "cannot be empty" in str(e)


def test_validate_invalid_node_type_format():
    """Test validation rejects invalid node type format."""
    registry = NodeTypeRegistry(storage_path=None)
    node_def = NodeDefinition(node_type="invalid")

    try:
        registry.register(node_def)
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "domain.category.name" in str(e)


def test_validate_duplicate_input_ports():
    """Test validation rejects duplicate input port names."""
    registry = NodeTypeRegistry(storage_path=None)
    node_def = NodeDefinition(
        node_type="hardware.test.node",
        input_ports=[
            primitive_port("duplicate", PortDirection.INPUT, PrimitiveType.STRING),
            primitive_port("duplicate", PortDirection.INPUT, PrimitiveType.INTEGER),
        ],
    )

    try:
        registry.register(node_def)
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "Duplicate input port names" in str(e)


def test_validate_duplicate_output_ports():
    """Test validation rejects duplicate output port names."""
    registry = NodeTypeRegistry(storage_path=None)
    node_def = NodeDefinition(
        node_type="hardware.test.node",
        output_ports=[
            primitive_port("duplicate", PortDirection.OUTPUT, PrimitiveType.STRING),
            primitive_port("duplicate", PortDirection.OUTPUT, PrimitiveType.INTEGER),
        ],
    )

    try:
        registry.register(node_def)
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "Duplicate output port names" in str(e)


def test_save_and_load():
    """Test saving and loading node types from file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        storage_path = Path(tmpdir) / "node_types.json"
        registry = NodeTypeRegistry(storage_path=storage_path)

        node_def = _make_sample_node_def()
        registry.register(node_def)
        registry.save()

        # Create new registry and load
        registry2 = NodeTypeRegistry(storage_path=storage_path)
        registry2.load()

        assert "hardware.test.node" in registry2
        loaded_node = registry2.get("hardware.test.node")
        assert loaded_node.description == "Test node"


def test_save_excludes_builtins():
    """Test that builtin types are not saved to file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        storage_path = Path(tmpdir) / "node_types.json"
        registry = NodeTypeRegistry(storage_path=storage_path)

        builtin_node = _make_sample_node_def("builtin.test.node")
        dynamic_node = _make_sample_node_def("dynamic.test.node")

        registry.register(builtin_node, builtin=True)
        registry.register(dynamic_node, builtin=False)
        registry.save()

        # Load file and check contents
        with open(storage_path) as f:
            data = json.load(f)

        node_types = [item["node_type"] for item in data]
        assert "dynamic.test.node" in node_types
        assert "builtin.test.node" not in node_types


def test_load_invalid_json():
    """Test loading from invalid JSON file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        storage_path = Path(tmpdir) / "node_types.json"
        storage_path.write_text("invalid json{")

        registry = NodeTypeRegistry(storage_path=storage_path)
        registry.load()

        # Should not raise, just log error and continue
        assert len(registry) == 0


def test_load_missing_file():
    """Test loading from non-existent file."""
    registry = NodeTypeRegistry(storage_path=Path("/nonexistent/path.json"))
    registry.load()

    # Should not raise, just skip loading
    assert len(registry) == 0


def test_load_skips_invalid_entries():
    """Test loading skips invalid node type entries."""
    with tempfile.TemporaryDirectory() as tmpdir:
        storage_path = Path(tmpdir) / "node_types.json"

        # Create file with one valid and one invalid entry
        data = [
            {
                "node_type": "hardware.test.valid",
                "description": "Valid node",
                "input_ports": [],
                "output_ports": [],
            },
            {
                # Missing required field 'node_type'
                "description": "Invalid node",
            },
        ]
        storage_path.write_text(json.dumps(data))

        registry = NodeTypeRegistry(storage_path=storage_path)
        registry.load()

        # Should load the valid entry and skip the invalid one
        assert len(registry) == 1
        assert "hardware.test.valid" in registry


def test_save_with_none_storage_path():
    """Test that save() does nothing when storage_path is None."""
    registry = NodeTypeRegistry(storage_path=None)
    node_def = _make_sample_node_def()
    registry.register(node_def)

    # Should not raise
    registry.save()
