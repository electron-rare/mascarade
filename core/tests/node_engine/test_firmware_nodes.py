"""Tests pour les nœuds firmware du domaine electronics."""

import base64

import pytest

from mascarade.node_engine.types import PortDirection
from mascarade.node_engine.workers.electronics.firmware_nodes import (
    CompileConfig,
    CompileNode,
    FlashPrepareConfig,
    FlashPrepareNode,
    NodeConfig,
    SizeAnalysisConfig,
    SizeAnalysisNode,
)

# Tests pour NodeConfig et ses sous-classes


def test_node_config_base():
    """NodeConfig de base peut être instancié."""
    config = NodeConfig()
    assert config is not None


def test_compile_config_defaults():
    """CompileConfig a des valeurs par défaut correctes."""
    config = CompileConfig()
    assert config.timeout_seconds == 300
    assert config.idf_path == ""
    assert config.clean_build is False


def test_compile_config_custom():
    """CompileConfig accepte des valeurs personnalisées."""
    config = CompileConfig(
        timeout_seconds=600,
        idf_path="/opt/esp-idf",
        clean_build=True,
    )
    assert config.timeout_seconds == 600
    assert config.idf_path == "/opt/esp-idf"
    assert config.clean_build is True


def test_flash_prepare_config_defaults():
    """FlashPrepareConfig peut être instancié."""
    config = FlashPrepareConfig()
    assert config is not None


def test_size_analysis_config_defaults():
    """SizeAnalysisConfig peut être instancié."""
    config = SizeAnalysisConfig()
    assert config is not None


# Tests pour CompileNode


def test_compile_node_creation():
    """CompileNode peut être créé avec et sans configuration."""
    node = CompileNode()
    assert node.node_type == "electronics.firmware.compile"
    assert isinstance(node.config, CompileConfig)


def test_compile_node_custom_config():
    """CompileNode accepte une configuration personnalisée."""
    config = CompileConfig(
        timeout_seconds=600,
        idf_path="/custom/esp-idf",
    )
    node = CompileNode(config=config)
    assert node.config is config
    assert node.config.timeout_seconds == 600
    assert node.config.idf_path == "/custom/esp-idf"


def test_compile_node_input_ports():
    """CompileNode définit les ports d'entrée corrects."""
    node = CompileNode()
    assert len(node.input_ports) == 4

    # Port source_path
    source_port = node.input_ports[0]
    assert source_port.name == "source_path"
    assert source_port.direction == PortDirection.INPUT
    assert source_port.port_type == "string"
    assert source_port.optional is False

    # Port target
    target_port = node.input_ports[1]
    assert target_port.name == "target"
    assert target_port.direction == PortDirection.INPUT
    assert target_port.port_type == "string"
    assert target_port.optional is False

    # Port framework
    framework_port = node.input_ports[2]
    assert framework_port.name == "framework"
    assert framework_port.direction == PortDirection.INPUT
    assert framework_port.port_type == "string"
    assert framework_port.optional is True
    assert framework_port.default_value == "esp-idf"

    # Port build_flags
    flags_port = node.input_ports[3]
    assert flags_port.name == "build_flags"
    assert flags_port.direction == PortDirection.INPUT
    assert flags_port.port_type == "json"
    assert flags_port.optional is True
    assert flags_port.default_value == []


def test_compile_node_output_ports():
    """CompileNode définit les ports de sortie corrects."""
    node = CompileNode()
    assert len(node.output_ports) == 3

    # Port firmware
    firmware_port = node.output_ports[0]
    assert firmware_port.name == "firmware"
    assert firmware_port.direction == PortDirection.OUTPUT
    assert firmware_port.port_type == "electronics.FirmwareBinary"

    # Port build_log
    log_port = node.output_ports[1]
    assert log_port.name == "build_log"
    assert log_port.direction == PortDirection.OUTPUT
    assert log_port.port_type == "string"

    # Port success
    success_port = node.output_ports[2]
    assert success_port.name == "success"
    assert success_port.direction == PortDirection.OUTPUT
    assert success_port.port_type == "boolean"


@pytest.mark.asyncio
async def test_compile_node_execute_missing_source_path():
    """CompileNode lève ValueError si source_path est manquant."""
    node = CompileNode()
    inputs = {"target": "esp32"}

    with pytest.raises(ValueError) as exc_info:
        await node.execute(inputs)

    assert "source_path" in str(exc_info.value)


@pytest.mark.asyncio
async def test_compile_node_execute_missing_target():
    """CompileNode lève ValueError si target est manquant."""
    node = CompileNode()
    inputs = {"source_path": "/tmp/test"}

    with pytest.raises(ValueError) as exc_info:
        await node.execute(inputs)

    assert "target" in str(exc_info.value)


@pytest.mark.asyncio
async def test_compile_node_execute_empty_source_path():
    """CompileNode lève ValueError si source_path est vide."""
    node = CompileNode()
    inputs = {"source_path": "", "target": "esp32"}

    with pytest.raises(ValueError) as exc_info:
        await node.execute(inputs)

    assert "source_path" in str(exc_info.value)


@pytest.mark.asyncio
async def test_compile_node_execute_empty_target():
    """CompileNode lève ValueError si target est vide."""
    node = CompileNode()
    inputs = {"source_path": "/tmp/test", "target": ""}

    with pytest.raises(ValueError) as exc_info:
        await node.execute(inputs)

    assert "target" in str(exc_info.value)


@pytest.mark.asyncio
async def test_compile_node_execute_nonexistent_path(tmp_path):
    """CompileNode lève ValueError si le chemin source n'existe pas."""
    node = CompileNode()
    inputs = {
        "source_path": str(tmp_path / "nonexistent"),
        "target": "esp32",
    }

    with pytest.raises(ValueError) as exc_info:
        await node.execute(inputs)

    assert "does not exist" in str(exc_info.value)


@pytest.mark.asyncio
async def test_compile_node_execute_unsupported_framework(tmp_path):
    """CompileNode lève ValueError pour un framework non supporté."""
    node = CompileNode()
    inputs = {
        "source_path": str(tmp_path),
        "target": "esp32",
        "framework": "unsupported",
    }

    with pytest.raises(ValueError) as exc_info:
        await node.execute(inputs)

    assert "Unsupported framework" in str(exc_info.value)


def test_compile_node_parse_size_esp_idf():
    """CompileNode parse correctement les tailles ESP-IDF."""
    node = CompileNode()
    build_log = """
    Total sizes:
    Used static DRAM:   12345 bytes (  67890 remain, 15.3% used)
    Used static IRAM:   23456 bytes (  78901 remain, 22.9% used)
    Flash code:        123456 bytes
    Flash rodata:       34567 bytes
    """

    sections = node._parse_size_esp_idf(build_log)

    assert sections["dram"] == 12345
    assert sections["iram"] == 23456
    assert sections["flash_code"] == 123456
    assert sections["flash_rodata"] == 34567


def test_compile_node_parse_size_platformio():
    """CompileNode parse correctement les tailles PlatformIO."""
    node = CompileNode()
    build_log = """
    RAM:   [====      ]  40.0% (used 12345 bytes from 65536 bytes)
    Flash: [======    ]  60.0% (used 123456 bytes from 1048576 bytes)
    """

    sections = node._parse_size_platformio(build_log)

    assert sections["ram"] == 12345
    assert sections["flash"] == 123456


# Tests pour FlashPrepareNode


def test_flash_prepare_node_creation():
    """FlashPrepareNode peut être créé."""
    node = FlashPrepareNode()
    assert node.node_type == "electronics.firmware.flash_prepare"
    assert isinstance(node.config, FlashPrepareConfig)


def test_flash_prepare_node_input_ports():
    """FlashPrepareNode définit les ports d'entrée corrects."""
    node = FlashPrepareNode()
    assert len(node.input_ports) == 2

    # Port firmware
    firmware_port = node.input_ports[0]
    assert firmware_port.name == "firmware"
    assert firmware_port.direction == PortDirection.INPUT
    assert firmware_port.port_type == "electronics.FirmwareBinary"
    assert firmware_port.optional is False

    # Port flash_config
    config_port = node.input_ports[1]
    assert config_port.name == "flash_config"
    assert config_port.direction == PortDirection.INPUT
    assert config_port.port_type == "json"
    assert config_port.optional is True


def test_flash_prepare_node_output_ports():
    """FlashPrepareNode définit les ports de sortie corrects."""
    node = FlashPrepareNode()
    assert len(node.output_ports) == 2

    # Port flash_command
    command_port = node.output_ports[0]
    assert command_port.name == "flash_command"
    assert command_port.direction == PortDirection.OUTPUT
    assert command_port.port_type == "string"

    # Port merged_binary
    binary_port = node.output_ports[1]
    assert binary_port.name == "merged_binary"
    assert binary_port.direction == PortDirection.OUTPUT
    assert binary_port.port_type == "binary"
    assert binary_port.optional is True


@pytest.mark.asyncio
async def test_flash_prepare_node_execute_missing_firmware():
    """FlashPrepareNode lève ValueError si firmware est manquant."""
    node = FlashPrepareNode()
    inputs = {}

    with pytest.raises(ValueError) as exc_info:
        await node.execute(inputs)

    assert "firmware" in str(exc_info.value)


@pytest.mark.asyncio
async def test_flash_prepare_node_execute_empty_firmware():
    """FlashPrepareNode lève ValueError si firmware est vide."""
    node = FlashPrepareNode()
    inputs = {"firmware": None}

    with pytest.raises(ValueError) as exc_info:
        await node.execute(inputs)

    assert "firmware" in str(exc_info.value)


@pytest.mark.asyncio
async def test_flash_prepare_node_execute_basic():
    """FlashPrepareNode génère une commande flash basique."""
    node = FlashPrepareNode()
    firmware = {
        "binary": base64.b64encode(b"fake_binary").decode(),
        "target": "esp32",
        "framework": "esp-idf",
        "size_bytes": 1024,
    }
    inputs = {"firmware": firmware}

    result = await node.execute(inputs)

    assert "flash_command" in result
    assert "merged_binary" in result
    assert "esptool.py" in result["flash_command"]
    assert "esp32" in result["flash_command"]
    assert result["merged_binary"] is None  # Not implemented yet


@pytest.mark.asyncio
async def test_flash_prepare_node_execute_with_config():
    """FlashPrepareNode applique la configuration flash personnalisée."""
    node = FlashPrepareNode()
    firmware = {
        "binary": base64.b64encode(b"fake_binary").decode(),
        "target": "esp32s3",
        "framework": "esp-idf",
        "size_bytes": 2048,
    }
    flash_config = {
        "port": "/dev/ttyUSB1",
        "baud": 921600,
        "flash_mode": "qio",
        "flash_freq": "80m",
        "flash_size": "8MB",
    }
    inputs = {"firmware": firmware, "flash_config": flash_config}

    result = await node.execute(inputs)

    flash_command = result["flash_command"]
    assert "/dev/ttyUSB1" in flash_command
    assert "921600" in flash_command
    assert "qio" in flash_command
    assert "80m" in flash_command
    assert "8MB" in flash_command
    assert "esp32s3" in flash_command


@pytest.mark.asyncio
async def test_flash_prepare_node_execute_platformio():
    """FlashPrepareNode génère une commande pour PlatformIO."""
    node = FlashPrepareNode()
    firmware = {
        "binary": base64.b64encode(b"fake_binary").decode(),
        "target": "esp32",
        "framework": "platformio",
        "size_bytes": 1024,
    }
    inputs = {"firmware": firmware}

    result = await node.execute(inputs)

    assert "flash_command" in result
    # Should still use esptool.py for ESP32 targets
    assert "esptool.py" in result["flash_command"]


def test_flash_prepare_node_generate_esptool_command():
    """FlashPrepareNode génère une commande esptool correcte."""
    node = FlashPrepareNode()
    firmware = {
        "target": "esp32c3",
        "framework": "esp-idf",
    }
    config = {
        "port": "/dev/ttyUSB0",
        "baud": 460800,
        "flash_mode": "dio",
        "flash_freq": "40m",
        "flash_size": "4MB",
    }

    command = node._generate_esptool_command(firmware, config)

    assert "esptool.py" in command
    assert "--chip esp32c3" in command
    assert "--port /dev/ttyUSB0" in command
    assert "--baud 460800" in command
    assert "write_flash" in command
    assert "--flash_mode dio" in command
    assert "--flash_freq 40m" in command
    assert "--flash_size 4MB" in command
    assert "0x10000 firmware.bin" in command


# Tests pour SizeAnalysisNode


def test_size_analysis_node_creation():
    """SizeAnalysisNode peut être créé."""
    node = SizeAnalysisNode()
    assert node.node_type == "electronics.firmware.size_analysis"
    assert isinstance(node.config, SizeAnalysisConfig)


def test_size_analysis_node_input_ports():
    """SizeAnalysisNode définit les ports d'entrée corrects."""
    node = SizeAnalysisNode()
    assert len(node.input_ports) == 1

    # Port firmware
    firmware_port = node.input_ports[0]
    assert firmware_port.name == "firmware"
    assert firmware_port.direction == PortDirection.INPUT
    assert firmware_port.port_type == "electronics.FirmwareBinary"
    assert firmware_port.optional is False


def test_size_analysis_node_output_ports():
    """SizeAnalysisNode définit les ports de sortie corrects."""
    node = SizeAnalysisNode()
    assert len(node.output_ports) == 2

    # Port size_report
    report_port = node.output_ports[0]
    assert report_port.name == "size_report"
    assert report_port.direction == PortDirection.OUTPUT
    assert report_port.port_type == "json"

    # Port warnings
    warnings_port = node.output_ports[1]
    assert warnings_port.name == "warnings"
    assert warnings_port.direction == PortDirection.OUTPUT
    assert warnings_port.port_type == "json"


@pytest.mark.asyncio
async def test_size_analysis_node_execute_missing_firmware():
    """SizeAnalysisNode lève ValueError si firmware est manquant."""
    node = SizeAnalysisNode()
    inputs = {}

    with pytest.raises(ValueError) as exc_info:
        await node.execute(inputs)

    assert "firmware" in str(exc_info.value)


@pytest.mark.asyncio
async def test_size_analysis_node_execute_empty_firmware():
    """SizeAnalysisNode lève ValueError si firmware est vide."""
    node = SizeAnalysisNode()
    inputs = {"firmware": None}

    with pytest.raises(ValueError) as exc_info:
        await node.execute(inputs)

    assert "firmware" in str(exc_info.value)


@pytest.mark.asyncio
async def test_size_analysis_node_execute_basic():
    """SizeAnalysisNode génère un rapport de taille basique."""
    node = SizeAnalysisNode()
    firmware = {
        "size_bytes": 512000,
        "target": "esp32",
        "framework": "esp-idf",
        "sections": {
            "dram": 20000,
            "iram": 30000,
            "flash_code": 400000,
            "flash_rodata": 50000,
        },
    }
    inputs = {"firmware": firmware}

    result = await node.execute(inputs)

    assert "size_report" in result
    assert "warnings" in result

    size_report = result["size_report"]
    assert size_report["total_size_bytes"] == 512000
    assert size_report["total_size_kb"] == 500.0
    assert size_report["target"] == "esp32"
    assert size_report["framework"] == "esp-idf"
    assert size_report["flash_size_bytes"] == 4 * 1024 * 1024
    assert "usage_percent" in size_report

    warnings = result["warnings"]
    assert isinstance(warnings, list)


@pytest.mark.asyncio
async def test_size_analysis_node_execute_small_firmware():
    """SizeAnalysisNode génère peu d'avertissements pour un petit firmware."""
    node = SizeAnalysisNode()
    firmware = {
        "size_bytes": 100000,  # ~100KB, <50% of 4MB
        "target": "esp32",
        "framework": "esp-idf",
        "sections": {},
    }
    inputs = {"firmware": firmware}

    result = await node.execute(inputs)

    size_report = result["size_report"]
    warnings = result["warnings"]

    assert size_report["usage_percent"] < 50
    assert len(warnings) == 0  # No warnings for small firmware


@pytest.mark.asyncio
async def test_size_analysis_node_execute_medium_firmware():
    """SizeAnalysisNode génère un avertissement info pour un firmware moyen."""
    node = SizeAnalysisNode()
    firmware = {
        "size_bytes": 2500000,  # ~2.5MB, >50% of 4MB
        "target": "esp32",
        "framework": "esp-idf",
        "sections": {},
    }
    inputs = {"firmware": firmware}

    result = await node.execute(inputs)

    size_report = result["size_report"]
    warnings = result["warnings"]

    assert 50 < size_report["usage_percent"] < 75
    assert len(warnings) > 0
    assert "Info:" in warnings[0]


@pytest.mark.asyncio
async def test_size_analysis_node_execute_large_firmware():
    """SizeAnalysisNode génère un avertissement pour un firmware large."""
    node = SizeAnalysisNode()
    firmware = {
        "size_bytes": 3200000,  # ~3.2MB, >75% of 4MB
        "target": "esp32",
        "framework": "esp-idf",
        "sections": {},
    }
    inputs = {"firmware": firmware}

    result = await node.execute(inputs)

    size_report = result["size_report"]
    warnings = result["warnings"]

    assert 75 < size_report["usage_percent"] < 90
    assert len(warnings) > 0
    assert "Warning:" in warnings[0]


@pytest.mark.asyncio
async def test_size_analysis_node_execute_critical_firmware():
    """SizeAnalysisNode génère un avertissement critique pour un firmware très large."""
    node = SizeAnalysisNode()
    firmware = {
        "size_bytes": 3800000,  # ~3.8MB, >90% of 4MB
        "target": "esp32",
        "framework": "esp-idf",
        "sections": {},
    }
    inputs = {"firmware": firmware}

    result = await node.execute(inputs)

    size_report = result["size_report"]
    warnings = result["warnings"]

    assert size_report["usage_percent"] > 90
    assert len(warnings) > 0
    assert "Critical:" in warnings[0]


@pytest.mark.asyncio
async def test_size_analysis_node_execute_with_section_warnings():
    """SizeAnalysisNode génère des avertissements pour les grandes sections."""
    node = SizeAnalysisNode()
    firmware = {
        "size_bytes": 2000000,
        "target": "esp32",
        "framework": "esp-idf",
        "sections": {
            "dram": 300000,  # >50% of 520KB RAM
            "flash_code": 1500000,  # >1MB
            "flash_rodata": 600000,  # >512KB
        },
    }
    inputs = {"firmware": firmware}

    result = await node.execute(inputs)

    warnings = result["warnings"]

    # Should have warnings about large sections
    assert any("code section" in w for w in warnings)
    assert any("rodata section" in w for w in warnings)
    assert any("RAM usage" in w for w in warnings)


@pytest.mark.asyncio
async def test_size_analysis_node_execute_esp32s3():
    """SizeAnalysisNode utilise les bonnes limites pour ESP32-S3."""
    node = SizeAnalysisNode()
    firmware = {
        "size_bytes": 5000000,  # 5MB
        "target": "esp32s3",
        "framework": "esp-idf",
        "sections": {},
    }
    inputs = {"firmware": firmware}

    result = await node.execute(inputs)

    size_report = result["size_report"]

    # ESP32-S3 has 8MB flash typically
    assert size_report["flash_size_bytes"] == 8 * 1024 * 1024
    assert size_report["usage_percent"] < 75  # 5MB/8MB ~= 62.5%


@pytest.mark.asyncio
async def test_size_analysis_node_execute_esp32c3():
    """SizeAnalysisNode utilise les bonnes limites pour ESP32-C3."""
    node = SizeAnalysisNode()
    firmware = {
        "size_bytes": 2000000,  # 2MB
        "target": "esp32c3",
        "framework": "esp-idf",
        "sections": {},
    }
    inputs = {"firmware": firmware}

    result = await node.execute(inputs)

    size_report = result["size_report"]

    # ESP32-C3 has 4MB flash typically
    assert size_report["flash_size_bytes"] == 4 * 1024 * 1024
    assert 40 < size_report["usage_percent"] < 60  # 2MB/4MB = 50%
