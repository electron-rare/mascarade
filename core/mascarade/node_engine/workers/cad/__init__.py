"""CAD worker for FreeCAD, KiCad, toolpath, and mesh operations."""

from mascarade.node_engine.registry import NodeTypeRegistry
from mascarade.node_engine.types import DomainType

# CAD domain types as defined in SPEC-029-P2 section 2.1
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

# Global registry instance for module-level registration
_global_registry: NodeTypeRegistry | None = None


def register_cad_types(registry: NodeTypeRegistry | None = None) -> None:
    """Register CAD domain types with the NodeTypeRegistry."""
    global _global_registry

    # Use provided registry or create/reuse global one
    if registry is None:
        if _global_registry is None:
            _global_registry = NodeTypeRegistry()
        registry = _global_registry

    # Register all CAD domain types as builtin
    for domain_type in CAD_DOMAIN_TYPES:
        registry.register_domain_type(domain_type, builtin=True)


def register_cad_workers(registry: NodeTypeRegistry) -> None:
    """Register all CAD workers and their node types with the NodeTypeRegistry.

    This function registers:
    - All 8 CAD domain types (MeshData, Toolpath, BOM, GCode, etc.)
    - All 15 CAD node types from 4 workers:
      * FreeCADWorker: 4 nodes (create_document, run_script, parametric_model, export)
      * KiCadWorker: 5 nodes (generate_schematic, optimize_layout, create_footprint, check_drc, export_manufacturing)
      * ToolpathWorker: 2 nodes (generate_gcode, optimize)
      * MeshWorker: 4 nodes (import, export, simplify, boolean)

    Args:
        registry: The NodeTypeRegistry to register with
    """
    from mascarade.node_engine.types import NodeType, PortType
    from mascarade.node_engine.workers.cad.freecad_worker import FreeCADWorker
    from mascarade.node_engine.workers.cad.kicad_worker import KiCadWorker
    from mascarade.node_engine.workers.cad.mesh_worker import MeshWorker
    from mascarade.node_engine.workers.cad.toolpath_worker import ToolpathWorker

    # First register CAD domain types
    register_cad_types(registry)

    # FreeCAD nodes
    freecad_nodes = [
        NodeType(
            id="cad.freecad.create_document",
            category="CAD / FreeCAD",
            inputs=[
                PortType(name="name", type="string", required=True),
                PortType(name="parameters", type="map<string, number>", required=False),
            ],
            outputs=[
                PortType(name="document", type="cad.CADDocument", required=True),
            ],
        ),
        NodeType(
            id="cad.freecad.run_script",
            category="CAD / FreeCAD",
            inputs=[
                PortType(name="document", type="cad.CADDocument", required=True),
                PortType(name="script", type="string", required=True),
                PortType(name="timeout_s", type="number", required=False),
            ],
            outputs=[
                PortType(name="document", type="cad.CADDocument", required=True),
                PortType(name="result", type="json", required=True),
                PortType(name="logs", type="string", required=True),
            ],
        ),
        NodeType(
            id="cad.freecad.parametric_model",
            category="CAD / FreeCAD",
            inputs=[
                PortType(name="template", type="string", required=True),
                PortType(name="parameters", type="map<string, number>", required=True),
                PortType(name="description", type="string", required=False),
            ],
            outputs=[
                PortType(name="document", type="cad.CADDocument", required=True),
                PortType(name="mesh", type="cad.MeshData", required=True),
            ],
        ),
        NodeType(
            id="cad.freecad.export",
            category="CAD / FreeCAD",
            inputs=[
                PortType(name="document", type="cad.CADDocument", required=True),
                PortType(name="format", type="string", required=True),
                PortType(name="options", type="json", required=False),
            ],
            outputs=[
                PortType(name="result", type="cad.ExportResult", required=True),
                PortType(name="mesh", type="cad.MeshData", required=False),
            ],
        ),
    ]

    # KiCad nodes
    kicad_nodes = [
        NodeType(
            id="cad.kicad.generate_schematic",
            category="CAD / KiCad",
            inputs=[
                PortType(name="requirements", type="string", required=True),
                PortType(name="library", type="string", required=False),
            ],
            outputs=[
                PortType(name="schematic", type="cad.SchematicData", required=True),
                PortType(name="bom", type="cad.BOM", required=True),
            ],
        ),
        NodeType(
            id="cad.kicad.optimize_layout",
            category="CAD / KiCad",
            inputs=[
                PortType(name="schematic", type="cad.SchematicData", required=True),
                PortType(name="constraints", type="json", required=True),
                PortType(name="board_outline", type="cad.MeshData", required=False),
            ],
            outputs=[
                PortType(name="layout", type="cad.PCBLayout", required=True),
                PortType(name="report", type="string", required=True),
            ],
        ),
        NodeType(
            id="cad.kicad.create_footprint",
            category="CAD / KiCad",
            inputs=[
                PortType(name="component_description", type="string", required=True),
                PortType(name="datasheet_url", type="string", required=False),
            ],
            outputs=[
                PortType(name="footprint", type="json", required=True),
                PortType(name="preview_mesh", type="cad.MeshData", required=False),
            ],
        ),
        NodeType(
            id="cad.kicad.check_drc",
            category="CAD / KiCad",
            inputs=[
                PortType(name="layout", type="cad.PCBLayout", required=True),
                PortType(name="rules", type="json", required=True),
            ],
            outputs=[
                PortType(name="passed", type="boolean", required=True),
                PortType(name="violations", type="array<json>", required=True),
                PortType(name="report", type="string", required=True),
            ],
        ),
        NodeType(
            id="cad.kicad.export_manufacturing",
            category="CAD / KiCad",
            inputs=[
                PortType(name="layout", type="cad.PCBLayout", required=True),
                PortType(name="bom", type="cad.BOM", required=False),
                PortType(name="format", type="string", required=False),
            ],
            outputs=[
                PortType(name="gerbers", type="json", required=True),
                PortType(name="drill_files", type="json", required=True),
                PortType(name="bom", type="cad.BOM", required=True),
                PortType(name="pick_and_place", type="json", required=True),
                PortType(name="report", type="string", required=True),
            ],
        ),
    ]

    # Toolpath nodes
    toolpath_nodes = [
        NodeType(
            id="cad.toolpath.generate_gcode",
            category="CAD / Toolpath",
            inputs=[
                PortType(name="mesh", type="cad.MeshData", required=True),
                PortType(name="tool", type="json", required=True),
                PortType(name="strategy", type="string", required=True),
                PortType(name="stock", type="json", required=False),
            ],
            outputs=[
                PortType(name="gcode", type="cad.GCode", required=True),
                PortType(name="toolpath", type="cad.Toolpath", required=True),
            ],
        ),
        NodeType(
            id="cad.toolpath.optimize",
            category="CAD / Toolpath",
            inputs=[
                PortType(name="toolpath", type="cad.Toolpath", required=True),
                PortType(name="objective", type="string", required=True),
                PortType(name="constraints", type="json", required=False),
            ],
            outputs=[
                PortType(name="toolpath", type="cad.Toolpath", required=True),
                PortType(name="gcode", type="cad.GCode", required=True),
                PortType(name="improvement_pct", type="number", required=True),
            ],
        ),
    ]

    # Mesh nodes
    mesh_nodes = [
        NodeType(
            id="cad.mesh.import",
            category="CAD / Mesh",
            inputs=[
                PortType(name="data", type="binary", required=True),
                PortType(name="format", type="string", required=True),
            ],
            outputs=[
                PortType(name="mesh", type="cad.MeshData", required=True),
                PortType(name="stats", type="json", required=True),
            ],
        ),
        NodeType(
            id="cad.mesh.export",
            category="CAD / Mesh",
            inputs=[
                PortType(name="mesh", type="cad.MeshData", required=True),
                PortType(name="format", type="string", required=True),
                PortType(name="options", type="json", required=False),
            ],
            outputs=[
                PortType(name="data", type="binary", required=True),
                PortType(name="result", type="cad.ExportResult", required=True),
            ],
        ),
        NodeType(
            id="cad.mesh.simplify",
            category="CAD / Mesh",
            inputs=[
                PortType(name="mesh", type="cad.MeshData", required=True),
                PortType(name="target_ratio", type="number", required=True),
                PortType(name="preserve_boundaries", type="boolean", required=False),
            ],
            outputs=[
                PortType(name="mesh", type="cad.MeshData", required=True),
                PortType(name="reduction_pct", type="number", required=True),
            ],
        ),
        NodeType(
            id="cad.mesh.boolean",
            category="CAD / Mesh",
            inputs=[
                PortType(name="mesh_a", type="cad.MeshData", required=True),
                PortType(name="mesh_b", type="cad.MeshData", required=True),
                PortType(name="operation", type="string", required=True),
            ],
            outputs=[
                PortType(name="mesh", type="cad.MeshData", required=True),
            ],
        ),
    ]

    # Register all node types as builtin
    all_nodes = freecad_nodes + kicad_nodes + toolpath_nodes + mesh_nodes
    for node_type in all_nodes:
        registry.register_node(node_type, builtin=True)


__all__ = ["CAD_DOMAIN_TYPES", "register_cad_types", "register_cad_workers"]
