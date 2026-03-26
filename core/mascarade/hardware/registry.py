"""Device Registry — registration, discovery, and lifecycle management for hardware devices."""

from __future__ import annotations

import json
import logging
import os
import tempfile
import time
from pathlib import Path

from mascarade.hardware.types import HardwareDeviceDescriptor
from mascarade.metrics.tracker import MetricsTracker

logger = logging.getLogger("mascarade.hardware")

DEFAULT_STORAGE_PATH = Path("data/devices.json")
DEFAULT_TTL_MS = 60_000  # 60 seconds


class DeviceRegistry:
    """Centralized registry for managing discovered hardware devices."""

    def __init__(
        self,
        storage_path: Path | None = DEFAULT_STORAGE_PATH,
        ttl_ms: int = DEFAULT_TTL_MS,
    ) -> None:
        self._devices: dict[str, HardwareDeviceDescriptor] = {}
        self._storage_path = storage_path
        self._ttl_ms = ttl_ms
        self.metrics = MetricsTracker()

    def register(self, device: HardwareDeviceDescriptor) -> None:
        """Register a discovered device in the registry.

        Args:
            device: Device descriptor to register
        """
        device_id = device.device_id
        is_new = device_id not in self._devices

        # Update last_seen_ms to current time
        device.last_seen_ms = int(time.time() * 1000)
        device.online = True

        self._devices[device_id] = device

        if is_new:
            logger.info("Device registered: %s (%s)", device_id, device.device_type)
        else:
            logger.debug("Device updated: %s", device_id)

    def get(self, device_id: str) -> HardwareDeviceDescriptor:
        """Get a device by ID.

        Args:
            device_id: Unique device identifier

        Returns:
            Device descriptor

        Raises:
            KeyError: If device not found
        """
        if device_id not in self._devices:
            raise KeyError(
                f"Device '{device_id}' not found. Available: {list(self._devices.keys())}"
            )
        return self._devices[device_id]

    def list(self, *, online_only: bool = False) -> list[HardwareDeviceDescriptor]:
        """List all registered devices.

        Args:
            online_only: If True, only return devices marked as online

        Returns:
            List of device descriptors
        """
        devices = list(self._devices.values())
        if online_only:
            devices = [d for d in devices if d.online]
        return devices

    def find_by_type(self, device_type: str) -> list[HardwareDeviceDescriptor]:
        """Find devices by type.

        Args:
            device_type: Device type to search for (e.g., "esp32", "midi_interface")

        Returns:
            List of matching device descriptors
        """
        return [d for d in self._devices.values() if d.device_type == device_type]

    def find_by_capability(self, capability: str) -> list[HardwareDeviceDescriptor]:
        """Find devices that have a specific capability.

        Args:
            capability: Capability to search for (e.g., "gpio", "sensor", "ota")

        Returns:
            List of matching device descriptors
        """
        return [d for d in self._devices.values() if capability in d.capabilities]

    def remove(self, device_id: str) -> None:
        """Remove a device from the registry.

        Args:
            device_id: Device identifier to remove
        """
        if device_id in self._devices:
            logger.info("Device removed: %s", device_id)
            self._devices.pop(device_id)

    def mark_offline(self, device_id: str) -> None:
        """Mark a device as offline without removing it.

        Args:
            device_id: Device identifier to mark offline
        """
        if device_id in self._devices:
            self._devices[device_id].online = False
            logger.warning("Device marked offline: %s", device_id)

    def mark_online(self, device_id: str) -> None:
        """Mark a device as online.

        Args:
            device_id: Device identifier to mark online
        """
        if device_id in self._devices:
            self._devices[device_id].online = True
            self._devices[device_id].last_seen_ms = int(time.time() * 1000)
            logger.info("Device marked online: %s", device_id)

    def expire_stale_devices(self) -> list[str]:
        """Mark devices as offline if they haven't been seen within TTL.

        Returns:
            List of device IDs marked offline
        """
        current_time_ms = int(time.time() * 1000)
        expired = []

        for device_id, device in self._devices.items():
            if device.online and (current_time_ms - device.last_seen_ms) > self._ttl_ms:
                device.online = False
                expired.append(device_id)
                logger.warning("Device expired (TTL=%dms): %s", self._ttl_ms, device_id)

        return expired

    def __contains__(self, device_id: str) -> bool:
        return device_id in self._devices

    def __len__(self) -> int:
        return len(self._devices)

    # --- Metrics ---

    def track_device_communication(
        self,
        device_id: str,
        success: bool,
        response_time: float,
    ) -> None:
        """Track communication metrics for a device.

        Args:
            device_id: Device identifier
            success: Whether the communication succeeded
            response_time: Response time in seconds
        """
        self.metrics.track_request(
            provider_name=device_id,
            tokens=0,
            cost=0.0,
            response_time=response_time,
            success=success,
        )

    def device_metrics(self, device_id: str) -> dict:
        """Get metrics for a specific device.

        Args:
            device_id: Device identifier

        Returns:
            Device metrics dictionary
        """
        return self.metrics.get_provider_stats(device_id)

    def metrics_summary(self) -> dict:
        """Get a summary of all device metrics.

        Returns:
            Metrics summary dictionary
        """
        return self.metrics.get_summary()

    def reset_metrics(self) -> None:
        """Reset all device metrics."""
        self.metrics.reset()

    # --- Persistence ---

    def save(self) -> None:
        """Save registered devices to disk."""
        if self._storage_path is None:
            return

        self._storage_path.parent.mkdir(parents=True, exist_ok=True)

        # Convert devices to JSON-serializable format
        devices_data = [device.model_dump() for device in self._devices.values()]

        # Atomic write: write to temp file, then rename
        fd, tmp_path = tempfile.mkstemp(dir=str(self._storage_path.parent), suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(devices_data, f, indent=2, ensure_ascii=False)
            os.replace(tmp_path, str(self._storage_path))
        except BaseException:
            os.unlink(tmp_path)
            raise

    def load(self) -> None:
        """Load registered devices from disk."""
        if self._storage_path is None or not self._storage_path.exists():
            return

        try:
            raw = json.loads(self._storage_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            logger.error("Failed to load devices from %s: %s", self._storage_path, exc)
            return

        for data in raw:
            try:
                device = HardwareDeviceDescriptor(**data)
                self._devices[device.device_id] = device
            except (KeyError, TypeError, ValueError) as exc:
                logger.warning("Skipping invalid device entry: %s", exc)
