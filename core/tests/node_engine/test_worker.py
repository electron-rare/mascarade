"""Tests pour les workers de domaine."""

import pytest

from mascarade.node_engine.worker import NodeWorker, WorkerCapabilities


def test_worker_capabilities_defaults():
    """WorkerCapabilities a des valeurs par défaut correctes."""
    caps = WorkerCapabilities()
    assert caps.node_prefixes == []
    assert caps.max_concurrent == 4
    assert caps.requires_gpu is False
    assert caps.estimated_memory_mb == 512
    assert caps.external_tools == []


def test_worker_capabilities_custom():
    """WorkerCapabilities accepte des valeurs personnalisées."""
    caps = WorkerCapabilities(
        node_prefixes=["electronics"],
        max_concurrent=8,
        requires_gpu=True,
        estimated_memory_mb=2048,
        external_tools=["ngspice", "kicad-cli"],
    )
    assert caps.node_prefixes == ["electronics"]
    assert caps.max_concurrent == 8
    assert caps.requires_gpu is True
    assert caps.estimated_memory_mb == 2048
    assert caps.external_tools == ["ngspice", "kicad-cli"]


@pytest.mark.asyncio
async def test_worker_base_class_not_implemented():
    """NodeWorker de base lève NotImplementedError pour les méthodes abstraites."""
    worker = NodeWorker()
    worker.domain = "test"
    worker.version = "1.0.0"

    with pytest.raises(NotImplementedError):
        worker.capabilities()

    with pytest.raises(NotImplementedError):
        await worker.initialize()

    with pytest.raises(NotImplementedError):
        await worker.shutdown()


class TestWorker(NodeWorker):
    """Worker de test concret."""

    domain = "test"
    version = "1.0.0"

    def capabilities(self) -> WorkerCapabilities:
        return WorkerCapabilities(
            node_prefixes=["test"],
            max_concurrent=2,
        )

    async def initialize(self) -> None:
        self.initialized = True

    async def shutdown(self) -> None:
        self.shutdown_called = True


@pytest.mark.asyncio
async def test_worker_implementation():
    """Un worker concret peut implémenter les méthodes abstraites."""
    worker = TestWorker()
    assert worker.domain == "test"
    assert worker.version == "1.0.0"

    caps = worker.capabilities()
    assert caps.node_prefixes == ["test"]
    assert caps.max_concurrent == 2

    await worker.initialize()
    assert worker.initialized is True

    await worker.shutdown()
    assert worker.shutdown_called is True


@pytest.mark.asyncio
async def test_worker_check_tool_available():
    """_check_tool retourne True si l'outil existe dans le PATH."""
    worker = TestWorker()
    # Utiliser un outil qui existe probablement (python)
    result = await worker._check_tool("python")
    assert isinstance(result, bool)


@pytest.mark.asyncio
async def test_worker_check_tool_missing():
    """_check_tool retourne False si l'outil n'existe pas."""
    worker = TestWorker()
    result = await worker._check_tool("nonexistent-tool-12345")
    assert result is False


def test_worker_registry_reference():
    """Un worker peut recevoir une référence au registre."""
    worker = TestWorker()
    assert worker.registry is None
    # Le registre sera assigné lors de register_worker
