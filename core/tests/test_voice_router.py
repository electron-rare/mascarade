"""Tests for mascarade.routers.voice — Voice Bridge WebSocket endpoint."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from mascarade.routers.voice import (
    _query_llm,
    _text_to_speech,
    _ws_auth,
)


# ---------------------------------------------------------------------------
# Auth helper tests
# ---------------------------------------------------------------------------


def _make_ws(token: str | None = None):
    ws = MagicMock()
    params = {}
    if token is not None:
        params["token"] = token
    ws.query_params = params
    return ws


class TestVoiceWsAuth:
    @pytest.mark.asyncio
    async def test_auth_no_keys(self):
        ws = _make_ws()
        with patch("mascarade.routers.voice.get_active_api_keys", return_value=[]):
            assert await _ws_auth(ws) is True

    @pytest.mark.asyncio
    async def test_auth_valid_token(self):
        ws = _make_ws(token="good-key")
        with patch("mascarade.routers.voice.get_active_api_keys", return_value=["good-key"]):
            assert await _ws_auth(ws) is True

    @pytest.mark.asyncio
    async def test_auth_invalid_token(self):
        ws = _make_ws(token="bad-key")
        with patch("mascarade.routers.voice.get_active_api_keys", return_value=["good-key"]):
            assert await _ws_auth(ws) is False

    @pytest.mark.asyncio
    async def test_auth_missing_token(self):
        ws = _make_ws()
        with patch("mascarade.routers.voice.get_active_api_keys", return_value=["key"]):
            assert await _ws_auth(ws) is False


# ---------------------------------------------------------------------------
# LLM query tests
# ---------------------------------------------------------------------------


class TestQueryLlm:
    @pytest.mark.asyncio
    async def test_direct_router_dispatch(self):
        mock_router = AsyncMock()
        mock_router.route = AsyncMock(return_value={"content": "Eureka!"})

        result = await _query_llm("Bonjour professeur", llm_router=mock_router)
        assert result == "Eureka!"
        mock_router.route.assert_awaited_once()
        call_kwargs = mock_router.route.call_args
        messages = call_kwargs.kwargs.get("messages") or call_kwargs[1].get("messages")
        assert any("Zacus" in m["content"] for m in messages if m["role"] == "system")

    @pytest.mark.asyncio
    async def test_router_dispatch_fallback_on_error(self):
        """When router raises, falls back to HTTP."""
        mock_router = AsyncMock()
        mock_router.route = AsyncMock(side_effect=RuntimeError("no provider"))

        mock_response = httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": "Fallback response"}}],
            },
            request=httpx.Request("POST", "http://test"),
        )

        with patch("mascarade.routers.voice.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            result = await _query_llm("test", llm_router=mock_router)
            assert result == "Fallback response"

    @pytest.mark.asyncio
    async def test_no_router_http_error_returns_fallback(self):
        """When HTTP also fails, returns a safe fallback string."""
        with patch("mascarade.routers.voice.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(side_effect=httpx.ConnectError("refused"))
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            result = await _query_llm("test", llm_router=None)
            assert isinstance(result, str)
            assert len(result) > 0


# ---------------------------------------------------------------------------
# TTS tests
# ---------------------------------------------------------------------------


class TestTextToSpeech:
    @pytest.mark.asyncio
    async def test_tts_disabled_when_url_empty(self):
        with patch("mascarade.routers.voice.settings") as mock_settings:
            mock_settings.voice_bridge_tts_url = ""
            result = await _text_to_speech("Bonjour")
            assert result is None

    @pytest.mark.asyncio
    async def test_tts_returns_audio_bytes(self):
        fake_audio = b"\x00" * 1024

        mock_response = httpx.Response(
            200,
            content=fake_audio,
            request=httpx.Request("POST", "http://test"),
        )

        with patch("mascarade.routers.voice.settings") as mock_settings, \
             patch("mascarade.routers.voice.httpx.AsyncClient") as mock_client_cls:
            mock_settings.voice_bridge_tts_url = "http://fake:8000/v1/audio/speech"
            mock_settings.voice_bridge_tts_voice = "alloy"

            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            result = await _text_to_speech("Bonjour")
            assert result == fake_audio

    @pytest.mark.asyncio
    async def test_tts_http_error_returns_none(self):
        mock_response = httpx.Response(
            500,
            request=httpx.Request("POST", "http://test"),
        )

        with patch("mascarade.routers.voice.settings") as mock_settings, \
             patch("mascarade.routers.voice.httpx.AsyncClient") as mock_client_cls:
            mock_settings.voice_bridge_tts_url = "http://fake:8000/v1/audio/speech"
            mock_settings.voice_bridge_tts_voice = "alloy"

            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            result = await _text_to_speech("Bonjour")
            assert result is None
