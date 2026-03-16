"""Hardware Runtime Worker — Domain-specific port types.

Registered with the NodeTypeRegistry at worker startup.
"""

from __future__ import annotations

from enum import IntEnum, StrEnum
from typing import Literal

from pydantic import BaseModel, Field


# --- GPIOState ---


class GPIODirection(StrEnum):
    """Direction of GPIO pin data flow."""

    INPUT = "input"
    OUTPUT = "output"


class GPIOPull(StrEnum):
    """GPIO pull resistor configuration."""

    NONE = "none"
    UP = "up"
    DOWN = "down"


class GPIOState(BaseModel):
    """State of a single GPIO pin on a microcontroller."""

    kind: Literal["domain"] = "domain"
    domain: Literal["hardware"] = "hardware"
    name: Literal["GPIOState"] = "GPIOState"

    pin: int = Field(ge=0, le=39, description="GPIO pin number (ESP32: 0-39)")
    direction: GPIODirection = GPIODirection.INPUT
    value: bool = False
    pull: GPIOPull = GPIOPull.NONE
    pwm_duty: float | None = Field(None, ge=0.0, le=1.0, description="PWM duty cycle 0.0-1.0")
    pwm_freq: int | None = Field(None, ge=1, le=40_000_000, description="PWM frequency in Hz")


# --- SensorReading ---


class SensorReading(BaseModel):
    """A timestamped reading from a hardware sensor."""

    kind: Literal["domain"] = "domain"
    domain: Literal["hardware"] = "hardware"
    name: Literal["SensorReading"] = "SensorReading"

    sensor_id: str = Field(description="Unique sensor identifier")
    sensor_type: str = Field(description="Sensor type (temperature, humidity, distance, etc.)")
    value: float = Field(description="Numeric reading value")
    unit: str = Field(description="Unit of measurement (°C, %, mm, lux, etc.)")
    timestamp_ms: int = Field(description="Unix timestamp in milliseconds")
    quality: float = Field(1.0, ge=0.0, le=1.0, description="Reading quality/confidence 0.0-1.0")
    raw: int | None = Field(None, description="Raw ADC value if applicable")


# --- MIDIMessage ---


class MIDIStatus(IntEnum):
    """MIDI message status types."""

    NOTE_OFF = 0x80
    NOTE_ON = 0x90
    POLY_AFTERTOUCH = 0xA0
    CONTROL_CHANGE = 0xB0
    PROGRAM_CHANGE = 0xC0
    CHANNEL_AFTERTOUCH = 0xD0
    PITCH_BEND = 0xE0
    SYSTEM = 0xF0


class MIDIMessage(BaseModel):
    """A single MIDI message."""

    kind: Literal["domain"] = "domain"
    domain: Literal["hardware"] = "hardware"
    name: Literal["MIDIMessage"] = "MIDIMessage"

    status: int = Field(ge=0, le=255, description="MIDI status byte")
    channel: int = Field(0, ge=0, le=15, description="MIDI channel 0-15")
    data1: int = Field(0, ge=0, le=127, description="First data byte")
    data2: int = Field(0, ge=0, le=127, description="Second data byte")
    timestamp_ms: int = Field(0, description="Timestamp in milliseconds")

    @property
    def message_type(self) -> MIDIStatus:
        """Get the MIDI message type from status byte."""
        return MIDIStatus(self.status & 0xF0)


# --- DMXFrame ---


class DMXFrame(BaseModel):
    """A single DMX512 frame (up to 512 channels per universe)."""

    kind: Literal["domain"] = "domain"
    domain: Literal["hardware"] = "hardware"
    name: Literal["DMXFrame"] = "DMXFrame"

    universe: int = Field(0, ge=0, le=32767, description="DMX universe number")
    channels: list[int] = Field(
        default_factory=lambda: [0] * 512,
        description="512 channel values (0-255)",
    )
    priority: int = Field(100, ge=0, le=200, description="sACN priority")
    timestamp_ms: int = Field(0, description="Timestamp in milliseconds")

    def set_channel(self, channel: int, value: int) -> None:
        """Set a specific DMX channel value.

        Args:
            channel: DMX channel number (1-512)
            value: Channel value (0-255)

        Raises:
            ValueError: If channel or value is out of range
        """
        if not (1 <= channel <= 512):
            raise ValueError(f"DMX channel must be 1-512, got {channel}")
        if not (0 <= value <= 255):
            raise ValueError(f"DMX value must be 0-255, got {value}")
        self.channels[channel - 1] = value


# --- SerialData ---


class SerialParity(StrEnum):
    """Serial port parity configuration."""

    NONE = "none"
    EVEN = "even"
    ODD = "odd"


class SerialData(BaseModel):
    """A chunk of serial communication data."""

    kind: Literal["domain"] = "domain"
    domain: Literal["hardware"] = "hardware"
    name: Literal["SerialData"] = "SerialData"

    port: str = Field(description="Serial port identifier (e.g., /dev/ttyUSB0)")
    data: str = Field(description="Base64-encoded byte payload")
    baud_rate: int = Field(115200, description="Baud rate")
    parity: SerialParity = SerialParity.NONE
    stop_bits: float = Field(1.0, description="Stop bits (1, 1.5, 2)")
    timestamp_ms: int = Field(0, description="Timestamp in milliseconds")


# --- HardwareDeviceDescriptor ---


class HardwareDeviceDescriptor(BaseModel):
    """Descriptor reported by a discovered hardware device."""

    device_id: str = Field(description="Unique device identifier")
    device_type: str = Field(description="Device type (esp32, midi_interface, dmx_adapter, etc.)")
    hostname: str = Field(description="Network hostname or IP")
    port: int = Field(description="Primary communication port")
    protocols: list[str] = Field(description="Supported protocols (http, ws, mqtt, serial)")
    capabilities: list[str] = Field(description="Device capabilities (gpio, sensor, ota, etc.)")
    firmware_version: str | None = Field(None, description="Current firmware version")
    last_seen_ms: int = Field(description="Last seen timestamp in milliseconds")
    online: bool = Field(True, description="Whether device is currently reachable")


# DomainType registration entries for the NodeTypeRegistry
HARDWARE_DOMAIN_TYPES = [
    {
        "kind": "domain",
        "domain": "hardware",
        "name": "GPIOState",
        "schema": GPIOState.model_json_schema(),
    },
    {
        "kind": "domain",
        "domain": "hardware",
        "name": "SensorReading",
        "schema": SensorReading.model_json_schema(),
    },
    {
        "kind": "domain",
        "domain": "hardware",
        "name": "MIDIMessage",
        "schema": MIDIMessage.model_json_schema(),
    },
    {
        "kind": "domain",
        "domain": "hardware",
        "name": "DMXFrame",
        "schema": DMXFrame.model_json_schema(),
    },
    {
        "kind": "domain",
        "domain": "hardware",
        "name": "SerialData",
        "schema": SerialData.model_json_schema(),
    },
]
