"""Worker de base — interface pour les workers de domaine du Node Engine."""

from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mascarade.node_engine.registry import NodeRegistry


@dataclass
class WorkerCapabilities:
    """Capacités et contraintes d'un worker de domaine."""

    node_prefixes: list[str] = field(default_factory=list)
    max_concurrent: int = 4
    requires_gpu: bool = False
    estimated_memory_mb: int = 512
    external_tools: list[str] = field(default_factory=list)


class NodeWorker:
    """Interface de base pour les workers de domaine du Node Engine.

    Un NodeWorker est responsable de:
    - Enregistrer les types de domaine avec le registre
    - Fournir des nœuds exécutables pour son domaine
    - Gérer le cycle de vie (initialisation, arrêt)
    - Vérifier la disponibilité des outils externes
    """

    domain: str = ""
    version: str = "0.0.0"
    registry: NodeRegistry | None = None

    def capabilities(self) -> WorkerCapabilities:
        """Retourne les capacités et contraintes de ce worker.

        Doit être implémenté par les classes dérivées.
        """
        raise NotImplementedError("Subclasses must implement capabilities()")

    async def initialize(self) -> None:
        """Initialise le worker et enregistre ses types de domaine.

        Appelé une fois au démarrage du worker. Utilise le registre
        pour enregistrer les types de domaine et vérifier la disponibilité
        des outils externes.
        """
        raise NotImplementedError("Subclasses must implement initialize()")

    async def shutdown(self) -> None:
        """Nettoie les ressources et ferme les connexions.

        Appelé lors de l'arrêt du worker pour libérer les ressources,
        fermer les connexions, et supprimer les fichiers temporaires.
        """
        raise NotImplementedError("Subclasses must implement shutdown()")

    async def _check_tool(self, tool_name: str) -> bool:
        """Vérifie la disponibilité d'un outil externe.

        Args:
            tool_name: Nom de l'outil à vérifier (ex: "ngspice", "kicad-cli")

        Returns:
            True si l'outil est disponible dans le PATH, False sinon
        """
        return shutil.which(tool_name) is not None
