"""MIDI domain worker for mascarade node engine.

Handles MIDI message generation, sequence creation, CC mapping,
and real-time MIDI output for hardware integration.
"""

from __future__ import annotations

from .worker import MIDIWorker

MIDI_DOMAIN_TYPES = [
    "midi.note-sequence",
    "midi.cc-map",
    "midi.pattern-generate",
    "midi.transform",
]

__all__ = ["MIDI_DOMAIN_TYPES", "MIDIWorker"]
