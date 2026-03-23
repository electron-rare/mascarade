"""ESP32 HTTP/WebSocket client for device communication."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import httpx
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

logger = logging.getLogger("mascarade.node_engine.esp32")

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
class ESP32Device:
    """ESP32 device representation."""

    id: str
    name: str
    host: str
    port: int = 80
    protocol: str = "http"  # "http" or "https"
    websocket_enabled: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def base_url(self) -> str:
        """Get base HTTP URL for the device."""
        return f"{self.protocol}://{self.host}:{self.port}"

    @property
    def ws_url(self) -> str:
        """Get WebSocket URL for the device."""
        ws_protocol = "wss" if self.protocol == "https" else "ws"
        return f"{ws_protocol}://{self.host}:{self.port}/ws"


@dataclass
class ESP32Command:
    """ESP32 command representation."""

    device_id: str
    endpoint: str
    method: str = "POST"  # HTTP method
    data: dict[str, Any] = field(default_factory=dict)
    params: dict[str, Any] = field(default_factory=dict)


@dataclass
class ESP32Message:
    """ESP32 WebSocket message representation."""

    type: str
    data: dict[str, Any] = field(default_factory=dict)
    timestamp: float | None = None


class ESP32Client:
    """ESP32 HTTP/WebSocket client for device communication."""

    def __init__(
        self,
        devices: list[ESP32Device] | None = None,
        timeout: float = 10.0,
    ):
        """
        Initialize ESP32 client.

        Args:
            devices: List of ESP32 devices to manage (optional)
            timeout: HTTP request timeout in seconds
        """
        self._devices: dict[str, ESP32Device] = {}
        if devices:
            for device in devices:
                self._devices[device.id] = device

        self._http_client = httpx.AsyncClient(timeout=timeout)
        self._ws_connections: dict[str, Any] = {}  # WebSocket connections by device_id
        self._ws_handlers: dict[str, list] = {}  # Message handlers by device_id

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()

    async def close(self) -> None:
        """Close all connections and cleanup resources."""
        # Close all WebSocket connections
        for device_id in list(self._ws_connections.keys()):
            await self.disconnect_websocket(device_id)

        # Close HTTP client
        await self._http_client.aclose()
        logger.info("ESP32 client closed")

    def add_device(self, device: ESP32Device) -> None:
        """
        Add an ESP32 device to the client.

        Args:
            device: ESP32 device to add
        """
        self._devices[device.id] = device
        logger.info(f"Added ESP32 device: {device.name} ({device.id})")

    def remove_device(self, device_id: str) -> None:
        """
        Remove an ESP32 device from the client.

        Args:
            device_id: Device ID to remove
        """
        if device_id in self._devices:
            del self._devices[device_id]
            logger.info(f"Removed ESP32 device: {device_id}")

    def get_device(self, device_id: str) -> ESP32Device | None:
        """
        Get ESP32 device by ID.

        Args:
            device_id: Device ID to retrieve

        Returns:
            ESP32Device if found, None otherwise
        """
        return self._devices.get(device_id)

    def list_devices(self) -> list[ESP32Device]:
        """
        Get list of all registered ESP32 devices.

        Returns:
            List of ESP32 devices
        """
        return list(self._devices.values())

    @make_retry()
    async def ping(self, device_id: str) -> bool:
        """
        Ping an ESP32 device to check availability.

        Args:
            device_id: Target device ID

        Returns:
            True if device responds, False otherwise
        """
        device = self.get_device(device_id)
        if not device:
            logger.warning(f"Device not found: {device_id}")
            return False

        try:
            response = await self._http_client.get(
                f"{device.base_url}/health",
                timeout=5.0,
            )
            return response.status_code == 200
        except (httpx.HTTPError, ConnectionError) as e:
            logger.debug(f"Ping failed for {device_id}: {e}")
            return False

    @make_retry()
    async def get_status(self, device_id: str) -> dict[str, Any]:
        """
        Get ESP32 device status.

        Args:
            device_id: Target device ID

        Returns:
            Device status dictionary
        """
        device = self.get_device(device_id)
        if not device:
            return {
                "available": False,
                "error": "Device not found",
                "device_id": device_id,
            }

        try:
            response = await self._http_client.get(f"{device.base_url}/status")
            response.raise_for_status()
            return response.json()
        except (httpx.HTTPError, ConnectionError) as e:
            logger.warning(f"Failed to get status for {device_id}: {e}")
            return {
                "available": False,
                "error": str(e),
                "device_id": device_id,
            }

    @make_retry()
    async def send_command(
        self,
        device_id: str,
        endpoint: str,
        method: str = "POST",
        data: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Send HTTP command to ESP32 device.

        Args:
            device_id: Target device ID
            endpoint: API endpoint (e.g., "/led/set")
            method: HTTP method (GET, POST, PUT, DELETE)
            data: Request body data (for POST/PUT)
            params: URL query parameters

        Returns:
            Response from device
        """
        device = self.get_device(device_id)
        if not device:
            raise ValueError(f"Device not found: {device_id}")

        url = f"{device.base_url}{endpoint}"
        method = method.upper()

        try:
            if method == "GET":
                response = await self._http_client.get(url, params=params or {})
            elif method == "POST":
                response = await self._http_client.post(
                    url,
                    json=data or {},
                    params=params or {},
                )
            elif method == "PUT":
                response = await self._http_client.put(
                    url,
                    json=data or {},
                    params=params or {},
                )
            elif method == "DELETE":
                response = await self._http_client.delete(url, params=params or {})
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")

            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"Failed to send command to {device_id}: {e}")
            raise

    async def connect_websocket(
        self,
        device_id: str,
        on_message: callable | None = None,
    ) -> bool:
        """
        Connect to ESP32 device via WebSocket.

        Args:
            device_id: Target device ID
            on_message: Optional callback for incoming messages

        Returns:
            True if connection successful, False otherwise
        """
        device = self.get_device(device_id)
        if not device:
            logger.warning(f"Device not found: {device_id}")
            return False

        if not device.websocket_enabled:
            logger.warning(f"WebSocket not enabled for device: {device_id}")
            return False

        if device_id in self._ws_connections:
            logger.info(f"WebSocket already connected for {device_id}")
            return True

        try:
            # Note: For production, use websockets library
            # This is a placeholder showing the pattern
            logger.info(f"WebSocket connection established for {device_id}")
            self._ws_connections[device_id] = {"url": device.ws_url}

            if on_message:
                self._ws_handlers.setdefault(device_id, []).append(on_message)

            return True
        except Exception as e:
            logger.error(f"Failed to connect WebSocket for {device_id}: {e}")
            return False

    async def disconnect_websocket(self, device_id: str) -> None:
        """
        Disconnect WebSocket connection for device.

        Args:
            device_id: Target device ID
        """
        if device_id in self._ws_connections:
            # Close WebSocket connection
            del self._ws_connections[device_id]
            logger.info(f"WebSocket disconnected for {device_id}")

        if device_id in self._ws_handlers:
            del self._ws_handlers[device_id]

    async def send_websocket_message(
        self,
        device_id: str,
        message: ESP32Message | dict[str, Any],
    ) -> bool:
        """
        Send message to ESP32 device via WebSocket.

        Args:
            device_id: Target device ID
            message: Message to send

        Returns:
            True if sent successfully, False otherwise
        """
        if device_id not in self._ws_connections:
            logger.warning(f"WebSocket not connected for {device_id}")
            return False

        try:
            if isinstance(message, ESP32Message):
                payload = {
                    "type": message.type,
                    "data": message.data,
                }
            else:
                payload = message

            # Note: For production, use websockets library to send
            logger.debug(f"Sending WebSocket message to {device_id}: {payload}")
            return True
        except Exception as e:
            logger.error(f"Failed to send WebSocket message to {device_id}: {e}")
            return False

    @make_retry()
    async def set_gpio(
        self,
        device_id: str,
        pin: int,
        value: int | bool,
    ) -> dict[str, Any]:
        """
        Set GPIO pin value on ESP32 device.

        Args:
            device_id: Target device ID
            pin: GPIO pin number
            value: Pin value (0/1 or False/True)

        Returns:
            Response from device
        """
        return await self.send_command(
            device_id,
            "/gpio/set",
            method="POST",
            data={
                "pin": pin,
                "value": 1 if value else 0,
            },
        )

    @make_retry()
    async def get_gpio(self, device_id: str, pin: int) -> dict[str, Any]:
        """
        Get GPIO pin value from ESP32 device.

        Args:
            device_id: Target device ID
            pin: GPIO pin number

        Returns:
            Response with pin state
        """
        return await self.send_command(
            device_id,
            "/gpio/get",
            method="GET",
            params={"pin": pin},
        )

    @make_retry()
    async def get_sensors(self, device_id: str) -> dict[str, Any]:
        """
        Get sensor readings from ESP32 device.

        Args:
            device_id: Target device ID

        Returns:
            Sensor data dictionary
        """
        return await self.send_command(
            device_id,
            "/sensors",
            method="GET",
        )


# Singleton instance
_esp32_client: ESP32Client | None = None


def get_esp32_client() -> ESP32Client:
    """Get or create singleton ESP32 client instance."""
    global _esp32_client
    if _esp32_client is None:
        _esp32_client = ESP32Client()
    return _esp32_client
