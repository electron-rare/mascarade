"""Tests for MIDI nodes — graceful degradation and mocked mido operations."""

from __future__ import annotations

import asyncio
import time
from unittest.mock import MagicMock, patch

import pytest
from pydantic import ValidationError

from mascarade.hardware.nodes.midi import (
    MIDIClient,
    MIDIError,
    MIDIMessageError,
    MIDIPortError,
    _midi_message_to_mido_msg,
    _mido_msg_to_midi_message,
    execute_midi_input,
    execute_midi_output,
)
from mascarade.hardware.types import MIDIMessage, MIDIStatus
from mascarade.node_engine.base import NodeExecutionContext

# --- Helpers ---


def _make_context(**inputs) -> NodeExecutionContext:
    """Create a NodeExecutionContext with given inputs."""
    return NodeExecutionContext(inputs=inputs)


@pytest.fixture(autouse=True)
def _reset_global_midi_client():
    """Reset the global _midi_client between tests."""
    import mascarade.hardware.nodes.midi as midi_mod

    midi_mod._midi_client = None
    yield
    midi_mod._midi_client = None


# --- Graceful degradation tests (mido unavailable) ---


def test_midi_client_initialization_without_mido():
    """MIDIClient initializes with _available=False when mido is None."""
    with patch("mascarade.hardware.nodes.midi.mido", None):
        client = MIDIClient()
        assert client._available is False
        assert client._input_ports == {}
        assert client._output_ports == {}


def test_midi_client_list_input_ports_no_mido():
    """list_input_ports returns empty list when mido unavailable."""
    with patch("mascarade.hardware.nodes.midi.mido", None):
        client = MIDIClient()
        ports = asyncio.run(client.list_input_ports())
        assert ports == []


def test_midi_client_list_output_ports_no_mido():
    """list_output_ports returns empty list when mido unavailable."""
    with patch("mascarade.hardware.nodes.midi.mido", None):
        client = MIDIClient()
        ports = asyncio.run(client.list_output_ports())
        assert ports == []


def test_midi_client_open_input_port_no_mido():
    """open_input_port raises RuntimeError when mido unavailable."""
    with patch("mascarade.hardware.nodes.midi.mido", None):
        client = MIDIClient()
        with pytest.raises(RuntimeError, match="mido is not installed"):
            asyncio.run(client.open_input_port("some-port"))


def test_midi_client_open_output_port_no_mido():
    """open_output_port raises RuntimeError when mido unavailable."""
    with patch("mascarade.hardware.nodes.midi.mido", None):
        client = MIDIClient()
        with pytest.raises(RuntimeError, match="mido is not installed"):
            asyncio.run(client.open_output_port("some-port"))


def test_midi_client_read_messages_no_mido():
    """read_messages returns empty list when mido unavailable."""
    with patch("mascarade.hardware.nodes.midi.mido", None):
        client = MIDIClient()
        messages = asyncio.run(client.read_messages("any-port"))
        assert messages == []


def test_midi_client_send_message_no_mido():
    """send_message raises RuntimeError when mido unavailable."""
    with patch("mascarade.hardware.nodes.midi.mido", None):
        client = MIDIClient()
        msg = MIDIMessage(status=MIDIStatus.NOTE_ON, data1=60, data2=100)
        with pytest.raises(RuntimeError, match="mido is not installed"):
            asyncio.run(client.send_message("any-port", msg))


# --- MIDIClient with mocked mido ---


def _make_mock_mido() -> MagicMock:
    """Build a mock mido module with typical port operations."""
    mock_mido = MagicMock()
    mock_mido.get_input_names.return_value = ["IAC Driver Bus 1", "USB MIDI Interface"]
    mock_mido.get_output_names.return_value = ["IAC Driver Bus 1", "USB MIDI Interface"]

    mock_input_port = MagicMock()
    mock_input_port.iter_pending.return_value = []
    mock_mido.open_input.return_value = mock_input_port

    mock_output_port = MagicMock()
    mock_mido.open_output.return_value = mock_output_port

    return mock_mido


def test_midi_client_initialization_with_mido():
    """MIDIClient initializes with _available=True when mido is present."""
    mock_mido = _make_mock_mido()
    with patch("mascarade.hardware.nodes.midi.mido", mock_mido):
        client = MIDIClient()
        assert client._available is True


def test_midi_client_list_input_ports_with_mido():
    """list_input_ports returns port names from mido."""
    mock_mido = _make_mock_mido()
    with patch("mascarade.hardware.nodes.midi.mido", mock_mido):
        client = MIDIClient()
        ports = asyncio.run(client.list_input_ports())
        assert ports == ["IAC Driver Bus 1", "USB MIDI Interface"]
        mock_mido.get_input_names.assert_called_once()


def test_midi_client_list_output_ports_with_mido():
    """list_output_ports returns port names from mido."""
    mock_mido = _make_mock_mido()
    with patch("mascarade.hardware.nodes.midi.mido", mock_mido):
        client = MIDIClient()
        ports = asyncio.run(client.list_output_ports())
        assert ports == ["IAC Driver Bus 1", "USB MIDI Interface"]
        mock_mido.get_output_names.assert_called_once()


def test_midi_client_open_input_port_with_mido():
    """open_input_port opens port via mido and caches it."""
    mock_mido = _make_mock_mido()
    with patch("mascarade.hardware.nodes.midi.mido", mock_mido):
        client = MIDIClient()
        asyncio.run(client.open_input_port("IAC Driver Bus 1"))
        assert "IAC Driver Bus 1" in client._input_ports
        mock_mido.open_input.assert_called_once_with("IAC Driver Bus 1")

        # Opening same port again should not call mido again
        asyncio.run(client.open_input_port("IAC Driver Bus 1"))
        assert mock_mido.open_input.call_count == 1


def test_midi_client_open_output_port_with_mido():
    """open_output_port opens port via mido and caches it."""
    mock_mido = _make_mock_mido()
    with patch("mascarade.hardware.nodes.midi.mido", mock_mido):
        client = MIDIClient()
        asyncio.run(client.open_output_port("IAC Driver Bus 1"))
        assert "IAC Driver Bus 1" in client._output_ports
        mock_mido.open_output.assert_called_once_with("IAC Driver Bus 1")


def test_midi_client_open_input_port_failure():
    """open_input_port raises MIDIPortError when mido raises."""
    mock_mido = _make_mock_mido()
    mock_mido.open_input.side_effect = OSError("device busy")
    with patch("mascarade.hardware.nodes.midi.mido", mock_mido):
        client = MIDIClient()
        with pytest.raises(MIDIPortError, match="Failed to open MIDI input port"):
            asyncio.run(client.open_input_port("bad-port"))


def test_midi_client_open_output_port_failure():
    """open_output_port raises MIDIPortError when mido raises."""
    mock_mido = _make_mock_mido()
    mock_mido.open_output.side_effect = OSError("device busy")
    with patch("mascarade.hardware.nodes.midi.mido", mock_mido):
        client = MIDIClient()
        with pytest.raises(MIDIPortError, match="Failed to open MIDI output port"):
            asyncio.run(client.open_output_port("bad-port"))


def test_midi_client_read_messages_empty():
    """read_messages returns empty list when no pending messages."""
    mock_mido = _make_mock_mido()
    with patch("mascarade.hardware.nodes.midi.mido", mock_mido):
        client = MIDIClient()
        asyncio.run(client.open_input_port("port1"))
        messages = asyncio.run(client.read_messages("port1"))
        assert messages == []


def test_midi_client_read_messages_with_data():
    """read_messages converts mido messages to MIDIMessage objects."""
    mock_mido = _make_mock_mido()

    # Create a fake mido message
    fake_msg = MagicMock()
    fake_msg.type = "note_on"
    fake_msg.channel = 0
    fake_msg.note = 60
    fake_msg.velocity = 100

    mock_input_port = MagicMock()
    mock_input_port.iter_pending.return_value = [fake_msg]
    mock_mido.open_input.return_value = mock_input_port

    with patch("mascarade.hardware.nodes.midi.mido", mock_mido):
        client = MIDIClient()
        asyncio.run(client.open_input_port("port1"))
        messages = asyncio.run(client.read_messages("port1"))
        assert len(messages) == 1
        assert messages[0].data1 == 60
        assert messages[0].data2 == 100
        assert messages[0].channel == 0


def test_midi_client_read_messages_with_channel_filter():
    """read_messages filters by channel."""
    mock_mido = _make_mock_mido()

    fake_msg_ch0 = MagicMock()
    fake_msg_ch0.type = "note_on"
    fake_msg_ch0.channel = 0
    fake_msg_ch0.note = 60
    fake_msg_ch0.velocity = 100

    fake_msg_ch5 = MagicMock()
    fake_msg_ch5.type = "note_on"
    fake_msg_ch5.channel = 5
    fake_msg_ch5.note = 72
    fake_msg_ch5.velocity = 80

    mock_input_port = MagicMock()
    mock_input_port.iter_pending.return_value = [fake_msg_ch0, fake_msg_ch5]
    mock_mido.open_input.return_value = mock_input_port

    with patch("mascarade.hardware.nodes.midi.mido", mock_mido):
        client = MIDIClient()
        asyncio.run(client.open_input_port("port1"))
        messages = asyncio.run(client.read_messages("port1", channel_filter=5))
        assert len(messages) == 1
        assert messages[0].data1 == 72


def test_midi_client_read_messages_with_message_filter():
    """read_messages filters by message type."""
    mock_mido = _make_mock_mido()

    fake_note = MagicMock()
    fake_note.type = "note_on"
    fake_note.channel = 0
    fake_note.note = 60
    fake_note.velocity = 100

    fake_cc = MagicMock()
    fake_cc.type = "control_change"
    fake_cc.channel = 0
    fake_cc.control = 7
    fake_cc.value = 127

    mock_input_port = MagicMock()
    mock_input_port.iter_pending.return_value = [fake_note, fake_cc]
    mock_mido.open_input.return_value = mock_input_port

    with patch("mascarade.hardware.nodes.midi.mido", mock_mido):
        client = MIDIClient()
        asyncio.run(client.open_input_port("port1"))
        messages = asyncio.run(client.read_messages("port1", message_filter=["control_change"]))
        assert len(messages) == 1
        assert messages[0].data1 == 7
        assert messages[0].data2 == 127


def test_midi_client_read_messages_port_not_open():
    """read_messages raises MIDIPortError for unopened port."""
    mock_mido = _make_mock_mido()
    with patch("mascarade.hardware.nodes.midi.mido", mock_mido):
        client = MIDIClient()
        with pytest.raises(MIDIPortError, match="Input port not open"):
            asyncio.run(client.read_messages("nonexistent"))


def test_midi_client_send_message_with_mido():
    """send_message sends via mido output port."""
    mock_mido = _make_mock_mido()
    mock_output_port = MagicMock()
    mock_mido.open_output.return_value = mock_output_port
    mock_mido.Message.return_value = MagicMock()

    with patch("mascarade.hardware.nodes.midi.mido", mock_mido):
        client = MIDIClient()
        asyncio.run(client.open_output_port("port1"))

        msg = MIDIMessage(
            status=MIDIStatus.NOTE_ON,
            channel=0,
            data1=60,
            data2=100,
            timestamp_ms=int(time.time() * 1000),
        )
        sent = asyncio.run(client.send_message("port1", msg))
        assert sent is True
        mock_output_port.send.assert_called_once()


def test_midi_client_send_message_note_off():
    """send_message handles NOTE_OFF messages."""
    mock_mido = _make_mock_mido()
    mock_output_port = MagicMock()
    mock_mido.open_output.return_value = mock_output_port
    mock_mido.Message.return_value = MagicMock()

    with patch("mascarade.hardware.nodes.midi.mido", mock_mido):
        client = MIDIClient()
        asyncio.run(client.open_output_port("port1"))

        msg = MIDIMessage(
            status=MIDIStatus.NOTE_OFF,
            channel=0,
            data1=60,
            data2=0,
            timestamp_ms=int(time.time() * 1000),
        )
        sent = asyncio.run(client.send_message("port1", msg))
        assert sent is True


def test_midi_client_send_message_control_change():
    """send_message handles CONTROL_CHANGE messages."""
    mock_mido = _make_mock_mido()
    mock_output_port = MagicMock()
    mock_mido.open_output.return_value = mock_output_port
    mock_mido.Message.return_value = MagicMock()

    with patch("mascarade.hardware.nodes.midi.mido", mock_mido):
        client = MIDIClient()
        asyncio.run(client.open_output_port("port1"))

        msg = MIDIMessage(
            status=MIDIStatus.CONTROL_CHANGE,
            channel=0,
            data1=7,
            data2=127,
            timestamp_ms=int(time.time() * 1000),
        )
        sent = asyncio.run(client.send_message("port1", msg))
        assert sent is True


def test_midi_client_send_message_port_not_open():
    """send_message raises MIDIPortError for unopened port."""
    mock_mido = _make_mock_mido()
    with patch("mascarade.hardware.nodes.midi.mido", mock_mido):
        client = MIDIClient()
        msg = MIDIMessage(status=MIDIStatus.NOTE_ON, data1=60, data2=100)
        with pytest.raises(MIDIPortError, match="Output port not open"):
            asyncio.run(client.send_message("nonexistent", msg))


def test_midi_client_send_batch_with_mido():
    """send_batch sends multiple messages."""
    mock_mido = _make_mock_mido()
    mock_output_port = MagicMock()
    mock_mido.open_output.return_value = mock_output_port
    mock_mido.Message.return_value = MagicMock()

    with patch("mascarade.hardware.nodes.midi.mido", mock_mido):
        client = MIDIClient()
        asyncio.run(client.open_output_port("port1"))

        messages = [
            MIDIMessage(status=MIDIStatus.NOTE_ON, channel=0, data1=60, data2=100),
            MIDIMessage(status=MIDIStatus.NOTE_ON, channel=0, data1=64, data2=100),
            MIDIMessage(status=MIDIStatus.NOTE_ON, channel=0, data1=67, data2=100),
        ]
        success = asyncio.run(client.send_batch("port1", messages))
        assert success is True
        assert mock_output_port.send.call_count == 3


def test_midi_client_send_batch_empty():
    """send_batch handles empty list."""
    mock_mido = _make_mock_mido()
    with patch("mascarade.hardware.nodes.midi.mido", mock_mido):
        client = MIDIClient()
        asyncio.run(client.open_output_port("port1"))
        success = asyncio.run(client.send_batch("port1", []))
        assert success is True


def test_midi_client_close():
    """close clears all ports and calls close on each."""
    mock_mido = _make_mock_mido()
    mock_in = MagicMock()
    mock_out = MagicMock()
    mock_mido.open_input.return_value = mock_in
    mock_mido.open_output.return_value = mock_out

    with patch("mascarade.hardware.nodes.midi.mido", mock_mido):
        client = MIDIClient()
        asyncio.run(client.open_input_port("in1"))
        asyncio.run(client.open_output_port("out1"))

        assert len(client._input_ports) == 1
        assert len(client._output_ports) == 1

        asyncio.run(client.close())

        assert client._input_ports == {}
        assert client._output_ports == {}
        mock_in.close.assert_called_once()
        mock_out.close.assert_called_once()


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
    with pytest.raises(ValidationError):
        MIDIMessage(
            status=MIDIStatus.NOTE_ON,
            channel=16,  # Invalid, must be 0-15
            data1=60,
            data2=100,
        )


def test_midi_message_data_validation():
    """MIDIMessage validates data byte range."""
    with pytest.raises(ValidationError):
        MIDIMessage(
            status=MIDIStatus.NOTE_ON,
            channel=0,
            data1=128,  # Invalid, must be 0-127
            data2=100,
        )


def test_midi_message_defaults():
    """MIDIMessage uses default values."""
    message = MIDIMessage(status=MIDIStatus.NOTE_ON)

    assert message.channel == 0
    assert message.data1 == 0
    assert message.data2 == 0
    assert message.timestamp_ms == 0


# --- Converter helper tests ---


def test_mido_msg_to_midi_message_note_on():
    """_mido_msg_to_midi_message converts note_on correctly."""
    fake_msg = MagicMock()
    fake_msg.type = "note_on"
    fake_msg.channel = 3
    fake_msg.note = 64
    fake_msg.velocity = 80

    result = _mido_msg_to_midi_message(fake_msg)
    assert result is not None
    assert result.channel == 3
    assert result.data1 == 64
    assert result.data2 == 80


def test_mido_msg_to_midi_message_control_change():
    """_mido_msg_to_midi_message converts control_change correctly."""
    fake_msg = MagicMock()
    fake_msg.type = "control_change"
    fake_msg.channel = 0
    fake_msg.control = 7
    fake_msg.value = 100

    result = _mido_msg_to_midi_message(fake_msg)
    assert result is not None
    assert result.data1 == 7
    assert result.data2 == 100


def test_mido_msg_to_midi_message_unsupported():
    """_mido_msg_to_midi_message returns None for unsupported types."""
    fake_msg = MagicMock()
    fake_msg.type = "sysex"

    result = _mido_msg_to_midi_message(fake_msg)
    assert result is None


def test_midi_message_to_mido_msg_note_on():
    """_midi_message_to_mido_msg converts NOTE_ON correctly."""
    mock_mido = _make_mock_mido()
    mock_mido.Message.return_value = MagicMock()

    with patch("mascarade.hardware.nodes.midi.mido", mock_mido):
        msg = MIDIMessage(status=MIDIStatus.NOTE_ON, channel=0, data1=60, data2=100)
        _midi_message_to_mido_msg(msg)
        mock_mido.Message.assert_called_once_with("note_on", channel=0, note=60, velocity=100)


def test_midi_message_to_mido_msg_no_mido():
    """_midi_message_to_mido_msg raises RuntimeError when mido unavailable."""
    with patch("mascarade.hardware.nodes.midi.mido", None):
        msg = MIDIMessage(status=MIDIStatus.NOTE_ON, data1=60, data2=100)
        with pytest.raises(RuntimeError, match="mido is not installed"):
            _midi_message_to_mido_msg(msg)


# --- Node Execution Tests ---


def test_execute_midi_input_no_mido_graceful():
    """execute_midi_input returns error when mido unavailable (RuntimeError from open_input_port)."""
    with patch("mascarade.hardware.nodes.midi.mido", None):
        ctx = _make_context(port_name="any-port")
        result = asyncio.run(execute_midi_input(ctx))
        # open_input_port raises RuntimeError when mido is None,
        # caught by the generic Exception handler
        assert result.success is False
        assert "mido is not installed" in result.error_message


def test_execute_midi_input_with_mido():
    """execute_midi_input reads messages with mocked mido."""
    mock_mido = _make_mock_mido()
    with patch("mascarade.hardware.nodes.midi.mido", mock_mido):
        ctx = _make_context(port_name="port1")
        result = asyncio.run(execute_midi_input(ctx))
        assert result.success is True
        assert result.outputs.get("messages") == []


def test_execute_midi_input_with_filters():
    """execute_midi_input accepts channel and message filters."""
    mock_mido = _make_mock_mido()
    with patch("mascarade.hardware.nodes.midi.mido", mock_mido):
        ctx = _make_context(
            port_name="port1",
            channel_filter=0,
            message_filter=["note_on", "note_off"],
        )
        result = asyncio.run(execute_midi_input(ctx))
        assert result.success is True
        assert result.outputs.get("messages") == []


def test_execute_midi_input_missing_port_name():
    """execute_midi_input returns error when port_name missing."""
    ctx = _make_context()
    result = asyncio.run(execute_midi_input(ctx))
    assert result.success is False
    assert "port_name is required" in result.error_message


def test_execute_midi_output_single_message_with_mido():
    """execute_midi_output sends a single message with mocked mido."""
    mock_mido = _make_mock_mido()
    mock_mido.Message.return_value = MagicMock()
    with patch("mascarade.hardware.nodes.midi.mido", mock_mido):
        ctx = _make_context(
            port_name="port1",
            message={
                "status": MIDIStatus.NOTE_ON,
                "channel": 0,
                "data1": 60,
                "data2": 100,
                "timestamp_ms": 0,
            },
        )
        result = asyncio.run(execute_midi_output(ctx))
        assert result.success is True
        assert result.outputs.get("sent") is True


def test_execute_midi_output_no_mido_graceful():
    """execute_midi_output returns error when mido unavailable."""
    with patch("mascarade.hardware.nodes.midi.mido", None):
        ctx = _make_context(
            port_name="any-port",
            message=MIDIMessage(status=MIDIStatus.NOTE_ON, data1=60, data2=100),
        )
        result = asyncio.run(execute_midi_output(ctx))
        # open_output_port raises RuntimeError when mido is None,
        # caught by the generic Exception handler
        assert result.success is False
        assert "mido is not installed" in result.error_message


def test_execute_midi_output_batch_with_mido():
    """execute_midi_output sends a batch of messages."""
    mock_mido = _make_mock_mido()
    mock_mido.Message.return_value = MagicMock()
    with patch("mascarade.hardware.nodes.midi.mido", mock_mido):
        ctx = _make_context(
            port_name="port1",
            batch=[
                MIDIMessage(status=MIDIStatus.NOTE_ON, channel=0, data1=60, data2=100),
                MIDIMessage(status=MIDIStatus.NOTE_ON, channel=0, data1=64, data2=100),
            ],
        )
        result = asyncio.run(execute_midi_output(ctx))
        assert result.success is True
        assert result.outputs.get("sent") is True


def test_execute_midi_output_missing_port_name():
    """execute_midi_output returns error when port_name missing."""
    ctx = _make_context(message=MIDIMessage(status=MIDIStatus.NOTE_ON))
    result = asyncio.run(execute_midi_output(ctx))
    assert result.success is False
    assert "port_name is required" in result.error_message


def test_execute_midi_output_missing_message_and_batch():
    """execute_midi_output returns error when both message and batch missing."""
    mock_mido = _make_mock_mido()
    with patch("mascarade.hardware.nodes.midi.mido", mock_mido):
        ctx = _make_context(port_name="port1")
        result = asyncio.run(execute_midi_output(ctx))
        assert result.success is False
        assert "Either message or batch is required" in result.error_message


def test_execute_midi_output_message_as_midi_message():
    """execute_midi_output handles MIDIMessage object directly."""
    mock_mido = _make_mock_mido()
    mock_mido.Message.return_value = MagicMock()
    with patch("mascarade.hardware.nodes.midi.mido", mock_mido):
        ctx = _make_context(
            port_name="port1",
            message=MIDIMessage(status=MIDIStatus.CONTROL_CHANGE, channel=0, data1=7, data2=127),
        )
        result = asyncio.run(execute_midi_output(ctx))
        assert result.success is True
        assert result.outputs.get("sent") is True


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
    with pytest.raises(MIDIPortError, match="Port not found"):
        raise MIDIPortError("Port not found")


def test_midi_message_error_message():
    """MIDIMessageError can be raised with message."""
    with pytest.raises(MIDIMessageError, match="Invalid message"):
        raise MIDIMessageError("Invalid message")
