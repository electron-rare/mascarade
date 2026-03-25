"""Tests for mascarade.voice_pipeline — VAD filter, pipeline, result dataclass."""

from __future__ import annotations

import struct
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mascarade.voice_pipeline import (
    VoicePipeline,
    VoicePipelineResult,
    _rms_energy,
    vad_filter,
)

# ---------------------------------------------------------------------------
# VoicePipelineResult dataclass
# ---------------------------------------------------------------------------


class TestVoicePipelineResult:
    def test_defaults(self):
        r = VoicePipelineResult()
        assert r.ok is True
        assert r.transcript == ""
        assert r.llm_reply == ""
        assert r.audio_response == b""
        assert r.audio_content_type == "audio/wav"
        assert r.error is None
        assert r.timings_ms == {}

    def test_error_result(self):
        r = VoicePipelineResult(ok=False, error="asr_error: timeout")
        assert r.ok is False
        assert r.error == "asr_error: timeout"

    def test_full_result(self):
        r = VoicePipelineResult(
            ok=True,
            transcript="bonjour",
            llm_reply="salut",
            audio_response=b"\x00\x01",
            timings_ms={"asr_ms": 100, "llm_ms": 200},
        )
        assert r.transcript == "bonjour"
        assert r.timings_ms["asr_ms"] == 100


# ---------------------------------------------------------------------------
# VAD helpers
# ---------------------------------------------------------------------------


class TestRmsEnergy:
    def test_silence(self):
        """All-zero samples should have zero energy."""
        frame = b"\x00\x00" * 320
        assert _rms_energy(frame) == 0.0

    def test_empty(self):
        assert _rms_energy(b"") == 0.0

    def test_loud_signal(self):
        """A frame full of max-amplitude samples should have high energy."""
        frame = struct.pack("<320h", *([32767] * 320))
        energy = _rms_energy(frame)
        assert energy > 30000

    def test_known_value(self):
        """Single value repeated: RMS should equal the absolute value."""
        val = 1000
        frame = struct.pack("<320h", *([val] * 320))
        energy = _rms_energy(frame)
        assert abs(energy - val) < 1.0


class TestVadFilter:
    def _make_silent_frame(self) -> bytes:
        return b"\x00\x00" * 320

    def _make_voiced_frame(self, amplitude: int = 1000) -> bytes:
        return struct.pack("<320h", *([amplitude] * 320))

    def test_all_silence_returns_original(self):
        """When no voiced frames are found, original audio is returned."""
        audio = self._make_silent_frame() * 10
        result = vad_filter(audio, threshold=300, min_voiced_frames=3)
        assert result == audio

    def test_all_voiced(self):
        """All frames above threshold should be kept."""
        audio = self._make_voiced_frame(1000) * 5
        result = vad_filter(audio, threshold=300, min_voiced_frames=3)
        assert result == audio

    def test_strips_silence(self):
        """Should strip silence and keep only voiced frames."""
        silent = self._make_silent_frame()
        voiced = self._make_voiced_frame(1000)
        audio = silent * 5 + voiced * 4 + silent * 5
        result = vad_filter(audio, threshold=300, min_voiced_frames=3)
        assert result == voiced * 4

    def test_too_few_voiced_returns_original(self):
        """Below min_voiced_frames threshold, original audio is returned."""
        silent = self._make_silent_frame()
        voiced = self._make_voiced_frame(1000)
        audio = silent * 10 + voiced * 2  # only 2 voiced frames
        result = vad_filter(audio, threshold=300, min_voiced_frames=3)
        assert result == audio

    def test_custom_threshold(self):
        """With a very high threshold, all frames are 'silent'."""
        voiced = self._make_voiced_frame(500)
        audio = voiced * 10
        result = vad_filter(audio, threshold=50000, min_voiced_frames=3)
        assert result == audio  # returned as-is because no voiced frames detected


# ---------------------------------------------------------------------------
# VoicePipeline (mocked external calls)
# ---------------------------------------------------------------------------


class TestVoicePipeline:
    @pytest.fixture()
    def mock_router(self):
        router = MagicMock()
        response = MagicMock()
        response.content = " Bienvenue, aventurier ! "
        router.send = AsyncMock(return_value=response)
        return router

    @pytest.mark.asyncio
    async def test_full_pipeline_pcm(self, mock_router):
        """Full pipeline with PCM input, mocked ASR and TTS."""
        pipe = VoicePipeline(router=mock_router)

        # Build a short PCM audio with some voiced frames
        voiced = struct.pack("<320h", *([1000] * 320))
        pcm_audio = voiced * 5

        with (
            patch.object(pipe, "_transcribe", new_callable=AsyncMock) as mock_asr,
            patch.object(pipe, "_synthesize", new_callable=AsyncMock) as mock_tts,
        ):
            mock_asr.return_value = "qui est la"
            mock_tts.return_value = b"\x00wav_data"

            result = await pipe.process(pcm_audio, content_type="audio/pcm")

        assert result.ok is True
        assert result.transcript == "qui est la"
        assert result.llm_reply == "Bienvenue, aventurier !"
        assert result.audio_response == b"\x00wav_data"
        assert "llm_ms" in result.timings_ms

    @pytest.mark.asyncio
    async def test_empty_transcript(self, mock_router):
        """When ASR returns empty text, pipeline stops early."""
        pipe = VoicePipeline(router=mock_router)

        with patch.object(pipe, "_transcribe", new_callable=AsyncMock) as mock_asr:
            mock_asr.return_value = "   "
            result = await pipe.process(b"\x00" * 100, content_type="audio/pcm")

        assert result.ok is True
        assert result.error == "empty_transcript"
        assert result.llm_reply == ""

    @pytest.mark.asyncio
    async def test_asr_failure(self, mock_router):
        """ASR error should be reported in result."""
        pipe = VoicePipeline(router=mock_router)

        with patch.object(pipe, "_transcribe", new_callable=AsyncMock) as mock_asr:
            mock_asr.side_effect = RuntimeError("API key not configured")
            result = await pipe.process(b"\x00" * 100, content_type="audio/pcm")

        assert result.ok is False
        assert "asr_error" in result.error

    @pytest.mark.asyncio
    async def test_llm_failure(self, mock_router):
        """LLM error after successful ASR."""
        mock_router.send.side_effect = RuntimeError("provider down")
        pipe = VoicePipeline(router=mock_router)

        with patch.object(pipe, "_transcribe", new_callable=AsyncMock) as mock_asr:
            mock_asr.return_value = "bonjour"
            result = await pipe.process(b"\x00" * 100, content_type="audio/pcm")

        assert result.ok is False
        assert "llm_error" in result.error
        assert result.transcript == "bonjour"

    @pytest.mark.asyncio
    async def test_tts_failure(self, mock_router):
        """TTS error after successful ASR + LLM."""
        pipe = VoicePipeline(router=mock_router)

        with (
            patch.object(pipe, "_transcribe", new_callable=AsyncMock) as mock_asr,
            patch.object(pipe, "_synthesize", new_callable=AsyncMock) as mock_tts,
        ):
            mock_asr.return_value = "bonjour"
            mock_tts.side_effect = RuntimeError("TTS timeout")
            result = await pipe.process(b"\x00" * 100, content_type="audio/pcm")

        assert result.ok is False
        assert "tts_error" in result.error
        assert result.transcript == "bonjour"
        assert result.llm_reply == "Bienvenue, aventurier !"

    @pytest.mark.asyncio
    async def test_custom_system_prompt(self):
        """Custom system prompt is passed to router."""
        router = MagicMock()
        response = MagicMock()
        response.content = "ok"
        router.send = AsyncMock(return_value=response)

        pipe = VoicePipeline(router=router, system_prompt="You are a pirate.")

        with (
            patch.object(pipe, "_transcribe", new_callable=AsyncMock, return_value="hi"),
            patch.object(pipe, "_synthesize", new_callable=AsyncMock, return_value=b"wav"),
        ):
            await pipe.process(b"\x00" * 100, content_type="audio/pcm")

        call_kwargs = router.send.call_args
        assert call_kwargs.kwargs.get("system") == "You are a pirate."
