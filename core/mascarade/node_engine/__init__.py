"""Universal Node Engine — graph-based execution system for domain workers.

This module provides the foundational type system, graph runtime, and worker
interface for composable node-based workflows across AI, CAD, Electronics,
and Hardware domains.
"""

from __future__ import annotations

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
from mascarade.node_engine.workers.ai.register import register_ai_worker

__version__ = "0.1.0"

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
    "register_ai_worker",
]
