"""Core type system for the Universal Node Engine.

Defines DomainType and PortType models that form the foundation for
domain-specific type registration and node port validation.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class DomainType(BaseModel):
    """Domain-specific type definition with JSON schema validation."""

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
    schema: dict[str, Any] = Field(
        ...,
        description="JSON Schema definition for this type",
    )

    @field_validator("schema")
    @classmethod
    def validate_schema(cls, v: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(v, dict):
            raise ValueError("schema must be a dictionary")
        if "type" not in v:
            raise ValueError("schema must include a 'type' field")
        return v

    @property
    def qualified_name(self) -> str:
        return f"{self.domain}.{self.name}"

    model_config = ConfigDict(
        frozen=True,
        protected_namespaces=(),
    )


class PortType(BaseModel):
    """Port type definition for node inputs and outputs."""

    name: str = Field(
        ...,
        description="Port name (must be unique within the node)",
        min_length=1,
    )
    type: str = Field(
        ...,
        description="Port data type (primitive or domain-specific)",
        min_length=1,
    )
    required: bool = Field(
        default=True,
        description="Whether this port must be connected",
    )
    description: str | None = Field(
        default=None,
        description="Human-readable description of the port",
    )

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
