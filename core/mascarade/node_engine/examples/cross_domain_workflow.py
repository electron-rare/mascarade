#!/usr/bin/env python3
"""Cross-Domain Workflow Example — AI-designed PCB → Electronics validation → Hardware deploy.

Demonstrates a workflow spanning 4 domains:
1. AI: Generate component specs from natural language
2. CAD: Calculate trace widths and generate BOM
3. Electronics: Validate with DRC rules and run SPICE simulation
4. Hardware: Prepare firmware for OTA deployment

This is an MVP Phase 5 template showing the cross-domain adapter pipeline.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from mascarade.node_engine.cross_domain.adapters import (
    AIToElectronicsAdapter,
    CADToElectronicsAdapter,
    ElectronicsToHardwareAdapter,
)
from mascarade.node_engine.cross_domain.register import AdapterRegistry, register_all_adapters
from mascarade.node_engine.workers.cad.worker import CADWorker
from mascarade.node_engine.workers.electronics.worker import ElectronicsWorker


async def main():
    print("=" * 70)
    print("Cross-Domain Workflow: AI → CAD → Electronics → Hardware")
    print("=" * 70)

    # Setup
    registry = AdapterRegistry()
    register_all_adapters(registry)
    cad = CADWorker()
    elec = ElectronicsWorker()
    elec.registry = None

    # ── Step 1: AI generates component specs (simulated) ──────────────
    print("\n[Step 1] AI → Electronics: Generate component specs")
    ai_to_elec = AIToElectronicsAdapter()

    # Simulate LLM output describing a circuit
    llm_response = {
        "content": """Design an ESP32 IoT sensor board with:
- ESP32-S3-WROOM-1 microcontroller
- BME280 temperature/humidity sensor (I2C)
- 3.3V LDO regulator (AMS1117-3.3)
- USB-C connector for power and programming
- 10k pull-up resistors on I2C lines
- 100nF decoupling capacitors

Component list:
{"components": [
  {"ref": "U1", "value": "ESP32-S3-WROOM-1", "package": "QFN-56"},
  {"ref": "U2", "value": "BME280", "package": "LGA-8"},
  {"ref": "U3", "value": "AMS1117-3.3", "package": "SOT-223"},
  {"ref": "R1", "value": "10k", "package": "0402"},
  {"ref": "R2", "value": "10k", "package": "0402"},
  {"ref": "C1", "value": "100nF", "package": "0402"},
  {"ref": "C2", "value": "100nF", "package": "0402"},
  {"ref": "C3", "value": "10uF", "package": "0805"},
  {"ref": "J1", "value": "USB-C", "package": "USB-C-16P"}
]}""",
        "model": "claude-3-5-sonnet",
        "provider": "claude",
    }

    # Find the right mapping
    mapping = next(m for m in ai_to_elec.supported_mappings() if "ComponentSpec" in m.target_type)
    component_spec = await ai_to_elec.convert(llm_response, mapping)
    print(f"  Components extracted: {len(component_spec.get('components', []))} parts")

    # ── Step 2: CAD calculations ──────────────────────────────────────
    print("\n[Step 2] CAD: Calculate trace widths + BOM")

    trace = await cad.execute("cad.trace-width", {
        "current": 0.5, "copper_oz": 1.0, "temp_rise": 10.0, "layer": "external"
    }, {})
    print(f"  Trace width for 0.5A: {trace['width_mm']:.3f}mm")

    bom = await cad.execute("cad.bom-generate", {
        "components": [
            {"ref": "U1", "value": "ESP32-S3", "footprint": "QFN-56", "qty": 1},
            {"ref": "U2", "value": "BME280", "footprint": "LGA-8", "qty": 1},
            {"ref": "U3", "value": "AMS1117-3.3", "footprint": "SOT-223", "qty": 1},
            {"ref": "R1", "value": "10k", "footprint": "0402", "qty": 2},
            {"ref": "C1", "value": "100nF", "footprint": "0402", "qty": 2},
            {"ref": "C3", "value": "10uF", "footprint": "0805", "qty": 1},
            {"ref": "J1", "value": "USB-C", "footprint": "USB-C-16P", "qty": 1},
        ]
    }, {})
    print(f"  BOM: {bom['total_unique']} unique parts, {bom['total_qty']} total")

    stackup = await cad.execute("cad.stackup-calc", {"layers": 4, "thickness_mm": 1.6}, {})
    print(f"  Stackup: {stackup['layers']} layers, {stackup['total_thickness']}mm")

    # ── Step 3: Electronics validation ────────────────────────────────
    print("\n[Step 3] Electronics: DRC check + component search")

    drc = await cad.execute("cad.drc-check", {
        "rules": {"min_trace_mm": 0.15, "min_clearance_mm": 0.15, "min_via_mm": 0.3},
        "design": {"trace_mm": trace["width_mm"], "clearance_mm": 0.2, "via_mm": 0.4},
    }, {})
    print(f"  DRC: {'PASS' if drc['passed'] else 'FAIL'} ({len(drc['violations'])} violations)")

    # Component parametric search
    await elec.initialize()
    search = await elec.execute("electronics.component.parametric_search", {
        "category": "resistor", "filters": {"value": "10k", "package": "0402"}
    }, {}, None)
    print(f"  Resistor search: {search['count']} matches")

    # SPICE analysis
    netlist = """ESP32 Power Supply
V1 vin 0 5
U3 vin vout 0 AMS1117
R_load vout 0 100
C1 vout 0 100n
C3 vin 0 10u
.model AMS1117 NMOS
.op
.end"""

    analysis = await elec.execute("electronics.spice.analyze", {
        "netlist_content": netlist
    }, {}, None)
    print(f"  SPICE analysis: {analysis['characteristics']['component_count']} components, "
          f"{len(analysis['recommendations'])} recommendations")

    # ── Step 4: Hardware preparation ──────────────────────────────────
    print("\n[Step 4] Electronics → Hardware: Prepare deployment")

    elec_to_hw = ElectronicsToHardwareAdapter()

    mock_firmware = {
        "format": "esp-idf",
        "binary": b"\x00" * 1024,  # Mock firmware binary
        "target": "esp32s3",
        "size_bytes": 256000,
        "version": "1.0.0",
    }

    mapping_fw = next(m for m in elec_to_hw.supported_mappings() if "OTA" in m.target_type)
    ota_payload = await elec_to_hw.convert(mock_firmware, mapping_fw)
    print(f"  OTA payload prepared: {ota_payload.get('target', 'unknown')} v{ota_payload.get('version', '?')}")
    print(f"  Integrity: SHA-256 {ota_payload.get('sha256', 'N/A')[:16]}...")

    # ── Summary ───────────────────────────────────────────────────────
    print("\n" + "=" * 70)
    print("Cross-Domain Workflow COMPLETE")
    print("=" * 70)
    print(f"  Domains traversed: AI → CAD → Electronics → Hardware")
    print(f"  Adapters used: 3 (AI→Elec, CAD→Elec, Elec→HW)")
    print(f"  Components: {bom['total_qty']} parts on {stackup['layers']}-layer PCB")
    print(f"  DRC: {'PASS' if drc['passed'] else 'FAIL'}")
    print(f"  Trace width: {trace['width_mm']:.3f}mm for 0.5A")
    print(f"  Firmware: ready for OTA deploy to {mock_firmware['target']}")


if __name__ == "__main__":
    asyncio.run(main())
