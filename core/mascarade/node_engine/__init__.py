"""Universal Node Engine — Phase 0 Foundations.

The Node Engine provides a graph-based execution framework for domain workers.
Each domain (hardware, LLM, CAD, electronics) implements the NodeWorker interface
to provide nodes that can be composed into execution graphs.

Core components:
- NodeWorker: Abstract interface for domain workers
- NodeDefinition: Definition of a node type (ports, metadata)
- NodePort: Input/output port specification
- PortDirection: Input vs Output
- PortType: Type system for port values

Example:
    ```python
    from mascarade.node_engine import NodeWorker, NodeDefinition, NodePort, PortDirection

    class MyWorker(NodeWorker):
        domain = "my_domain"

        def register_nodes(self) -> list[NodeDefinition]:
            return [
                NodeDefinition(
                    node_type="my_domain.example.node",
                    description="Example node",
                    input_ports=[...],
                    output_ports=[...],
                )
            ]

        async def execute_node(self, node_def, context):
            # Implement node execution
            return NodeExecutionResult.ok(output=42)
    ```
"""

from __future__ import annotations

from mascarade.node_engine.base import (
    NodeDefinition,
    NodeExecutionContext,
    NodeExecutionResult,
    NodeWorker,
)
from mascarade.node_engine.types import (
    NodePort,
    PortDirection,
    PortKind,
    PortType,
    PrimitiveType,
    array_port,
    domain_port,
    primitive_port,
    void_port,
)

__all__ = [
    # Base classes
    "NodeWorker",
    "NodeDefinition",
    "NodeExecutionContext",
    "NodeExecutionResult",
    # Type system
    "NodePort",
    "PortDirection",
    "PortType",
    "PortKind",
    "PrimitiveType",
    # Port constructors
    "primitive_port",
    "array_port",
    "void_port",
    "domain_port",
]
