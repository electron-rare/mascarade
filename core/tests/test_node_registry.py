"""Tests pour NodeTypeRegistry et WorkerRegistry."""

import concurrent.futures
import json

import pytest

from mascarade.node_engine.registry import (
    NodeRegistry,
    NodeType,
    NodeTypeRegistry,
    WorkerRegistry,
)
from mascarade.node_engine.types import DomainType
from mascarade.node_engine.worker import NodeCapability, NodeWorker

# --- Mock Worker for testing ---


class MockNodeWorker(NodeWorker):
    """Mock worker for testing purposes."""

    def __init__(self, name: str, domain: str, available: bool = True):
        self.name = name
        self.domain = domain
        self._available = available

    async def execute(
        self, node_type: str, inputs: dict, config: dict, context
    ) -> dict:
        """Mock execute - returns empty dict."""
        return {}

    async def validate(self, node_type: str, inputs: dict, config: dict) -> list[str]:
        """Mock validate - returns empty list."""
        return []

    def capabilities(self) -> NodeCapability:
        """Mock capabilities."""
        return NodeCapability(
            node_types=[f"{self.domain}.test"],
            domain=self.domain,
        )

    @property
    def is_available(self) -> bool:
        return self._available


# --- Fixtures ---


@pytest.fixture()
def registry():
    """Create a fresh NodeTypeRegistry with no persistence."""
    return NodeTypeRegistry(storage_path=None)


def _make_node_type(id: str, domain: str = "", category: str = "", label: str = "") -> NodeType:
    return NodeType(id=id, domain=domain, category=category, label=label or id, description=id)


def _make_domain_type(domain: str, name: str) -> DomainType:
    return DomainType(domain=domain, name=name, schema={})


# --- NodeTypeRegistry: register() ---


class TestRegisterNodeType:
    def test_register_node_type(self, registry):
        nt = _make_node_type("ai.test", domain="ai")
        registry.register(nt)
        assert registry.get("ai.test") is nt
        assert len(registry) == 1

    def test_register_domain_type(self, registry):
        dt = _make_domain_type("ai", "LLMResponse")
        registry.register(dt)
        assert registry.get("ai.LLMResponse") is dt
        assert len(registry) == 1

    def test_register_invalid_type_raises(self, registry):
        with pytest.raises(TypeError, match="expected NodeType or DomainType"):
            registry.register("not a type")  # type: ignore[arg-type]

    def test_register_builtin_flag(self, registry):
        nt = _make_node_type("ai.builtin", domain="ai")
        registry.register(nt, builtin=True)
        assert registry.is_builtin("ai.builtin")

    def test_register_type_alias(self, registry):
        """register_type is an alias for register."""
        nt = _make_node_type("ai.alias", domain="ai")
        registry.register_type(nt)
        assert "ai.alias" in registry


# --- NodeTypeRegistry: unregister() ---


class TestUnregister:
    def test_unregister_node_type(self, registry):
        nt = _make_node_type("ai.rm", domain="ai")
        registry.register(nt)
        registry.unregister("ai.rm")
        assert "ai.rm" not in registry

    def test_unregister_domain_type(self, registry):
        dt = _make_domain_type("cad", "Part")
        registry.register(dt)
        registry.unregister("cad.Part")
        assert "cad.Part" not in registry

    def test_unregister_clears_builtin(self, registry):
        nt = _make_node_type("ai.bi", domain="ai")
        registry.register(nt, builtin=True)
        assert registry.is_builtin("ai.bi")
        registry.unregister("ai.bi")
        assert not registry.is_builtin("ai.bi")

    def test_unregister_unknown_key_silent(self, registry):
        registry.unregister("nonexistent")  # should not raise

    def test_remove_alias(self, registry):
        """remove is an alias for unregister."""
        nt = _make_node_type("ai.x", domain="ai")
        registry.register(nt)
        registry.remove("ai.x")
        assert "ai.x" not in registry


# --- NodeTypeRegistry: get() ---


class TestGet:
    def test_get_node_type_by_id(self, registry):
        nt = _make_node_type("ai.llm", domain="ai")
        registry.register(nt)
        assert registry.get("ai.llm") is nt

    def test_get_domain_type_by_qualified_name(self, registry):
        dt = _make_domain_type("electronics", "PCB")
        registry.register(dt)
        assert registry.get("electronics.PCB") is dt

    def test_get_missing_raises_key_error(self, registry):
        with pytest.raises(KeyError, match="missing"):
            registry.get("missing")


# --- NodeTypeRegistry: list_all(), list_by_category(), get_by_domain() ---


class TestListMethods:
    def test_list_all(self, registry):
        registry.register(_make_node_type("ai.a", domain="ai"))
        registry.register(_make_domain_type("ai", "Resp"))
        items = registry.list_all()
        assert len(items) == 2

    def test_list_by_category(self, registry):
        registry.register(_make_node_type("ai.inf", domain="ai", category="inference"))
        registry.register(_make_node_type("ai.emb", domain="ai", category="embedding"))
        registry.register(_make_node_type("db.q", domain="db", category="query"))
        result = registry.list_by_category("inference")
        assert len(result) == 1
        assert result[0].id == "ai.inf"

    def test_list_by_category_empty(self, registry):
        assert registry.list_by_category("nonexistent") == []

    def test_get_by_domain(self, registry):
        registry.register(_make_node_type("ai.a", domain="ai"))
        registry.register(_make_node_type("db.b", domain="db"))
        registry.register(_make_domain_type("ai", "X"))
        result = registry.get_by_domain("ai")
        assert len(result) == 2

    def test_list_with_domain_filter(self, registry):
        registry.register(_make_node_type("ai.a", domain="ai"))
        registry.register(_make_node_type("db.b", domain="db"))
        ai_types = registry.list(domain="ai")
        assert len(ai_types) == 1
        assert ai_types[0].id == "ai.a"

    def test_domains(self, registry):
        registry.register(_make_node_type("ai.a", domain="ai"))
        registry.register(_make_node_type("db.b", domain="db"))
        registry.register(_make_node_type("ai.c", domain="ai"))
        assert registry.domains() == ["ai", "db"]


# --- NodeTypeRegistry: is_builtin() ---


class TestIsBuiltin:
    def test_builtin_true(self, registry):
        registry.register(_make_node_type("ai.builtin", domain="ai"), builtin=True)
        assert registry.is_builtin("ai.builtin") is True

    def test_builtin_false_for_dynamic(self, registry):
        registry.register(_make_node_type("ai.dynamic", domain="ai"))
        assert registry.is_builtin("ai.dynamic") is False

    def test_builtin_false_for_unknown(self, registry):
        assert registry.is_builtin("unknown") is False


# --- NodeTypeRegistry: save() and load() ---


class TestPersistence:
    def test_save_and_load_node_types(self, tmp_path):
        storage = tmp_path / "types.json"
        reg = NodeTypeRegistry(storage_path=storage)
        reg.register(_make_node_type("ai.builtin", domain="ai"), builtin=True)
        reg.register(_make_node_type("ai.dynamic", domain="ai"))
        reg.save()

        reg2 = NodeTypeRegistry(storage_path=storage)
        reg2.load()
        assert "ai.dynamic" in reg2
        assert "ai.builtin" not in reg2  # builtins not persisted

    def test_save_and_load_domain_types(self, tmp_path):
        storage = tmp_path / "types.json"
        reg = NodeTypeRegistry(storage_path=storage)
        reg.register(_make_domain_type("cad", "Assembly"))
        reg.save()

        reg2 = NodeTypeRegistry(storage_path=storage)
        reg2.load()
        assert "cad.Assembly" in reg2

    def test_save_and_load_mixed(self, tmp_path):
        storage = tmp_path / "types.json"
        reg = NodeTypeRegistry(storage_path=storage)
        reg.register(_make_node_type("ai.n1", domain="ai"))
        reg.register(_make_domain_type("ai", "DT1"))
        reg.save()

        reg2 = NodeTypeRegistry(storage_path=storage)
        reg2.load()
        assert len(reg2) == 2
        assert "ai.n1" in reg2
        assert "ai.DT1" in reg2

    def test_save_noop_when_disabled(self):
        reg = NodeTypeRegistry(storage_path=None)
        reg.register(_make_node_type("ai.x", domain="ai"))
        reg.save()  # should not raise

    def test_load_noop_when_no_file(self, tmp_path):
        storage = tmp_path / "nonexistent.json"
        reg = NodeTypeRegistry(storage_path=storage)
        reg.load()  # should not raise
        assert len(reg) == 0

    def test_load_handles_corrupt_json(self, tmp_path):
        storage = tmp_path / "bad.json"
        storage.write_text("not valid json!!!")
        reg = NodeTypeRegistry(storage_path=storage)
        reg.load()  # should not raise, just log warning
        assert len(reg) == 0

    def test_load_legacy_flat_list_format(self, tmp_path):
        """Old format was a flat list of node type dicts."""
        storage = tmp_path / "legacy.json"
        data = [{"id": "ai.old", "domain": "ai", "label": "Old", "description": "legacy"}]
        storage.write_text(json.dumps(data))
        reg = NodeTypeRegistry(storage_path=storage)
        reg.load()
        assert "ai.old" in reg


# --- Thread safety ---


class TestThreadSafety:
    def test_concurrent_register(self):
        reg = NodeTypeRegistry(storage_path=None)

        def register_one(i: int):
            reg.register(_make_node_type(f"ai.t{i}", domain="ai"))

        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            futures = [pool.submit(register_one, i) for i in range(100)]
            for f in futures:
                f.result()

        assert len(reg) == 100


# --- Backward compat alias ---


class TestBackwardCompat:
    def test_node_registry_alias(self):
        assert NodeRegistry is NodeTypeRegistry

    def test_node_registry_alias_works(self):
        reg = NodeRegistry(storage_path=None)
        reg.register(_make_node_type("ai.alias_test", domain="ai"))
        assert "ai.alias_test" in reg


# --- Dunder methods ---


class TestDunderMethods:
    def test_contains(self, registry):
        registry.register(_make_node_type("ai.x", domain="ai"))
        assert "ai.x" in registry
        assert "ai.y" not in registry

    def test_len(self, registry):
        assert len(registry) == 0
        registry.register(_make_node_type("ai.a", domain="ai"))
        registry.register(_make_domain_type("ai", "B"))
        assert len(registry) == 2

    def test_bool_always_truthy(self, registry):
        assert bool(registry) is True  # even when empty


# --- WorkerRegistry Tests ---


def test_worker_registry_register_and_get():
    reg = WorkerRegistry()
    worker = MockNodeWorker(name="test-worker", domain="ai")
    reg.register(worker)
    assert reg.get("ai") is worker
    assert len(reg) == 1


def test_worker_registry_list():
    reg = WorkerRegistry()
    reg.register(MockNodeWorker(name="worker-a", domain="ai"))
    reg.register(MockNodeWorker(name="worker-b", domain="db"))
    assert len(reg.list()) == 2


def test_worker_registry_contains():
    reg = WorkerRegistry()
    reg.register(MockNodeWorker(name="worker-x", domain="ai"))
    assert "ai" in reg
    assert "db" not in reg


def test_worker_registry_remove():
    reg = WorkerRegistry()
    reg.register(MockNodeWorker(name="worker-rm", domain="ai"))
    reg.remove("ai")
    assert "ai" not in reg


def test_worker_registry_get_missing():
    reg = WorkerRegistry()
    with pytest.raises(KeyError, match="missing"):
        reg.get("missing")


def test_worker_registry_available_domains():
    reg = WorkerRegistry()
    reg.register(MockNodeWorker(name="available", domain="ai", available=True))
    reg.register(MockNodeWorker(name="unavailable", domain="db", available=False))
    available = reg.available_domains()
    assert "ai" in available
    assert "db" not in available


def test_worker_registry_one_worker_per_domain():
    """Later worker registration overwrites previous for same domain."""
    reg = WorkerRegistry()
    worker1 = MockNodeWorker(name="worker-1", domain="ai")
    worker2 = MockNodeWorker(name="worker-2", domain="ai")
    reg.register(worker1)
    reg.register(worker2)
    assert len(reg) == 1
    assert reg.get("ai") is worker2  # Latest wins
