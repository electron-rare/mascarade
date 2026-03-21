"""Registry for domain type registration, node type management, and worker discovery."""

from __future__ import annotations

import json
import logging
import os
import tempfile
from pathlib import Path
from typing import Any

from mascarade.node_engine.types import DomainType, NodeType

logger = logging.getLogger("mascarade.node_engine")

DEFAULT_STORAGE_PATH = Path("data/domain_types.json")


class NodeTypeRegistry:
    """Centralized registry for managing domain types and node types.

    Stores and retrieves domain-specific type definitions (DomainType instances)
    and node type definitions (NodeType instances).
    """

    def __init__(self, storage_path: Path | None = DEFAULT_STORAGE_PATH) -> None:
        """Initialize the registry.

        Args:
            storage_path: Path to JSON file for persistence. If None, persistence is disabled.
        """
        self._types: dict[str, DomainType] = {}
        self._node_types: dict[str, NodeType] = {}
        self._builtin_names: set[str] = set()
        self._storage_path = storage_path

    def register(self, item: DomainType | NodeType, *, builtin: bool = False) -> None:
        """Register a domain type or node type.

        Args:
            item: The DomainType or NodeType instance to register
            builtin: Whether this is a builtin type (not persisted)
        """
        if isinstance(item, NodeType):
            self._node_types[item.id] = item
            if builtin:
                self._builtin_names.add(item.id)
        elif isinstance(item, DomainType):
            qualified_name = item.qualified_name
            if qualified_name in self._types and qualified_name not in self._builtin_names:
                logger.warning(
                    "Overwriting existing domain type: %s", qualified_name
                )
            self._types[qualified_name] = item
            if builtin:
                self._builtin_names.add(qualified_name)
        else:
            raise TypeError(f"Cannot register {type(item).__name__}")

    def get(self, qualified_name: str) -> DomainType | NodeType:
        """Get a domain type or node type by its qualified name.

        Args:
            qualified_name: The qualified type name (e.g., "ai.LLMResponse" or "math.add")

        Returns:
            The DomainType or NodeType instance

        Raises:
            KeyError: If the type is not found
        """
        if qualified_name in self._node_types:
            return self._node_types[qualified_name]
        if qualified_name in self._types:
            return self._types[qualified_name]
        raise KeyError(
            f"Type '{qualified_name}' not found. "
            f"Available: {list(self._types.keys()) + list(self._node_types.keys())}"
        )

    def get_by_domain(self, domain: str) -> list[DomainType]:
        """Get all domain types for a specific domain."""
        return [dt for dt in self._types.values() if dt.domain == domain]

    def list(self, *, domain: str | None = None) -> list[DomainType | NodeType]:
        """List all registered types, optionally filtered by domain.

        Args:
            domain: Optional domain filter

        Returns:
            List of all registered types
        """
        all_items: list[DomainType | NodeType] = list(self._types.values()) + list(self._node_types.values())
        if domain:
            return [item for item in all_items if getattr(item, 'domain', '') == domain]
        return all_items

    def domains(self) -> list[str]:
        """Return sorted list of unique domains."""
        domain_set: set[str] = set()
        for dt in self._types.values():
            domain_set.add(dt.domain)
        for nt in self._node_types.values():
            domain_set.add(nt.domain)
        return sorted(domain_set)

    def remove(self, qualified_name: str) -> None:
        """Remove a type from the registry."""
        self._types.pop(qualified_name, None)
        self._node_types.pop(qualified_name, None)
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

    def register_type(self, item: DomainType | NodeType, *, builtin: bool = False) -> None:
        """Alias for register() for backward compatibility."""
        self.register(item, builtin=builtin)

    def register_worker(self, worker: Any) -> None:
        """Register a worker and set its registry reference.

        Args:
            worker: A NodeWorker instance (must have .domain attribute)
        """
        worker.registry = self
        if not hasattr(self, "_workers"):
            self._workers: dict[str, Any] = {}
        domain = worker.domain
        if domain in self._workers:
            logger.warning("Replacing worker for domain '%s'", domain)
        self._workers[domain] = worker

    def has_worker(self, domain: str) -> bool:
        """Check if a worker is registered for a domain."""
        return domain in getattr(self, "_workers", {})

    def get_worker(self, domain: str) -> Any:
        """Get the worker for a domain."""
        workers = getattr(self, "_workers", {})
        if domain not in workers:
            raise KeyError(f"No worker registered for domain '{domain}'")
        return workers[domain]

    def remove_worker(self, domain: str) -> None:
        """Remove the worker for a domain."""
        workers = getattr(self, "_workers", {})
        worker = workers.pop(domain, None)
        if worker is not None:
            worker.registry = None

    async def initialize_workers(self) -> None:
        """Initialize all registered workers."""
        for worker in getattr(self, "_workers", {}).values():
            await worker.initialize()

    async def shutdown_workers(self) -> None:
        """Shutdown all registered workers."""
        for worker in getattr(self, "_workers", {}).values():
            await worker.shutdown()

    # --- Type queries ---

    def list_types(self, *, domain: str | None = None) -> list[DomainType]:
        """List registered domain types, optionally filtered by domain."""
        types = list(self._types.values())
        if domain:
            types = [dt for dt in types if dt.domain == domain]
        return types

    def get_type(self, qualified_name: str) -> DomainType:
        """Get a domain type by its qualified name."""
        if qualified_name in self._types:
            return self._types[qualified_name]
        raise KeyError(f"Type '{qualified_name}' not found")

    def is_builtin_type(self, qualified_name: str) -> bool:
        """Check if a type is a builtin type."""
        return qualified_name in self._builtin_names

    # --- Persistence ---

    def save(self) -> None:
        """Save custom types to JSON file.

        Builtin types are not persisted. Uses atomic write to prevent corruption.
        """
        if self._storage_path is None:
            return

        self._storage_path.parent.mkdir(parents=True, exist_ok=True)

        # Collect non-builtin items
        types_data = []
        for domain_type in self._types.values():
            if domain_type.qualified_name not in self._builtin_names:
                types_data.append({"_kind": "domain", **domain_type.model_dump()})

        for node_type in self._node_types.values():
            if node_type.id not in self._builtin_names:
                types_data.append({"_kind": "node", **node_type.model_dump()})

        # Atomic write
        fd, tmp_path = tempfile.mkstemp(
            dir=str(self._storage_path.parent), suffix=".tmp"
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(types_data, f, indent=2, ensure_ascii=False)
            os.replace(tmp_path, str(self._storage_path))
        except BaseException:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
            raise

    def load(self) -> None:
        """Load custom types from JSON file."""
        if self._storage_path is None or not self._storage_path.exists():
            return

        try:
            raw = json.loads(self._storage_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            logger.error(
                "Failed to load types from %s: %s", self._storage_path, exc
            )
            return

        for data in raw:
            try:
                kind = data.pop("_kind", "domain")
                if kind == "node":
                    node_type = NodeType(**data)
                    self.register(node_type)
                else:
                    domain_type = DomainType(**data)
                    self.register(domain_type)
            except (KeyError, TypeError, ValueError) as exc:
                logger.warning("Skipping invalid type entry: %s", exc)


# Alias for code that imports NodeRegistry
NodeRegistry = NodeTypeRegistry


class WorkerRegistry:
    """Registry for domain workers.

    Each domain can have at most one registered worker.
    """

    def __init__(self) -> None:
        self._workers: dict[str, Any] = {}

    def register(self, worker: Any) -> None:
        """Register a worker for its domain.

        Args:
            worker: A NodeWorker instance (must have .domain attribute)
        """
        domain = worker.domain
        if domain in self._workers:
            logger.warning("Replacing worker for domain '%s'", domain)
        self._workers[domain] = worker

    def get(self, domain: str) -> Any:
        """Get the worker for a domain.

        Args:
            domain: The domain identifier

        Returns:
            The registered worker

        Raises:
            KeyError: If no worker is registered for the domain
        """
        if domain not in self._workers:
            raise KeyError(
                f"No worker registered for domain '{domain}'. "
                f"Available: {list(self._workers.keys())}"
            )
        return self._workers[domain]

    def list(self) -> list[Any]:
        """List all registered workers."""
        return list(self._workers.values())

    def remove(self, domain: str) -> None:
        """Remove the worker for a domain."""
        self._workers.pop(domain, None)

    def available_domains(self) -> list[str]:
        """Return domains with available workers."""
        return [
            domain
            for domain, worker in self._workers.items()
            if getattr(worker, "is_available", True)
        ]

    def __contains__(self, domain: str) -> bool:
        """Check if a worker is registered for a domain."""
        return domain in self._workers

    def __len__(self) -> int:
        """Get the number of registered workers."""
        return len(self._workers)
