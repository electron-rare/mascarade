"""Tests for NodeTypeRegistry."""

import json
import tempfile
from pathlib import Path

import pytest

from mascarade.node_engine.registry import NodeTypeRegistry
from mascarade.node_engine.types import DomainType


def _make_domain_type(domain: str, name: str) -> DomainType:
    """Helper to create a DomainType for testing."""
    return DomainType(
        domain=domain,
        name=name,
        schema={
            "type": "object",
            "properties": {"value": {"type": "string"}},
        },
    )


def test_registry_initialization():
    """Test registry initialization."""
    registry = NodeTypeRegistry()
    assert len(registry) == 0
    assert list(registry.list()) == []


def test_register_domain_type():
    """Test registering a domain type."""
    registry = NodeTypeRegistry()
    domain_type = _make_domain_type("ai", "LLMResponse")

    registry.register(domain_type)
    assert len(registry) == 1
    assert "ai.LLMResponse" in registry


def test_get_domain_type():
    """Test retrieving a domain type by qualified name."""
    registry = NodeTypeRegistry()
    domain_type = _make_domain_type("ai", "LLMResponse")
    registry.register(domain_type)

    retrieved = registry.get("ai.LLMResponse")
    assert retrieved.domain == "ai"
    assert retrieved.name == "LLMResponse"
    assert retrieved.qualified_name == "ai.LLMResponse"


def test_get_missing_domain_type():
    """Test getting a non-existent domain type raises KeyError."""
    registry = NodeTypeRegistry()
    with pytest.raises(KeyError) as exc_info:
        registry.get("ai.NonExistent")
    assert "ai.NonExistent" in str(exc_info.value)
    assert "not found" in str(exc_info.value)


def test_get_by_domain():
    """Test retrieving all types for a specific domain."""
    registry = NodeTypeRegistry()
    registry.register(_make_domain_type("ai", "LLMResponse"))
    registry.register(_make_domain_type("ai", "EmbeddingVector"))
    registry.register(_make_domain_type("cad", "Sketch"))

    ai_types = registry.get_by_domain("ai")
    assert len(ai_types) == 2
    assert all(dt.domain == "ai" for dt in ai_types)

    cad_types = registry.get_by_domain("cad")
    assert len(cad_types) == 1
    assert cad_types[0].name == "Sketch"

    empty = registry.get_by_domain("electronics")
    assert len(empty) == 0


def test_list_all_types():
    """Test listing all registered domain types."""
    registry = NodeTypeRegistry()
    registry.register(_make_domain_type("ai", "LLMResponse"))
    registry.register(_make_domain_type("cad", "Sketch"))

    all_types = registry.list()
    assert len(all_types) == 2
    qualified_names = {dt.qualified_name for dt in all_types}
    assert qualified_names == {"ai.LLMResponse", "cad.Sketch"}


def test_remove_domain_type():
    """Test removing a domain type."""
    registry = NodeTypeRegistry()
    domain_type = _make_domain_type("ai", "LLMResponse")
    registry.register(domain_type)
    assert "ai.LLMResponse" in registry

    registry.remove("ai.LLMResponse")
    assert "ai.LLMResponse" not in registry
    assert len(registry) == 0


def test_remove_nonexistent_type():
    """Test removing a non-existent type doesn't raise an error."""
    registry = NodeTypeRegistry()
    registry.remove("ai.NonExistent")  # Should not raise
    assert len(registry) == 0


def test_contains():
    """Test __contains__ for membership checking."""
    registry = NodeTypeRegistry()
    domain_type = _make_domain_type("ai", "LLMResponse")
    registry.register(domain_type)

    assert "ai.LLMResponse" in registry
    assert "ai.NonExistent" not in registry


def test_len():
    """Test __len__ for counting registered types."""
    registry = NodeTypeRegistry()
    assert len(registry) == 0

    registry.register(_make_domain_type("ai", "Type1"))
    assert len(registry) == 1

    registry.register(_make_domain_type("ai", "Type2"))
    assert len(registry) == 2

    registry.remove("ai.Type1")
    assert len(registry) == 1


def test_builtin_types():
    """Test builtin type tracking."""
    registry = NodeTypeRegistry()
    builtin_type = _make_domain_type("ai", "Builtin")
    custom_type = _make_domain_type("ai", "Custom")

    registry.register(builtin_type, builtin=True)
    registry.register(custom_type, builtin=False)

    assert registry.is_builtin("ai.Builtin") is True
    assert registry.is_builtin("ai.Custom") is False
    assert registry.is_builtin("ai.NonExistent") is False


def test_overwrite_existing_type():
    """Test overwriting an existing type logs warning but succeeds."""
    registry = NodeTypeRegistry()
    type1 = _make_domain_type("ai", "Test")
    type2 = DomainType(
        domain="ai",
        name="Test",
        schema={"type": "string"},  # Different schema
    )

    registry.register(type1)
    registry.register(type2)  # Should overwrite

    retrieved = registry.get("ai.Test")
    assert retrieved.schema["type"] == "string"


def test_save_and_load():
    """Test persisting and loading domain types."""
    with tempfile.TemporaryDirectory() as tmpdir:
        storage_path = Path(tmpdir) / "types.json"
        registry = NodeTypeRegistry(storage_path=storage_path)

        # Register types
        registry.register(_make_domain_type("ai", "Type1"))
        registry.register(_make_domain_type("cad", "Type2"))

        # Save
        registry.save()
        assert storage_path.exists()

        # Load into new registry
        registry2 = NodeTypeRegistry(storage_path=storage_path)
        registry2.load()

        assert len(registry2) == 2
        assert "ai.Type1" in registry2
        assert "cad.Type2" in registry2


def test_save_excludes_builtin_types():
    """Test that builtin types are not persisted."""
    with tempfile.TemporaryDirectory() as tmpdir:
        storage_path = Path(tmpdir) / "types.json"
        registry = NodeTypeRegistry(storage_path=storage_path)

        # Register builtin and custom types
        registry.register(_make_domain_type("ai", "Builtin"), builtin=True)
        registry.register(_make_domain_type("ai", "Custom"), builtin=False)

        # Save
        registry.save()

        # Check saved data
        saved_data = json.loads(storage_path.read_text())
        assert len(saved_data) == 1
        assert saved_data[0]["name"] == "Custom"


def test_load_invalid_json():
    """Test loading handles invalid JSON gracefully."""
    with tempfile.TemporaryDirectory() as tmpdir:
        storage_path = Path(tmpdir) / "types.json"
        storage_path.write_text("invalid json{{{")

        registry = NodeTypeRegistry(storage_path=storage_path)
        registry.load()  # Should not raise, just log error

        assert len(registry) == 0


def test_load_invalid_entries():
    """Test loading skips invalid entries."""
    with tempfile.TemporaryDirectory() as tmpdir:
        storage_path = Path(tmpdir) / "types.json"

        # Write data with one valid and one invalid entry
        data = [
            {
                "domain": "ai",
                "name": "Valid",
                "schema": {"type": "object"},
            },
            {
                "domain": "ai",
                "name": "Invalid",
                # Missing 'schema' field
            },
        ]
        storage_path.write_text(json.dumps(data))

        registry = NodeTypeRegistry(storage_path=storage_path)
        registry.load()

        # Both entries load — schema defaults to empty dict when missing
        assert len(registry) == 2
        assert "ai.Valid" in registry
        assert "ai.Invalid" in registry


def test_save_atomic_write():
    """Test that save uses atomic write (temp file + rename)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        storage_path = Path(tmpdir) / "types.json"
        registry = NodeTypeRegistry(storage_path=storage_path)

        registry.register(_make_domain_type("ai", "Test"))
        registry.save()

        # Verify no temp files left behind
        temp_files = list(Path(tmpdir).glob("*.tmp"))
        assert len(temp_files) == 0


def test_persistence_disabled_when_storage_path_none():
    """Test that persistence is disabled when storage_path is None."""
    registry = NodeTypeRegistry(storage_path=None)
    registry.register(_make_domain_type("ai", "Test"))

    # Save should do nothing
    registry.save()  # Should not raise

    # Load should do nothing
    registry.load()  # Should not raise
    assert len(registry) == 1  # Original registration still there


def test_remove_also_removes_from_builtin_set():
    """Test that remove() also removes from builtin tracking."""
    registry = NodeTypeRegistry()
    domain_type = _make_domain_type("ai", "Test")
    registry.register(domain_type, builtin=True)

    assert registry.is_builtin("ai.Test") is True

    registry.remove("ai.Test")

    assert "ai.Test" not in registry
    assert registry.is_builtin("ai.Test") is False
