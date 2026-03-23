"""Core type system for the Universal Node Engine.

Defines the port type hierarchy and domain type models used across all domain workers.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal, Union

from pydantic import BaseModel, ConfigDict, Field, field_validator

# --- Primitive type system (used by graph validation and tests) ---


class PrimitiveType(StrEnum):
    STRING = "string"
    NUMBER = "number"
    INTEGER = "integer"
    BOOLEAN = "boolean"
    BINARY = "binary"
    JSON = "json"
    VOID = "void"


class ArrayType(BaseModel):
    kind: Literal["array"] = "array"
    element: "PortTypeUnion"


class MapType(BaseModel):
    kind: Literal["map"] = "map"
    key: PrimitiveType
    value: "PortTypeUnion"


class OptionalType(BaseModel):
    kind: Literal["optional"] = "optional"
    inner: "PortTypeUnion"


class UnionType(BaseModel):
    kind: Literal["union"] = "union"
    variants: list["PortTypeUnion"]


class StreamType(BaseModel):
    kind: Literal["stream"] = "stream"
    element: "PortTypeUnion"


# --- Domain type (Pydantic validated, for registry) ---


class DomainType(BaseModel):
    """Domain-specific type definition with JSON schema validation."""

    kind: Literal["domain"] = "domain"
    domain: str = Field(
        ...,
        description="Domain identifier (e.g., 'ai', 'cad', 'electronics')",
        min_length=1,
    )
    name: str = Field(
        ...,
        description="Type name within the domain (e.g., 'LLMResponse')",
        min_length=1,
    )
    schema_def: dict[str, Any] = Field(
        default_factory=dict,
        alias="schema",
        description="JSON Schema definition for this type",
    )

    @field_validator("schema_def")
    @classmethod
    def validate_schema(cls, v: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(v, dict):
            raise ValueError("schema must be a dictionary")
        return v

    @property
    def qualified_name(self) -> str:
        return f"{self.domain}.{self.name}"

    model_config = ConfigDict(
        frozen=True,
        protected_namespaces=(),
        populate_by_name=True,
    )


# Union of all port types
PortTypeUnion = Union[
    PrimitiveType,
    ArrayType,
    MapType,
    OptionalType,
    UnionType,
    StreamType,
    DomainType,
]

# Rebuild models for forward reference resolution
ArrayType.model_rebuild()
MapType.model_rebuild()
OptionalType.model_rebuild()
UnionType.model_rebuild()
StreamType.model_rebuild()


class NodePortDefinition(BaseModel):
    """Definition of a single input or output port on a node."""

    id: str
    label: str
    type: PortTypeUnion
    required: bool = True
    default: Any = None
    description: str = ""


# --- Port type (Pydantic validated, for API/graph construction) ---


class PortType(BaseModel):
    """Port type definition for node inputs and outputs."""

    name: str = Field(..., description="Port name", min_length=1)
    type: str = Field(
        ...,
        description="Port data type (primitive or domain-specific)",
        min_length=1,
    )
    required: bool = Field(default=True)
    description: str | None = Field(default=None)

    @field_validator("type")
    @classmethod
    def validate_type(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("type cannot be empty")
        return v.strip()

    @property
    def is_primitive(self) -> bool:
        primitives = {"string", "number", "integer", "boolean", "json", "void"}
        base_type = self.type.split("<")[0].split(".")[0]
        return base_type in primitives

    @property
    def is_stream(self) -> bool:
        return self.type.startswith("stream<")

    @property
    def is_array(self) -> bool:
        return self.type.startswith("array<")

    @property
    def is_map(self) -> bool:
        return self.type.startswith("map<")

    model_config = ConfigDict(frozen=True)
