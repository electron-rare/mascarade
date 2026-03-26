"""Base interface for Node Workers.

Node Workers are domain-specific execution engines that implement nodes
for a particular domain (e.g., hardware, LLM, CAD, electronics).
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from mascarade.node_engine.types import NodePort, PortDirection

logger = logging.getLogger("mascarade.node_engine")

# Re-export for convenience
__all__ = [
    "NodeWorker",
    "NodeDefinition",
    "NodeExecutionContext",
    "NodeExecutionResult",
    "NodePort",
    "PortDirection",
]


@dataclass
class NodeDefinition:
    """Definition of a node type provided by a NodeWorker.

    A node definition specifies:
    - The node's unique identifier (domain.category.name)
    - Input and output ports
    - Metadata (description, tags, timing constraints)
    - Version information
    """

    node_type: str = field(
        metadata={"description": "Fully qualified node type (e.g., hardware.esp32.gpio)"}
    )
    description: str = ""
    input_ports: list[NodePort] = field(default_factory=list)
    output_ports: list[NodePort] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    version: str = "1.0.0"

    # Timing constraints (for real-time nodes)
    max_latency_ms: int | None = None
    max_jitter_ms: int | None = None

    # Resource hints
    cpu_intensive: bool = False
    io_intensive: bool = False
    memory_estimate_mb: int = 0

    def get_input_port(self, name: str) -> NodePort:
        """Get input port by name."""
        for port in self.input_ports:
            if port.name == name:
                return port
        raise KeyError(f"Input port '{name}' not found on node {self.node_type}")

    def get_output_port(self, name: str) -> NodePort:
        """Get output port by name."""
        for port in self.output_ports:
            if port.name == name:
                return port
        raise KeyError(f"Output port '{name}' not found on node {self.node_type}")


@dataclass
class NodeExecutionContext:
    """Context provided to a node during execution.

    Contains:
    - Input values from connected ports
    - Configuration parameters
    - Execution metadata (graph ID, node ID, timestamps)
    - Capability grants (permissions)
    """

    node_id: str = field(default="", metadata={"description": "Unique node instance ID"})
    graph_id: str = field(default="", metadata={"description": "Parent graph ID"})
    node_type: str = field(default="", metadata={"description": "Node type identifier"})
    inputs: dict[str, Any] = field(default_factory=dict)
    config: dict[str, Any] = field(default_factory=dict)
    capabilities: set[str] = field(default_factory=set)
    metadata: dict[str, Any] = field(default_factory=dict)

    def get_input(self, port_name: str, default: Any = None) -> Any:
        """Get input value for a port."""
        return self.inputs.get(port_name, default)

    def has_capability(self, capability: str) -> bool:
        """Check if a capability is granted."""
        return capability in self.capabilities

    def require_capability(self, capability: str) -> None:
        """Require a capability, raise if not granted."""
        if not self.has_capability(capability):
            raise PermissionError(
                f"Node {self.node_id} requires capability '{capability}' " f"but it is not granted"
            )


@dataclass
class NodeExecutionResult:
    """Result of node execution.

    Contains:
    - Output values for each output port
    - Status (success/error)
    - Error details if failed
    - Metadata (execution time, warnings, etc.)
    """

    success: bool = True
    outputs: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    error_type: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def error_message(self) -> str | None:
        """Alias for error field, for backward compatibility."""
        return self.error

    @classmethod
    def ok(cls, **outputs: Any) -> NodeExecutionResult:
        """Create a successful result with outputs."""
        return cls(success=True, outputs=outputs)

    @classmethod
    def error(cls, error: str, error_type: str = "RuntimeError") -> NodeExecutionResult:
        """Create an error result."""
        return cls(success=False, error=error, error_type=error_type)


class NodeWorker(ABC):
    """Abstract base class for Node Workers.

    A NodeWorker is responsible for:
    1. Registering node definitions for its domain
    2. Executing nodes when called by the graph runtime
    3. Managing domain-specific resources (connections, devices, etc.)

    Subclasses should implement:
    - register_nodes(): Return list of NodeDefinition objects
    - execute_node(): Execute a node and return results
    - shutdown(): Clean up resources (optional)
    """

    domain: str

    @abstractmethod
    def register_nodes(self) -> list[NodeDefinition]:
        """Register all node types provided by this worker.

        Returns:
            List of NodeDefinition objects describing available nodes

        Example:
            ```python
            def register_nodes(self) -> list[NodeDefinition]:
                return [
                    NodeDefinition(
                        node_type="hardware.esp32.gpio",
                        description="Read/write ESP32 GPIO pin",
                        input_ports=[...],
                        output_ports=[...],
                    ),
                    # ... more nodes
                ]
            ```
        """
        ...

    @abstractmethod
    async def execute_node(
        self,
        node_def: NodeDefinition,
        context: NodeExecutionContext,
    ) -> NodeExecutionResult:
        """Execute a node with the given context.

        Args:
            node_def: The node definition to execute
            context: Execution context with inputs and metadata

        Returns:
            NodeExecutionResult with outputs or error

        Example:
            ```python
            async def execute_node(
                self,
                node_def: NodeDefinition,
                context: NodeExecutionContext,
            ) -> NodeExecutionResult:
                if node_def.node_type == "hardware.esp32.gpio":
                    device = context.get_input("device")
                    pin_config = context.get_input("pin_config")
                    result = await self._gpio_operation(device, pin_config)
                    return NodeExecutionResult.ok(state=result)
                return NodeExecutionResult.error(f"Unknown node type: {node_def.node_type}")
            ```
        """
        ...

    async def initialize(self) -> None:
        """Initialize the worker.

        Called once when the worker is registered with the runtime.
        Override to perform setup (e.g., connect to devices, load resources).
        """
        logger.info("Initializing %s worker", self.domain)

    async def shutdown(self) -> None:
        """Shutdown the worker and clean up resources.

        Called when the worker is being removed or the system is shutting down.
        Override to perform cleanup (e.g., close connections, release devices).
        """
        logger.info("Shutting down %s worker", self.domain)

    def get_node_definition(self, node_type: str) -> NodeDefinition | None:
        """Get node definition by type.

        Args:
            node_type: Fully qualified node type (e.g., "hardware.esp32.gpio")

        Returns:
            NodeDefinition if found, None otherwise
        """
        for node_def in self.register_nodes():
            if node_def.node_type == node_type:
                return node_def
        return None
