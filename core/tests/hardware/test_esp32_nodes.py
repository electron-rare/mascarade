"""Tests for ESP32 control nodes with mocked hardware."""

from __future__ import annotations

import asyncio
import base64

import httpx
from pydantic import ValidationError

from mascarade.hardware.nodes.esp32 import (
    ESP32Client,
    ESP32ConnectionConfig,
    ESP32ConnectionError,
    ESP32Error,
    ESP32TimeoutError,
    execute_discover_node,
    execute_gpio_node,
    execute_ota_node,
    execute_sensor_node,
)
from mascarade.hardware.types import GPIODirection, GPIOPull, GPIOState
from mascarade.node_engine.base import NodeExecutionContext

# --- ESP32ConnectionConfig Tests ---


def test_esp32_connection_config_defaults():
    """ESP32ConnectionConfig initializes with correct defaults."""
    config = ESP32ConnectionConfig(device_id="esp32-01.local")
    assert config.device_id == "esp32-01.local"
    assert config.protocol == "http"
    assert config.port == 80
    assert config.mqtt_broker is None
    assert config.mqtt_topic_prefix == "mascarade/esp32"
    assert config.timeout_ms == 5000
    assert config.retry_count == 3


def test_esp32_connection_config_custom():
    """ESP32ConnectionConfig accepts custom values."""
    config = ESP32ConnectionConfig(
        device_id="192.168.1.100",
        protocol="mqtt",
        port=1883,
        mqtt_broker="192.168.1.1",
        mqtt_topic_prefix="custom/topic",
        timeout_ms=10000,
        retry_count=5,
    )
    assert config.device_id == "192.168.1.100"
    assert config.protocol == "mqtt"
    assert config.port == 1883
    assert config.mqtt_broker == "192.168.1.1"
    assert config.timeout_ms == 10000
    assert config.retry_count == 5


def test_esp32_connection_config_timeout_validation():
    """ESP32ConnectionConfig validates timeout range."""
    try:
        ESP32ConnectionConfig(device_id="test", timeout_ms=50)
        assert False, "Should have raised ValidationError"
    except ValidationError:
        pass

    try:
        ESP32ConnectionConfig(device_id="test", timeout_ms=40000)
        assert False, "Should have raised ValidationError"
    except ValidationError:
        pass


def test_esp32_connection_config_retry_validation():
    """ESP32ConnectionConfig validates retry count range."""
    try:
        ESP32ConnectionConfig(device_id="test", retry_count=-1)
        assert False, "Should have raised ValidationError"
    except ValidationError:
        pass

    try:
        ESP32ConnectionConfig(device_id="test", retry_count=11)
        assert False, "Should have raised ValidationError"
    except ValidationError:
        pass


# --- ESP32Client Tests ---


def test_esp32_client_initialization():
    """ESP32Client initializes with correct timeout."""
    config = ESP32ConnectionConfig(device_id="esp32-test", timeout_ms=3000)
    client = ESP32Client(config)

    assert client.config == config
    assert client._http_client.timeout.read == 3.0


def test_esp32_client_custom_http_client():
    """ESP32Client accepts custom HTTP client."""
    config = ESP32ConnectionConfig(device_id="test")
    custom_client = httpx.AsyncClient(timeout=10.0)
    client = ESP32Client(config, http_client=custom_client)

    assert client._http_client == custom_client
    assert client._owns_http_client is False


async def test_esp32_client_close():
    """ESP32Client closes HTTP client when owned."""
    config = ESP32ConnectionConfig(device_id="test")
    client = ESP32Client(config)
    await client.close()


async def test_esp32_client_close_custom_client():
    """ESP32Client does not close custom HTTP client."""
    config = ESP32ConnectionConfig(device_id="test")
    custom_client = httpx.AsyncClient()
    client = ESP32Client(config, http_client=custom_client)
    await client.close()
    # Custom client should still be usable
    await custom_client.aclose()


async def test_esp32_client_discover_placeholder():
    """ESP32Client.discover returns empty list (placeholder implementation)."""
    config = ESP32ConnectionConfig(device_id="test")
    client = ESP32Client(config)

    try:
        devices = await client.discover()
        assert devices == []
    finally:
        await client.close()


# --- GPIO Operation Tests ---


async def test_esp32_gpio_operation_success():
    """ESP32Client.gpio_operation handles successful response."""

    class _FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def post(self, url, json):
            class _FakeResponse:
                status_code = 200

                def raise_for_status(self):
                    pass

                def json(self):
                    return {
                        "pin": 5,
                        "direction": "output",
                        "value": True,
                        "pull": "none",
                    }

            return _FakeResponse()

        async def aclose(self):
            pass

    config = ESP32ConnectionConfig(device_id="192.168.1.100")
    client = ESP32Client(config, http_client=_FakeAsyncClient())

    pin_config = GPIOState(pin=5, direction=GPIODirection.OUTPUT, value=True)
    result = await client.gpio_operation(pin_config)

    assert result.pin == 5
    assert result.direction == GPIODirection.OUTPUT
    assert result.value is True
    await client.close()


async def test_esp32_gpio_operation_with_pwm():
    """ESP32Client.gpio_operation handles PWM parameters."""

    class _FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def post(self, url, json):
            class _FakeResponse:
                status_code = 200

                def raise_for_status(self):
                    pass

                def json(self):
                    return {
                        "pin": 18,
                        "direction": "output",
                        "value": False,
                        "pull": "none",
                        "pwm_duty": 0.5,
                        "pwm_freq": 1000,
                    }

            return _FakeResponse()

        async def aclose(self):
            pass

    config = ESP32ConnectionConfig(device_id="test")
    client = ESP32Client(config, http_client=_FakeAsyncClient())

    pin_config = GPIOState(
        pin=18, direction=GPIODirection.OUTPUT, pwm_duty=0.5, pwm_freq=1000
    )
    result = await client.gpio_operation(pin_config)

    assert result.pwm_duty == 0.5
    assert result.pwm_freq == 1000
    await client.close()


async def test_esp32_gpio_operation_timeout_with_retry():
    """ESP32Client.gpio_operation retries on timeout."""
    attempt = 0

    class _FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def post(self, url, json):
            nonlocal attempt
            attempt += 1
            if attempt < 3:
                raise httpx.ReadTimeout("timeout")

            class _FakeResponse:
                status_code = 200

                def raise_for_status(self):
                    pass

                def json(self):
                    return {
                        "pin": 5,
                        "direction": "input",
                        "value": False,
                        "pull": "up",
                    }

            return _FakeResponse()

        async def aclose(self):
            pass

    config = ESP32ConnectionConfig(device_id="test", retry_count=3)
    client = ESP32Client(config, http_client=_FakeAsyncClient())

    pin_config = GPIOState(pin=5, direction=GPIODirection.INPUT, pull=GPIOPull.UP)
    result = await client.gpio_operation(pin_config)

    assert attempt == 3
    assert result.pin == 5
    await client.close()


async def test_esp32_gpio_operation_timeout_exhausted():
    """ESP32Client.gpio_operation raises ESP32TimeoutError after retries exhausted."""

    class _FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def post(self, url, json):
            raise httpx.ReadTimeout("timeout")

        async def aclose(self):
            pass

    config = ESP32ConnectionConfig(device_id="test", retry_count=2)
    client = ESP32Client(config, http_client=_FakeAsyncClient())

    pin_config = GPIOState(pin=5, direction=GPIODirection.OUTPUT, value=True)

    try:
        await client.gpio_operation(pin_config)
        assert False, "Should have raised ESP32TimeoutError"
    except ESP32TimeoutError as exc:
        assert "timed out after 3 attempts" in str(exc)
    finally:
        await client.close()


async def test_esp32_gpio_operation_http_error():
    """ESP32Client.gpio_operation raises ESP32ConnectionError on HTTP error."""

    class _FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def post(self, url, json):
            class _FakeResponse:
                status_code = 404

                def raise_for_status(self):
                    raise httpx.HTTPStatusError(
                        "Not Found", request=None, response=self
                    )

            return _FakeResponse()

        async def aclose(self):
            pass

    config = ESP32ConnectionConfig(device_id="test", retry_count=0)
    client = ESP32Client(config, http_client=_FakeAsyncClient())

    pin_config = GPIOState(pin=5)

    try:
        await client.gpio_operation(pin_config)
        assert False, "Should have raised ESP32ConnectionError"
    except ESP32ConnectionError as exc:
        assert "404" in str(exc)
    finally:
        await client.close()


async def test_esp32_gpio_operation_connection_error_with_retry():
    """ESP32Client.gpio_operation retries on connection error."""
    attempt = 0

    class _FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def post(self, url, json):
            nonlocal attempt
            attempt += 1
            if attempt < 2:
                raise httpx.ConnectError("connection failed")

            class _FakeResponse:
                status_code = 200

                def raise_for_status(self):
                    pass

                def json(self):
                    return {
                        "pin": 5,
                        "direction": "input",
                        "value": False,
                        "pull": "none",
                    }

            return _FakeResponse()

        async def aclose(self):
            pass

    config = ESP32ConnectionConfig(device_id="test", retry_count=3)
    client = ESP32Client(config, http_client=_FakeAsyncClient())

    pin_config = GPIOState(pin=5)
    result = await client.gpio_operation(pin_config)

    assert attempt == 2
    assert result.pin == 5
    await client.close()


async def test_esp32_gpio_operation_wrong_protocol():
    """ESP32Client.gpio_operation raises error for non-HTTP protocol."""
    config = ESP32ConnectionConfig(device_id="test", protocol="mqtt")
    client = ESP32Client(config)

    pin_config = GPIOState(pin=5)

    try:
        await client.gpio_operation(pin_config)
        assert False, "Should have raised ESP32Error"
    except ESP32Error as exc:
        assert "only supported over HTTP" in str(exc)
    finally:
        await client.close()


# --- Sensor Read Tests ---


async def test_esp32_read_sensor_success():
    """ESP32Client.read_sensor handles successful response."""

    class _FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def get(self, url):
            class _FakeResponse:
                status_code = 200

                def raise_for_status(self):
                    pass

                def json(self):
                    return {
                        "sensor_id": "dht22-01",
                        "sensor_type": "temperature",
                        "value": 23.5,
                        "unit": "°C",
                        "timestamp_ms": 1678900000000,
                        "quality": 0.98,
                        "raw": 2350,
                    }

            return _FakeResponse()

        async def aclose(self):
            pass

    config = ESP32ConnectionConfig(device_id="test")
    client = ESP32Client(config, http_client=_FakeAsyncClient())

    reading = await client.read_sensor("dht22-01")

    assert reading.sensor_id == "dht22-01"
    assert reading.sensor_type == "temperature"
    assert reading.value == 23.5
    assert reading.unit == "°C"
    assert reading.quality == 0.98
    assert reading.raw == 2350
    await client.close()


async def test_esp32_read_sensor_timeout_with_retry():
    """ESP32Client.read_sensor retries on timeout."""
    attempt = 0

    class _FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def get(self, url):
            nonlocal attempt
            attempt += 1
            if attempt < 3:
                raise httpx.ReadTimeout("timeout")

            class _FakeResponse:
                status_code = 200

                def raise_for_status(self):
                    pass

                def json(self):
                    return {
                        "sensor_id": "test",
                        "sensor_type": "test",
                        "value": 42.0,
                        "unit": "test",
                        "timestamp_ms": 1000,
                    }

            return _FakeResponse()

        async def aclose(self):
            pass

    config = ESP32ConnectionConfig(device_id="test", retry_count=3)
    client = ESP32Client(config, http_client=_FakeAsyncClient())

    reading = await client.read_sensor("test")

    assert attempt == 3
    assert reading.value == 42.0
    await client.close()


async def test_esp32_read_sensor_timeout_exhausted():
    """ESP32Client.read_sensor raises ESP32TimeoutError after retries exhausted."""

    class _FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def get(self, url):
            raise httpx.ReadTimeout("timeout")

        async def aclose(self):
            pass

    config = ESP32ConnectionConfig(device_id="test", retry_count=1)
    client = ESP32Client(config, http_client=_FakeAsyncClient())

    try:
        await client.read_sensor("test")
        assert False, "Should have raised ESP32TimeoutError"
    except ESP32TimeoutError as exc:
        assert "timed out after 2 attempts" in str(exc)
    finally:
        await client.close()


async def test_esp32_read_sensor_wrong_protocol():
    """ESP32Client.read_sensor raises error for non-HTTP protocol."""
    config = ESP32ConnectionConfig(device_id="test", protocol="websocket")
    client = ESP32Client(config)

    try:
        await client.read_sensor("test")
        assert False, "Should have raised ESP32Error"
    except ESP32Error as exc:
        assert "only supported over HTTP" in str(exc)
    finally:
        await client.close()


# --- OTA Update Tests ---


async def test_esp32_ota_update_success():
    """ESP32Client.ota_update handles successful update."""

    class _FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def post(self, url, files, data, timeout):
            class _FakeResponse:
                status_code = 200

                def raise_for_status(self):
                    pass

                def json(self):
                    return {"success": True, "error": None}

            return _FakeResponse()

        async def aclose(self):
            pass

    config = ESP32ConnectionConfig(device_id="test")
    client = ESP32Client(config, http_client=_FakeAsyncClient())

    firmware = b"\x00\x01\x02\x03\x04\x05"
    success, error = await client.ota_update(firmware, verify=True)

    assert success is True
    assert error is None
    await client.close()


async def test_esp32_ota_update_failure():
    """ESP32Client.ota_update handles update failure."""

    class _FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def post(self, url, files, data, timeout):
            class _FakeResponse:
                status_code = 200

                def raise_for_status(self):
                    pass

                def json(self):
                    return {"success": False, "error": "Verification failed"}

            return _FakeResponse()

        async def aclose(self):
            pass

    config = ESP32ConnectionConfig(device_id="test")
    client = ESP32Client(config, http_client=_FakeAsyncClient())

    firmware = b"\x00\x01\x02\x03\x04\x05"
    success, error = await client.ota_update(firmware, verify=True)

    assert success is False
    assert error == "Verification failed"
    await client.close()


async def test_esp32_ota_update_timeout():
    """ESP32Client.ota_update handles timeout gracefully."""

    class _FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def post(self, url, files, data, timeout):
            raise httpx.ReadTimeout("OTA timeout")

        async def aclose(self):
            pass

    config = ESP32ConnectionConfig(device_id="test")
    client = ESP32Client(config, http_client=_FakeAsyncClient())

    firmware = b"\x00\x01\x02\x03\x04\x05"
    success, error = await client.ota_update(firmware)

    assert success is False
    assert "timed out" in error
    await client.close()


async def test_esp32_ota_update_wrong_protocol():
    """ESP32Client.ota_update raises error for non-HTTP protocol."""
    config = ESP32ConnectionConfig(device_id="test", protocol="mqtt")
    client = ESP32Client(config)

    firmware = b"\x00\x01\x02\x03"

    try:
        await client.ota_update(firmware)
        assert False, "Should have raised ESP32Error"
    except ESP32Error as exc:
        assert "only supported over HTTP" in str(exc)
    finally:
        await client.close()


# --- Node Execution Tests ---


def test_execute_discover_node():
    """execute_discover_node returns empty list (placeholder)."""

    class _FakeContext(NodeExecutionContext):
        def __init__(self):
            self._inputs = {}

        def get_input(self, name, default=None):
            return self._inputs.get(name, default)

    context = _FakeContext()
    result = asyncio.run(execute_discover_node(context))

    assert result.success is True
    assert result.outputs.get("devices") == []
    assert result.outputs.get("count") == 0


def test_execute_gpio_node_missing_device():
    """execute_gpio_node returns error when device input missing."""

    class _FakeContext(NodeExecutionContext):
        def __init__(self):
            self._inputs = {}

        def get_input(self, name, default=None):
            return self._inputs.get(name, default)

    context = _FakeContext()
    result = asyncio.run(execute_gpio_node(context))

    assert result.success is False
    assert "Missing required input: device" in result.error_message


def test_execute_gpio_node_missing_pin_config():
    """execute_gpio_node returns error when pin_config input missing."""

    class _FakeContext(NodeExecutionContext):
        def __init__(self):
            self._inputs = {"device": {"device_id": "test"}}

        def get_input(self, name, default=None):
            return self._inputs.get(name, default)

    context = _FakeContext()
    result = asyncio.run(execute_gpio_node(context))

    assert result.success is False
    assert "Missing required input: pin_config" in result.error_message


def test_execute_gpio_node_invalid_config():
    """execute_gpio_node returns error for invalid configuration."""

    class _FakeContext(NodeExecutionContext):
        def __init__(self):
            self._inputs = {
                "device": {"device_id": "test"},
                "pin_config": {"pin": -1},  # Invalid pin
            }

        def get_input(self, name, default=None):
            return self._inputs.get(name, default)

    context = _FakeContext()
    result = asyncio.run(execute_gpio_node(context))

    assert result.success is False
    assert "Invalid input configuration" in result.error_message


def test_execute_sensor_node_missing_device():
    """execute_sensor_node returns error when device input missing."""

    class _FakeContext(NodeExecutionContext):
        def __init__(self):
            self._inputs = {}

        def get_input(self, name, default=None):
            return self._inputs.get(name, default)

    context = _FakeContext()
    result = asyncio.run(execute_sensor_node(context))

    assert result.success is False
    assert "Missing required input: device" in result.error_message


def test_execute_sensor_node_missing_sensor_id():
    """execute_sensor_node returns error when sensor_id input missing."""

    class _FakeContext(NodeExecutionContext):
        def __init__(self):
            self._inputs = {"device": {"device_id": "test"}}

        def get_input(self, name, default=None):
            return self._inputs.get(name, default)

    context = _FakeContext()
    result = asyncio.run(execute_sensor_node(context))

    assert result.success is False
    assert "Missing required input: sensor_id" in result.error_message


def test_execute_ota_node_missing_device():
    """execute_ota_node returns error when device input missing."""

    class _FakeContext(NodeExecutionContext):
        def __init__(self):
            self._inputs = {}
            self._required_capabilities = []

        def get_input(self, name, default=None):
            return self._inputs.get(name, default)

        def require_capability(self, capability):
            self._required_capabilities.append(capability)

    context = _FakeContext()
    result = asyncio.run(execute_ota_node(context))

    assert result.success is False
    assert "Missing required input: device" in result.error_message
    assert "hardware.ota.flash" in context._required_capabilities


def test_execute_ota_node_missing_firmware():
    """execute_ota_node returns error when firmware input missing."""

    class _FakeContext(NodeExecutionContext):
        def __init__(self):
            self._inputs = {"device": {"device_id": "test"}}
            self._required_capabilities = []

        def get_input(self, name, default=None):
            return self._inputs.get(name, default)

        def require_capability(self, capability):
            self._required_capabilities.append(capability)

    context = _FakeContext()
    result = asyncio.run(execute_ota_node(context))

    assert result.success is False
    assert "Missing required input: firmware" in result.error_message


def test_execute_ota_node_base64_firmware():
    """execute_ota_node decodes base64-encoded firmware."""

    class _FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def post(self, url, files, data, timeout):
            class _FakeResponse:
                status_code = 200

                def raise_for_status(self):
                    pass

                def json(self):
                    return {"success": True, "error": None}

            return _FakeResponse()

        async def aclose(self):
            pass

    class _FakeContext(NodeExecutionContext):
        def __init__(self):
            firmware_bytes = b"test_firmware"
            firmware_b64 = base64.b64encode(firmware_bytes).decode("utf-8")
            self._inputs = {
                "device": {"device_id": "test"},
                "firmware": firmware_b64,
                "verify": True,
            }
            self._required_capabilities = []

        def get_input(self, name, default=None):
            return self._inputs.get(name, default)

        def require_capability(self, capability):
            self._required_capabilities.append(capability)

    import mascarade.hardware.nodes.esp32 as esp32_module

    original_client = esp32_module.ESP32Client

    class _PatchedClient:
        def __init__(self, config):
            self.config = config
            self._http_client = _FakeAsyncClient()
            self._owns_http_client = True

        async def close(self):
            pass

        async def ota_update(self, firmware, verify=True):
            return True, None

    esp32_module.ESP32Client = _PatchedClient

    try:
        context = _FakeContext()
        result = asyncio.run(execute_ota_node(context))

        assert result.success is True
        assert result.outputs.get("success") is True
    finally:
        esp32_module.ESP32Client = original_client
