"""Tests for device voice routes and service behavior."""

from __future__ import annotations

import io
import time
import wave
from contextlib import asynccontextmanager
from unittest.mock import patch

import httpx
import pytest

from mascarade.auth import add_api_key, get_active_api_keys, remove_api_key
from mascarade.device_voice import (
    DeviceCurrentMedia,
    DeviceIntent,
    DevicePlayerEvent,
    DeviceStateStore,
    DeviceVoiceService,
    IntentRouter,
    ReplyAudioStore,
    _battery_reply,
    _normalize,
    _player_action_for,
    _wav_duration_ms,
    _what_is_playing_reply,
    _wifi_reply,
)
from mascarade.router.providers.base import LLMResponse
from mascarade.server import app

# ── Helper functions ──


def _make_wav_bytes(*, duration_s: float = 0.5, sample_rate: int = 16000) -> bytes:
    """Create a valid WAV file in memory."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        n_frames = int(sample_rate * duration_s)
        wf.writeframes(b"\x00\x00" * n_frames)
    return buf.getvalue()


# ── Unit tests for _normalize ──


class TestNormalize:
    def test_strips_and_lowercases(self):
        assert _normalize("  HELLO World  ") == "hello world"

    def test_removes_accents(self):
        result = _normalize("precede\u0301")
        assert "e" in result
        # The accent combining char should be gone
        assert "\u0301" not in result

    def test_empty_string(self):
        assert _normalize("") == ""


# ── Unit tests for ReplyAudioStore ──


class TestReplyAudioStore:
    def test_put_and_get(self):
        store = ReplyAudioStore(ttl_seconds=60)
        reply_id = store.put(b"audio-data", content_type="audio/wav")
        item = store.get(reply_id)
        assert item is not None
        assert item.payload == b"audio-data"
        assert item.content_type == "audio/wav"

    def test_get_unknown_returns_none(self):
        store = ReplyAudioStore()
        assert store.get("nonexistent") is None

    def test_expired_entries_gc(self):
        store = ReplyAudioStore(ttl_seconds=0)
        reply_id = store.put(b"data")
        # Force GC by calling get (which calls _gc internally)
        time.sleep(0.01)
        assert store.get(reply_id) is None


# ── Unit tests for DeviceStateStore ──


class TestDeviceStateStore:
    def test_snapshot_default(self):
        store = DeviceStateStore()
        snap = store.snapshot("dev-1")
        assert snap.mode == "idle"
        assert snap.playing is False

    def test_merge_updates_state(self):
        store = DeviceStateStore()
        result = store.merge_current_media("dev-1", {"mode": "radio", "playing": True, "volume": 50})
        assert result.mode == "radio"
        assert result.playing is True
        assert result.volume == 50

    def test_merge_preserves_existing_fields(self):
        store = DeviceStateStore()
        store.merge_current_media("dev-1", {"mode": "radio", "station": "BBC"})
        result = store.merge_current_media("dev-1", {"volume": 70})
        assert result.station == "BBC"
        assert result.volume == 70

    def test_merge_ignores_none_values(self):
        store = DeviceStateStore()
        store.merge_current_media("dev-1", {"volume": 50})
        result = store.merge_current_media("dev-1", {"volume": None})
        assert result.volume == 50

    def test_record_event(self):
        store = DeviceStateStore()
        event = DevicePlayerEvent(
            device_id="dev-1",
            event="playback_started",
            mode="radio",
            playing=True,
            station="Classic FM",
        )
        result = store.record_event(event)
        assert result.mode == "radio"
        assert result.station == "Classic FM"


# ── Unit tests for IntentRouter ──


class TestIntentRouter:
    def setup_method(self):
        self.router = IntentRouter()
        self.media = DeviceCurrentMedia(
            mode="radio",
            playing=True,
            station="BBC World Service",
            volume=40,
            available_stations=["BBC World Service", "Classic FM"],
        )

    def test_empty_transcript_returns_none_intent(self):
        intent = self.router.resolve("", self.media)
        assert intent.type == "none"
        assert intent.spoken_confirmation != ""

    def test_volume_command(self):
        intent = self.router.resolve("volume a 30", self.media)
        assert intent.type == "set_volume"
        assert intent.value == 30

    def test_volume_clamps_to_100(self):
        intent = self.router.resolve("volume 150", self.media)
        assert intent.type == "set_volume"
        assert intent.value == 100

    def test_next_command(self):
        intent = self.router.resolve("suivant", self.media)
        assert intent.type == "next"

    def test_previous_command(self):
        intent = self.router.resolve("precedent", self.media)
        assert intent.type == "previous"

    def test_pause_command(self):
        intent = self.router.resolve("pause", self.media)
        assert intent.type == "pause"

    def test_play_command(self):
        intent = self.router.resolve("reprend la lecture", self.media)
        assert intent.type == "play"

    def test_station_selection(self):
        intent = self.router.resolve("mets Classic FM", self.media)
        assert intent.type == "select_station"
        assert intent.value == "Classic FM"

    def test_battery_status(self):
        intent = self.router.resolve("quelle est la batterie", self.media)
        assert intent.type == "battery_status"

    def test_wifi_status(self):
        intent = self.router.resolve("quel est le wifi", self.media)
        assert intent.type == "wifi_status"

    def test_what_is_playing(self):
        intent = self.router.resolve("c est quoi la musique en cours", self.media)
        assert intent.type == "what_is_playing"

    def test_switch_mode_radio(self):
        intent = self.router.resolve("passe en radio", self.media)
        assert intent.type == "switch_mode"
        assert intent.value == "radio"

    def test_switch_mode_mp3(self):
        intent = self.router.resolve("mode mp3", self.media)
        assert intent.type == "switch_mode"
        assert intent.value == "mp3"

    def test_unrecognized_returns_none_type(self):
        intent = self.router.resolve("quel est le sens de la vie", self.media)
        assert intent.type == "none"


# ── Unit tests for helper functions ──


class TestHelperFunctions:
    def test_battery_reply_with_value(self):
        media = DeviceCurrentMedia(battery_pct=75)
        assert "75%" in _battery_reply(media)

    def test_battery_reply_without_value(self):
        media = DeviceCurrentMedia()
        assert "pas encore" in _battery_reply(media)

    def test_wifi_reply_with_ssid_and_rssi(self):
        media = DeviceCurrentMedia(wifi_ssid="Home", wifi_rssi=-42)
        reply = _wifi_reply(media)
        assert "Home" in reply
        assert "-42" in reply

    def test_wifi_reply_with_ssid_only(self):
        media = DeviceCurrentMedia(wifi_ssid="Home")
        reply = _wifi_reply(media)
        assert "Home" in reply
        assert "dBm" not in reply

    def test_wifi_reply_without_ssid(self):
        media = DeviceCurrentMedia()
        assert "pas encore" in _wifi_reply(media)

    def test_what_is_playing_radio(self):
        media = DeviceCurrentMedia(mode="radio", station="Jazz FM")
        assert "Jazz FM" in _what_is_playing_reply(media)

    def test_what_is_playing_mp3(self):
        media = DeviceCurrentMedia(mode="mp3", track="Song.mp3")
        assert "Song.mp3" in _what_is_playing_reply(media)

    def test_what_is_playing_nothing(self):
        media = DeviceCurrentMedia()
        assert "Rien" in _what_is_playing_reply(media)

    def test_player_action_pause(self):
        intent = DeviceIntent(type="pause")
        media = DeviceCurrentMedia(playing=True)
        assert _player_action_for(intent, media) == "none"

    def test_player_action_media_intent(self):
        intent = DeviceIntent(type="next")
        media = DeviceCurrentMedia(playing=True)
        assert _player_action_for(intent, media) == "duck"

    def test_player_action_stop_resume_when_playing(self):
        intent = DeviceIntent(type="none")
        media = DeviceCurrentMedia(playing=True)
        assert _player_action_for(intent, media) == "stop_resume"

    def test_player_action_none_when_not_playing(self):
        intent = DeviceIntent(type="none")
        media = DeviceCurrentMedia(playing=False)
        assert _player_action_for(intent, media) == "none"


class TestWavDuration:
    def test_valid_wav(self):
        wav_bytes = _make_wav_bytes(duration_s=1.0, sample_rate=16000)
        ms = _wav_duration_ms(wav_bytes)
        assert ms is not None
        assert 950 <= ms <= 1050  # roughly 1000ms

    def test_invalid_bytes_returns_none(self):
        assert _wav_duration_ms(b"not a wav") is None

    def test_empty_bytes_returns_none(self):
        assert _wav_duration_ms(b"") is None


# ── Original integration-style tests ──


class FakeAudioBridge:
    def __init__(self, *, transcript: str, wav_payload: bytes = b"RIFFfake") -> None:
        self.transcript = transcript
        self.wav_payload = wav_payload
        self.transcribe_calls: list[dict[str, object]] = []
        self.synthesize_calls: list[str] = []

    async def transcribe(
        self,
        *,
        audio_bytes: bytes,
        filename: str,
        content_type: str,
        language: str | None = None,
    ) -> str:
        self.transcribe_calls.append(
            {
                "audio_bytes": audio_bytes,
                "filename": filename,
                "content_type": content_type,
                "language": language,
            }
        )
        return self.transcript

    async def synthesize(self, *, text: str) -> bytes:
        self.synthesize_calls.append(text)
        return self.wav_payload


class FakeRouter:
    def __init__(
        self,
        *,
        available_providers: list[str],
        responses: dict[str, LLMResponse] | None = None,
        failures: set[str] | None = None,
    ) -> None:
        self.available_providers = available_providers
        self.responses = responses or {}
        self.failures = failures or set()
        self.calls: list[dict[str, object]] = []

    async def send(
        self,
        messages: list[dict],
        *,
        strategy,
        provider: str | None = None,
        model: str | None = None,
        system: str | None = None,
        response_format: dict | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        self.calls.append(
            {
                "messages": messages,
                "strategy": strategy,
                "provider": provider,
                "model": model,
                "system": system,
                "response_format": response_format,
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
        )
        if provider in self.failures:
            raise RuntimeError(f"{provider} unavailable")
        if provider in self.responses:
            return self.responses[provider]
        raise RuntimeError(f"unexpected provider {provider}")


@pytest.fixture(autouse=True)
def _clean_api_keys():
    for key in get_active_api_keys():
        remove_api_key(key)
    yield
    for key in get_active_api_keys():
        remove_api_key(key)


@asynccontextmanager
async def _client(device_voice: DeviceVoiceService):
    with (
        patch("mascarade.auth.is_valid_api_key", return_value=True),
        patch("mascarade.auth._resolve_role", return_value="admin"),
    ):
        async with app.router.lifespan_context(app):
            original_device_voice = app.state.device_voice
            app.state.device_voice = device_voice
            try:
                transport = httpx.ASGITransport(app=app)
                async with httpx.AsyncClient(
                    transport=transport,
                    base_url="http://testserver",
                ) as client:
                    yield client
            finally:
                app.state.device_voice = original_device_voice


@pytest.mark.asyncio
@pytest.mark.skip(reason="device voice session route not yet implemented on server")
async def test_device_voice_session_handles_local_volume_intent():
    add_api_key("device-test-key!")
    fake_audio = FakeAudioBridge(transcript="volume 30", wav_payload=b"RIFFvolume")
    fake_router = FakeRouter(available_providers=["claude"])
    service = DeviceVoiceService(router=fake_router, audio_bridge=fake_audio)

    async with _client(service) as client:
        response = await client.post(
            "/device/v1/voice/session",
            headers={"Authorization": "Bearer device-test-key!"},
            files={"audio": ("audio.wav", b"RIFF\x00\x00fake", "audio/wav")},
            data={
                "device_id": "round-box-1",
                "mode": "radio",
                "current_media": (
                    '{"mode":"radio","playing":true,"station":"BBC World Service",'
                    '"volume":24,"available_stations":["BBC World Service","Classic FM"]}'
                ),
            },
        )

        assert response.status_code == 200
        body = response.json()
        assert body["ok"] is True
        assert body["intent"]["type"] == "set_volume"
        assert body["intent"]["value"] == 30
        assert body["player_action"] == "duck"
        assert body["reply_audio_url"].endswith(".wav")

        audio_reply = await client.get(
            body["reply_audio_url"].replace("http://testserver", ""),
            headers={"Authorization": "Bearer device-test-key!"},
        )

    assert audio_reply.status_code == 200
    assert audio_reply.content == b"RIFFvolume"
    assert fake_audio.synthesize_calls == ["D'accord, volume 30."]


@pytest.mark.asyncio
@pytest.mark.skip(reason="device voice session/player event routes not yet implemented on server")
async def test_player_event_state_is_reused_for_now_playing_questions():
    add_api_key("device-test-key!")
    fake_audio = FakeAudioBridge(
        transcript="c'est quoi la musique en cours ?", wav_payload=b"RIFFstate"
    )
    fake_router = FakeRouter(available_providers=["claude"])
    service = DeviceVoiceService(router=fake_router, audio_bridge=fake_audio)

    async with _client(service) as client:
        event_response = await client.post(
            "/device/v1/player/event",
            headers={"Authorization": "Bearer device-test-key!"},
            json={
                "device_id": "round-box-1",
                "event": "playback_started",
                "mode": "radio",
                "playing": True,
                "station": "BBC World Service",
                "volume": 21,
                "wifi_ssid": "Maison",
                "battery_pct": 82,
            },
        )
        assert event_response.status_code == 200

        response = await client.post(
            "/device/v1/voice/session",
            headers={"Authorization": "Bearer device-test-key!"},
            files={"audio.wav": ("audio.wav", b"RIFF\x00\x00state", "audio/wav")},
            data={
                "device_id": "round-box-1",
                "mode": "radio",
                "current_media": "{}",
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["intent"]["type"] == "what_is_playing"
    assert "BBC World Service" in body["reply_text"]


@pytest.mark.asyncio
async def test_service_falls_back_from_claude_to_local_provider():
    fake_audio = FakeAudioBridge(transcript="donne-moi les infos du jour")
    fake_router = FakeRouter(
        available_providers=["claude", "apple-coreml"],
        responses={
            "apple-coreml": LLMResponse(
                content="Voici un résumé très bref des infos du jour.",
                model="qwen3.5-4b-onnx-q4f16",
                provider="apple-coreml",
                usage={"input_tokens": 12, "output_tokens": 8},
            )
        },
        failures={"claude"},
    )
    service = DeviceVoiceService(router=fake_router, audio_bridge=fake_audio)

    result = await service.handle_session(
        device_id="round-box-1",
        mode="radio",
        current_media_payload={
            "mode": "radio",
            "playing": True,
            "station": "BBC World Service",
        },
        audio_bytes=b"RIFF\x00\x00news",
        filename="audio.wav",
        content_type="audio/wav",
        request_base_url="http://testserver/",
    )

    assert result.ok is True
    assert result.provider == "apple-coreml"
    assert result.player_action == "stop_resume"
    assert fake_router.calls[0]["provider"] == "claude"
    assert fake_router.calls[1]["provider"] == "apple-coreml"


@pytest.mark.asyncio
@pytest.mark.skip(reason="device voice session route not yet implemented on server")
async def test_device_voice_routes_require_authentication():
    add_api_key("device-test-key!")
    fake_audio = FakeAudioBridge(transcript="volume 10")
    fake_router = FakeRouter(available_providers=["claude"])
    service = DeviceVoiceService(router=fake_router, audio_bridge=fake_audio)

    async with _client(service) as client:
        response = await client.post(
            "/device/v1/voice/session",
            files={"audio": ("audio.wav", b"RIFF\x00\x00auth", "audio/wav")},
            data={
                "device_id": "round-box-1",
                "mode": "radio",
                "current_media": "{}",
            },
        )

    assert response.status_code == 401
