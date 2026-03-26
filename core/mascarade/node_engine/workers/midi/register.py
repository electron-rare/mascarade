"""Register the MIDI worker with the node engine."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mascarade.node_engine.engine import NodeEngine
    from mascarade.router import Router


def register_midi_worker(engine: NodeEngine, router: Router | None = None) -> None:
    """Register MIDIWorker for all midi.* node types."""
    from . import MIDI_DOMAIN_TYPES
    from .worker import MIDIWorker

    worker = MIDIWorker(router=router)
    for node_type in MIDI_DOMAIN_TYPES:
        engine.register_worker(node_type, worker)
