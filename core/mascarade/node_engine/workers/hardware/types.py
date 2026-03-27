"""Hardware domain types for the node engine.

Types pour ESP32 GPIO, capteurs, DMX frames et serial I/O.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class GPIODirection(str, Enum):
    """Direction d'un pin GPIO."""

    INPUT = "input"
    OUTPUT = "output"


class GPIOPull(str, Enum):
    """Pull-up/pull-down configuration."""

    NONE = "none"
    UP = "up"
    DOWN = "down"


@dataclass
class GPIOState:
    """State of a single GPIO pin on a device."""

    pin: int
    value: int  # 0 or 1 for digital, 0-4095 for ADC
    direction: GPIODirection = GPIODirection.INPUT
    pull: GPIOPull = GPIOPull.NONE
    analog: bool = False
    device_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "pin": self.pin,
            "value": self.value,
            "direction": self.direction.value,
            "pull": self.pull.value,
            "analog": self.analog,
            "device_id": self.device_id,
        }


@dataclass
class SensorReading:
    """Lecture d'un capteur (temperature, humidity, etc.)."""

    sensor_type: str  # "temperature", "humidity", "pressure", "light", etc.
    value: float
    unit: str = ""  # "C", "%", "hPa", "lux", etc.
    device_id: str = ""
    pin: int | None = None
    timestamp: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "sensor_type": self.sensor_type,
            "value": self.value,
            "unit": self.unit,
            "device_id": self.device_id,
        }
        if self.pin is not None:
            result["pin"] = self.pin
        if self.timestamp is not None:
            result["timestamp"] = self.timestamp
        if self.metadata:
            result["metadata"] = self.metadata
        return result


@dataclass
class DMXFrame:
    """A single DMX frame — channel values pour un universe."""

    universe_id: str
    channels: dict[int, int] = field(default_factory=dict)  # channel (1-512) -> value (0-255)
    transition_ms: int = 0  # Fade time in milliseconds

    def to_dict(self) -> dict[str, Any]:
        return {
            "universe_id": self.universe_id,
            "channels": self.channels,
            "transition_ms": self.transition_ms,
        }


@dataclass
class SerialData:
    """Data sent/received over a serial port."""

    port: str  # e.g. "/dev/ttyUSB0", "/dev/cu.usbserial-1420"
    data: str | bytes = ""
    baudrate: int = 115200
    encoding: str = "utf-8"
    timeout: float = 5.0
    raw: bool = False  # True = binary mode, False = text mode

    def to_dict(self) -> dict[str, Any]:
        return {
            "port": self.port,
            "data": self.data if isinstance(self.data, str) else self.data.hex(),
            "baudrate": self.baudrate,
            "encoding": self.encoding,
            "timeout": self.timeout,
            "raw": self.raw,
        }


@dataclass
class DeviceDescriptor:
    """Description d'un device hardware decouvert sur le reseau ou en USB."""

    id: str
    name: str
    device_type: str  # "esp32", "dmx", "serial"
    host: str | None = None  # Network address (for ESP32)
    port: int | None = None  # Network port or serial port number
    serial_port: str | None = None  # e.g. "/dev/ttyUSB0"
    available: bool = True
    firmware_version: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "id": self.id,
            "name": self.name,
            "device_type": self.device_type,
            "available": self.available,
        }
        if self.host:
            result["host"] = self.host
        if self.port is not None:
            result["port"] = self.port
        if self.serial_port:
            result["serial_port"] = self.serial_port
        if self.firmware_version:
            result["firmware_version"] = self.firmware_version
        if self.metadata:
            result["metadata"] = self.metadata
        return result
