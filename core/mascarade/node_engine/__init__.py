"""Universal Node Engine -- graph-based execution system for domain workers.

This module provides the foundational type system, graph runtime, and worker
interface for composable node-based workflows across AI, CAD, Electronics,
and Hardware domains.
"""

from __future__ import annotations

from mascarade.node_engine.runtime import ExecutionMode
from mascarade.node_engine.types import (
    DomainType,
    PortType,
)
from mascarade.node_engine.workers.ai.register import register_ai_worker
from mascarade.node_engine.workers.cad.register import register_cad_worker
from mascarade.node_engine.workers.hardware.register import register_hardware_worker

__version__ = "0.1.0"

__all__ = [
    "DomainType",
    "ExecutionMode",
    "PortType",
    "register_ai_worker",
    "register_cad_worker",
    "register_hardware_worker",
]
