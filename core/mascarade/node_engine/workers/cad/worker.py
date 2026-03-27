"""CAD domain worker for mascarade node engine.

Dispatches to sub-workers:
- Pure calculation nodes: trace width, stackup, thermal vias, BOM, DRC, footprint
- Mesh operations: STL/OBJ/PLY import/export, validation, stats, simplify, boolean
- Toolpath generation: G-code from mesh/path, optimization
- FreeCAD operations: document creation, scripting, parametric modeling (requires MCP)
- KiCad operations: schematic, layout, DRC, manufacturing files (requires MCP)
"""

from __future__ import annotations

import logging
import math
from typing import Any

from mascarade.node_engine.worker import NodeWorker

logger = logging.getLogger(__name__)

# IPC-2221 constants for trace width calculation
K_INTERNAL = 0.024  # Internal layers
K_EXTERNAL = 0.048  # External layers
COPPER_RESISTIVITY = 1.724e-6  # ohm-cm


class CADWorker(NodeWorker):
    """Worker for CAD domain — pure calculations + mesh + toolpath + MCP sub-workers.

    Dispatches node types to the appropriate handler:
    - cad.bom-generate, cad.drc-check, cad.footprint-lookup, cad.stackup-calc,
      cad.trace-width, cad.thermal-via: pure calculation (inline)
    - cad.mesh.*: delegated to MeshWorker
    - cad.toolpath.*: delegated to ToolpathWorker
    - cad.freecad.*: delegated to FreeCADWorker (requires MCP)
    - cad.kicad.*: delegated to KiCadWorker (requires MCP)
    """

    name: str = "cad-worker"
    domain: str = "cad"

    def __init__(self) -> None:
        from mascarade.node_engine.workers.cad.mesh_worker import MeshWorker
        from mascarade.node_engine.workers.cad.toolpath_worker import ToolpathWorker

        self._mesh_worker = MeshWorker()
        self._toolpath_worker = ToolpathWorker()
        # MCP sub-workers are lazy-initialized
        self._freecad_worker = None
        self._kicad_worker = None

    def capabilities(self) -> dict[str, Any]:
        # Collect all node types from sub-workers
        pure_node_types = [
            "cad.bom-generate",
            "cad.drc-check",
            "cad.footprint-lookup",
            "cad.stackup-calc",
            "cad.trace-width",
            "cad.thermal-via",
        ]
        all_node_types = (
            pure_node_types
            + self._mesh_worker.node_types
            + self._toolpath_worker.node_types
        )
        # Include MCP worker node types (they may not be available at runtime)
        from mascarade.node_engine.workers.cad.freecad_worker import FreeCADWorker
        from mascarade.node_engine.workers.cad.kicad_worker import KiCadWorker

        all_node_types += FreeCADWorker.node_types + KiCadWorker.node_types

        return {
            "node_types": all_node_types,
            "domain": "cad",
            "supports_streaming": False,
            "max_concurrent": 10,
        }

    async def execute(
        self,
        node_type: str,
        inputs: dict[str, Any],
        config: dict[str, Any],
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        # Pure calculation handlers
        pure_handlers = {
            "cad.bom-generate": self._bom_generate,
            "cad.drc-check": self._drc_check,
            "cad.footprint-lookup": self._footprint_lookup,
            "cad.stackup-calc": self._stackup_calc,
            "cad.trace-width": self._trace_width,
            "cad.thermal-via": self._thermal_via,
        }
        handler = pure_handlers.get(node_type)
        if handler:
            return handler(inputs)

        # Delegate to sub-workers
        if node_type.startswith("cad.mesh."):
            return await self._mesh_worker.execute(node_type, inputs)
        if node_type.startswith("cad.toolpath."):
            return await self._toolpath_worker.execute(node_type, inputs)
        if node_type.startswith("cad.freecad."):
            return await self._get_freecad_worker().execute(node_type, inputs)
        if node_type.startswith("cad.kicad."):
            return await self._get_kicad_worker().execute(node_type, inputs)

        raise ValueError(f"Unsupported CAD node type: {node_type}")

    def _get_freecad_worker(self):
        if self._freecad_worker is None:
            from mascarade.node_engine.workers.cad.freecad_worker import FreeCADWorker

            self._freecad_worker = FreeCADWorker()
        return self._freecad_worker

    def _get_kicad_worker(self):
        if self._kicad_worker is None:
            from mascarade.node_engine.workers.cad.kicad_worker import KiCadWorker

            self._kicad_worker = KiCadWorker()
        return self._kicad_worker

    async def validate(
        self, node_type: str, inputs: dict[str, Any], config: dict[str, Any]
    ) -> list[str]:
        errors: list[str] = []
        if node_type == "cad.bom-generate":
            if "components" not in inputs or not isinstance(
                inputs.get("components"), list
            ):
                errors.append("components (list) is required")
        elif node_type == "cad.trace-width":
            if "current" not in inputs or inputs.get("current", 0) <= 0:
                errors.append("current (positive float) is required")
        elif node_type == "cad.thermal-via":
            if "power" not in inputs or inputs.get("power", 0) <= 0:
                errors.append("power (positive float) is required")
        elif node_type == "cad.stackup-calc":
            layers = inputs.get("layers", 0)
            if layers < 2 or layers > 16 or layers % 2 != 0:
                errors.append("layers must be even number 2-16")
        elif node_type == "cad.footprint-lookup":
            if "package" not in inputs:
                errors.append("package is required")
        # Mesh and toolpath validations are handled at execution time
        return errors

    def _bom_generate(self, inputs: dict) -> dict:
        components = inputs.get("components", [])
        bom = {}
        for c in components:
            key = f"{c.get('value', '?')}_{c.get('footprint', '?')}"
            if key not in bom:
                bom[key] = {
                    "value": c.get("value", ""),
                    "footprint": c.get("footprint", ""),
                    "refs": [],
                    "qty": 0,
                }
            bom[key]["refs"].append(c.get("ref", "?"))
            bom[key]["qty"] += c.get("qty", 1)

        bom_list = sorted(bom.values(), key=lambda x: x["value"])
        return {
            "bom": bom_list,
            "total_unique": len(bom_list),
            "total_qty": sum(b["qty"] for b in bom_list),
        }

    def _drc_check(self, inputs: dict) -> dict:
        rules = inputs.get("rules", {})
        design = inputs.get("design", {})
        violations = []
        warnings = []

        # Check minimum trace width
        min_trace = rules.get("min_trace_width", 0.15)
        if design.get("min_trace_width", min_trace) < min_trace:
            violations.append(
                f"Trace width {design.get('min_trace_width')}mm < minimum {min_trace}mm"
            )

        # Check minimum clearance
        min_clearance = rules.get("min_clearance", 0.15)
        if design.get("min_clearance", min_clearance) < min_clearance:
            violations.append(
                f"Clearance {design.get('min_clearance')}mm < minimum {min_clearance}mm"
            )

        # Check via drill
        min_drill = rules.get("min_drill", 0.3)
        if design.get("min_drill", min_drill) < min_drill:
            violations.append(
                f"Via drill {design.get('min_drill')}mm < minimum {min_drill}mm"
            )

        # Check annular ring
        min_annular = rules.get("min_annular_ring", 0.13)
        if design.get("min_annular_ring", min_annular) < min_annular:
            warnings.append(
                f"Annular ring {design.get('min_annular_ring')}mm near minimum {min_annular}mm"
            )

        return {
            "passed": len(violations) == 0,
            "violations": violations,
            "warnings": warnings,
            "rules_checked": len(rules),
        }

    def _footprint_lookup(self, inputs: dict) -> dict:
        package = inputs.get("package", "").upper()

        # Common package database
        packages = {
            "0201": {
                "footprint": "R_0201_0603Metric",
                "pads": 2,
                "dimensions": {"length": 0.6, "width": 0.3},
            },
            "0402": {
                "footprint": "R_0402_1005Metric",
                "pads": 2,
                "dimensions": {"length": 1.0, "width": 0.5},
            },
            "0603": {
                "footprint": "R_0603_1608Metric",
                "pads": 2,
                "dimensions": {"length": 1.6, "width": 0.8},
            },
            "0805": {
                "footprint": "R_0805_2012Metric",
                "pads": 2,
                "dimensions": {"length": 2.0, "width": 1.25},
            },
            "1206": {
                "footprint": "R_1206_3216Metric",
                "pads": 2,
                "dimensions": {"length": 3.2, "width": 1.6},
            },
            "SOT-23": {
                "footprint": "SOT-23",
                "pads": 3,
                "dimensions": {"length": 2.9, "width": 1.3},
            },
            "SOT-23-5": {
                "footprint": "SOT-23-5",
                "pads": 5,
                "dimensions": {"length": 2.9, "width": 1.6},
            },
            "SOT-223": {
                "footprint": "SOT-223",
                "pads": 4,
                "dimensions": {"length": 6.5, "width": 3.5},
            },
            "QFN-16": {
                "footprint": "QFN-16-1EP_3x3mm_P0.5mm",
                "pads": 17,
                "dimensions": {"length": 3.0, "width": 3.0},
            },
            "QFN-32": {
                "footprint": "QFN-32-1EP_5x5mm_P0.5mm",
                "pads": 33,
                "dimensions": {"length": 5.0, "width": 5.0},
            },
            "TQFP-32": {
                "footprint": "TQFP-32_7x7mm_P0.8mm",
                "pads": 32,
                "dimensions": {"length": 7.0, "width": 7.0},
            },
            "TQFP-48": {
                "footprint": "TQFP-48_7x7mm_P0.5mm",
                "pads": 48,
                "dimensions": {"length": 7.0, "width": 7.0},
            },
            "TQFP-64": {
                "footprint": "TQFP-64_10x10mm_P0.5mm",
                "pads": 64,
                "dimensions": {"length": 10.0, "width": 10.0},
            },
            "SOP-8": {
                "footprint": "SOIC-8_3.9x4.9mm_P1.27mm",
                "pads": 8,
                "dimensions": {"length": 4.9, "width": 3.9},
            },
            "SSOP-16": {
                "footprint": "SSOP-16_3.9x4.9mm_P0.635mm",
                "pads": 16,
                "dimensions": {"length": 4.9, "width": 3.9},
            },
            "USB-C": {
                "footprint": "USB_C_Receptacle_HRO_TYPE-C-31-M-12",
                "pads": 16,
                "dimensions": {"length": 8.94, "width": 7.35},
            },
        }

        match = packages.get(package)
        if match:
            return match
        return {
            "footprint": f"Unknown_{package}",
            "pads": 0,
            "dimensions": {},
            "note": f"Package {package} not in database",
        }

    def _stackup_calc(self, inputs: dict) -> dict:
        layers = inputs.get("layers", 4)
        total_thickness = inputs.get("thickness", 1.6)  # mm
        copper_weight = inputs.get("copper_weight", 1.0)  # oz
        er = inputs.get("dielectric_constant", 4.4)  # FR4

        copper_thickness_mm = copper_weight * 0.035  # 1oz = 35um
        num_dielectric = layers - 1
        dielectric_thickness = (
            total_thickness - layers * copper_thickness_mm
        ) / num_dielectric

        stackup = []
        for i in range(layers):
            stackup.append(
                {
                    "layer": i + 1,
                    "type": "copper",
                    "name": f"{'Top' if i == 0 else 'Bottom' if i == layers - 1 else f'Inner{i}'}",
                    "thickness_mm": round(copper_thickness_mm, 4),
                    "thickness_um": round(copper_thickness_mm * 1000, 1),
                }
            )
            if i < layers - 1:
                stackup.append(
                    {
                        "type": "dielectric",
                        "name": "Core" if i % 2 == 0 else "Prepreg",
                        "thickness_mm": round(dielectric_thickness, 4),
                        "er": er,
                    }
                )

        return {
            "stackup": stackup,
            "total_thickness": round(total_thickness, 2),
            "layers": layers,
            "copper_weight_oz": copper_weight,
            "dielectric_constant": er,
        }

    def _trace_width(self, inputs: dict) -> dict:
        current = inputs["current"]  # Amps
        copper_oz = inputs.get("copper_thickness", 1.0)  # oz
        temp_rise = inputs.get("temp_rise", 10.0)  # degrees C
        layer = inputs.get("layer", "external")

        copper_thickness_mil = copper_oz * 1.378  # 1oz = 1.378 mil
        k = K_EXTERNAL if layer == "external" else K_INTERNAL

        # IPC-2221 formula: A = (I / (k * dT^0.44))^(1/0.725)
        area = (current / (k * temp_rise**0.44)) ** (1 / 0.725)  # mil^2
        width_mil = area / copper_thickness_mil
        width_mm = width_mil * 0.0254

        # Resistance per cm
        area_cm2 = area * (0.00254**2)
        resistance_per_cm = COPPER_RESISTIVITY / area_cm2 if area_cm2 > 0 else 0

        return {
            "width_mm": round(width_mm, 3),
            "width_mil": round(width_mil, 1),
            "area_mil2": round(area, 1),
            "resistance_per_cm": round(resistance_per_cm, 6),
            "current": current,
            "temp_rise": temp_rise,
            "layer": layer,
            "copper_oz": copper_oz,
        }

    def _thermal_via(self, inputs: dict) -> dict:
        power = inputs["power"]  # Watts
        via_dia = inputs.get("via_diameter", 0.3)  # mm
        plating = inputs.get("via_plating", 25)  # um
        board_thickness = inputs.get("board_thickness", 1.6)  # mm
        max_temp_rise = inputs.get("max_temp_rise", 40)  # C

        # Thermal resistance of a single via
        # R_th = L / (k * A) where k_copper = 385 W/m-K
        via_radius = via_dia / 2  # mm
        plating_mm = plating / 1000
        inner_radius = via_radius - plating_mm
        cross_section = math.pi * (via_radius**2 - inner_radius**2)  # mm^2
        cross_section_m2 = cross_section * 1e-6
        length_m = board_thickness * 1e-3

        k_copper = 385  # W/m-K
        r_th_via = (
            length_m / (k_copper * cross_section_m2)
            if cross_section_m2 > 0
            else float("inf")
        )

        # Number of vias needed for target thermal resistance
        target_r_th = max_temp_rise / power if power > 0 else float("inf")
        vias_needed = max(1, math.ceil(r_th_via / target_r_th))

        # Array size (square)
        side = math.ceil(math.sqrt(vias_needed))

        return {
            "thermal_resistance_per_via": round(r_th_via, 2),
            "vias_needed": vias_needed,
            "array_size": f"{side}x{side}",
            "total_thermal_resistance": round(r_th_via / vias_needed, 2),
            "power": power,
            "via_diameter": via_dia,
        }
