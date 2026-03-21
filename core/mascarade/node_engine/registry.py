"""Registre de types de nœuds — enregistrement, découverte et validation."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from mascarade.node_engine.base import NodeDefinition

logger = logging.getLogger("mascarade.node_engine")

DEFAULT_STORAGE_PATH = Path("data/node_types.json")


class NodeTypeRegistry:
    """Registre centralisé pour gérer les types de nœuds disponibles."""

    def __init__(self, storage_path: Path | None = DEFAULT_STORAGE_PATH) -> None:
        self._node_types: dict[str, NodeDefinition] = {}
        self._builtin_types: set[str] = set()
        self._storage_path = storage_path

    def register(self, node_def: NodeDefinition, *, builtin: bool = False) -> None:
        """Enregistrer un type de nœud.

        Args:
            node_def: Définition du nœud à enregistrer
            builtin: Si True, marque ce type comme intégré (non persisté)

        Raises:
            ValueError: Si le type de nœud est invalide
        """
        self._validate_node_definition(node_def)
        self._node_types[node_def.node_type] = node_def
        if builtin:
            self._builtin_types.add(node_def.node_type)

    def get(self, node_type: str) -> NodeDefinition:
        """Obtenir une définition de nœud par son type.

        Args:
            node_type: Type de nœud qualifié (e.g., "hardware.esp32.gpio")

        Returns:
            NodeDefinition correspondante

        Raises:
            KeyError: Si le type de nœud n'est pas trouvé
        """
        if node_type not in self._node_types:
            raise KeyError(
                f"Node type '{node_type}' non trouvé. Disponibles: {list(self._node_types.keys())}"
            )
        return self._node_types[node_type]

    def list(self) -> list[NodeDefinition]:
        """Lister toutes les définitions de nœuds enregistrées.

        Returns:
            Liste de toutes les NodeDefinition
        """
        return list(self._node_types.values())

    def list_by_domain(self, domain: str) -> list[NodeDefinition]:
        """Lister les nœuds d'un domaine spécifique.

        Args:
            domain: Nom du domaine (e.g., "hardware", "llm")

        Returns:
            Liste des NodeDefinition du domaine
        """
        return [
            node_def
            for node_def in self._node_types.values()
            if node_def.node_type.startswith(f"{domain}.")
        ]

    def remove(self, node_type: str) -> None:
        """Retirer un type de nœud du registre.

        Args:
            node_type: Type de nœud à retirer
        """
        self._node_types.pop(node_type, None)
        self._builtin_types.discard(node_type)

    def __contains__(self, node_type: str) -> bool:
        """Vérifier si un type de nœud est enregistré."""
        return node_type in self._node_types

    def __len__(self) -> int:
        """Obtenir le nombre de types de nœuds enregistrés."""
        return len(self._node_types)

    def is_builtin(self, node_type: str) -> bool:
        """Vérifier si un type de nœud est intégré.

        Args:
            node_type: Type de nœud à vérifier

        Returns:
            True si le type est intégré, False sinon
        """
        return node_type in self._builtin_types

    # --- Validation ---

    def _validate_node_definition(self, node_def: NodeDefinition) -> None:
        """Valider une définition de nœud.

        Args:
            node_def: Définition à valider

        Raises:
            ValueError: Si la définition est invalide
        """
        if not node_def.node_type:
            raise ValueError("Node type cannot be empty")

        # Validate node_type format (domain.category.name)
        parts = node_def.node_type.split(".")
        if len(parts) < 2:
            raise ValueError(
                f"Node type '{node_def.node_type}' must be in format 'domain.category.name'"
            )

        # Validate port names are unique within input and output sets
        input_names = {port.name for port in node_def.input_ports}
        if len(input_names) != len(node_def.input_ports):
            raise ValueError(
                f"Duplicate input port names in node type '{node_def.node_type}'"
            )

        output_names = {port.name for port in node_def.output_ports}
        if len(output_names) != len(node_def.output_ports):
            raise ValueError(
                f"Duplicate output port names in node type '{node_def.node_type}'"
            )

    # --- Persistance ---

    def save(self) -> None:
        """Sauvegarder les types de nœuds dynamiques dans un fichier JSON.

        Ne sauvegarde que les types non-intégrés.
        """
        if self._storage_path is None:
            return

        self._storage_path.parent.mkdir(parents=True, exist_ok=True)

        # Filter out builtin types
        types_data = []
        for node_def in self._node_types.values():
            if node_def.node_type in self._builtin_types:
                continue

            # Convert to dict for JSON serialization
            data = {
                "node_type": node_def.node_type,
                "description": node_def.description,
                "input_ports": [port.model_dump() for port in node_def.input_ports],
                "output_ports": [port.model_dump() for port in node_def.output_ports],
                "tags": node_def.tags,
                "version": node_def.version,
                "max_latency_ms": node_def.max_latency_ms,
                "max_jitter_ms": node_def.max_jitter_ms,
                "cpu_intensive": node_def.cpu_intensive,
                "io_intensive": node_def.io_intensive,
                "memory_estimate_mb": node_def.memory_estimate_mb,
            }
            types_data.append(data)

        # Write to file
        with self._storage_path.open("w", encoding="utf-8") as f:
            json.dump(types_data, f, indent=2, ensure_ascii=False)

    def load(self) -> None:
        """Charger les types de nœuds dynamiques depuis le fichier JSON."""
        if self._storage_path is None or not self._storage_path.exists():
            return

        try:
            raw = json.loads(self._storage_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            logger.error(
                "Failed to load node types from %s: %s", self._storage_path, exc
            )
            return

        for data in raw:
            try:
                # Reconstruct NodeDefinition from dict
                from mascarade.node_engine.types import NodePort

                node_def = NodeDefinition(
                    node_type=data["node_type"],
                    description=data.get("description", ""),
                    input_ports=[NodePort(**port) for port in data.get("input_ports", [])],
                    output_ports=[NodePort(**port) for port in data.get("output_ports", [])],
                    tags=data.get("tags", []),
                    version=data.get("version", "1.0.0"),
                    max_latency_ms=data.get("max_latency_ms"),
                    max_jitter_ms=data.get("max_jitter_ms"),
                    cpu_intensive=data.get("cpu_intensive", False),
                    io_intensive=data.get("io_intensive", False),
                    memory_estimate_mb=data.get("memory_estimate_mb", 0),
                )
                self.register(node_def)
            except (KeyError, TypeError, ValueError) as exc:
                logger.warning("Skipping invalid node type entry: %s", exc)
