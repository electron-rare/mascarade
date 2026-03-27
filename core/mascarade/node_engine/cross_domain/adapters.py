"""Concrete cross-domain adapter implementations.

Each adapter converts data between two domain-specific type systems,
performing real structural transformations rather than pass-through.
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import re
import uuid
from datetime import datetime, timezone
from typing import Any

from mascarade.node_engine.cross_domain.adapter import (
    AdapterMapping,
    CrossDomainAdapter,
)

logger = logging.getLogger("mascarade.node_engine.cross_domain.adapters")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _safe_get(data: dict[str, Any], key: str, default: Any = None) -> Any:
    """Safely extract a key from a dict, returning *default* on any failure."""
    if not isinstance(data, dict):
        return default
    return data.get(key, default)


def _extract_json_block(text: str) -> dict[str, Any] | None:
    """Try to extract a JSON object from markdown fenced blocks or raw text."""
    # Try fenced code blocks first (```json ... ``` or ``` ... ```)
    fenced = re.search(r"```(?:json)?\s*\n(.*?)```", text, re.DOTALL)
    if fenced:
        try:
            return json.loads(fenced.group(1))
        except json.JSONDecodeError:
            pass
    # Try raw JSON object anywhere in the text
    brace = re.search(r"\{.*\}", text, re.DOTALL)
    if brace:
        try:
            return json.loads(brace.group(0))
        except json.JSONDecodeError:
            pass
    return None


def _extract_key_value_pairs(text: str) -> dict[str, str]:
    """Extract simple key: value or key = value pairs from text."""
    pairs: dict[str, str] = {}
    for match in re.finditer(r"(\w[\w\s]*?)\s*[:=]\s*([^\n,;]+)", text):
        key = match.group(1).strip().lower().replace(" ", "_")
        pairs[key] = match.group(2).strip()
    return pairs


# ---------------------------------------------------------------------------
# 1. AIToCADAdapter
# ---------------------------------------------------------------------------


class AIToCADAdapter(CrossDomainAdapter):
    """Convert AI LLMResponse into CAD-domain structures.

    Supported conversions:
    - LLMResponse -> CADDocument  (extract structured design description)
    - LLMResponse -> GCode        (extract G-code program from LLM text)
    """

    def supported_mappings(self) -> list[AdapterMapping]:
        return [
            AdapterMapping(
                source_domain="ai",
                source_type="LLMResponse",
                target_domain="cad",
                target_type="CADDocument",
                lossy=True,
                requires_config=False,
            ),
            AdapterMapping(
                source_domain="ai",
                source_type="LLMResponse",
                target_domain="cad",
                target_type="GCode",
                lossy=True,
                requires_config=False,
            ),
        ]

    async def convert(
        self,
        source_data: Any,
        mapping: AdapterMapping,
        config: dict[str, Any] | None = None,
    ) -> Any:
        content = _safe_get(source_data, "content", "")
        if not content:
            raise ValueError("LLMResponse has empty content — cannot extract CAD data")

        if mapping.target_type == "CADDocument":
            return self._to_cad_document(content, source_data, config or {})
        if mapping.target_type == "GCode":
            return self._to_gcode(content)
        raise ValueError(f"Unsupported target type: {mapping.target_type}")

    # -- private -----------------------------------------------------------

    def _to_cad_document(
        self, content: str, source: dict[str, Any], config: dict[str, Any]
    ) -> dict[str, Any]:
        """Parse LLM output into a CADDocument structure."""
        # Try structured JSON first
        extracted = _extract_json_block(content)
        objects: list[dict[str, Any]] = []
        parameters: dict[str, Any] = {}

        if extracted:
            # If the LLM returned well-structured JSON, pull objects and params
            objects = extracted.get("objects", [])
            parameters = {
                k: v
                for k, v in extracted.items()
                if k not in ("objects", "name", "document_id")
            }
            # Ensure each object has required fields
            for i, obj in enumerate(objects):
                obj.setdefault("label", f"object_{i}")
                obj.setdefault("type", "solid")
        else:
            # Fallback: parse free-form text for dimensional info
            kv = _extract_key_value_pairs(content)
            for key in ("width", "height", "depth", "length", "radius", "diameter"):
                if key in kv:
                    try:
                        parameters[key] = float(
                            re.sub(r"[^\d.]", "", kv[key])
                        )
                    except ValueError:
                        parameters[key] = kv[key]

            # Detect shape mentions
            shape_patterns = {
                "box": r"\b(box|cube|rectangular)\b",
                "cylinder": r"\b(cylinder|cylindrical|tube)\b",
                "sphere": r"\b(sphere|spherical|ball)\b",
                "cone": r"\b(cone|conical)\b",
                "extrusion": r"\b(extrude|extrusion|profile)\b",
            }
            lower = content.lower()
            for shape_type, pattern in shape_patterns.items():
                if re.search(pattern, lower):
                    objects.append(
                        {
                            "label": shape_type,
                            "type": "solid",
                            "shape_type": shape_type,
                        }
                    )

            if not objects:
                # Last resort: create a generic placeholder from the response
                objects.append(
                    {
                        "label": "ai_generated",
                        "type": "solid",
                        "shape_type": "unknown",
                    }
                )

        doc_name = config.get("name", "ai_generated_design")
        return {
            "document_id": str(uuid.uuid4()),
            "name": doc_name,
            "objects": objects,
            "parameters": parameters,
        }

    def _to_gcode(self, content: str) -> dict[str, Any]:
        """Extract G-code program from LLM output."""
        # Look for G-code inside fenced blocks
        fenced = re.search(r"```(?:gcode)?\s*\n(.*?)```", content, re.DOTALL)
        program = fenced.group(1).strip() if fenced else ""

        if not program:
            # Try to find G-code lines directly (lines starting with G/M/T/S/F)
            lines = [
                line.strip()
                for line in content.splitlines()
                if re.match(r"^\s*[GMTSF]\d", line, re.IGNORECASE)
            ]
            program = "\n".join(lines)

        if not program:
            raise ValueError(
                "LLMResponse does not contain recognizable G-code content"
            )

        # Parse basic stats
        tool_changes = len(re.findall(r"\bT\d+", program, re.IGNORECASE))
        bounds = self._estimate_gcode_bounds(program)
        move_count = len(re.findall(r"\b[Gg][01]\b", program))
        estimated_time_s = float(move_count) * 0.5  # rough heuristic

        return {
            "program": program,
            "estimated_time_s": estimated_time_s,
            "bounds": bounds,
            "tool_changes": tool_changes,
        }

    @staticmethod
    def _estimate_gcode_bounds(program: str) -> dict[str, float]:
        """Scan G-code lines for max X/Y/Z coordinates."""
        max_vals = {"x": 0.0, "y": 0.0, "z": 0.0}
        for axis in ("x", "y", "z"):
            for m in re.finditer(rf"{axis.upper()}([\d.]+)", program):
                try:
                    val = float(m.group(1))
                    if val > max_vals[axis]:
                        max_vals[axis] = val
                except ValueError:
                    pass
        return max_vals


# ---------------------------------------------------------------------------
# 2. AIToElectronicsAdapter
# ---------------------------------------------------------------------------


class AIToElectronicsAdapter(CrossDomainAdapter):
    """Convert AI LLMResponse into Electronics-domain structures.

    Supported conversions:
    - LLMResponse -> Netlist       (extract SPICE/KiCad netlist from text)
    - LLMResponse -> ComponentSpec (extract component parameters from text)
    """

    def supported_mappings(self) -> list[AdapterMapping]:
        return [
            AdapterMapping(
                source_domain="ai",
                source_type="LLMResponse",
                target_domain="electronics",
                target_type="Netlist",
                lossy=True,
                requires_config=False,
            ),
            AdapterMapping(
                source_domain="ai",
                source_type="LLMResponse",
                target_domain="electronics",
                target_type="ComponentSpec",
                lossy=True,
                requires_config=False,
            ),
        ]

    async def convert(
        self,
        source_data: Any,
        mapping: AdapterMapping,
        config: dict[str, Any] | None = None,
    ) -> Any:
        content = _safe_get(source_data, "content", "")
        if not content:
            raise ValueError(
                "LLMResponse has empty content — cannot extract electronics data"
            )

        if mapping.target_type == "Netlist":
            return self._to_netlist(content, config or {})
        if mapping.target_type == "ComponentSpec":
            return self._to_component_spec(content, config or {})
        raise ValueError(f"Unsupported target type: {mapping.target_type}")

    # -- private -----------------------------------------------------------

    def _to_netlist(
        self, content: str, config: dict[str, Any]
    ) -> dict[str, Any]:
        """Extract a netlist from LLM text."""
        # Try to find a SPICE netlist inside fenced blocks
        fenced = re.search(
            r"```(?:spice|netlist)?\s*\n(.*?)```", content, re.DOTALL
        )
        netlist_content = fenced.group(1).strip() if fenced else ""

        fmt = config.get("format", "spice")

        if not netlist_content:
            # Detect SPICE-like lines: start with . or component designators
            spice_lines = [
                line.strip()
                for line in content.splitlines()
                if re.match(
                    r"^\s*(\.[a-z]|[RVCLQDMJKBXIF]\w*\s)",
                    line,
                    re.IGNORECASE,
                )
            ]
            if spice_lines:
                netlist_content = "\n".join(spice_lines)
                fmt = "spice"

        if not netlist_content:
            raise ValueError(
                "LLMResponse does not contain recognizable netlist content"
            )

        # Extract component references from the netlist
        components = list(
            {
                m.group(0)
                for m in re.finditer(
                    r"\b[RVCLQDMJKBXIF]\w+", netlist_content
                )
            }
        )
        components.sort()

        # Detect analysis directives
        analyses = [
            m.group(1)
            for m in re.finditer(
                r"\.(tran|ac|dc|noise|op|tf|sens)\b",
                netlist_content,
                re.IGNORECASE,
            )
        ]

        return {
            "format": fmt,
            "content": netlist_content,
            "components": components,
            "analyses": analyses,
        }

    def _to_component_spec(
        self, content: str, config: dict[str, Any]
    ) -> dict[str, Any]:
        """Extract a component specification from LLM text."""
        extracted = _extract_json_block(content)

        if extracted:
            # Validate required fields, fill defaults
            spec = {
                "mpn": extracted.get("mpn", extracted.get("part_number", "UNKNOWN")),
                "manufacturer": extracted.get("manufacturer", "Unknown"),
                "category": extracted.get("category", "passive"),
                "parameters": {},
                "footprint": extracted.get("footprint", ""),
                "lcsc_part": extracted.get("lcsc_part"),
                "datasheet_url": extracted.get("datasheet_url"),
            }
            # Collect any extra keys as parameters
            reserved = {
                "mpn", "part_number", "manufacturer", "category",
                "footprint", "lcsc_part", "datasheet_url",
            }
            spec["parameters"] = {
                k: v for k, v in extracted.items() if k not in reserved
            }
            return spec

        # Fallback: parse key-value pairs from text
        kv = _extract_key_value_pairs(content)
        return {
            "mpn": kv.get("mpn", kv.get("part_number", "UNKNOWN")),
            "manufacturer": kv.get("manufacturer", "Unknown"),
            "category": kv.get("category", kv.get("type", "passive")),
            "parameters": {
                k: v
                for k, v in kv.items()
                if k
                not in (
                    "mpn", "part_number", "manufacturer", "category",
                    "type", "footprint", "lcsc_part", "datasheet_url",
                )
            },
            "footprint": kv.get("footprint", ""),
            "lcsc_part": kv.get("lcsc_part"),
            "datasheet_url": kv.get("datasheet_url"),
        }


# ---------------------------------------------------------------------------
# 3. CADToElectronicsAdapter
# ---------------------------------------------------------------------------


class CADToElectronicsAdapter(CrossDomainAdapter):
    """Convert CAD schematic/layout data into Electronics-domain structures.

    Supported conversions:
    - SchematicData -> Netlist    (derive netlist from schematic symbols/nets)
    - PCBLayout    -> DRCReport  (basic design-rule checks on layout data)
    """

    def supported_mappings(self) -> list[AdapterMapping]:
        return [
            AdapterMapping(
                source_domain="cad",
                source_type="SchematicData",
                target_domain="electronics",
                target_type="Netlist",
                lossy=False,
                requires_config=False,
            ),
            AdapterMapping(
                source_domain="cad",
                source_type="PCBLayout",
                target_domain="electronics",
                target_type="DRCReport",
                lossy=False,
                requires_config=False,
            ),
        ]

    async def convert(
        self,
        source_data: Any,
        mapping: AdapterMapping,
        config: dict[str, Any] | None = None,
    ) -> Any:
        if mapping.source_type == "SchematicData" and mapping.target_type == "Netlist":
            return self._schematic_to_netlist(source_data, config or {})
        if mapping.source_type == "PCBLayout" and mapping.target_type == "DRCReport":
            return self._pcb_to_drc(source_data, config or {})
        raise ValueError(
            f"Unsupported conversion: {mapping.source_type} -> {mapping.target_type}"
        )

    # -- private -----------------------------------------------------------

    def _schematic_to_netlist(
        self, data: dict[str, Any], config: dict[str, Any]
    ) -> dict[str, Any]:
        """Convert schematic symbol/net data into a SPICE-like netlist."""
        symbols = _safe_get(data, "symbols", [])
        nets = _safe_get(data, "nets", [])

        if not symbols:
            raise ValueError("SchematicData contains no symbols")

        fmt = config.get("format", "spice")

        # Build a ref -> value mapping for components
        ref_value: dict[str, str] = {}
        for sym in symbols:
            ref = _safe_get(sym, "ref", "")
            value = _safe_get(sym, "value", "")
            if ref:
                ref_value[ref] = value

        # Generate SPICE netlist lines from nets
        lines: list[str] = [f"* Auto-generated netlist from SchematicData"]
        lines.append(f"* Components: {len(symbols)}, Nets: {len(nets)}")
        lines.append("")

        # Map net names to integer node numbers (SPICE convention)
        net_ids: dict[str, int] = {"GND": 0, "gnd": 0, "0": 0}
        next_id = 1

        def net_id(name: str) -> int:
            nonlocal next_id
            if name not in net_ids:
                net_ids[name] = next_id
                next_id += 1
            return net_ids[name]

        # For each component, try to reconstruct a SPICE line
        # Build pin-to-net mapping: "REF.PIN" -> net_name
        pin_net: dict[str, str] = {}
        for net in nets:
            net_name = _safe_get(net, "name", "")
            for pin in _safe_get(net, "pins", []):
                pin_net[pin] = net_name

        for sym in symbols:
            ref = _safe_get(sym, "ref", "")
            value = _safe_get(sym, "value", "")
            if not ref:
                continue

            # Collect nets connected to this component's pins
            comp_nets: list[str] = []
            for pin_key, net_name in pin_net.items():
                if pin_key.startswith(f"{ref}.") or pin_key.startswith(f"{ref}/"):
                    comp_nets.append(net_name)

            if not comp_nets:
                # Pins not mapped — add as comment
                lines.append(f"* {ref} {value} (pins not mapped to nets)")
                continue

            node_str = " ".join(str(net_id(n)) for n in comp_nets)
            lines.append(f"{ref} {node_str} {value}")

        lines.append("")
        lines.append(".end")

        components = sorted(ref_value.keys())
        analyses: list[str] = []
        power_flags = _safe_get(data, "power_flags", [])
        if power_flags:
            lines.insert(2, f"* Power flags: {', '.join(power_flags)}")

        return {
            "format": fmt,
            "content": "\n".join(lines),
            "components": components,
            "analyses": analyses,
        }

    def _pcb_to_drc(
        self, data: dict[str, Any], config: dict[str, Any]
    ) -> dict[str, Any]:
        """Run basic design-rule checks on PCB layout data."""
        components = _safe_get(data, "components", [])
        traces = _safe_get(data, "traces", [])
        layers = _safe_get(data, "layers", [])

        violations: list[dict[str, Any]] = []
        rules_checked = 0

        # Rule 1: Every component must have a footprint
        rules_checked += 1
        for comp in components:
            ref = _safe_get(comp, "ref", "?")
            if not _safe_get(comp, "footprint"):
                violations.append(
                    {
                        "rule": "missing_footprint",
                        "severity": "error",
                        "ref": ref,
                        "message": f"Component {ref} has no footprint assigned",
                    }
                )

        # Rule 2: Trace width must be positive
        rules_checked += 1
        for i, trace in enumerate(traces):
            width = _safe_get(trace, "width", 0)
            if not isinstance(width, (int, float)) or width <= 0:
                violations.append(
                    {
                        "rule": "invalid_trace_width",
                        "severity": "error",
                        "trace_index": i,
                        "net": _safe_get(trace, "net", "?"),
                        "message": f"Trace on net '{_safe_get(trace, 'net', '?')}' "
                        f"has invalid width: {width}",
                    }
                )

        # Rule 3: Traces must reference a valid layer
        rules_checked += 1
        layer_set = set(layers) if layers else set()
        for i, trace in enumerate(traces):
            layer = _safe_get(trace, "layer", "")
            if layer_set and layer not in layer_set:
                violations.append(
                    {
                        "rule": "invalid_layer",
                        "severity": "warning",
                        "trace_index": i,
                        "net": _safe_get(trace, "net", "?"),
                        "message": f"Trace references layer '{layer}' not in "
                        f"board layer stack: {layers}",
                    }
                )

        # Rule 4: Minimum trace width (configurable, default 0.15mm)
        min_width = config.get("min_trace_width_mm", 0.15)
        rules_checked += 1
        for i, trace in enumerate(traces):
            width = _safe_get(trace, "width", 0)
            if isinstance(width, (int, float)) and 0 < width < min_width:
                violations.append(
                    {
                        "rule": "trace_width_below_minimum",
                        "severity": "warning",
                        "trace_index": i,
                        "net": _safe_get(trace, "net", "?"),
                        "message": f"Trace width {width}mm is below minimum "
                        f"{min_width}mm on net '{_safe_get(trace, 'net', '?')}'",
                    }
                )

        # Rule 5: Duplicate component references
        rules_checked += 1
        seen_refs: set[str] = set()
        for comp in components:
            ref = _safe_get(comp, "ref", "")
            if ref in seen_refs:
                violations.append(
                    {
                        "rule": "duplicate_reference",
                        "severity": "error",
                        "ref": ref,
                        "message": f"Duplicate component reference: {ref}",
                    }
                )
            if ref:
                seen_refs.add(ref)

        board_file = config.get("board_file", "unknown.kicad_pcb")

        return {
            "passed": len(violations) == 0,
            "violations": violations,
            "rules_checked": rules_checked,
            "board_file": board_file,
        }


# ---------------------------------------------------------------------------
# 4. ElectronicsToHardwareAdapter
# ---------------------------------------------------------------------------


class ElectronicsToHardwareAdapter(CrossDomainAdapter):
    """Convert Electronics-domain data into Hardware-domain structures.

    The hardware domain does not yet have formal type definitions, so this
    adapter produces well-structured dicts matching the conventions used by
    embedded device management (OTA payloads, device descriptors).

    Supported conversions:
    - FirmwareBinary -> OTAPayload      (package firmware for over-the-air update)
    - ComponentSpec  -> DeviceDescriptor (derive hardware descriptor from component)
    """

    def supported_mappings(self) -> list[AdapterMapping]:
        return [
            AdapterMapping(
                source_domain="electronics",
                source_type="FirmwareBinary",
                target_domain="hardware",
                target_type="OTAPayload",
                lossy=False,
                requires_config=False,
            ),
            AdapterMapping(
                source_domain="electronics",
                source_type="ComponentSpec",
                target_domain="hardware",
                target_type="DeviceDescriptor",
                lossy=True,
                requires_config=False,
            ),
        ]

    async def convert(
        self,
        source_data: Any,
        mapping: AdapterMapping,
        config: dict[str, Any] | None = None,
    ) -> Any:
        if mapping.target_type == "OTAPayload":
            return self._firmware_to_ota(source_data, config or {})
        if mapping.target_type == "DeviceDescriptor":
            return self._component_to_device(source_data, config or {})
        raise ValueError(f"Unsupported target type: {mapping.target_type}")

    # -- private -----------------------------------------------------------

    def _firmware_to_ota(
        self, data: dict[str, Any], config: dict[str, Any]
    ) -> dict[str, Any]:
        """Package a FirmwareBinary as an OTA update payload."""
        binary_b64 = _safe_get(data, "binary", "")
        target = _safe_get(data, "target", "")
        framework = _safe_get(data, "framework", "")
        size_bytes = _safe_get(data, "size_bytes", 0)

        if not binary_b64:
            raise ValueError("FirmwareBinary has no binary content")
        if not target:
            raise ValueError("FirmwareBinary has no target platform")

        # Compute integrity hash over the raw binary
        try:
            raw = base64.b64decode(binary_b64)
            sha256 = hashlib.sha256(raw).hexdigest()
        except Exception:
            # If base64 decode fails, hash the string representation
            sha256 = hashlib.sha256(binary_b64.encode()).hexdigest()

        # Determine OTA partition scheme from framework and sections
        sections = _safe_get(data, "sections", {})
        partition_label = config.get("partition", "ota_0")

        # Estimate if the binary fits typical OTA partition sizes
        max_ota_bytes = config.get("max_ota_bytes", 1_572_864)  # 1.5 MiB default
        fits = size_bytes <= max_ota_bytes if size_bytes else True

        return {
            "firmware_b64": binary_b64,
            "target": target,
            "framework": framework,
            "size_bytes": size_bytes,
            "sha256": sha256,
            "partition": partition_label,
            "fits_partition": fits,
            "max_ota_bytes": max_ota_bytes,
            "sections": sections,
            "version": config.get("version", "0.0.0"),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

    def _component_to_device(
        self, data: dict[str, Any], config: dict[str, Any]
    ) -> dict[str, Any]:
        """Derive a hardware device descriptor from a ComponentSpec."""
        mpn = _safe_get(data, "mpn", "UNKNOWN")
        manufacturer = _safe_get(data, "manufacturer", "Unknown")
        category = _safe_get(data, "category", "")
        parameters = _safe_get(data, "parameters", {})
        footprint = _safe_get(data, "footprint", "")

        # Infer device class from category and parameters
        device_class = self._infer_device_class(category, parameters)

        # Extract communication interfaces from parameters
        interfaces: list[str] = []
        param_lower = {k.lower(): v for k, v in parameters.items()}
        for iface in ("i2c", "spi", "uart", "usb", "can", "jtag", "swd", "gpio"):
            if iface in param_lower or any(iface in str(v).lower() for v in param_lower.values()):
                interfaces.append(iface.upper())

        # Extract voltage/power info
        supply_voltage = None
        for key in ("vcc", "vdd", "supply_voltage", "voltage", "v_supply"):
            if key in param_lower:
                try:
                    supply_voltage = float(
                        re.sub(r"[^\d.]", "", str(param_lower[key]))
                    )
                except ValueError:
                    supply_voltage = str(param_lower[key])
                break

        return {
            "mpn": mpn,
            "manufacturer": manufacturer,
            "device_class": device_class,
            "footprint": footprint,
            "interfaces": interfaces,
            "supply_voltage": supply_voltage,
            "parameters": parameters,
            "datasheet_url": _safe_get(data, "datasheet_url"),
        }

    @staticmethod
    def _infer_device_class(category: str, parameters: dict[str, Any]) -> str:
        """Map component category/parameters to a hardware device class."""
        cat = category.lower()
        class_map = {
            "mcu": "microcontroller",
            "microcontroller": "microcontroller",
            "sensor": "sensor",
            "adc": "analog_converter",
            "dac": "analog_converter",
            "regulator": "power_supply",
            "ldo": "power_supply",
            "dc-dc": "power_supply",
            "mosfet": "switch",
            "transistor": "switch",
            "relay": "switch",
            "connector": "connector",
            "led": "indicator",
            "display": "display",
            "memory": "memory",
            "eeprom": "memory",
            "flash": "memory",
            "wireless": "communication",
            "bluetooth": "communication",
            "wifi": "communication",
            "lora": "communication",
        }
        for keyword, cls in class_map.items():
            if keyword in cat:
                return cls
        return "passive" if cat in ("resistor", "capacitor", "inductor", "passive") else "unknown"


# ---------------------------------------------------------------------------
# 5. HardwareToAIAdapter
# ---------------------------------------------------------------------------


class HardwareToAIAdapter(CrossDomainAdapter):
    """Convert Hardware-domain sensor/GPIO data into AI ChatMessage format.

    This adapter formats raw hardware telemetry as natural-language messages
    suitable for LLM consumption, enabling AI reasoning about physical state.

    Supported conversions:
    - SensorReading  -> ChatMessage (format sensor data as user message)
    - GPIOState      -> ChatMessage (format GPIO pin states as user message)
    """

    def supported_mappings(self) -> list[AdapterMapping]:
        return [
            AdapterMapping(
                source_domain="hardware",
                source_type="SensorReading",
                target_domain="ai",
                target_type="ChatMessage",
                lossy=True,
                requires_config=False,
            ),
            AdapterMapping(
                source_domain="hardware",
                source_type="GPIOState",
                target_domain="ai",
                target_type="ChatMessage",
                lossy=True,
                requires_config=False,
            ),
        ]

    async def convert(
        self,
        source_data: Any,
        mapping: AdapterMapping,
        config: dict[str, Any] | None = None,
    ) -> Any:
        cfg = config or {}

        if mapping.source_type == "SensorReading":
            return self._sensor_to_chat(source_data, cfg)
        if mapping.source_type == "GPIOState":
            return self._gpio_to_chat(source_data, cfg)
        raise ValueError(f"Unsupported source type: {mapping.source_type}")

    # -- private -----------------------------------------------------------

    def _sensor_to_chat(
        self, data: dict[str, Any], config: dict[str, Any]
    ) -> dict[str, Any]:
        """Format sensor readings as a natural-language ChatMessage."""
        sensor_id = _safe_get(data, "sensor_id", "unknown_sensor")
        sensor_type = _safe_get(data, "sensor_type", _safe_get(data, "type", "generic"))
        value = _safe_get(data, "value")
        unit = _safe_get(data, "unit", "")
        timestamp = _safe_get(data, "timestamp", "")
        metadata = _safe_get(data, "metadata", {})

        if value is None:
            raise ValueError("SensorReading has no value")

        # Build human-readable description
        parts: list[str] = []
        parts.append(
            f"Sensor '{sensor_id}' ({sensor_type}) reports: {value}"
            + (f" {unit}" if unit else "")
        )

        if timestamp:
            parts.append(f"Timestamp: {timestamp}")

        # Include thresholds and status if available
        status = _safe_get(data, "status", "")
        if status:
            parts.append(f"Status: {status}")

        min_val = _safe_get(data, "min_threshold")
        max_val = _safe_get(data, "max_threshold")
        if min_val is not None or max_val is not None:
            range_str = f"[{min_val or '...'}, {max_val or '...'}]"
            parts.append(f"Acceptable range: {range_str}")

            # Check for out-of-range condition
            try:
                v = float(value)
                if min_val is not None and v < float(min_val):
                    parts.append(f"WARNING: Value {v} is BELOW minimum threshold {min_val}")
                if max_val is not None and v > float(max_val):
                    parts.append(f"WARNING: Value {v} is ABOVE maximum threshold {max_val}")
            except (ValueError, TypeError):
                pass

        if metadata:
            details = ", ".join(f"{k}={v}" for k, v in metadata.items())
            parts.append(f"Additional: {details}")

        # Optional context prompt from config
        context_prompt = config.get("context", "")
        if context_prompt:
            parts.append(f"Context: {context_prompt}")

        role = config.get("role", "user")
        return {
            "role": role,
            "content": "\n".join(parts),
            "name": f"sensor_{sensor_id}",
        }

    def _gpio_to_chat(
        self, data: dict[str, Any], config: dict[str, Any]
    ) -> dict[str, Any]:
        """Format GPIO state as a natural-language ChatMessage."""
        pins = _safe_get(data, "pins", {})
        device = _safe_get(data, "device", "unknown_device")
        timestamp = _safe_get(data, "timestamp", "")

        if not pins and not isinstance(pins, dict):
            raise ValueError("GPIOState has no pin data")

        # Classify pins by state
        high_pins: list[str] = []
        low_pins: list[str] = []
        other_pins: list[str] = []

        for pin, state in pins.items():
            if isinstance(state, bool):
                (high_pins if state else low_pins).append(str(pin))
            elif isinstance(state, (int, float)):
                (high_pins if state > 0 else low_pins).append(str(pin))
            else:
                other_pins.append(f"{pin}={state}")

        parts: list[str] = [f"GPIO state for device '{device}':"]

        if high_pins:
            parts.append(f"  HIGH: {', '.join(sorted(high_pins))}")
        if low_pins:
            parts.append(f"  LOW: {', '.join(sorted(low_pins))}")
        if other_pins:
            parts.append(f"  OTHER: {', '.join(sorted(other_pins))}")

        total = len(high_pins) + len(low_pins) + len(other_pins)
        parts.append(f"  Total pins reported: {total}")

        if timestamp:
            parts.append(f"Timestamp: {timestamp}")

        # Detect changes if previous state is provided
        previous = _safe_get(data, "previous_state", {})
        if previous:
            changed: list[str] = []
            for pin, state in pins.items():
                prev = previous.get(pin)
                if prev is not None and prev != state:
                    changed.append(f"{pin}: {prev} -> {state}")
            if changed:
                parts.append(f"  Changes: {', '.join(changed)}")

        role = config.get("role", "user")
        return {
            "role": role,
            "content": "\n".join(parts),
            "name": f"gpio_{device}",
        }


# ---------------------------------------------------------------------------
# Public list of all adapter classes
# ---------------------------------------------------------------------------

ALL_ADAPTERS: list[type[CrossDomainAdapter]] = [
    AIToCADAdapter,
    AIToElectronicsAdapter,
    CADToElectronicsAdapter,
    ElectronicsToHardwareAdapter,
    HardwareToAIAdapter,
]
