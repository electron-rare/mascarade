"""Node type and worker registries for the Universal Node Engine.

Provides two registries:
- NodeTypeRegistry: manages NodeType and DomainType definitions with JSON persistence
- WorkerRegistry: manages domain workers (one per domain)

Thread-safe. Persistence uses atomic writes (tempfile + rename) to prevent corruption.
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
import threading
from pathlib import Path
from typing import TYPE_CHECKING, Any

from mascarade.node_engine.types import DomainType, NodeType

if TYPE_CHECKING:
    from mascarade.node_engine.worker import NodeWorker

logger = logging.getLogger("mascarade.node_engine.registry")

DEFAULT_STORAGE_PATH = Path("data/node_types.json")


class NodeTypeRegistry:
    """Centralized registry for NodeType and DomainType definitions.

    Supports both node types (used by the graph executor) and domain types
    (domain-specific data schemas). Both share the same namespace keyed by
    their qualified ID (``domain.name`` for DomainType, ``id`` for NodeType).

    Builtin types are loaded at startup and excluded from persistence.
    Custom types are saved to / loaded from a JSON file using atomic writes.
    All public methods are thread-safe.
    """

    def __init__(self, storage_path: Path | None = DEFAULT_STORAGE_PATH) -> None:
        self._node_types: dict[str, NodeType] = {}
        self._domain_types: dict[str, DomainType] = {}
        self._builtin_ids: set[str] = set()
        self._storage_path = storage_path
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register(
        self,
        item: NodeType | DomainType,
        *,
        builtin: bool = False,
    ) -> None:
        """Register a NodeType or DomainType.

        Args:
            item: The type definition to register.
            builtin: If True the type is considered builtin and will not be
                persisted to disk.

        Raises:
            TypeError: If *item* is neither a NodeType nor a DomainType.
            ValueError: If a non-builtin type with the same key already exists.
        """
        with self._lock:
            if isinstance(item, NodeType):
                key = item.id
                if key in self._node_types and key not in self._builtin_ids:
                    logger.warning("Overwriting existing node type: %s", key)
                self._node_types[key] = item
            elif isinstance(item, DomainType):
                key = item.qualified_name
                if key in self._domain_types and key not in self._builtin_ids:
                    logger.warning("Overwriting existing domain type: %s", key)
                self._domain_types[key] = item
            else:
                raise TypeError(
                    f"Cannot register {type(item).__name__}; expected NodeType or DomainType"
                )
            if builtin:
                self._builtin_ids.add(key)

    # Backward-compatible alias
    register_type = register

    def unregister(self, key: str) -> None:
        """Remove a type by its key (node type ID or domain qualified name).

        Silently ignores unknown keys.
        """
        with self._lock:
            self._node_types.pop(key, None)
            self._domain_types.pop(key, None)
            self._builtin_ids.discard(key)

    # Keep ``remove`` as an alias for callers that expect it.
    remove = unregister

    # ------------------------------------------------------------------
    # Lookup
    # ------------------------------------------------------------------

    def get(self, key: str) -> NodeType | DomainType:
        """Get a type by its key.

        Args:
            key: Node type ID (e.g. ``"ai.llm-inference"``) or domain type
                qualified name (e.g. ``"ai.LLMResponse"``).

        Returns:
            The registered NodeType or DomainType.

        Raises:
            KeyError: If the key is not found.
        """
        with self._lock:
            if key in self._node_types:
                return self._node_types[key]
            if key in self._domain_types:
                return self._domain_types[key]
        available = self._all_keys()
        raise KeyError(f"Type '{key}' not found. Available: {available}")

    def list_all(self) -> list[NodeType | DomainType]:
        """Return all registered types (node types + domain types)."""
        with self._lock:
            return list(self._node_types.values()) + list(self._domain_types.values())

    # Keep ``list`` as a convenience alias (used by existing callers).
    def list(self, domain: str | None = None) -> list[NodeType | DomainType]:
        """List registered types, optionally filtered by domain.

        Args:
            domain: If provided, only return types belonging to this domain.
        """
        with self._lock:
            items: list[NodeType | DomainType] = list(self._node_types.values()) + list(
                self._domain_types.values()
            )
        if domain:
            items = [t for t in items if getattr(t, "domain", "") == domain]
        return items

    def list_by_category(self, category: str) -> list[NodeType]:
        """Return node types matching a given category."""
        with self._lock:
            return [nt for nt in self._node_types.values() if nt.category == category]

    def get_by_domain(self, domain: str) -> list[NodeType | DomainType]:
        """Return all types (node + domain) for a specific domain."""
        return self.list(domain=domain)

    def domains(self) -> list[str]:
        """Return sorted list of all registered domains."""
        with self._lock:
            ds = {getattr(t, "domain", "") for t in self._node_types.values()}
            ds |= {t.domain for t in self._domain_types.values()}
        ds.discard("")
        return sorted(ds)

    # ------------------------------------------------------------------
    # Introspection helpers
    # ------------------------------------------------------------------

    def is_builtin(self, key: str) -> bool:
        """Return True if *key* was registered as builtin."""
        with self._lock:
            return key in self._builtin_ids

    def __contains__(self, key: str) -> bool:
        with self._lock:
            return key in self._node_types or key in self._domain_types

    def __len__(self) -> int:
        with self._lock:
            return len(self._node_types) + len(self._domain_types)

    def __bool__(self) -> bool:
        """Registry is always truthy (even when empty)."""
        return True

    def _all_keys(self) -> list[str]:
        with self._lock:
            return list(self._node_types.keys()) + list(self._domain_types.keys())

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def save(self) -> None:
        """Persist custom (non-builtin) types to JSON.

        Uses atomic write: data is written to a temporary file in the same
        directory, then renamed over the target path.
        """
        if self._storage_path is None:
            return

        self._storage_path.parent.mkdir(parents=True, exist_ok=True)

        with self._lock:
            node_data = [
                nt.model_dump()
                for nt in self._node_types.values()
                if nt.id not in self._builtin_ids
            ]
            domain_data = [
                dt.model_dump()
                for dt in self._domain_types.values()
                if dt.qualified_name not in self._builtin_ids
            ]

        payload: dict[str, Any] = {
            "node_types": node_data,
            "domain_types": domain_data,
        }

        fd, tmp_path = tempfile.mkstemp(
            dir=str(self._storage_path.parent),
            suffix=".tmp",
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(payload, fh, indent=2, ensure_ascii=False)
            os.replace(tmp_path, str(self._storage_path))
            logger.debug(
                "Saved %d types to %s", len(node_data) + len(domain_data), self._storage_path
            )
        except BaseException:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
            raise

    def load(self) -> None:
        """Load custom types from JSON file.

        Builtin types already in the registry are preserved. Invalid entries
        are logged and skipped.
        """
        if self._storage_path is None or not self._storage_path.exists():
            return

        try:
            raw = json.loads(self._storage_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            logger.error("Failed to load types from %s: %s", self._storage_path, exc)
            return

        # Support both old flat list format and new dict format
        if isinstance(raw, list):
            node_entries = raw
            domain_entries: list[dict[str, Any]] = []
        else:
            node_entries = raw.get("node_types", [])
            domain_entries = raw.get("domain_types", [])

        for data in node_entries:
            try:
                self.register(NodeType(**data))
            except (TypeError, ValueError) as exc:
                logger.warning("Skipping invalid node type entry: %s", exc)

        for data in domain_entries:
            try:
                self.register(DomainType(**data))
            except (TypeError, ValueError) as exc:
                logger.warning("Skipping invalid domain type entry: %s", exc)


# Backward-compatible alias used by some test files.
NodeRegistry = NodeTypeRegistry


class WorkerRegistry:
    """Registry of domain workers. One worker per domain.

    Thread-safe. Workers are keyed by their ``domain`` attribute.
    """

    def __init__(self) -> None:
        self._workers: dict[str, NodeWorker] = {}
        self._lock = threading.Lock()

    def register(self, worker: NodeWorker) -> None:
        """Register a worker for its domain."""
        with self._lock:
            self._workers[worker.domain] = worker

    def get(self, domain: str) -> NodeWorker:
        """Get the worker for *domain*.

        Raises:
            KeyError: If no worker is registered for the domain.
        """
        with self._lock:
            if domain not in self._workers:
                raise KeyError(
                    f"No worker registered for domain '{domain}'. "
                    f"Available: {list(self._workers.keys())}"
                )
            return self._workers[domain]

    def list(self) -> list[NodeWorker]:
        """Return all registered workers."""
        with self._lock:
            return list(self._workers.values())

    def remove(self, domain: str) -> None:
        """Remove a worker from the registry."""
        with self._lock:
            self._workers.pop(domain, None)

    def available_domains(self) -> list[str]:
        """Return domains whose worker reports ``is_available``."""
        with self._lock:
            return [d for d, w in self._workers.items() if w.is_available]

    def __contains__(self, domain: str) -> bool:
        with self._lock:
            return domain in self._workers

    def __len__(self) -> int:
        with self._lock:
            return len(self._workers)
