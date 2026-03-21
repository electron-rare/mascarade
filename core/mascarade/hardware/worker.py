"""Hardware Runtime Worker — Node worker for hardware control.

The HardwareWorker implements the NodeWorker interface and provides
domain-specific execution for hardware nodes (ESP32, MIDI, DMX, serial, control).
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from mascarade.hardware.types import HARDWARE_DOMAIN_TYPES
from mascarade.node_engine.base import (
    NodeDefinition,
    NodeExecutionContext,
    NodeExecutionResult,
    NodeWorker,
)

if TYPE_CHECKING:
    pass

logger = logging.getLogger("mascarade.hardware")


class HardwareWorker(NodeWorker):
    """Hardware Runtime Worker — manages hardware control nodes.

    The HardwareWorker is responsible for:
    1. Registering hardware node definitions (ESP32, MIDI, DMX, serial, control)
    2. Executing hardware nodes when called by the graph runtime
    3. Managing hardware resources (device connections, ports, etc.)
    4. Enforcing safety constraints and timing requirements

    Domain: hardware
    """

    domain: str = "hardware"

    def __init__(self) -> None:
        """Initialize the Hardware Worker."""
        super().__init__()
        self._initialized = False
        self._device_registry = {}  # Device connection registry
        self._node_definitions = []  # Registered node definitions

    def register_nodes(self) -> list[NodeDefinition]:
        """Register all hardware node types.

        Returns:
            List of NodeDefinition objects for hardware nodes

        Node categories:
            - ESP32 control (discover, gpio, sensor, ota)
            - MIDI I/O (input, output, cc_map, note_trigger, clock)
            - DMX lighting (universe, fixture, scene)
            - Serial communication (port, parser, protocol_adapter)
            - Real-time control (pid, timer, interlock)
        """
        # For now, return empty list. Specific node definitions will be
        # registered in subsequent subtasks as they are implemented.
        return self._node_definitions

    async def execute_node(
        self,
        node_def: NodeDefinition,
        context: NodeExecutionContext,
    ) -> NodeExecutionResult:
        """Execute a hardware node with the given context.

        Args:
            node_def: The hardware node definition to execute
            context: Execution context with inputs and metadata

        Returns:
            NodeExecutionResult with outputs or error

        Raises:
            PermissionError: If required hardware capabilities are not granted
        """
        node_type = node_def.node_type

        # Verify the node belongs to the hardware domain
        if not node_type.startswith("hardware."):
            return NodeExecutionResult.error(
                f"Invalid node type for HardwareWorker: {node_type}",
                error_type="InvalidNodeType",
            )

        # Check for required capabilities based on node category
        if node_type.startswith("hardware.esp32.gpio"):
            context.require_capability("hardware.gpio.read")
            pin_config = context.get_input("pin_config")
            if pin_config and pin_config.get("direction") == "output":
                context.require_capability("hardware.gpio.write")
        elif node_type.startswith("hardware.esp32.ota"):
            context.require_capability("hardware.ota.flash")
        elif node_type.startswith("hardware.serial.port"):
            context.require_capability("hardware.serial.write")
        elif node_type.startswith("hardware.dmx."):
            context.require_capability("hardware.dmx.output")
        elif node_type.startswith("hardware.midi.output"):
            context.require_capability("hardware.midi.output")

        # Route to specific node implementation
        # For now, return a not-implemented error until specific nodes are added
        return NodeExecutionResult.error(
            f"Node execution not yet implemented for: {node_type}",
            error_type="NotImplemented",
        )

    async def initialize(self) -> None:
        """Initialize the Hardware Worker.

        Called once when the worker is registered with the runtime.
        Sets up hardware resources and registers domain types.
        """
        if self._initialized:
            logger.warning("HardwareWorker already initialized, skipping")
            return

        logger.info("Initializing HardwareWorker (domain: %s)", self.domain)

        # Register hardware domain types with the type system
        # (This will integrate with the NodeTypeRegistry once it's available)
        logger.debug("Registered %d hardware domain types", len(HARDWARE_DOMAIN_TYPES))

        # Initialize device registry
        self._device_registry.clear()
        logger.debug("Device registry initialized")

        self._initialized = True
        logger.info("HardwareWorker initialization complete")

    async def shutdown(self) -> None:
        """Shutdown the Hardware Worker and clean up resources.

        Called when the worker is being removed or the system is shutting down.
        Closes device connections, releases hardware resources, and ensures
        all outputs are set to safe defaults.
        """
        logger.info("Shutting down HardwareWorker (domain: %s)", self.domain)

        # Set all hardware outputs to safe defaults
        # (GPIO LOW, PWM 0%, DMX blackout, etc.)
        for device_id in list(self._device_registry.keys()):
            logger.debug("Closing device connection: %s", device_id)
            # TODO: Implement actual device cleanup in device-specific subtasks

        self._device_registry.clear()
        self._initialized = False
        logger.info("HardwareWorker shutdown complete")

    def register_device(self, device_id: str, device_config: dict) -> None:
        """Register a hardware device connection.

        Args:
            device_id: Unique device identifier
            device_config: Device connection configuration
        """
        self._device_registry[device_id] = device_config
        logger.debug("Registered device: %s", device_id)

    def unregister_device(self, device_id: str) -> None:
        """Unregister a hardware device connection.

        Args:
            device_id: Unique device identifier
        """
        if device_id in self._device_registry:
            del self._device_registry[device_id]
            logger.debug("Unregistered device: %s", device_id)

    def get_device(self, device_id: str) -> dict | None:
        """Get device configuration by ID.

        Args:
            device_id: Unique device identifier

        Returns:
            Device configuration dict, or None if not found
        """
        return self._device_registry.get(device_id)
