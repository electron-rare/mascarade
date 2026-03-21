"""Tests pour le registre de types et workers."""

import pytest

from mascarade.node_engine.registry import NodeRegistry
from mascarade.node_engine.types import DomainType
from mascarade.node_engine.worker import NodeWorker, WorkerCapabilities


class TestWorker(NodeWorker):
    """Worker de test pour les tests."""

    def __init__(self, domain: str, version: str = "1.0.0"):
        self.domain = domain
        self.version = version
        self.registry = None

    def capabilities(self) -> WorkerCapabilities:
        return WorkerCapabilities(node_prefixes=[self.domain])

    async def initialize(self) -> None:
        pass

    async def shutdown(self) -> None:
        pass


def test_registry_register_and_get_type():
    """Enregistrer et récupérer un type de domaine."""
    reg = NodeRegistry(storage_path=None)
    dt = DomainType(
        domain="electronics",
        name="Netlist",
        schema={"type": "object"},
    )
    reg.register_type(dt)
    assert reg.get_type("electronics.Netlist") is dt
    assert len(reg.list_types()) == 1


def test_registry_list_types():
    """Lister tous les types de domaine."""
    reg = NodeRegistry(storage_path=None)
    reg.register_type(DomainType(domain="electronics", name="Netlist", schema={}))
    reg.register_type(DomainType(domain="3d", name="Mesh", schema={}))
    assert len(reg.list_types()) == 2


def test_registry_list_types_filtered():
    """Lister les types filtrés par domaine."""
    reg = NodeRegistry(storage_path=None)
    reg.register_type(DomainType(domain="electronics", name="Netlist", schema={}))
    reg.register_type(DomainType(domain="electronics", name="Schematic", schema={}))
    reg.register_type(DomainType(domain="3d", name="Mesh", schema={}))

    electronics_types = reg.list_types(domain="electronics")
    assert len(electronics_types) == 2

    d3_types = reg.list_types(domain="3d")
    assert len(d3_types) == 1


def test_registry_has_type():
    """Vérifier l'existence d'un type."""
    reg = NodeRegistry(storage_path=None)
    reg.register_type(DomainType(domain="electronics", name="Netlist", schema={}))
    assert reg.has_type("electronics.Netlist") is True
    assert reg.has_type("electronics.Missing") is False


def test_registry_remove_type():
    """Retirer un type du registre."""
    reg = NodeRegistry(storage_path=None)
    reg.register_type(DomainType(domain="test", name="Remove", schema={}))
    reg.remove_type("test.Remove")
    assert reg.has_type("test.Remove") is False


def test_registry_get_type_missing():
    """Lever KeyError si le type n'existe pas."""
    reg = NodeRegistry(storage_path=None)
    try:
        reg.get_type("missing.Type")
        assert False, "Should have raised KeyError"
    except KeyError as e:
        assert "missing.Type" in str(e)


def test_registry_is_builtin_type():
    """Suivre les types intégrés vs dynamiques."""
    reg = NodeRegistry(storage_path=None)
    reg.register_type(
        DomainType(domain="test", name="Builtin", schema={}),
        builtin=True,
    )
    reg.register_type(DomainType(domain="test", name="Dynamic", schema={}))

    assert reg.is_builtin_type("test.Builtin") is True
    assert reg.is_builtin_type("test.Dynamic") is False


def test_registry_save_and_load_types(tmp_path):
    """Les types dynamiques sont persistés et rechargés."""
    storage = tmp_path / "types.json"

    reg = NodeRegistry(storage_path=storage)
    reg.register_type(
        DomainType(domain="test", name="Builtin", schema={"type": "string"}),
        builtin=True,
    )
    reg.register_type(
        DomainType(
            domain="test",
            name="Dynamic",
            schema={"type": "object"},
            description="A dynamic type",
        )
    )
    reg.save()

    reg2 = NodeRegistry(storage_path=storage)
    reg2.load()
    assert reg2.has_type("test.Dynamic") is True
    assert reg2.has_type("test.Builtin") is False  # Built-in non persisté

    loaded_type = reg2.get_type("test.Dynamic")
    assert loaded_type.domain == "test"
    assert loaded_type.name == "Dynamic"
    assert loaded_type.description == "A dynamic type"


def test_registry_save_noop_when_disabled():
    """Pas d'erreur si storage_path=None."""
    reg = NodeRegistry(storage_path=None)
    reg.register_type(DomainType(domain="test", name="Example", schema={}))
    reg.save()  # Ne doit pas lever d'erreur


def test_registry_load_noop_when_no_file(tmp_path):
    """Pas d'erreur si le fichier n'existe pas."""
    storage = tmp_path / "nonexistent.json"
    reg = NodeRegistry(storage_path=storage)
    reg.load()  # Ne doit pas lever d'erreur
    assert len(reg.list_types()) == 0


def test_registry_register_and_get_worker():
    """Enregistrer et récupérer un worker."""
    reg = NodeRegistry(storage_path=None)
    worker = TestWorker(domain="electronics")
    reg.register_worker(worker)

    assert reg.get_worker("electronics") is worker
    assert worker.registry is reg


def test_registry_list_workers():
    """Lister tous les workers enregistrés."""
    reg = NodeRegistry(storage_path=None)
    reg.register_worker(TestWorker(domain="electronics"))
    reg.register_worker(TestWorker(domain="3d"))
    assert len(reg.list_workers()) == 2


def test_registry_has_worker():
    """Vérifier l'existence d'un worker."""
    reg = NodeRegistry(storage_path=None)
    reg.register_worker(TestWorker(domain="electronics"))
    assert reg.has_worker("electronics") is True
    assert reg.has_worker("missing") is False


def test_registry_remove_worker():
    """Retirer un worker du registre."""
    reg = NodeRegistry(storage_path=None)
    worker = TestWorker(domain="test")
    reg.register_worker(worker)

    reg.remove_worker("test")
    assert reg.has_worker("test") is False
    assert worker.registry is None


def test_registry_get_worker_missing():
    """Lever KeyError si le worker n'existe pas."""
    reg = NodeRegistry(storage_path=None)
    try:
        reg.get_worker("missing")
        assert False, "Should have raised KeyError"
    except KeyError as e:
        assert "missing" in str(e)


def test_registry_len():
    """__len__ retourne le total types + workers."""
    reg = NodeRegistry(storage_path=None)
    reg.register_type(DomainType(domain="test", name="Type1", schema={}))
    reg.register_type(DomainType(domain="test", name="Type2", schema={}))
    reg.register_worker(TestWorker(domain="electronics"))

    assert len(reg) == 3


def test_registry_repr():
    """__repr__ affiche un résumé du registre."""
    reg = NodeRegistry(storage_path=None)
    reg.register_type(DomainType(domain="test", name="Type1", schema={}))
    reg.register_worker(TestWorker(domain="electronics"))

    repr_str = repr(reg)
    assert "NodeRegistry" in repr_str
    assert "types=1" in repr_str
    assert "workers=1" in repr_str
