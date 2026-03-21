"""Core type system for the Universal Node Engine.

Defines DomainType, PortType, NodePort, NodeType, and composite type models
that form the foundation for domain-specific type registration and node port validation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Union

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


# --- Enums ---


class PrimitiveType(str, Enum):
    """Primitive port types."""

    STRING = "string"
    NUMBER = "number"
    INTEGER = "integer"
    BOOLEAN = "boolean"
    BINARY = "binary"
    JSON = "json"
    VOID = "void"


class PortDirection(str, Enum):
    """Port direction enum."""

    INPUT = "input"
    OUTPUT = "output"


class PortKind(str, Enum):
    """Port kind enum."""

    DATA = "data"
    CONTROL = "control"
    TRIGGER = "trigger"
    PRIMITIVE = "primitive"
    DOMAIN = "domain"
    ARRAY = "array"
    MAP = "map"
    STREAM = "stream"


# --- Composite Types (for rich type system used by test_node_engine_types) ---


class ArrayType(BaseModel):
    """Array type wrapping an element type."""

    kind: str = "array"
    element: Any

    model_config = ConfigDict(frozen=True)


class MapType(BaseModel):
    """Map type with key and value types."""

    kind: str = "map"
    key: Any
    value: Any

    model_config = ConfigDict(frozen=True)


class OptionalType(BaseModel):
    """Optional type wrapping an inner type."""

    kind: str = "optional"
    inner: Any

    model_config = ConfigDict(frozen=True)


class UnionType(BaseModel):
    """Union type with multiple variants."""

    kind: str = "union"
    variants: list[Any]

    model_config = ConfigDict(frozen=True)


class StreamType(BaseModel):
    """Stream type wrapping an element type."""

    kind: str = "stream"
    element: Any

    model_config = ConfigDict(frozen=True)


# --- DomainType ---


class DomainType(BaseModel):
    """Domain-specific type definition with JSON schema validation.

    Domain types extend the base type system with domain-specific structures
    (e.g., "ai" domain defines LLMResponse, EmbeddingVector, etc.). They are
    registered with the NodeTypeRegistry at worker startup.

    Supports two construction patterns:
    - With ``schema`` dict (original API, requires 'type' key)
    - With ``schema_def`` dict (rich type system API, no 'type' key required)
    """

    kind: str = "domain"
    domain: str = Field(
        ...,
        description="Domain identifier (e.g., 'ai', 'cad', 'electronics')",
        min_length=1,
    )
    name: str = Field(
        ...,
        description="Type name within the domain (e.g., 'LLMResponse', 'EmbeddingVector')",
        min_length=1,
    )
    schema_def: dict[str, Any] = Field(
        default_factory=dict,
        alias="schema",
        description="JSON Schema definition for this type",
    )

    @field_validator("schema_def", mode="before")
    @classmethod
    def validate_schema_field(cls, v: dict[str, Any]) -> dict[str, Any]:
        """Accept any dict as schema_def (rich type system uses arbitrary schemas)."""
        return v

    @property
    def schema(self) -> dict[str, Any]:
        """Access schema_def via the 'schema' name."""
        return self.schema_def

    @property
    def qualified_name(self) -> str:
        """Return the fully qualified type name (domain.name)."""
        return f"{self.domain}.{self.name}"

    @property
    def full_name(self) -> str:
        """Alias for qualified_name."""
        return self.qualified_name

    def validate_schema(self, data: dict[str, Any]) -> tuple[bool, str | None]:
        """Validate data against this domain type's JSON schema.

        Args:
            data: The data to validate

        Returns:
            Tuple of (is_valid, error_message_or_none)
        """
        schema = self.schema_def
        if not schema:
            return True, None

        # Check required fields
        required = schema.get("required", [])
        for field_name in required:
            if field_name not in data:
                return False, f"Missing required field: {field_name}"

        # Check property constraints
        properties = schema.get("properties", {})
        for key, value in data.items():
            if key in properties:
                prop_schema = properties[key]
                # Check enum constraints
                if "enum" in prop_schema and value not in prop_schema["enum"]:
                    return False, f"Invalid value for {key}: {value}. enum constraint violated, must be one of {prop_schema['enum']}"

        return True, None

    model_config = ConfigDict(
        frozen=True,
        protected_namespaces=(),
        populate_by_name=True,
    )


# --- PortType Union (for rich type descriptors) ---

PortTypeUnion = Union[
    PrimitiveType, ArrayType, MapType, OptionalType,
    UnionType, StreamType, DomainType,
]

# Required for Pydantic forward reference resolution
ArrayType.model_rebuild()
MapType.model_rebuild()
OptionalType.model_rebuild()
UnionType.model_rebuild()
StreamType.model_rebuild()


# --- PortType (extended to support direction, port_type, optional, default_value) ---


class PortType(BaseModel):
    """Port type definition for node inputs and outputs.

    Supports both the minimal API (name + type) and the extended API
    (direction, port_type, optional, default_value) used by electronics workers.

    Also serves as a recursive type descriptor when used with kind=PortKind.PRIMITIVE,
    kind=PortKind.ARRAY, or kind=PortKind.DOMAIN.
    """

    name: Any = Field(
        default="",
        description="Port name (must be unique within the node), or PrimitiveType for type descriptors",
    )
    type: str = Field(
        default="",
        description=(
            "Port data type. Can be primitive (string, number, boolean, array<T>, "
            "map<K,V>) or domain-specific (domain.TypeName, e.g., 'ai.LLMResponse')"
        ),
    )

    @model_validator(mode="after")
    def validate_port_fields(self) -> "PortType":
        """Validate port name and type when used as a port definition."""
        name = self.name
        typ = self.type
        kind = self.kind

        # Only validate as a port definition when kind is DATA/CONTROL/TRIGGER
        # Type descriptors use kind=PRIMITIVE/DOMAIN/ARRAY/MAP/STREAM
        is_type_descriptor = kind in (PortKind.PRIMITIVE, PortKind.DOMAIN, PortKind.ARRAY, PortKind.MAP, PortKind.STREAM)
        if is_type_descriptor:
            return self

        # For port definitions: name must not be empty when type is set
        if isinstance(name, str) and not isinstance(name, PrimitiveType) and typ:
            if not name or not name.strip():
                raise ValueError("Port name cannot be empty")

        # For port definitions: type must not be empty when name is set
        if isinstance(name, str) and not isinstance(name, PrimitiveType) and name:
            if isinstance(typ, str) and (not typ or not typ.strip()):
                # Allow empty type if port_type is set
                if not self.port_type:
                    raise ValueError("Port type cannot be empty")

        return self
    required: bool = Field(
        default=True,
        description="Whether this port must be connected (inputs) or always produces a value (outputs)",
    )
    description: str | None = Field(
        default=None,
        description="Human-readable description of the port's purpose",
    )

    # Extended fields for electronics/hardware workers
    direction: PortDirection | None = Field(
        default=None,
        description="Port direction (input/output)",
    )
    port_type: Any = Field(
        default="",
        description="Alternative type field used by electronics workers (str or PortType)",
    )
    optional: bool = Field(
        default=False,
        description="Whether this port is optional",
    )
    default_value: Any = Field(
        default=None,
        description="Default value for this port",
    )
    kind: PortKind = Field(
        default=PortKind.DATA,
        description="Port kind (data, control, trigger, primitive, domain, array)",
    )

    # Fields for recursive type descriptors
    element_type: Any = Field(
        default=None,
        description="Element type for array type descriptors",
    )
    key_type: Any = Field(
        default=None,
        description="Key type for map type descriptors",
    )
    value_type: Any = Field(
        default=None,
        description="Value type for map type descriptors",
    )
    domain: str = Field(
        default="",
        description="Domain for domain type descriptors",
    )

    @property
    def effective_type(self) -> str:
        """Return the effective type string (prefers 'type' then 'port_type')."""
        t = self.type
        if t:
            return t
        pt = self.port_type
        if isinstance(pt, str) and pt:
            return pt
        return ""

    @property
    def is_primitive(self) -> bool:
        """Check if this port uses a primitive type (not domain-specific)."""
        primitives = {"string", "number", "integer", "boolean", "json", "void"}
        t = self.effective_type
        if not t:
            return False
        base_type = t.split("<")[0].split(".")[0]
        return base_type in primitives

    @property
    def is_stream(self) -> bool:
        """Check if this port is a stream type."""
        return self.effective_type.startswith("stream<")

    @property
    def is_array(self) -> bool:
        """Check if this port is an array type."""
        return self.effective_type.startswith("array<")

    @property
    def is_map(self) -> bool:
        """Check if this port is a map type."""
        return self.effective_type.startswith("map<")

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)


# Alias for NodePort — used by base.py and hardware nodes
NodePort = PortType


# --- NodePortDefinition (rich port definition used by test_node_engine_types) ---


class NodePortDefinition(BaseModel):
    """Rich port definition for node inputs and outputs."""

    id: str
    label: str
    type: Any  # Can be PrimitiveType, ArrayType, etc.
    required: bool = True
    default: Any = None
    description: str = ""

    model_config = ConfigDict(frozen=True)


# --- NodeType (used by executor.py and registry.py) ---


class NodeType(BaseModel):
    """Node type definition with input and output ports."""

    id: str = Field(..., description="Unique identifier for this node type")
    domain: str = Field(default="", description="Domain this node type belongs to")
    label: str = Field(default="", description="Human-readable label")
    description: str = Field(default="", description="Description of this node type")
    category: str = Field(default="", description="Category within the domain")
    inputs: list[PortType] = Field(default_factory=list, description="Input port definitions")
    outputs: list[PortType] = Field(default_factory=list, description="Output port definitions")

    model_config = ConfigDict(frozen=True, protected_namespaces=())


# --- Helper functions for creating ports (used by hardware nodes) ---


def primitive_port(
    name: str,
    direction: PortDirection | PrimitiveType | str = PortDirection.INPUT,
    primitive_type: PrimitiveType | str | PortDirection | None = None,
    *,
    ptype: PrimitiveType | str | None = None,
    description: str = "",
    optional: bool = False,
    default_value: Any = None,
    kind: PortKind = PortKind.DATA,
) -> PortType:
    """Create a primitive port.

    Supports multiple calling conventions:
    - primitive_port("name", PortDirection.INPUT, PrimitiveType.STRING, ...)
    - primitive_port(name="name", direction=..., primitive_type=..., ...)
    - primitive_port("name", PrimitiveType.STRING, PortDirection.INPUT, ...)
    """
    # Resolve the actual direction and type from flexible args
    actual_direction = direction
    actual_type = primitive_type or ptype

    # Handle swapped positional args: (name, PrimitiveType, PortDirection)
    if isinstance(direction, (PrimitiveType, str)) and not isinstance(direction, PortDirection):
        if isinstance(primitive_type, PortDirection):
            actual_direction = primitive_type
            actual_type = direction
        else:
            # direction is actually a type string
            actual_type = direction
            actual_direction = PortDirection.INPUT

    # Handle case where primitive_type is passed as keyword
    if actual_type is None:
        actual_type = PrimitiveType.STRING

    t = actual_type.value if isinstance(actual_type, PrimitiveType) else str(actual_type)
    d = actual_direction if isinstance(actual_direction, PortDirection) else PortDirection(actual_direction)

    return PortType(
        name=name,
        type=t,
        port_type=t,
        direction=d,
        description=description,
        optional=optional,
        default_value=default_value,
        kind=kind,
    )


def domain_port(
    name: str = "",
    direction: PortDirection = PortDirection.INPUT,
    domain: str = "",
    type_name: str = "",
    *,
    domain_type: str = "",
    description: str = "",
    optional: bool = False,
    default_value: Any = None,
    kind: PortKind = PortKind.DATA,
) -> PortType:
    """Create a domain-specific port.

    Supports:
    - domain_port(name, direction, domain, type_name, ...)
    - domain_port(name, domain_type, direction, ...)
    """
    if domain and type_name:
        resolved_type = f"{domain}.{type_name}"
    elif domain_type:
        resolved_type = domain_type
    else:
        resolved_type = "unknown"

    return PortType(
        name=name,
        type=resolved_type,
        port_type=resolved_type,
        direction=direction,
        description=description,
        optional=optional,
        default_value=default_value,
        kind=kind,
    )


def array_port(
    name: str = "",
    direction: PortDirection = PortDirection.INPUT,
    element_type: Any = None,
    *,
    description: str = "",
    optional: bool = False,
    default_value: Any = None,
    kind: PortKind = PortKind.DATA,
) -> PortType:
    """Create an array port."""
    if isinstance(element_type, str):
        t = f"array<{element_type}>"
    elif element_type is not None:
        # Handle PortType objects passed as element_type
        t = f"array<{getattr(element_type, 'name', str(element_type))}>"
    else:
        t = "array"
    return PortType(
        name=name,
        type=t,
        port_type=t,
        direction=direction,
        description=description,
        optional=optional,
        default_value=default_value,
        kind=kind,
    )


def void_port(
    name: str = "",
    direction: PortDirection = PortDirection.INPUT,
    *,
    description: str = "",
    optional: bool = False,
    kind: PortKind = PortKind.DATA,
) -> PortType:
    """Create a void port."""
    return PortType(
        name=name,
        type="void",
        port_type="void",
        direction=direction,
        description=description,
        optional=optional,
        kind=kind,
    )
