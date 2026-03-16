"""Hardware Runtime Worker — Core types and interfaces."""

from __future__ import annotations

from mascarade.hardware.types import (
    DMXFrame,
    GPIODirection,
    GPIOPull,
    GPIOState,
    HardwareDeviceDescriptor,
    HARDWARE_DOMAIN_TYPES,
    MIDIMessage,
    MIDIStatus,
    SensorReading,
    SerialData,
    SerialParity,
)
from mascarade.hardware.worker import HardwareWorker

__all__ = [
    "DMXFrame",
    "GPIODirection",
    "GPIOPull",
    "GPIOState",
    "HardwareDeviceDescriptor",
    "HARDWARE_DOMAIN_TYPES",
    "HardwareWorker",
    "MIDIMessage",
    "MIDIStatus",
    "SensorReading",
    "SerialData",
    "SerialParity",
]
