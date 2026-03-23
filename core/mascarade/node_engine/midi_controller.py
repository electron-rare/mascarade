"""MIDI controller backend — JZZ bridge via Node.js subprocess."""

from __future__ import annotations

import asyncio
import logging
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

logger = logging.getLogger("mascarade.node_engine.midi")

# Retryable exceptions for network calls
RETRYABLE_EXCEPTIONS = (ConnectionError, TimeoutError, httpx.HTTPError)


def make_retry(*extra_exceptions: type[BaseException]):
    """Create retry decorator with specific exceptions."""
    return retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type(RETRYABLE_EXCEPTIONS + tuple(extra_exceptions)),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )


@dataclass
class MIDIDevice:
    """MIDI device representation."""

    id: str
    name: str
    manufacturer: str | None = None
    type: str = "output"  # "input" or "output"


@dataclass
class MIDIMessage:
    """MIDI message representation."""

    type: str  # "note_on", "note_off", "cc", "program_change"
    channel: int  # 1-16
    data: dict[str, Any] = field(default_factory=dict)


class MIDIController:
    """MIDI controller backend using JZZ Node.js bridge."""

    def __init__(
        self,
        bridge_url: str = "http://localhost:3333",
        auto_start: bool = True,
    ):
        """
        Initialize MIDI controller.

        Args:
            bridge_url: URL of the JZZ Node.js bridge service
            auto_start: Whether to automatically start the bridge if not running
        """
        self.bridge_url = bridge_url
        self.auto_start = auto_start
        self._process: subprocess.Popen | None = None
        self._client = httpx.AsyncClient(timeout=10.0)

    async def __aenter__(self):
        """Async context manager entry."""
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.stop()

    async def start(self) -> None:
        """Start the MIDI bridge service if not already running."""
        if not self.auto_start:
            return

        # Check if bridge is already running
        try:
            response = await self._client.get(f"{self.bridge_url}/health")
            if response.status_code == 200:
                logger.info("MIDI bridge already running")
                return
        except (httpx.HTTPError, ConnectionError):
            logger.info("MIDI bridge not running, starting...")

        # Start Node.js bridge subprocess
        bridge_script = Path(__file__).parent / "midi_bridge.js"
        if not bridge_script.exists():
            logger.warning(f"MIDI bridge script not found: {bridge_script}")
            logger.warning("MIDI functionality will be unavailable")
            return

        try:
            self._process = subprocess.Popen(
                ["node", str(bridge_script)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            logger.info(f"Started MIDI bridge (PID: {self._process.pid})")

            # Wait for bridge to be ready
            for _ in range(30):  # 3 seconds timeout
                try:
                    response = await self._client.get(f"{self.bridge_url}/health")
                    if response.status_code == 200:
                        logger.info("MIDI bridge ready")
                        return
                except (httpx.HTTPError, ConnectionError):
                    await asyncio.sleep(0.1)

            logger.warning("MIDI bridge started but not responding")
        except FileNotFoundError:
            logger.error("Node.js not found — install Node.js to use MIDI features")
        except Exception as e:
            logger.error(f"Failed to start MIDI bridge: {e}")

    async def stop(self) -> None:
        """Stop the MIDI bridge service."""
        if self._process:
            self._process.terminate()
            try:
                self._process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._process.kill()
            logger.info("MIDI bridge stopped")

        await self._client.aclose()

    @make_retry()
    async def get_devices(self, device_type: str = "output") -> list[MIDIDevice]:
        """
        Get list of available MIDI devices.

        Args:
            device_type: "input" or "output"

        Returns:
            List of MIDI devices
        """
        try:
            response = await self._client.get(
                f"{self.bridge_url}/devices",
                params={"type": device_type},
            )
            response.raise_for_status()
            data = response.json()

            return [
                MIDIDevice(
                    id=device["id"],
                    name=device["name"],
                    manufacturer=device.get("manufacturer"),
                    type=device_type,
                )
                for device in data.get("devices", [])
            ]
        except (httpx.HTTPError, ConnectionError) as e:
            logger.warning(f"Failed to get MIDI devices: {e}")
            return []  # Graceful degradation

    @make_retry()
    async def send_message(
        self,
        device_id: str,
        message: MIDIMessage,
    ) -> dict[str, Any]:
        """
        Send MIDI message to device.

        Args:
            device_id: Target MIDI device ID
            message: MIDI message to send

        Returns:
            Response from bridge service
        """
        try:
            response = await self._client.post(
                f"{self.bridge_url}/send",
                json={
                    "device_id": device_id,
                    "type": message.type,
                    "channel": message.channel,
                    "data": message.data,
                },
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"Failed to send MIDI message: {e}")
            raise

    async def note_on(
        self,
        device_id: str,
        note: int,
        velocity: int = 64,
        channel: int = 1,
    ) -> dict[str, Any]:
        """
        Send MIDI note on message.

        Args:
            device_id: Target MIDI device ID
            note: MIDI note number (0-127)
            velocity: Note velocity (0-127)
            channel: MIDI channel (1-16)
        """
        message = MIDIMessage(
            type="note_on",
            channel=channel,
            data={"note": note, "velocity": velocity},
        )
        return await self.send_message(device_id, message)

    async def note_off(
        self,
        device_id: str,
        note: int,
        channel: int = 1,
    ) -> dict[str, Any]:
        """
        Send MIDI note off message.

        Args:
            device_id: Target MIDI device ID
            note: MIDI note number (0-127)
            channel: MIDI channel (1-16)
        """
        message = MIDIMessage(
            type="note_off",
            channel=channel,
            data={"note": note},
        )
        return await self.send_message(device_id, message)

    async def control_change(
        self,
        device_id: str,
        controller: int,
        value: int,
        channel: int = 1,
    ) -> dict[str, Any]:
        """
        Send MIDI control change (CC) message.

        Args:
            device_id: Target MIDI device ID
            controller: Controller number (0-127)
            value: Controller value (0-127)
            channel: MIDI channel (1-16)
        """
        message = MIDIMessage(
            type="cc",
            channel=channel,
            data={"controller": controller, "value": value},
        )
        return await self.send_message(device_id, message)

    async def program_change(
        self,
        device_id: str,
        program: int,
        channel: int = 1,
    ) -> dict[str, Any]:
        """
        Send MIDI program change message.

        Args:
            device_id: Target MIDI device ID
            program: Program number (0-127)
            channel: MIDI channel (1-16)
        """
        message = MIDIMessage(
            type="program_change",
            channel=channel,
            data={"program": program},
        )
        return await self.send_message(device_id, message)


# Singleton instance
_midi_controller: MIDIController | None = None


def get_midi_controller() -> MIDIController:
    """Get or create singleton MIDI controller instance."""
    global _midi_controller
    if _midi_controller is None:
        _midi_controller = MIDIController()
    return _midi_controller
