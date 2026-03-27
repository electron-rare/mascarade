"""Hardware Worker mock test — test all 10 node types without physical hardware.

Validates graceful degradation: each handler should return a structured
response (with error info) rather than crashing when hardware is unavailable.

Run:
    cd /Users/cils/mascarade/core && PYTHONPATH=. python3.14 mascarade/node_engine/examples/test_hardware_mock.py
"""

from __future__ import annotations

import asyncio
import logging
import sys
import time

# Show warnings from the worker so we can see degradation in action
logging.basicConfig(
    level=logging.WARNING,
    format="  %(levelname)s %(name)s: %(message)s",
)

# ---------------------------------------------------------------------------
# Test definitions: (node_type, inputs, description)
# ---------------------------------------------------------------------------

TESTS: list[tuple[str, dict, str]] = [
    # ESP32 ---
    (
        "hardware.esp32.discover",
        {"subnet": "192.168.0", "range_start": 1, "range_end": 2, "timeout": 1.0},
        "ESP32 discovery (tiny range, no devices expected)",
    ),
    (
        "hardware.esp32.gpio_read",
        {"device_id": "mock-esp32", "pin": 2},
        "ESP32 GPIO read (device not registered)",
    ),
    (
        "hardware.esp32.gpio_write",
        {"device_id": "mock-esp32", "pin": 2, "value": 1},
        "ESP32 GPIO write (device not registered)",
    ),
    (
        "hardware.esp32.sensor_read",
        {"device_id": "mock-esp32"},
        "ESP32 sensor read (device not registered)",
    ),
    (
        "hardware.esp32.ota_update",
        {"device_id": "mock-esp32", "firmware_url": "http://example.com/fw.bin"},
        "ESP32 OTA update (device not registered)",
    ),
    # DMX ---
    (
        "hardware.dmx.universe_create",
        {"name": "test-universe", "driver": "enttec-usb-dmx-pro", "channels": 512},
        "DMX universe create (no bridge running)",
    ),
    (
        "hardware.dmx.fixture_set",
        {"universe_id": "test-universe", "channels": {1: 255, 2: 128}},
        "DMX fixture set (no bridge running)",
    ),
    (
        "hardware.dmx.scene_apply",
        {
            "universe_id": "test-universe",
            "fixtures": [{"start_channel": 1, "values": [255, 128, 64]}],
            "transition_ms": 500,
        },
        "DMX scene apply (no bridge running)",
    ),
    # Serial ---
    (
        "hardware.serial.send",
        {"port": "/dev/null", "data": "hello", "baudrate": 115200},
        "Serial send to /dev/null (no real serial port)",
    ),
    (
        "hardware.serial.receive",
        {"port": "/dev/null", "baudrate": 115200, "timeout": 1.0},
        "Serial receive from /dev/null (no real serial port)",
    ),
]


async def run_tests() -> bool:
    """Run all hardware mock tests and return True if all pass."""
    from mascarade.node_engine.workers.hardware.worker import HardwareWorker

    worker = HardwareWorker()
    passed = 0
    failed = 0
    total = len(TESTS)

    print(f"Hardware Worker Mock Tests — {total} node types")
    print("=" * 70)

    for node_type, inputs, description in TESTS:
        t0 = time.perf_counter()
        try:
            result = await worker.execute(node_type, inputs, {}, None)
            elapsed = time.perf_counter() - t0

            # Validate: result must be a dict
            assert isinstance(result, dict), f"Expected dict, got {type(result)}"

            # Check for expected graceful degradation keys
            has_error = (
                "error" in result
                or any("error" in str(v) for v in result.values() if isinstance(v, dict))
            )
            has_data = bool(result)

            status = "PASS"
            if has_error:
                status = "PASS (degraded)"
            passed += 1

            print(f"\n[{status}] {node_type}")
            print(f"  {description}")
            print(f"  Time: {elapsed:.3f}s")
            # Print result summary (truncated)
            result_str = str(result)
            if len(result_str) > 200:
                result_str = result_str[:200] + "..."
            print(f"  Result: {result_str}")

        except Exception as exc:
            elapsed = time.perf_counter() - t0
            failed += 1
            print(f"\n[FAIL] {node_type}")
            print(f"  {description}")
            print(f"  Time: {elapsed:.3f}s")
            print(f"  CRASHED: {type(exc).__name__}: {exc}")

    print()
    print("=" * 70)
    print(f"Results: {passed}/{total} passed, {failed} failed")

    if failed > 0:
        print("\nSome node types crashed instead of degrading gracefully.")
        print("These need to be fixed in worker.py.")
    else:
        print("\nAll node types degrade gracefully when hardware is unavailable.")

    # Also test validate() for completeness
    print()
    print("Validation tests:")
    print("-" * 40)
    validation_cases = [
        ("hardware.esp32.gpio_read", {}, "Missing device_id and pin"),
        ("hardware.esp32.gpio_write", {"device_id": "x"}, "Missing pin and value"),
        ("hardware.dmx.fixture_set", {}, "Missing universe_id and channels"),
        ("hardware.serial.send", {}, "Missing port and data"),
    ]
    for node_type, inputs, desc in validation_cases:
        errors = await worker.validate(node_type, inputs, {})
        print(f"  validate({node_type}): {errors} — {desc}")

    # Test capabilities
    caps = worker.capabilities()
    print(f"\nCapabilities: {len(caps)} node types declared")
    for cap in caps:
        print(f"  - {cap['node_type']}: {cap['description'][:60]}")

    return failed == 0


def main():
    ok = asyncio.run(run_tests())
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
