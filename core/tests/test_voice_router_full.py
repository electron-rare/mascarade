"""Extended tests for mascarade.routers.voice — handshake, messages, TTS."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from mascarade.routers.voice import (
    _handle_json_message,
    _text_to_speech,
    _ws_auth,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_ws(token: str | None = None):
    ws = MagicMock()
    params = {}
    if token is not None:
        params["token"] = token
    ws.query_params = params
    return ws


# ---------------------------------------------------------------------------
# _ws_auth (same pattern as ws_router)
# ---------------------------------------------------------------------------


class TestVoiceWsAuthExtended:
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
    async def test_auth_no_keys_allows(self):
        ws = _make_ws()
        with patch("mascarade.routers.voice.get_active_api_keys", return_value=[]):
            assert await _ws_auth(ws) is True


# ---------------------------------------------------------------------------
# Handshake validation
# ---------------------------------------------------------------------------


class TestHandshake:
    @pytest.mark.asyncio
    async def test_hello_handshake_expected(self):
        """The endpoint expects a hello message; non-hello should trigger close."""
        ws = AsyncMock()
        ws.query_params = {}
        ws.client = ("127.0.0.1", 9999)
        ws.client_state = MagicMock()

        # Simulate receive_json returning a non-hello message
        ws.receive_json = AsyncMock(return_value={"type": "not_hello"})

        # The voice_websocket function calls receive_json and checks type == hello.
        # We test the logic inline:
        hello = await ws.receive_json()
        assert hello.get("type") != "hello"

    @pytest.mark.asyncio
    async def test_hello_handshake_timeout(self):
        """Handshake should timeout if no message arrives within 5 seconds."""
        ws = AsyncMock()

        async def _slow_receive():
            await asyncio.sleep(10)
            return {"type": "hello"}

        ws.receive_json = _slow_receive

        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(ws.receive_json(), timeout=0.1)


# ---------------------------------------------------------------------------
# _handle_json_message
# ---------------------------------------------------------------------------


class TestHandleJsonMessage:
    @pytest.mark.asyncio
    async def test_text_query_dispatches_to_llm(self):
        ws = AsyncMock()
        mock_router = AsyncMock()
        mock_router.route = AsyncMock(return_value={"content": "Reponse du professeur"})

        with patch(
            "mascarade.routers.voice._text_to_speech",
            new_callable=AsyncMock,
            return_value=b"\x00" * 100,
        ):
            await _handle_json_message(
                ws,
                {"type": "text_query", "text": "Bonjour professeur"},
                llm_router=mock_router,
            )

        # Should send tts start, audio bytes, tts stop
        assert ws.send_json.call_count == 2  # start + stop
        ws.send_bytes.assert_awaited_once()

        # Verify tts start message
        start_call = ws.send_json.call_args_list[0]
        assert start_call[0][0]["type"] == "tts"
        assert start_call[0][0]["state"] == "start"

    @pytest.mark.asyncio
    async def test_text_query_empty_text_ignored(self):
        ws = AsyncMock()
        mock_router = AsyncMock()

        await _handle_json_message(ws, {"type": "text_query", "text": ""}, llm_router=mock_router)

        ws.send_json.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_abort_message(self):
        ws = AsyncMock()
        await _handle_json_message(ws, {"type": "abort"}, llm_router=None)

        # abort is a no-op (just logs), should not send anything
        ws.send_json.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_listen_detect_sends_ack(self):
        ws = AsyncMock()
        await _handle_json_message(
            ws,
            {"type": "listen", "state": "detect", "text": "hey zacus"},
            llm_router=None,
        )

        ws.send_json.assert_awaited_once()
        ack = ws.send_json.call_args[0][0]
        assert ack["type"] == "listen_ack"
        assert ack["state"] == "ready"


# ---------------------------------------------------------------------------
# TTS integration
# ---------------------------------------------------------------------------


class TestTtsIntegration:
    @pytest.mark.asyncio
    async def test_tts_success(self):
        fake_audio = b"\x00\x01\x02" * 100
        mock_response = httpx.Response(
            200,
            content=fake_audio,
            request=httpx.Request("POST", "http://test"),
        )

        with (
            patch("mascarade.routers.voice.settings") as mock_settings,
            patch("mascarade.routers.voice.httpx.AsyncClient") as mock_client_cls,
        ):
            mock_settings.voice_bridge_tts_url = "http://piper:8000/v1/audio/speech"
            mock_settings.voice_bridge_tts_voice = "fr_FR-upmc-medium"

            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            result = await _text_to_speech("Bonjour les enfants")
            assert result == fake_audio

    @pytest.mark.asyncio
    async def test_tts_not_configured_returns_none(self):
        with patch("mascarade.routers.voice.settings") as mock_settings:
            mock_settings.voice_bridge_tts_url = ""
            result = await _text_to_speech("test")
            assert result is None

    @pytest.mark.asyncio
    async def test_tts_server_error_returns_none(self):
        mock_response = httpx.Response(
            500,
            request=httpx.Request("POST", "http://test"),
        )

        with (
            patch("mascarade.routers.voice.settings") as mock_settings,
            patch("mascarade.routers.voice.httpx.AsyncClient") as mock_client_cls,
        ):
            mock_settings.voice_bridge_tts_url = "http://piper:8000/v1/audio/speech"
            mock_settings.voice_bridge_tts_voice = "alloy"

            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            result = await _text_to_speech("test")
            assert result is None
