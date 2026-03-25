"""Electronics domain port types for the Universal Node Engine."""

from __future__ import annotations

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
            "signals": {
                "type": "object",
                "additionalProperties": {"type": "array", "items": {"type": "number"}},
            },
            "time_axis": {"type": "array", "items": {"type": "number"}},
            "units": {"type": "object", "additionalProperties": {"type": "string"}},
            "analysis_type": {
                "type": "string",
                "enum": ["transient", "ac", "dc", "noise", "op"],
            },
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
            "framework": {
                "type": "string",
                "enum": ["esp-idf", "platformio", "arduino"],
            },
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

DRC_REPORT_TYPE = DomainType(
    domain="electronics",
    name="DRCReport",
    schema={
        "type": "object",
        "properties": {
            "passed": {"type": "boolean"},
            "violations": {"type": "array", "items": {"type": "object"}},
            "rules_checked": {"type": "integer"},
            "board_file": {"type": "string"},
        },
        "required": ["passed", "violations", "rules_checked", "board_file"],
    },
)

ELECTRONICS_DOMAIN_TYPES = [
    NETLIST_TYPE,
    SCHEMATIC_TYPE,
    WAVEFORM_TYPE,
    FIRMWARE_BINARY_TYPE,
    COMPONENT_SPEC_TYPE,
    DRC_REPORT_TYPE,
]

__all__ = [
    "ELECTRONICS_DOMAIN_TYPES",
    "NETLIST_TYPE",
    "SCHEMATIC_TYPE",
    "WAVEFORM_TYPE",
    "FIRMWARE_BINARY_TYPE",
    "COMPONENT_SPEC_TYPE",
    "DRC_REPORT_TYPE",
]
