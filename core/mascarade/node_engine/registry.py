"""Registry for domain type registration and discovery."""

from __future__ import annotations

import json
import logging
import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from mascarade.node_engine.types import DomainType

if TYPE_CHECKING:
    from mascarade.node_engine.worker import NodeWorker

logger = logging.getLogger("mascarade.node_engine.registry")


@dataclass
class NodeType:
    """Definition of a node type in the registry."""

    id: str
    domain: str
    label: str
    description: str
    version: str = "1.0.0"
    inputs: list[dict[str, Any]] = field(default_factory=list)
    outputs: list[dict[str, Any]] = field(default_factory=list)
    config_schema: dict[str, Any] = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)
    deprecated: bool = False
    deprecated_by: str | None = None


DEFAULT_STORAGE_PATH = Path("data/domain_types.json")


class NodeTypeRegistry:
    """Centralized registry for managing domain types.

    Stores and retrieves domain-specific type definitions (DomainType instances)
    that extend the base type system with domain-specific structures.
    """

    def __init__(self, storage_path: Path | None = DEFAULT_STORAGE_PATH) -> None:
        self._types: dict[str, DomainType] = {}
        self._builtin_names: set[str] = set()
        self._storage_path = storage_path

    def register(self, domain_type: DomainType | NodeType, *, builtin: bool = False) -> None:
        """Register a domain type or node type."""
        if isinstance(domain_type, NodeType):
            qualified_name = domain_type.id
        else:
            qualified_name = domain_type.qualified_name
        if qualified_name in self._types and qualified_name not in self._builtin_names:
            logger.warning("Overwriting existing type: %s", qualified_name)
        self._types[qualified_name] = domain_type  # type: ignore[assignment]
        if builtin:
            self._builtin_names.add(qualified_name)

    def get(self, qualified_name: str) -> DomainType:
        """Get a domain type by its qualified name (domain.name)."""
        if qualified_name not in self._types:
            raise KeyError(
                f"Domain type '{qualified_name}' not found. "
                f"Available: {list(self._types.keys())}"
            )
        return self._types[qualified_name]

    def get_by_domain(self, domain: str) -> list[DomainType]:
        """Get all domain types for a specific domain."""
        return [dt for dt in self._types.values() if dt.domain == domain]

    def list(self, domain: str | None = None) -> list:
        """List all registered types, optionally filtered by domain."""
        types = list(self._types.values())
        if domain:
            types = [t for t in types if getattr(t, "domain", None) == domain]
        return types

    def remove(self, qualified_name: str) -> None:
        """Remove a domain type from the registry."""
        self._types.pop(qualified_name, None)
        self._builtin_names.discard(qualified_name)

    def __contains__(self, qualified_name: str) -> bool:
        return qualified_name in self._types

    def __len__(self) -> int:
        return len(self._types)

    def is_builtin(self, qualified_name: str) -> bool:
        return qualified_name in self._builtin_names

    # --- Persistence ---

    def save(self) -> None:
        """Save custom domain types to JSON file (atomic write)."""
        if self._storage_path is None:
            return

        self._storage_path.parent.mkdir(parents=True, exist_ok=True)

        types_data = []
        for key, entry in self._types.items():
            if key in self._builtin_names:
                continue
            if isinstance(entry, NodeType):
                from dataclasses import asdict

                types_data.append(asdict(entry))
            else:
                types_data.append(entry.model_dump())

        fd, tmp_path = tempfile.mkstemp(dir=str(self._storage_path.parent), suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(types_data, f, indent=2, ensure_ascii=False)
            os.replace(tmp_path, str(self._storage_path))
        except BaseException:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
            raise

    def load(self) -> None:
        """Load custom domain types from JSON file."""
        if self._storage_path is None or not self._storage_path.exists():
            return

        try:
            raw = json.loads(self._storage_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            logger.error("Failed to load domain types from %s: %s", self._storage_path, exc)
            return

        for data in raw:
            try:
                if "id" in data and "label" in data:
                    node_type = NodeType(**data)
                    self.register(node_type)
                else:
                    domain_type = DomainType(**data)
                    self.register(domain_type)
            except (KeyError, TypeError, ValueError) as exc:
                logger.warning("Skipping invalid type entry: %s", exc)


class WorkerRegistry:
    """Registry of domain workers. One worker per domain."""

    def __init__(self) -> None:
        self._workers: dict[str, "NodeWorker"] = {}

    def register(self, worker: "NodeWorker") -> None:
        """Register a worker for its domain."""
        self._workers[worker.domain] = worker

    def get(self, domain: str) -> "NodeWorker":
        """Get the worker for a domain. Raises KeyError if not found."""
        if domain not in self._workers:
            raise KeyError(
                f"No worker registered for domain '{domain}'. "
                f"Available: {list(self._workers.keys())}"
            )
        return self._workers[domain]

    def list(self) -> list["NodeWorker"]:
        return list(self._workers.values())

    def remove(self, domain: str) -> None:
        self._workers.pop(domain, None)

    def available_domains(self) -> list[str]:
        return [d for d, w in self._workers.items() if w.is_available]

    def __contains__(self, domain: str) -> bool:
        return domain in self._workers

    def __len__(self) -> int:
        return len(self._workers)
