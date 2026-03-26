"""MIDI domain types for the node engine."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class MIDINote:
    """A single MIDI note event."""

    note: int  # 0-127
    velocity: int = 100  # 0-127
    channel: int = 0  # 0-15
    duration: float = 0.5  # seconds
    time: float = 0.0  # offset in seconds


@dataclass
class MIDISequence:
    """A sequence of MIDI notes."""

    notes: list[MIDINote] = field(default_factory=list)
    tempo: int = 120  # BPM
    name: str = ""


@dataclass
class MIDIControlChange:
    """A MIDI control change message."""

    controller: int  # 0-127
    value: int  # 0-127
    channel: int = 0


@dataclass
class MIDICCMap:
    """Maps a parameter name to a MIDI CC."""

    name: str
    controller: int  # CC number 0-127
    channel: int = 0
    min_value: int = 0
    max_value: int = 127
    default_value: int = 64
