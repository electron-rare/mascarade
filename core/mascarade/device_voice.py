"""Voice-session service for ESP32 devices talking to Mascarade over LAN."""

from __future__ import annotations

import json
import logging
import re
import threading
import time
import unicodedata
import wave
from dataclasses import dataclass
from io import BytesIO
from typing import Any, Literal, Protocol
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from mascarade.config import is_secret_configured, settings
from mascarade.router.router import Strategy

logger = logging.getLogger("mascarade.device_voice")

_MEDIA_ACTION_INTENTS = {
    "play",
    "next",
    "previous",
    "set_volume",
    "switch_mode",
    "select_station",
}


class DeviceIntent(BaseModel):
    model_config = ConfigDict(extra="ignore")

    type: Literal[
        "none",
        "play",
        "pause",
        "next",
        "previous",
        "set_volume",
        "switch_mode",
        "select_station",
        "battery_status",
        "wifi_status",
        "what_is_playing",
    ] = "none"
    target: str | None = None
    value: int | str | dict[str, Any] | None = None
    spoken_confirmation: str = ""
    resume_media_after_tts: bool = False


class DeviceCurrentMedia(BaseModel):
    model_config = ConfigDict(extra="ignore")

    mode: Literal["idle", "mp3", "radio"] = "idle"
    playing: bool = False
    station: str | None = None
    track: str | None = None
    volume: int = Field(default=40, ge=0, le=100)
    battery_pct: int | None = Field(default=None, ge=0, le=100)
    wifi_ssid: str | None = None
    wifi_rssi: int | None = None
    available_stations: list[str] = Field(default_factory=list)


class DevicePlayerEvent(BaseModel):
    model_config = ConfigDict(extra="ignore")

    device_id: str = Field(min_length=1, max_length=120)
    event: Literal[
        "boot",
        "playback_started",
        "playback_failed",
        "voice_error",
        "battery_update",
    ]
    mode: Literal["idle", "mp3", "radio"] | None = None
    playing: bool | None = None
    station: str | None = Field(default=None, max_length=200)
    track: str | None = Field(default=None, max_length=200)
    volume: int | None = Field(default=None, ge=0, le=100)
    battery_pct: int | None = Field(default=None, ge=0, le=100)
    wifi_ssid: str | None = Field(default=None, max_length=200)
    wifi_rssi: int | None = None
    detail: str | None = Field(default=None, max_length=1000)


class DeviceVoiceSessionResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    ok: bool
    session_id: str
    transcript: str = ""
    intent: DeviceIntent = Field(default_factory=DeviceIntent)
    reply_text: str = ""
    reply_audio_url: str | None = None
    player_action: Literal["none", "duck", "stop_resume"] = "none"
    provider: str = "none"
    timings_ms: dict[str, int] = Field(default_factory=dict)
    error: str | None = None


class AudioBridge(Protocol):
    async def transcribe(
        self,
        *,
        audio_bytes: bytes,
        filename: str,
        content_type: str,
        language: str | None = None,
    ) -> str: ...

    async def synthesize(self, *, text: str) -> bytes: ...


@dataclass
class StoredReplyAudio:
    content_type: str
    payload: bytes
    expires_at: float


class ReplyAudioStore:
    def __init__(self, ttl_seconds: int = 900) -> None:
        self._ttl_seconds = ttl_seconds
        self._lock = threading.Lock()
        self._entries: dict[str, StoredReplyAudio] = {}

    def _gc(self, now: float | None = None) -> None:
        now = now or time.time()
        expired = [
            reply_id
            for reply_id, item in self._entries.items()
            if item.expires_at <= now
        ]
        for reply_id in expired:
            self._entries.pop(reply_id, None)

    def put(self, payload: bytes, *, content_type: str = "audio/wav") -> str:
        reply_id = uuid4().hex
        with self._lock:
            self._gc()
            self._entries[reply_id] = StoredReplyAudio(
                content_type=content_type,
                payload=payload,
                expires_at=time.time() + self._ttl_seconds,
            )
        return reply_id

    def get(self, reply_id: str) -> StoredReplyAudio | None:
        with self._lock:
            self._gc()
            return self._entries.get(reply_id)


class DeviceStateStore:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._states: dict[str, DeviceCurrentMedia] = {}

    def snapshot(self, device_id: str) -> DeviceCurrentMedia:
        with self._lock:
            existing = self._states.get(device_id, DeviceCurrentMedia())
            return existing.model_copy(deep=True)

    def merge_current_media(
        self, device_id: str, payload: dict[str, Any]
    ) -> DeviceCurrentMedia:
        with self._lock:
            existing = self._states.get(device_id, DeviceCurrentMedia())
            merged = existing.model_dump()
            updates = {
                key: value
                for key, value in payload.items()
                if value is not None
                and not (key == "available_stations" and value == [])
            }
            merged.update(updates)
            current = DeviceCurrentMedia.model_validate(merged)
            self._states[device_id] = current
            return current.model_copy(deep=True)

    def record_event(self, event: DevicePlayerEvent) -> DeviceCurrentMedia:
        payload = event.model_dump(exclude_none=True)
        payload.pop("device_id", None)
        payload.pop("event", None)
        payload.pop("detail", None)
        return self.merge_current_media(event.device_id, payload)


class OpenAIAudioBridge:
    def __init__(self) -> None:
        self._client = None

    @property
    def is_available(self) -> bool:
        return is_secret_configured(settings.openai_api_key)

    def _get_client(self):
        if self._client is None:
            from openai import AsyncOpenAI

            self._client = AsyncOpenAI(
                api_key=settings.openai_api_key,
                timeout=30.0,
            )
        return self._client

    async def transcribe(
        self,
        *,
        audio_bytes: bytes,
        filename: str,
        content_type: str,
        language: str | None = None,
    ) -> str:
        if not self.is_available:
            raise RuntimeError("OpenAI audio bridge is not configured")

        result = await self._get_client().audio.transcriptions.create(
            file=(filename, audio_bytes, content_type),
            model=settings.device_stt_model,
            language=language or settings.device_stt_language,
            response_format="text",
        )
        return str(result).strip()

    async def synthesize(self, *, text: str) -> bytes:
        if not self.is_available:
            raise RuntimeError("OpenAI audio bridge is not configured")

        response = await self._get_client().audio.speech.create(
            model=settings.device_tts_model,
            voice=settings.device_tts_voice,
            input=text,
            response_format="wav",
        )
        return await response.aread()


class IntentRouter:
    _volume_pattern = re.compile(
        r"\b(?:volume|son)\s*(?:a|à|to)?\s*(\d{1,3})\b", re.IGNORECASE
    )

    def resolve(self, transcript: str, media: DeviceCurrentMedia) -> DeviceIntent:
        normalized = _normalize(transcript)
        if not normalized:
            return DeviceIntent(
                spoken_confirmation="Je n'ai pas compris la demande.",
                resume_media_after_tts=media.playing,
            )

        station = self._match_station(normalized, media.available_stations)
        if station:
            return DeviceIntent(
                type="select_station",
                target="station",
                value=station,
                spoken_confirmation=f"Je lance {station}.",
                resume_media_after_tts=True,
            )

        if any(token in normalized for token in ("batterie", "battery")):
            return DeviceIntent(
                type="battery_status",
                target="device",
                spoken_confirmation=_battery_reply(media),
                resume_media_after_tts=media.playing,
            )

        if any(token in normalized for token in ("wifi", "wi fi", "reseau", "réseau")):
            return DeviceIntent(
                type="wifi_status",
                target="device",
                spoken_confirmation=_wifi_reply(media),
                resume_media_after_tts=media.playing,
            )

        if any(
            token in normalized
            for token in (
                "c est quoi la musique",
                "c est quoi en cours",
                "what is playing",
                "whats playing",
                "now playing",
                "musique en cours",
            )
        ):
            return DeviceIntent(
                type="what_is_playing",
                target="player",
                spoken_confirmation=_what_is_playing_reply(media),
                resume_media_after_tts=media.playing,
            )

        volume_match = self._volume_pattern.search(normalized)
        if volume_match:
            volume = max(0, min(int(volume_match.group(1)), 100))
            return DeviceIntent(
                type="set_volume",
                target="player",
                value=volume,
                spoken_confirmation=f"D'accord, volume {volume}.",
                resume_media_after_tts=media.playing,
            )

        if any(
            token in normalized
            for token in ("suivant", "next", "station suivante", "piste suivante")
        ):
            return DeviceIntent(
                type="next",
                target="player",
                spoken_confirmation="Je passe au suivant.",
                resume_media_after_tts=True,
            )

        if any(
            token in normalized
            for token in (
                "precedent",
                "précédent",
                "previous",
                "station precedente",
                "station précédente",
            )
        ):
            return DeviceIntent(
                type="previous",
                target="player",
                spoken_confirmation="Je reviens au précédent.",
                resume_media_after_tts=True,
            )

        if any(token in normalized for token in ("pause", "arrete", "arrête", "stop")):
            return DeviceIntent(
                type="pause",
                target="player",
                spoken_confirmation="Je mets la lecture en pause.",
                resume_media_after_tts=False,
            )

        if any(
            token in normalized for token in ("mode radio", "passe en radio", "radio")
        ):
            return DeviceIntent(
                type="switch_mode",
                target="mode",
                value="radio",
                spoken_confirmation="Je passe en mode radio.",
                resume_media_after_tts=True,
            )

        if any(
            token in normalized
            for token in (
                "mode mp3",
                "mp3",
                "carte sd",
                "musique locale",
                "local files",
            )
        ):
            return DeviceIntent(
                type="switch_mode",
                target="mode",
                value="mp3",
                spoken_confirmation="Je passe en mode MP3.",
                resume_media_after_tts=True,
            )

        if any(
            token in normalized
            for token in (
                "reprend",
                "reprends",
                "play",
                "continue",
                "resume",
                "relance",
            )
        ):
            return DeviceIntent(
                type="play",
                target="player",
                spoken_confirmation="Je relance la lecture.",
                resume_media_after_tts=True,
            )

        return DeviceIntent(
            spoken_confirmation="",
            resume_media_after_tts=media.playing,
        )

    @staticmethod
    def _match_station(normalized_text: str, stations: list[str]) -> str | None:
        for station in stations:
            if _normalize(station) and _normalize(station) in normalized_text:
                return station
        return None


class DeviceVoiceService:
    def __init__(
        self,
        *,
        router,
        audio_bridge: AudioBridge | None = None,
        state_store: DeviceStateStore | None = None,
        reply_store: ReplyAudioStore | None = None,
        intent_router: IntentRouter | None = None,
    ) -> None:
        self._router = router
        self._audio_bridge = audio_bridge or OpenAIAudioBridge()
        self._state_store = state_store or DeviceStateStore()
        self._reply_store = reply_store or ReplyAudioStore(
            ttl_seconds=settings.device_reply_ttl_seconds
        )
        self._intent_router = intent_router or IntentRouter()

    async def handle_session(
        self,
        *,
        device_id: str,
        mode: str,
        current_media_payload: dict[str, Any],
        audio_bytes: bytes,
        filename: str,
        content_type: str,
        request_base_url: str,
    ) -> DeviceVoiceSessionResponse:
        started_at = time.perf_counter()
        timings_ms: dict[str, int] = {}
        session_id = uuid4().hex

        current_media_payload = dict(current_media_payload)
        current_media_payload.setdefault("mode", mode or "idle")
        media = self._state_store.merge_current_media(device_id, current_media_payload)

        try:
            transcript_started = time.perf_counter()
            transcript = await self._audio_bridge.transcribe(
                audio_bytes=audio_bytes,
                filename=filename,
                content_type=content_type,
                language=settings.device_stt_language,
            )
            timings_ms["stt"] = _elapsed_ms(transcript_started)
        except Exception as exc:
            logger.warning("STT failed for %s: %s", device_id, exc)
            response = DeviceVoiceSessionResponse(
                ok=False,
                session_id=session_id,
                reply_text="La transcription vocale est indisponible.",
                error="stt_unavailable",
                provider="openai-stt",
                player_action="none",
            )
            self._log_session(
                device_id=device_id,
                session_id=session_id,
                transcript="",
                media=media,
                response=response,
                total_ms=_elapsed_ms(started_at),
                audio_duration_ms=_wav_duration_ms(audio_bytes),
            )
            return response

        intent = self._intent_router.resolve(transcript, media)
        player_action = _player_action_for(intent, media)
        provider = "intent-router"

        if intent.type != "none":
            reply_text = intent.spoken_confirmation
        else:
            llm_started = time.perf_counter()
            reply_text, provider = await self._generate_llm_reply(transcript, media)
            timings_ms["llm"] = _elapsed_ms(llm_started)
            if not reply_text:
                reply_text = "Je n'ai pas de réponse exploitable pour l'instant."

        reply_audio_url: str | None = None
        tts_error: str | None = None
        if reply_text:
            tts_started = time.perf_counter()
            try:
                audio_payload = await self._audio_bridge.synthesize(text=reply_text)
                timings_ms["tts"] = _elapsed_ms(tts_started)
                reply_id = self._reply_store.put(
                    audio_payload, content_type="audio/wav"
                )
                reply_audio_url = f"{request_base_url.rstrip('/')}/device/v1/voice/replies/{reply_id}.wav"
            except Exception as exc:
                tts_error = "tts_unavailable"
                logger.warning("TTS failed for %s: %s", device_id, exc)

        response = DeviceVoiceSessionResponse(
            ok=tts_error is None or bool(reply_text),
            session_id=session_id,
            transcript=transcript,
            intent=intent,
            reply_text=reply_text,
            reply_audio_url=reply_audio_url,
            player_action=player_action,
            provider=provider,
            timings_ms=timings_ms,
            error=tts_error,
        )

        self._log_session(
            device_id=device_id,
            session_id=session_id,
            transcript=transcript,
            media=media,
            response=response,
            total_ms=_elapsed_ms(started_at),
            audio_duration_ms=_wav_duration_ms(audio_bytes),
        )
        return response

    def record_player_event(self, event: DevicePlayerEvent) -> DeviceCurrentMedia:
        state = self._state_store.record_event(event)
        logger.info(
            "device.voice.event %s",
            json.dumps(
                {
                    "device_id": event.device_id,
                    "event": event.event,
                    "state": state.model_dump(),
                    "detail": event.detail,
                },
                ensure_ascii=True,
                sort_keys=True,
            ),
        )
        return state

    def get_reply_audio(self, reply_id: str) -> StoredReplyAudio | None:
        return self._reply_store.get(reply_id)

    async def _generate_llm_reply(
        self, transcript: str, media: DeviceCurrentMedia
    ) -> tuple[str, str]:
        prompt = (
            "Contexte boitier ESP32-S3 radio/MP3.\n"
            f"Etat lecteur: {json.dumps(media.model_dump(), ensure_ascii=False)}\n"
            f"Demande utilisateur: {transcript}\n"
            "Réponds en français, très brièvement, sans markdown."
        )
        system = (
            "Tu es l'assistant vocal d'un boîtier audio compact. "
            "Réponds en une à trois phrases maximum, avec des formulations naturelles."
        )

        attempts: list[tuple[str | None, str | None]] = []
        if "claude" in self._router.available_providers:
            attempts.append(("claude", settings.default_model or None))
        if "apple-coreml" in self._router.available_providers:
            attempts.append(("apple-coreml", settings.apple_llm_model_id or None))
        if "ollama" in self._router.available_providers:
            attempts.append(("ollama", None))
        if "openai" in self._router.available_providers:
            attempts.append(("openai", None))
        if not attempts:
            return ("Aucun modèle texte n'est disponible sur Mascarade.", "none")

        last_error: Exception | None = None
        for provider_name, model_name in attempts:
            try:
                response = await self._router.send(
                    [{"role": "user", "content": prompt}],
                    strategy=Strategy.SPECIFIC,
                    provider=provider_name,
                    model=model_name,
                    system=system,
                    temperature=0.3,
                    max_tokens=160,
                )
                return (response.content.strip(), response.provider)
            except Exception as exc:
                last_error = exc
                logger.warning("Voice reply provider %s failed: %s", provider_name, exc)

        logger.warning("Voice reply fallback exhausted: %s", last_error)
        return (
            "Je n'arrive pas à joindre le moteur principal pour le moment.",
            "fallback",
        )

    @staticmethod
    def _log_session(
        *,
        device_id: str,
        session_id: str,
        transcript: str,
        media: DeviceCurrentMedia,
        response: DeviceVoiceSessionResponse,
        total_ms: int,
        audio_duration_ms: int | None,
    ) -> None:
        logger.info(
            "device.voice.session %s",
            json.dumps(
                {
                    "audio_duration_ms": audio_duration_ms,
                    "device_id": device_id,
                    "intent": response.intent.model_dump(),
                    "media": media.model_dump(),
                    "ok": response.ok,
                    "player_action": response.player_action,
                    "provider": response.provider,
                    "reply_audio_url": response.reply_audio_url,
                    "reply_text": response.reply_text,
                    "session_id": session_id,
                    "timings_ms": response.timings_ms,
                    "total_ms": total_ms,
                    "transcript": transcript,
                },
                ensure_ascii=True,
                sort_keys=True,
            ),
        )


def _elapsed_ms(started_at: float) -> int:
    return int((time.perf_counter() - started_at) * 1000)


def _normalize(text: str) -> str:
    lowered = text.strip().lower()
    normalized = unicodedata.normalize("NFKD", lowered)
    return "".join(ch for ch in normalized if not unicodedata.combining(ch))


def _battery_reply(media: DeviceCurrentMedia) -> str:
    if media.battery_pct is None:
        return "Je n'ai pas encore le niveau de batterie."
    return f"La batterie est à {media.battery_pct}%."


def _wifi_reply(media: DeviceCurrentMedia) -> str:
    if not media.wifi_ssid:
        return "Je n'ai pas encore d'état Wi-Fi exploitable."
    if media.wifi_rssi is None:
        return f"Je suis connecté au Wi-Fi {media.wifi_ssid}."
    return f"Je suis connecté au Wi-Fi {media.wifi_ssid} avec un signal de {media.wifi_rssi} dBm."


def _what_is_playing_reply(media: DeviceCurrentMedia) -> str:
    if media.mode == "radio" and media.station:
        return f"La radio en cours est {media.station}."
    if media.mode == "mp3" and media.track:
        return f"Le morceau en cours est {media.track}."
    if media.playing:
        return "La lecture est active, mais je n'ai pas le titre précis."
    return "Rien n'est en lecture pour l'instant."


def _player_action_for(
    intent: DeviceIntent, media: DeviceCurrentMedia
) -> Literal["none", "duck", "stop_resume"]:
    if intent.type == "pause":
        return "none"
    if intent.type in _MEDIA_ACTION_INTENTS:
        return "duck"
    if media.playing:
        return "stop_resume"
    return "none"


def _wav_duration_ms(audio_bytes: bytes) -> int | None:
    try:
        with wave.open(BytesIO(audio_bytes), "rb") as wav_file:
            frames = wav_file.getnframes()
            frame_rate = wav_file.getframerate()
            if frame_rate <= 0:
                return None
            return int((frames / frame_rate) * 1000)
    except Exception:
        return None
