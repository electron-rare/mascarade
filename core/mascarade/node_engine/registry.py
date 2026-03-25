"""Node type definition and registry.

Modeled on AgentRegistry (core/mascarade/agents/registry.py)
with the same patterns: centralized register/get/list/remove,
builtin vs. dynamic distinction, metrics tracking, atomic JSON persistence.
"""
"""Registry for domain type registration and discovery."""

from __future__ import annotations

import json
import logging
import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from mascarade.node_engine.worker import NodeWorker

logger = logging.getLogger("mascarade.node_engine.registry")


@dataclass
class NodeType:
    """Definition of a node type in the registry."""

    id: str                               # Unique identifier (e.g., "ai.llm-inference")
    domain: str                           # Domain this node belongs to
    label: str                            # Human-readable label
    description: str                      # What this node does
    version: str = "1.0.0"               # Semantic version
    inputs: list[dict[str, Any]] = field(default_factory=list)
    outputs: list[dict[str, Any]] = field(default_factory=list)
    config_schema: dict[str, Any] = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)
    deprecated: bool = False
    deprecated_by: str | None = None


DEFAULT_REGISTRY_PATH = Path("data/node_types.json")


class NodeTypeRegistry:
    """
    Centralized registry for node type definitions.

    Follows AgentRegistry patterns:
    - register/get/list/remove semantics
    - builtin vs. dynamic node type distinction
    - JSON persistence with atomic writes (temp + rename)
    """

    def __init__(self, storage_path: Path | None = DEFAULT_REGISTRY_PATH) -> None:
        self._types: dict[str, NodeType] = {}
        self._builtin_ids: set[str] = set()
        self._storage_path = storage_path

    def register(self, node_type: NodeType, *, builtin: bool = False) -> None:
        """Register a node type. Raises ValueError if ID already exists."""
        if node_type.id in self._types and not node_type.deprecated:
            raise ValueError(f"Node type '{node_type.id}' already registered")
        self._types[node_type.id] = node_type
        if builtin:
            self._builtin_ids.add(node_type.id)

    def get(self, type_id: str) -> NodeType:
        """Get a node type by ID. Raises KeyError if not found."""
        if type_id not in self._types:
            raise KeyError(
                f"Node type '{type_id}' not found. Available: {list(self._types.keys())}"
            )
        return self._types[type_id]

    def list(self, domain: str | None = None) -> list[NodeType]:
        """List all node types, optionally filtered by domain."""
        types = list(self._types.values())
        if domain:
            types = [t for t in types if t.domain == domain]
        return types

    def remove(self, type_id: str) -> None:
        """Remove a node type from the registry."""
        self._types.pop(type_id, None)
        self._builtin_ids.discard(type_id)

    def domains(self) -> list[str]:
        """List all registered domains."""
        return sorted(set(t.domain for t in self._types.values()))

    def __contains__(self, type_id: str) -> bool:
        return type_id in self._types

    def __len__(self) -> int:
        return len(self._types)

    def is_builtin(self, type_id: str) -> bool:
        return type_id in self._builtin_ids

    # --- Persistence (follows AgentRegistry.save/load pattern) ---

    def save(self) -> None:
        """Save dynamic node types to JSON with atomic write."""
from pathlib import Path

from mascarade.node_engine.types import DomainType

logger = logging.getLogger("mascarade.node_engine")

DEFAULT_STORAGE_PATH = Path("data/domain_types.json")


class NodeTypeRegistry:
    """Centralized registry for managing domain types.

    Stores and retrieves domain-specific type definitions (DomainType instances)
    that extend the base type system with domain-specific structures.
    """

    def __init__(self, storage_path: Path | None = DEFAULT_STORAGE_PATH) -> None:
        """Initialize the registry.

        Args:
            storage_path: Path to JSON file for persistence. If None, persistence is disabled.
        """
        self._types: dict[str, DomainType] = {}
        self._builtin_names: set[str] = set()
        self._storage_path = storage_path

    def register(self, domain_type: DomainType, *, builtin: bool = False) -> None:
        """Register a domain type.

        Args:
            domain_type: The DomainType instance to register
            builtin: Whether this is a builtin type (not persisted)
        """
        if isinstance(item, NodeType):
            self._node_types[item.id] = item
            if builtin:
                self._builtin_names.add(item.id)
        elif isinstance(item, DomainType):
            qualified_name = item.qualified_name
            if (
                qualified_name in self._types
                and qualified_name not in self._builtin_names
            ):
                logger.warning("Overwriting existing domain type: %s", qualified_name)
            self._types[qualified_name] = item
            if builtin:
                self._builtin_names.add(qualified_name)
        else:
            raise TypeError(f"Cannot register {type(item).__name__}")

        Raises:
            ValueError: If a type with the same qualified name is already registered
        """
        qualified_name = domain_type.qualified_name
        if qualified_name in self._types and qualified_name not in self._builtin_names:
            logger.warning(
                "Overwriting existing domain type: %s", qualified_name
            )
        self._types[qualified_name] = domain_type
        if builtin:
            self._builtin_names.add(qualified_name)

    def get(self, qualified_name: str) -> DomainType:
        """Get a domain type by its qualified name (domain.name).

        Args:
            qualified_name: The qualified type name (e.g., "ai.LLMResponse")

        Returns:
            The DomainType instance

        Raises:
            KeyError: If the type is not found
        """
        if qualified_name not in self._types:
            raise KeyError(
                f"Domain type '{qualified_name}' not found. "
                f"Available: {list(self._types.keys())}"
            )
        return self._types[qualified_name]

    def get_by_domain(self, domain: str) -> list[DomainType]:
        """Get all domain types for a specific domain.

        Args:
            domain: The domain identifier (e.g., "ai", "cad")

        Returns:
            List of DomainType instances for the specified domain
        """
        all_items: list[DomainType | NodeType] = list(self._types.values()) + list(
            self._node_types.values()
        )
        if domain:
            return [item for item in all_items if getattr(item, "domain", "") == domain]
        return all_items

    def list(self) -> list[DomainType]:
        """List all registered domain types.

        Returns:
            List of all DomainType instances
        """
        return list(self._types.values())

    def remove(self, qualified_name: str) -> None:
        """Remove a domain type from the registry.

        Args:
            qualified_name: The qualified type name to remove
        """
        self._types.pop(qualified_name, None)
        self._builtin_names.discard(qualified_name)

    def __contains__(self, qualified_name: str) -> bool:
        """Check if a type is registered."""
        return qualified_name in self._types or qualified_name in self._node_types

    def __len__(self) -> int:
        """Get the number of registered types."""
        return len(self._types) + len(self._node_types)

    def __bool__(self) -> bool:
        """Registry is always truthy (even when empty)."""
        return True

    def is_builtin(self, qualified_name: str) -> bool:
        """Check if a type is builtin."""
        return qualified_name in self._builtin_names

    # --- Worker management ---

    def register_type(
        self, item: DomainType | NodeType, *, builtin: bool = False
    ) -> None:
        """Alias for register() for backward compatibility."""
        self.register(item, builtin=builtin)

    def register_worker(self, worker: Any) -> None:
        """Register a worker and set its registry reference.

        Args:
            qualified_name: The qualified type name to check

        Returns:
            True if the type is registered
        """
        return qualified_name in self._types

    def __len__(self) -> int:
        """Get the number of registered domain types.

        Returns:
            Number of registered types
        """
        return len(self._types)

    def is_builtin(self, qualified_name: str) -> bool:
        """Check if a domain type is builtin.

        Args:
            qualified_name: The qualified type name to check

        Returns:
            True if the type is builtin
        """
        return qualified_name in self._builtin_names

    # --- Persistence ---

    def save(self) -> None:
        """Save custom domain types to JSON file.

        Builtin types are not persisted. Uses atomic write to prevent corruption.
        """
        if self._storage_path is None:
            return

        self._storage_path.parent.mkdir(parents=True, exist_ok=True)
        types_data = []
        for nt in self._types.values():
            if nt.id in self._builtin_ids:
                continue
            types_data.append({
                "id": nt.id,
                "domain": nt.domain,
                "label": nt.label,
                "description": nt.description,
                "version": nt.version,
                "inputs": nt.inputs,
                "outputs": nt.outputs,
                "config_schema": nt.config_schema,
                "tags": nt.tags,
                "deprecated": nt.deprecated,
                "deprecated_by": nt.deprecated_by,
            })


        # Only save non-builtin types
        types_data = []
        for domain_type in self._types.values():
            if domain_type.qualified_name not in self._builtin_names:
                types_data.append(domain_type.model_dump())

        # Atomic write: write to temp file, then rename
        fd, tmp_path = tempfile.mkstemp(
            dir=str(self._storage_path.parent), suffix=".tmp"
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(types_data, f, indent=2, ensure_ascii=False)
            os.replace(tmp_path, str(self._storage_path))
        except BaseException:
            os.unlink(tmp_path)
            raise

    def load(self) -> None:
        """Load dynamic node types from JSON."""
        if self._storage_path is None or not self._storage_path.exists():
            return
        try:
            raw = json.loads(self._storage_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            logger.error("Failed to load types from %s: %s", self._storage_path, exc)
            return
        for data in raw:
            try:
                nt = NodeType(**data)
                self.register(nt)
            except (KeyError, TypeError, ValueError) as exc:
                logger.warning("Skipping invalid node type entry: %s", exc)


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
        """Remove a worker from the registry."""
        self._workers.pop(domain, None)

    def available_domains(self) -> list[str]:
        return [d for d, w in self._workers.items() if w.is_available]

    def __contains__(self, domain: str) -> bool:
        return domain in self._workers

    def __len__(self) -> int:
        return len(self._workers)
