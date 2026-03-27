"""Register the CAD worker with the node engine.

Supports both the legacy NodeEngine (register_cad_worker_legacy) and
the GraphRuntime (register_cad_worker).
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mascarade.node_engine.engine import NodeEngine
    from mascarade.node_engine.runtime import GraphRuntime

from mascarade.node_engine.workers.cad.worker import CADWorker

logger = logging.getLogger("mascarade.node_engine.workers.cad")


def register_cad_worker(runtime: GraphRuntime) -> CADWorker:
    """Register CADWorker with GraphRuntime.

    Creates and registers a CADWorker instance that handles all cad.* node
    types including mesh, toolpath, FreeCAD, and KiCad sub-workers.

    Args:
        runtime: GraphRuntime instance to register the worker with

    Returns:
        CADWorker: The registered CADWorker instance

    Example:
        >>> from mascarade.node_engine.runtime import GraphRuntime
        >>> from mascarade.node_engine.workers.cad.register import register_cad_worker
        >>>
        >>> runtime = GraphRuntime()
        >>> cad_worker = register_cad_worker(runtime)
        >>>
        >>> # Runtime can now execute cad.mesh.*, cad.toolpath.*, etc.
        >>> workers = runtime.list_workers()
    """
    cad_worker = CADWorker()
    runtime.register_worker(cad_worker)

    logger.info(
        "Registered CAD Worker with GraphRuntime (sub-workers: mesh, toolpath, freecad, kicad)"
    )

    return cad_worker


def register_cad_worker_legacy(engine: NodeEngine) -> None:
    """Register CADWorker for all cad.* node types (legacy NodeEngine API)."""
    from . import CAD_DOMAIN_TYPES

    worker = CADWorker()
    for node_type in CAD_DOMAIN_TYPES:
        engine.register_worker(node_type, worker)
