"""CAD domain port types — registered by CADWorker during initialization."""

from __future__ import annotations

from mascarade.node_engine.types import DomainType

CAD_DOMAIN_TYPES = [
    DomainType(
        domain="cad",
        name="MeshData",
        schema={
            "type": "object",
            "properties": {
                "vertices": {
                    "type": "array",
                    "items": {
                        "type": "array",
                        "items": {"type": "number"},
                        "minItems": 3,
                        "maxItems": 3,
                    },
                },
                "faces": {
                    "type": "array",
                    "items": {
                        "type": "array",
                        "items": {"type": "integer"},
                        "minItems": 3,
                    },
                },
                "normals": {
                    "type": "array",
                    "items": {
                        "type": "array",
                        "items": {"type": "number"},
                        "minItems": 3,
                        "maxItems": 3,
                    },
                },
                "format": {
                    "type": "string",
                    "enum": ["stl", "obj", "ply", "step"],
                },
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
                "moves": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "x": {"type": "number"},
                            "y": {"type": "number"},
                            "z": {"type": "number"},
                            "feed_rate": {"type": "number"},
                            "type": {
                                "type": "string",
                                "enum": ["rapid", "linear", "arc_cw", "arc_ccw"],
                            },
                        },
                        "required": ["x", "y", "z", "type"],
                    },
                },
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
                "items": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "reference": {"type": "string"},
                            "value": {"type": "string"},
                            "footprint": {"type": "string"},
                            "quantity": {"type": "integer"},
                            "supplier": {"type": "string"},
                        },
                        "required": ["reference", "value", "quantity"],
                    },
                },
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
                "bounds": {
                    "type": "object",
                    "properties": {
                        "x": {"type": "number"},
                        "y": {"type": "number"},
                        "z": {"type": "number"},
                    },
                },
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
                "symbols": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "ref": {"type": "string"},
                            "value": {"type": "string"},
                            "lib": {"type": "string"},
                            "position": {"type": "object"},
                        },
                        "required": ["ref", "value"],
                    },
                },
                "nets": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "pins": {"type": "array", "items": {"type": "string"}},
                        },
                        "required": ["name", "pins"],
                    },
                },
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
                "components": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "ref": {"type": "string"},
                            "footprint": {"type": "string"},
                            "position": {"type": "object"},
                            "rotation": {"type": "number"},
                        },
                        "required": ["ref", "footprint"],
                    },
                },
                "traces": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "net": {"type": "string"},
                            "layer": {"type": "string"},
                            "points": {"type": "array"},
                            "width": {"type": "number"},
                        },
                        "required": ["net", "layer", "points", "width"],
                    },
                },
                "zones": {"type": "array"},
                "layers": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["components", "traces", "layers"],
        },
    ),
    DomainType(
        domain="cad",
        name="CADDocument",
        schema={
            "type": "object",
            "properties": {
                "document_id": {"type": "string"},
                "name": {"type": "string"},
                "objects": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "label": {"type": "string"},
                            "type": {"type": "string"},
                            "shape_type": {"type": "string"},
                        },
                    },
                },
                "parameters": {"type": "object"},
            },
            "required": ["document_id", "name", "objects"],
        },
    ),
    DomainType(
        domain="cad",
        name="ExportResult",
        schema={
            "type": "object",
            "properties": {
                "format": {"type": "string"},
                "file_path": {"type": "string"},
                "file_size_bytes": {"type": "integer"},
                "warnings": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["format", "file_path", "file_size_bytes"],
        },
    ),
]
