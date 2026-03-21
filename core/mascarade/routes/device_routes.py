"""Device voice session routes."""

from __future__ import annotations

import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response

from mascarade.auth import require_auth
from mascarade.device_voice import DevicePlayerEvent, DeviceVoiceService

logger = logging.getLogger("mascarade.routes.device")

router = APIRouter(prefix="/device/v1", dependencies=[Depends(require_auth)])


@router.post("/voice/session")
async def device_voice_session(request: Request):
    form = await request.form()
    device_id = form.get("device_id", "")
    mode = form.get("mode", "idle")
    current_media_raw = form.get("current_media", "{}")
    try:
        current_media_payload = json.loads(current_media_raw)
    except (json.JSONDecodeError, TypeError):
        current_media_payload = {}

    audio_file = form.get("audio") or form.get("audio.wav")
    if audio_file is None:
        raise HTTPException(status_code=400, detail="Missing audio file")

    audio_bytes = await audio_file.read()
    filename = getattr(audio_file, "filename", "audio.wav")
    content_type = getattr(audio_file, "content_type", "audio/wav")

    service: DeviceVoiceService = request.app.state.device_voice
    result = await service.handle_session(
        device_id=device_id,
        mode=mode,
        current_media_payload=current_media_payload,
        audio_bytes=audio_bytes,
        filename=filename,
        content_type=content_type,
        request_base_url=str(request.base_url),
    )
    return result.model_dump()


@router.post("/player/event")
async def device_player_event(event: DevicePlayerEvent, request: Request):
    service: DeviceVoiceService = request.app.state.device_voice
    state = service.record_player_event(event)
    return {"ok": True, "state": state.model_dump()}


@router.get("/voice/replies/{reply_id}.wav")
async def device_voice_reply_audio(reply_id: str, request: Request):
    service: DeviceVoiceService = request.app.state.device_voice
    audio = service.get_reply_audio(reply_id)
    if audio is None:
        raise HTTPException(status_code=404, detail="Reply audio not found or expired")
    return Response(content=audio.payload, media_type=audio.content_type)
