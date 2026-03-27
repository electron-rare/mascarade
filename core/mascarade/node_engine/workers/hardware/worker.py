"""Hardware domain worker for mascarade node engine.

Handles ESP32 GPIO/sensors, DMX lighting control, and serial I/O.
Dégradation gracieuse quand le hardware n'est pas connecté.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import TYPE_CHECKING, Any

from mascarade.node_engine.dmx_controller import DMXController, get_dmx_controller
from mascarade.node_engine.esp32_client import ESP32Client, ESP32Device, get_esp32_client
from mascarade.node_engine.worker import NodeWorker

from .types import (
    DMXFrame,
    DeviceDescriptor,
    GPIODirection,
    GPIOState,
    SensorReading,
    SerialData,
)

if TYPE_CHECKING:
    from mascarade.router import Router

logger = logging.getLogger(__name__)

# Subnet scan defaults pour mDNS / HTTP discovery
_DEFAULT_SCAN_TIMEOUT = 3.0
_DEFAULT_SUBNET = "192.168.0"
_DEFAULT_ESP32_PORT = 80

# Serial port paths by platform
_SERIAL_PORT_GLOBS = [
    "/dev/ttyUSB*",
    "/dev/ttyACM*",
    "/dev/cu.usbserial*",
    "/dev/cu.usbmodem*",
    "/dev/cu.SLAB*",
]


class HardwareWorker(NodeWorker):
    """Worker for hardware domain node types.

    Dispatches to ESP32, DMX and serial handlers.
    Chaque handler gère la dégradation gracieuse si le hardware est absent.
    """

    name = "hardware-worker"
    domain = "hardware"

    def __init__(
        self,
        router: Router | None = None,
        esp32_client: ESP32Client | None = None,
        dmx_controller: DMXController | None = None,
    ):
        self.router = router
        self._esp32: ESP32Client | None = esp32_client
        self._dmx: DMXController | None = dmx_controller

    # ------------------------------------------------------------------
    # Lazy accessors — avoid creating clients when hardware is unused
    # ------------------------------------------------------------------

    @property
    def esp32(self) -> ESP32Client:
        """Get or create ESP32 client singleton."""
        if self._esp32 is None:
            self._esp32 = get_esp32_client()
        return self._esp32

    @property
    def dmx(self) -> DMXController:
        """Get or create DMX controller singleton."""
        if self._dmx is None:
            self._dmx = get_dmx_controller()
        return self._dmx

    # ------------------------------------------------------------------
    # NodeWorker interface
    # ------------------------------------------------------------------

    def capabilities(self) -> list[dict[str, Any]]:
        """Declare hardware worker capabilities."""
        return [
            {
                "node_type": "hardware.esp32.discover",
                "description": "Discover ESP32 devices on the local network",
                "inputs": {
                    "subnet": "str (e.g. '192.168.0')",
                    "port": "int HTTP port to scan",
                    "timeout": "float scan timeout in seconds",
                },
                "outputs": {"devices": "list[DeviceDescriptor]"},
            },
            {
                "node_type": "hardware.esp32.gpio_read",
                "description": "Read GPIO pin state from an ESP32",
                "inputs": {"device_id": "str", "pin": "int"},
                "outputs": {"state": "GPIOState"},
            },
            {
                "node_type": "hardware.esp32.gpio_write",
                "description": "Set GPIO pin state on an ESP32",
                "inputs": {"device_id": "str", "pin": "int", "value": "int|bool"},
                "outputs": {"state": "GPIOState"},
            },
            {
                "node_type": "hardware.esp32.sensor_read",
                "description": "Read sensor data from an ESP32 device",
                "inputs": {"device_id": "str", "sensor_type": "str (optional)"},
                "outputs": {"readings": "list[SensorReading]"},
            },
            {
                "node_type": "hardware.esp32.ota_update",
                "description": "Trigger OTA firmware update on an ESP32",
                "inputs": {"device_id": "str", "firmware_url": "str"},
                "outputs": {"status": "dict"},
            },
            {
                "node_type": "hardware.dmx.universe_create",
                "description": "Create a DMX universe (requires DMX bridge)",
                "inputs": {"name": "str", "driver": "str", "channels": "int"},
                "outputs": {"universe": "dict"},
            },
            {
                "node_type": "hardware.dmx.fixture_set",
                "description": "Set DMX fixture channel values",
                "inputs": {
                    "universe_id": "str",
                    "channels": "dict[int, int]",
                    "transition_ms": "int",
                },
                "outputs": {"frame": "DMXFrame"},
            },
            {
                "node_type": "hardware.dmx.scene_apply",
                "description": "Apply a DMX scene (multiple fixtures at once)",
                "inputs": {
                    "universe_id": "str",
                    "fixtures": "list[dict]",
                    "transition_ms": "int",
                },
                "outputs": {"applied": "dict"},
            },
            {
                "node_type": "hardware.serial.send",
                "description": "Send data over a serial port",
                "inputs": {
                    "port": "str",
                    "data": "str|bytes",
                    "baudrate": "int",
                },
                "outputs": {"sent": "SerialData"},
            },
            {
                "node_type": "hardware.serial.receive",
                "description": "Read data from a serial port",
                "inputs": {
                    "port": "str",
                    "baudrate": "int",
                    "timeout": "float",
                },
                "outputs": {"received": "SerialData"},
            },
        ]

    async def execute(
        self,
        node_type: str,
        inputs: dict[str, Any],
        config: dict[str, Any],
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Dispatch to the appropriate hardware handler."""
        dispatch: dict[str, Any] = {
            # ESP32
            "hardware.esp32.discover": self._esp32_discover,
            "hardware.esp32.gpio_read": self._esp32_gpio_read,
            "hardware.esp32.gpio_write": self._esp32_gpio_write,
            "hardware.esp32.sensor_read": self._esp32_sensor_read,
            "hardware.esp32.ota_update": self._esp32_ota_update,
            # DMX
            "hardware.dmx.universe_create": self._dmx_universe_create,
            "hardware.dmx.fixture_set": self._dmx_fixture_set,
            "hardware.dmx.scene_apply": self._dmx_scene_apply,
            # Serial
            "hardware.serial.send": self._serial_send,
            "hardware.serial.receive": self._serial_receive,
        }

        handler = dispatch.get(node_type)
        if handler is None:
            raise ValueError(f"Unsupported hardware node type: {node_type}")

        return await handler(inputs, config)

    async def validate(
        self, node_type: str, inputs: dict[str, Any], config: dict[str, Any]
    ) -> list[str]:
        """Validate inputs before execution."""
        errors: list[str] = []

        # ESP32 nodes need device_id (except discover)
        if node_type.startswith("hardware.esp32.") and node_type != "hardware.esp32.discover":
            if not inputs.get("device_id"):
                errors.append("device_id is required")

        if node_type in ("hardware.esp32.gpio_read", "hardware.esp32.gpio_write"):
            pin = inputs.get("pin")
            if pin is None:
                errors.append("pin is required")
            elif not isinstance(pin, int) or pin < 0:
                errors.append("pin must be a non-negative integer")

        if node_type == "hardware.esp32.gpio_write":
            if "value" not in inputs:
                errors.append("value is required")

        if node_type == "hardware.esp32.ota_update":
            if not inputs.get("firmware_url"):
                errors.append("firmware_url is required")

        if node_type == "hardware.dmx.fixture_set":
            if not inputs.get("universe_id"):
                errors.append("universe_id is required")
            if not inputs.get("channels"):
                errors.append("channels is required")

        if node_type == "hardware.dmx.scene_apply":
            if not inputs.get("universe_id"):
                errors.append("universe_id is required")
            if not inputs.get("fixtures"):
                errors.append("fixtures is required")

        if node_type in ("hardware.serial.send", "hardware.serial.receive"):
            if not inputs.get("port"):
                errors.append("port is required")

        if node_type == "hardware.serial.send":
            if "data" not in inputs:
                errors.append("data is required")

        return errors

    # ------------------------------------------------------------------
    # ESP32 handlers
    # ------------------------------------------------------------------

    async def _esp32_discover(
        self, inputs: dict[str, Any], config: dict[str, Any]
    ) -> dict[str, Any]:
        """Discover ESP32 devices via HTTP health endpoint scan.

        Scanne le sous-reseau en parallele pour trouver des ESP32.
        """
        subnet = inputs.get("subnet", _DEFAULT_SUBNET)
        port = inputs.get("port", _DEFAULT_ESP32_PORT)
        timeout = inputs.get("timeout", _DEFAULT_SCAN_TIMEOUT)
        # Allow limiting scan range (default: .1 to .254)
        range_start = inputs.get("range_start", 1)
        range_end = inputs.get("range_end", 255)

        discovered: list[DeviceDescriptor] = []

        async def _probe(ip: str) -> DeviceDescriptor | None:
            """Probe a single IP for an ESP32 health endpoint."""
            import httpx

            url = f"http://{ip}:{port}/health"
            try:
                async with httpx.AsyncClient(timeout=timeout) as client:
                    response = await client.get(url)
                    if response.status_code == 200:
                        data = response.json() if response.headers.get("content-type", "").startswith("application/json") else {}
                        device_name = data.get("name", f"esp32-{ip.split('.')[-1]}")
                        device_id = data.get("id", f"esp32-{ip.replace('.', '-')}")
                        desc = DeviceDescriptor(
                            id=device_id,
                            name=device_name,
                            device_type="esp32",
                            host=ip,
                            port=port,
                            available=True,
                            firmware_version=data.get("firmware_version"),
                            metadata=data,
                        )
                        # Register with ESP32 client for future use
                        self.esp32.add_device(
                            ESP32Device(
                                id=device_id,
                                name=device_name,
                                host=ip,
                                port=port,
                            )
                        )
                        return desc
            except Exception:
                pass
            return None

        # Also include already-registered devices
        for device in self.esp32.list_devices():
            alive = await self.esp32.ping(device.id)
            discovered.append(
                DeviceDescriptor(
                    id=device.id,
                    name=device.name,
                    device_type="esp32",
                    host=device.host,
                    port=device.port,
                    available=alive,
                    metadata=device.metadata,
                )
            )

        # Parallel subnet scan
        known_hosts = {d.host for d in discovered}
        tasks = []
        for i in range(range_start, range_end):
            ip = f"{subnet}.{i}"
            if ip not in known_hosts:
                tasks.append(_probe(ip))

        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for result in results:
                if isinstance(result, DeviceDescriptor):
                    discovered.append(result)

        logger.info(f"ESP32 discovery: found {len(discovered)} device(s)")
        return {"devices": [d.to_dict() for d in discovered]}

    async def _esp32_gpio_read(
        self, inputs: dict[str, Any], config: dict[str, Any]
    ) -> dict[str, Any]:
        """Read GPIO pin state from ESP32 device."""
        device_id = inputs["device_id"]
        pin = inputs["pin"]

        try:
            response = await self.esp32.get_gpio(device_id, pin)
            state = GPIOState(
                pin=pin,
                value=response.get("value", 0),
                direction=GPIODirection(response.get("direction", "input")),
                analog=response.get("analog", False),
                device_id=device_id,
            )
            return {"state": state.to_dict()}
        except (ConnectionError, TimeoutError, ValueError) as e:
            logger.warning(f"GPIO read failed for {device_id}:{pin} — {e}")
            return {
                "state": GPIOState(
                    pin=pin, value=-1, device_id=device_id
                ).to_dict(),
                "error": str(e),
                "available": False,
            }

    async def _esp32_gpio_write(
        self, inputs: dict[str, Any], config: dict[str, Any]
    ) -> dict[str, Any]:
        """Set GPIO pin state on ESP32 device."""
        device_id = inputs["device_id"]
        pin = inputs["pin"]
        value = inputs["value"]

        try:
            response = await self.esp32.set_gpio(device_id, pin, value)
            state = GPIOState(
                pin=pin,
                value=1 if value else 0,
                direction=GPIODirection.OUTPUT,
                device_id=device_id,
            )
            return {"state": state.to_dict(), "response": response}
        except (ConnectionError, TimeoutError, ValueError) as e:
            logger.warning(f"GPIO write failed for {device_id}:{pin}={value} — {e}")
            return {
                "state": GPIOState(
                    pin=pin, value=-1, direction=GPIODirection.OUTPUT, device_id=device_id
                ).to_dict(),
                "error": str(e),
                "available": False,
            }

    async def _esp32_sensor_read(
        self, inputs: dict[str, Any], config: dict[str, Any]
    ) -> dict[str, Any]:
        """Read sensor data from ESP32 device.

        Retourne toutes les lectures capteur, ou filtre par sensor_type.
        """
        device_id = inputs["device_id"]
        sensor_filter = inputs.get("sensor_type")

        try:
            response = await self.esp32.send_command(
                device_id, "/sensors", method="GET"
            )
            readings: list[SensorReading] = []
            now = time.time()

            for sensor_data in response.get("sensors", []):
                s_type = sensor_data.get("type", "unknown")
                if sensor_filter and s_type != sensor_filter:
                    continue
                readings.append(
                    SensorReading(
                        sensor_type=s_type,
                        value=sensor_data.get("value", 0.0),
                        unit=sensor_data.get("unit", ""),
                        device_id=device_id,
                        pin=sensor_data.get("pin"),
                        timestamp=sensor_data.get("timestamp", now),
                        metadata=sensor_data.get("metadata", {}),
                    )
                )

            return {"readings": [r.to_dict() for r in readings]}
        except (ConnectionError, TimeoutError, ValueError) as e:
            logger.warning(f"Sensor read failed for {device_id} — {e}")
            return {
                "readings": [],
                "error": str(e),
                "available": False,
            }

    async def _esp32_ota_update(
        self, inputs: dict[str, Any], config: dict[str, Any]
    ) -> dict[str, Any]:
        """Trigger OTA firmware update on ESP32 device.

        Envoie l'URL du firmware a l'ESP32 qui telecharge et flash.
        """
        device_id = inputs["device_id"]
        firmware_url = inputs["firmware_url"]

        try:
            response = await self.esp32.send_command(
                device_id,
                "/ota/update",
                method="POST",
                data={"url": firmware_url},
            )
            return {
                "status": {
                    "device_id": device_id,
                    "firmware_url": firmware_url,
                    "accepted": response.get("accepted", True),
                    "message": response.get("message", "OTA update triggered"),
                    "response": response,
                }
            }
        except (ConnectionError, TimeoutError, ValueError) as e:
            logger.error(f"OTA update failed for {device_id} — {e}")
            return {
                "status": {
                    "device_id": device_id,
                    "firmware_url": firmware_url,
                    "accepted": False,
                    "error": str(e),
                }
            }

    # ------------------------------------------------------------------
    # DMX handlers
    # ------------------------------------------------------------------

    async def _dmx_universe_create(
        self, inputs: dict[str, Any], config: dict[str, Any]
    ) -> dict[str, Any]:
        """Create a DMX universe via the node-dmx bridge.

        Le bridge doit etre lance pour que cette operation fonctionne.
        """
        name = inputs.get("name", "default")
        driver = inputs.get("driver", "enttec-usb-dmx-pro")
        channels = inputs.get("channels", 512)

        try:
            import httpx

            response = await self.dmx._client.post(
                f"{self.dmx.bridge_url}/universes",
                json={
                    "name": name,
                    "driver": driver,
                    "channels": channels,
                },
            )
            response.raise_for_status()
            data = response.json()
            return {
                "universe": {
                    "id": data.get("id", name),
                    "name": name,
                    "driver": driver,
                    "channels": channels,
                    "created": True,
                }
            }
        except Exception as e:
            logger.warning(f"DMX universe creation failed — {e}")
            return {
                "universe": {
                    "name": name,
                    "driver": driver,
                    "channels": channels,
                    "created": False,
                    "error": str(e),
                    "message": "DMX bridge unavailable — start bridge or connect hardware",
                },
            }

    async def _dmx_fixture_set(
        self, inputs: dict[str, Any], config: dict[str, Any]
    ) -> dict[str, Any]:
        """Set fixture channel values in a DMX universe."""
        universe_id = inputs["universe_id"]
        channels_raw = inputs["channels"]
        transition_ms = inputs.get("transition_ms", 0)

        # Normalize channel keys to int
        channels: dict[int, int] = {
            int(k): int(v) for k, v in channels_raw.items()
        }

        frame = DMXFrame(
            universe_id=universe_id,
            channels=channels,
            transition_ms=transition_ms,
        )

        try:
            response = await self.dmx.set_channels(
                universe_id, channels, transition_time=transition_ms
            )
            return {"frame": frame.to_dict(), "response": response}
        except Exception as e:
            logger.warning(f"DMX fixture_set failed for universe {universe_id} — {e}")
            return {
                "frame": frame.to_dict(),
                "error": str(e),
                "available": False,
            }

    async def _dmx_scene_apply(
        self, inputs: dict[str, Any], config: dict[str, Any]
    ) -> dict[str, Any]:
        """Apply a DMX scene — multiple fixtures at once.

        Chaque fixture est un dict avec 'start_channel' et 'values' (list[int]).
        """
        universe_id = inputs["universe_id"]
        fixtures = inputs["fixtures"]
        transition_ms = inputs.get("transition_ms", 0)

        # Flatten all fixture definitions into a single channel map
        merged_channels: dict[int, int] = {}
        for fixture in fixtures:
            start_ch = int(fixture.get("start_channel", 1))
            values = fixture.get("values", [])
            for offset, value in enumerate(values):
                ch = start_ch + offset
                if 1 <= ch <= 512:
                    merged_channels[ch] = max(0, min(255, int(value)))

        frame = DMXFrame(
            universe_id=universe_id,
            channels=merged_channels,
            transition_ms=transition_ms,
        )

        try:
            response = await self.dmx.set_channels(
                universe_id, merged_channels, transition_time=transition_ms
            )
            return {
                "applied": {
                    "universe_id": universe_id,
                    "fixture_count": len(fixtures),
                    "channel_count": len(merged_channels),
                    "transition_ms": transition_ms,
                    "frame": frame.to_dict(),
                },
                "response": response,
            }
        except Exception as e:
            logger.warning(f"DMX scene_apply failed for universe {universe_id} — {e}")
            return {
                "applied": {
                    "universe_id": universe_id,
                    "fixture_count": len(fixtures),
                    "channel_count": len(merged_channels),
                    "error": str(e),
                    "available": False,
                },
            }

    # ------------------------------------------------------------------
    # Serial handlers
    # ------------------------------------------------------------------

    async def _serial_send(
        self, inputs: dict[str, Any], config: dict[str, Any]
    ) -> dict[str, Any]:
        """Send data over a serial port via subprocess (stty + cat/echo).

        Utilise asyncio subprocess pour ne pas bloquer l'event loop.
        Fallback sans pyserial — fonctionne sur macOS/Linux.
        """
        port = inputs["port"]
        data = inputs["data"]
        baudrate = inputs.get("baudrate", 115200)
        encoding = inputs.get("encoding", "utf-8")

        serial_data = SerialData(
            port=port, data=data, baudrate=baudrate, encoding=encoding
        )

        try:
            # Configure port baudrate
            await asyncio.create_subprocess_exec(
                "stty", "-f", port, str(baudrate),
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )

            # Write data to port
            payload = data.encode(encoding) if isinstance(data, str) else data
            proc = await asyncio.create_subprocess_exec(
                "bash", "-c", f"echo -ne '{data}' > {port}",
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.PIPE,
            )
            _, stderr = await asyncio.wait_for(proc.communicate(), timeout=5.0)

            if proc.returncode != 0:
                error_msg = stderr.decode().strip() if stderr else "Unknown error"
                logger.warning(f"Serial send failed on {port}: {error_msg}")
                return {
                    "sent": serial_data.to_dict(),
                    "success": False,
                    "error": error_msg,
                }

            return {"sent": serial_data.to_dict(), "success": True, "bytes_written": len(payload)}
        except FileNotFoundError:
            logger.warning(f"Serial port not found: {port}")
            return {
                "sent": serial_data.to_dict(),
                "success": False,
                "error": f"Port not found: {port}",
            }
        except asyncio.TimeoutError:
            logger.warning(f"Serial send timed out on {port}")
            return {
                "sent": serial_data.to_dict(),
                "success": False,
                "error": "Write timed out",
            }
        except Exception as e:
            logger.warning(f"Serial send error on {port} — {e}")
            return {
                "sent": serial_data.to_dict(),
                "success": False,
                "error": str(e),
            }

    async def _serial_receive(
        self, inputs: dict[str, Any], config: dict[str, Any]
    ) -> dict[str, Any]:
        """Read data from a serial port via subprocess.

        Lit les données disponibles avec timeout.
        """
        port = inputs["port"]
        baudrate = inputs.get("baudrate", 115200)
        timeout = inputs.get("timeout", 5.0)
        encoding = inputs.get("encoding", "utf-8")
        max_bytes = inputs.get("max_bytes", 4096)

        serial_data = SerialData(
            port=port, baudrate=baudrate, encoding=encoding, timeout=timeout
        )

        try:
            # Configure port baudrate
            await asyncio.create_subprocess_exec(
                "stty", "-f", port, str(baudrate),
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )

            # Read from port with timeout
            proc = await asyncio.create_subprocess_exec(
                "head", "-c", str(max_bytes), port,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=timeout
            )

            if proc.returncode != 0 and not stdout:
                error_msg = stderr.decode().strip() if stderr else "Read error"
                return {
                    "received": serial_data.to_dict(),
                    "success": False,
                    "error": error_msg,
                }

            received_data = stdout.decode(encoding, errors="replace") if stdout else ""
            serial_data.data = received_data
            return {
                "received": serial_data.to_dict(),
                "success": True,
                "bytes_read": len(stdout) if stdout else 0,
            }
        except FileNotFoundError:
            logger.warning(f"Serial port not found: {port}")
            return {
                "received": serial_data.to_dict(),
                "success": False,
                "error": f"Port not found: {port}",
            }
        except asyncio.TimeoutError:
            logger.warning(f"Serial receive timed out on {port}")
            return {
                "received": serial_data.to_dict(),
                "success": False,
                "error": f"Read timed out after {timeout}s",
            }
        except Exception as e:
            logger.warning(f"Serial receive error on {port} — {e}")
            return {
                "received": serial_data.to_dict(),
                "success": False,
                "error": str(e),
            }

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def initialize(self) -> None:
        """Initialize hardware worker — start DMX bridge if configured."""
        logger.info("HardwareWorker initializing")
        try:
            await self.dmx.start()
        except Exception as e:
            logger.warning(f"DMX bridge not available at init — {e}")

    async def shutdown(self) -> None:
        """Shutdown hardware worker — cleanup connections."""
        logger.info("HardwareWorker shutting down")
        try:
            if self._esp32 is not None:
                await self._esp32.close()
        except Exception as e:
            logger.warning(f"Error closing ESP32 client: {e}")

        try:
            if self._dmx is not None:
                await self._dmx.stop()
        except Exception as e:
            logger.warning(f"Error stopping DMX controller: {e}")
