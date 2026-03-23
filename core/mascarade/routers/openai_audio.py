"""OpenAI Audio API compatibility router for ESP32-S3-BOX-3 integration.

Exposes:
  POST /v1/audio/transcriptions  — Whisper-compatible STT
  POST /v1/audio/speech           — TTS (returns MP3 or WAV)

This file should be placed in mascarade/routers/openai_audio.py and
registered in server.py.

STT backend options (in order of preference):
  1. faster-whisper (local, GPU-accelerated)
  2. OpenAI Whisper API (remote, requires OPENAI_API_KEY)

TTS backend options:
  1. Piper TTS (local, configured via VOICE_BRIDGE_TTS_URL)
  2. OpenAI TTS API (remote, requires OPENAI_API_KEY)
"""

from __future__ import annotations

import io
import logging
import struct
import time
from typing import Literal

import httpx
from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, SecretStr

from mascarade.config import settings


def _is_secret_configured(secret) -> bool:
    """Check if a SecretStr or str secret is set and non-empty."""
    if secret is None:
        return False
    if isinstance(secret, SecretStr):
        val = secret.get_secret_value()
    else:
        val = str(secret)
    return bool(val and val.strip() and val != "changeme")

logger = logging.getLogger("mascarade.openai_audio")

router = APIRouter(prefix="/v1", tags=["audio"])

# ---------------------------------------------------------------------------
# STT — POST /v1/audio/transcriptions
# ---------------------------------------------------------------------------
# The ESP-BOX firmware sends a multipart form with:
#   - file: WAV audio bytes
#   - model: "whisper-1" (ignored, we use our config)
#   - language: "fr"
#   - response_format: "json"


@router.post("/audio/transcriptions")
async def audio_transcriptions(
    request: Request,
    file: UploadFile = File(...),
    model: str = Form(default="whisper-1"),
    language: str = Form(default="fr"),
    response_format: str = Form(default="json"),
):
    """OpenAI-compatible Whisper STT endpoint."""
    audio_bytes = await file.read()
    if len(audio_bytes) < 44:
        raise HTTPException(status_code=400, detail="Audio too short")

    logger.info(
        "STT request: %d bytes, lang=%s, format=%s",
        len(audio_bytes),
        language,
        response_format,
    )

    started = time.perf_counter()

    # Try faster-whisper first (local)
    text = await _transcribe_faster_whisper(audio_bytes, language)

    # Fallback to OpenAI API
    if text is None and _is_secret_configured(settings.openai_api_key):
        text = await _transcribe_openai(audio_bytes, file.filename or "audio.wav", language)

    if text is None:
        raise HTTPException(
            status_code=503,
            detail="No STT backend available. Configure faster-whisper or OPENAI_API_KEY.",
        )

    elapsed_ms = int((time.perf_counter() - started) * 1000)
    logger.info("STT completed in %dms: %s", elapsed_ms, text[:100])

    if response_format == "json":
        return {"text": text}
    # "text" format - plain text
    return Response(content=text, media_type="text/plain")


# ---------------------------------------------------------------------------
# TTS — POST /v1/audio/speech
# ---------------------------------------------------------------------------


class SpeechRequest(BaseModel):
    model: str = "tts-1"
    input: str
    voice: str = "nova"
    response_format: Literal["mp3", "wav", "opus", "aac", "flac"] = "mp3"
    speed: float = 1.0


@router.post("/audio/speech")
async def audio_speech(request: Request, body: SpeechRequest):
    """OpenAI-compatible TTS endpoint."""
    if not body.input.strip():
        raise HTTPException(status_code=400, detail="Empty input text")

    logger.info(
        "TTS request: %d chars, voice=%s, format=%s",
        len(body.input),
        body.voice,
        body.response_format,
    )

    started = time.perf_counter()

    # Try Piper TTS first (local)
    audio_bytes = await _synthesize_piper(body.input, body.voice, body.response_format)

    # Fallback to OpenAI TTS API
    if audio_bytes is None and _is_secret_configured(settings.openai_api_key):
        audio_bytes = await _synthesize_openai(
            body.input, body.voice, body.response_format
        )

    if audio_bytes is None:
        raise HTTPException(
            status_code=503,
            detail="No TTS backend available. Configure VOICE_BRIDGE_TTS_URL or OPENAI_API_KEY.",
        )

    elapsed_ms = int((time.perf_counter() - started) * 1000)
    logger.info("TTS completed in %dms: %d bytes", elapsed_ms, len(audio_bytes))

    content_type_map = {
        "mp3": "audio/mpeg",
        "wav": "audio/wav",
        "opus": "audio/opus",
        "aac": "audio/aac",
        "flac": "audio/flac",
    }

    return Response(
        content=audio_bytes,
        media_type=content_type_map.get(body.response_format, "audio/mpeg"),
    )


# ---------------------------------------------------------------------------
# STT backends
# ---------------------------------------------------------------------------


async def _transcribe_faster_whisper(
    audio_bytes: bytes, language: str
) -> str | None:
    """Transcribe using faster-whisper (local GPU/CPU)."""
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        return None

    try:
        # Lazy-load model (cached after first call)
        if not hasattr(_transcribe_faster_whisper, "_model"):
            model_size = getattr(settings, "whisper_model_size", "base")
            device = getattr(settings, "whisper_device", "auto")
            compute_type = getattr(settings, "whisper_compute_type", "int8")
            _transcribe_faster_whisper._model = WhisperModel(
                model_size, device=device, compute_type=compute_type
            )

        model = _transcribe_faster_whisper._model
        audio_file = io.BytesIO(audio_bytes)
        segments, info = model.transcribe(
            audio_file,
            language=language,
            beam_size=5,
            vad_filter=True,
        )
        text = " ".join(seg.text.strip() for seg in segments)
        return text if text else None
    except Exception as e:
        logger.warning("faster-whisper error: %s", e)
        return None


async def _transcribe_openai(
    audio_bytes: bytes, filename: str, language: str
) -> str | None:
    """Transcribe using OpenAI Whisper API."""
    try:
        from openai import AsyncOpenAI

        client = AsyncOpenAI(
            api_key=settings.openai_api_key
            if isinstance(settings.openai_api_key, str)
            else settings.openai_api_key.get_secret_value(),
            timeout=30.0,
        )
        result = await client.audio.transcriptions.create(
            file=(filename, audio_bytes, "audio/wav"),
            model=settings.device_stt_model,
            language=language,
            response_format="text",
        )
        return str(result).strip() or None
    except Exception as e:
        logger.warning("OpenAI STT error: %s", e)
        return None


# ---------------------------------------------------------------------------
# TTS backends
# ---------------------------------------------------------------------------


async def _synthesize_piper(
    text: str, voice: str, response_format: str
) -> bytes | None:
    """Synthesize using Piper TTS (or any OpenAI-compatible TTS endpoint)."""
    tts_url = settings.voice_bridge_tts_url
    if not tts_url:
        return None

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                tts_url,
                json={
                    "model": "tts-1",
                    "input": text,
                    "voice": voice,
                    "response_format": response_format,
                },
            )
            if resp.status_code == 200:
                return resp.content
            logger.warning("Piper TTS error: HTTP %s", resp.status_code)
            return None
    except Exception as e:
        logger.warning("Piper TTS error: %s", e)
        return None


async def _synthesize_openai(
    text: str, voice: str, response_format: str
) -> bytes | None:
    """Synthesize using OpenAI TTS API."""
    try:
        from openai import AsyncOpenAI

        client = AsyncOpenAI(
            api_key=settings.openai_api_key
            if isinstance(settings.openai_api_key, str)
            else settings.openai_api_key.get_secret_value(),
            timeout=30.0,
        )
        response = await client.audio.speech.create(
            model=settings.device_tts_model,
            voice=voice,
            input=text,
            response_format=response_format,
        )
        return await response.aread()
    except Exception as e:
        logger.warning("OpenAI TTS error: %s", e)
        return None
