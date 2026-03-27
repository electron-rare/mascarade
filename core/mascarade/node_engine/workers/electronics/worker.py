"""Electronics domain worker for the Universal Node Engine."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from mascarade.node_engine.domains.electronics import ELECTRONICS_DOMAIN_TYPES
from mascarade.node_engine.worker import NodeCapability, NodeWorker
from mascarade.node_engine.workers.electronics.component_nodes import (
    AvailabilityCheckNode,
    BomGenerateNode,
    BomGeneratorNode,
    CplGeneratorNode,
    DatasheetNode,
    FindAlternativesNode,
    JlcpcbOptimizationNode,
    LookupNode,
)
from mascarade.node_engine.workers.electronics.firmware_nodes import (
    CompileNode,
    FlashPrepareNode,
    SizeAnalysisNode,
)
from mascarade.node_engine.workers.electronics.pcb_nodes import (
    DrcCheckNode,
    RuleDefinitionNode,
    ViolationReporterNode,
)
from mascarade.node_engine.workers.electronics.spice_nodes import (
    AnalyzeNode,
    DebugConvergenceNode,
    NetlistGeneratorNode,
    SimulateNode,
)

if TYPE_CHECKING:
    from mascarade.node_engine.workers.electronics.spice_nodes import BaseNode

logger = logging.getLogger("mascarade.node_engine.workers.electronics")

# Correspondance entre node_type et l'outil externe requis
_TOOL_REQUIREMENTS: dict[str, str] = {
    "electronics.spice.netlist_generator": "ngspice",
    "electronics.spice.simulate": "ngspice",
    "electronics.spice.analyze": "ngspice",
    "electronics.spice.debug_convergence": "ngspice",
    "electronics.pcb.drc_check": "kicad-cli",
    "electronics.pcb.rule_definition": "kicad-cli",
    "electronics.pcb.violation_reporter": "kicad-cli",
    "electronics.firmware.compile": "idf.py",
    "electronics.firmware.flash_prepare": "idf.py",
    "electronics.firmware.size_analysis": "idf.py",
}

# Correspondance entre node_type et la classe de nœud
_NODE_CLASSES: dict[str, type[BaseNode]] = {
    # SPICE
    "electronics.spice.netlist_generator": NetlistGeneratorNode,
    "electronics.spice.simulate": SimulateNode,
    "electronics.spice.analyze": AnalyzeNode,
    "electronics.spice.debug_convergence": DebugConvergenceNode,
    # PCB
    "electronics.pcb.drc_check": DrcCheckNode,
    "electronics.pcb.rule_definition": RuleDefinitionNode,
    "electronics.pcb.violation_reporter": ViolationReporterNode,
    # Firmware
    "electronics.firmware.compile": CompileNode,
    "electronics.firmware.flash_prepare": FlashPrepareNode,
    "electronics.firmware.size_analysis": SizeAnalysisNode,
    # Composants
    "electronics.component.lookup": LookupNode,
    "electronics.component.jlcpcb_optimization": JlcpcbOptimizationNode,
    "electronics.component.bom_generator": BomGeneratorNode,
    "electronics.component.cpl_generator": CplGeneratorNode,
    "electronics.component.availability_check": AvailabilityCheckNode,
    "electronics.component.datasheet": DatasheetNode,
    "electronics.component.bom_generate": BomGenerateNode,
    "electronics.component.find_alternatives": FindAlternativesNode,
}

# Correspondance nom d'outil → attribut de disponibilité sur le worker
_TOOL_ATTR_MAP: dict[str, str] = {
    "ngspice": "_ngspice_available",
    "kicad-cli": "_kicad_available",
    "idf.py": "_espidf_available",
    "pio": "_platformio_available",
}


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

    def capabilities(self) -> NodeCapability:
        """Retourne les capacités et contraintes du worker électronique.

        Returns:
            NodeCapability avec les préfixes de nœuds supportés,
            limites de concurrence, et outils externes requis
        """
        return NodeCapability(
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

    async def execute(
        self,
        node_type: str,
        inputs: dict[str, Any],
        config: dict[str, Any],
        context: Any,
    ) -> dict[str, Any]:
        """Exécute un nœud du domaine électronique.

        Résout la classe de nœud correspondant au node_type, vérifie la
        disponibilité de l'outil externe requis, instancie le nœud avec
        la configuration fournie, puis délègue l'exécution.

        Args:
            node_type: Identifiant qualifié du type de nœud
                (ex. "electronics.spice.simulate")
            inputs: Valeurs des ports d'entrée
            config: Configuration spécifique au nœud
            context: Contexte d'exécution (métadonnées, annulation)

        Returns:
            Valeurs des ports de sortie

        Raises:
            ValueError: Si le node_type est inconnu
            RuntimeError: Si l'outil externe requis n'est pas disponible
        """
        # Vérifier que le node_type est supporté
        node_cls = _NODE_CLASSES.get(node_type)
        if node_cls is None:
            raise ValueError(
                f"Type de nœud inconnu: {node_type}. "
                f"Types supportés: {', '.join(sorted(_NODE_CLASSES.keys()))}"
            )

        # Vérifier la disponibilité de l'outil externe requis
        required_tool = _TOOL_REQUIREMENTS.get(node_type)
        if required_tool:
            attr_name = _TOOL_ATTR_MAP.get(required_tool)
            tool_available = getattr(self, attr_name, False) if attr_name else False

            # Pour le firmware, accepter soit idf.py soit pio
            if node_type.startswith("electronics.firmware."):
                tool_available = self._espidf_available or self._platformio_available

            if not tool_available:
                raise RuntimeError(
                    f"Outil externe requis '{required_tool}' non disponible pour "
                    f"le nœud {node_type}. Vérifiez l'installation et le PATH."
                )

        # Construire la config du nœud à partir du dict de configuration
        node_config = None
        if config:
            # Les classes de nœuds acceptent des dataclass de config spécifiques.
            # On passe None pour laisser le nœud utiliser sa config par défaut,
            # sauf si la config fournit des paramètres exploitables.
            try:
                default_cfg = node_cls(config=None).config
                cfg_cls = type(default_cfg)
                # Filtrer les clés valides pour la dataclass de config
                valid_keys = {f.name for f in cfg_cls.__dataclass_fields__.values()}  # type: ignore[attr-defined]
                filtered = {k: v for k, v in config.items() if k in valid_keys}
                if filtered:
                    node_config = cfg_cls(**filtered)
            except Exception:
                # En cas d'échec de construction de config, laisser le nœud
                # utiliser sa config par défaut
                logger.debug(
                    "Impossible de construire la config pour %s, utilisation des défauts",
                    node_type,
                )

        # Instancier et exécuter le nœud
        node = node_cls(config=node_config)

        logger.info("Exécution du nœud %s", node_type)
        result = await node.execute(inputs)
        logger.debug("Nœud %s terminé avec %d sorties", node_type, len(result))

        return result

    async def validate(
        self,
        node_type: str,
        inputs: dict[str, Any],
        config: dict[str, Any],
    ) -> list[str]:
        """Valide les entrées et la configuration avant exécution.

        Vérifie que le node_type est supporté et que l'outil externe
        requis est disponible.

        Args:
            node_type: Identifiant qualifié du type de nœud
            inputs: Valeurs des ports d'entrée à valider
            config: Paramètres de configuration à valider

        Returns:
            Liste de messages d'erreur. Liste vide si la validation passe.
        """
        errors: list[str] = []

        # Vérifier que le node_type est supporté
        if node_type not in _NODE_CLASSES:
            errors.append(
                f"Type de nœud inconnu: {node_type}. "
                f"Types supportés: {', '.join(sorted(_NODE_CLASSES.keys()))}"
            )
            return errors

        # Vérifier la disponibilité de l'outil externe
        required_tool = _TOOL_REQUIREMENTS.get(node_type)
        if required_tool:
            attr_name = _TOOL_ATTR_MAP.get(required_tool)
            tool_available = getattr(self, attr_name, False) if attr_name else False

            if node_type.startswith("electronics.firmware."):
                tool_available = self._espidf_available or self._platformio_available

            if not tool_available:
                errors.append(
                    f"Outil externe '{required_tool}' non disponible pour {node_type}"
                )

        return errors

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
