"""Registre de types de nœuds — enregistrement, découverte et persistance."""

from __future__ import annotations

import json
import logging
import os
import tempfile
from dataclasses import asdict
from pathlib import Path

from mascarade.node_engine.types import DomainType, NodeType, PortType

logger = logging.getLogger("mascarade.node_engine")

DEFAULT_STORAGE_PATH = Path("data/node_types.json")


class NodeTypeRegistry:
    """Registre centralisé pour gérer les types de nœuds et types de domaine."""

    def __init__(self, storage_path: Path | None = DEFAULT_STORAGE_PATH) -> None:
        self._node_types: dict[str, NodeType] = {}
        self._domain_types: dict[str, DomainType] = {}
        self._builtin_node_names: set[str] = set()
        self._builtin_domain_names: set[str] = set()
        self._storage_path = storage_path

    # --- Node Type Management ---

    def register_node(self, node_type: NodeType, *, builtin: bool = False) -> None:
        """Enregistrer un type de nœud."""
        self._node_types[node_type.id] = node_type
        if builtin:
            self._builtin_node_names.add(node_type.id)

    def get_node(self, node_id: str) -> NodeType:
        """Récupérer un type de nœud par ID."""
        if node_id not in self._node_types:
            raise KeyError(
                f"Node type '{node_id}' non trouvé. Disponibles: {list(self._node_types.keys())}"
            )
        return self._node_types[node_id]

    def list_nodes(self, category: str | None = None) -> list[NodeType]:
        """Lister tous les types de nœuds, optionnellement filtrés par catégorie."""
        nodes = list(self._node_types.values())
        if category:
            nodes = [n for n in nodes if n.category == category]
        return nodes

    def remove_node(self, node_id: str) -> None:
        """Supprimer un type de nœud."""
        self._node_types.pop(node_id, None)
        self._builtin_node_names.discard(node_id)

    def is_builtin_node(self, node_id: str) -> bool:
        """Vérifier si un type de nœud est builtin."""
        return node_id in self._builtin_node_names

    # --- Domain Type Management ---

    def register_domain_type(
        self, domain_type: DomainType, *, builtin: bool = False
    ) -> None:
        """Enregistrer un type de domaine."""
        key = f"{domain_type.domain}.{domain_type.name}"
        self._domain_types[key] = domain_type
        if builtin:
            self._builtin_domain_names.add(key)

    def get_domain_type(self, domain: str, name: str) -> DomainType:
        """Récupérer un type de domaine par domaine et nom."""
        key = f"{domain}.{name}"
        if key not in self._domain_types:
            raise KeyError(
                f"Domain type '{key}' non trouvé. Disponibles: {list(self._domain_types.keys())}"
            )
        return self._domain_types[key]

    def list_domain_types(self, domain: str | None = None) -> list[DomainType]:
        """Lister tous les types de domaine, optionnellement filtrés par domaine."""
        types = list(self._domain_types.values())
        if domain:
            types = [t for t in types if t.domain == domain]
        return types

    def remove_domain_type(self, domain: str, name: str) -> None:
        """Supprimer un type de domaine."""
        key = f"{domain}.{name}"
        self._domain_types.pop(key, None)
        self._builtin_domain_names.discard(key)

    def is_builtin_domain_type(self, domain: str, name: str) -> bool:
        """Vérifier si un type de domaine est builtin."""
        key = f"{domain}.{name}"
        return key in self._builtin_domain_names

    # --- Magic Methods ---

    def __contains__(self, item: str) -> bool:
        """Vérifier si un type de nœud ou de domaine existe."""
        return item in self._node_types or item in self._domain_types

    def __len__(self) -> int:
        """Nombre total de types (nœuds + domaines)."""
        return len(self._node_types) + len(self._domain_types)

    # --- Persistance ---

    def save(self) -> None:
        """Sauvegarder les types dynamiques dans un fichier JSON."""
        if self._storage_path is None:
            return

        self._storage_path.parent.mkdir(parents=True, exist_ok=True)

        # Séparer les types builtin des types dynamiques
        node_types_data = []
        for node_type in self._node_types.values():
            if node_type.id in self._builtin_node_names:
                continue
            data = asdict(node_type)
            node_types_data.append(data)

        domain_types_data = []
        for domain_type in self._domain_types.values():
            key = f"{domain_type.domain}.{domain_type.name}"
            if key in self._builtin_domain_names:
                continue
            data = asdict(domain_type)
            domain_types_data.append(data)

        registry_data = {
            "node_types": node_types_data,
            "domain_types": domain_types_data,
        }

        # Atomic write: write to temp file, then rename
        fd, tmp_path = tempfile.mkstemp(
            dir=str(self._storage_path.parent), suffix=".tmp"
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(registry_data, f, indent=2, ensure_ascii=False)
            os.replace(tmp_path, str(self._storage_path))
        except BaseException:
            os.unlink(tmp_path)
            raise

    def load(self) -> None:
        """Charger les types dynamiques depuis le fichier JSON."""
        if self._storage_path is None or not self._storage_path.exists():
            return
        try:
            raw = json.loads(self._storage_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            logger.error("Failed to load node types from %s: %s", self._storage_path, exc)
            return

        # Charger les types de nœuds
        for data in raw.get("node_types", []):
            try:
                # Convertir les dicts inputs/outputs en PortType
                inputs = [PortType(**p) for p in data.get("inputs", [])]
                outputs = [PortType(**p) for p in data.get("outputs", [])]
                node_type = NodeType(
                    id=data["id"],
                    category=data["category"],
                    inputs=inputs,
                    outputs=outputs,
                )
                self.register_node(node_type)
            except (KeyError, TypeError, ValueError) as exc:
                logger.warning("Skipping invalid node type entry: %s", exc)

        # Charger les types de domaine
        for data in raw.get("domain_types", []):
            try:
                domain_type = DomainType(**data)
                self.register_domain_type(domain_type)
            except (KeyError, TypeError, ValueError) as exc:
                logger.warning("Skipping invalid domain type entry: %s", exc)
