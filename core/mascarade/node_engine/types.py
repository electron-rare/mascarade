"""Phase 0 - Core type system for Universal Node Engine.

Stub implementation for Phase 5 cross-domain adapter development.
Full implementation TBD in Phase 0.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class DomainType:
    """Represents a domain-specific data type (e.g., ai.LLMResponse, cad.CADDocument)."""

    domain: str
    type_name: str
    schema: dict[str, Any] | None = None


@dataclass
class PortType:
    """Represents an input/output port type on a node."""

    name: str
    domain_type: DomainType
    required: bool = True
