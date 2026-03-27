"""Register the hardware worker with the node engine."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mascarade.node_engine.engine import NodeEngine
    from mascarade.router import Router


def register_hardware_worker(engine: NodeEngine, router: Router | None = None) -> None:
    """Register HardwareWorker for all hardware.* node types."""
    from . import HARDWARE_DOMAIN_TYPES
    from .worker import HardwareWorker

    worker = HardwareWorker(router=router)
    for node_type in HARDWARE_DOMAIN_TYPES:
        engine.register_worker(node_type, worker)
