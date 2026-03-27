"""Cross-domain adapter registration.

Provides utilities to instantiate and register all concrete adapters
with a runtime adapter registry keyed by their supported mapping IDs.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from mascarade.node_engine.cross_domain.adapters import ALL_ADAPTERS

if TYPE_CHECKING:
    from mascarade.node_engine.cross_domain.adapter import (
        AdapterMapping,
        CrossDomainAdapter,
    )
    from mascarade.node_engine.registry import NodeTypeRegistry

logger = logging.getLogger("mascarade.node_engine.cross_domain.register")


class AdapterRegistry:
    """Runtime registry that maps ``mapping_id`` strings to adapter instances.

    Usage::

        registry = AdapterRegistry()
        register_all_adapters(registry)

        adapter, mapping = registry.lookup("ai.LLMResponse->cad.CADDocument")
        result = await adapter.convert(source_data, mapping, config)
    """

    def __init__(self) -> None:
        self._adapters: dict[str, tuple[CrossDomainAdapter, AdapterMapping]] = {}

    def register(self, adapter: CrossDomainAdapter) -> None:
        """Register all mappings declared by *adapter*.

        Raises:
            ValueError: If a mapping ID is already registered by a different
                adapter class (duplicate registrations by the same class are
                silently ignored, enabling idempotent startup).
        """
        for mapping in adapter.supported_mappings():
            mid = mapping.mapping_id()
            existing = self._adapters.get(mid)
            if existing is not None and type(existing[0]) is not type(adapter):
                raise ValueError(
                    f"Mapping '{mid}' is already registered by "
                    f"{type(existing[0]).__name__}; cannot register "
                    f"{type(adapter).__name__}"
                )
            self._adapters[mid] = (adapter, mapping)
            logger.debug("Registered adapter mapping: %s", mid)

    def lookup(
        self, mapping_id: str
    ) -> tuple[CrossDomainAdapter, AdapterMapping]:
        """Return the (adapter, mapping) pair for a given mapping ID.

        Raises:
            KeyError: If *mapping_id* is not registered.
        """
        try:
            return self._adapters[mapping_id]
        except KeyError:
            available = sorted(self._adapters.keys())
            raise KeyError(
                f"No adapter registered for '{mapping_id}'. "
                f"Available mappings: {available}"
            ) from None

    def list_mappings(self) -> list[str]:
        """Return all registered mapping IDs, sorted alphabetically."""
        return sorted(self._adapters.keys())

    def list_adapters(self) -> list[str]:
        """Return unique adapter class names currently registered."""
        seen: dict[str, None] = {}
        for adapter, _ in self._adapters.values():
            name = type(adapter).__name__
            if name not in seen:
                seen[name] = None
        return list(seen.keys())

    def __contains__(self, mapping_id: str) -> bool:
        return mapping_id in self._adapters

    def __len__(self) -> int:
        return len(self._adapters)


def register_all_adapters(
    adapter_registry: AdapterRegistry,
    type_registry: NodeTypeRegistry | None = None,
) -> AdapterRegistry:
    """Instantiate and register every concrete adapter from :mod:`adapters`.

    Args:
        adapter_registry: The :class:`AdapterRegistry` to populate.
        type_registry: Optional :class:`NodeTypeRegistry` for schema
            validation inside each adapter.

    Returns:
        The same *adapter_registry*, for chaining convenience.
    """
    for cls in ALL_ADAPTERS:
        adapter = cls(registry=type_registry)
        adapter_registry.register(adapter)
        logger.info(
            "Registered %s (%d mappings)",
            cls.__name__,
            len(adapter.supported_mappings()),
        )

    logger.info(
        "Cross-domain adapter registration complete: %d mappings from %d adapters",
        len(adapter_registry),
        len(adapter_registry.list_adapters()),
    )
    return adapter_registry
