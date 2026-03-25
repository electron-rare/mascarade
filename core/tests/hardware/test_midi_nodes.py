"""Tests for MIDI nodes with virtual ports."""

from __future__ import annotations

import asyncio
import time

from pydantic import ValidationError

from mascarade.hardware.nodes.midi import (
    MIDIClient,
    MIDIError,
    MIDIMessageError,
    MIDIPortError,
    execute_midi_input,
    execute_midi_output,
)
from mascarade.hardware.types import MIDIMessage, MIDIStatus
from mascarade.node_engine.base import NodeExecutionContext

# --- MIDIClient Tests ---


def test_midi_client_initialization():
    """MIDIClient initializes in mock mode."""
    client = MIDIClient()

    assert client._mock_mode is True
    assert client._input_ports == {}
    assert client._output_ports == {}


async def test_midi_client_list_input_ports_mock():
    """MIDIClient.list_input_ports returns mock ports."""
    client = MIDIClient()

    try:
        ports = await client.list_input_ports()
        assert ports == ["Mock MIDI Input"]
    finally:
        await client.close()


async def test_midi_client_list_output_ports_mock():
    """MIDIClient.list_output_ports returns mock ports."""
    client = MIDIClient()

    try:
        ports = await client.list_output_ports()
        assert ports == ["Mock MIDI Output"]
    finally:
        await client.close()


async def test_midi_client_open_input_port():
    """MIDIClient.open_input_port succeeds in mock mode."""
    client = MIDIClient()

    try:
        await client.open_input_port("Mock MIDI Input")
        assert "Mock MIDI Input" in client._input_ports
    finally:
        await client.close()


async def test_midi_client_open_output_port():
    """MIDIClient.open_output_port succeeds in mock mode."""
    client = MIDIClient()

    try:
        await client.open_output_port("Mock MIDI Output")
        assert "Mock MIDI Output" in client._output_ports
    finally:
        await client.close()


async def test_midi_client_read_messages_mock():
    """MIDIClient.read_messages returns empty list in mock mode."""
    client = MIDIClient()

    try:
        await client.open_input_port("Mock MIDI Input")
        messages = await client.read_messages("Mock MIDI Input")
        assert messages == []
    finally:
        await client.close()


async def test_midi_client_read_messages_with_filters():
    """MIDIClient.read_messages accepts filter parameters."""
    client = MIDIClient()

    try:
        await client.open_input_port("Mock MIDI Input")
        messages = await client.read_messages(
            "Mock MIDI Input",
            channel_filter=0,
            message_filter=["note_on", "control_change"],
        )
        assert messages == []
    finally:
        await client.close()


async def test_midi_client_send_message_mock():
    """MIDIClient.send_message returns False in mock mode."""
    client = MIDIClient()

    try:
        await client.open_output_port("Mock MIDI Output")

        message = MIDIMessage(
            status=MIDIStatus.NOTE_ON,
            channel=0,
            data1=60,  # Middle C
            data2=100,  # Velocity
            timestamp_ms=int(time.time() * 1000),
        )

        sent = await client.send_message("Mock MIDI Output", message)
        assert sent is False  # Mock mode returns False
    finally:
        await client.close()


async def test_midi_client_send_message_note_off():
    """MIDIClient.send_message handles NOTE_OFF messages."""
    client = MIDIClient()

    try:
        await client.open_output_port("Mock MIDI Output")

        message = MIDIMessage(
            status=MIDIStatus.NOTE_OFF,
            channel=0,
            data1=60,
            data2=0,
            timestamp_ms=int(time.time() * 1000),
        )

        sent = await client.send_message("Mock MIDI Output", message)
        assert sent is False  # Mock mode
    finally:
        await client.close()


async def test_midi_client_send_message_control_change():
    """MIDIClient.send_message handles CONTROL_CHANGE messages."""
    client = MIDIClient()

    try:
        await client.open_output_port("Mock MIDI Output")

        message = MIDIMessage(
            status=MIDIStatus.CONTROL_CHANGE,
            channel=0,
            data1=7,  # Volume CC
            data2=127,  # Max volume
            timestamp_ms=int(time.time() * 1000),
        )

        sent = await client.send_message("Mock MIDI Output", message)
        assert sent is False  # Mock mode
    finally:
        await client.close()


async def test_midi_client_send_batch():
    """MIDIClient.send_batch sends multiple messages."""
    client = MIDIClient()

    try:
        await client.open_output_port("Mock MIDI Output")

        messages = [
            MIDIMessage(
                status=MIDIStatus.NOTE_ON,
                channel=0,
                data1=60,
                data2=100,
                timestamp_ms=int(time.time() * 1000),
            ),
            MIDIMessage(
                status=MIDIStatus.NOTE_ON,
                channel=0,
                data1=64,
                data2=100,
                timestamp_ms=int(time.time() * 1000),
            ),
            MIDIMessage(
                status=MIDIStatus.NOTE_ON,
                channel=0,
                data1=67,
                data2=100,
                timestamp_ms=int(time.time() * 1000),
            ),
        ]

        success = await client.send_batch("Mock MIDI Output", messages)
        assert success is True
    finally:
        await client.close()


async def test_midi_client_send_batch_empty():
    """MIDIClient.send_batch handles empty list."""
    client = MIDIClient()

    try:
        await client.open_output_port("Mock MIDI Output")
        success = await client.send_batch("Mock MIDI Output", [])
        assert success is True
    finally:
        await client.close()


async def test_midi_client_close():
    """MIDIClient.close clears all ports."""
    client = MIDIClient()

    await client.open_input_port("Mock MIDI Input")
    await client.open_output_port("Mock MIDI Output")

    assert len(client._input_ports) > 0
    assert len(client._output_ports) > 0

    await client.close()

    assert client._input_ports == {}
    assert client._output_ports == {}


# --- MIDIMessage Tests ---


def test_midi_message_creation():
    """MIDIMessage can be created with valid parameters."""
    message = MIDIMessage(
        status=MIDIStatus.NOTE_ON,
        channel=5,
        data1=60,
        data2=100,
        timestamp_ms=1234567890,
    )

    assert message.status == MIDIStatus.NOTE_ON
    assert message.channel == 5
    assert message.data1 == 60
    assert message.data2 == 100
    assert message.timestamp_ms == 1234567890


def test_midi_message_type_property():
    """MIDIMessage.message_type extracts type from status byte."""
    message = MIDIMessage(
        status=MIDIStatus.NOTE_ON | 0x05,  # NOTE_ON on channel 5
        channel=5,
        data1=60,
        data2=100,
    )

    assert message.message_type == MIDIStatus.NOTE_ON


def test_midi_message_channel_validation():
    """MIDIMessage validates channel range."""
    try:
        MIDIMessage(
            status=MIDIStatus.NOTE_ON,
            channel=16,  # Invalid, must be 0-15
            data1=60,
            data2=100,
        )
        assert False, "Should have raised ValidationError"
    except ValidationError:
        pass


def test_midi_message_data_validation():
    """MIDIMessage validates data byte range."""
    try:
        MIDIMessage(
            status=MIDIStatus.NOTE_ON,
            channel=0,
            data1=128,  # Invalid, must be 0-127
            data2=100,
        )
        assert False, "Should have raised ValidationError"
    except ValidationError:
        pass


def test_midi_message_defaults():
    """MIDIMessage uses default values."""
    message = MIDIMessage(status=MIDIStatus.NOTE_ON)

    assert message.channel == 0
    assert message.data1 == 0
    assert message.data2 == 0
    assert message.timestamp_ms == 0


# --- Node Execution Tests ---


def test_execute_midi_input_success():
    """execute_midi_input returns empty messages in mock mode."""

    class _FakeContext(NodeExecutionContext):
        def __init__(self):
            self._inputs = {"port_name": "Mock MIDI Input"}

        def get_input(self, name, default=None):
            return self._inputs.get(name, default)

    context = _FakeContext()
    result = asyncio.run(execute_midi_input(context))

    assert result.success is True
    assert result.outputs.get("messages") == []


def test_execute_midi_input_with_filters():
    """execute_midi_input accepts channel and message filters."""

    class _FakeContext(NodeExecutionContext):
        def __init__(self):
            self._inputs = {
                "port_name": "Mock MIDI Input",
                "channel_filter": 0,
                "message_filter": ["note_on", "note_off"],
            }

        def get_input(self, name, default=None):
            return self._inputs.get(name, default)

    context = _FakeContext()
    result = asyncio.run(execute_midi_input(context))

    assert result.success is True
    assert result.outputs.get("messages") == []


def test_execute_midi_input_missing_port_name():
    """execute_midi_input returns error when port_name missing."""

    class _FakeContext(NodeExecutionContext):
        def __init__(self):
            self._inputs = {}

        def get_input(self, name, default=None):
            return self._inputs.get(name, default)

    context = _FakeContext()
    result = asyncio.run(execute_midi_input(context))

    assert result.success is False
    assert "port_name is required" in result.error_message


def test_execute_midi_output_single_message():
    """execute_midi_output sends a single message."""

    class _FakeContext(NodeExecutionContext):
        def __init__(self):
            self._inputs = {
                "port_name": "Mock MIDI Output",
                "message": {
                    "status": MIDIStatus.NOTE_ON,
                    "channel": 0,
                    "data1": 60,
                    "data2": 100,
                    "timestamp_ms": 0,
                },
            }

        def get_input(self, name, default=None):
            return self._inputs.get(name, default)

    context = _FakeContext()
    result = asyncio.run(execute_midi_output(context))

    assert result.success is True
    assert result.outputs.get("sent") is False  # Mock mode returns False


def test_execute_midi_output_batch():
    """execute_midi_output sends a batch of messages."""

    class _FakeContext(NodeExecutionContext):
        def __init__(self):
            self._inputs = {
                "port_name": "Mock MIDI Output",
                "batch": [
                    MIDIMessage(
                        status=MIDIStatus.NOTE_ON, channel=0, data1=60, data2=100
                    ),
                    MIDIMessage(
                        status=MIDIStatus.NOTE_ON, channel=0, data1=64, data2=100
                    ),
                ],
            }

        def get_input(self, name, default=None):
            return self._inputs.get(name, default)

    context = _FakeContext()
    result = asyncio.run(execute_midi_output(context))

    assert result.success is True
    assert result.outputs.get("sent") is True


def test_execute_midi_output_missing_port_name():
    """execute_midi_output returns error when port_name missing."""

    class _FakeContext(NodeExecutionContext):
        def __init__(self):
            self._inputs = {"message": MIDIMessage(status=MIDIStatus.NOTE_ON)}

        def get_input(self, name, default=None):
            return self._inputs.get(name, default)

    context = _FakeContext()
    result = asyncio.run(execute_midi_output(context))

    assert result.success is False
    assert "port_name is required" in result.error_message


def test_execute_midi_output_missing_message_and_batch():
    """execute_midi_output returns error when both message and batch missing."""

    class _FakeContext(NodeExecutionContext):
        def __init__(self):
            self._inputs = {"port_name": "Mock MIDI Output"}

        def get_input(self, name, default=None):
            return self._inputs.get(name, default)

    context = _FakeContext()
    result = asyncio.run(execute_midi_output(context))

    assert result.success is False
    assert "Either message or batch is required" in result.error_message


def test_execute_midi_output_message_as_midi_message():
    """execute_midi_output handles MIDIMessage object directly."""

    class _FakeContext(NodeExecutionContext):
        def __init__(self):
            self._inputs = {
                "port_name": "Mock MIDI Output",
                "message": MIDIMessage(
                    status=MIDIStatus.CONTROL_CHANGE, channel=0, data1=7, data2=127
                ),
            }

        def get_input(self, name, default=None):
            return self._inputs.get(name, default)

    context = _FakeContext()
    result = asyncio.run(execute_midi_output(context))

    assert result.success is True
    assert result.outputs.get("sent") is False  # Mock mode


# --- Error Handling Tests ---


def test_midi_error_inheritance():
    """MIDIError is a RuntimeError subclass."""
    assert issubclass(MIDIError, RuntimeError)


def test_midi_port_error_inheritance():
    """MIDIPortError is a MIDIError subclass."""
    assert issubclass(MIDIPortError, MIDIError)


def test_midi_message_error_inheritance():
    """MIDIMessageError is a MIDIError subclass."""
    assert issubclass(MIDIMessageError, MIDIError)


def test_midi_port_error_message():
    """MIDIPortError can be raised with message."""
    try:
        raise MIDIPortError("Port not found")
    except MIDIPortError as exc:
        assert "Port not found" in str(exc)


def test_midi_message_error_message():
    """MIDIMessageError can be raised with message."""
    try:
        raise MIDIMessageError("Invalid message")
    except MIDIMessageError as exc:
        assert "Invalid message" in str(exc)
