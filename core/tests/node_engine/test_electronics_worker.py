"""Tests d'intégration end-to-end pour ElectronicsWorker."""

import pytest

from mascarade.node_engine.domains.electronics import ELECTRONICS_DOMAIN_TYPES
from mascarade.node_engine.registry import NodeRegistry
from mascarade.node_engine.workers.electronics.worker import ElectronicsWorker


def test_electronics_worker_domain_and_version():
    """Le worker électronique a un domaine et une version corrects."""
    worker = ElectronicsWorker()
    assert worker.domain == "electronics"
    assert worker.version == "1.0.0"


def test_electronics_worker_capabilities():
    """Les capacités du worker incluent tous les préfixes de nœuds requis."""
    worker = ElectronicsWorker()
    caps = worker.capabilities()

    assert "electronics.spice" in caps.node_prefixes
    assert "electronics.pcb" in caps.node_prefixes
    assert "electronics.firmware" in caps.node_prefixes
    assert "electronics.components" in caps.node_prefixes
    assert caps.max_concurrent == 4
    assert caps.requires_gpu is False
    assert caps.estimated_memory_mb == 512
    assert "ngspice" in caps.external_tools
    assert "kicad-cli" in caps.external_tools
    assert "idf.py" in caps.external_tools
    assert "pio" in caps.external_tools


@pytest.mark.asyncio
async def test_electronics_worker_initialize_without_registry():
    """Le worker peut s'initialiser sans registre (aucun type enregistré)."""
    worker = ElectronicsWorker()
    assert worker.registry is None

    # Ne devrait pas lever d'erreur
    await worker.initialize()

    # Les flags de disponibilité des outils sont définis
    assert isinstance(worker._ngspice_available, bool)
    assert isinstance(worker._kicad_available, bool)
    assert isinstance(worker._espidf_available, bool)
    assert isinstance(worker._platformio_available, bool)


@pytest.mark.asyncio
async def test_electronics_worker_initialize_with_registry():
    """Le worker enregistre les types de domaine lors de l'initialisation."""
    reg = NodeRegistry(storage_path=None)
    worker = ElectronicsWorker()
    reg.register_worker(worker)

    assert worker.registry is reg
    assert len(reg.list_types(domain="electronics")) == 0

    await worker.initialize()

    # Tous les types de domaine électronique doivent être enregistrés
    electronics_types = reg.list_types(domain="electronics")
    assert len(electronics_types) == len(ELECTRONICS_DOMAIN_TYPES)

    # Vérifier que tous les types attendus sont présents
    type_names = {dt.name for dt in electronics_types}
    assert "Netlist" in type_names
    assert "Schematic" in type_names
    assert "Waveform" in type_names
    assert "FirmwareBinary" in type_names
    assert "ComponentSpec" in type_names
    assert "DRCReport" in type_names


@pytest.mark.asyncio
async def test_electronics_worker_types_marked_as_builtin():
    """Les types enregistrés par le worker sont marqués comme intégrés."""
    reg = NodeRegistry(storage_path=None)
    worker = ElectronicsWorker()
    reg.register_worker(worker)

    await worker.initialize()

    # Tous les types de domaine électronique doivent être intégrés
    assert reg.is_builtin_type("electronics.Netlist") is True
    assert reg.is_builtin_type("electronics.Schematic") is True
    assert reg.is_builtin_type("electronics.Waveform") is True
    assert reg.is_builtin_type("electronics.FirmwareBinary") is True
    assert reg.is_builtin_type("electronics.ComponentSpec") is True
    assert reg.is_builtin_type("electronics.DRCReport") is True


@pytest.mark.asyncio
async def test_electronics_worker_shutdown():
    """Le worker peut être arrêté sans erreur."""
    worker = ElectronicsWorker()
    await worker.initialize()
    await worker.shutdown()  # Ne devrait pas lever d'erreur


@pytest.mark.asyncio
async def test_electronics_worker_full_lifecycle():
    """Cycle de vie complet: enregistrement, initialisation, arrêt."""
    reg = NodeRegistry(storage_path=None)
    worker = ElectronicsWorker()

    # Enregistrement
    reg.register_worker(worker)
    assert reg.has_worker("electronics") is True
    assert reg.get_worker("electronics") is worker

    # Initialisation
    await worker.initialize()
    electronics_types = reg.list_types(domain="electronics")
    assert len(electronics_types) == len(ELECTRONICS_DOMAIN_TYPES)

    # Arrêt
    await worker.shutdown()

    # Le worker reste enregistré après l'arrêt
    assert reg.has_worker("electronics") is True


@pytest.mark.asyncio
async def test_electronics_worker_tool_availability_checks():
    """Le worker vérifie la disponibilité des outils externes."""
    worker = ElectronicsWorker()
    await worker.initialize()

    # Les flags doivent être définis (True ou False selon l'environnement)
    assert isinstance(worker._ngspice_available, bool)
    assert isinstance(worker._kicad_available, bool)
    assert isinstance(worker._espidf_available, bool)
    assert isinstance(worker._platformio_available, bool)


@pytest.mark.asyncio
async def test_electronics_worker_graceful_degradation():
    """Le worker s'initialise même si les outils externes sont manquants."""
    worker = ElectronicsWorker()

    # L'initialisation ne doit pas échouer même si les outils sont absents
    try:
        await worker.initialize()
        # Si aucune exception n'est levée, le test réussit
        assert True
    except Exception as e:
        # Le worker ne devrait pas lever d'exception pendant l'initialisation
        pytest.fail(f"Worker initialization failed: {e}")


@pytest.mark.asyncio
async def test_registry_initialize_workers_includes_electronics():
    """initialize_workers initialise le worker électronique."""
    reg = NodeRegistry(storage_path=None)
    worker = ElectronicsWorker()
    reg.register_worker(worker)

    # Avant l'initialisation, aucun type n'est enregistré
    assert len(reg.list_types(domain="electronics")) == 0

    # Initialiser tous les workers via le registre
    await reg.initialize_workers()

    # Après l'initialisation, les types sont enregistrés
    assert len(reg.list_types(domain="electronics")) == len(ELECTRONICS_DOMAIN_TYPES)


@pytest.mark.asyncio
async def test_registry_shutdown_workers_includes_electronics():
    """shutdown_workers arrête le worker électronique."""
    reg = NodeRegistry(storage_path=None)
    worker = ElectronicsWorker()
    reg.register_worker(worker)

    await reg.initialize_workers()

    # L'arrêt ne devrait pas lever d'erreur
    try:
        await reg.shutdown_workers()
        assert True
    except Exception as e:
        pytest.fail(f"Worker shutdown failed: {e}")


@pytest.mark.asyncio
async def test_electronics_worker_multiple_initializations():
    """Le worker peut être initialisé plusieurs fois sans erreur."""
    reg = NodeRegistry(storage_path=None)
    worker = ElectronicsWorker()
    reg.register_worker(worker)

    # Première initialisation
    await worker.initialize()
    first_count = len(reg.list_types(domain="electronics"))

    # Deuxième initialisation (devrait être idempotente)
    await worker.initialize()
    second_count = len(reg.list_types(domain="electronics"))

    # Les types ne devraient pas être dupliqués
    assert first_count == second_count == len(ELECTRONICS_DOMAIN_TYPES)


@pytest.mark.asyncio
async def test_electronics_worker_registry_reference():
    """Le worker reçoit une référence au registre lors de l'enregistrement."""
    reg = NodeRegistry(storage_path=None)
    worker = ElectronicsWorker()

    assert worker.registry is None

    reg.register_worker(worker)
    assert worker.registry is reg


@pytest.mark.asyncio
async def test_electronics_worker_can_retrieve_registered_types():
    """Les types enregistrés peuvent être récupérés par leur nom complet."""
    reg = NodeRegistry(storage_path=None)
    worker = ElectronicsWorker()
    reg.register_worker(worker)
    await worker.initialize()

    # Récupérer chaque type par son nom complet
    netlist_type = reg.get_type("electronics.Netlist")
    assert netlist_type.domain == "electronics"
    assert netlist_type.name == "Netlist"

    schematic_type = reg.get_type("electronics.Schematic")
    assert schematic_type.domain == "electronics"
    assert schematic_type.name == "Schematic"

    waveform_type = reg.get_type("electronics.Waveform")
    assert waveform_type.domain == "electronics"
    assert waveform_type.name == "Waveform"

    firmware_type = reg.get_type("electronics.FirmwareBinary")
    assert firmware_type.domain == "electronics"
    assert firmware_type.name == "FirmwareBinary"

    component_type = reg.get_type("electronics.ComponentSpec")
    assert component_type.domain == "electronics"
    assert component_type.name == "ComponentSpec"

    drc_type = reg.get_type("electronics.DRCReport")
    assert drc_type.domain == "electronics"
    assert drc_type.name == "DRCReport"


@pytest.mark.asyncio
async def test_electronics_worker_types_have_valid_schemas():
    """Les types enregistrés ont des schémas JSON valides."""
    reg = NodeRegistry(storage_path=None)
    worker = ElectronicsWorker()
    reg.register_worker(worker)
    await worker.initialize()

    for domain_type in reg.list_types(domain="electronics"):
        # Chaque type doit avoir un schéma non vide
        assert domain_type.schema is not None
        assert len(domain_type.schema) > 0
        assert "type" in domain_type.schema


@pytest.mark.asyncio
async def test_electronics_worker_worker_removed_from_registry():
    """Le worker peut être retiré du registre."""
    reg = NodeRegistry(storage_path=None)
    worker = ElectronicsWorker()
    reg.register_worker(worker)

    assert reg.has_worker("electronics") is True

    reg.remove_worker("electronics")
    assert reg.has_worker("electronics") is False
    assert worker.registry is None
