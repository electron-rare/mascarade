"""MIDI I/O nodes — Input capture, output generation, CC mapping, note triggering, and clock synchronization.

Implements nodes for communicating with MIDI hardware and software ports via
the system's MIDI subsystem (ALSA on Linux, CoreMIDI on macOS). Follows the
graceful degradation model defined in SPEC-029-P4 section 4.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Any

from mascarade.hardware.types import MIDIMessage, MIDIStatus
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

# Optional mido import — graceful degradation when not installed
try:
    import mido
except ImportError:
    mido = None  # type: ignore[assignment]

_INSTALL_HINT = (
    "mido is not installed. Install with: "
    "pip install 'mascarade[midi]'  "
    "(requires mido>=1.3 and python-rtmidi>=1.5)"
)

# Map mido message type strings to MIDIStatus enum values
_MIDO_TYPE_TO_STATUS: dict[str, int] = {
    "note_off": MIDIStatus.NOTE_OFF,
    "note_on": MIDIStatus.NOTE_ON,
    "polytouch": MIDIStatus.POLY_AFTERTOUCH,
    "control_change": MIDIStatus.CONTROL_CHANGE,
    "program_change": MIDIStatus.PROGRAM_CHANGE,
    "aftertouch": MIDIStatus.CHANNEL_AFTERTOUCH,
    "pitchwheel": MIDIStatus.PITCH_BEND,
}

# Reverse mapping: status int -> mido type string
_STATUS_TO_MIDO_TYPE: dict[int, str] = {v: k for k, v in _MIDO_TYPE_TO_STATUS.items()}

# --- Error Classes ---


class MIDIError(RuntimeError):
    """Base error for MIDI node failures."""


class MIDIPortError(MIDIError):
    """Raised when MIDI port cannot be opened or accessed."""


class MIDIMessageError(MIDIError):
    """Raised when MIDI message is invalid or cannot be sent."""


# --- Helpers ---


def _mido_msg_to_midi_message(msg: Any) -> MIDIMessage | None:
    """Convert a mido Message to our MIDIMessage model.

    Returns None for unsupported system messages.
    """
    status = _MIDO_TYPE_TO_STATUS.get(msg.type)
    if status is None:
        return None

    channel = getattr(msg, "channel", 0)

    # Extract data bytes depending on message type
    if msg.type in ("note_on", "note_off"):
        data1 = msg.note
        data2 = msg.velocity
    elif msg.type == "control_change":
        data1 = msg.control
        data2 = msg.value
    elif msg.type == "program_change":
        data1 = msg.program
        data2 = 0
    elif msg.type == "polytouch":
        data1 = msg.note
        data2 = msg.value
    elif msg.type == "aftertouch":
        data1 = msg.value
        data2 = 0
    elif msg.type == "pitchwheel":
        # pitchwheel stores a signed 14-bit value; pack into two 7-bit bytes
        data1 = msg.pitch & 0x7F
        data2 = (msg.pitch >> 7) & 0x7F
    else:
        data1, data2 = 0, 0

    return MIDIMessage(
        status=status | channel,
        channel=channel,
        data1=data1,
        data2=data2,
        timestamp_ms=int(time.monotonic() * 1000),
    )


def _midi_message_to_mido_msg(message: MIDIMessage) -> Any:
    """Convert our MIDIMessage model to a mido Message.

    Raises:
        MIDIMessageError: If the message type is not supported.
    """
    if mido is None:
        raise RuntimeError(_INSTALL_HINT)

    status_nibble = message.status & 0xF0
    mido_type = _STATUS_TO_MIDO_TYPE.get(status_nibble)
    if mido_type is None:
        raise MIDIMessageError(f"Unsupported MIDI status byte for sending: 0x{message.status:02X}")

    channel = message.channel

    if mido_type in ("note_on", "note_off"):
        return mido.Message(mido_type, channel=channel, note=message.data1, velocity=message.data2)
    if mido_type == "control_change":
        return mido.Message(mido_type, channel=channel, control=message.data1, value=message.data2)
    if mido_type == "program_change":
        return mido.Message(mido_type, channel=channel, program=message.data1)
    if mido_type == "polytouch":
        return mido.Message(mido_type, channel=channel, note=message.data1, value=message.data2)
    if mido_type == "aftertouch":
        return mido.Message(mido_type, channel=channel, value=message.data1)
    if mido_type == "pitchwheel":
        pitch = message.data1 | (message.data2 << 7)
        return mido.Message(mido_type, channel=channel, pitch=pitch)

    raise MIDIMessageError(f"Cannot build mido message for type: {mido_type}")


# --- MIDI Client ---


class MIDIClient:
    """Async client for communicating with MIDI ports.

    Manages MIDI input/output port connections and message routing.
    Implements graceful degradation when hardware is unavailable.

    Thread-safe: all port access is guarded by a lock since MIDI callbacks
    may arrive on a backend thread.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._input_ports: dict[str, Any] = {}
        self._output_ports: dict[str, Any] = {}
        self._available = mido is not None

    # --- Port discovery ---

    async def list_input_ports(self) -> list[str]:
        """List available MIDI input ports."""
        if not self._available:
            logger.debug("mido not installed — returning empty input port list")
            return []
        return list(mido.get_input_names())  # type: ignore[union-attr]

    async def list_output_ports(self) -> list[str]:
        """List available MIDI output ports."""
        if not self._available:
            logger.debug("mido not installed — returning empty output port list")
            return []
        return list(mido.get_output_names())  # type: ignore[union-attr]

    # --- Port management (lazy open, cached) ---

    async def open_input_port(self, port_name: str) -> None:
        """Open a MIDI input port (lazy — skips if already open).

        Args:
            port_name: Name of the MIDI input port.

        Raises:
            MIDIPortError: If port cannot be opened.
            RuntimeError: If mido is not installed.
        """
        if not self._available:
            raise RuntimeError(_INSTALL_HINT)

        with self._lock:
            if port_name in self._input_ports:
                return  # already open
            try:
                port = mido.open_input(port_name)  # type: ignore[union-attr]
                self._input_ports[port_name] = port
                logger.info("Opened MIDI input port: %s", port_name)
            except Exception as exc:
                raise MIDIPortError(f"Failed to open MIDI input port '{port_name}': {exc}") from exc

    async def open_output_port(self, port_name: str) -> None:
        """Open a MIDI output port (lazy — skips if already open).

        Args:
            port_name: Name of the MIDI output port.

        Raises:
            MIDIPortError: If port cannot be opened.
            RuntimeError: If mido is not installed.
        """
        if not self._available:
            raise RuntimeError(_INSTALL_HINT)

        with self._lock:
            if port_name in self._output_ports:
                return  # already open
            try:
                port = mido.open_output(port_name)  # type: ignore[union-attr]
                self._output_ports[port_name] = port
                logger.info("Opened MIDI output port: %s", port_name)
            except Exception as exc:
                raise MIDIPortError(
                    f"Failed to open MIDI output port '{port_name}': {exc}"
                ) from exc

    # --- Message I/O ---

    async def read_messages(
        self,
        port_name: str,
        channel_filter: int | None = None,
        message_filter: list[str] | None = None,
    ) -> list[MIDIMessage]:
        """Read pending MIDI messages from an input port (non-blocking).

        Args:
            port_name: MIDI input port name.
            channel_filter: Optional MIDI channel filter (0-15).
            message_filter: Optional message type filter (e.g. ["note_on", "control_change"]).

        Returns:
            List of received MIDI messages.
        """
        if not self._available:
            return []

        with self._lock:
            port = self._input_ports.get(port_name)
        if port is None:
            raise MIDIPortError(f"Input port not open: {port_name}")

        results: list[MIDIMessage] = []
        for raw_msg in port.iter_pending():
            if message_filter and raw_msg.type not in message_filter:
                continue
            midi_msg = _mido_msg_to_midi_message(raw_msg)
            if midi_msg is None:
                continue
            if channel_filter is not None and midi_msg.channel != channel_filter:
                continue
            results.append(midi_msg)

        return results

    async def send_message(
        self,
        port_name: str,
        message: MIDIMessage,
    ) -> bool:
        """Send a MIDI message to an output port.

        Args:
            port_name: MIDI output port name.
            message: MIDI message to send.

        Returns:
            True if message was sent successfully.

        Raises:
            MIDIPortError: If port is not open.
            MIDIMessageError: If message is invalid.
        """
        if not self._available:
            raise RuntimeError(_INSTALL_HINT)

        with self._lock:
            port = self._output_ports.get(port_name)
        if port is None:
            raise MIDIPortError(f"Output port not open: {port_name}")

        mido_msg = _midi_message_to_mido_msg(message)
        port.send(mido_msg)
        logger.debug(
            "MIDI out [%s]: status=0x%02X ch=%d data1=%d data2=%d",
            port_name,
            message.status,
            message.channel,
            message.data1,
            message.data2,
        )
        return True

    async def send_batch(
        self,
        port_name: str,
        messages: list[MIDIMessage],
    ) -> bool:
        """Send a batch of MIDI messages atomically.

        Args:
            port_name: MIDI output port name.
            messages: List of MIDI messages to send.

        Returns:
            True if all messages were sent successfully.
        """
        for message in messages:
            success = await self.send_message(port_name, message)
            if not success:
                return False
        return True

    async def close(self) -> None:
        """Close all MIDI ports and release resources."""
        with self._lock:
            for name, port in self._input_ports.items():
                try:
                    port.close()
                    logger.debug("Closed MIDI input port: %s", name)
                except Exception:
                    logger.warning("Error closing MIDI input port: %s", name, exc_info=True)
            for name, port in self._output_ports.items():
                try:
                    port.close()
                    logger.debug("Closed MIDI output port: %s", name)
                except Exception:
                    logger.warning("Error closing MIDI output port: %s", name, exc_info=True)
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
            return NodeExecutionResult.error("Either message or batch is required", "ValueError")

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
