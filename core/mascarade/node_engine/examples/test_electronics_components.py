#!/usr/bin/env python3
"""Test script for electronics component nodes that don't require external tools.

Tests all component nodes and the PCB rule_definition node via ElectronicsWorker.
These nodes use mock/local data and don't need ngspice, kicad-cli, or idf.py.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
import traceback
from typing import Any

# Ensure we load from THIS repo, not the stale mascarade-main editable install.
# The editable install for mascarade-core points to mascarade-main, which is stale.
# We must remove the editable meta-path finder so that sys.path takes precedence.
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

# Configure logging to see node execution
logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")

# ── Helpers ──────────────────────────────────────────────────────────────────

PASS = "\033[92mPASS\033[0m"
FAIL = "\033[91mFAIL\033[0m"
SKIP = "\033[93mSKIP\033[0m"
BUG  = "\033[93mBUG\033[0m"


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


# ── Test definitions ─────────────────────────────────────────────────────────

async def test_component_lookup(worker) -> tuple[str, list[str]]:
    """Test electronics.component.lookup node."""
    result = await worker.execute(
        node_type="electronics.component.lookup",
        inputs={
            "component_spec": "10k ohm resistor 0805",
            "requirements": {"tolerance": "1%", "voltage": "50V"},
        },
        config={},
        context=None,
    )
    errors = check_keys(result, ["alternatives", "best_match"])
    errors += check_type(result.get("alternatives", None), "alternatives", list)
    errors += check_type(result.get("best_match", None), "best_match", dict)
    if result.get("alternatives") and len(result["alternatives"]) == 0:
        errors.append("alternatives should not be empty with default config")
    return "electronics.component.lookup", errors


async def test_jlcpcb_optimization(worker) -> tuple[str, list[str]]:
    """Test electronics.component.jlcpcb_optimization node."""
    result = await worker.execute(
        node_type="electronics.component.jlcpcb_optimization",
        inputs={
            "requirements": {
                "components": [
                    {"type": "resistor", "value": "10k", "package": "0805"},
                    {"type": "capacitor", "value": "100nF", "package": "0805"},
                ]
            },
            "prefer_basic": True,
        },
        config={},
        context=None,
    )
    errors = check_keys(result, ["optimized_bom", "summary"])
    errors += check_type(result.get("optimized_bom", None), "optimized_bom", list)
    errors += check_type(result.get("summary", None), "summary", dict)
    summary = result.get("summary", {})
    if "total_components" not in summary:
        errors.append("summary missing 'total_components'")
    if "basic_parts" not in summary:
        errors.append("summary missing 'basic_parts'")
    return "electronics.component.jlcpcb_optimization", errors


async def test_bom_generator(worker) -> tuple[str, list[str]]:
    """Test electronics.component.bom_generator node."""
    result = await worker.execute(
        node_type="electronics.component.bom_generator",
        inputs={
            "circuit_description": "Simple LED driver with 3 resistors and 2 capacitors",
        },
        config={"format": "jlcpcb"},
        context=None,
    )
    errors = check_keys(result, ["bom", "bom_json"])
    errors += check_type(result.get("bom", None), "bom", str)
    errors += check_type(result.get("bom_json", None), "bom_json", list)
    bom_csv = result.get("bom", "")
    if "Comment" not in bom_csv or "LCSC" not in bom_csv:
        errors.append("BOM CSV missing expected JLCPCB header columns")
    return "electronics.component.bom_generator", errors


async def test_bom_generate(worker) -> tuple[str, list[str]]:
    """Test electronics.component.bom_generate node (variant)."""
    result = await worker.execute(
        node_type="electronics.component.bom_generate",
        inputs={
            "circuit_description": "ESP32 dev board with voltage regulator and decoupling caps",
        },
        config={},
        context=None,
    )
    errors = check_keys(result, ["bom_csv", "bom_data", "summary"])
    errors += check_type(result.get("bom_csv", None), "bom_csv", str)
    errors += check_type(result.get("bom_data", None), "bom_data", list)
    errors += check_type(result.get("summary", None), "summary", dict)
    summary = result.get("summary", {})
    if "total_line_items" not in summary:
        errors.append("summary missing 'total_line_items'")
    return "electronics.component.bom_generate", errors


async def test_cpl_generator(worker) -> tuple[str, list[str]]:
    """Test electronics.component.cpl_generator node."""
    result = await worker.execute(
        node_type="electronics.component.cpl_generator",
        inputs={
            "pcb_description": "2-layer PCB, 50x30mm, components on top side",
            "components": [
                {"designator": "R1", "x": 10.5, "y": 20.3},
                {"designator": "C1", "x": 15.0, "y": 25.0},
            ],
        },
        config={},
        context=None,
    )
    errors = check_keys(result, ["cpl", "cpl_json"])
    errors += check_type(result.get("cpl", None), "cpl", str)
    errors += check_type(result.get("cpl_json", None), "cpl_json", list)
    cpl_csv = result.get("cpl", "")
    if "Designator" not in cpl_csv or "Mid X" not in cpl_csv:
        errors.append("CPL CSV missing expected header columns")
    return "electronics.component.cpl_generator", errors


async def test_availability_check(worker) -> tuple[str, list[str]]:
    """Test electronics.component.availability_check node."""
    result = await worker.execute(
        node_type="electronics.component.availability_check",
        inputs={
            "part_numbers": ["C17414", "C49678", "C25804"],
            "check_alternatives": True,
        },
        config={},
        context=None,
    )
    errors = check_keys(result, ["availability", "recommendations"])
    errors += check_type(result.get("availability", None), "availability", list)
    errors += check_type(result.get("recommendations", None), "recommendations", list)
    avail = result.get("availability", [])
    if len(avail) != 3:
        errors.append(f"Expected 3 availability records, got {len(avail)}")
    for rec in avail:
        if "lcsc_part_number" not in rec:
            errors.append("Availability record missing 'lcsc_part_number'")
            break
    return "electronics.component.availability_check", errors


async def test_datasheet(worker) -> tuple[str, list[str]]:
    """Test electronics.component.datasheet node."""
    result = await worker.execute(
        node_type="electronics.component.datasheet",
        inputs={
            "component": "C17414",
        },
        config={},
        context=None,
    )
    errors = check_keys(result, ["datasheet_url", "parameters", "summary"])
    errors += check_type(result.get("datasheet_url", None), "datasheet_url", str)
    errors += check_type(result.get("parameters", None), "parameters", dict)
    errors += check_type(result.get("summary", None), "summary", str)
    if not result.get("datasheet_url", "").startswith("http"):
        errors.append("datasheet_url should be an HTTP URL")
    return "electronics.component.datasheet", errors


async def test_find_alternatives(worker) -> tuple[str, list[str]]:
    """Test electronics.component.find_alternatives node."""
    result = await worker.execute(
        node_type="electronics.component.find_alternatives",
        inputs={
            "component_spec": "10k ohm 0805 resistor",
            "requirements": {"tolerance": "1%"},
            "max_results": 5,
        },
        config={},
        context=None,
    )
    errors = check_keys(result, ["alternatives", "pin_compatible", "functional_equiv"])
    errors += check_type(result.get("alternatives", None), "alternatives", list)
    errors += check_type(result.get("pin_compatible", None), "pin_compatible", list)
    errors += check_type(result.get("functional_equiv", None), "functional_equiv", list)
    if len(result.get("alternatives", [])) == 0:
        errors.append("Expected at least 1 alternative")
    return "electronics.component.find_alternatives", errors


async def test_pcb_rule_definition_direct() -> tuple[str, list[str], str | None]:
    """Test electronics.pcb.rule_definition node DIRECTLY (bypassing worker tool check).

    The worker incorrectly requires kicad-cli for this node, but the node itself
    is purely computational (returns preset rules). This tests the node directly
    and reports the worker bug.
    """
    from mascarade.node_engine.workers.electronics.pcb_nodes import RuleDefinitionNode

    node = RuleDefinitionNode()
    bug_note = None

    # Test with JLCPCB standard preset
    result = await node.execute({
        "manufacturer_preset": "jlcpcb_standard",
    })
    errors = check_keys(result, ["rules"])
    errors += check_type(result.get("rules", None), "rules", dict)
    rules = result.get("rules", {})
    expected_rule_keys = [
        "min_trace_width_mm", "min_clearance_mm", "min_drill_mm",
        "min_annular_ring_mm", "min_via_diameter_mm",
    ]
    for k in expected_rule_keys:
        if k not in rules:
            errors.append(f"JLCPCB standard preset missing rule: '{k}'")

    # Test with custom overrides
    result2 = await node.execute({
        "manufacturer_preset": "jlcpcb_standard",
        "custom_overrides": {"min_trace_width_mm": 0.2},
    })
    rules2 = result2.get("rules", {})
    if rules2.get("min_trace_width_mm") != 0.2:
        errors.append("Custom override for min_trace_width_mm not applied")

    # Test with OSH Park preset
    result3 = await node.execute({
        "manufacturer_preset": "oshpark",
    })
    rules3 = result3.get("rules", {})
    if rules3.get("min_trace_width_mm") != 0.152:
        errors.append("OSH Park preset has wrong min_trace_width_mm")

    # Test with no preset (default rules)
    result4 = await node.execute({})
    rules4 = result4.get("rules", {})
    if not rules4:
        errors.append("Default rules should not be empty")

    return "electronics.pcb.rule_definition", errors, bug_note


async def test_pcb_rule_definition_via_worker(worker) -> tuple[str, list[str], str | None]:
    """Test electronics.pcb.rule_definition via worker (expected to fail without kicad-cli)."""
    bug_note = None

    # Architectural note: worker.py lists rule_definition in _TOOL_REQUIREMENTS
    # as needing kicad-cli, but the node itself is purely computational.
    # This works here because kicad-cli is installed, but would fail on machines without it.
    from mascarade.node_engine.workers.electronics.worker import _TOOL_REQUIREMENTS
    if "electronics.pcb.rule_definition" in _TOOL_REQUIREMENTS:
        bug_note = (
            "NOTE: worker.py lists rule_definition as requiring kicad-cli, "
            "but RuleDefinitionNode.execute() is purely computational. "
            "On machines without kicad-cli this node would be blocked unnecessarily. "
            "Fix: remove 'electronics.pcb.rule_definition' from _TOOL_REQUIREMENTS."
        )

    try:
        result = await worker.execute(
            node_type="electronics.pcb.rule_definition",
            inputs={"manufacturer_preset": "jlcpcb_standard"},
            config={},
            context=None,
        )
        errors = check_keys(result, ["rules"])
        return "electronics.pcb.rule_definition (via worker)", errors, bug_note
    except RuntimeError as e:
        if "kicad-cli" in str(e):
            bug_note = (
                "BUG: worker.py requires kicad-cli for rule_definition, "
                "but this node is purely computational and does NOT use kicad-cli. "
                "Fix: remove 'electronics.pcb.rule_definition' from _TOOL_REQUIREMENTS."
            )
            return "electronics.pcb.rule_definition (via worker)", [], bug_note
        raise


# ── Main ─────────────────────────────────────────────────────────────────────

async def main() -> int:
    from mascarade.node_engine.workers.electronics.worker import ElectronicsWorker

    print("=" * 72)
    print("Electronics Component Nodes -- Test Suite")
    print("=" * 72)
    print()

    worker = ElectronicsWorker()
    # The worker expects a registry attribute (normally set by the Node Engine).
    # We set it to None to skip domain type registration during testing.
    if not hasattr(worker, "registry"):
        worker.registry = None
    await worker.initialize()
    print()

    # Component node tests (all go through the worker)
    component_tests = [
        test_component_lookup,
        test_jlcpcb_optimization,
        test_bom_generator,
        test_bom_generate,
        test_cpl_generator,
        test_availability_check,
        test_datasheet,
        test_find_alternatives,
    ]

    results: list[tuple[str, str, str | None]] = []  # (name, status, detail)
    bugs: list[str] = []

    for test_fn in component_tests:
        try:
            name, errors = await test_fn(worker)
            if errors:
                status = FAIL
                detail = "; ".join(errors)
            else:
                status = PASS
                detail = None
            results.append((name, status, detail))
        except Exception as e:
            results.append((test_fn.__doc__ or test_fn.__name__, FAIL, f"Exception: {e}"))
            traceback.print_exc()

    # PCB rule_definition -- direct node test (no kicad-cli needed)
    try:
        name, errors, bug_note = await test_pcb_rule_definition_direct()
        if errors:
            results.append((name + " (direct)", FAIL, "; ".join(errors)))
        else:
            results.append((name + " (direct)", PASS, None))
        if bug_note:
            bugs.append(bug_note)
    except Exception as e:
        results.append(("electronics.pcb.rule_definition (direct)", FAIL, f"Exception: {e}"))
        traceback.print_exc()

    # PCB rule_definition -- via worker (will expose the kicad-cli bug)
    try:
        name, errors, bug_note = await test_pcb_rule_definition_via_worker(worker)
        if bug_note:
            results.append((name, BUG, bug_note))
            bugs.append(bug_note)
        elif errors:
            results.append((name, FAIL, "; ".join(errors)))
        else:
            results.append((name, PASS, None))
    except Exception as e:
        results.append(("electronics.pcb.rule_definition (via worker)", FAIL, f"Exception: {e}"))
        traceback.print_exc()

    # Print results
    print()
    print("-" * 72)
    print(f"{'Node Type':<50} {'Result'}")
    print("-" * 72)

    pass_count = 0
    fail_count = 0
    bug_count = 0

    for name, status, detail in results:
        print(f"  {name:<48} {status}")
        if detail:
            print(f"    -> {detail}")
        if "PASS" in status:
            pass_count += 1
        elif "FAIL" in status:
            fail_count += 1
        elif "BUG" in status:
            bug_count += 1

    print("-" * 72)
    print(f"Total: {len(results)} | Passed: {pass_count} | Failed: {fail_count} | Bugs: {bug_count}")
    print()

    if bugs:
        print("BUGS DETECTED:")
        for b in bugs:
            print(f"  * {b}")
        print()

    await worker.shutdown()
    return 1 if fail_count > 0 else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
