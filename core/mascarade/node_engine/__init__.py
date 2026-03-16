"""Universal Node Engine — Core module for node-based graph execution.

The node engine provides a universal type system and execution runtime for
domain-agnostic graph execution across AI, CAD, Electronics, and Hardware domains.
"""

from __future__ import annotations

__all__ = [
    "PrimitiveType",
    "ArrayType",
    "MapType",
    "OptionalType",
    "UnionType",
    "StreamType",
    "DomainType",
    "PortType",
    "NodePortDefinition",
]

from mascarade.node_engine.types import (
    ArrayType,
    DomainType,
    MapType,
    NodePortDefinition,
    OptionalType,
    PortType,
    PrimitiveType,
    StreamType,
    UnionType,
)
