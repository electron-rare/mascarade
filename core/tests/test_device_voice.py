"""Tests for device voice routes and service behavior."""

from __future__ import annotations

from contextlib import asynccontextmanager
from unittest.mock import patch

import httpx
import pytest

from mascarade.auth import add_api_key, get_active_api_keys, remove_api_key
from mascarade.device_voice import DeviceVoiceService
from mascarade.router.providers.base import LLMResponse
from mascarade.server import app


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
    with patch("mascarade.auth.is_valid_api_key", return_value=True), \
         patch("mascarade.auth._resolve_role", return_value="admin"):
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
