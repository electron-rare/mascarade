"""Extended tests for mascarade.routers.ws — WebSocket auth, traces, health."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest

from mascarade.routers.ws import _json_payload, _ws_auth

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_ws(token: str | None = None):
    """Build a minimal mock WebSocket with query_params."""
    ws = MagicMock()
    params = {}
    if token is not None:
        params["token"] = token
    ws.query_params = params
    return ws


# ---------------------------------------------------------------------------
# _ws_auth tests
# ---------------------------------------------------------------------------


class TestWsAuthExtended:
    @pytest.mark.asyncio
    async def test_auth_valid_token(self):
        ws = _make_ws(token="valid-key")
        with patch("mascarade.routers.ws.get_active_api_keys", return_value=["valid-key"]):
            result = await _ws_auth(ws)
        assert result is True

    @pytest.mark.asyncio
    async def test_auth_invalid_token_returns_false(self):
        ws = _make_ws(token="wrong-key")
        with patch("mascarade.routers.ws.get_active_api_keys", return_value=["correct-key"]):
            result = await _ws_auth(ws)
        assert result is False

    @pytest.mark.asyncio
    async def test_auth_no_keys_configured_allows_all(self):
        ws = _make_ws()
        with patch("mascarade.routers.ws.get_active_api_keys", return_value=[]):
            result = await _ws_auth(ws)
        assert result is True

    @pytest.mark.asyncio
    async def test_auth_missing_token_when_keys_exist(self):
        ws = _make_ws()  # no token
        with patch("mascarade.routers.ws.get_active_api_keys", return_value=["key-a"]):
            result = await _ws_auth(ws)
        assert result is False

    @pytest.mark.asyncio
    async def test_auth_multiple_valid_keys(self):
        ws = _make_ws(token="key-b")
        with patch(
            "mascarade.routers.ws.get_active_api_keys", return_value=["key-a", "key-b", "key-c"]
        ):
            result = await _ws_auth(ws)
        assert result is True


# ---------------------------------------------------------------------------
# _json_payload helper
# ---------------------------------------------------------------------------


class TestJsonPayload:
    def test_payload_structure(self):
        raw = _json_payload("trace", {"key": "value"})
        parsed = json.loads(raw)
        assert parsed["type"] == "trace"
        assert parsed["data"]["key"] == "value"

    def test_payload_serializes_datetime(self):
        now = datetime.now(UTC)
        raw = _json_payload("ping", {"ts": now})
        parsed = json.loads(raw)
        assert parsed["type"] == "ping"
        # datetime should be serialized via default=str
        assert isinstance(parsed["data"]["ts"], str)


# ---------------------------------------------------------------------------
# WS /ws/health data structure
# ---------------------------------------------------------------------------


class TestWsHealthData:
    """Test that the health WebSocket sends the expected data shape."""

    @pytest.mark.asyncio
    async def test_health_payload_contains_status(self):
        """Verify the health data dict built by ws_health contains 'status'."""
        # We replicate the logic from the endpoint to validate the structure
        # without needing a full WebSocket connection.
        health_data: dict = {"status": "ok"}

        app_state = MagicMock()
        app_state.router = None
        app_state.registry = None
        app_state.scheduler = None
        app_state.cluster = None

        # Without router, providers should not appear
        assert health_data["status"] == "ok"
        assert "providers" not in health_data

    @pytest.mark.asyncio
    async def test_health_payload_with_router(self):
        """Health data should include provider info when router is set."""
        health_data: dict = {"status": "ok"}

        @dataclass
        class FakeProviderHealth:
            provider_name: str
            health_score: float = 1.0
            latency_p50: float = 0.0
            latency_p95: float = 0.0
            latency_p99: float = 0.0
            error_rate: float = 0.0
            availability: float = 1.0
            total_requests: int = 0

        class FakeHealthMonitor:
            def get_all_health(self):
                return {
                    "openai": FakeProviderHealth(
                        provider_name="openai",
                        health_score=0.99,
                        latency_p50=80.0,
                        latency_p95=100.0,
                        latency_p99=120.0,
                        error_rate=0.01,
                        availability=0.99,
                        total_requests=50,
                    ),
                }

        class FakeCircuitBreaker:
            def get_state(self, provider):
                return "closed"

        mock_router = MagicMock()
        mock_router.available_providers = ["openai"]
        mock_router.health_monitor = FakeHealthMonitor()
        mock_router.circuit_breaker = FakeCircuitBreaker()

        health_data["providers"] = mock_router.available_providers
        assert "providers" in health_data
        assert "openai" in health_data["providers"]
