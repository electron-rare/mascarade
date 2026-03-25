"""Voice pipeline: OPUS audio -> VAD -> ASR -> LLM -> TTS -> audio response.

Receives raw audio (OPUS or PCM), detects speech segments via energy-based
VAD, transcribes with OpenAI Whisper, routes through the Mascarade LLM
router, and synthesises a spoken reply via OpenAI TTS.
"""

from __future__ import annotations

import logging
import struct
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import httpx

from mascarade.config import is_secret_configured, secret_value, settings

if TYPE_CHECKING:
    from mascarade.router.router import Router

logger = logging.getLogger("mascarade.voice_pipeline")

# ---------------------------------------------------------------------------
# Configuration defaults
# ---------------------------------------------------------------------------

# VAD: energy threshold (RMS of 16-bit PCM samples).  Frames below this are
# considered silence.  Tuned for typical close-talk microphone on ESP32.
_VAD_ENERGY_THRESHOLD = 300
# Minimum number of voiced frames to keep a segment (avoids micro-bursts)
_VAD_MIN_VOICED_FRAMES = 3
# Frame duration for energy calculation (20 ms at 16 kHz mono 16-bit)
_VAD_FRAME_SAMPLES = 320  # 16000 Hz * 0.020 s

_OPENAI_API_BASE = "https://api.openai.com/v1"

_DEFAULT_SYSTEM_PROMPT = (
    "Tu es le Professeur Zacus, un scientifique excentrique et bienveillant. "
    "Tu parles en francais. Tu donnes des indices cryptiques pour aider les "
    "joueurs a progresser dans le mystere sans jamais reveler les solutions. "
    "Reponds en 1-2 phrases courtes et theatrales."
)


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------


@dataclass
class VoicePipelineResult:
    """Outcome of a single voice pipeline invocation."""

    ok: bool = True
    transcript: str = ""
    llm_reply: str = ""
    audio_response: bytes = b""
    audio_content_type: str = "audio/wav"
    error: str | None = None
    timings_ms: dict[str, int] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Voice Activity Detection (energy-based)
# ---------------------------------------------------------------------------


def _rms_energy(pcm_frame: bytes) -> float:
    """Compute RMS energy for a 16-bit little-endian PCM frame."""
    n_samples = len(pcm_frame) // 2
    if n_samples == 0:
        return 0.0
    samples = struct.unpack(f"<{n_samples}h", pcm_frame[: n_samples * 2])
    sum_sq = sum(s * s for s in samples)
    return (sum_sq / n_samples) ** 0.5


def vad_filter(
    pcm_audio: bytes,
    *,
    sample_rate: int = 16000,
    threshold: float = _VAD_ENERGY_THRESHOLD,
    min_voiced_frames: int = _VAD_MIN_VOICED_FRAMES,
) -> bytes:
    """Strip silence from 16-bit mono PCM audio using energy-based VAD.

    Returns the concatenated voiced frames.  If no speech is detected the
    original audio is returned unchanged (the ASR model will handle it).
    """
    frame_bytes = _VAD_FRAME_SAMPLES * 2  # 16-bit = 2 bytes per sample
    total = len(pcm_audio)
    voiced_frames: list[bytes] = []
    pos = 0

    while pos + frame_bytes <= total:
        frame = pcm_audio[pos : pos + frame_bytes]
        energy = _rms_energy(frame)
        if energy >= threshold:
            voiced_frames.append(frame)
        pos += frame_bytes

    if len(voiced_frames) < min_voiced_frames:
        # Not enough speech detected -- return original to let ASR decide
        return pcm_audio

    return b"".join(voiced_frames)


# ---------------------------------------------------------------------------
# OPUS decoding helpers
# ---------------------------------------------------------------------------


def _try_decode_opus(opus_data: bytes) -> bytes | None:
    """Attempt to decode OPUS data to 16 kHz mono 16-bit PCM.

    Returns None if opuslib is not installed or decoding fails.
    """
    try:
        import opuslib  # type: ignore[import-untyped]

        decoder = opuslib.Decoder(16000, 1)  # 16 kHz, mono
        # OPUS frames are typically 20 ms (960 samples at 48 kHz, 320 at 16 kHz)
        # For a single payload we decode the whole buffer as one frame.
        pcm = decoder.decode(opus_data, _VAD_FRAME_SAMPLES)
        return pcm
    except ImportError:
        logger.debug("opuslib not installed -- passing raw audio to ASR")
        return None
    except Exception as exc:
        logger.debug("OPUS decode failed (%s) -- passing raw to ASR", exc)
        return None


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------


class VoicePipeline:
    """Async voice pipeline: audio in -> text + audio out.

    Parameters
    ----------
    router : Router | None
        Mascarade LLM router for the LLM step.  When ``None`` the pipeline
        falls back to an HTTP call against the local API.
    system_prompt : str | None
        Override the default Zacus persona.
    vad_threshold : float
        RMS energy threshold for the VAD filter.
    """

    def __init__(
        self,
        *,
        router: Router | None = None,
        system_prompt: str | None = None,
        vad_threshold: float = _VAD_ENERGY_THRESHOLD,
    ) -> None:
        self._router = router
        self._system_prompt = system_prompt or _DEFAULT_SYSTEM_PROMPT
        self._vad_threshold = vad_threshold

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    async def process(
        self,
        audio_bytes: bytes,
        *,
        content_type: str = "audio/opus",
    ) -> VoicePipelineResult:
        """Run the full OPUS -> VAD -> ASR -> LLM -> TTS pipeline.

        Parameters
        ----------
        audio_bytes : bytes
            Raw audio payload (OPUS or PCM/WAV).
        content_type : str
            MIME type of *audio_bytes* (``audio/opus``, ``audio/pcm``,
            ``audio/wav``, etc.).

        Returns
        -------
        VoicePipelineResult
        """
        timings: dict[str, int] = {}

        # ---- 1. Decode OPUS -> PCM (best-effort) -----------------------
        pcm_audio: bytes | None = None
        if content_type in ("audio/opus", "audio/ogg"):
            t0 = time.perf_counter()
            pcm_audio = _try_decode_opus(audio_bytes)
            timings["opus_decode_ms"] = _elapsed_ms(t0)

        # If we couldn't decode (no opuslib, or not OPUS), keep original
        # and send it straight to the ASR API which accepts various formats.
        asr_input = pcm_audio if pcm_audio is not None else audio_bytes

        # ---- 2. VAD — strip silence ------------------------------------
        if pcm_audio is not None:
            t0 = time.perf_counter()
            asr_input = vad_filter(pcm_audio, threshold=self._vad_threshold)
            timings["vad_ms"] = _elapsed_ms(t0)

        # ---- 3. ASR — Speech-to-Text -----------------------------------
        t0 = time.perf_counter()
        try:
            transcript = await self._transcribe(asr_input, content_type=content_type)
        except Exception as exc:
            logger.error("[VOICE-PIPE] ASR failed: %s", exc)
            return VoicePipelineResult(
                ok=False,
                error=f"asr_error: {exc}",
                timings_ms=timings,
            )
        timings["asr_ms"] = _elapsed_ms(t0)

        if not transcript.strip():
            return VoicePipelineResult(
                ok=True,
                transcript="",
                llm_reply="",
                error="empty_transcript",
                timings_ms=timings,
            )

        # ---- 4. LLM — route through Mascarade -------------------------
        t0 = time.perf_counter()
        try:
            llm_reply = await self._query_llm(transcript)
        except Exception as exc:
            logger.error("[VOICE-PIPE] LLM failed: %s", exc)
            return VoicePipelineResult(
                ok=False,
                transcript=transcript,
                error=f"llm_error: {exc}",
                timings_ms=timings,
            )
        timings["llm_ms"] = _elapsed_ms(t0)

        # ---- 5. TTS — Text-to-Speech -----------------------------------
        t0 = time.perf_counter()
        try:
            audio_response = await self._synthesize(llm_reply)
        except Exception as exc:
            logger.error("[VOICE-PIPE] TTS failed: %s", exc)
            return VoicePipelineResult(
                ok=False,
                transcript=transcript,
                llm_reply=llm_reply,
                error=f"tts_error: {exc}",
                timings_ms=timings,
            )
        timings["tts_ms"] = _elapsed_ms(t0)

        return VoicePipelineResult(
            ok=True,
            transcript=transcript,
            llm_reply=llm_reply,
            audio_response=audio_response,
            audio_content_type="audio/wav",
            timings_ms=timings,
        )

    # ------------------------------------------------------------------
    # ASR (OpenAI Whisper API via httpx)
    # ------------------------------------------------------------------

    async def _transcribe(
        self,
        audio: bytes,
        *,
        content_type: str = "audio/opus",
    ) -> str:
        """Transcribe audio via the OpenAI Whisper API."""
        api_key = secret_value(settings.openai_api_key)
        if not is_secret_configured(settings.openai_api_key):
            raise RuntimeError("OpenAI API key not configured for ASR")

        # Determine filename extension from content type for the multipart upload
        ext_map = {
            "audio/opus": "audio.opus",
            "audio/ogg": "audio.ogg",
            "audio/wav": "audio.wav",
            "audio/pcm": "audio.pcm",
            "audio/webm": "audio.webm",
            "audio/mp3": "audio.mp3",
            "audio/mpeg": "audio.mp3",
        }
        filename = ext_map.get(content_type, "audio.bin")

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{_OPENAI_API_BASE}/audio/transcriptions",
                headers={"Authorization": f"Bearer {api_key}"},
                files={"file": (filename, audio, content_type)},
                data={
                    "model": settings.device_stt_model,
                    "language": settings.device_stt_language,
                    "response_format": "text",
                },
            )
            resp.raise_for_status()
            return resp.text.strip()

    # ------------------------------------------------------------------
    # LLM (Mascarade router or HTTP fallback)
    # ------------------------------------------------------------------

    async def _query_llm(self, text: str) -> str:
        """Route transcribed text through the Mascarade LLM router."""
        messages = [
            {"role": "user", "content": text},
        ]

        # Direct router dispatch (preferred)
        if self._router is not None:
            result = await self._router.send(
                messages,
                strategy="cheapest",
                system=self._system_prompt,
                temperature=0.7,
                max_tokens=150,
            )
            return result.content.strip()

        # HTTP fallback
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                "http://localhost:8100/v1/chat/completions",
                json={
                    "model": "auto",
                    "messages": [
                        {"role": "system", "content": self._system_prompt},
                        {"role": "user", "content": text},
                    ],
                    "max_tokens": 150,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            choices = data.get("choices", [])
            if choices:
                return choices[0]["message"]["content"].strip()
            return "Je ne comprends pas."

    # ------------------------------------------------------------------
    # TTS (OpenAI TTS API via httpx)
    # ------------------------------------------------------------------

    async def _synthesize(self, text: str) -> bytes:
        """Convert text to speech via the OpenAI TTS API."""
        api_key = secret_value(settings.openai_api_key)
        if not is_secret_configured(settings.openai_api_key):
            raise RuntimeError("OpenAI API key not configured for TTS")

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{_OPENAI_API_BASE}/audio/speech",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": settings.device_tts_model,
                    "voice": settings.device_tts_voice,
                    "input": text,
                    "response_format": "wav",
                },
            )
            resp.raise_for_status()
            return resp.content


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _elapsed_ms(start: float) -> int:
    return int((time.perf_counter() - start) * 1000)
