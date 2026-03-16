"""Graph serialization with versioned JSON format.

Provides GraphSerializer for saving/loading graph definitions
with version tracking and migration support.
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
from dataclasses import asdict
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


class GraphSerializer:
    """
    Serializes and deserializes graphs to/from versioned JSON format.

    Follows the AgentRegistry persistence pattern with atomic writes,
    error handling, and logging. The JSON format is versioned for
    forward compatibility and schema evolution.
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
        # Convert dataclass to dict
        graph_data = asdict(graph)

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
