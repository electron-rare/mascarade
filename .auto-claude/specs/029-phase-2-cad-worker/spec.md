# Phase 2 — CAD Worker Specification

**Document:** SPEC-029-P2 — Universal Node Engine Phase 2 CAD Worker
**Date:** 2026-03-16
**Version:** 1.0
**Status:** Draft
**Parent:** SPEC-029 (Universal Node Engine Architecture)

---

## Table of Contents

1. [Overview](#1-overview)
2. [CAD Domain Port Types](#2-cad-domain-port-types)
3. [FreeCAD Nodes](#3-freecad-nodes)
4. [KiCad Nodes](#4-kicad-nodes)
5. [Toolpath Generation Nodes](#5-toolpath-generation-nodes)
6. [Mesh Operation Nodes](#6-mesh-operation-nodes)
7. [API Integration Surface](#7-api-integration-surface)
8. [Acceptance Criteria](#8-acceptance-criteria)

---

## 1. Overview

Phase 2 introduces the CAD Worker domain to the Universal Node Engine. This worker provides graph-composable nodes for 3D modeling (FreeCAD), electronics design (KiCad), toolpath generation, and mesh operations. It integrates with the existing `freecad_agent` and `kicad_agent` patterns in `core/mascarade/agents/` and exposes functionality through the `api/src/routes/cad.ts` API surface.

### 1.1 Goals

- Provide FreeCAD nodes for document creation, script execution, parametric modeling, and export
- Provide KiCad nodes for schematic generation, PCB layout optimization, footprint creation, DRC checking, and manufacturing file export
- Provide toolpath generation nodes for G-code and CNC optimization
- Provide mesh operation nodes for STL import/export, simplification, and boolean operations
- Define CAD-specific domain port types registered at worker initialization

### 1.2 Non-Goals

- Cross-domain type adapters (deferred to Phase 5)
- ReactFlow UI node components (separate UI spec)
- Distributed execution of CAD workloads via Ray (Phase 5)

### 1.3 Dependencies

- Phase 0 Foundations: `NodeWorker` interface, `NodeTypeRegistry`, `PortType`, `DomainType`
- Existing agent patterns: `core/mascarade/agents/freecad_agent.py`, `core/mascarade/agents/kicad_agent.py`
- Existing API routes: `api/src/routes/cad.ts` (FreeCAD and OpenSCAD endpoints)
- Python 3.11+ with Pydantic

---

## 2. CAD Domain Port Types

The CAD worker registers domain-specific port types during initialization. These types extend the Phase 0 `DomainType` mechanism and are validated via JSON Schema.

### 2.1 Type Definitions

| Type | Description | Schema Summary |
|------|-------------|----------------|
| `MeshData` | Triangulated 3D mesh (vertices, faces, normals) | `{vertices: array<array<number>>, faces: array<array<integer>>, normals?: array<array<number>>, format: string}` |
| `Toolpath` | Ordered sequence of machine tool movements | `{moves: array<{x, y, z, feed_rate, type}>, unit: "mm"\|"inch", tool_id: string}` |
| `BOM` | Bill of Materials — component list with quantities | `{items: array<{reference, value, footprint, quantity, supplier?}>, total_count: integer}` |
| `GCode` | G-code program as structured text with metadata | `{program: string, estimated_time_s: number, bounds: {x, y, z}, tool_changes: integer}` |
| `SchematicData` | KiCad schematic representation | `{symbols: array<{ref, value, lib, position}>, nets: array<{name, pins}>, power_flags: array<string>}` |
| `PCBLayout` | KiCad PCB layout with component placement and routing | `{components: array<{ref, footprint, position, rotation}>, traces: array<{net, layer, points, width}>, zones: array<{net, layer, outline}>, layers: array<string>}` |
| `CADDocument` | FreeCAD document reference with metadata | `{document_id: string, name: string, objects: array<{label, type, shape_type}>, parameters: map<string, number>}` |
| `ExportResult` | Result of a CAD export operation | `{format: string, file_path: string, file_size_bytes: integer, warnings: array<string>}` |

### 2.2 Python Registration

```python
"""CAD domain port types — registered by CADWorker during initialization."""

from core.node_engine.types import DomainType

CAD_DOMAIN_TYPES = [
    DomainType(
        domain="cad",
        name="MeshData",
        schema={
            "type": "object",
            "properties": {
                "vertices": {"type": "array", "items": {"type": "array", "items": {"type": "number"}, "minItems": 3, "maxItems": 3}},
                "faces": {"type": "array", "items": {"type": "array", "items": {"type": "integer"}, "minItems": 3}},
                "normals": {"type": "array", "items": {"type": "array", "items": {"type": "number"}, "minItems": 3, "maxItems": 3}},
                "format": {"type": "string", "enum": ["stl", "obj", "ply", "step"]},
            },
            "required": ["vertices", "faces", "format"],
        },
    ),
    DomainType(
        domain="cad",
        name="Toolpath",
        schema={
            "type": "object",
            "properties": {
                "moves": {"type": "array", "items": {"type": "object", "properties": {"x": {"type": "number"}, "y": {"type": "number"}, "z": {"type": "number"}, "feed_rate": {"type": "number"}, "type": {"type": "string", "enum": ["rapid", "linear", "arc_cw", "arc_ccw"]}}, "required": ["x", "y", "z", "type"]}},
                "unit": {"type": "string", "enum": ["mm", "inch"]},
                "tool_id": {"type": "string"},
            },
            "required": ["moves", "unit", "tool_id"],
        },
    ),
    DomainType(
        domain="cad",
        name="BOM",
        schema={
            "type": "object",
            "properties": {
                "items": {"type": "array", "items": {"type": "object", "properties": {"reference": {"type": "string"}, "value": {"type": "string"}, "footprint": {"type": "string"}, "quantity": {"type": "integer"}, "supplier": {"type": "string"}}, "required": ["reference", "value", "quantity"]}},
                "total_count": {"type": "integer"},
            },
            "required": ["items", "total_count"],
        },
    ),
    DomainType(
        domain="cad",
        name="GCode",
        schema={
            "type": "object",
            "properties": {
                "program": {"type": "string"},
                "estimated_time_s": {"type": "number"},
                "bounds": {"type": "object", "properties": {"x": {"type": "number"}, "y": {"type": "number"}, "z": {"type": "number"}}},
                "tool_changes": {"type": "integer"},
            },
            "required": ["program"],
        },
    ),
    DomainType(
        domain="cad",
        name="SchematicData",
        schema={
            "type": "object",
            "properties": {
                "symbols": {"type": "array", "items": {"type": "object", "properties": {"ref": {"type": "string"}, "value": {"type": "string"}, "lib": {"type": "string"}, "position": {"type": "object"}}, "required": ["ref", "value"]}},
                "nets": {"type": "array", "items": {"type": "object", "properties": {"name": {"type": "string"}, "pins": {"type": "array", "items": {"type": "string"}}}, "required": ["name", "pins"]}},
                "power_flags": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["symbols", "nets"],
        },
    ),
    DomainType(
        domain="cad",
        name="PCBLayout",
        schema={
            "type": "object",
            "properties": {
                "components": {"type": "array", "items": {"type": "object", "properties": {"ref": {"type": "string"}, "footprint": {"type": "string"}, "position": {"type": "object"}, "rotation": {"type": "number"}}, "required": ["ref", "footprint"]}},
                "traces": {"type": "array", "items": {"type": "object", "properties": {"net": {"type": "string"}, "layer": {"type": "string"}, "points": {"type": "array"}, "width": {"type": "number"}}, "required": ["net", "layer", "points", "width"]}},
                "zones": {"type": "array"},
                "layers": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["components", "traces", "layers"],
        },
    ),
]
```

---

## 3. FreeCAD Nodes

FreeCAD nodes wrap the existing `FreeCADAgent` capabilities and `api/src/routes/cad.ts` endpoints into composable graph nodes. Each node delegates to the FreeCAD runtime via the core Python service.

### 3.1 Node Catalog

#### 3.1.1 `cad.freecad.create_document`

Creates a new FreeCAD document with optional initial parameters.

| Property | Value |
|----------|-------|
| **ID** | `cad.freecad.create_document` |
| **Category** | CAD / FreeCAD |
| **Inputs** | `name: string`, `parameters: optional<map<string, number>>` |
| **Outputs** | `document: CADDocument` |
| **API Endpoint** | `POST /cad/freecad/documents` |
| **Error Modes** | FreeCAD runtime unavailable, invalid parameters |

**Behavior:** Sends a document creation request to the FreeCAD runtime. Returns a `CADDocument` with the document ID and metadata. Maps directly to `coreClient.freecadCreateDocument()`.

#### 3.1.2 `cad.freecad.run_script`

Executes a FreeCAD Python script within a document context. Integrates with the `FreeCADAgent.generate_freecad_script()` pattern for AI-assisted script generation.

| Property | Value |
|----------|-------|
| **ID** | `cad.freecad.run_script` |
| **Category** | CAD / FreeCAD |
| **Inputs** | `document: CADDocument`, `script: string`, `timeout_s: optional<number>` |
| **Outputs** | `document: CADDocument`, `result: json`, `logs: string` |
| **API Endpoint** | `POST /cad/freecad/script` |
| **Error Modes** | Script syntax error, execution timeout, FreeCAD crash |

**Behavior:** Executes the provided Python script within the FreeCAD runtime, scoped to the given document. Returns the updated document state, any script return value, and execution logs. Timeout defaults to 60 seconds.

#### 3.1.3 `cad.freecad.parametric_model`

Creates a parametric 3D model from a template and parameter values. This is a higher-level node that combines document creation and script execution.

| Property | Value |
|----------|-------|
| **ID** | `cad.freecad.parametric_model` |
| **Category** | CAD / FreeCAD |
| **Inputs** | `template: string`, `parameters: map<string, number>`, `description: optional<string>` |
| **Outputs** | `document: CADDocument`, `mesh: MeshData` |
| **Error Modes** | Invalid template, parameter out of range, tessellation failure |

**Behavior:** Loads the specified parametric template, applies parameter values, and generates both the FreeCAD document and a tessellated mesh output. When `description` is provided, delegates to `FreeCADAgent` for AI-assisted parameter inference.

#### 3.1.4 `cad.freecad.export`

Exports a FreeCAD document to a target format (STEP, STL, OBJ, IGES, etc.).

| Property | Value |
|----------|-------|
| **ID** | `cad.freecad.export` |
| **Category** | CAD / FreeCAD |
| **Inputs** | `document: CADDocument`, `format: string`, `options: optional<json>` |
| **Outputs** | `result: ExportResult`, `mesh: optional<MeshData>` |
| **API Endpoint** | `POST /cad/freecad/export` |
| **Error Modes** | Unsupported format, empty document, export failure |

**Behavior:** Exports the document via `coreClient.freecadExportDocument()`. For mesh formats (STL, OBJ), also returns the `MeshData` for downstream mesh operations. Supported formats: `step`, `stl`, `obj`, `iges`, `brep`, `dxf`.

### 3.2 FreeCAD Worker Configuration

```python
"""FreeCAD node worker — registers FreeCAD nodes with the Node Engine."""

from core.node_engine.worker import NodeWorker, WorkerCapabilities

class FreeCADWorker(NodeWorker):
    domain = "cad"
    name = "freecad"
    version = "1.0.0"

    capabilities = WorkerCapabilities(
        max_concurrent=2,  # FreeCAD runtime is memory-intensive
        timeout_default_s=120,
        requires_runtime=True,
        runtime_check_endpoint="/cad/freecad/runtime",
    )

    node_types = [
        "cad.freecad.create_document",
        "cad.freecad.run_script",
        "cad.freecad.parametric_model",
        "cad.freecad.export",
    ]
```

---

## 4. KiCad Nodes

KiCad nodes wrap the existing `KiCadAgent` capabilities into composable graph nodes for electronics design automation. Each node maps to one of the agent's core methods.

### 4.1 Node Catalog

#### 4.1.1 `cad.kicad.generate_schematic`

Generates a KiCad schematic from requirements. Wraps `KiCadAgent.generate_schematic()`.

| Property | Value |
|----------|-------|
| **ID** | `cad.kicad.generate_schematic` |
| **Category** | CAD / KiCad |
| **Inputs** | `requirements: string`, `library: optional<string>` |
| **Outputs** | `schematic: SchematicData`, `bom: BOM` |
| **Error Modes** | Invalid requirements, missing symbols, library not found |

**Behavior:** Uses the KiCad agent to generate a complete schematic with symbol placement, net labeling, power flags, and design rules. Extracts a preliminary BOM from the schematic symbols.

#### 4.1.2 `cad.kicad.optimize_layout`

Optimizes PCB component placement and trace routing. Wraps `KiCadAgent.optimize_layout()`.

| Property | Value |
|----------|-------|
| **ID** | `cad.kicad.optimize_layout` |
| **Category** | CAD / KiCad |
| **Inputs** | `schematic: SchematicData`, `constraints: json`, `board_outline: optional<MeshData>` |
| **Outputs** | `layout: PCBLayout`, `report: string` |
| **Error Modes** | Unroutable netlist, constraint violation, board area exceeded |

**Behavior:** Takes a schematic and design constraints (clearances, trace widths, layer count, board dimensions) and produces an optimized PCB layout. The report includes placement strategy, routing metrics, signal integrity notes, and thermal considerations.

#### 4.1.3 `cad.kicad.create_footprint`

Creates a KiCad footprint for a component. Wraps `KiCadAgent.generate_footprint()`.

| Property | Value |
|----------|-------|
| **ID** | `cad.kicad.create_footprint` |
| **Category** | CAD / KiCad |
| **Inputs** | `component_description: string`, `datasheet_url: optional<string>` |
| **Outputs** | `footprint: json`, `preview_mesh: optional<MeshData>` |
| **Error Modes** | Ambiguous description, invalid pad dimensions |

**Behavior:** Generates a KiCad footprint with pad layout, silkscreen markings, courtyard definition, and 3D model reference. Optionally generates a preview mesh for visualization.

#### 4.1.4 `cad.kicad.check_drc`

Performs Design Rule Check on a PCB layout. Wraps `KiCadAgent.perform_drc()`.

| Property | Value |
|----------|-------|
| **ID** | `cad.kicad.check_drc` |
| **Category** | CAD / KiCad |
| **Inputs** | `layout: PCBLayout`, `rules: json` |
| **Outputs** | `passed: boolean`, `violations: array<json>`, `report: string` |
| **Error Modes** | Invalid layout data, malformed rules |

**Behavior:** Checks the layout against design rules including clearance violations, trace width compliance, via specifications, silkscreen issues, and manufacturing constraints. Returns a structured list of violations and a human-readable report.

#### 4.1.5 `cad.kicad.export_manufacturing`

Generates manufacturing files from a PCB layout. Wraps `KiCadAgent.generate_manufacturing_files()`.

| Property | Value |
|----------|-------|
| **ID** | `cad.kicad.export_manufacturing` |
| **Category** | CAD / KiCad |
| **Inputs** | `layout: PCBLayout`, `bom: optional<BOM>`, `format: optional<string>` |
| **Outputs** | `gerbers: json`, `drill_files: json`, `bom: BOM`, `pick_and_place: json`, `report: string` |
| **Error Modes** | Incomplete layout, missing netlists, DRC not passed |

**Behavior:** Generates the complete set of manufacturing outputs: Gerber files (F.Cu, B.Cu, F.SilkS, B.SilkS, F.Mask, B.Mask, Edge.Cuts), drill files, BOM, and pick-and-place data. Warns if DRC has not been run.

### 4.2 KiCad Worker Configuration

```python
"""KiCad node worker — registers KiCad nodes with the Node Engine."""

from core.node_engine.worker import NodeWorker, WorkerCapabilities

class KiCadWorker(NodeWorker):
    domain = "cad"
    name = "kicad"
    version = "1.0.0"

    capabilities = WorkerCapabilities(
        max_concurrent=4,
        timeout_default_s=90,
        requires_runtime=False,  # KiCad nodes are agent-driven, no runtime daemon
    )

    node_types = [
        "cad.kicad.generate_schematic",
        "cad.kicad.optimize_layout",
        "cad.kicad.create_footprint",
        "cad.kicad.check_drc",
        "cad.kicad.export_manufacturing",
    ]
```

---

## 5. Toolpath Generation Nodes

Toolpath nodes convert 3D geometry into machine-executable instructions for CNC mills, lathes, and 3D printers.

### 5.1 Node Catalog

#### 5.1.1 `cad.toolpath.generate_gcode`

Generates G-code from mesh geometry and machining parameters.

| Property | Value |
|----------|-------|
| **ID** | `cad.toolpath.generate_gcode` |
| **Category** | CAD / Toolpath |
| **Inputs** | `mesh: MeshData`, `tool: json`, `strategy: string`, `stock: optional<json>` |
| **Outputs** | `gcode: GCode`, `toolpath: Toolpath` |
| **Error Modes** | Unsupported geometry, tool collision, invalid strategy |

**Behavior:** Generates G-code using the specified machining strategy (`adaptive`, `contour`, `pocket`, `drill`, `facing`). The `tool` input specifies tool geometry (diameter, flute count, material). The `stock` input defines raw material dimensions. Returns both the G-code program and the structured toolpath for visualization.

#### 5.1.2 `cad.toolpath.optimize`

Optimizes an existing toolpath for reduced machining time or improved surface finish.

| Property | Value |
|----------|-------|
| **ID** | `cad.toolpath.optimize` |
| **Category** | CAD / Toolpath |
| **Inputs** | `toolpath: Toolpath`, `objective: string`, `constraints: optional<json>` |
| **Outputs** | `toolpath: Toolpath`, `gcode: GCode`, `improvement_pct: number` |
| **Error Modes** | Infeasible constraints, optimization timeout |

**Behavior:** Optimizes the toolpath for the given objective (`time`, `finish`, `tool_life`). Applies feed rate optimization, rapid move consolidation, and path reordering. Reports the percentage improvement over the input toolpath.

---

## 6. Mesh Operation Nodes

Mesh nodes provide low-level geometry operations that serve as building blocks for CAD pipelines.

### 6.1 Node Catalog

#### 6.1.1 `cad.mesh.import`

Imports a mesh from file data (STL, OBJ, PLY).

| Property | Value |
|----------|-------|
| **ID** | `cad.mesh.import` |
| **Category** | CAD / Mesh |
| **Inputs** | `data: binary`, `format: string` |
| **Outputs** | `mesh: MeshData`, `stats: json` |
| **Error Modes** | Corrupt file, unsupported format, non-manifold geometry |

**Behavior:** Parses the binary input as the specified mesh format. Returns the mesh and statistics (vertex count, face count, bounding box, volume, surface area, manifold status).

#### 6.1.2 `cad.mesh.export`

Exports a mesh to a target format.

| Property | Value |
|----------|-------|
| **ID** | `cad.mesh.export` |
| **Category** | CAD / Mesh |
| **Inputs** | `mesh: MeshData`, `format: string`, `options: optional<json>` |
| **Outputs** | `data: binary`, `result: ExportResult` |
| **Error Modes** | Invalid mesh, unsupported format |

**Behavior:** Serializes the mesh to the target format (`stl`, `obj`, `ply`, `3mf`). Options include binary/ASCII mode and precision settings.

#### 6.1.3 `cad.mesh.simplify`

Reduces mesh complexity while preserving shape fidelity.

| Property | Value |
|----------|-------|
| **ID** | `cad.mesh.simplify` |
| **Category** | CAD / Mesh |
| **Inputs** | `mesh: MeshData`, `target_ratio: number`, `preserve_boundaries: optional<boolean>` |
| **Outputs** | `mesh: MeshData`, `reduction_pct: number` |
| **Error Modes** | Target ratio too aggressive, degenerate triangles |

**Behavior:** Applies quadric edge collapse decimation to reduce face count to `target_ratio` (0.0–1.0) of the original. Optionally preserves boundary edges for watertight models.

#### 6.1.4 `cad.mesh.boolean`

Performs boolean operations (union, intersection, difference) on two meshes.

| Property | Value |
|----------|-------|
| **ID** | `cad.mesh.boolean` |
| **Category** | CAD / Mesh |
| **Inputs** | `mesh_a: MeshData`, `mesh_b: MeshData`, `operation: string` |
| **Outputs** | `mesh: MeshData` |
| **Error Modes** | Non-manifold input, degenerate result, operation failure |

**Behavior:** Performs the specified boolean operation (`union`, `intersection`, `difference`) on two manifold meshes. Both inputs must be closed (watertight) meshes.

---

## 7. API Integration Surface

The CAD Worker integrates with the existing `api/src/routes/cad.ts` Hono routes. Node execution is proxied through the TypeScript API layer to the Python core service.

### 7.1 Endpoint Mapping

| Node | HTTP Method | API Route | Core Client Method |
|------|------------|-----------|-------------------|
| `cad.freecad.create_document` | POST | `/cad/freecad/documents` | `coreClient.freecadCreateDocument()` |
| `cad.freecad.run_script` | POST | `/cad/freecad/script` | `coreClient.freecadRunScript()` |
| `cad.freecad.export` | POST | `/cad/freecad/export` | `coreClient.freecadExportDocument()` |
| `cad.freecad.parametric_model` | POST | `/cad/freecad/script` | Composed: create + script |

FreeCAD runtime health is checked via `GET /cad/freecad/runtime` before node execution.

### 7.2 New Endpoints Required

The following endpoints must be added to `api/src/routes/cad.ts` for full Phase 2 coverage:

| Route | Purpose |
|-------|---------|
| `POST /cad/kicad/schematic` | Schematic generation |
| `POST /cad/kicad/layout` | PCB layout optimization |
| `POST /cad/kicad/footprint` | Footprint creation |
| `POST /cad/kicad/drc` | Design rule check |
| `POST /cad/kicad/manufacturing` | Manufacturing file export |
| `POST /cad/mesh/import` | Mesh import |
| `POST /cad/mesh/export` | Mesh export |
| `POST /cad/mesh/simplify` | Mesh simplification |
| `POST /cad/mesh/boolean` | Boolean operations |
| `POST /cad/toolpath/generate` | G-code generation |
| `POST /cad/toolpath/optimize` | Toolpath optimization |

---

## 8. Acceptance Criteria

### 8.1 Type System

- [ ] All 8 CAD domain types (`MeshData`, `Toolpath`, `BOM`, `GCode`, `SchematicData`, `PCBLayout`, `CADDocument`, `ExportResult`) are registered with the `NodeTypeRegistry`
- [ ] Domain types validate against their JSON Schema definitions
- [ ] CAD types appear in the node catalog type browser

### 8.2 FreeCAD Nodes

- [ ] `cad.freecad.create_document` creates a document via the existing API endpoint
- [ ] `cad.freecad.run_script` executes scripts with timeout enforcement
- [ ] `cad.freecad.parametric_model` combines creation and scripting
- [ ] `cad.freecad.export` supports STEP, STL, OBJ, IGES formats
- [ ] FreeCAD runtime health is verified before execution

### 8.3 KiCad Nodes

- [ ] `cad.kicad.generate_schematic` produces valid `SchematicData` output
- [ ] `cad.kicad.optimize_layout` accepts constraints and produces `PCBLayout`
- [ ] `cad.kicad.create_footprint` generates footprints with pad layout and courtyard
- [ ] `cad.kicad.check_drc` returns structured violation data
- [ ] `cad.kicad.export_manufacturing` produces Gerber, drill, BOM, and pick-and-place outputs

### 8.4 Toolpath & Mesh Nodes

- [ ] `cad.toolpath.generate_gcode` produces valid G-code from mesh input
- [ ] `cad.mesh.import` and `cad.mesh.export` round-trip STL data without loss
- [ ] `cad.mesh.simplify` reduces face count within specified ratio
- [ ] `cad.mesh.boolean` performs union, intersection, and difference operations

### 8.5 Integration

- [ ] All nodes are discoverable in the Node Registry under the `cad` domain
- [ ] Nodes compose in graphs (e.g., schematic → layout → DRC → manufacturing pipeline)
- [ ] API routes in `cad.ts` are extended for new endpoints
- [ ] Error handling follows Mascarade patterns (circuit breaker, retry, dead letter)
