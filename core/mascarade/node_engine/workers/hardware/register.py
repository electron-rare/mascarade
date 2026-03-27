"""Register the hardware worker with the node engine.

Supports both the legacy NodeEngine (register_hardware_worker_legacy) and
the GraphRuntime (register_hardware_worker).
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mascarade.node_engine.engine import NodeEngine
    from mascarade.node_engine.runtime import GraphRuntime
    from mascarade.router import Router

from mascarade.node_engine.workers.hardware.worker import HardwareWorker

logger = logging.getLogger("mascarade.node_engine.workers.hardware")


def register_hardware_worker(
    runtime: GraphRuntime,
    router: Router | None = None,
) -> HardwareWorker:
    """Register HardwareWorker with GraphRuntime.

    Creates and registers a HardwareWorker instance that handles all
    hardware.* and hardware.midi.* node types (ESP32, DMX, serial, MIDI).

    Args:
        runtime: GraphRuntime instance to register the worker with
        router: Optional Router instance for hardware-AI integration

    Returns:
        HardwareWorker: The registered HardwareWorker instance
    """
    worker = HardwareWorker(router=router)
    runtime.register_worker(worker)

    logger.info(
        "Registered Hardware Worker with GraphRuntime (esp32, dmx, serial, midi, safety)"
    )

    return worker


def register_hardware_worker_legacy(
    engine: NodeEngine, router: Router | None = None
) -> None:
    """Register HardwareWorker for all hardware.* node types (legacy NodeEngine API)."""
    from . import HARDWARE_DOMAIN_TYPES

    worker = HardwareWorker(router=router)
    for node_type in HARDWARE_DOMAIN_TYPES:
        engine.register_worker(node_type, worker)
