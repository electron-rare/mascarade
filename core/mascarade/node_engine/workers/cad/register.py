"""Register the CAD worker with the node engine."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mascarade.node_engine.engine import NodeEngine


def register_cad_worker(engine: NodeEngine) -> None:
    """Register CADWorker for all cad.* node types."""
    from . import CAD_DOMAIN_TYPES
    from .worker import CADWorker

    worker = CADWorker()
    for node_type in CAD_DOMAIN_TYPES:
        engine.register_worker(node_type, worker)
