"""Electronics domain worker for the Universal Node Engine."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from mascarade.node_engine.domains.electronics import ELECTRONICS_DOMAIN_TYPES
from mascarade.node_engine.worker import NodeWorker, WorkerCapabilities

if TYPE_CHECKING:
    from mascarade.node_engine.registry import NodeRegistry

logger = logging.getLogger("mascarade.node_engine.workers.electronics")


class ElectronicsWorker(NodeWorker):
    """Worker de domaine pour l'électronique: SPICE, PCB DRC, firmware, composants.

    Ce worker fournit des nœuds pour:
    - Simulation SPICE (génération de netlist, simulation, analyse, debug de convergence)
    - Vérification de règles de conception PCB (DRC avec KiCad)
    - Compilation de firmware (ESP-IDF, PlatformIO)
    - Gestion de bibliothèque de composants (LCSC, JLCPCB)

    Le worker dégrade gracieusement lorsque les outils externes ne sont pas disponibles,
    en émettant des avertissements clairs au lieu d'échouer complètement.
    """

    domain = "electronics"
    version = "1.0.0"

    def __init__(self) -> None:
        """Initialise le worker électronique."""
        super().__init__()
        self._ngspice_available: bool = False
        self._kicad_available: bool = False
        self._espidf_available: bool = False
        self._platformio_available: bool = False

    def capabilities(self) -> WorkerCapabilities:
        """Retourne les capacités et contraintes du worker électronique.

        Returns:
            WorkerCapabilities avec les préfixes de nœuds supportés,
            limites de concurrence, et outils externes requis
        """
        return WorkerCapabilities(
            node_prefixes=[
                "electronics.spice",
                "electronics.pcb",
                "electronics.firmware",
                "electronics.components",
            ],
            max_concurrent=4,
            requires_gpu=False,
            estimated_memory_mb=512,
            external_tools=["ngspice", "kicad-cli", "idf.py", "pio"],
        )

    async def initialize(self) -> None:
        """Initialise le worker et enregistre les types de domaine électronique.

        Enregistre tous les types de domaine (Netlist, Schematic, Waveform,
        FirmwareBinary, ComponentSpec) et vérifie la disponibilité des outils
        externes (ngspice, kicad-cli, idf.py, pio).

        Les outils manquants émettent des avertissements mais n'empêchent pas
        l'initialisation — les nœuds qui en dépendent échoueront avec des
        messages d'erreur descriptifs lors de l'exécution.
        """
        # Enregistrer les types de domaine électronique
        if self.registry:
            for domain_type in ELECTRONICS_DOMAIN_TYPES:
                self.registry.register_type(domain_type, builtin=True)
            logger.info(
                "Registered %d electronics domain types",
                len(ELECTRONICS_DOMAIN_TYPES),
            )

        # Vérifier la disponibilité des outils externes (warn if missing, don't fail)
        self._ngspice_available = await self._check_tool("ngspice")
        if not self._ngspice_available:
            logger.warning(
                "ngspice not found in PATH. SPICE simulation nodes will fail. "
                "Install with: apt-get install ngspice (Debian/Ubuntu) or brew install ngspice (macOS)"
            )

        self._kicad_available = await self._check_tool("kicad-cli")
        if not self._kicad_available:
            logger.warning(
                "kicad-cli not found in PATH. PCB DRC nodes will fail. "
                "Install KiCad 7.0+ from https://www.kicad.org/download/"
            )

        self._espidf_available = await self._check_tool("idf.py")
        if not self._espidf_available:
            logger.warning(
                "idf.py not found in PATH. ESP-IDF firmware compilation will not be available. "
                "Install ESP-IDF from https://docs.espressif.com/projects/esp-idf/en/latest/esp32/get-started/"
            )

        self._platformio_available = await self._check_tool("pio")
        if not self._platformio_available:
            logger.warning(
                "pio (PlatformIO) not found in PATH. PlatformIO firmware compilation will not be available. "
                "Install with: pip install platformio"
            )

        # Avertissement si aucun framework de firmware n'est disponible
        if not self._espidf_available and not self._platformio_available:
            logger.warning(
                "Neither ESP-IDF nor PlatformIO available. Firmware compilation nodes will fail. "
                "Install at least one firmware framework."
            )

    async def shutdown(self) -> None:
        """Nettoie les ressources et ferme les connexions.

        Appelé lors de l'arrêt du worker. Actuellement, il n'y a pas de
        ressources persistantes à nettoyer (pas de connexions réseau,
        pas de fichiers temporaires gérés au niveau du worker).

        Les nœuds individuels gèrent leurs propres fichiers temporaires
        et processus externes dans leurs méthodes execute().
        """
        # Aucune ressource persistante à nettoyer pour l'instant
        # Les nœuds individuels gèrent leurs propres fichiers temporaires
        pass
