"""Tests for the MIDI domain worker."""

import pytest

from mascarade.node_engine.workers.midi import MIDI_DOMAIN_TYPES
from mascarade.node_engine.workers.midi.types import MIDICCMap, MIDINote, MIDISequence
from mascarade.node_engine.workers.midi.worker import SCALES, MIDIWorker


class TestMIDIWorkerCapabilities:
    def setup_method(self):
        self.worker = MIDIWorker()

    def test_capabilities_returns_4_types(self):
        caps = self.worker.capabilities()
        assert len(caps) == 4

    def test_capabilities_match_domain_types(self):
        caps = self.worker.capabilities()
        cap_types = {c["node_type"] for c in caps}
        assert cap_types == set(MIDI_DOMAIN_TYPES)

    def test_all_capabilities_have_description(self):
        for cap in self.worker.capabilities():
            assert cap.get("description")


class TestMIDINoteSequence:
    def setup_method(self):
        self.worker = MIDIWorker()

    @pytest.mark.asyncio
    async def test_create_simple_sequence(self):
        result = await self.worker.execute(
            "midi.note-sequence",
            {
                "notes": [{"note": 60}, {"note": 64}, {"note": 67}],
                "tempo": 120,
            },
            {},
        )
        seq = result["sequence"]
        assert seq["note_count"] == 3
        assert seq["tempo"] == 120
        assert seq["notes"][0]["note"] == 60
        assert seq["notes"][1]["note"] == 64

    @pytest.mark.asyncio
    async def test_create_sequence_from_ints(self):
        result = await self.worker.execute(
            "midi.note-sequence",
            {
                "notes": [60, 64, 67],
            },
            {},
        )
        assert result["sequence"]["note_count"] == 3
        assert result["sequence"]["notes"][0]["note"] == 60

    @pytest.mark.asyncio
    async def test_create_sequence_with_velocity(self):
        result = await self.worker.execute(
            "midi.note-sequence",
            {
                "notes": [{"note": 60, "velocity": 80, "duration": 1.0}],
            },
            {},
        )
        n = result["sequence"]["notes"][0]
        assert n["velocity"] == 80
        assert n["duration"] == 1.0

    def test_validate_sequence_missing_notes(self):
        errors = self.worker.validate("midi.note-sequence", {}, {})
        assert any("notes" in e for e in errors)

    def test_validate_sequence_invalid_notes(self):
        errors = self.worker.validate("midi.note-sequence", {"notes": "wrong"}, {})
        assert any("list" in e for e in errors)


class TestMIDICCMap:
    def setup_method(self):
        self.worker = MIDIWorker()

    @pytest.mark.asyncio
    async def test_create_cc_map(self):
        result = await self.worker.execute(
            "midi.cc-map",
            {
                "mappings": [
                    {"name": "volume", "controller": 7},
                    {"name": "pan", "controller": 10},
                ],
            },
            {},
        )
        cc = result["cc_map"]
        assert len(cc) == 2
        assert cc[0]["name"] == "volume"
        assert cc[0]["controller"] == 7
        assert cc[1]["name"] == "pan"

    def test_validate_cc_map_missing(self):
        errors = self.worker.validate("midi.cc-map", {}, {})
        assert any("mappings" in e for e in errors)


class TestMIDIPatternGenerate:
    def setup_method(self):
        self.worker = MIDIWorker()

    @pytest.mark.asyncio
    async def test_ascending_major(self):
        result = await self.worker.execute(
            "midi.pattern-generate",
            {
                "scale": "major",
                "root": 60,
                "steps": 8,
                "pattern": "ascending",
            },
            {},
        )
        seq = result["sequence"]
        assert seq["note_count"] == 8
        assert seq["notes"][0]["note"] == 60  # C
        assert seq["notes"][1]["note"] == 62  # D
        assert seq["notes"][2]["note"] == 64  # E

    @pytest.mark.asyncio
    async def test_descending(self):
        result = await self.worker.execute(
            "midi.pattern-generate",
            {
                "scale": "pentatonic",
                "root": 60,
                "steps": 5,
                "pattern": "descending",
            },
            {},
        )
        notes = result["sequence"]["notes"]
        assert notes[0]["note"] >= notes[-1]["note"]

    @pytest.mark.asyncio
    async def test_pendulum(self):
        result = await self.worker.execute(
            "midi.pattern-generate",
            {
                "scale": "minor",
                "root": 48,
                "steps": 4,
                "pattern": "pendulum",
            },
            {},
        )
        assert result["sequence"]["note_count"] > 4  # pendulum expands

    def test_validate_unknown_scale(self):
        errors = self.worker.validate("midi.pattern-generate", {"scale": "unknown"}, {})
        assert any("Unknown scale" in e for e in errors)

    def test_validate_root_out_of_range(self):
        errors = self.worker.validate("midi.pattern-generate", {"root": 200}, {})
        assert any("root" in e for e in errors)

    def test_all_scales_exist(self):
        for scale in [
            "major",
            "minor",
            "pentatonic",
            "blues",
            "chromatic",
            "dorian",
            "mixolydian",
        ]:
            assert scale in SCALES


class TestMIDITransform:
    def setup_method(self):
        self.worker = MIDIWorker()

    @pytest.mark.asyncio
    async def test_transpose(self):
        seq = {
            "notes": [
                {
                    "note": 60,
                    "velocity": 100,
                    "channel": 0,
                    "duration": 0.5,
                    "time": 0.0,
                }
            ],
            "tempo": 120,
        }
        result = await self.worker.execute(
            "midi.transform",
            {
                "sequence": seq,
                "transpose": 12,
            },
            {},
        )
        assert result["sequence"]["notes"][0]["note"] == 72

    @pytest.mark.asyncio
    async def test_velocity_scale(self):
        seq = {
            "notes": [
                {
                    "note": 60,
                    "velocity": 100,
                    "channel": 0,
                    "duration": 0.5,
                    "time": 0.0,
                }
            ]
        }
        result = await self.worker.execute(
            "midi.transform",
            {
                "sequence": seq,
                "velocity_scale": 0.5,
            },
            {},
        )
        assert result["sequence"]["notes"][0]["velocity"] == 50

    @pytest.mark.asyncio
    async def test_time_stretch(self):
        seq = {
            "notes": [
                {
                    "note": 60,
                    "velocity": 100,
                    "channel": 0,
                    "duration": 0.5,
                    "time": 1.0,
                }
            ]
        }
        result = await self.worker.execute(
            "midi.transform",
            {
                "sequence": seq,
                "time_scale": 2.0,
            },
            {},
        )
        assert result["sequence"]["notes"][0]["duration"] == 1.0
        assert result["sequence"]["notes"][0]["time"] == 2.0

    @pytest.mark.asyncio
    async def test_clamp_note_range(self):
        seq = {
            "notes": [
                {
                    "note": 120,
                    "velocity": 100,
                    "channel": 0,
                    "duration": 0.5,
                    "time": 0.0,
                }
            ]
        }
        result = await self.worker.execute(
            "midi.transform",
            {
                "sequence": seq,
                "transpose": 20,
            },
            {},
        )
        assert result["sequence"]["notes"][0]["note"] == 127  # clamped

    def test_validate_missing_sequence(self):
        errors = self.worker.validate("midi.transform", {}, {})
        assert any("sequence" in e for e in errors)


class TestMIDITypes:
    def test_midi_note_defaults(self):
        note = MIDINote(note=60)
        assert note.velocity == 100
        assert note.channel == 0
        assert note.duration == 0.5

    def test_midi_sequence(self):
        seq = MIDISequence(notes=[MIDINote(60), MIDINote(64)], tempo=140)
        assert len(seq.notes) == 2
        assert seq.tempo == 140

    def test_midi_cc_map(self):
        cc = MIDICCMap(name="filter", controller=74)
        assert cc.default_value == 64
        assert cc.min_value == 0
        assert cc.max_value == 127
