"""Core type system for the Universal Node Engine.

Defines DomainType and PortType models that form the foundation for
domain-specific type registration and node port validation.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class DomainType(BaseModel):
    """Domain-specific type definition with JSON schema validation.

    Domain types extend the base type system with domain-specific structures
    (e.g., "ai" domain defines LLMResponse, EmbeddingVector, etc.). They are
    registered with the NodeTypeRegistry at worker startup.

    Example:
        >>> domain_type = DomainType(
        ...     domain="ai",
        ...     name="LLMResponse",
        ...     schema={
        ...         "type": "object",
        ...         "properties": {
        ...             "content": {"type": "string"},
        ...             "model": {"type": "string"},
        ...             "provider": {"type": "string"},
        ...         },
        ...         "required": ["content", "model", "provider"],
        ...     },
        ... )
    """

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
    schema: dict[str, Any] = Field(
        ...,
        description="JSON Schema definition for this type",
    )

    @field_validator("schema")
    @classmethod
    def validate_schema(cls, v: dict[str, Any]) -> dict[str, Any]:
        """Validate that schema is a valid JSON Schema object."""
        if not isinstance(v, dict):
            raise ValueError("schema must be a dictionary")
        if "type" not in v:
            raise ValueError("schema must include a 'type' field")
        return v

    @property
    def qualified_name(self) -> str:
        """Return the fully qualified type name (domain.name)."""
        return f"{self.domain}.{self.name}"

    model_config = ConfigDict(
        frozen=True,  # Make instances immutable
        protected_namespaces=(),  # Allow 'schema' field (shadows BaseModel.schema)
    )


class PortType(BaseModel):
    """Port type definition for node inputs and outputs.

    Ports define the data interface of a node. Each port has a type
    (primitive like 'string' or domain-specific like 'ai.LLMResponse'),
    a name, and validation constraints.

    Example:
        >>> input_port = PortType(
        ...     name="prompt",
        ...     type="string",
        ...     required=True,
        ...     description="The user prompt to send to the LLM",
        ... )
        >>> output_port = PortType(
        ...     name="response",
        ...     type="ai.LLMResponse",
        ...     required=True,
        ...     description="Complete LLM response with metadata",
        ... )
    """

    name: str = Field(
        ...,
        description="Port name (must be unique within the node)",
        min_length=1,
    )
    type: str = Field(
        ...,
        description=(
            "Port data type. Can be primitive (string, number, boolean, array<T>, "
            "map<K,V>) or domain-specific (domain.TypeName, e.g., 'ai.LLMResponse')"
        ),
        min_length=1,
    )
    required: bool = Field(
        default=True,
        description="Whether this port must be connected (inputs) or always produces a value (outputs)",
    )
    description: str | None = Field(
        default=None,
        description="Human-readable description of the port's purpose",
    )

    @field_validator("type")
    @classmethod
    def validate_type(cls, v: str) -> str:
        """Validate port type format."""
        if not v or not v.strip():
            raise ValueError("type cannot be empty")
        # Basic validation — detailed type checking happens at graph validation time
        return v.strip()

    @property
    def is_primitive(self) -> bool:
        """Check if this port uses a primitive type (not domain-specific)."""
        primitives = {"string", "number", "integer", "boolean", "json", "void"}
        # Check for base type (before generics like array<T>)
        base_type = self.type.split("<")[0].split(".")[0]
        return base_type in primitives

    @property
    def is_stream(self) -> bool:
        """Check if this port is a stream type."""
        return self.type.startswith("stream<")

    @property
    def is_array(self) -> bool:
        """Check if this port is an array type."""
        return self.type.startswith("array<")

    @property
    def is_map(self) -> bool:
        """Check if this port is a map type."""
        return self.type.startswith("map<")

    model_config = ConfigDict(frozen=True)  # Make instances immutable
