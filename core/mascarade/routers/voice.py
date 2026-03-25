"""Voice Bridge — ESP32 ↔ LLM ↔ TTS WebSocket endpoint.

Accepts WebSocket connections from ESP32 devices running the Zacus voice
pipeline.  Protocol loosely inspired by XiaoZhi:

1. Device connects (optional ``token`` query-param for auth)
2. JSON ``hello`` handshake
3. Device sends binary OPUS audio frames *or* ``text_query`` JSON messages
4. Server: decode → ASR (faster-whisper) → LLM (mascarade router) → TTS
   (Piper on VM) → stream audio back
5. JSON control messages for state transitions
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import TYPE_CHECKING

import httpx
from fastapi import APIRouter, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse, Response
from starlette.websockets import WebSocketState

from mascarade.auth import get_active_api_keys
from mascarade.config import settings
from mascarade.voice_pipeline import VoicePipeline

if TYPE_CHECKING:
    from mascarade.router.router import Router

logger = logging.getLogger("mascarade.voice")

router = APIRouter(prefix="/voice", tags=["voice"])

# Default Zacus persona prompt
_ZACUS_SYSTEM_PROMPT = (
    "Tu es le Professeur Zacus, un scientifique excentrique et bienveillant. "
    "Tu parles en francais. Tu donnes des indices cryptiques pour aider les "
    "joueurs a progresser dans le mystere sans jamais reveler les solutions. "
    "Reponds en 1-2 phrases courtes et theatrales."
)


# ---------------------------------------------------------------------------
# Auth helper (same pattern as ws.py)
# ---------------------------------------------------------------------------


async def _ws_auth(websocket: WebSocket) -> bool:
    """Validate bearer token from query param ``token``.

    Returns True when authorised or when no API keys are configured.
    """
    active_keys = get_active_api_keys()
    if not active_keys:
        return True
    token = websocket.query_params.get("token")
    if not token:
        return False
    return token in active_keys


# ---------------------------------------------------------------------------
# WebSocket endpoint
# ---------------------------------------------------------------------------


@router.websocket("/ws")
async def voice_websocket(websocket: WebSocket):
    """WebSocket endpoint for ESP32 voice pipeline.

    Connect at ``/voice/ws?token=<api-key>`` (token optional when auth
    is disabled).
    """
    # Auth
    if not await _ws_auth(websocket):
        await websocket.close(code=4003, reason="Unauthorized")
        return

    await websocket.accept()
    client_info = websocket.client
    logger.info("[VOICE] Client connected: %s", client_info)

    try:
        # --- Handshake ---------------------------------------------------
        hello = await asyncio.wait_for(websocket.receive_json(), timeout=5.0)
        if hello.get("type") != "hello":
            await websocket.close(code=4001, reason="expected hello")
            return

        device_id = hello.get("device_id", "unknown")
        logger.info("[VOICE] Hello from device %s", device_id)

        await websocket.send_json(
            {
                "type": "hello_ack",
                "version": 1,
                "capabilities": ["tts", "llm"],
            }
        )

        # --- Main loop ---------------------------------------------------
        llm_router: Router | None = getattr(websocket.app.state, "router", None)

        while True:
            data = await websocket.receive()

            if "text" in data:
                msg = json.loads(data["text"])
                await _handle_json_message(websocket, msg, llm_router)
            elif "bytes" in data:
                await _handle_audio_frame(websocket, data["bytes"], llm_router)

    except WebSocketDisconnect:
        logger.info("[VOICE] Client disconnected: %s", client_info)
    except TimeoutError:
        logger.warning("[VOICE] Handshake timeout from %s", client_info)
        if websocket.client_state == WebSocketState.CONNECTED:
            await websocket.close(code=4002, reason="timeout")
    except Exception as e:
        logger.error("[VOICE] Error: %s", e, exc_info=True)
        if websocket.client_state == WebSocketState.CONNECTED:
            await websocket.close(code=4000, reason=str(e)[:120])


# ---------------------------------------------------------------------------
# Message handlers
# ---------------------------------------------------------------------------


async def _handle_json_message(
    ws: WebSocket,
    msg: dict,
    llm_router: Router | None,
) -> None:
    """Handle JSON control messages from device."""
    msg_type = msg.get("type", "")

    if msg_type == "listen":
        state = msg.get("state", "")
        if state == "detect":
            logger.info("[VOICE] Wake-word detected: %s", msg.get("text", ""))
            await ws.send_json({"type": "listen_ack", "state": "ready"})
        elif state == "stop":
            logger.info("[VOICE] Listening stopped")

    elif msg_type == "text_query":
        query = msg.get("text", "")
        if not query:
            return
        response_text = await _query_llm(query, llm_router)
        audio = await _text_to_speech(response_text)

        await ws.send_json({"type": "tts", "state": "start", "text": response_text})
        if audio:
            await ws.send_bytes(audio)
        await ws.send_json({"type": "tts", "state": "stop"})

    elif msg_type == "abort":
        logger.info("[VOICE] Client aborted playback")

    else:
        logger.debug("[VOICE] Unknown message type: %s", msg_type)


async def _handle_audio_frame(
    ws: WebSocket,
    frame: bytes,
    llm_router: Router | None,
) -> None:
    """Handle binary audio frame from device.

    Runs the full voice pipeline: OPUS decode -> VAD -> ASR -> LLM -> TTS
    and streams the audio response back over the WebSocket.
    """
    logger.debug("[VOICE] Audio frame: %d bytes", len(frame))

    pipeline = VoicePipeline(router=llm_router)
    result = await pipeline.process(frame, content_type="audio/opus")

    if not result.ok:
        logger.warning("[VOICE] Pipeline error: %s", result.error)
        await ws.send_json(
            {
                "type": "pipeline_error",
                "error": result.error or "unknown",
            }
        )
        return

    if not result.transcript:
        logger.debug("[VOICE] Empty transcript -- skipping")
        return

    # Send TTS audio back to device
    await ws.send_json(
        {
            "type": "tts",
            "state": "start",
            "text": result.llm_reply,
            "transcript": result.transcript,
            "timings_ms": result.timings_ms,
        }
    )
    if result.audio_response:
        await ws.send_bytes(result.audio_response)
    await ws.send_json({"type": "tts", "state": "stop"})


# ---------------------------------------------------------------------------
# LLM query
# ---------------------------------------------------------------------------


async def _query_llm(text: str, llm_router: Router | None = None) -> str:
    """Query the mascarade LLM for a response.

    When a *Router* instance is available (from ``app.state.router``),
    dispatches directly through the router.  Otherwise falls back to an
    HTTP call against the local ``/v1/chat/completions`` endpoint.
    """
    messages = [
        {"role": "system", "content": _ZACUS_SYSTEM_PROMPT},
        {"role": "user", "content": text},
    ]

    # --- Direct router dispatch (preferred) ------------------------------
    if llm_router is not None:
        try:
            result = await llm_router.route(
                messages=messages,
                strategy="cheapest",
                timeout=10,
            )
            return result.get("content", "Je ne comprends pas.")
        except Exception as e:
            logger.error("[VOICE] Router dispatch error: %s", e)
            # Fall through to HTTP fallback

    # --- HTTP fallback ---------------------------------------------------
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                "http://localhost:8100/v1/chat/completions",
                json={
                    "model": "auto",
                    "messages": messages,
                    "max_tokens": 150,
                },
            )
            if resp.status_code == 200:
                data = resp.json()
                choices = data.get("choices", [])
                if choices:
                    return choices[0]["message"]["content"]
                return "Je ne comprends pas."
            logger.error("[VOICE] LLM HTTP error: %s", resp.status_code)
            return "Hmm, mon laboratoire a un probleme technique."
    except Exception as e:
        logger.error("[VOICE] LLM HTTP error: %s", e)
        return "Un instant, je reflechis..."


# ---------------------------------------------------------------------------
# TTS
# ---------------------------------------------------------------------------


async def _text_to_speech(text: str) -> bytes | None:
    """Convert *text* to speech using Piper TTS (OpenAI-compatible API)."""
    tts_url = settings.voice_bridge_tts_url
    if not tts_url:
        logger.warning("[VOICE] TTS not configured (VOICE_BRIDGE_TTS_URL)")
        return None

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                tts_url,
                json={
                    "model": "tts-1",
                    "input": text,
                    "voice": settings.voice_bridge_tts_voice,
                    "response_format": "wav",
                },
            )
            if resp.status_code == 200:
                return resp.content
            logger.error("[VOICE] TTS error: HTTP %s", resp.status_code)
            return None
    except Exception as e:
        logger.error("[VOICE] TTS error: %s", e)
        return None


# ---------------------------------------------------------------------------
# POST endpoint — voice pipeline (non-WebSocket)
# ---------------------------------------------------------------------------


@router.post("/pipeline")
async def voice_pipeline_post(request: Request) -> Response:
    """Process audio through the full voice pipeline via HTTP POST.

    Send raw audio (OPUS, WAV, etc.) as the request body.
    Set ``Content-Type`` to ``audio/opus``, ``audio/wav``, etc.

    Returns the TTS audio (WAV) on success, or a JSON error payload.

    Query params:
        ``format`` — response format: ``audio`` (default) returns WAV bytes,
        ``json`` returns a JSON object with transcript, reply, and timings.
    """
    llm_router: Router | None = getattr(request.app.state, "router", None)
    content_type = request.headers.get("content-type", "audio/opus")
    response_format = request.query_params.get("format", "audio")

    body = await request.body()
    if not body:
        return JSONResponse(
            status_code=400,
            content={"error": "empty_body", "detail": "No audio payload received."},
        )

    if len(body) > settings.device_voice_max_audio_bytes:
        return JSONResponse(
            status_code=413,
            content={
                "error": "payload_too_large",
                "detail": f"Max {settings.device_voice_max_audio_bytes} bytes.",
            },
        )

    pipeline = VoicePipeline(router=llm_router)
    result = await pipeline.process(body, content_type=content_type)

    if not result.ok:
        return JSONResponse(
            status_code=502,
            content={
                "error": result.error or "pipeline_error",
                "transcript": result.transcript,
                "llm_reply": result.llm_reply,
                "timings_ms": result.timings_ms,
            },
        )

    if response_format == "json":
        return JSONResponse(
            content={
                "ok": True,
                "transcript": result.transcript,
                "llm_reply": result.llm_reply,
                "timings_ms": result.timings_ms,
                "audio_content_type": result.audio_content_type,
                "audio_size": len(result.audio_response),
            },
        )

    # Default: return audio bytes
    return Response(
        content=result.audio_response,
        media_type=result.audio_content_type,
        headers={
            "X-Transcript": result.transcript[:200],
            "X-LLM-Reply": result.llm_reply[:200],
        },
    )
