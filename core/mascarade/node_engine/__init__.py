"""Node Engine — infrastructure pour l'exécution de graphes composables."""

from __future__ import annotations

from mascarade.node_engine.executor import NodeExecutionResult, NodeExecutor
from mascarade.node_engine.registry import NodeTypeRegistry
from mascarade.node_engine.types import DomainType, NodeType, PortType

__all__ = [
    "DomainType",
    "PortType",
    "NodeType",
    "NodeTypeRegistry",
    "NodeExecutor",
    "NodeExecutionResult",
]
