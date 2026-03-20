"""AI Worker domain types.

These types extend the base type system with AI-specific structures.
Modeled on the existing LLMResponse dataclass from providers/base.py.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from mascarade.node_engine.types import DomainType


@dataclass
class LLMResponse:
    """Normalized LLM response — mirrors core/mascarade/router/providers/base.py.

    This is the primary output type for inference nodes. It preserves
    the exact structure used by the Router so that downstream consumers
    can access provider metadata without transformation.
    """

    content: str
    model: str
    provider: str
    usage: dict[str, int] = field(default_factory=dict)


@dataclass
class TokenUsage:
    """Token consumption metrics for cost tracking and budgeting."""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    cost_usd: float = 0.0


@dataclass
class EmbeddingVector:
    """Dense vector embedding produced by an embedding model."""

    values: list[float]
    model: str
    dimensions: int


@dataclass
class ChatMessage:
    """A single message in a conversation.

    Follows the standard role-based message format used by all
    LLM providers in the Mascarade Router.
    """

    role: str  # "system" | "user" | "assistant"
    content: str
    name: str | None = None


@dataclass
class PromptTemplate:
    """A template with variable placeholders for dynamic prompt construction."""

    template: str
    variables: list[str]  # Variable names expected in the template
    defaults: dict[str, str] = field(default_factory=dict)


# Domain type registration for the NodeTypeRegistry
AI_DOMAIN_TYPES = [
    DomainType(
        domain="ai",
        name="LLMResponse",
        schema={
            "type": "object",
            "properties": {
                "content": {"type": "string"},
                "model": {"type": "string"},
                "provider": {"type": "string"},
                "usage": {"type": "object"},
            },
            "required": ["content", "model", "provider"],
        },
    ),
    DomainType(
        domain="ai",
        name="TokenUsage",
        schema={
            "type": "object",
            "properties": {
                "prompt_tokens": {"type": "integer"},
                "completion_tokens": {"type": "integer"},
                "total_tokens": {"type": "integer"},
                "cost_usd": {"type": "number"},
            },
        },
    ),
    DomainType(
        domain="ai",
        name="EmbeddingVector",
        schema={
            "type": "object",
            "properties": {
                "values": {"type": "array", "items": {"type": "number"}},
                "model": {"type": "string"},
                "dimensions": {"type": "integer"},
            },
            "required": ["values", "model", "dimensions"],
        },
    ),
    DomainType(
        domain="ai",
        name="ChatMessage",
        schema={
            "type": "object",
            "properties": {
                "role": {"type": "string", "enum": ["system", "user", "assistant"]},
                "content": {"type": "string"},
                "name": {"type": "string"},
            },
            "required": ["role", "content"],
        },
    ),
    DomainType(
        domain="ai",
        name="PromptTemplate",
        schema={
            "type": "object",
            "properties": {
                "template": {"type": "string"},
                "variables": {"type": "array", "items": {"type": "string"}},
                "defaults": {"type": "object"},
            },
            "required": ["template", "variables"],
        },
    ),
]
