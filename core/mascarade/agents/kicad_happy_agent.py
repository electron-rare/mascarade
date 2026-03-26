"""KiCad Happy Agent — agent tout-en-un pour l'analyse de projets KiCad.

Skills:
    analyze_schematic  — parser S-expression .kicad_sch, extraire composants/nets
    analyze_pcb        — analyser un .kicad_pcb (placement, routing stats)
    bom_extract        — extraire la BOM depuis un schematic
    bom_export         — exporter la BOM en CSV (JLCPCB, DigiKey, Mouser)
    component_source   — rechercher un composant dans la base LCSC
    dfm_check          — verifier les heuristiques DFM (trace, via, clearance)
    review             — review complet d'un projet KiCad
"""

from __future__ import annotations

import csv
import io
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from mascarade.agents.base import Agent
from mascarade.router.router import Strategy

logger = logging.getLogger("mascarade.agents.kicad_happy")

# ---------------------------------------------------------------------------
# LCSC component database (common parts)
# ---------------------------------------------------------------------------

LCSC_COMPONENTS: dict[str, dict[str, Any]] = {
    "R_100R": {
        "lcsc": "C25803",
        "mfr": "Uniroyal",
        "mpn": "0402WGF1000TCE",
        "desc": "100R 0402 1%",
        "pkg": "0402",
        "price": 0.002,
    },
    "R_1K": {
        "lcsc": "C11702",
        "mfr": "Uniroyal",
        "mpn": "0402WGF1001TCE",
        "desc": "1K 0402 1%",
        "pkg": "0402",
        "price": 0.002,
    },
    "R_4K7": {
        "lcsc": "C25905",
        "mfr": "Uniroyal",
        "mpn": "0402WGF4701TCE",
        "desc": "4.7K 0402 1%",
        "pkg": "0402",
        "price": 0.002,
    },
    "R_10K": {
        "lcsc": "C25744",
        "mfr": "Uniroyal",
        "mpn": "0402WGF1002TCE",
        "desc": "10K 0402 1%",
        "pkg": "0402",
        "price": 0.002,
    },
    "R_100K": {
        "lcsc": "C25741",
        "mfr": "Uniroyal",
        "mpn": "0402WGF1003TCE",
        "desc": "100K 0402 1%",
        "pkg": "0402",
        "price": 0.002,
    },
    "C_100nF": {
        "lcsc": "C1525",
        "mfr": "Samsung",
        "mpn": "CL05B104KO5NNNC",
        "desc": "100nF 0402 X7R 16V",
        "pkg": "0402",
        "price": 0.003,
    },
    "C_1uF": {
        "lcsc": "C52923",
        "mfr": "Samsung",
        "mpn": "CL05A105KA5NQNC",
        "desc": "1uF 0402 X5R 16V",
        "pkg": "0402",
        "price": 0.004,
    },
    "C_10uF": {
        "lcsc": "C19702",
        "mfr": "Samsung",
        "mpn": "CL10A106KP8NNNC",
        "desc": "10uF 0603 X5R 10V",
        "pkg": "0603",
        "price": 0.008,
    },
    "C_100uF": {
        "lcsc": "C59461",
        "mfr": "Samsung",
        "mpn": "CL31A107MQHNNNE",
        "desc": "100uF 1206 X5R 6.3V",
        "pkg": "1206",
        "price": 0.05,
    },
    "ESP32_S3_WROOM": {
        "lcsc": "C2913202",
        "mfr": "Espressif",
        "mpn": "ESP32-S3-WROOM-1-N16R8",
        "desc": "ESP32-S3 WiFi+BLE 16MB/8MB",
        "pkg": "Module",
        "price": 3.20,
    },
    "ESP32_C3_MINI": {
        "lcsc": "C2838502",
        "mfr": "Espressif",
        "mpn": "ESP32-C3-MINI-1-N4",
        "desc": "ESP32-C3 WiFi+BLE 4MB",
        "pkg": "Module",
        "price": 1.50,
    },
    "STM32F103C8": {
        "lcsc": "C8734",
        "mfr": "ST",
        "mpn": "STM32F103C8T6",
        "desc": "STM32F103 ARM Cortex-M3 72MHz",
        "pkg": "LQFP-48",
        "price": 1.80,
    },
    "STM32G431KB": {
        "lcsc": "C529339",
        "mfr": "ST",
        "mpn": "STM32G431KBT6",
        "desc": "STM32G4 ARM Cortex-M4 170MHz",
        "pkg": "LQFP-32",
        "price": 3.50,
    },
    "USB_C_16P": {
        "lcsc": "C2765186",
        "mfr": "SHOU HAN",
        "mpn": "TYPE-C-31-M-12",
        "desc": "USB-C 16pin SMD",
        "pkg": "SMD",
        "price": 0.10,
    },
    "AMS1117_3V3": {
        "lcsc": "C6186",
        "mfr": "AMS",
        "mpn": "AMS1117-3.3",
        "desc": "3.3V LDO 1A SOT-223",
        "pkg": "SOT-223",
        "price": 0.08,
    },
    "CH340N": {
        "lcsc": "C2977777",
        "mfr": "WCH",
        "mpn": "CH340N",
        "desc": "USB-UART bridge SOP-8",
        "pkg": "SOP-8",
        "price": 0.35,
    },
}

# ---------------------------------------------------------------------------
# DFM thresholds (JLCPCB-compatible defaults)
# ---------------------------------------------------------------------------

DFM_RULES: dict[str, dict[str, float]] = {
    "jlcpcb": {
        "min_trace_mm": 0.127,
        "min_space_mm": 0.127,
        "min_via_drill_mm": 0.3,
        "min_via_annular_mm": 0.15,
        "min_hole_mm": 0.3,
        "min_silkscreen_mm": 0.15,
        "min_courtyard_mm": 0.25,
    },
    "pcbway": {
        "min_trace_mm": 0.1,
        "min_space_mm": 0.1,
        "min_via_drill_mm": 0.2,
        "min_via_annular_mm": 0.125,
        "min_hole_mm": 0.2,
        "min_silkscreen_mm": 0.15,
        "min_courtyard_mm": 0.2,
    },
}


# ---------------------------------------------------------------------------
# S-expression parser (minimal, for .kicad_sch)
# ---------------------------------------------------------------------------


@dataclass
class SchComponent:
    reference: str = ""
    value: str = ""
    footprint: str = ""
    lib_id: str = ""
    position: tuple[float, float] = (0.0, 0.0)


@dataclass
class SchNet:
    name: str = ""
    pins: list[str] = field(default_factory=list)


def _tokenize_sexpr(text: str) -> list[str]:
    """Tokenize an S-expression string into a flat list of tokens."""
    tokens: list[str] = []
    i = 0
    n = len(text)
    while i < n:
        ch = text[i]
        if ch in ("(", ")"):
            tokens.append(ch)
            i += 1
        elif ch == '"':
            j = i + 1
            while j < n and text[j] != '"':
                if text[j] == "\\":
                    j += 1
                j += 1
            tokens.append(text[i : j + 1])
            i = j + 1
        elif ch in (" ", "\t", "\n", "\r"):
            i += 1
        else:
            j = i
            while j < n and text[j] not in ("(", ")", " ", "\t", "\n", "\r", '"'):
                j += 1
            tokens.append(text[i:j])
            i = j
    return tokens


def _parse_sexpr(tokens: list[str], pos: int = 0) -> tuple[list, int]:
    """Recursively parse tokens into nested lists."""
    result: list = []
    while pos < len(tokens):
        tok = tokens[pos]
        if tok == "(":
            child, pos = _parse_sexpr(tokens, pos + 1)
            result.append(child)
        elif tok == ")":
            return result, pos + 1
        else:
            # Strip quotes
            if tok.startswith('"') and tok.endswith('"'):
                tok = tok[1:-1]
            result.append(tok)
            pos += 1
    return result, pos


def parse_kicad_sch(path: str | Path) -> tuple[list[SchComponent], list[SchNet]]:
    """Parse a .kicad_sch file and extract components and nets.

    This is a simplified parser that handles the most common structures.
    """
    text = Path(path).read_text(encoding="utf-8", errors="replace")
    tokens = _tokenize_sexpr(text)
    tree, _ = _parse_sexpr(tokens)

    components: list[SchComponent] = []
    nets: list[SchNet] = []

    def _walk(node: list) -> None:
        if not node or not isinstance(node, list):
            return

        for item in node:
            if not isinstance(item, list) or not item:
                continue

            tag = item[0] if isinstance(item[0], str) else ""

            if tag == "symbol":
                comp = _extract_component(item)
                if comp and comp.reference:
                    components.append(comp)

            if tag == "wire" or tag == "label" or tag == "global_label":
                net = _extract_net_label(item)
                if net:
                    nets.append(net)

            _walk(item)

    def _extract_component(node: list) -> SchComponent | None:
        comp = SchComponent()
        for item in node:
            if not isinstance(item, list) or not item:
                continue
            tag = item[0] if isinstance(item[0], str) else ""
            if tag == "lib_id" and len(item) > 1:
                comp.lib_id = str(item[1])
            elif tag == "at" and len(item) >= 3:
                try:
                    comp.position = (float(item[1]), float(item[2]))
                except (ValueError, TypeError):
                    pass
            elif tag == "property":
                prop_name = str(item[1]) if len(item) > 1 else ""
                prop_val = str(item[2]) if len(item) > 2 else ""
                if prop_name == "Reference":
                    comp.reference = prop_val
                elif prop_name == "Value":
                    comp.value = prop_val
                elif prop_name == "Footprint":
                    comp.footprint = prop_val
        return comp

    def _extract_net_label(node: list) -> SchNet | None:
        tag = node[0] if isinstance(node[0], str) else ""
        if tag in ("label", "global_label") and len(node) > 1:
            name = str(node[1])
            return SchNet(name=name)
        return None

    _walk(tree)
    return components, nets


# ---------------------------------------------------------------------------
# BOM export helpers
# ---------------------------------------------------------------------------


def _bom_to_jlcpcb_csv(components: list[SchComponent]) -> str:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["Comment", "Designator", "Footprint", "LCSC Part #"])
    for comp in components:
        lcsc = _lookup_lcsc(comp.value)
        writer.writerow([comp.value, comp.reference, comp.footprint, lcsc])
    return buf.getvalue()


def _bom_to_digikey_csv(components: list[SchComponent]) -> str:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["Quantity", "Reference", "Value", "Footprint", "Description"])
    for comp in components:
        info = _lookup_component_info(comp.value)
        writer.writerow([1, comp.reference, comp.value, comp.footprint, info.get("desc", "")])
    return buf.getvalue()


def _bom_to_mouser_csv(components: list[SchComponent]) -> str:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(
        ["Mouser Part Number", "Manufacturer Part Number", "Quantity", "Reference", "Description"]
    )
    for comp in components:
        info = _lookup_component_info(comp.value)
        writer.writerow(["", info.get("mpn", ""), 1, comp.reference, info.get("desc", "")])
    return buf.getvalue()


def _lookup_lcsc(value: str) -> str:
    """Try to match a component value to an LCSC part number."""
    info = _lookup_component_info(value)
    return info.get("lcsc", "")


def _lookup_component_info(value: str) -> dict[str, Any]:
    """Fuzzy-match a component value against the LCSC database."""
    # Direct match
    if value in LCSC_COMPONENTS:
        return LCSC_COMPONENTS[value]

    # Normalize value for matching
    val_lower = value.lower().replace(" ", "").replace("_", "")

    for key, info in LCSC_COMPONENTS.items():
        key_lower = key.lower().replace("_", "")
        if val_lower == key_lower:
            return info
        # Partial match on description
        if val_lower in info.get("desc", "").lower().replace(" ", ""):
            return info

    return {}


# ---------------------------------------------------------------------------
# DFM check heuristics
# ---------------------------------------------------------------------------


@dataclass
class DFMViolation:
    rule: str
    message: str
    severity: str  # "error" | "warning"
    location: str = ""


def dfm_check(
    trace_widths_mm: list[float] | None = None,
    via_drills_mm: list[float] | None = None,
    clearances_mm: list[float] | None = None,
    via_annulars_mm: list[float] | None = None,
    manufacturer: str = "jlcpcb",
) -> list[DFMViolation]:
    """Run DFM heuristic checks against manufacturer rules."""
    rules = DFM_RULES.get(manufacturer, DFM_RULES["jlcpcb"])
    violations: list[DFMViolation] = []

    if trace_widths_mm:
        for i, tw in enumerate(trace_widths_mm):
            if tw < rules["min_trace_mm"]:
                violations.append(
                    DFMViolation(
                        rule="min_trace_width",
                        message=f"Trace width {tw:.3f}mm < min {rules['min_trace_mm']:.3f}mm",
                        severity="error",
                        location=f"trace[{i}]",
                    )
                )
            elif tw < rules["min_trace_mm"] * 1.5:
                violations.append(
                    DFMViolation(
                        rule="trace_width_margin",
                        message=f"Trace width {tw:.3f}mm close to min {rules['min_trace_mm']:.3f}mm",
                        severity="warning",
                        location=f"trace[{i}]",
                    )
                )

    if via_drills_mm:
        for i, vd in enumerate(via_drills_mm):
            if vd < rules["min_via_drill_mm"]:
                violations.append(
                    DFMViolation(
                        rule="min_via_drill",
                        message=f"Via drill {vd:.3f}mm < min {rules['min_via_drill_mm']:.3f}mm",
                        severity="error",
                        location=f"via[{i}]",
                    )
                )

    if clearances_mm:
        for i, cl in enumerate(clearances_mm):
            if cl < rules["min_space_mm"]:
                violations.append(
                    DFMViolation(
                        rule="min_clearance",
                        message=f"Clearance {cl:.3f}mm < min {rules['min_space_mm']:.3f}mm",
                        severity="error",
                        location=f"clearance[{i}]",
                    )
                )

    if via_annulars_mm:
        for i, va in enumerate(via_annulars_mm):
            if va < rules["min_via_annular_mm"]:
                violations.append(
                    DFMViolation(
                        rule="min_via_annular",
                        message=f"Via annular ring {va:.3f}mm < min {rules['min_via_annular_mm']:.3f}mm",
                        severity="error",
                        location=f"via_annular[{i}]",
                    )
                )

    return violations


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------


class KiCadHappyAgent(Agent):
    """Agent tout-en-un pour l'analyse et la review de projets KiCad.

    7 skills: analyze_schematic, analyze_pcb, bom_extract, bom_export,
    component_source, dfm_check, review.
    """

    SKILLS = [
        "analyze_schematic",
        "analyze_pcb",
        "bom_extract",
        "bom_export",
        "component_source",
        "dfm_check",
        "review",
    ]

    def __init__(self) -> None:
        super().__init__(
            name="kicad-happy",
            description=(
                "Agent KiCad tout-en-un: analyse schematic/PCB, extraction BOM, "
                "export JLCPCB/DigiKey/Mouser, sourcing LCSC, DFM check, review."
            ),
            system_prompt=(
                "You are KiCad Happy, a cheerful and thorough KiCad project analyst. "
                "You parse schematics, extract BOMs, check DFM rules, source components "
                "from LCSC/JLCPCB, and provide actionable design reviews. "
                "Always provide concrete numbers and part references."
            ),
            preferred_provider="mistral",
            preferred_model="mistral-large-latest",
            strategy=Strategy.DOMAIN,
            tools=["kicad_api", "python", "filesystem"],
            temperature=0.2,
            max_tokens=4096,
            skills=self.SKILLS,
            category="eda",
        )

    # -- skill: analyze_schematic -------------------------------------------

    async def analyze_schematic(self, sch_path: str, router=None) -> dict[str, Any]:
        """Parse a .kicad_sch and return components and nets."""
        path = Path(sch_path)
        if not path.exists():
            return {"error": f"File not found: {sch_path}"}

        components, nets = parse_kicad_sch(path)

        result = {
            "file": str(path),
            "component_count": len(components),
            "components": [
                {
                    "ref": c.reference,
                    "value": c.value,
                    "footprint": c.footprint,
                    "lib_id": c.lib_id,
                    "position": list(c.position),
                }
                for c in components
            ],
            "net_labels": [n.name for n in nets],
            "unique_nets": len({n.name for n in nets}),
        }

        if router:
            prompt = (
                f"Analyze this KiCad schematic summary and provide insights:\n\n"
                f"Components: {len(components)}\n"
                f"Nets: {len({n.name for n in nets})}\n"
                f"Component list: {', '.join(c.reference + '=' + c.value for c in components[:20])}\n\n"
                f"Provide: design quality assessment, potential issues, improvement suggestions."
            )
            resp = await self.run(prompt, router=router)
            result["ai_analysis"] = resp.content

        return result

    # -- skill: analyze_pcb -------------------------------------------------

    async def analyze_pcb(self, pcb_path: str, router=None) -> dict[str, Any]:
        """Basic analysis of a .kicad_pcb file (size, layers, footprints)."""
        path = Path(pcb_path)
        if not path.exists():
            return {"error": f"File not found: {pcb_path}"}

        text = path.read_text(encoding="utf-8", errors="replace")

        # Extract basic stats via regex (lightweight, no full parser needed)
        footprints = re.findall(r'\(footprint\s+"([^"]*)"', text)
        layers = re.findall(r'\(layer\s+"([^"]*)"', text)
        vias = re.findall(r"\(via\s", text)
        tracks = re.findall(r"\(segment\s", text)
        zones = re.findall(r"\(zone\s", text)

        # Board outline
        edge_cuts = re.findall(
            r"\(gr_line\s+\(start\s+([\d.]+)\s+([\d.]+)\)\s+\(end\s+([\d.]+)\s+([\d.]+)\).*?Edge\.Cuts",
            text,
        )

        result = {
            "file": str(path),
            "footprint_count": len(footprints),
            "unique_footprints": len(set(footprints)),
            "track_count": len(tracks),
            "via_count": len(vias),
            "zone_count": len(zones),
            "layers_used": sorted(set(layers)),
            "edge_segments": len(edge_cuts),
        }

        if router:
            prompt = (
                f"Analyze this KiCad PCB summary:\n"
                f"Footprints: {len(footprints)}, Tracks: {len(tracks)}, "
                f"Vias: {len(vias)}, Zones: {len(zones)}, "
                f"Layers: {', '.join(sorted(set(layers))[:8])}\n"
                f"Provide routing quality assessment and improvement suggestions."
            )
            resp = await self.run(prompt, router=router)
            result["ai_analysis"] = resp.content

        return result

    # -- skill: bom_extract -------------------------------------------------

    async def bom_extract(self, sch_path: str) -> list[dict[str, str]]:
        """Extract BOM from a .kicad_sch as a list of dicts."""
        components, _ = parse_kicad_sch(sch_path)
        return [
            {
                "reference": c.reference,
                "value": c.value,
                "footprint": c.footprint,
                "lcsc": _lookup_lcsc(c.value),
            }
            for c in components
        ]

    # -- skill: bom_export --------------------------------------------------

    async def bom_export(
        self,
        sch_path: str,
        fmt: str = "jlcpcb",
    ) -> str:
        """Export BOM as CSV string in the specified format.

        Formats: jlcpcb, digikey, mouser.
        """
        components, _ = parse_kicad_sch(sch_path)

        exporters = {
            "jlcpcb": _bom_to_jlcpcb_csv,
            "digikey": _bom_to_digikey_csv,
            "mouser": _bom_to_mouser_csv,
        }

        exporter = exporters.get(fmt)
        if exporter is None:
            return f"Unknown format: {fmt}. Supported: {', '.join(exporters)}"

        return exporter(components)

    # -- skill: component_source --------------------------------------------

    async def component_source(self, query: str) -> list[dict[str, Any]]:
        """Search the LCSC component database for a query string."""
        query_lower = query.lower().replace(" ", "").replace("_", "")
        matches: list[dict[str, Any]] = []

        for key, info in LCSC_COMPONENTS.items():
            searchable = (key + info.get("desc", "") + info.get("mpn", "")).lower().replace(" ", "")
            if query_lower in searchable:
                matches.append({"key": key, **info})

        return matches

    # -- skill: dfm_check ---------------------------------------------------

    async def dfm_check_skill(
        self,
        trace_widths_mm: list[float] | None = None,
        via_drills_mm: list[float] | None = None,
        clearances_mm: list[float] | None = None,
        via_annulars_mm: list[float] | None = None,
        manufacturer: str = "jlcpcb",
    ) -> dict[str, Any]:
        """Run DFM checks and return structured results."""
        violations = dfm_check(
            trace_widths_mm=trace_widths_mm,
            via_drills_mm=via_drills_mm,
            clearances_mm=clearances_mm,
            via_annulars_mm=via_annulars_mm,
            manufacturer=manufacturer,
        )

        errors = [v for v in violations if v.severity == "error"]
        warnings = [v for v in violations if v.severity == "warning"]

        return {
            "manufacturer": manufacturer,
            "rules": DFM_RULES.get(manufacturer, {}),
            "total_violations": len(violations),
            "errors": len(errors),
            "warnings": len(warnings),
            "violations": [
                {
                    "rule": v.rule,
                    "message": v.message,
                    "severity": v.severity,
                    "location": v.location,
                }
                for v in violations
            ],
            "pass": len(errors) == 0,
        }

    # -- skill: review ------------------------------------------------------

    async def review(
        self, sch_path: str, pcb_path: str | None = None, router=None
    ) -> dict[str, Any]:
        """Full review of a KiCad project: schematic + optional PCB."""
        result: dict[str, Any] = {}

        # Schematic analysis
        result["schematic"] = await self.analyze_schematic(sch_path)

        # BOM with sourcing
        bom = await self.bom_extract(sch_path)
        result["bom"] = bom
        result["bom_sourced"] = sum(1 for b in bom if b.get("lcsc")) if bom else 0
        result["bom_total"] = len(bom)

        # PCB analysis if provided
        if pcb_path and Path(pcb_path).exists():
            result["pcb"] = await self.analyze_pcb(pcb_path)

        # AI review
        if router:
            summary_lines = [
                f"Components: {len(bom)}",
                f"LCSC sourced: {result['bom_sourced']}/{result['bom_total']}",
            ]
            if "pcb" in result:
                summary_lines.append(f"Tracks: {result['pcb'].get('track_count', '?')}")
                summary_lines.append(f"Vias: {result['pcb'].get('via_count', '?')}")

            prompt = (
                f"Review this KiCad project:\n\n"
                f"{chr(10).join(summary_lines)}\n\n"
                f"BOM: {', '.join(b['reference'] + '=' + b['value'] for b in bom[:15])}\n\n"
                f"Provide: overall quality score (1-10), key issues, recommendations."
            )
            resp = await self.run(prompt, router=router)
            result["ai_review"] = resp.content

        return result
