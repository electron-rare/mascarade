# Phase 3 — Electronics Worker Specification

**Document:** SPEC-029-P3 — Universal Node Engine Phase 3 Electronics Worker
**Date:** 2026-03-16
**Version:** 1.0
**Status:** Draft
**Parent:** SPEC-029 (Universal Node Engine Architecture)

---

## Table of Contents

1. [Overview](#1-overview)
2. [Electronics Domain Port Types](#2-electronics-domain-port-types)
3. [SPICE Simulation Nodes](#3-spice-simulation-nodes)
4. [PCB Design Rule Checking Nodes](#4-pcb-design-rule-checking-nodes)
5. [Firmware Compilation Nodes](#5-firmware-compilation-nodes)
6. [Component Library Nodes](#6-component-library-nodes)
7. [Worker Registration & Lifecycle](#7-worker-registration--lifecycle)
8. [Acceptance Criteria](#8-acceptance-criteria)

---

## 1. Overview

Phase 3 introduces the Electronics Worker — a domain worker providing nodes for SPICE circuit simulation, PCB design rule checking, firmware compilation, and electronic component library management. It builds on the existing `spice_agent` and `components_agent` patterns in the Mascarade core, elevating their capabilities into composable, graph-connected nodes.

### 1.1 Goals

- Provide SPICE simulation nodes for netlist generation, transient/AC/DC analysis, and convergence debugging
- Provide PCB DRC nodes for rule definition, execution, and violation reporting
- Provide firmware compilation nodes for ESP-IDF and PlatformIO build targets
- Provide component library nodes for part lookup, datasheet retrieval, and BOM management
- Define electronics-specific port types: `Netlist`, `Schematic`, `Waveform`, `FirmwareBinary`, `ComponentSpec`

### 1.2 Non-Goals

- Physical PCB layout/routing (future extension)
- Hardware-in-the-loop testing (deferred to Phase 4 Hardware Runtime)
- FPGA synthesis workflows
- Cross-domain adapters (Phase 5)

### 1.3 Dependencies

- Phase 0 Foundations (core type system, graph runtime, NodeWorker interface, registry)
- Existing `SpiceAgent` (`core/mascarade/agents/spice_agent.py`) — patterns for ngspice integration
- Existing `ComponentsAgent` (`core/mascarade/agents/components_agent.py`) — patterns for JLCPCB/LCSC integration
- ngspice (recommended SPICE simulator — open-source, CLI-driven, well-supported)
- KiCad DRC engine (for PCB design rule checking)
- ESP-IDF / PlatformIO CLI toolchains (for firmware compilation)

---

## 2. Electronics Domain Port Types

The Electronics Worker registers the following domain-specific port types with the core type system at initialization. Each type is a `DomainType` with `domain: "electronics"`.

### 2.1 Type Definitions

| Type | Description | Schema Summary |
|------|-------------|----------------|
| `Netlist` | SPICE netlist text with metadata | `{ format: "spice"\|"kicad", content: string, components: array<string>, analyses: array<string> }` |
| `Schematic` | Circuit schematic representation | `{ format: "kicad"\|"svg"\|"json", content: string\|binary, sheets: array<string> }` |
| `Waveform` | Simulation result waveform data | `{ signals: map<string, array<number>>, time_axis: array<number>, units: map<string, string>, analysis_type: string }` |
| `FirmwareBinary` | Compiled firmware artifact | `{ binary: binary, target: string, framework: string, size_bytes: integer, sections: map<string, integer> }` |
| `ComponentSpec` | Electronic component specification | `{ mpn: string, manufacturer: string, category: string, parameters: map<string, any>, footprint: string, lcsc_part: optional<string>, datasheet_url: optional<string> }` |
| `BOMEntry` | Bill of Materials line item | `{ designator: string, component: ComponentSpec, quantity: integer, dnp: boolean }` |
| `DRCReport` | Design rule check results | `{ passed: boolean, violations: array<DRCViolation>, rules_checked: integer, board_file: string }` |
| `DRCViolation` | Single DRC violation | `{ rule: string, severity: "error"\|"warning"\|"info", location: { x: number, y: number, layer: string }, message: string }` |

### 2.2 Python Type Registration

```python
"""Electronics domain port types for the Universal Node Engine."""

from __future__ import annotations

from pydantic import BaseModel, Field
from typing import Any, Literal

from mascarade.node_engine.types import DomainType


# --- Domain type definitions ---

NETLIST_TYPE = DomainType(
    domain="electronics",
    name="Netlist",
    schema={
        "type": "object",
        "properties": {
            "format": {"type": "string", "enum": ["spice", "kicad"]},
            "content": {"type": "string"},
            "components": {"type": "array", "items": {"type": "string"}},
            "analyses": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["format", "content"],
    },
)

SCHEMATIC_TYPE = DomainType(
    domain="electronics",
    name="Schematic",
    schema={
        "type": "object",
        "properties": {
            "format": {"type": "string", "enum": ["kicad", "svg", "json"]},
            "content": {"type": "string"},
            "sheets": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["format", "content"],
    },
)

WAVEFORM_TYPE = DomainType(
    domain="electronics",
    name="Waveform",
    schema={
        "type": "object",
        "properties": {
            "signals": {"type": "object", "additionalProperties": {"type": "array", "items": {"type": "number"}}},
            "time_axis": {"type": "array", "items": {"type": "number"}},
            "units": {"type": "object", "additionalProperties": {"type": "string"}},
            "analysis_type": {"type": "string", "enum": ["transient", "ac", "dc", "noise", "op"]},
        },
        "required": ["signals", "analysis_type"],
    },
)

FIRMWARE_BINARY_TYPE = DomainType(
    domain="electronics",
    name="FirmwareBinary",
    schema={
        "type": "object",
        "properties": {
            "binary": {"type": "string", "contentEncoding": "base64"},
            "target": {"type": "string"},
            "framework": {"type": "string", "enum": ["esp-idf", "platformio", "arduino"]},
            "size_bytes": {"type": "integer"},
            "sections": {"type": "object", "additionalProperties": {"type": "integer"}},
        },
        "required": ["binary", "target", "framework", "size_bytes"],
    },
)

COMPONENT_SPEC_TYPE = DomainType(
    domain="electronics",
    name="ComponentSpec",
    schema={
        "type": "object",
        "properties": {
            "mpn": {"type": "string"},
            "manufacturer": {"type": "string"},
            "category": {"type": "string"},
            "parameters": {"type": "object"},
            "footprint": {"type": "string"},
            "lcsc_part": {"type": ["string", "null"]},
            "datasheet_url": {"type": ["string", "null"]},
        },
        "required": ["mpn", "manufacturer", "category"],
    },
)

ELECTRONICS_DOMAIN_TYPES = [
    NETLIST_TYPE,
    SCHEMATIC_TYPE,
    WAVEFORM_TYPE,
    FIRMWARE_BINARY_TYPE,
    COMPONENT_SPEC_TYPE,
]
```

---

## 3. SPICE Simulation Nodes

SPICE simulation nodes wrap ngspice (the recommended open-source simulator, consistent with the existing `SpiceAgent` which targets ngspice/LTspice). All SPICE nodes operate on `Netlist` and `Waveform` port types.

### 3.1 Node: `electronics.spice.netlist_generator`

Generates a SPICE netlist from a high-level circuit description. Mirrors the `SpiceAgent.generate_netlist()` method, using LLM-assisted generation with validation.

| Port | Direction | Type | Description |
|------|-----------|------|-------------|
| `circuit_description` | input | `string` | Natural language or structured circuit description |
| `device_models` | input | `optional<string>` | Custom `.model` / `.subckt` definitions to include |
| `target_simulator` | input | `optional<string>` | Simulator target: `"ngspice"` (default), `"ltspice"` |
| `netlist` | output | `Netlist` | Generated SPICE netlist |

**Configuration:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `include_control_section` | `boolean` | `true` | Whether to include `.control` / `.endc` block |
| `default_analyses` | `array<string>` | `["op"]` | Default analysis types if none specified |

**Execution behavior:**
1. Parse circuit description for component references and topology
2. Generate netlist with proper device models, node numbering, and analysis directives
3. Validate netlist syntax before output (basic structural checks)
4. Output includes metadata: component list, analysis types, simulator target

### 3.2 Node: `electronics.spice.simulate`

Executes a SPICE simulation using ngspice in batch mode. This is the primary simulation execution node.

| Port | Direction | Type | Description |
|------|-----------|------|-------------|
| `netlist` | input | `Netlist` | SPICE netlist to simulate |
| `waveform` | output | `Waveform` | Simulation result waveforms |
| `raw_output` | output | `string` | Raw simulator stdout/stderr |
| `success` | output | `boolean` | Whether simulation completed without errors |

**Configuration:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `timeout_seconds` | `integer` | `120` | Maximum simulation time |
| `max_iterations` | `integer` | `10000` | Convergence iteration limit |
| `simulator_path` | `string` | `"ngspice"` | Path to ngspice binary |

**Execution behavior:**
1. Write netlist to temporary file
2. Invoke `ngspice -b -r <rawfile> <netlist>` in subprocess
3. Parse raw output file for waveform data
4. Extract signal names, time axis, and values into `Waveform` structure
5. Report convergence failures via `success` output port

**Error handling:**
- Convergence failure: set `success = false`, populate `raw_output` with error details
- Timeout: kill subprocess, report timeout in `raw_output`
- Missing simulator: fail with clear error message indicating ngspice installation required

### 3.3 Node: `electronics.spice.analyze`

Performs specific analysis on a netlist (transient, AC, DC sweep). Wraps the `SpiceAgent.analyze_circuit()` pattern with structured output.

| Port | Direction | Type | Description |
|------|-----------|------|-------------|
| `netlist` | input | `Netlist` | Circuit netlist |
| `analysis_type` | input | `string` | One of: `"transient"`, `"ac"`, `"dc"`, `"op"`, `"noise"` |
| `parameters` | input | `json` | Analysis-specific parameters (see below) |
| `waveform` | output | `Waveform` | Analysis results |

**Analysis parameters by type:**

- **Transient:** `{ step: "1u", stop: "10m", start: "0" }`
- **AC:** `{ variation: "dec", points: 100, fstart: "1", fstop: "1Meg" }`
- **DC:** `{ source: "V1", start: 0, stop: 5, step: 0.1 }`
- **OP:** `{}` (no additional parameters)
- **Noise:** `{ output: "out", source: "V1", variation: "dec", points: 100, fstart: "1", fstop: "1Meg" }`

### 3.4 Node: `electronics.spice.debug_convergence`

Diagnoses and attempts to fix SPICE convergence issues. Mirrors `SpiceAgent.debug_convergence()`.

| Port | Direction | Type | Description |
|------|-----------|------|-------------|
| `netlist` | input | `Netlist` | Problematic netlist |
| `error_message` | input | `string` | Convergence error from simulator |
| `fixed_netlist` | output | `Netlist` | Corrected netlist |
| `diagnosis` | output | `string` | Root cause analysis and applied fixes |

**Common convergence fixes applied:**
- Adding `RSHUNT` across floating nodes
- Adjusting `.options` (`RELTOL`, `ABSTOL`, `VNTOL`, `ITL1`, `ITL4`)
- Adding initial conditions (`.ic`)
- Reducing timestep for transient analysis
- Replacing problematic device models

---

## 4. PCB Design Rule Checking Nodes

PCB DRC nodes integrate with KiCad's DRC engine to validate PCB designs against manufacturing rules.

### 4.1 Node: `electronics.pcb.drc_check`

Executes design rule checking on a KiCad PCB file.

| Port | Direction | Type | Description |
|------|-----------|------|-------------|
| `board_file` | input | `binary` | KiCad `.kicad_pcb` file content |
| `rules` | input | `optional<json>` | Custom DRC rules (overrides board defaults) |
| `report` | output | `DRCReport` | DRC results with violations |

**Configuration:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `severity_threshold` | `string` | `"warning"` | Minimum severity to report: `"error"`, `"warning"`, `"info"` |
| `kicad_cli_path` | `string` | `"kicad-cli"` | Path to KiCad CLI |

**Execution behavior:**
1. Write board file to temp directory
2. Invoke `kicad-cli pcb drc --output <report.json> --format json <board.kicad_pcb>`
3. Parse JSON report into `DRCReport` structure
4. Filter violations by severity threshold

### 4.2 Node: `electronics.pcb.rule_definition`

Defines custom DRC rules for manufacturing constraints (e.g., JLCPCB capabilities).

| Port | Direction | Type | Description |
|------|-----------|------|-------------|
| `manufacturer_preset` | input | `optional<string>` | Preset: `"jlcpcb_standard"`, `"jlcpcb_advanced"`, `"oshpark"` |
| `custom_overrides` | input | `optional<json>` | Override specific rules |
| `rules` | output | `json` | Complete DRC rule set |

**Built-in manufacturer presets:**

```json
{
  "jlcpcb_standard": {
    "min_trace_width_mm": 0.127,
    "min_clearance_mm": 0.127,
    "min_drill_mm": 0.3,
    "min_annular_ring_mm": 0.13,
    "min_via_diameter_mm": 0.45,
    "min_silkscreen_width_mm": 0.15,
    "min_solder_mask_bridge_mm": 0.1,
    "max_board_size_mm": [400, 500],
    "layer_count": [1, 2, 4, 6]
  }
}
```

### 4.3 Node: `electronics.pcb.violation_reporter`

Formats DRC violations into human-readable or machine-parsable reports.

| Port | Direction | Type | Description |
|------|-----------|------|-------------|
| `report` | input | `DRCReport` | Raw DRC report |
| `format` | input | `optional<string>` | Output format: `"markdown"` (default), `"csv"`, `"json"` |
| `formatted_report` | output | `string` | Formatted violation report |
| `summary` | output | `json` | `{ total: int, errors: int, warnings: int, passed: bool }` |

---

## 5. Firmware Compilation Nodes

Firmware compilation nodes manage build pipelines for embedded targets, focusing on ESP32 (ESP-IDF) and PlatformIO-supported boards — consistent with the project's hardware focus.

### 5.1 Node: `electronics.firmware.compile`

Compiles firmware from source using ESP-IDF or PlatformIO.

| Port | Direction | Type | Description |
|------|-----------|------|-------------|
| `source_path` | input | `string` | Path to firmware project directory |
| `target` | input | `string` | Build target (e.g., `"esp32"`, `"esp32s3"`, `"esp32c3"`) |
| `framework` | input | `optional<string>` | `"esp-idf"` (default) or `"platformio"` |
| `build_flags` | input | `optional<array<string>>` | Additional build flags |
| `firmware` | output | `FirmwareBinary` | Compiled firmware binary |
| `build_log` | output | `string` | Full build output |
| `success` | output | `boolean` | Whether build succeeded |

**Configuration:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `timeout_seconds` | `integer` | `300` | Maximum build time |
| `idf_path` | `string` | `""` | ESP-IDF installation path (auto-detect if empty) |
| `clean_build` | `boolean` | `false` | Force clean build |

**Execution behavior (ESP-IDF):**
1. Source ESP-IDF environment (`export.sh`)
2. Set target via `idf.py set-target <target>`
3. Build via `idf.py build`
4. Extract binary from `build/` directory
5. Parse build output for size information (`.text`, `.data`, `.bss`, `.rodata`)

**Execution behavior (PlatformIO):**
1. Invoke `pio run -e <target>`
2. Extract binary from `.pio/build/<target>/`
3. Parse build output for size metrics

### 5.2 Node: `electronics.firmware.flash_prepare`

Prepares firmware for flashing — generates flash command, merges binaries, sets partition table.

| Port | Direction | Type | Description |
|------|-----------|------|-------------|
| `firmware` | input | `FirmwareBinary` | Compiled firmware |
| `flash_config` | input | `optional<json>` | Flash parameters (baud, port, partition table) |
| `flash_command` | output | `string` | Ready-to-execute flash command |
| `merged_binary` | output | `optional<binary>` | Merged binary for single-file flashing |

**Default flash configuration:**

```json
{
  "baud": 460800,
  "port": "/dev/ttyUSB0",
  "flash_mode": "dio",
  "flash_freq": "40m",
  "flash_size": "4MB"
}
```

### 5.3 Node: `electronics.firmware.size_analysis`

Analyzes firmware binary size breakdown for optimization.

| Port | Direction | Type | Description |
|------|-----------|------|-------------|
| `firmware` | input | `FirmwareBinary` | Compiled firmware |
| `size_report` | output | `json` | Section-by-section size analysis |
| `warnings` | output | `array<string>` | Size warnings (e.g., approaching flash limit) |

---

## 6. Component Library Nodes

Component library nodes provide part lookup, datasheet retrieval, and BOM management — extending the patterns established in `ComponentsAgent`.

### 6.1 Node: `electronics.components.lookup`

Searches for electronic components by parameters or part number.

| Port | Direction | Type | Description |
|------|-----------|------|-------------|
| `query` | input | `string` | Search query (part number, description, or parametric) |
| `filters` | input | `optional<json>` | Parametric filters: `{ category, package, min_stock, supplier }` |
| `results` | output | `array<ComponentSpec>` | Matching components |

**Configuration:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `sources` | `array<string>` | `["lcsc", "jlcpcb"]` | Component databases to search |
| `max_results` | `integer` | `20` | Maximum results to return |
| `prefer_basic_parts` | `boolean` | `true` | Prioritize JLCPCB basic parts library |

### 6.2 Node: `electronics.components.datasheet`

Retrieves and parses datasheet information for a component.

| Port | Direction | Type | Description |
|------|-----------|------|-------------|
| `component` | input | `ComponentSpec` | Component to look up |
| `datasheet_url` | output | `optional<string>` | URL to datasheet PDF |
| `key_parameters` | output | `json` | Extracted key parameters (voltage, current, temp range, etc.) |
| `pinout` | output | `optional<json>` | Pin definitions if available |

### 6.3 Node: `electronics.components.bom_generate`

Generates a manufacturing-ready BOM from a list of components. Mirrors `ComponentsAgent.generate_bom()`.

| Port | Direction | Type | Description |
|------|-----------|------|-------------|
| `entries` | input | `array<BOMEntry>` | Component entries with designators and quantities |
| `format` | input | `optional<string>` | `"jlcpcb"` (default), `"generic_csv"`, `"kicad"` |
| `bom_output` | output | `string` | Formatted BOM (CSV) |
| `cost_estimate` | output | `optional<json>` | Estimated cost breakdown |

**JLCPCB BOM format output:**
```
Comment,Designator,Footprint,LCSC Part Number
"100nF","C1,C2,C3","0402","C1525"
"10K","R1,R2","0402","C25744"
```

### 6.4 Node: `electronics.components.find_alternatives`

Finds alternative components with compatible specifications. Mirrors `ComponentsAgent.find_alternatives()`.

| Port | Direction | Type | Description |
|------|-----------|------|-------------|
| `component` | input | `ComponentSpec` | Original component |
| `criteria` | input | `optional<json>` | `{ pin_compatible: bool, same_footprint: bool, max_cost: number }` |
| `alternatives` | output | `array<ComponentSpec>` | Ranked alternative components |
| `comparison` | output | `json` | Parameter comparison table |

---

## 7. Worker Registration & Lifecycle

### 7.1 Worker Definition

```python
"""Electronics domain worker for the Universal Node Engine."""

from mascarade.node_engine.worker import NodeWorker, WorkerCapabilities


class ElectronicsWorker(NodeWorker):
    """Domain worker for electronics: SPICE, PCB DRC, firmware, components."""

    domain = "electronics"
    version = "1.0.0"

    def capabilities(self) -> WorkerCapabilities:
        return WorkerCapabilities(
            node_prefixes=["electronics.spice", "electronics.pcb",
                           "electronics.firmware", "electronics.components"],
            max_concurrent=4,
            requires_gpu=False,
            estimated_memory_mb=512,
            external_tools=["ngspice", "kicad-cli", "idf.py", "pio"],
        )

    async def initialize(self) -> None:
        """Register electronics domain types and verify tool availability."""
        for domain_type in ELECTRONICS_DOMAIN_TYPES:
            await self.registry.register_type(domain_type)
        # Verify ngspice availability (warn if missing, don't fail)
        self._ngspice_available = await self._check_tool("ngspice")
        self._kicad_available = await self._check_tool("kicad-cli")

    async def shutdown(self) -> None:
        """Clean up temp files and close connections."""
        pass
```

### 7.2 Tool Availability

The Electronics Worker degrades gracefully when external tools are unavailable:

| Tool | Required For | Behavior If Missing |
|------|-------------|-------------------|
| `ngspice` | SPICE simulation nodes | Nodes fail with descriptive error; netlist generation still works via LLM |
| `kicad-cli` | PCB DRC nodes | Nodes fail with installation instructions |
| `idf.py` (ESP-IDF) | ESP-IDF firmware compilation | Falls back to PlatformIO if available |
| `pio` (PlatformIO) | PlatformIO firmware compilation | Nodes fail with installation instructions |

### 7.3 Resource Constraints

Given the deployment target (4 vCPU, 6.8 GiB RAM):

- SPICE simulations: max 2 concurrent, 512 MiB memory limit per simulation
- Firmware builds: max 1 concurrent (build systems are memory-intensive)
- DRC checks: max 4 concurrent (lightweight)
- Component lookups: max 8 concurrent (network I/O bound)

---

## 8. Acceptance Criteria

### 8.1 SPICE Simulation

- [ ] `netlist_generator` produces valid ngspice-compatible netlists
- [ ] `simulate` executes ngspice in batch mode and parses `Waveform` output
- [ ] `analyze` supports all five analysis types (transient, AC, DC, OP, noise)
- [ ] `debug_convergence` produces corrected netlists with documented fixes
- [ ] Simulation timeout and convergence failure are handled gracefully

### 8.2 PCB Design Rule Checking

- [ ] `drc_check` invokes KiCad CLI and parses JSON DRC reports
- [ ] `rule_definition` provides JLCPCB manufacturing presets
- [ ] `violation_reporter` produces markdown and CSV formatted reports

### 8.3 Firmware Compilation

- [ ] `compile` builds ESP-IDF projects and produces `FirmwareBinary` output
- [ ] `compile` builds PlatformIO projects as an alternative framework
- [ ] `flash_prepare` generates correct esptool.py flash commands
- [ ] `size_analysis` reports section-level binary size breakdown

### 8.4 Component Library

- [ ] `lookup` searches LCSC/JLCPCB component databases
- [ ] `datasheet` retrieves datasheet URLs and extracts key parameters
- [ ] `bom_generate` outputs JLCPCB-compatible CSV BOM format
- [ ] `find_alternatives` ranks alternatives by compatibility criteria

### 8.5 Integration

- [ ] All electronics port types (`Netlist`, `Schematic`, `Waveform`, `FirmwareBinary`, `ComponentSpec`) are registered with the core type system
- [ ] Worker degrades gracefully when external tools are unavailable
- [ ] All nodes follow the `NodeWorker` interface from Phase 0
- [ ] Resource limits are enforced per deployment constraints

## SPEC-025 Compatibility

Electronics Worker nodes implement the `NodeWorker` interface from Phase 0. Legacy electronics plugins built against SPEC-025 can be adapted via the `Spec025Adapter` without code changes.
