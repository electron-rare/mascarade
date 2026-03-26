"""MIDI domain worker for mascarade node engine.

Handles MIDI note sequences, CC mapping, pattern generation,
and MIDI transformation nodes.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from mascarade.node_engine.worker import NodeWorker

from .types import MIDICCMap, MIDINote, MIDISequence

if TYPE_CHECKING:
    from mascarade.router import Router

logger = logging.getLogger(__name__)

# Common scales for pattern generation
SCALES = {
    "major": [0, 2, 4, 5, 7, 9, 11],
    "minor": [0, 2, 3, 5, 7, 8, 10],
    "pentatonic": [0, 2, 4, 7, 9],
    "blues": [0, 3, 5, 6, 7, 10],
    "chromatic": list(range(12)),
    "dorian": [0, 2, 3, 5, 7, 9, 10],
    "mixolydian": [0, 2, 4, 5, 7, 9, 10],
}


class MIDIWorker(NodeWorker):
    """Worker for MIDI domain node types."""

    def __init__(self, router: Router | None = None):
        self.router = router

    def capabilities(self) -> list[dict[str, Any]]:
        return [
            {
                "node_type": "midi.note-sequence",
                "description": "Create a MIDI note sequence from parameters",
                "inputs": {
                    "notes": "list of {note, velocity, duration, time}",
                    "tempo": "int BPM",
                },
                "outputs": {"sequence": "MIDISequence"},
            },
            {
                "node_type": "midi.cc-map",
                "description": "Create MIDI CC mapping for hardware control",
                "inputs": {"mappings": "list of {name, controller, channel}"},
                "outputs": {"cc_map": "list of MIDICCMap"},
            },
            {
                "node_type": "midi.pattern-generate",
                "description": "Generate a MIDI pattern from scale, rhythm and parameters",
                "inputs": {
                    "scale": "str",
                    "root": "int",
                    "octave": "int",
                    "steps": "int",
                    "pattern": "str",
                },
                "outputs": {"sequence": "MIDISequence"},
            },
            {
                "node_type": "midi.transform",
                "description": "Transform a MIDI sequence (transpose, velocity scale, time stretch)",
                "inputs": {
                    "sequence": "MIDISequence",
                    "transpose": "int",
                    "velocity_scale": "float",
                    "time_scale": "float",
                },
                "outputs": {"sequence": "MIDISequence"},
            },
        ]

    async def execute(
        self,
        node_type: str,
        inputs: dict[str, Any],
        config: dict[str, Any],
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if node_type == "midi.note-sequence":
            return self._create_sequence(inputs, config)
        elif node_type == "midi.cc-map":
            return self._create_cc_map(inputs, config)
        elif node_type == "midi.pattern-generate":
            return self._generate_pattern(inputs, config)
        elif node_type == "midi.transform":
            return self._transform_sequence(inputs, config)
        else:
            raise ValueError(f"Unsupported MIDI node type: {node_type}")

    def validate(
        self, node_type: str, inputs: dict[str, Any], config: dict[str, Any]
    ) -> list[str]:
        errors = []
        if node_type == "midi.note-sequence":
            if "notes" not in inputs:
                errors.append("notes is required")
            elif not isinstance(inputs["notes"], list):
                errors.append("notes must be a list")
        elif node_type == "midi.cc-map":
            if "mappings" not in inputs:
                errors.append("mappings is required")
        elif node_type == "midi.pattern-generate":
            scale = inputs.get("scale", "major")
            if scale not in SCALES:
                errors.append(
                    f"Unknown scale: {scale}. Available: {', '.join(SCALES.keys())}"
                )
            root = inputs.get("root", 60)
            if not isinstance(root, int) or root < 0 or root > 127:
                errors.append("root must be 0-127")
        elif node_type == "midi.transform":
            if "sequence" not in inputs:
                errors.append("sequence is required")
        return errors

    def _create_sequence(self, inputs: dict, config: dict) -> dict:
        notes_data = inputs.get("notes", [])
        tempo = inputs.get("tempo", 120)
        name = inputs.get("name", "sequence")

        notes = []
        for n in notes_data:
            if isinstance(n, dict):
                notes.append(
                    MIDINote(
                        note=n.get("note", 60),
                        velocity=n.get("velocity", 100),
                        channel=n.get("channel", 0),
                        duration=n.get("duration", 0.5),
                        time=n.get("time", 0.0),
                    )
                )
            elif isinstance(n, (int, float)):
                notes.append(MIDINote(note=int(n)))

        seq = MIDISequence(notes=notes, tempo=tempo, name=name)
        return {
            "sequence": {
                "name": seq.name,
                "tempo": seq.tempo,
                "note_count": len(seq.notes),
                "notes": [
                    {
                        "note": n.note,
                        "velocity": n.velocity,
                        "channel": n.channel,
                        "duration": n.duration,
                        "time": n.time,
                    }
                    for n in seq.notes
                ],
            }
        }

    def _create_cc_map(self, inputs: dict, config: dict) -> dict:
        mappings_data = inputs.get("mappings", [])
        cc_maps = []
        for m in mappings_data:
            cc_maps.append(
                MIDICCMap(
                    name=m.get("name", "param"),
                    controller=m.get("controller", 1),
                    channel=m.get("channel", 0),
                    min_value=m.get("min", 0),
                    max_value=m.get("max", 127),
                    default_value=m.get("default", 64),
                )
            )
        return {
            "cc_map": [
                {
                    "name": c.name,
                    "controller": c.controller,
                    "channel": c.channel,
                    "min": c.min_value,
                    "max": c.max_value,
                    "default": c.default_value,
                }
                for c in cc_maps
            ]
        }

    def _generate_pattern(self, inputs: dict, config: dict) -> dict:
        scale_name = inputs.get("scale", "major")
        root = inputs.get("root", 60)
        octave = inputs.get("octave", 0)
        steps = inputs.get("steps", 8)
        pattern_type = inputs.get("pattern", "ascending")
        tempo = inputs.get("tempo", 120)
        duration = inputs.get("duration", 0.25)
        velocity = inputs.get("velocity", 100)

        scale = SCALES.get(scale_name, SCALES["major"])
        base_note = root + (octave * 12)

        # Generate note indices based on pattern
        if pattern_type == "ascending":
            indices = list(range(steps))
        elif pattern_type == "descending":
            indices = list(range(steps - 1, -1, -1))
        elif pattern_type == "pendulum":
            indices = list(range(steps)) + list(range(steps - 2, 0, -1))
        elif pattern_type == "random":
            import random

            indices = [random.randint(0, steps - 1) for _ in range(steps)]
        elif pattern_type == "arpeggio":
            indices = [0, 2, 4, 7] * (steps // 4 + 1)
            indices = indices[:steps]
        else:
            indices = list(range(steps))

        notes = []
        beat_duration = 60.0 / tempo
        for i, idx in enumerate(indices):
            scale_idx = idx % len(scale)
            octave_offset = idx // len(scale) * 12
            note_num = min(127, max(0, base_note + scale[scale_idx] + octave_offset))
            notes.append(
                MIDINote(
                    note=note_num,
                    velocity=velocity,
                    duration=duration,
                    time=i * beat_duration * duration * 4,
                )
            )

        seq = MIDISequence(
            notes=notes, tempo=tempo, name=f"{scale_name}_{pattern_type}"
        )
        return {
            "sequence": {
                "name": seq.name,
                "tempo": seq.tempo,
                "note_count": len(seq.notes),
                "notes": [
                    {
                        "note": n.note,
                        "velocity": n.velocity,
                        "channel": n.channel,
                        "duration": n.duration,
                        "time": n.time,
                    }
                    for n in seq.notes
                ],
            }
        }

    def _transform_sequence(self, inputs: dict, config: dict) -> dict:
        seq_data = inputs.get("sequence", {})
        transpose = inputs.get("transpose", 0)
        velocity_scale = inputs.get("velocity_scale", 1.0)
        time_scale = inputs.get("time_scale", 1.0)

        notes = []
        for n in seq_data.get("notes", []):
            new_note = min(127, max(0, n.get("note", 60) + transpose))
            new_vel = min(127, max(0, int(n.get("velocity", 100) * velocity_scale)))
            notes.append(
                {
                    "note": new_note,
                    "velocity": new_vel,
                    "channel": n.get("channel", 0),
                    "duration": n.get("duration", 0.5) * time_scale,
                    "time": n.get("time", 0.0) * time_scale,
                }
            )

        return {
            "sequence": {
                "name": seq_data.get("name", "transformed"),
                "tempo": seq_data.get("tempo", 120),
                "note_count": len(notes),
                "notes": notes,
            }
        }
