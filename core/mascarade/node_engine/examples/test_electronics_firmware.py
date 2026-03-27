#!/usr/bin/env python3
"""Test script for electronics firmware nodes (Phase 3).

Tests firmware.compile, firmware.size_analysis, and firmware.flash_prepare
via both direct node instantiation and ElectronicsWorker.execute().

Firmware nodes require either idf.py or pio (PlatformIO) to be available.
The compile node needs a real project directory; size_analysis and flash_prepare
work with mock firmware data structures.
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import os
import shutil
import sys
import tempfile
import traceback
from pathlib import Path
from typing import Any

# Ensure we load from THIS repo, not the stale mascarade-main editable install.
_CORE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.insert(0, _CORE_DIR)
# Remove stale editable finders that point to mascarade-main
sys.meta_path[:] = [
    f for f in sys.meta_path
    if not (hasattr(f, '__module__') and 'editable' in str(getattr(f, '__module__', '')))
    and not (hasattr(f, 'find_spec') and 'mascarade_core' in str(type(f).__module__ if hasattr(type(f), '__module__') else ''))
    and 'EditableFinder' not in type(f).__name__
]
# Also clear any cached mascarade modules
for key in list(sys.modules.keys()):
    if key.startswith("mascarade"):
        del sys.modules[key]

# Configure logging
logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")

# ── Helpers ──────────────────────────────────────────────────────────────────

PASS = "\033[92mPASS\033[0m"
FAIL = "\033[91mFAIL\033[0m"
SKIP = "\033[93mSKIP\033[0m"
INFO = "\033[94mINFO\033[0m"


def check_keys(result: dict[str, Any], expected_keys: list[str]) -> list[str]:
    """Verify expected keys exist in result dict. Returns list of errors."""
    errors = []
    for key in expected_keys:
        if key not in result:
            errors.append(f"Missing output key: '{key}'")
    return errors


def check_type(value: Any, name: str, expected_type: type) -> list[str]:
    """Verify value has expected type. Returns list of errors."""
    if not isinstance(value, expected_type):
        return [f"'{name}' should be {expected_type.__name__}, got {type(value).__name__}"]
    return []


def make_mock_firmware(
    size_bytes: int = 65536,
    target: str = "esp32",
    framework: str = "esp-idf",
    sections: dict[str, int] | None = None,
) -> dict[str, Any]:
    """Create a mock firmware binary structure for testing."""
    binary_data = os.urandom(size_bytes)
    return {
        "binary": base64.b64encode(binary_data).decode(),
        "target": target,
        "framework": framework,
        "size_bytes": size_bytes,
        "sections": sections or {
            "dram": 15360,
            "iram": 32768,
            "flash_code": 45056,
            "flash_rodata": 8192,
        },
    }


def create_pio_test_project(tmpdir: Path) -> Path:
    """Create a minimal PlatformIO project for compilation testing."""
    project_dir = tmpdir / "pio_test_project"
    project_dir.mkdir(parents=True, exist_ok=True)

    # platformio.ini
    (project_dir / "platformio.ini").write_text(
        "[env:esp32dev]\n"
        "platform = espressif32\n"
        "board = esp32dev\n"
        "framework = arduino\n"
        "monitor_speed = 115200\n"
    )

    # src/main.cpp
    src_dir = project_dir / "src"
    src_dir.mkdir(exist_ok=True)
    (src_dir / "main.cpp").write_text(
        '#include <Arduino.h>\n'
        '\n'
        'void setup() {\n'
        '    Serial.begin(115200);\n'
        '    Serial.println("Hello from test firmware");\n'
        '}\n'
        '\n'
        'void loop() {\n'
        '    delay(1000);\n'
        '}\n'
    )

    return project_dir


# ── Test: SizeAnalysisNode (direct) ─────────────────────────────────────────

async def test_size_analysis_direct() -> tuple[str, list[str]]:
    """Test firmware.size_analysis node directly with mock firmware."""
    from mascarade.node_engine.workers.electronics.firmware_nodes import SizeAnalysisNode

    node = SizeAnalysisNode()
    name = "firmware.size_analysis (direct)"

    # Test with normal-sized firmware (64KB for ESP32, ~1.5% of flash)
    firmware = make_mock_firmware(size_bytes=65536, target="esp32")
    result = await node.execute({"firmware": firmware})

    errors = check_keys(result, ["size_report", "warnings"])
    errors += check_type(result.get("size_report"), "size_report", dict)
    errors += check_type(result.get("warnings"), "warnings", list)

    report = result.get("size_report", {})
    if report.get("total_size_bytes") != 65536:
        errors.append(f"total_size_bytes should be 65536, got {report.get('total_size_bytes')}")
    if report.get("target") != "esp32":
        errors.append(f"target should be 'esp32', got {report.get('target')}")
    if "usage_percent" not in report:
        errors.append("size_report missing usage_percent")
    if "flash_size_bytes" not in report:
        errors.append("size_report missing flash_size_bytes")
    if report.get("sections") != firmware["sections"]:
        errors.append("sections not preserved in report")

    return name, errors


async def test_size_analysis_warnings_large() -> tuple[str, list[str]]:
    """Test firmware.size_analysis generates warnings for large firmware."""
    from mascarade.node_engine.workers.electronics.firmware_nodes import SizeAnalysisNode

    node = SizeAnalysisNode()
    name = "firmware.size_analysis (warnings - large)"

    # 3.8MB firmware on ESP32 (4MB flash) => ~95% usage => Critical warning
    firmware = make_mock_firmware(
        size_bytes=3_800_000,
        target="esp32",
        sections={
            "dram": 15360,
            "iram": 32768,
            "flash_code": 2_500_000,
            "flash_rodata": 600_000,
        },
    )
    result = await node.execute({"firmware": firmware})

    errors = []
    warnings = result.get("warnings", [])
    if not warnings:
        errors.append("Expected warnings for 95% flash usage, got none")
    else:
        has_critical = any("Critical" in w or ">90%" in w for w in warnings)
        if not has_critical:
            errors.append(f"Expected critical warning for >90% usage, got: {warnings}")

        # flash_code > 1MB should trigger a warning
        has_code_warn = any("code section" in w.lower() or "large code" in w.lower() for w in warnings)
        if not has_code_warn:
            errors.append("Expected warning for large code section (>1MB)")

        # flash_rodata > 512KB should trigger a warning
        has_rodata_warn = any("rodata" in w.lower() for w in warnings)
        if not has_rodata_warn:
            errors.append("Expected warning for large rodata section (>512KB)")

    return name, errors


async def test_size_analysis_warnings_esp32s3() -> tuple[str, list[str]]:
    """Test firmware.size_analysis with ESP32-S3 (8MB flash)."""
    from mascarade.node_engine.workers.electronics.firmware_nodes import SizeAnalysisNode

    node = SizeAnalysisNode()
    name = "firmware.size_analysis (ESP32-S3 8MB)"

    # 3.8MB on ESP32-S3 (8MB flash) => ~47.5% => only Info level
    firmware = make_mock_firmware(size_bytes=3_800_000, target="esp32s3")
    result = await node.execute({"firmware": firmware})

    errors = []
    report = result.get("size_report", {})
    if report.get("flash_size_bytes") != 8 * 1024 * 1024:
        errors.append(f"ESP32-S3 flash size should be 8MB, got {report.get('flash_size_bytes')}")

    usage = report.get("usage_percent", 0)
    if not (40 < usage < 55):
        errors.append(f"Expected ~47.5% usage for 3.8MB on 8MB flash, got {usage}%")

    return name, errors


async def test_size_analysis_high_ram() -> tuple[str, list[str]]:
    """Test firmware.size_analysis warns about high static RAM usage."""
    from mascarade.node_engine.workers.electronics.firmware_nodes import SizeAnalysisNode

    node = SizeAnalysisNode()
    name = "firmware.size_analysis (high RAM)"

    # High DRAM usage: 300KB out of ~520KB on ESP32 => ~57%
    firmware = make_mock_firmware(
        size_bytes=65536,
        target="esp32",
        sections={
            "dram": 300 * 1024,
            "iram": 32768,
            "flash_code": 45056,
            "flash_rodata": 8192,
        },
    )
    result = await node.execute({"firmware": firmware})

    errors = []
    warnings = result.get("warnings", [])
    has_ram_warn = any("ram" in w.lower() for w in warnings)
    if not has_ram_warn:
        errors.append("Expected RAM usage warning for 300KB DRAM on ESP32")

    return name, errors


async def test_size_analysis_missing_firmware() -> tuple[str, list[str]]:
    """Test firmware.size_analysis raises ValueError for missing firmware."""
    from mascarade.node_engine.workers.electronics.firmware_nodes import SizeAnalysisNode

    node = SizeAnalysisNode()
    name = "firmware.size_analysis (missing input)"

    errors = []
    try:
        await node.execute({})
        errors.append("Should have raised ValueError for missing firmware")
    except ValueError:
        pass  # expected
    except Exception as e:
        errors.append(f"Expected ValueError, got {type(e).__name__}: {e}")

    return name, errors


# ── Test: FlashPrepareNode (direct) ─────────────────────────────────────────

async def test_flash_prepare_direct() -> tuple[str, list[str]]:
    """Test firmware.flash_prepare node directly with mock firmware."""
    from mascarade.node_engine.workers.electronics.firmware_nodes import FlashPrepareNode

    node = FlashPrepareNode()
    name = "firmware.flash_prepare (direct)"

    firmware = make_mock_firmware(target="esp32")
    result = await node.execute({"firmware": firmware})

    errors = check_keys(result, ["flash_command", "merged_binary"])
    errors += check_type(result.get("flash_command"), "flash_command", str)

    flash_cmd = result.get("flash_command", "")
    if "esptool.py" not in flash_cmd:
        errors.append("flash_command should contain 'esptool.py'")
    if "--chip esp32" not in flash_cmd:
        errors.append("flash_command should contain '--chip esp32'")
    if "--port" not in flash_cmd:
        errors.append("flash_command should contain '--port'")
    if "--baud" not in flash_cmd:
        errors.append("flash_command should contain '--baud'")
    if "write_flash" not in flash_cmd:
        errors.append("flash_command should contain 'write_flash'")

    return name, errors


async def test_flash_prepare_custom_config() -> tuple[str, list[str]]:
    """Test firmware.flash_prepare with custom flash configuration."""
    from mascarade.node_engine.workers.electronics.firmware_nodes import FlashPrepareNode

    node = FlashPrepareNode()
    name = "firmware.flash_prepare (custom config)"

    firmware = make_mock_firmware(target="esp32s3")
    flash_config = {
        "baud": 921600,
        "port": "/dev/ttyACM0",
        "flash_mode": "qio",
        "flash_freq": "80m",
        "flash_size": "8MB",
    }
    result = await node.execute({"firmware": firmware, "flash_config": flash_config})

    errors = []
    flash_cmd = result.get("flash_command", "")

    if "--chip esp32s3" not in flash_cmd:
        errors.append("flash_command should use esp32s3 chip")
    if "/dev/ttyACM0" not in flash_cmd:
        errors.append("flash_command should use custom port /dev/ttyACM0")
    if "921600" not in flash_cmd:
        errors.append("flash_command should use custom baud 921600")
    if "qio" not in flash_cmd:
        errors.append("flash_command should use qio flash mode")
    if "80m" not in flash_cmd:
        errors.append("flash_command should use 80m flash freq")
    if "8MB" not in flash_cmd:
        errors.append("flash_command should use 8MB flash size")

    return name, errors


async def test_flash_prepare_missing_firmware() -> tuple[str, list[str]]:
    """Test firmware.flash_prepare raises ValueError for missing firmware."""
    from mascarade.node_engine.workers.electronics.firmware_nodes import FlashPrepareNode

    node = FlashPrepareNode()
    name = "firmware.flash_prepare (missing input)"

    errors = []
    try:
        await node.execute({})
        errors.append("Should have raised ValueError for missing firmware")
    except ValueError:
        pass  # expected
    except Exception as e:
        errors.append(f"Expected ValueError, got {type(e).__name__}: {e}")

    return name, errors


# ── Test: CompileNode (direct) ──────────────────────────────────────────────

async def test_compile_missing_source() -> tuple[str, list[str]]:
    """Test firmware.compile raises ValueError for missing source_path."""
    from mascarade.node_engine.workers.electronics.firmware_nodes import CompileNode

    node = CompileNode()
    name = "firmware.compile (missing source_path)"

    errors = []
    try:
        await node.execute({"target": "esp32"})
        errors.append("Should have raised ValueError for missing source_path")
    except ValueError as e:
        if "source_path" not in str(e):
            errors.append(f"Error message should mention source_path: {e}")
    except Exception as e:
        errors.append(f"Expected ValueError, got {type(e).__name__}: {e}")

    return name, errors


async def test_compile_missing_target() -> tuple[str, list[str]]:
    """Test firmware.compile raises ValueError for missing target."""
    from mascarade.node_engine.workers.electronics.firmware_nodes import CompileNode

    node = CompileNode()
    name = "firmware.compile (missing target)"

    errors = []
    try:
        await node.execute({"source_path": "/tmp/nonexistent"})
        errors.append("Should have raised ValueError for missing target")
    except ValueError as e:
        if "target" not in str(e):
            errors.append(f"Error message should mention target: {e}")
    except Exception as e:
        errors.append(f"Expected ValueError, got {type(e).__name__}: {e}")

    return name, errors


async def test_compile_nonexistent_path() -> tuple[str, list[str]]:
    """Test firmware.compile raises ValueError for nonexistent source path."""
    from mascarade.node_engine.workers.electronics.firmware_nodes import CompileNode

    node = CompileNode()
    name = "firmware.compile (nonexistent path)"

    errors = []
    try:
        await node.execute({
            "source_path": "/tmp/nonexistent_firmware_project_xyz",
            "target": "esp32",
        })
        errors.append("Should have raised ValueError for nonexistent path")
    except ValueError as e:
        if "not exist" not in str(e).lower() and "does not exist" not in str(e).lower():
            errors.append(f"Error message should mention path does not exist: {e}")
    except Exception as e:
        errors.append(f"Expected ValueError, got {type(e).__name__}: {e}")

    return name, errors


async def test_compile_invalid_framework() -> tuple[str, list[str]]:
    """Test firmware.compile raises ValueError for unsupported framework."""
    from mascarade.node_engine.workers.electronics.firmware_nodes import CompileNode

    node = CompileNode()
    name = "firmware.compile (invalid framework)"

    # Create a temporary directory to pass path validation
    with tempfile.TemporaryDirectory() as tmpdir:
        errors = []
        try:
            await node.execute({
                "source_path": tmpdir,
                "target": "esp32",
                "framework": "mbed",
            })
            errors.append("Should have raised ValueError for unsupported framework")
        except ValueError as e:
            if "unsupported" not in str(e).lower() and "framework" not in str(e).lower():
                errors.append(f"Error message should mention unsupported framework: {e}")
        except RuntimeError:
            pass  # Also acceptable (tool not found)
        except Exception as e:
            errors.append(f"Expected ValueError, got {type(e).__name__}: {e}")

    return name, errors


async def test_compile_platformio_real(pio_available: bool) -> tuple[str, list[str]]:
    """Test firmware.compile with PlatformIO on a real minimal project.

    This test actually invokes 'pio run' if PlatformIO is available.
    It may take 30-120 seconds on first run (downloads platform/toolchain).
    """
    name = "firmware.compile (PlatformIO real build)"

    if not pio_available:
        return name, ["SKIP: pio not available"]

    from mascarade.node_engine.workers.electronics.firmware_nodes import CompileNode

    node = CompileNode()
    errors = []

    with tempfile.TemporaryDirectory(prefix="mascarade_pio_test_") as tmpdir:
        project_dir = create_pio_test_project(Path(tmpdir))

        try:
            result = await node.execute({
                "source_path": str(project_dir),
                "target": "esp32dev",
                "framework": "platformio",
            })

            errors += check_keys(result, ["firmware", "build_log", "success"])

            if result.get("success"):
                fw = result.get("firmware")
                if fw is None:
                    errors.append("Build succeeded but firmware is None")
                else:
                    if fw.get("size_bytes", 0) == 0:
                        errors.append("Firmware size_bytes should be > 0")
                    if fw.get("framework") != "platformio":
                        errors.append(f"Framework should be 'platformio', got {fw.get('framework')}")
                    if fw.get("target") != "esp32dev":
                        errors.append(f"Target should be 'esp32dev', got {fw.get('target')}")
                    # Verify binary is valid base64
                    try:
                        binary = base64.b64decode(fw.get("binary", ""))
                        if len(binary) == 0:
                            errors.append("Decoded binary should not be empty")
                    except Exception as e:
                        errors.append(f"Invalid base64 binary: {e}")
            else:
                # Build failed -- check if it is an infrastructure issue
                build_log = result.get("build_log", "")
                if "Error" in build_log or "error" in build_log:
                    # This is expected if espressif32 platform is not installed
                    errors.append(
                        f"Build failed (may need 'pio pkg install -p espressif32'). "
                        f"Last 200 chars of log: ...{build_log[-200:]}"
                    )
                else:
                    errors.append("Build failed with no error in log")

        except RuntimeError as e:
            if "PlatformIO not" in str(e):
                errors.append(f"SKIP: {e}")
            else:
                errors.append(f"RuntimeError: {e}")
        except Exception as e:
            errors.append(f"Unexpected {type(e).__name__}: {e}")

    return name, errors


# ── Test: via ElectronicsWorker ─────────────────────────────────────────────

async def test_size_analysis_via_worker(worker) -> tuple[str, list[str]]:
    """Test firmware.size_analysis via ElectronicsWorker.execute()."""
    name = "firmware.size_analysis (via worker)"

    firmware = make_mock_firmware(size_bytes=131072, target="esp32c3")

    try:
        result = await worker.execute(
            node_type="electronics.firmware.size_analysis",
            inputs={"firmware": firmware},
            config={},
            context=None,
        )
        errors = check_keys(result, ["size_report", "warnings"])
        report = result.get("size_report", {})
        if report.get("target") != "esp32c3":
            errors.append(f"target should be 'esp32c3', got {report.get('target')}")
        if report.get("total_size_bytes") != 131072:
            errors.append(f"total_size_bytes should be 131072, got {report.get('total_size_bytes')}")
        return name, errors
    except RuntimeError as e:
        if "non disponible" in str(e).lower() or "not available" in str(e).lower():
            return name, [f"SKIP: Worker reports tool not available: {e}"]
        raise


async def test_flash_prepare_via_worker(worker) -> tuple[str, list[str]]:
    """Test firmware.flash_prepare via ElectronicsWorker.execute()."""
    name = "firmware.flash_prepare (via worker)"

    firmware = make_mock_firmware(target="esp32s3")

    try:
        result = await worker.execute(
            node_type="electronics.firmware.flash_prepare",
            inputs={"firmware": firmware},
            config={},
            context=None,
        )
        errors = check_keys(result, ["flash_command", "merged_binary"])
        flash_cmd = result.get("flash_command", "")
        if "esptool.py" not in flash_cmd:
            errors.append("flash_command should contain 'esptool.py'")
        if "esp32s3" not in flash_cmd:
            errors.append("flash_command should contain 'esp32s3'")
        return name, errors
    except RuntimeError as e:
        if "non disponible" in str(e).lower() or "not available" in str(e).lower():
            return name, [f"SKIP: Worker reports tool not available: {e}"]
        raise


# ── Test: Node port definitions ─────────────────────────────────────────────

async def test_node_ports() -> tuple[str, list[str]]:
    """Test that all firmware nodes define correct input/output ports."""
    from mascarade.node_engine.workers.electronics.firmware_nodes import (
        CompileNode, FlashPrepareNode, SizeAnalysisNode,
    )

    name = "firmware node port definitions"
    errors = []

    # CompileNode
    cn = CompileNode()
    input_names = {p.name for p in cn.input_ports}
    output_names = {p.name for p in cn.output_ports}
    for expected in ["source_path", "target"]:
        if expected not in input_names:
            errors.append(f"CompileNode missing input port: {expected}")
    for expected in ["firmware", "build_log", "success"]:
        if expected not in output_names:
            errors.append(f"CompileNode missing output port: {expected}")

    # FlashPrepareNode
    fp = FlashPrepareNode()
    input_names = {p.name for p in fp.input_ports}
    output_names = {p.name for p in fp.output_ports}
    if "firmware" not in input_names:
        errors.append("FlashPrepareNode missing input port: firmware")
    if "flash_command" not in output_names:
        errors.append("FlashPrepareNode missing output port: flash_command")

    # SizeAnalysisNode
    sa = SizeAnalysisNode()
    input_names = {p.name for p in sa.input_ports}
    output_names = {p.name for p in sa.output_ports}
    if "firmware" not in input_names:
        errors.append("SizeAnalysisNode missing input port: firmware")
    for expected in ["size_report", "warnings"]:
        if expected not in output_names:
            errors.append(f"SizeAnalysisNode missing output port: {expected}")

    return name, errors


# ── Test: _parse_size helpers ───────────────────────────────────────────────

async def test_parse_size_esp_idf() -> tuple[str, list[str]]:
    """Test CompileNode._parse_size_esp_idf with sample build output."""
    from mascarade.node_engine.workers.electronics.firmware_nodes import CompileNode

    node = CompileNode()
    name = "firmware.compile._parse_size_esp_idf"

    sample_log = """
Project build complete. To flash, run this command:
esptool.py -p (PORT) -b 460800 write_flash @flash_args
or run 'idf.py -p (PORT) flash'

Total sizes:
 Used static DRAM:   35284 bytes (  145452 remain, 19.5% used)
      .data size:    11500 bytes
      .bss  size:    23784 bytes
 Used static IRAM:   82963 bytes (   48109 remain, 63.3% used)
      .text size:    81935 bytes
   .vectors size:     1027 bytes
 Flash code:        652321 bytes
 Flash rodata:      218736 bytes
 Total image size:  965020 bytes (.bin may be padded larger)
"""

    sections = node._parse_size_esp_idf(sample_log)

    errors = []
    if sections.get("dram") != 35284:
        errors.append(f"dram should be 35284, got {sections.get('dram')}")
    if sections.get("iram") != 82963:
        errors.append(f"iram should be 82963, got {sections.get('iram')}")
    if sections.get("flash_code") != 652321:
        errors.append(f"flash_code should be 652321, got {sections.get('flash_code')}")
    if sections.get("flash_rodata") != 218736:
        errors.append(f"flash_rodata should be 218736, got {sections.get('flash_rodata')}")

    return name, errors


async def test_parse_size_platformio() -> tuple[str, list[str]]:
    """Test CompileNode._parse_size_platformio with sample build output."""
    from mascarade.node_engine.workers.electronics.firmware_nodes import CompileNode

    node = CompileNode()
    name = "firmware.compile._parse_size_platformio"

    sample_log = """
Linking .pio/build/esp32dev/firmware.elf
Retrieving maximum program size .pio/build/esp32dev/firmware.elf
Checking size .pio/build/esp32dev/firmware.elf
Advanced Memory Usage is available via "PlatformIO Home > Project Inspect"
RAM:   [=         ]  12.5% (used 40960 bytes from 327680 bytes)
Flash: [====      ]  38.2% (used 400384 bytes from 1048576 bytes)
Building .pio/build/esp32dev/firmware.bin
"""

    sections = node._parse_size_platformio(sample_log)

    errors = []
    if sections.get("ram") != 40960:
        errors.append(f"ram should be 40960, got {sections.get('ram')}")
    if sections.get("flash") != 400384:
        errors.append(f"flash should be 400384, got {sections.get('flash')}")

    return name, errors


# ── Main ─────────────────────────────────────────────────────────────────────

async def main() -> int:
    from mascarade.node_engine.workers.electronics.worker import ElectronicsWorker

    print("=" * 72)
    print("Electronics Firmware Nodes -- Test Suite (Phase 3)")
    print("=" * 72)
    print()

    # Check tool availability
    pio_available = shutil.which("pio") is not None
    idf_available = shutil.which("idf.py") is not None
    arm_gcc_available = shutil.which("arm-none-eabi-gcc") is not None

    print(f"  pio (PlatformIO):    {'FOUND (' + shutil.which('pio') + ')' if pio_available else 'NOT FOUND'}")
    print(f"  idf.py (ESP-IDF):    {'FOUND' if idf_available else 'NOT FOUND'}")
    print(f"  arm-none-eabi-gcc:   {'FOUND (' + shutil.which('arm-none-eabi-gcc') + ')' if arm_gcc_available else 'NOT FOUND'}")
    print()

    # Initialize worker
    worker = ElectronicsWorker()
    if not hasattr(worker, "registry"):
        worker.registry = None
    await worker.initialize()

    print(f"  Worker._platformio_available: {worker._platformio_available}")
    print(f"  Worker._espidf_available:     {worker._espidf_available}")
    print()

    results: list[tuple[str, str, str | None]] = []

    # ── Direct node tests (no external tools needed) ────────────────────────
    direct_tests = [
        test_node_ports,
        test_parse_size_esp_idf,
        test_parse_size_platformio,
        test_size_analysis_direct,
        test_size_analysis_warnings_large,
        test_size_analysis_warnings_esp32s3,
        test_size_analysis_high_ram,
        test_size_analysis_missing_firmware,
        test_flash_prepare_direct,
        test_flash_prepare_custom_config,
        test_flash_prepare_missing_firmware,
        test_compile_missing_source,
        test_compile_missing_target,
        test_compile_nonexistent_path,
        test_compile_invalid_framework,
    ]

    for test_fn in direct_tests:
        try:
            test_name, errors = await test_fn()
            if errors:
                skip_errors = [e for e in errors if e.startswith("SKIP:")]
                real_errors = [e for e in errors if not e.startswith("SKIP:")]
                if skip_errors and not real_errors:
                    results.append((test_name, SKIP, skip_errors[0]))
                else:
                    results.append((test_name, FAIL, "; ".join(errors)))
            else:
                results.append((test_name, PASS, None))
        except Exception as e:
            results.append((test_fn.__name__, FAIL, f"Exception: {e}"))
            traceback.print_exc()

    # ── PlatformIO real compilation test ────────────────────────────────────
    try:
        test_name, errors = await test_compile_platformio_real(pio_available)
        if errors:
            skip_errors = [e for e in errors if e.startswith("SKIP:")]
            real_errors = [e for e in errors if not e.startswith("SKIP:")]
            if skip_errors and not real_errors:
                results.append((test_name, SKIP, skip_errors[0]))
            else:
                results.append((test_name, FAIL, "; ".join(errors)))
        else:
            results.append((test_name, PASS, None))
    except Exception as e:
        results.append(("firmware.compile (PlatformIO real build)", FAIL, f"Exception: {e}"))
        traceback.print_exc()

    # ── Worker integration tests ────────────────────────────────────────────
    worker_tests = [
        test_size_analysis_via_worker,
        test_flash_prepare_via_worker,
    ]

    for test_fn in worker_tests:
        try:
            test_name, errors = await test_fn(worker)
            if errors:
                skip_errors = [e for e in errors if e.startswith("SKIP:")]
                real_errors = [e for e in errors if not e.startswith("SKIP:")]
                if skip_errors and not real_errors:
                    results.append((test_name, SKIP, skip_errors[0]))
                else:
                    results.append((test_name, FAIL, "; ".join(errors)))
            else:
                results.append((test_name, PASS, None))
        except Exception as e:
            results.append((test_fn.__name__, FAIL, f"Exception: {e}"))
            traceback.print_exc()

    # ── Print results ───────────────────────────────────────────────────────
    print()
    print("-" * 72)
    print(f"{'Test':<55} {'Result'}")
    print("-" * 72)

    pass_count = 0
    fail_count = 0
    skip_count = 0

    for test_name, status, detail in results:
        print(f"  {test_name:<53} {status}")
        if detail:
            # Truncate long detail lines
            if len(detail) > 120:
                print(f"    -> {detail[:120]}...")
            else:
                print(f"    -> {detail}")
        if "PASS" in status:
            pass_count += 1
        elif "FAIL" in status:
            fail_count += 1
        elif "SKIP" in status:
            skip_count += 1

    print("-" * 72)
    total = len(results)
    print(f"Total: {total} | Passed: {pass_count} | Failed: {fail_count} | Skipped: {skip_count}")
    print()

    await worker.shutdown()
    return 1 if fail_count > 0 else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
