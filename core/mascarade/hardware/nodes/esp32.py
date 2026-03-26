"""ESP32 control nodes — Device discovery, GPIO, sensor, and OTA update nodes.

Implements nodes for communicating with ESP32 microcontrollers over HTTP,
WebSocket, or MQTT protocols. Follows the connection model defined in
SPEC-029-P4 section 3.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Literal

import httpx
from pydantic import BaseModel, Field

from mascarade.hardware.types import GPIOState, SensorReading
from mascarade.node_engine.base import (
    NodeDefinition,
    NodeExecutionContext,
    NodeExecutionResult,
)
from mascarade.node_engine.types import (
    NodePort,
    PortDirection,
    PortKind,
    PortType,
    PrimitiveType,
    array_port,
    domain_port,
    primitive_port,
    void_port,
)

logger = logging.getLogger("mascarade.hardware.esp32")

# --- Error Classes ---


class ESP32Error(RuntimeError):
    """Base error for ESP32 node failures."""


class ESP32ConnectionError(ESP32Error):
    """Raised when connection to ESP32 device fails."""


class ESP32TimeoutError(ESP32Error):
    """Raised when ESP32 operation times out."""


# --- Connection Model ---


class ESP32ConnectionConfig(BaseModel):
    """Connection configuration for an ESP32 device.

    Defines how to connect to an ESP32 microcontroller using HTTP,
    WebSocket, or MQTT protocols. Used by all ESP32 nodes.
    """

    device_id: str = Field(description="mDNS hostname or IP address")
    protocol: Literal["http", "websocket", "mqtt"] = "http"
    port: int = Field(80, description="TCP port for HTTP/WS, or MQTT broker port")
    mqtt_broker: str | None = Field(None, description="MQTT broker address if protocol=mqtt")
    mqtt_topic_prefix: str = Field("mascarade/esp32", description="MQTT topic prefix")
    timeout_ms: int = Field(5000, ge=100, le=30000, description="Connection timeout")
    retry_count: int = Field(3, ge=0, le=10, description="Retry attempts on failure")


# --- ESP32 Client ---


class ESP32Client:
    """Async client for communicating with ESP32 devices.

    Supports HTTP, WebSocket, and MQTT protocols. Manages connection pooling
    and retry logic.
    """

    def __init__(
        self,
        config: ESP32ConnectionConfig,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        """Initialize ESP32 client.

        Args:
            config: Connection configuration
            http_client: Optional custom HTTP client (for testing)
        """
        self.config = config
        self._http_client = http_client or httpx.AsyncClient(
            timeout=config.timeout_ms / 1000.0,
            headers={"User-Agent": "mascarade-hardware-worker"},
        )
        self._owns_http_client = http_client is None

    async def close(self) -> None:
        """Close the client and release resources."""
        if self._owns_http_client:
            await self._http_client.aclose()

    async def discover(
        self,
        network: str | None = None,
        timeout_ms: int = 5000,
    ) -> list[dict[str, Any]]:
        """Discover ESP32 devices on the network.

        Args:
            network: Network CIDR to scan (default: auto-detect)
            timeout_ms: Discovery timeout in milliseconds

        Returns:
            List of device descriptors

        Note:
            This is a placeholder implementation. Full mDNS/UDP discovery
            will be implemented in phase-8-device-discovery.
        """
        logger.info(
            "ESP32 discovery not yet implemented (phase-8-device-discovery), returning empty list"
        )
        return []

    async def gpio_operation(
        self,
        pin_config: GPIOState,
        retry: int = 0,
    ) -> GPIOState:
        """Perform GPIO read/write operation.

        Args:
            pin_config: Desired GPIO configuration
            retry: Current retry attempt (internal)

        Returns:
            Actual GPIO state after operation

        Raises:
            ESP32ConnectionError: If connection fails
            ESP32TimeoutError: If operation times out
        """
        if self.config.protocol != "http":
            raise ESP32Error(
                f"GPIO operations only supported over HTTP, got {self.config.protocol}"
            )

        url = f"http://{self.config.device_id}:{self.config.port}/gpio"
        payload = {
            "pin": pin_config.pin,
            "direction": pin_config.direction.value,
            "value": pin_config.value,
            "pull": pin_config.pull.value,
        }

        if pin_config.pwm_duty is not None:
            payload["pwm_duty"] = pin_config.pwm_duty
        if pin_config.pwm_freq is not None:
            payload["pwm_freq"] = pin_config.pwm_freq

        try:
            response = await self._http_client.post(url, json=payload)
            response.raise_for_status()
            data = response.json()

            # Parse response into GPIOState
            return GPIOState(
                pin=data.get("pin", pin_config.pin),
                direction=data.get("direction", pin_config.direction.value),
                value=data.get("value", pin_config.value),
                pull=data.get("pull", pin_config.pull.value),
                pwm_duty=data.get("pwm_duty"),
                pwm_freq=data.get("pwm_freq"),
            )
        except httpx.TimeoutException as exc:
            if retry < self.config.retry_count:
                logger.warning(
                    "GPIO operation timed out, retrying (%d/%d)",
                    retry + 1,
                    self.config.retry_count,
                )
                await asyncio.sleep(0.1 * (retry + 1))
                return await self.gpio_operation(pin_config, retry + 1)
            raise ESP32TimeoutError(f"GPIO operation timed out after {retry + 1} attempts") from exc
        except httpx.HTTPStatusError as exc:
            raise ESP32ConnectionError(
                f"GPIO operation failed: {exc.response.status_code}"
            ) from exc
        except httpx.RequestError as exc:
            if retry < self.config.retry_count:
                logger.warning(
                    "GPIO connection failed, retrying (%d/%d)",
                    retry + 1,
                    self.config.retry_count,
                )
                await asyncio.sleep(0.1 * (retry + 1))
                return await self.gpio_operation(pin_config, retry + 1)
            raise ESP32ConnectionError(f"Failed to connect to ESP32: {exc}") from exc

    async def read_sensor(
        self,
        sensor_id: str,
        retry: int = 0,
    ) -> SensorReading:
        """Read sensor data from ESP32 device.

        Args:
            sensor_id: Sensor identifier on the device
            retry: Current retry attempt (internal)

        Returns:
            Sensor reading

        Raises:
            ESP32ConnectionError: If connection fails
            ESP32TimeoutError: If operation times out
        """
        if self.config.protocol != "http":
            raise ESP32Error(
                f"Sensor operations only supported over HTTP, got {self.config.protocol}"
            )

        url = f"http://{self.config.device_id}:{self.config.port}/sensor/{sensor_id}"

        try:
            response = await self._http_client.get(url)
            response.raise_for_status()
            data = response.json()

            return SensorReading(
                sensor_id=data.get("sensor_id", sensor_id),
                sensor_type=data.get("sensor_type", "unknown"),
                value=float(data.get("value", 0.0)),
                unit=data.get("unit", ""),
                timestamp_ms=int(data.get("timestamp_ms", int(time.time() * 1000))),
                quality=float(data.get("quality", 1.0)),
                raw=data.get("raw"),
            )
        except httpx.TimeoutException as exc:
            if retry < self.config.retry_count:
                logger.warning(
                    "Sensor read timed out, retrying (%d/%d)",
                    retry + 1,
                    self.config.retry_count,
                )
                await asyncio.sleep(0.1 * (retry + 1))
                return await self.read_sensor(sensor_id, retry + 1)
            raise ESP32TimeoutError(f"Sensor read timed out after {retry + 1} attempts") from exc
        except httpx.HTTPStatusError as exc:
            raise ESP32ConnectionError(f"Sensor read failed: {exc.response.status_code}") from exc
        except httpx.RequestError as exc:
            if retry < self.config.retry_count:
                logger.warning(
                    "Sensor connection failed, retrying (%d/%d)",
                    retry + 1,
                    self.config.retry_count,
                )
                await asyncio.sleep(0.1 * (retry + 1))
                return await self.read_sensor(sensor_id, retry + 1)
            raise ESP32ConnectionError(f"Failed to connect to ESP32: {exc}") from exc

    async def ota_update(
        self,
        firmware: bytes,
        verify: bool = True,
    ) -> tuple[bool, str | None]:
        """Perform over-the-air firmware update.

        Args:
            firmware: Firmware binary data
            verify: Verify firmware hash after upload

        Returns:
            Tuple of (success, error_message)
        """
        if self.config.protocol != "http":
            raise ESP32Error(f"OTA updates only supported over HTTP, got {self.config.protocol}")

        url = f"http://{self.config.device_id}:{self.config.port}/ota"

        try:
            # Upload firmware
            response = await self._http_client.post(
                url,
                files={"firmware": ("firmware.bin", firmware, "application/octet-stream")},
                data={"verify": "true" if verify else "false"},
                timeout=60.0,  # OTA updates can take longer
            )
            response.raise_for_status()
            data = response.json()

            success = data.get("success", False)
            error = data.get("error")

            return success, error
        except httpx.TimeoutException as exc:
            return False, f"OTA update timed out: {exc}"
        except httpx.HTTPStatusError as exc:
            return False, f"OTA update failed: {exc.response.status_code}"
        except httpx.RequestError as exc:
            return False, f"Failed to connect to ESP32: {exc}"


# --- Node Execution Functions ---


async def execute_discover_node(context: NodeExecutionContext) -> NodeExecutionResult:
    """Execute hardware.esp32.discover node.

    Discovers ESP32 devices on the local network via mDNS and UDP broadcast.
    """
    network = context.get_input("network")
    timeout_ms = context.get_input("timeout_ms", 5000)

    # Create temporary client for discovery (no specific device)
    config = ESP32ConnectionConfig(
        device_id="255.255.255.255",  # Broadcast
        timeout_ms=timeout_ms,
    )
    client = ESP32Client(config)

    try:
        devices = await client.discover(network=network, timeout_ms=timeout_ms)
        return NodeExecutionResult.ok(
            devices=devices,
            count=len(devices),
        )
    except Exception:
        logger.exception("ESP32 discovery failed")
        # Graceful degradation: return empty list instead of error
        return NodeExecutionResult.ok(devices=[], count=0)
    finally:
        await client.close()


async def execute_gpio_node(context: NodeExecutionContext) -> NodeExecutionResult:
    """Execute hardware.esp32.gpio node.

    Reads or writes GPIO pin state on a connected ESP32.
    """
    # Check capability for GPIO write operations
    device_config_dict = context.get_input("device")
    pin_config_dict = context.get_input("pin_config")

    if not device_config_dict:
        return NodeExecutionResult.error("Missing required input: device")
    if not pin_config_dict:
        return NodeExecutionResult.error("Missing required input: pin_config")

    # Parse inputs
    try:
        device_config = ESP32ConnectionConfig(**device_config_dict)
        pin_config = GPIOState(**pin_config_dict)
    except Exception as exc:
        return NodeExecutionResult.error(f"Invalid input configuration: {exc}", "ValidationError")

    # Check write capability
    if pin_config.direction == "output":
        context.require_capability("hardware.gpio.write")

    # Create client and perform GPIO operation
    client = ESP32Client(device_config)

    try:
        state = await client.gpio_operation(pin_config)
        return NodeExecutionResult.ok(state=state.model_dump(), error=None)
    except ESP32Error as exc:
        logger.error("GPIO operation failed: %s", exc)
        return NodeExecutionResult.ok(state=None, error=str(exc))
    finally:
        await client.close()


async def execute_sensor_node(context: NodeExecutionContext) -> NodeExecutionResult:
    """Execute hardware.esp32.sensor node.

    Reads sensor data from an ESP32 device.
    """
    device_config_dict = context.get_input("device")
    sensor_id = context.get_input("sensor_id")

    if not device_config_dict:
        return NodeExecutionResult.error("Missing required input: device")
    if not sensor_id:
        return NodeExecutionResult.error("Missing required input: sensor_id")

    # Parse device config
    try:
        device_config = ESP32ConnectionConfig(**device_config_dict)
    except Exception as exc:
        return NodeExecutionResult.error(f"Invalid device configuration: {exc}", "ValidationError")

    # Create client and read sensor
    client = ESP32Client(device_config)

    try:
        reading = await client.read_sensor(sensor_id)
        return NodeExecutionResult.ok(
            reading=reading.model_dump(),
            stream=None,  # Streaming mode not yet implemented
        )
    except ESP32Error as exc:
        logger.error("Sensor read failed: %s", exc)
        return NodeExecutionResult.error(str(exc), "ESP32Error")
    finally:
        await client.close()


async def execute_ota_node(context: NodeExecutionContext) -> NodeExecutionResult:
    """Execute hardware.esp32.ota node.

    Performs over-the-air firmware update on an ESP32 device.
    """
    # Check capability for OTA flash
    context.require_capability("hardware.ota.flash")

    device_config_dict = context.get_input("device")
    firmware = context.get_input("firmware")
    verify = context.get_input("verify", True)

    if not device_config_dict:
        return NodeExecutionResult.error("Missing required input: device")
    if not firmware:
        return NodeExecutionResult.error("Missing required input: firmware")

    # Parse device config
    try:
        device_config = ESP32ConnectionConfig(**device_config_dict)
    except Exception as exc:
        return NodeExecutionResult.error(f"Invalid device configuration: {exc}", "ValidationError")

    # Firmware should be bytes
    if isinstance(firmware, str):
        # Assume base64-encoded
        import base64

        try:
            firmware = base64.b64decode(firmware)
        except Exception as exc:
            return NodeExecutionResult.error(f"Invalid firmware data: {exc}", "ValidationError")

    # Create client and perform OTA
    client = ESP32Client(device_config)

    try:
        success, error = await client.ota_update(firmware, verify=verify)
        return NodeExecutionResult.ok(
            progress=None,  # Progress streaming not yet implemented
            success=success,
            error=error,
        )
    finally:
        await client.close()


# --- Node Definitions ---


ESP32DiscoverNode = NodeDefinition(
    node_type="hardware.esp32.discover",
    description="Discovers ESP32 devices on the local network via mDNS and UDP broadcast",
    input_ports=[
        void_port(
            name="trigger",
            direction=PortDirection.INPUT,
            description="Trigger discovery scan",
        ),
        primitive_port(
            name="network",
            direction=PortDirection.INPUT,
            primitive_type=PrimitiveType.STRING,
            description="Network CIDR to scan (default: auto-detect)",
            optional=True,
        ),
        primitive_port(
            name="timeout_ms",
            direction=PortDirection.INPUT,
            primitive_type=PrimitiveType.INTEGER,
            description="Discovery timeout (default: 5000)",
            optional=True,
        ),
    ],
    output_ports=[
        array_port(
            name="devices",
            direction=PortDirection.OUTPUT,
            element_type=PortType(kind=PortKind.PRIMITIVE, name=PrimitiveType.JSON),
            description="Discovered device descriptors",
        ),
        primitive_port(
            name="count",
            direction=PortDirection.OUTPUT,
            primitive_type=PrimitiveType.INTEGER,
            description="Number of devices found",
        ),
    ],
    tags=["hardware", "esp32", "discovery", "network"],
    io_intensive=True,
)


ESP32GPIONode = NodeDefinition(
    node_type="hardware.esp32.gpio",
    description="Reads or writes GPIO pin state on a connected ESP32",
    input_ports=[
        primitive_port(
            name="device",
            direction=PortDirection.INPUT,
            primitive_type=PrimitiveType.JSON,
            description="ESP32 connection config (ESP32ConnectionConfig)",
        ),
        domain_port(
            name="pin_config",
            direction=PortDirection.INPUT,
            domain="hardware",
            type_name="GPIOState",
            description="Desired GPIO configuration",
        ),
    ],
    output_ports=[
        domain_port(
            name="state",
            direction=PortDirection.OUTPUT,
            domain="hardware",
            type_name="GPIOState",
            description="Actual GPIO state after operation",
        ),
        primitive_port(
            name="error",
            direction=PortDirection.OUTPUT,
            primitive_type=PrimitiveType.STRING,
            description="Error message if operation failed",
            optional=True,
        ),
    ],
    tags=["hardware", "esp32", "gpio", "control"],
    io_intensive=True,
    max_latency_ms=100,  # Per spec: 100ms round-trip requirement
)


ESP32SensorNode = NodeDefinition(
    node_type="hardware.esp32.sensor",
    description="Reads sensor data from an ESP32 device",
    input_ports=[
        primitive_port(
            name="device",
            direction=PortDirection.INPUT,
            primitive_type=PrimitiveType.JSON,
            description="ESP32 connection config (ESP32ConnectionConfig)",
        ),
        primitive_port(
            name="sensor_id",
            direction=PortDirection.INPUT,
            primitive_type=PrimitiveType.STRING,
            description="Sensor identifier on the device",
        ),
        primitive_port(
            name="interval_ms",
            direction=PortDirection.INPUT,
            primitive_type=PrimitiveType.INTEGER,
            description="Polling interval for stream mode",
            optional=True,
        ),
    ],
    output_ports=[
        domain_port(
            name="reading",
            direction=PortDirection.OUTPUT,
            domain="hardware",
            type_name="SensorReading",
            description="Latest sensor reading",
        ),
        NodePort(
            name="stream",
            direction=PortDirection.OUTPUT,
            port_type=PortType(
                kind=PortKind.ARRAY,
                element_type=PortType(
                    kind=PortKind.DOMAIN, domain="hardware", name="SensorReading"
                ),
            ),
            description="Continuous sensor stream (if interval set)",
        ),
    ],
    tags=["hardware", "esp32", "sensor", "monitoring"],
    io_intensive=True,
)


ESP32OTANode = NodeDefinition(
    node_type="hardware.esp32.ota",
    description="Performs over-the-air firmware update on an ESP32 device",
    input_ports=[
        primitive_port(
            name="device",
            direction=PortDirection.INPUT,
            primitive_type=PrimitiveType.JSON,
            description="ESP32 connection config (ESP32ConnectionConfig)",
        ),
        primitive_port(
            name="firmware",
            direction=PortDirection.INPUT,
            primitive_type=PrimitiveType.BINARY,
            description="Firmware binary (or FirmwareBinary from Phase 3)",
        ),
        primitive_port(
            name="verify",
            direction=PortDirection.INPUT,
            primitive_type=PrimitiveType.BOOLEAN,
            description="Verify firmware hash after upload (default: true)",
            optional=True,
        ),
    ],
    output_ports=[
        array_port(
            name="progress",
            direction=PortDirection.OUTPUT,
            element_type=PortType(kind=PortKind.PRIMITIVE, name=PrimitiveType.NUMBER),
            description="Upload progress 0.0-1.0",
        ),
        primitive_port(
            name="success",
            direction=PortDirection.OUTPUT,
            primitive_type=PrimitiveType.BOOLEAN,
            description="Whether OTA completed successfully",
        ),
        primitive_port(
            name="error",
            direction=PortDirection.OUTPUT,
            primitive_type=PrimitiveType.STRING,
            description="Error details if failed",
            optional=True,
        ),
    ],
    tags=["hardware", "esp32", "ota", "firmware", "update"],
    io_intensive=True,
)


# Export all nodes
__all__ = [
    "ESP32ConnectionConfig",
    "ESP32Client",
    "ESP32Error",
    "ESP32ConnectionError",
    "ESP32TimeoutError",
    "ESP32DiscoverNode",
    "ESP32GPIONode",
    "ESP32SensorNode",
    "ESP32OTANode",
    "execute_discover_node",
    "execute_gpio_node",
    "execute_sensor_node",
    "execute_ota_node",
]
