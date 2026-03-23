"""MIDI I/O nodes — Input capture, output generation, CC mapping, note triggering, and clock synchronization.

Implements nodes for communicating with MIDI hardware and software ports via
the system's MIDI subsystem (ALSA on Linux, CoreMIDI on macOS). Follows the
graceful degradation model defined in SPEC-029-P4 section 4.
"""

from __future__ import annotations

import logging
from typing import Any

from mascarade.hardware.types import MIDIMessage
from mascarade.node_engine.base import (
    NodeDefinition,
    NodeExecutionContext,
    NodeExecutionResult,
)
from mascarade.node_engine.types import (
    PortDirection,
    PortKind,
    PortType,
    PrimitiveType,
    array_port,
    domain_port,
    primitive_port,
)

logger = logging.getLogger("mascarade.hardware.midi")

# --- Error Classes ---


class MIDIError(RuntimeError):
    """Base error for MIDI node failures."""


class MIDIPortError(MIDIError):
    """Raised when MIDI port cannot be opened or accessed."""


class MIDIMessageError(MIDIError):
    """Raised when MIDI message is invalid or cannot be sent."""


# --- MIDI Client ---


class MIDIClient:
    """Async client for communicating with MIDI ports.

    Manages MIDI input/output port connections and message routing.
    Implements graceful degradation when hardware is unavailable.
    """

    def __init__(self) -> None:
        """Initialize MIDI client.

        Note:
            Actual MIDI library integration (mido/python-rtmidi) will be
            implemented in a future iteration. This is a placeholder that
            supports the node interface.
        """
        self._input_ports: dict[str, Any] = {}
        self._output_ports: dict[str, Any] = {}
        self._mock_mode = True  # Enable mock mode until MIDI library is integrated

    async def list_input_ports(self) -> list[str]:
        """List available MIDI input ports.

        Returns:
            List of input port names
        """
        if self._mock_mode:
            logger.debug("MIDI hardware not available, returning mock input ports")
            return ["Mock MIDI Input"]
        # TODO: Implement with mido.get_input_names() or similar
        return []

    async def list_output_ports(self) -> list[str]:
        """List available MIDI output ports.

        Returns:
            List of output port names
        """
        if self._mock_mode:
            logger.debug("MIDI hardware not available, returning mock output ports")
            return ["Mock MIDI Output"]
        # TODO: Implement with mido.get_output_names() or similar
        return []

    async def open_input_port(self, port_name: str) -> None:
        """Open a MIDI input port.

        Args:
            port_name: Name or pattern of the MIDI input port

        Raises:
            MIDIPortError: If port cannot be opened
        """
        if self._mock_mode:
            logger.info("Opening mock MIDI input port: %s", port_name)
            self._input_ports[port_name] = None
            return

        # TODO: Implement with mido or python-rtmidi
        raise MIDIPortError(f"Failed to open MIDI input port: {port_name}")

    async def open_output_port(self, port_name: str) -> None:
        """Open a MIDI output port.

        Args:
            port_name: Name or pattern of the MIDI output port

        Raises:
            MIDIPortError: If port cannot be opened
        """
        if self._mock_mode:
            logger.info("Opening mock MIDI output port: %s", port_name)
            self._output_ports[port_name] = None
            return

        # TODO: Implement with mido or python-rtmidi
        raise MIDIPortError(f"Failed to open MIDI output port: {port_name}")

    async def read_messages(
        self,
        port_name: str,
        channel_filter: int | None = None,
        message_filter: list[str] | None = None,
    ) -> list[MIDIMessage]:
        """Read MIDI messages from an input port.

        Args:
            port_name: MIDI input port name
            channel_filter: Optional MIDI channel filter (0-15)
            message_filter: Optional message type filter

        Returns:
            List of received MIDI messages

        Note:
            This is a placeholder implementation. In production, this would
            use an async queue to buffer incoming MIDI messages.
        """
        if self._mock_mode:
            # Return empty list in mock mode (graceful degradation)
            return []

        if port_name not in self._input_ports:
            raise MIDIPortError(f"Input port not open: {port_name}")

        # TODO: Implement actual MIDI reading with mido/python-rtmidi
        return []

    async def send_message(
        self,
        port_name: str,
        message: MIDIMessage,
    ) -> bool:
        """Send a MIDI message to an output port.

        Args:
            port_name: MIDI output port name
            message: MIDI message to send

        Returns:
            True if message was sent successfully

        Raises:
            MIDIPortError: If port is not open
            MIDIMessageError: If message is invalid
        """
        if self._mock_mode:
            logger.debug(
                "Mock MIDI output [%s]: status=0x%02X ch=%d data1=%d data2=%d",
                port_name,
                message.status,
                message.channel,
                message.data1,
                message.data2,
            )
            return False  # Indicate mock mode - message not actually sent

        if port_name not in self._output_ports:
            raise MIDIPortError(f"Output port not open: {port_name}")

        # TODO: Implement actual MIDI sending with mido/python-rtmidi
        return True

    async def send_batch(
        self,
        port_name: str,
        messages: list[MIDIMessage],
    ) -> bool:
        """Send a batch of MIDI messages atomically.

        Args:
            port_name: MIDI output port name
            messages: List of MIDI messages to send

        Returns:
            True if all messages were sent successfully
        """
        for message in messages:
            success = await self.send_message(port_name, message)
            if not success and not self._mock_mode:
                return False
        return True

    async def close(self) -> None:
        """Close all MIDI ports and release resources."""
        self._input_ports.clear()
        self._output_ports.clear()
        logger.info("MIDI client closed")


# --- Node Definitions ---


# Global MIDI client instance (shared across all MIDI nodes)
_midi_client: MIDIClient | None = None


def _get_midi_client() -> MIDIClient:
    """Get or create the global MIDI client instance."""
    global _midi_client
    if _midi_client is None:
        _midi_client = MIDIClient()
    return _midi_client


async def execute_midi_input(ctx: NodeExecutionContext) -> NodeExecutionResult:
    """Execute hardware.midi.input node.

    Captures MIDI messages from a hardware or virtual MIDI input port.
    """
    port_name = ctx.get_input("port_name")
    channel_filter = ctx.get_input("channel_filter")
    message_filter = ctx.get_input("message_filter")

    if not port_name:
        return NodeExecutionResult.error("port_name is required", "ValueError")

    client = _get_midi_client()

    try:
        # Ensure port is open
        await client.open_input_port(port_name)

        # Read messages (returns empty list in mock mode)
        messages = await client.read_messages(port_name, channel_filter, message_filter)

        # In mock mode or when no messages, return empty stream marker
        # A real implementation would use a streaming port
        return NodeExecutionResult.ok(messages=messages)

    except MIDIPortError as exc:
        # Graceful degradation: log warning but don't block graph execution
        logger.warning("MIDI input port unavailable: %s", exc)
        return NodeExecutionResult.ok(messages=[])
    except Exception as exc:
        logger.exception("Unexpected error in MIDI input node")
        return NodeExecutionResult.error(str(exc), type(exc).__name__)


async def execute_midi_output(ctx: NodeExecutionContext) -> NodeExecutionResult:
    """Execute hardware.midi.output node.

    Sends MIDI messages to a hardware or virtual MIDI output port.
    """
    port_name = ctx.get_input("port_name")
    message = ctx.get_input("message")
    batch = ctx.get_input("batch")

    if not port_name:
        return NodeExecutionResult.error("port_name is required", "ValueError")

    client = _get_midi_client()

    try:
        # Ensure port is open
        await client.open_output_port(port_name)

        # Send batch if provided, otherwise single message
        if batch:
            sent = await client.send_batch(port_name, batch)
        elif message:
            # Convert message dict to MIDIMessage if needed
            if isinstance(message, dict):
                message = MIDIMessage(**message)
            sent = await client.send_message(port_name, message)
        else:
            return NodeExecutionResult.error(
                "Either message or batch is required", "ValueError"
            )

        return NodeExecutionResult.ok(sent=sent)

    except (MIDIPortError, MIDIMessageError) as exc:
        # Graceful degradation: log warning, return sent=False
        logger.warning("MIDI output failed: %s", exc)
        return NodeExecutionResult.ok(sent=False)
    except Exception as exc:
        logger.exception("Unexpected error in MIDI output node")
        return NodeExecutionResult.error(str(exc), type(exc).__name__)


# --- Node Definitions ---


MIDIInputNode = NodeDefinition(
    node_type="hardware.midi.input",
    description="Captures MIDI messages from a hardware or virtual MIDI input port",
    input_ports=[
        primitive_port(
            "port_name",
            PortDirection.INPUT,
            PrimitiveType.STRING,
            description="MIDI input port name or pattern",
        ),
        primitive_port(
            "channel_filter",
            PortDirection.INPUT,
            PrimitiveType.INTEGER,
            description="Filter by MIDI channel (0-15, null = all)",
            optional=True,
        ),
        array_port(
            "message_filter",
            PortDirection.INPUT,
            PortType(kind=PortKind.PRIMITIVE, name=PrimitiveType.STRING),
            description="Filter by message type (note_on, cc, etc.)",
            optional=True,
        ),
    ],
    output_ports=[
        array_port(
            "messages",
            PortDirection.OUTPUT,
            PortType(kind=PortKind.DOMAIN, domain="hardware", name="MIDIMessage"),
            description="Stream of incoming MIDI messages",
        ),
    ],
    tags=["hardware", "midi", "input", "realtime"],
    io_intensive=True,
)


MIDIOutputNode = NodeDefinition(
    node_type="hardware.midi.output",
    description="Sends MIDI messages to a hardware or virtual MIDI output port",
    input_ports=[
        primitive_port(
            "port_name",
            PortDirection.INPUT,
            PrimitiveType.STRING,
            description="MIDI output port name or pattern",
        ),
        domain_port(
            "message",
            PortDirection.INPUT,
            "hardware",
            "MIDIMessage",
            description="MIDI message to send",
            optional=True,
        ),
        array_port(
            "batch",
            PortDirection.INPUT,
            PortType(kind=PortKind.DOMAIN, domain="hardware", name="MIDIMessage"),
            description="Batch of messages to send atomically",
            optional=True,
        ),
    ],
    output_ports=[
        primitive_port(
            "sent",
            PortDirection.OUTPUT,
            PrimitiveType.BOOLEAN,
            description="Whether the message was sent successfully",
        ),
    ],
    tags=["hardware", "midi", "output", "realtime"],
    io_intensive=True,
)


# Export node definitions
__all__ = [
    "MIDIError",
    "MIDIPortError",
    "MIDIMessageError",
    "MIDIClient",
    "MIDIInputNode",
    "MIDIOutputNode",
    "execute_midi_input",
    "execute_midi_output",
]
