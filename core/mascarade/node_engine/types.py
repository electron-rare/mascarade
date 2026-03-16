"""Core type system for the Universal Node Engine.

Defines port types, directions, and type validation primitives.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, Field


class PortDirection(StrEnum):
    """Direction of data flow for a node port."""

    INPUT = "input"
    OUTPUT = "output"


class PortKind(StrEnum):
    """Kind of port type - primitive, composite, or domain-specific."""

    PRIMITIVE = "primitive"
    ARRAY = "array"
    MAP = "map"
    DOMAIN = "domain"
    VOID = "void"


class PrimitiveType(StrEnum):
    """Primitive data types for node ports."""

    STRING = "string"
    INTEGER = "integer"
    NUMBER = "number"
    BOOLEAN = "boolean"
    BINARY = "binary"
    JSON = "json"


class PortType(BaseModel):
    """Type specification for a node port.

    Examples:
        # Primitive types
        PortType(kind="primitive", name="string")
        PortType(kind="primitive", name="integer")

        # Array types
        PortType(kind="array", element_type=PortType(kind="primitive", name="string"))

        # Domain-specific types
        PortType(kind="domain", domain="hardware", name="GPIOState")

        # Void type (for trigger ports)
        PortType(kind="void")
    """

    kind: PortKind
    name: str | None = None
    domain: str | None = Field(None, description="Domain name for domain-specific types")
    element_type: PortType | None = Field(
        None, description="Element type for array types"
    )
    key_type: PortType | None = Field(None, description="Key type for map types")
    value_type: PortType | None = Field(None, description="Value type for map types")
    optional: bool = Field(False, description="Whether this port is optional")

    class Config:
        """Pydantic config."""

        # Allow self-referencing for element_type
        arbitrary_types_allowed = True


# Rebuild model to handle self-referencing PortType
PortType.model_rebuild()


class NodePort(BaseModel):
    """Definition of a node port (input or output).

    Ports are the connection points for data flow between nodes.
    Each port has a name, type, direction, and optional metadata.
    """

    name: str = Field(description="Port identifier (unique within the node)")
    direction: PortDirection
    port_type: PortType
    description: str = Field("", description="Human-readable port description")
    default_value: Any = Field(None, description="Default value for optional input ports")
    required: bool = Field(True, description="Whether this input port is required")

    def is_compatible_with(self, other: NodePort) -> bool:
        """Check if this output port is compatible with another input port.

        Args:
            other: The input port to check compatibility with

        Returns:
            True if this port's output can connect to the other port's input
        """
        if self.direction == PortDirection.INPUT:
            raise ValueError("is_compatible_with() requires an OUTPUT port")
        if other.direction == PortDirection.OUTPUT:
            raise ValueError("is_compatible_with() requires an INPUT port argument")

        # Check basic type compatibility
        return self._types_compatible(self.port_type, other.port_type)

    def _types_compatible(self, source: PortType, target: PortType) -> bool:
        """Check if source type can flow into target type."""
        # Exact match
        if source.kind == target.kind and source.name == target.name:
            # For domain types, also check domain
            if source.kind == PortKind.DOMAIN:
                return source.domain == target.domain
            return True

        # Optional target can accept non-optional source
        if target.optional and not source.optional:
            return self._types_compatible(
                source,
                PortType(
                    kind=target.kind,
                    name=target.name,
                    domain=target.domain,
                    element_type=target.element_type,
                    optional=False,
                ),
            )

        # Void compatibility (void can connect to anything, as it's just a trigger)
        if source.kind == PortKind.VOID or target.kind == PortKind.VOID:
            return True

        # Array element type compatibility
        if source.kind == PortKind.ARRAY and target.kind == PortKind.ARRAY:
            if source.element_type and target.element_type:
                return self._types_compatible(source.element_type, target.element_type)

        # Map type compatibility
        if source.kind == PortKind.MAP and target.kind == PortKind.MAP:
            if source.key_type and target.key_type and source.value_type and target.value_type:
                return self._types_compatible(
                    source.key_type, target.key_type
                ) and self._types_compatible(source.value_type, target.value_type)

        # Primitive type coercion rules
        if source.kind == PortKind.PRIMITIVE and target.kind == PortKind.PRIMITIVE:
            return self._primitive_coercion_allowed(
                source.name or "", target.name or ""
            )

        # No match
        return False

    def _primitive_coercion_allowed(self, source: str, target: str) -> bool:
        """Check if primitive type coercion is allowed."""
        # Same type
        if source == target:
            return True

        # Number coercions
        if target == PrimitiveType.NUMBER:
            return source in (PrimitiveType.INTEGER, PrimitiveType.NUMBER)
        if target == PrimitiveType.STRING:
            # Any primitive can coerce to string
            return True

        # Integer to boolean (0/1 convention)
        if target == PrimitiveType.BOOLEAN and source == PrimitiveType.INTEGER:
            return True

        return False


# Convenience constructors for common port types


def primitive_port(
    name: str,
    direction: PortDirection,
    primitive_type: PrimitiveType,
    description: str = "",
    optional: bool = False,
    default_value: Any = None,
) -> NodePort:
    """Create a primitive-typed port."""
    return NodePort(
        name=name,
        direction=direction,
        port_type=PortType(kind=PortKind.PRIMITIVE, name=primitive_type, optional=optional),
        description=description,
        default_value=default_value,
        required=not optional,
    )


def array_port(
    name: str,
    direction: PortDirection,
    element_type: PortType,
    description: str = "",
    optional: bool = False,
) -> NodePort:
    """Create an array-typed port."""
    return NodePort(
        name=name,
        direction=direction,
        port_type=PortType(kind=PortKind.ARRAY, element_type=element_type, optional=optional),
        description=description,
        required=not optional,
    )


def void_port(
    name: str,
    direction: PortDirection,
    description: str = "",
) -> NodePort:
    """Create a void/trigger port."""
    return NodePort(
        name=name,
        direction=direction,
        port_type=PortType(kind=PortKind.VOID),
        description=description,
        required=True,
    )


def domain_port(
    name: str,
    direction: PortDirection,
    domain: str,
    type_name: str,
    description: str = "",
    optional: bool = False,
) -> NodePort:
    """Create a domain-specific port."""
    return NodePort(
        name=name,
        direction=direction,
        port_type=PortType(
            kind=PortKind.DOMAIN, domain=domain, name=type_name, optional=optional
        ),
        description=description,
        required=not optional,
    )
