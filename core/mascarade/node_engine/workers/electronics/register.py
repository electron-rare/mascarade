"""Register the Electronics worker with the node engine."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mascarade.node_engine.engine import NodeEngine


def register_electronics_worker(engine: NodeEngine) -> None:
    """Register ElectronicsWorker for all electronics.* node types."""
    from . import ELECTRONICS_DOMAIN_TYPES
    from .worker import ElectronicsWorker

    worker = ElectronicsWorker()
    for node_type in ELECTRONICS_DOMAIN_TYPES:
        engine.register_worker(node_type, worker)
