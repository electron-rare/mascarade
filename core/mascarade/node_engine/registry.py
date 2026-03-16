"""Node registry — type and worker registration for the Node Engine."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING

from mascarade.node_engine.types import DomainType

if TYPE_CHECKING:
    from mascarade.node_engine.worker import NodeWorker

logger = logging.getLogger("mascarade.node_engine.registry")

DEFAULT_STORAGE_PATH = Path("data/node_types.json")


class NodeRegistry:
    """Registre centralisé pour gérer les types de domaine et les workers."""

    def __init__(self, storage_path: Path | None = DEFAULT_STORAGE_PATH) -> None:
        self._domain_types: dict[str, DomainType] = {}
        self._workers: dict[str, NodeWorker] = {}
        self._builtin_types: set[str] = set()
        self._storage_path = storage_path

    # --- Domain Type Registration ---

    def register_type(self, domain_type: DomainType, *, builtin: bool = False) -> None:
        """Enregistrer un type de domaine.

        Args:
            domain_type: Type de domaine à enregistrer
            builtin: Si True, marque le type comme intégré (non sauvegardé)
        """
        self._domain_types[domain_type.full_name] = domain_type
        if builtin:
            self._builtin_types.add(domain_type.full_name)

    def get_type(self, full_name: str) -> DomainType:
        """Obtenir un type de domaine par son nom complet.

        Args:
            full_name: Nom complet du type (ex: "electronics.Netlist")

        Returns:
            DomainType correspondant

        Raises:
            KeyError: Si le type n'existe pas
        """
        if full_name not in self._domain_types:
            raise KeyError(
                f"Type '{full_name}' non trouvé. Disponibles: {list(self._domain_types.keys())}"
            )
        return self._domain_types[full_name]

    def list_types(self, domain: str | None = None) -> list[DomainType]:
        """Lister les types de domaine disponibles.

        Args:
            domain: Si fourni, filtre par domaine spécifique

        Returns:
            Liste des types de domaine
        """
        if domain is None:
            return list(self._domain_types.values())
        return [dt for dt in self._domain_types.values() if dt.domain == domain]

    def remove_type(self, full_name: str) -> None:
        """Retirer un type de domaine du registre.

        Args:
            full_name: Nom complet du type à retirer
        """
        self._domain_types.pop(full_name, None)
        self._builtin_types.discard(full_name)

    def has_type(self, full_name: str) -> bool:
        """Vérifier si un type existe dans le registre.

        Args:
            full_name: Nom complet du type

        Returns:
            True si le type existe, False sinon
        """
        return full_name in self._domain_types

    def is_builtin_type(self, full_name: str) -> bool:
        """Vérifier si un type est intégré.

        Args:
            full_name: Nom complet du type

        Returns:
            True si le type est intégré, False sinon
        """
        return full_name in self._builtin_types

    # --- Worker Registration ---

    def register_worker(self, worker: NodeWorker) -> None:
        """Enregistrer un worker de domaine.

        Args:
            worker: Worker à enregistrer
        """
        self._workers[worker.domain] = worker
        worker.registry = self

    def get_worker(self, domain: str) -> NodeWorker:
        """Obtenir un worker par domaine.

        Args:
            domain: Nom du domaine (ex: "electronics")

        Returns:
            NodeWorker correspondant

        Raises:
            KeyError: Si le worker n'existe pas
        """
        if domain not in self._workers:
            raise KeyError(
                f"Worker pour domaine '{domain}' non trouvé. Disponibles: {list(self._workers.keys())}"
            )
        return self._workers[domain]

    def list_workers(self) -> list[NodeWorker]:
        """Lister tous les workers enregistrés.

        Returns:
            Liste des workers
        """
        return list(self._workers.values())

    def remove_worker(self, domain: str) -> None:
        """Retirer un worker du registre.

        Args:
            domain: Domaine du worker à retirer
        """
        worker = self._workers.pop(domain, None)
        if worker:
            worker.registry = None

    def has_worker(self, domain: str) -> bool:
        """Vérifier si un worker existe pour un domaine.

        Args:
            domain: Nom du domaine

        Returns:
            True si le worker existe, False sinon
        """
        return domain in self._workers

    async def initialize_workers(self) -> None:
        """Initialiser tous les workers enregistrés.

        Appelle la méthode initialize() de chaque worker dans l'ordre
        d'enregistrement. Les erreurs d'initialisation sont journalisées
        mais n'empêchent pas l'initialisation des autres workers.
        """
        for domain, worker in self._workers.items():
            try:
                logger.info("Initializing worker for domain: %s", domain)
                await worker.initialize()
            except Exception as exc:
                logger.error(
                    "Failed to initialize worker for domain %s: %s",
                    domain,
                    exc,
                    exc_info=True,
                )

    async def shutdown_workers(self) -> None:
        """Arrêter tous les workers enregistrés.

        Appelle la méthode shutdown() de chaque worker. Les erreurs
        sont journalisées mais n'empêchent pas l'arrêt des autres workers.
        """
        for domain, worker in self._workers.items():
            try:
                logger.info("Shutting down worker for domain: %s", domain)
                await worker.shutdown()
            except Exception as exc:
                logger.error(
                    "Failed to shutdown worker for domain %s: %s",
                    domain,
                    exc,
                    exc_info=True,
                )

    # --- Persistence ---

    def save(self) -> None:
        """Sauvegarder les types de domaine dynamiques dans un fichier JSON."""
        if self._storage_path is None:
            return

        self._storage_path.parent.mkdir(parents=True, exist_ok=True)
        types_data = []

        for domain_type in self._domain_types.values():
            if domain_type.full_name in self._builtin_types:
                continue

            data = {
                "domain": domain_type.domain,
                "name": domain_type.name,
                "schema": domain_type.schema,
                "description": domain_type.description,
                "metadata": domain_type.metadata,
            }
            types_data.append(data)

        try:
            with open(self._storage_path, "w", encoding="utf-8") as f:
                json.dump(types_data, f, indent=2, ensure_ascii=False)
        except OSError as exc:
            logger.error("Failed to save types to %s: %s", self._storage_path, exc)

    def load(self) -> None:
        """Charger les types de domaine depuis le fichier JSON."""
        if self._storage_path is None or not self._storage_path.exists():
            return

        try:
            raw = json.loads(self._storage_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            logger.error("Failed to load types from %s: %s", self._storage_path, exc)
            return

        for data in raw:
            try:
                domain_type = DomainType(
                    domain=data["domain"],
                    name=data["name"],
                    schema=data["schema"],
                    description=data.get("description", ""),
                    metadata=data.get("metadata", {}),
                )
                self.register_type(domain_type)
            except (KeyError, TypeError, ValueError) as exc:
                logger.warning("Skipping invalid type entry: %s", exc)

    # --- Utility Methods ---

    def __len__(self) -> int:
        """Retourne le nombre total de types et workers."""
        return len(self._domain_types) + len(self._workers)

    def __repr__(self) -> str:
        """Représentation lisible du registre."""
        return (
            f"NodeRegistry(types={len(self._domain_types)}, "
            f"workers={len(self._workers)})"
        )
