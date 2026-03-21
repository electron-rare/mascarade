"""Graph serialization with versioned JSON format.

Provides GraphSerializer for saving/loading graph definitions
with version tracking and migration support.
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
from collections.abc import Callable
from dataclasses import asdict
from enum import Enum
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from mascarade.node_engine.graph import Graph, GraphEdge, GraphNode, GraphStatus

logger = logging.getLogger("mascarade.node_engine.persistence")

CURRENT_SCHEMA_VERSION = "1.0.0"
SCHEMA_NAME = "universal-node-engine-graph-v1"


def iso_utc_now() -> str:
    """Retourne un timestamp ISO8601 UTC avec suffixe Z stable."""
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


class MigrationRegistry:
    """Registre de migrations pour les mises à jour de schéma."""

    def __init__(self) -> None:
        self._migrations: dict[tuple[str, str], Callable[[dict[str, Any]], dict[str, Any]]] = {}

    def register(
        self,
        from_version: str,
        to_version: str,
        migration_func: Callable[[dict[str, Any]], dict[str, Any]],
    ) -> None:
        """
        Enregistrer une fonction de migration.

        Args:
            from_version: Version source du schéma
            to_version: Version cible du schéma
            migration_func: Fonction qui transforme les données de la version source à la cible
        """
        key = (from_version, to_version)
        if key in self._migrations:
            logger.warning(
                "Replacing existing migration from %s to %s",
                from_version,
                to_version,
            )
        self._migrations[key] = migration_func
        logger.debug("Registered migration: %s -> %s", from_version, to_version)

    def get(
        self, from_version: str, to_version: str
    ) -> Callable[[dict[str, Any]], dict[str, Any]]:
        """
        Obtenir une fonction de migration.

        Args:
            from_version: Version source
            to_version: Version cible

        Returns:
            La fonction de migration

        Raises:
            KeyError: Si la migration n'existe pas
        """
        key = (from_version, to_version)
        if key not in self._migrations:
            raise KeyError(
                f"No migration from '{from_version}' to '{to_version}'. "
                f"Available: {list(self._migrations.keys())}"
            )
        return self._migrations[key]

    def migrate(self, data: dict[str, Any], target_version: str) -> dict[str, Any]:
        """
        Migrer des données vers une version cible.

        Args:
            data: Données à migrer (doit contenir une clé 'version')
            target_version: Version cible du schéma

        Returns:
            Données migrées

        Raises:
            KeyError: Si la migration nécessaire n'existe pas
            ValueError: Si les données sont invalides
        """
        current_version = data.get("version")
        if not current_version:
            raise ValueError("Data missing 'version' key")

        if current_version == target_version:
            logger.debug("Data already at target version %s", target_version)
            return data

        migration_func = self.get(current_version, target_version)
        logger.info("Migrating data from %s to %s", current_version, target_version)

        try:
            migrated_data = migration_func(data)
            migrated_data["version"] = target_version
            return migrated_data
        except Exception as exc:
            logger.error(
                "Migration failed from %s to %s: %s",
                current_version,
                target_version,
                exc,
            )
            raise

    def list_migrations(self) -> list[tuple[str, str]]:
        """
        Lister toutes les migrations disponibles.

        Returns:
            Liste de tuples (from_version, to_version)
        """
        return list(self._migrations.keys())

    def __contains__(self, key: tuple[str, str]) -> bool:
        """Vérifier si une migration existe."""
        return key in self._migrations

    def __len__(self) -> int:
        """Nombre de migrations enregistrées."""
        return len(self._migrations)


def _obj_to_dict(obj: Any) -> Any:
    """Convert a dataclass or object to a dict recursively."""
    import dataclasses
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return asdict(obj)
    elif isinstance(obj, dict):
        return {k: _obj_to_dict(v) for k, v in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return type(obj)(_obj_to_dict(item) for item in obj)
    elif isinstance(obj, Enum):
        return obj.value
    else:
        return obj


def _graph_to_dict(graph: Graph) -> dict[str, Any]:
    """Convert a Graph instance to a dictionary."""
    import dataclasses

    nodes_data = []
    for node in graph.nodes:
        if dataclasses.is_dataclass(node) and not isinstance(node, type):
            nodes_data.append(asdict(node))
        else:
            nodes_data.append({
                "id": getattr(node, "id", ""),
                "node_type": getattr(node, "node_type", ""),
                "label": getattr(node, "label", ""),
                "config": getattr(node, "config", {}),
                "position": getattr(node, "position", (0.0, 0.0)),
                "domain": getattr(node, "domain", None),
            })

    edges_data = []
    for edge in graph.edges:
        if dataclasses.is_dataclass(edge) and not isinstance(edge, type):
            edges_data.append(asdict(edge))
        else:
            edges_data.append({
                "id": getattr(edge, "id", ""),
                "source_node": getattr(edge, "source_node", ""),
                "source_port": getattr(edge, "source_port", ""),
                "target_node": getattr(edge, "target_node", ""),
                "target_port": getattr(edge, "target_port", ""),
            })

    status_val = graph.status.value if isinstance(graph.status, GraphStatus) else str(graph.status)

    return {
        "id": graph.id,
        "name": graph.name,
        "version": graph.version,
        "status": status_val,
        "nodes": nodes_data,
        "edges": edges_data,
        "metadata": dict(graph.metadata),
    }


class GraphSerializer:
    """
    Serializes and deserializes graphs to/from versioned JSON format.

    Follows the AgentRegistry persistence pattern with atomic writes,
    error handling, and logging. The JSON format is versioned for
    forward compatibility and schema evolution.

    Phase 0 Implementation:
        - Single-version persistence with atomic writes (temp + rename)
        - Schema versioning via MigrationRegistry
        - File-based JSON storage

    Phase 1+ Features (PostgreSQL):
        - Version history tracking with JSON Patch diffs (RFC 6902)
        - Version metadata (author, timestamp, description)
        - Efficient version chain storage and querying
        - Concurrent multi-user version management

    The file-based approach in Phase 0 focuses on reliable storage
    of the current graph state. Advanced version history features
    are deferred to the PostgreSQL backend in Phase 1+.
    """

    def __init__(self, schema_version: str = CURRENT_SCHEMA_VERSION) -> None:
        self._schema_version = schema_version

    def serialize(self, graph: Graph) -> dict[str, Any]:
        """
        Serialize a Graph to a versioned JSON-compatible dictionary.

        Args:
            graph: The Graph instance to serialize

        Returns:
            A dictionary ready for JSON serialization
        """
        # Convert to dict (handles both dataclass and regular class)
        graph_data = _graph_to_dict(graph)

        # Convert enum to string
        if isinstance(graph.status, GraphStatus):
            graph_data["status"] = graph.status.value

        # Add metadata timestamps if not present
        if "created_at" not in graph_data.get("metadata", {}):
            graph_data.setdefault("metadata", {})
            graph_data["metadata"]["created_at"] = iso_utc_now()

        graph_data["metadata"]["updated_at"] = iso_utc_now()

        # Wrap in versioned envelope
        return {
            "version": self._schema_version,
            "schema": SCHEMA_NAME,
            "graph": graph_data,
        }

    def deserialize(self, data: dict[str, Any]) -> Graph:
        """
        Deserialize a versioned JSON dictionary back to a Graph instance.

        Args:
            data: The versioned JSON data

        Returns:
            A Graph instance

        Raises:
            ValueError: If the data is invalid or unsupported version
        """
        schema_version = data.get("version")
        if schema_version != self._schema_version:
            logger.warning(
                "Schema version mismatch: expected %s, got %s. Attempting to parse anyway.",
                self._schema_version,
                schema_version,
            )

        graph_data = data.get("graph")
        if not graph_data:
            raise ValueError("Missing 'graph' key in serialized data")

        # Convert status string to enum
        if "status" in graph_data and isinstance(graph_data["status"], str):
            graph_data["status"] = GraphStatus(graph_data["status"])

        # Reconstruct nested dataclasses
        if "nodes" in graph_data:
            graph_data["nodes"] = [
                GraphNode(**node) if isinstance(node, dict) else node
                for node in graph_data["nodes"]
            ]

        if "edges" in graph_data:
            graph_data["edges"] = [
                GraphEdge(**edge) if isinstance(edge, dict) else edge
                for edge in graph_data["edges"]
            ]

        return Graph(**graph_data)

    def save(self, graph: Graph, path: Path) -> None:
        """
        Save a graph to a JSON file with atomic write.

        Args:
            graph: The graph to save
            path: The file path to save to

        Follows the AgentRegistry.save() pattern with atomic writes
        (temp file + rename) for crash safety.
        """
        path.parent.mkdir(parents=True, exist_ok=True)

        serialized = self.serialize(graph)

        # Atomic write: write to temp file, then rename
        fd, tmp_path = tempfile.mkstemp(
            dir=str(path.parent), suffix=".tmp"
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(serialized, f, indent=2, ensure_ascii=False)
            os.replace(tmp_path, str(path))
        except BaseException:
            os.unlink(tmp_path)
            raise

    def load(self, path: Path) -> Graph:
        """
        Load a graph from a JSON file.

        Args:
            path: The file path to load from

        Returns:
            The deserialized Graph instance

        Raises:
            FileNotFoundError: If the file doesn't exist
            ValueError: If the file contains invalid data
        """
        if not path.exists():
            raise FileNotFoundError(f"Graph file not found: {path}")

        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            logger.error("Failed to load graph from %s: %s", path, exc)
            raise ValueError(f"Failed to parse graph file: {exc}") from exc

        return self.deserialize(raw)
