"""Cross-domain type adapter base class.

Extends the Phase 0 NodeWorker interface with adapter-specific
validation and conversion semantics.  Uses :class:`NodeTypeRegistry`
for domain-type schema validation of source and target data.
"""

from __future__ import annotations

import logging
from abc import abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from mascarade.node_engine.worker import ExecutionContext, NodeResult, NodeWorker

if TYPE_CHECKING:
    from mascarade.node_engine.registry import NodeTypeRegistry

logger = logging.getLogger("mascarade.node_engine.cross_domain")


@dataclass
class AdapterMapping:
    """Declares a single type conversion supported by an adapter.

    Example:
        mapping = AdapterMapping(
            source_domain="ai",
            source_type="LLMResponse",
            target_domain="cad",
            target_type="CADDocument",
            lossy=True,
            requires_config=True
        )
    """

    source_domain: str
    source_type: str
    target_domain: str
    target_type: str
    lossy: bool = False  # True if conversion discards information
    requires_config: bool = False  # True if user must provide mapping config

    def mapping_id(self) -> str:
        """Return the unique identifier for this mapping."""
        return f"{self.source_domain}.{self.source_type}->{self.target_domain}.{self.target_type}"


class CrossDomainAdapter(NodeWorker):
    """Base class for all cross-domain type adapters.

    Subclasses declare which domain type conversions they support
    and implement the conversion logic. The adapter validates that
    source data conforms to the source domain schema before conversion
    and validates the output against the target domain schema after.

    When a :class:`NodeTypeRegistry` is provided, validation uses the
    registered :class:`DomainType` JSON-schema definitions. Otherwise
    only a ``None`` check is performed.

    Example:
        class AIToCADAdapter(CrossDomainAdapter):
            def supported_mappings(self) -> list[AdapterMapping]:
                return [
                    AdapterMapping("ai", "LLMResponse", "cad", "CADDocument", lossy=True),
                    AdapterMapping("ai", "LLMResponse", "cad", "GCode", lossy=True),
                ]

            async def convert(self, source_data, mapping, config):
                # Extract structured design parameters from LLM output
                if mapping.target_type == "CADDocument":
                    return self._extract_cad_params(source_data, config)
                elif mapping.target_type == "GCode":
                    return self._extract_gcode(source_data)
    """

    def __init__(self, registry: NodeTypeRegistry | None = None) -> None:
        self._registry = registry

    @abstractmethod
    def supported_mappings(self) -> list[AdapterMapping]:
        """Return all type conversions this adapter supports.

        Returns:
            List of AdapterMapping instances declaring source→target conversions
        """
        ...

    @abstractmethod
    async def convert(
        self,
        source_data: Any,
        mapping: AdapterMapping,
        config: dict[str, Any] | None = None,
    ) -> Any:
        """Convert source domain data to target domain data.

        Args:
            source_data: Data from the source domain
            mapping: The AdapterMapping defining the conversion
            config: Optional configuration for the conversion

        Returns:
            Converted data conforming to target domain type

        Raises:
            ValueError: If source data is invalid or conversion fails
            KeyError: If required config is missing
        """
        ...

    async def execute(self, context: ExecutionContext) -> NodeResult:
        """Standard NodeWorker execute — delegates to convert().

        Args:
            context: ExecutionContext with inputs["source"] and config

        Returns:
            NodeResult with outputs["result"] containing converted data

        Raises:
            ValueError: If mapping cannot be resolved or validation fails
        """
        source = context.inputs.get("source")
        if source is None:
            raise ValueError("Missing required input 'source'")

        mapping_id = context.config.get("mapping")
        config = context.config.get("adapter_config", {})

        mapping = self._resolve_mapping(mapping_id)

        # Validate required config
        if mapping.requires_config and not config:
            raise ValueError(
                f"Mapping {mapping.mapping_id()} requires adapter_config but none provided"
            )

        self._validate_source(source, mapping)
        result = await self.convert(source, mapping, config)
        self._validate_target(result, mapping)

        logger.info(
            "cross_domain_conversion",
            extra={
                "source_domain": mapping.source_domain,
                "source_type": mapping.source_type,
                "target_domain": mapping.target_domain,
                "target_type": mapping.target_type,
                "lossy": mapping.lossy,
            },
        )

        return NodeResult(outputs={"result": result})

    def _resolve_mapping(self, mapping_id: str | None) -> AdapterMapping:
        """Resolve mapping from ID or default to single mapping.

        Args:
            mapping_id: Optional mapping ID (e.g., "ai.LLMResponse->cad.CADDocument")

        Returns:
            The resolved AdapterMapping

        Raises:
            ValueError: If mapping cannot be resolved
        """
        mappings = self.supported_mappings()

        if mapping_id:
            for m in mappings:
                if m.mapping_id() == mapping_id:
                    return m
            raise ValueError(
                f"Mapping '{mapping_id}' not found. "
                f"Available: {[m.mapping_id() for m in mappings]}"
            )

        if len(mappings) == 1:
            return mappings[0]

        raise ValueError(
            f"Adapter has {len(mappings)} mappings — specify 'mapping' in config. "
            f"Available: {[m.mapping_id() for m in mappings]}"
        )

    def _validate_source(self, data: Any, mapping: AdapterMapping) -> None:
        """Validate source data against the source domain type schema.

        Args:
            data: Source data to validate
            mapping: The mapping defining expected source type

        Raises:
            ValueError: If data is None or fails schema validation.
        """
        if data is None:
            raise ValueError(
                f"Source data is None for {mapping.source_domain}.{mapping.source_type}"
            )
        self._validate_domain_type(
            data, mapping.source_domain, mapping.source_type, direction="source"
        )

    def _validate_target(self, data: Any, mapping: AdapterMapping) -> None:
        """Validate converted data against the target domain type schema.

        Args:
            data: Converted data to validate
            mapping: The mapping defining expected target type

        Raises:
            ValueError: If data is None or fails schema validation.
        """
        if data is None:
            raise ValueError(
                f"Converted data is None for {mapping.target_domain}.{mapping.target_type}"
            )
        self._validate_domain_type(
            data, mapping.target_domain, mapping.target_type, direction="target"
        )

    # ------------------------------------------------------------------
    # Registry integration
    # ------------------------------------------------------------------

    def _validate_domain_type(
        self,
        data: Any,
        domain: str,
        type_name: str,
        *,
        direction: str,
    ) -> None:
        """Validate *data* against a DomainType looked up in the registry.

        If no registry is set, or the qualified name is not registered,
        validation is skipped with a debug-level log.

        Args:
            data: The payload to validate (must be a dict for schema checks).
            domain: Domain identifier (e.g. ``"ai"``).
            type_name: Type name within the domain (e.g. ``"LLMResponse"``).
            direction: ``"source"`` or ``"target"`` — used in error messages.

        Raises:
            ValueError: If the data fails schema validation.
        """
        if self._registry is None:
            return

        qualified = f"{domain}.{type_name}"

        if qualified not in self._registry:
            logger.debug(
                "Domain type %s not found in registry — skipping %s validation",
                qualified,
                direction,
            )
            return

        from mascarade.node_engine.types import DomainType

        entry = self._registry.get(qualified)
        if not isinstance(entry, DomainType):
            # It's a NodeType, not a DomainType — nothing to schema-validate.
            return

        if not isinstance(data, dict):
            # DomainType.validate_schema expects a dict; non-dict payloads
            # cannot be validated against a JSON schema.
            logger.debug(
                "Skipping schema validation for %s %s: data is not a dict",
                direction,
                qualified,
            )
            return

        valid, error = entry.validate_schema(data)
        if not valid:
            raise ValueError(f"Schema validation failed for {direction} type {qualified}: {error}")
