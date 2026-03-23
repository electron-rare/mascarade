"""Tests for mascarade.routers.ws — WebSocket auth helper."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from mascarade.routers.ws import _ws_auth


def _make_ws(token: str | None = None):
    """Build a minimal mock WebSocket with query_params."""
    ws = MagicMock()
    params = {}
    if token is not None:
        params["token"] = token
    ws.query_params = params
    return ws


class TestWsAuth:
    @pytest.mark.asyncio
    async def test_auth_no_keys_configured(self):
        """When no API keys are configured, auth is effectively disabled."""
        ws = _make_ws()
        with patch("mascarade.routers.ws.get_active_api_keys", return_value=[]):
            result = await _ws_auth(ws)
        assert result is True

    @pytest.mark.asyncio
    async def test_auth_valid_token(self):
        ws = _make_ws(token="valid-key-123")
        with patch(
            "mascarade.routers.ws.get_active_api_keys", return_value=["valid-key-123"]
        ):
            result = await _ws_auth(ws)
        assert result is True

    @pytest.mark.asyncio
    async def test_auth_invalid_token(self):
        ws = _make_ws(token="wrong-key")
        with patch(
            "mascarade.routers.ws.get_active_api_keys", return_value=["valid-key-123"]
        ):
            result = await _ws_auth(ws)
        assert result is False

    @pytest.mark.asyncio
    async def test_auth_missing_token_when_keys_configured(self):
        ws = _make_ws()  # no token
        with patch(
            "mascarade.routers.ws.get_active_api_keys", return_value=["some-key"]
        ):
            result = await _ws_auth(ws)
        assert result is False

    @pytest.mark.asyncio
    async def test_auth_token_not_in_active_keys(self):
        ws = _make_ws(token="expired-key")
        with patch(
            "mascarade.routers.ws.get_active_api_keys", return_value=["key-a", "key-b"]
        ):
            result = await _ws_auth(ws)
        assert result is False
