"""Universal Node Engine — Core type system.

Defines the port type hierarchy used across all domain workers.
Modeled on the Pydantic validation patterns used throughout Mascarade core.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal, Union

from pydantic import BaseModel, Field


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
    element: "PortType"


class MapType(BaseModel):
    kind: Literal["map"] = "map"
    key: PrimitiveType
    value: "PortType"


class OptionalType(BaseModel):
    kind: Literal["optional"] = "optional"
    inner: "PortType"


class UnionType(BaseModel):
    kind: Literal["union"] = "union"
    variants: list["PortType"]


class StreamType(BaseModel):
    kind: Literal["stream"] = "stream"
    element: "PortType"


class DomainType(BaseModel):
    model_config = {"populate_by_name": True}

    kind: Literal["domain"] = "domain"
    domain: str
    name: str
    schema_def: dict[str, Any] = Field(default_factory=dict, alias="schema")


PortType = Union[
    PrimitiveType, ArrayType, MapType, OptionalType,
    UnionType, StreamType, DomainType,
]

# Required for Pydantic forward reference resolution
ArrayType.model_rebuild()
MapType.model_rebuild()
OptionalType.model_rebuild()
UnionType.model_rebuild()
StreamType.model_rebuild()


class NodePortDefinition(BaseModel):
    """Definition of a single input or output port on a node."""

    id: str
    label: str
    type: PortType
    required: bool = True
    default: Any = None
    description: str = ""
