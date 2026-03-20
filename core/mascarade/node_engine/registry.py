"""Registry for domain type registration and discovery."""

from __future__ import annotations

import json
import logging
import os
import tempfile
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
        return [dt for dt in self._types.values() if dt.domain == domain]

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
        """Check if a domain type is registered.

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
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
            raise

    def load(self) -> None:
        """Load custom domain types from JSON file.

        Builtin types are not loaded from storage. Invalid entries are skipped
        with a warning.
        """
        if self._storage_path is None or not self._storage_path.exists():
            return

        try:
            raw = json.loads(self._storage_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            logger.error(
                "Failed to load domain types from %s: %s",
                self._storage_path,
                exc
            )
            return

        for data in raw:
            try:
                domain_type = DomainType(**data)
                self.register(domain_type)
            except (KeyError, TypeError, ValueError) as exc:
                logger.warning("Skipping invalid domain type entry: %s", exc)
