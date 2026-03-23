"""DMX controller backend — node-dmx bridge via Node.js subprocess."""

from __future__ import annotations

import asyncio
import logging
import subprocess
from dataclasses import dataclass
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

logger = logging.getLogger("mascarade.node_engine.dmx")

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
class DMXUniverse:
    """DMX universe representation."""

    id: str
    name: str
    driver: str | None = None  # "enttec-usb-dmx-pro", "dmx-king-ultra-dmx-pro", etc.
    channels: int = 512  # Standard DMX512 universe size


@dataclass
class DMXCommand:
    """DMX command representation."""

    universe: str  # Universe ID
    channel: int  # 1-512
    value: int  # 0-255
    transition_time: int = 0  # Fade time in milliseconds (optional)


class DMXController:
    """DMX controller backend using node-dmx bridge."""

    def __init__(
        self,
        bridge_url: str = "http://localhost:3334",
        auto_start: bool = True,
    ):
        """
        Initialize DMX controller.

        Args:
            bridge_url: URL of the node-dmx Node.js bridge service
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
        """Start the DMX bridge service if not already running."""
        if not self.auto_start:
            return

        # Check if bridge is already running
        try:
            response = await self._client.get(f"{self.bridge_url}/health")
            if response.status_code == 200:
                logger.info("DMX bridge already running")
                return
        except (httpx.HTTPError, ConnectionError):
            logger.info("DMX bridge not running, starting...")

        # Start Node.js bridge subprocess
        bridge_script = Path(__file__).parent / "dmx_bridge.js"
        if not bridge_script.exists():
            logger.warning(f"DMX bridge script not found: {bridge_script}")
            logger.warning("DMX functionality will be unavailable")
            return

        try:
            self._process = subprocess.Popen(
                ["node", str(bridge_script)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            logger.info(f"Started DMX bridge (PID: {self._process.pid})")

            # Wait for bridge to be ready
            for _ in range(30):  # 3 seconds timeout
                try:
                    response = await self._client.get(f"{self.bridge_url}/health")
                    if response.status_code == 200:
                        logger.info("DMX bridge ready")
                        return
                except (httpx.HTTPError, ConnectionError):
                    await asyncio.sleep(0.1)

            logger.warning("DMX bridge started but not responding")
        except FileNotFoundError:
            logger.error("Node.js not found — install Node.js to use DMX features")
        except Exception as e:
            logger.error(f"Failed to start DMX bridge: {e}")

    async def stop(self) -> None:
        """Stop the DMX bridge service."""
        if self._process:
            self._process.terminate()
            try:
                self._process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._process.kill()
            logger.info("DMX bridge stopped")

        await self._client.aclose()

    @make_retry()
    async def get_universes(self) -> list[DMXUniverse]:
        """
        Get list of configured DMX universes.

        Returns:
            List of DMX universes
        """
        try:
            response = await self._client.get(f"{self.bridge_url}/universes")
            response.raise_for_status()
            data = response.json()

            return [
                DMXUniverse(
                    id=universe["id"],
                    name=universe["name"],
                    driver=universe.get("driver"),
                    channels=universe.get("channels", 512),
                )
                for universe in data.get("universes", [])
            ]
        except (httpx.HTTPError, ConnectionError) as e:
            logger.warning(f"Failed to get DMX universes: {e}")
            return []  # Graceful degradation

    @make_retry()
    async def get_status(self, universe_id: str | None = None) -> dict[str, Any]:
        """
        Get DMX universe status and channel values.

        Args:
            universe_id: Optional universe ID, returns all if None

        Returns:
            Status dictionary with universe states
        """
        try:
            params = {"universe": universe_id} if universe_id else {}
            response = await self._client.get(
                f"{self.bridge_url}/status",
                params=params,
            )
            response.raise_for_status()
            return response.json()
        except (httpx.HTTPError, ConnectionError) as e:
            logger.warning(f"Failed to get DMX status: {e}")
            return {
                "available": False,
                "error": str(e),
                "message": "DMX bridge unavailable - no hardware connected or bridge not running",
            }

    @make_retry()
    async def set_channel(
        self,
        universe: str,
        channel: int,
        value: int,
        transition_time: int = 0,
    ) -> dict[str, Any]:
        """
        Set DMX channel value.

        Args:
            universe: Universe ID
            channel: Channel number (1-512)
            value: Channel value (0-255)
            transition_time: Fade time in milliseconds (optional)

        Returns:
            Response from bridge service
        """
        if not (1 <= channel <= 512):
            raise ValueError(f"DMX channel must be 1-512, got {channel}")
        if not (0 <= value <= 255):
            raise ValueError(f"DMX value must be 0-255, got {value}")

        try:
            response = await self._client.post(
                f"{self.bridge_url}/set",
                json={
                    "universe": universe,
                    "channel": channel,
                    "value": value,
                    "transition_time": transition_time,
                },
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"Failed to set DMX channel: {e}")
            raise

    @make_retry()
    async def set_channels(
        self,
        universe: str,
        channels: dict[int, int],
        transition_time: int = 0,
    ) -> dict[str, Any]:
        """
        Set multiple DMX channels at once.

        Args:
            universe: Universe ID
            channels: Dictionary mapping channel numbers to values
            transition_time: Fade time in milliseconds (optional)

        Returns:
            Response from bridge service
        """
        # Validate all channels and values
        for channel, value in channels.items():
            if not (1 <= channel <= 512):
                raise ValueError(f"DMX channel must be 1-512, got {channel}")
            if not (0 <= value <= 255):
                raise ValueError(f"DMX value must be 0-255, got {value}")

        try:
            response = await self._client.post(
                f"{self.bridge_url}/set-multiple",
                json={
                    "universe": universe,
                    "channels": channels,
                    "transition_time": transition_time,
                },
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"Failed to set DMX channels: {e}")
            raise

    async def blackout(self, universe: str) -> dict[str, Any]:
        """
        Set all channels to 0 (blackout).

        Args:
            universe: Universe ID

        Returns:
            Response from bridge service
        """
        try:
            response = await self._client.post(
                f"{self.bridge_url}/blackout",
                json={"universe": universe},
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"Failed to blackout DMX universe: {e}")
            raise


# Singleton instance
_dmx_controller: DMXController | None = None


def get_dmx_controller() -> DMXController:
    """Get or create singleton DMX controller instance."""
    global _dmx_controller
    if _dmx_controller is None:
        _dmx_controller = DMXController()
    return _dmx_controller
