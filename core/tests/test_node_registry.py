"""Tests pour NodeTypeRegistry et WorkerRegistry."""

from mascarade.node_engine.registry import NodeType, NodeTypeRegistry, WorkerRegistry
from mascarade.node_engine.worker import NodeCapability, NodeWorker


# --- Mock Worker for testing ---

class MockNodeWorker(NodeWorker):
    """Mock worker for testing purposes."""

    def __init__(self, name: str, domain: str, available: bool = True):
        self.name = name
        self.domain = domain
        self._available = available

    async def execute(self, node_type: str, inputs: dict, config: dict, context) -> dict:
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


# --- NodeTypeRegistry Tests ---

def test_node_type_registry_register_and_get():
    reg = NodeTypeRegistry(storage_path=None)
    node_type = NodeType(
        id="ai.test",
        domain="ai",
        label="Test Node",
        description="A test node type",
    )
    reg.register(node_type)
    assert reg.get("ai.test") is node_type
    assert len(reg) == 1


def test_node_type_registry_list():
    reg = NodeTypeRegistry(storage_path=None)
    reg.register(NodeType(id="ai.a", domain="ai", label="A", description="A"))
    reg.register(NodeType(id="ai.b", domain="ai", label="B", description="B"))
    assert len(reg.list()) == 2


def test_node_type_registry_list_by_domain():
    reg = NodeTypeRegistry(storage_path=None)
    reg.register(NodeType(id="ai.a", domain="ai", label="A", description="A"))
    reg.register(NodeType(id="db.b", domain="db", label="B", description="B"))
    ai_types = reg.list(domain="ai")
    assert len(ai_types) == 1
    assert ai_types[0].id == "ai.a"


def test_node_type_registry_contains():
    reg = NodeTypeRegistry(storage_path=None)
    reg.register(NodeType(id="ai.x", domain="ai", label="X", description="X"))
    assert "ai.x" in reg
    assert "ai.y" not in reg


def test_node_type_registry_remove():
    reg = NodeTypeRegistry(storage_path=None)
    reg.register(NodeType(id="ai.rm", domain="ai", label="RM", description="Remove me"))
    reg.remove("ai.rm")
    assert "ai.rm" not in reg


def test_node_type_registry_get_missing():
    reg = NodeTypeRegistry(storage_path=None)
    try:
        reg.get("missing")
        assert False, "Should have raised KeyError"
    except KeyError as e:
        assert "missing" in str(e)


def test_node_type_registry_domains():
    reg = NodeTypeRegistry(storage_path=None)
    reg.register(NodeType(id="ai.a", domain="ai", label="A", description="A"))
    reg.register(NodeType(id="db.b", domain="db", label="B", description="B"))
    reg.register(NodeType(id="ai.c", domain="ai", label="C", description="C"))
    domains = reg.domains()
    assert domains == ["ai", "db"]  # Sorted and unique


def test_node_type_registry_is_builtin():
    reg = NodeTypeRegistry(storage_path=None)
    reg.register(
        NodeType(id="ai.builtin", domain="ai", label="B", description="B"),
        builtin=True,
    )
    reg.register(NodeType(id="ai.dynamic", domain="ai", label="D", description="D"))
    assert reg.is_builtin("ai.builtin") is True
    assert reg.is_builtin("ai.dynamic") is False


def test_node_type_registry_save_and_load(tmp_path):
    """Dynamic node types are persisted and reloaded."""
    storage = tmp_path / "node_types.json"

    reg = NodeTypeRegistry(storage_path=storage)
    reg.register(
        NodeType(id="ai.builtin", domain="ai", label="B", description="B"),
        builtin=True,
    )
    reg.register(NodeType(id="ai.dynamic", domain="ai", label="D", description="D"))
    reg.save()

    reg2 = NodeTypeRegistry(storage_path=storage)
    reg2.load()
    assert "ai.dynamic" in reg2
    assert "ai.builtin" not in reg2  # Builtin not persisted


def test_node_type_registry_save_noop_when_disabled():
    """No error if storage_path=None."""
    reg = NodeTypeRegistry(storage_path=None)
    reg.register(NodeType(id="ai.x", domain="ai", label="X", description="X"))
    reg.save()  # Should not raise error


def test_node_type_registry_load_noop_when_no_file(tmp_path):
    """No error if file doesn't exist."""
    storage = tmp_path / "nonexistent.json"
    reg = NodeTypeRegistry(storage_path=storage)
    reg.load()  # Should not raise error
    assert len(reg) == 0


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
    try:
        reg.get("missing")
        assert False, "Should have raised KeyError"
    except KeyError as e:
        assert "missing" in str(e)


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
