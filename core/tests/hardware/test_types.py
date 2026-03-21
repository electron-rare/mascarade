"""Tests for hardware domain types — validation and serialization."""

import json

import pytest
from pydantic import ValidationError

from mascarade.hardware.types import (
    DMXFrame,
    GPIODirection,
    GPIOPull,
    GPIOState,
    MIDIMessage,
    MIDIStatus,
    SensorReading,
    SerialData,
    SerialParity,
)


# --- GPIOState Tests ---


def test_gpiostate_defaults():
    """GPIOState initializes with correct defaults."""
    state = GPIOState(pin=5)
    assert state.pin == 5
    assert state.direction == GPIODirection.INPUT
    assert state.value is False
    assert state.pull == GPIOPull.NONE
    assert state.pwm_duty is None
    assert state.pwm_freq is None
    assert state.kind == "domain"
    assert state.domain == "hardware"
    assert state.name == "GPIOState"


def test_gpiostate_output_with_value():
    """GPIOState can be set to output with a value."""
    state = GPIOState(pin=12, direction=GPIODirection.OUTPUT, value=True, pull=GPIOPull.UP)
    assert state.direction == GPIODirection.OUTPUT
    assert state.value is True
    assert state.pull == GPIOPull.UP


def test_gpiostate_pwm_valid():
    """GPIOState accepts valid PWM parameters."""
    state = GPIOState(pin=18, pwm_duty=0.5, pwm_freq=1000)
    assert state.pwm_duty == 0.5
    assert state.pwm_freq == 1000


def test_gpiostate_pin_range_valid():
    """GPIOState accepts pins in valid range 0-39."""
    state_min = GPIOState(pin=0)
    state_max = GPIOState(pin=39)
    assert state_min.pin == 0
    assert state_max.pin == 39


def test_gpiostate_pin_negative_invalid():
    """GPIOState rejects negative pin numbers."""
    try:
        GPIOState(pin=-1)
        assert False, "Should have raised ValidationError"
    except ValidationError:
        pass


def test_gpiostate_pin_too_high_invalid():
    """GPIOState rejects pin numbers > 39."""
    try:
        GPIOState(pin=40)
        assert False, "Should have raised ValidationError"
    except ValidationError:
        pass


def test_gpiostate_pwm_duty_invalid():
    """GPIOState rejects PWM duty cycle outside 0.0-1.0."""
    try:
        GPIOState(pin=5, pwm_duty=1.5)
        assert False, "Should have raised ValidationError"
    except ValidationError:
        pass


def test_gpiostate_pwm_freq_invalid():
    """GPIOState rejects PWM frequency outside valid range."""
    try:
        GPIOState(pin=5, pwm_freq=0)
        assert False, "Should have raised ValidationError"
    except ValidationError:
        pass


def test_gpiostate_serialization():
    """GPIOState serializes to and from JSON correctly."""
    original = GPIOState(
        pin=25,
        direction=GPIODirection.OUTPUT,
        value=True,
        pull=GPIOPull.DOWN,
        pwm_duty=0.75,
        pwm_freq=5000,
    )
    json_str = original.model_dump_json()
    data = json.loads(json_str)

    assert data["pin"] == 25
    assert data["direction"] == "output"
    assert data["value"] is True
    assert data["pull"] == "down"
    assert data["pwm_duty"] == 0.75
    assert data["pwm_freq"] == 5000

    # Deserialize
    restored = GPIOState.model_validate_json(json_str)
    assert restored.pin == original.pin
    assert restored.direction == original.direction
    assert restored.value == original.value
    assert restored.pull == original.pull
    assert restored.pwm_duty == original.pwm_duty
    assert restored.pwm_freq == original.pwm_freq


# --- SensorReading Tests ---


def test_sensorreading_valid():
    """SensorReading initializes with valid data."""
    reading = SensorReading(
        sensor_id="dht22-01",
        sensor_type="temperature",
        value=23.5,
        unit="°C",
        timestamp_ms=1678900000000,
    )
    assert reading.sensor_id == "dht22-01"
    assert reading.sensor_type == "temperature"
    assert reading.value == 23.5
    assert reading.unit == "°C"
    assert reading.timestamp_ms == 1678900000000
    assert reading.quality == 1.0  # default
    assert reading.raw is None  # default


def test_sensorreading_with_quality_and_raw():
    """SensorReading accepts quality and raw values."""
    reading = SensorReading(
        sensor_id="adc-01",
        sensor_type="light",
        value=850.0,
        unit="lux",
        timestamp_ms=1678900000000,
        quality=0.95,
        raw=2048,
    )
    assert reading.quality == 0.95
    assert reading.raw == 2048


def test_sensorreading_quality_range_invalid():
    """SensorReading rejects quality outside 0.0-1.0."""
    try:
        SensorReading(
            sensor_id="test",
            sensor_type="test",
            value=0.0,
            unit="test",
            timestamp_ms=0,
            quality=1.5,
        )
        assert False, "Should have raised ValidationError"
    except ValidationError:
        pass


def test_sensorreading_serialization():
    """SensorReading serializes to and from JSON correctly."""
    original = SensorReading(
        sensor_id="humidity-01",
        sensor_type="humidity",
        value=65.2,
        unit="%",
        timestamp_ms=1678900000000,
        quality=0.98,
        raw=3200,
    )
    json_str = original.model_dump_json()
    data = json.loads(json_str)

    assert data["sensor_id"] == "humidity-01"
    assert data["value"] == 65.2
    assert data["quality"] == 0.98
    assert data["raw"] == 3200

    restored = SensorReading.model_validate_json(json_str)
    assert restored.sensor_id == original.sensor_id
    assert restored.value == original.value
    assert restored.quality == original.quality
    assert restored.raw == original.raw


# --- MIDIMessage Tests ---


def test_midimessage_note_on():
    """MIDIMessage handles NOTE_ON messages."""
    msg = MIDIMessage(
        status=0x90,  # NOTE_ON
        channel=0,
        data1=60,  # Middle C
        data2=127,  # Velocity
        timestamp_ms=1000,
    )
    assert msg.status == 0x90
    assert msg.channel == 0
    assert msg.data1 == 60
    assert msg.data2 == 127
    assert msg.message_type == MIDIStatus.NOTE_ON


def test_midimessage_control_change():
    """MIDIMessage handles CONTROL_CHANGE messages."""
    msg = MIDIMessage(
        status=0xB0,  # CONTROL_CHANGE
        channel=5,
        data1=7,  # Volume
        data2=100,
        timestamp_ms=2000,
    )
    assert msg.message_type == MIDIStatus.CONTROL_CHANGE
    assert msg.channel == 5


def test_midimessage_defaults():
    """MIDIMessage uses correct defaults."""
    msg = MIDIMessage(status=0x80)
    assert msg.channel == 0
    assert msg.data1 == 0
    assert msg.data2 == 0
    assert msg.timestamp_ms == 0


def test_midimessage_status_range_invalid():
    """MIDIMessage rejects status outside 0-255."""
    try:
        MIDIMessage(status=256)
        assert False, "Should have raised ValidationError"
    except ValidationError:
        pass


def test_midimessage_channel_range_invalid():
    """MIDIMessage rejects channel outside 0-15."""
    try:
        MIDIMessage(status=0x90, channel=16)
        assert False, "Should have raised ValidationError"
    except ValidationError:
        pass


def test_midimessage_data_range_invalid():
    """MIDIMessage rejects data bytes outside 0-127."""
    try:
        MIDIMessage(status=0x90, data1=128)
        assert False, "Should have raised ValidationError"
    except ValidationError:
        pass


def test_midimessage_message_type_property():
    """MIDIMessage.message_type extracts type from status byte."""
    note_on = MIDIMessage(status=0x95)  # NOTE_ON channel 5
    assert note_on.message_type == MIDIStatus.NOTE_ON

    pitch_bend = MIDIMessage(status=0xE3)  # PITCH_BEND channel 3
    assert pitch_bend.message_type == MIDIStatus.PITCH_BEND


def test_midimessage_serialization():
    """MIDIMessage serializes to and from JSON correctly."""
    original = MIDIMessage(
        status=0x90,
        channel=10,
        data1=64,
        data2=100,
        timestamp_ms=5000,
    )
    json_str = original.model_dump_json()
    data = json.loads(json_str)

    assert data["status"] == 0x90
    assert data["channel"] == 10
    assert data["data1"] == 64
    assert data["data2"] == 100

    restored = MIDIMessage.model_validate_json(json_str)
    assert restored.status == original.status
    assert restored.channel == original.channel
    assert restored.message_type == original.message_type


# --- DMXFrame Tests ---


def test_dmxframe_defaults():
    """DMXFrame initializes with correct defaults."""
    frame = DMXFrame()
    assert frame.universe == 0
    assert len(frame.channels) == 512
    assert all(ch == 0 for ch in frame.channels)
    assert frame.priority == 100
    assert frame.timestamp_ms == 0


def test_dmxframe_custom_universe():
    """DMXFrame accepts custom universe numbers."""
    frame = DMXFrame(universe=5, priority=150, timestamp_ms=1000)
    assert frame.universe == 5
    assert frame.priority == 150
    assert frame.timestamp_ms == 1000


def test_dmxframe_set_channel_valid():
    """DMXFrame.set_channel sets channel values correctly."""
    frame = DMXFrame()
    frame.set_channel(1, 255)
    frame.set_channel(256, 128)
    frame.set_channel(512, 64)

    assert frame.channels[0] == 255  # Channel 1 -> index 0
    assert frame.channels[255] == 128  # Channel 256 -> index 255
    assert frame.channels[511] == 64  # Channel 512 -> index 511


def test_dmxframe_set_channel_invalid_channel_low():
    """DMXFrame.set_channel rejects channel < 1."""
    frame = DMXFrame()
    try:
        frame.set_channel(0, 100)
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "1-512" in str(e)


def test_dmxframe_set_channel_invalid_channel_high():
    """DMXFrame.set_channel rejects channel > 512."""
    frame = DMXFrame()
    try:
        frame.set_channel(513, 100)
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "1-512" in str(e)


def test_dmxframe_set_channel_invalid_value_low():
    """DMXFrame.set_channel rejects value < 0."""
    frame = DMXFrame()
    try:
        frame.set_channel(1, -1)
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "0-255" in str(e)


def test_dmxframe_set_channel_invalid_value_high():
    """DMXFrame.set_channel rejects value > 255."""
    frame = DMXFrame()
    try:
        frame.set_channel(1, 256)
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "0-255" in str(e)


def test_dmxframe_universe_range_valid():
    """DMXFrame accepts universe in valid range 0-32767."""
    frame_min = DMXFrame(universe=0)
    frame_max = DMXFrame(universe=32767)
    assert frame_min.universe == 0
    assert frame_max.universe == 32767


def test_dmxframe_universe_range_invalid():
    """DMXFrame rejects universe > 32767."""
    try:
        DMXFrame(universe=32768)
        assert False, "Should have raised ValidationError"
    except ValidationError:
        pass


def test_dmxframe_priority_range_invalid():
    """DMXFrame rejects priority outside 0-200."""
    try:
        DMXFrame(priority=201)
        assert False, "Should have raised ValidationError"
    except ValidationError:
        pass


def test_dmxframe_serialization():
    """DMXFrame serializes to and from JSON correctly."""
    original = DMXFrame(universe=10, priority=120, timestamp_ms=3000)
    original.set_channel(1, 255)
    original.set_channel(100, 128)

    json_str = original.model_dump_json()
    data = json.loads(json_str)

    assert data["universe"] == 10
    assert data["priority"] == 120
    assert len(data["channels"]) == 512
    assert data["channels"][0] == 255
    assert data["channels"][99] == 128

    restored = DMXFrame.model_validate_json(json_str)
    assert restored.universe == original.universe
    assert restored.channels == original.channels


# --- SerialData Tests ---


def test_serialdata_valid():
    """SerialData initializes with valid data."""
    data = SerialData(
        port="/dev/ttyUSB0",
        data="SGVsbG8gV29ybGQ=",  # "Hello World" in base64
        baud_rate=9600,
        parity=SerialParity.EVEN,
        stop_bits=1.0,
        timestamp_ms=1000,
    )
    assert data.port == "/dev/ttyUSB0"
    assert data.data == "SGVsbG8gV29ybGQ="
    assert data.baud_rate == 9600
    assert data.parity == SerialParity.EVEN
    assert data.stop_bits == 1.0
    assert data.timestamp_ms == 1000


def test_serialdata_defaults():
    """SerialData uses correct defaults."""
    data = SerialData(port="/dev/ttyS0", data="dGVzdA==")
    assert data.baud_rate == 115200
    assert data.parity == SerialParity.NONE
    assert data.stop_bits == 1.0
    assert data.timestamp_ms == 0


def test_serialdata_parity_options():
    """SerialData accepts all parity options."""
    data_none = SerialData(port="/dev/ttyUSB0", data="test", parity=SerialParity.NONE)
    data_even = SerialData(port="/dev/ttyUSB0", data="test", parity=SerialParity.EVEN)
    data_odd = SerialData(port="/dev/ttyUSB0", data="test", parity=SerialParity.ODD)

    assert data_none.parity == SerialParity.NONE
    assert data_even.parity == SerialParity.EVEN
    assert data_odd.parity == SerialParity.ODD


def test_serialdata_serialization():
    """SerialData serializes to and from JSON correctly."""
    original = SerialData(
        port="/dev/ttyACM0",
        data="QUJDREVG",
        baud_rate=57600,
        parity=SerialParity.ODD,
        stop_bits=2.0,
        timestamp_ms=2500,
    )
    json_str = original.model_dump_json()
    data = json.loads(json_str)

    assert data["port"] == "/dev/ttyACM0"
    assert data["data"] == "QUJDREVG"
    assert data["baud_rate"] == 57600
    assert data["parity"] == "odd"
    assert data["stop_bits"] == 2.0

    restored = SerialData.model_validate_json(json_str)
    assert restored.port == original.port
    assert restored.data == original.data
    assert restored.baud_rate == original.baud_rate
    assert restored.parity == original.parity
    assert restored.stop_bits == original.stop_bits


# --- Domain Type Metadata Tests ---


def test_all_types_have_domain_metadata():
    """All hardware types have correct domain metadata."""
    types_to_test = [
        GPIOState(pin=0),
        SensorReading(sensor_id="test", sensor_type="test", value=0, unit="test", timestamp_ms=0),
        MIDIMessage(status=0x90),
        DMXFrame(),
        SerialData(port="test", data="test"),
    ]

    for obj in types_to_test:
        assert obj.kind == "domain"
        assert obj.domain == "hardware"
        assert obj.name in ["GPIOState", "SensorReading", "MIDIMessage", "DMXFrame", "SerialData"]
