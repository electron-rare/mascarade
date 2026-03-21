"""Core type system for domain types and port validation."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger("mascarade.node_engine.types")


class PortDirection(str, Enum):
    """Direction of data flow for a port."""

    INPUT = "input"
    OUTPUT = "output"


@dataclass
class DomainType:
    """
    Defines a domain-specific type for node ports.

    Domain types are used to define structured data types specific to a domain
    (e.g., electronics, 3D modeling, audio processing). Each type has a JSON
    schema that validates the data structure.

    Examples:
        >>> netlist_type = DomainType(
        ...     domain="electronics",
        ...     name="Netlist",
        ...     schema={
        ...         "type": "object",
        ...         "properties": {
        ...             "format": {"type": "string", "enum": ["spice", "kicad"]},
        ...             "content": {"type": "string"},
        ...         },
        ...         "required": ["format", "content"],
        ...     },
        ... )

    Attributes:
        domain: Domain namespace (e.g., "electronics", "3d", "audio")
        name: Type name within the domain (e.g., "Netlist", "Waveform")
        schema: JSON Schema definition for validation
        description: Human-readable type description
        metadata: Additional metadata about the type
    """

    domain: str
    name: str
    schema: dict[str, Any]
    description: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def full_name(self) -> str:
        """Get the fully qualified type name (domain.name)."""
        return f"{self.domain}.{self.name}"

    def validate_schema(self, data: Any) -> tuple[bool, str | None]:
        """
        Validate data against this type's schema.

        Args:
            data: Data to validate

        Returns:
            Tuple of (is_valid, error_message). error_message is None if valid.

        Note:
            This is a basic structural validator. For full JSON Schema validation,
            use a library like jsonschema in production.
        """
        # Basic type checking - in production, use jsonschema library
        schema_type = self.schema.get("type")

        if schema_type == "object":
            if not isinstance(data, dict):
                return False, f"Expected object, got {type(data).__name__}"

            # Check required fields
            required = self.schema.get("required", [])
            for field_name in required:
                if field_name not in data:
                    return False, f"Missing required field: {field_name}"

            # Check properties
            properties = self.schema.get("properties", {})
            for key, value in data.items():
                if key not in properties:
                    continue

                prop_schema = properties[key]
                prop_type = prop_schema.get("type")

                # Handle union types (e.g., ["string", "null"])
                if isinstance(prop_type, list):
                    type_match = False
                    for allowed_type in prop_type:
                        if allowed_type == "null" and value is None:
                            type_match = True
                            break
                        if allowed_type == "string" and isinstance(value, str):
                            type_match = True
                            break
                        if allowed_type == "integer" and isinstance(value, int):
                            type_match = True
                            break
                        if allowed_type == "number" and isinstance(value, (int, float)):
                            type_match = True
                            break
                        if allowed_type == "boolean" and isinstance(value, bool):
                            type_match = True
                            break
                        if allowed_type == "array" and isinstance(value, list):
                            type_match = True
                            break
                        if allowed_type == "object" and isinstance(value, dict):
                            type_match = True
                            break

                    if not type_match:
                        return False, f"Field '{key}' does not match allowed types: {prop_type}"

                # Handle enum constraints
                if "enum" in prop_schema and value not in prop_schema["enum"]:
                    return False, f"Field '{key}' value '{value}' not in allowed enum: {prop_schema['enum']}"

        elif schema_type == "string" and not isinstance(data, str):
            return False, f"Expected string, got {type(data).__name__}"
        elif schema_type == "integer" and not isinstance(data, int):
            return False, f"Expected integer, got {type(data).__name__}"
        elif schema_type == "number" and not isinstance(data, (int, float)):
            return False, f"Expected number, got {type(data).__name__}"
        elif schema_type == "boolean" and not isinstance(data, bool):
            return False, f"Expected boolean, got {type(data).__name__}"
        elif schema_type == "array" and not isinstance(data, list):
            return False, f"Expected array, got {type(data).__name__}"

        return True, None

    def __repr__(self) -> str:
        """Return a readable representation of the domain type."""
        return f"DomainType(domain='{self.domain}', name='{self.name}')"


@dataclass
class PortType:
    """
    Defines a port on a node (input or output).

    Ports are the interface points for data flow between nodes in a graph.
    Each port has a name, direction, and type definition that determines what
    data can flow through it.

    Examples:
        >>> from mascarade.node_engine.types import PortType, PortDirection
        >>> netlist_port = PortType(
        ...     name="netlist",
        ...     direction=PortDirection.OUTPUT,
        ...     port_type="electronics.Netlist",
        ...     description="Generated SPICE netlist",
        ... )
        >>> string_port = PortType(
        ...     name="circuit_description",
        ...     direction=PortDirection.INPUT,
        ...     port_type="string",
        ...     optional=False,
        ... )

    Attributes:
        name: Port identifier (unique within a node)
        direction: INPUT or OUTPUT
        port_type: Type identifier (built-in: "string", "integer", "boolean", "json", "binary"
                   or domain-specific: "domain.TypeName")
        description: Human-readable description
        optional: Whether this port is optional (default: False for inputs, True for outputs)
        default_value: Default value if port is optional and not connected
        metadata: Additional metadata about the port
    """

    name: str
    direction: PortDirection
    port_type: str
    description: str = ""
    optional: bool = False
    default_value: Any = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def is_compatible_with(self, other: PortType) -> bool:
        """
        Check if this port is compatible with another port for connection.

        Args:
            other: Another port to check compatibility with

        Returns:
            True if ports can be connected, False otherwise

        Rules:
            - One must be INPUT, the other OUTPUT
            - Port types must match exactly (no automatic conversion)
            - Optional status doesn't affect compatibility
        """
        # Must be opposite directions
        if self.direction == other.direction:
            return False

        # Types must match exactly
        if self.port_type != other.port_type:
            return False

        return True

    def validate_value(self, value: Any, domain_types: dict[str, DomainType] | None = None) -> tuple[bool, str | None]:
        """
        Validate a value against this port's type.

        Args:
            value: Value to validate
            domain_types: Registry of domain types for validation (optional)

        Returns:
            Tuple of (is_valid, error_message). error_message is None if valid.
        """
        # Handle None for optional ports
        if value is None:
            if self.optional:
                return True, None
            return False, f"Port '{self.name}' is required but received None"

        # Built-in types
        if self.port_type == "string":
            if not isinstance(value, str):
                return False, f"Expected string, got {type(value).__name__}"
        elif self.port_type == "integer":
            if not isinstance(value, int) or isinstance(value, bool):  # bool is subclass of int
                return False, f"Expected integer, got {type(value).__name__}"
        elif self.port_type == "number":
            if not isinstance(value, (int, float)) or isinstance(value, bool):
                return False, f"Expected number, got {type(value).__name__}"
        elif self.port_type == "boolean":
            if not isinstance(value, bool):
                return False, f"Expected boolean, got {type(value).__name__}"
        elif self.port_type == "json":
            if not isinstance(value, (dict, list)):
                return False, f"Expected JSON (dict or list), got {type(value).__name__}"
        elif self.port_type == "binary":
            if not isinstance(value, (bytes, bytearray)):
                return False, f"Expected binary data, got {type(value).__name__}"
        elif self.port_type.startswith("array<"):
            # Array types like "array<string>"
            if not isinstance(value, list):
                return False, f"Expected array, got {type(value).__name__}"
            # TODO: Validate inner type
        elif self.port_type.startswith("optional<"):
            # Optional wrapper type like "optional<string>"
            inner_type = self.port_type[9:-1]  # Extract inner type
            # TODO: Validate inner type
        elif "." in self.port_type:
            # Domain-specific type like "electronics.Netlist"
            if domain_types:
                domain_type = domain_types.get(self.port_type)
                if domain_type:
                    return domain_type.validate_schema(value)
                else:
                    logger.warning(f"Domain type '{self.port_type}' not found in registry")
            # If no domain_types registry provided, assume valid
        else:
            # Unknown type - log warning but allow
            logger.warning(f"Unknown port type '{self.port_type}' - skipping validation")

        return True, None

    def __repr__(self) -> str:
        """Return a readable representation of the port."""
        optional_marker = " (optional)" if self.optional else ""
        return f"PortType(name='{self.name}', direction={self.direction.value}, type='{self.port_type}'{optional_marker})"
