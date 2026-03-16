"""FreeCAD node worker — registers FreeCAD nodes with the Node Engine."""

from __future__ import annotations

from mascarade.node_engine.worker import NodeWorker, WorkerCapabilities


class FreeCADWorker(NodeWorker):
    """Worker for FreeCAD CAD operations.

    Provides graph-composable nodes for FreeCAD document creation, script execution,
    parametric modeling, and export operations. Integrates with the existing FreeCADAgent
    and api/src/routes/cad.ts endpoints.
    """

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
