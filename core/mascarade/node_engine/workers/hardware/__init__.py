"""Hardware domain worker for mascarade node engine.

Handles ESP32 GPIO/sensors, DMX lighting control, and serial I/O
for embedded hardware integration.
"""

from __future__ import annotations

HARDWARE_DOMAIN_TYPES = [
    "hardware.esp32.discover",
    "hardware.esp32.gpio_read",
    "hardware.esp32.gpio_write",
    "hardware.esp32.sensor_read",
    "hardware.esp32.ota_update",
    "hardware.dmx.universe_create",
    "hardware.dmx.fixture_set",
    "hardware.dmx.scene_apply",
    "hardware.serial.send",
    "hardware.serial.receive",
]

from mascarade.node_engine.workers.hardware.worker import HardwareWorker

__all__ = ["HARDWARE_DOMAIN_TYPES", "HardwareWorker"]
