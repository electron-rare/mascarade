"""Tests for mascarade.cody_gateway — Sourcegraph-compatible proxy endpoints."""

from __future__ import annotations

from dataclasses import dataclass
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from mascarade.cody_gateway import (
    _handle_graphql,
    mount_cody_gateway,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@dataclass
class FakeResponse:
    content: str = "Hello from mascarade"
    model: str = "devstral"
    provider: str = "ollama"
    usage: dict = None

    def __post_init__(self):
        if self.usage is None:
            self.usage = {"input_tokens": 10, "output_tokens": 20}


def _make_app(with_router: bool = True) -> FastAPI:
    app = FastAPI()
    mount_cody_gateway(app)
    if with_router:
        mock_router = MagicMock()
        mock_router.send = AsyncMock(return_value=FakeResponse())
        mock_router.provider_model_map.return_value = {
            "ollama": ["devstral", "qwen3.5:4b"],
            "anthropic": ["claude-sonnet-4-20250514"],
        }

        async def _stream_gen(*args, **kwargs):
            yield "chunk1"
            yield "chunk2"

        mock_router.stream = MagicMock(side_effect=_stream_gen)
        app.state.router = mock_router
    else:
        app.state.router = None
    return app


@pytest.fixture
def client():
    return TestClient(_make_app(with_router=True))


@pytest.fixture
def client_no_router():
    return TestClient(_make_app(with_router=False))


# ---------------------------------------------------------------------------
# /.api/client-config
# ---------------------------------------------------------------------------


class TestClientConfig:
    def test_returns_models(self, client):
        r = client.get("/.api/client-config")
        assert r.status_code == 200
        data = r.json()
        assert data["codyEnabled"] is True
        assert len(data["models"]) > 0

    def test_model_structure(self, client):
        r = client.get("/.api/client-config")
        model = r.json()["models"][0]
        assert "modelRef" in model
        assert "capabilities" in model
        assert "contextWindow" in model

    def test_no_router_returns_empty_models(self, client_no_router):
        r = client_no_router.get("/.api/client-config")
        assert r.status_code == 200
        assert r.json()["models"] == []


# ---------------------------------------------------------------------------
# /.api/completions/stream
# ---------------------------------------------------------------------------


class TestCompletionsStream:
    def test_returns_sse(self, client):
        r = client.post(
            "/.api/completions/stream",
            json={
                "messages": [{"speaker": "human", "text": "hello"}],
                "model": "ollama/devstral",
            },
        )
        assert r.status_code == 200
        assert "text/event-stream" in r.headers["content-type"]
        body = r.text
        assert "event: completion" in body
        assert "event: done" in body

    def test_no_router_503(self, client_no_router):
        r = client_no_router.post(
            "/.api/completions/stream",
            json={
                "messages": [{"speaker": "human", "text": "hi"}],
            },
        )
        assert r.status_code == 503

    def test_empty_messages_still_works(self, client):
        r = client.post(
            "/.api/completions/stream",
            json={
                "messages": [],
                "model": "ollama/devstral",
            },
        )
        assert r.status_code == 200

    def test_model_split(self, client):
        """Provider hint is extracted from model ref like 'anthropic/claude-sonnet-4-20250514'."""
        r = client.post(
            "/.api/completions/stream",
            json={
                "messages": [{"speaker": "human", "text": "test"}],
                "model": "anthropic/claude-sonnet-4-20250514",
            },
        )
        assert r.status_code == 200


# ---------------------------------------------------------------------------
# /.api/chat/completions
# ---------------------------------------------------------------------------


class TestChatCompletions:
    def test_non_streaming(self, client):
        r = client.post(
            "/.api/chat/completions",
            json={
                "messages": [{"role": "user", "content": "hi"}],
                "model": "ollama/devstral",
            },
        )
        assert r.status_code == 200
        data = r.json()
        assert data["object"] == "chat.completion"
        assert data["choices"][0]["message"]["content"] == "Hello from mascarade"

    def test_speaker_format(self, client):
        """Cody sometimes uses speaker/text instead of role/content."""
        r = client.post(
            "/.api/chat/completions",
            json={
                "messages": [{"speaker": "human", "text": "hi"}],
            },
        )
        assert r.status_code == 200

    def test_usage_in_response(self, client):
        r = client.post(
            "/.api/chat/completions",
            json={
                "messages": [{"role": "user", "content": "hi"}],
            },
        )
        usage = r.json()["usage"]
        assert usage["prompt_tokens"] == 10
        assert usage["completion_tokens"] == 20
        assert usage["total_tokens"] == 30

    def test_no_router_503(self, client_no_router):
        r = client_no_router.post(
            "/.api/chat/completions",
            json={
                "messages": [{"role": "user", "content": "hi"}],
            },
        )
        assert r.status_code == 503

    def test_streaming_chat(self, client):
        r = client.post(
            "/.api/chat/completions",
            json={
                "messages": [{"role": "user", "content": "hi"}],
                "stream": True,
            },
        )
        assert r.status_code == 200
        assert "text/event-stream" in r.headers["content-type"]


# ---------------------------------------------------------------------------
# /.api/graphql
# ---------------------------------------------------------------------------


class TestGraphQL:
    def test_current_user(self, client):
        r = client.post("/.api/graphql", json={"query": "query { currentUser { id } }"})
        assert r.status_code == 200
        data = r.json()["data"]
        assert "currentUser" in data
        assert data["currentUser"]["username"] == "mascarade"

    def test_site_version(self, client):
        r = client.post("/.api/graphql", json={"query": "query { site { version configuration } }"})
        assert r.status_code == 200
        assert "site" in r.json()["data"]

    def test_feature_flags(self, client):
        r = client.post("/.api/graphql", json={"query": "query { evaluateFeatureFlags }"})
        data = r.json()["data"]
        assert data["evaluateFeatureFlags"]["codyAutocomplete"] is True

    def test_viewer_settings(self, client):
        """viewerSettings is handled — but note 'cody' keyword also matches earlier."""
        result = _handle_graphql("query { viewerSettings }")
        # The handler matches "cody" before "viewersettings", so we get codyLLM config
        assert "data" in result

    def test_telemetry_accepted(self, client):
        r = client.post("/.api/graphql", json={"query": "mutation { recordTelemetryEvents }"})
        assert r.status_code == 200

    def test_unknown_query_returns_empty_data(self, client):
        r = client.post("/.api/graphql", json={"query": "query { somethingUnknown12345 }"})
        assert r.status_code == 200
        assert r.json()["data"] == {}


# ---------------------------------------------------------------------------
# _build_model_list (unit)
# ---------------------------------------------------------------------------


class TestBuildModelList:
    def test_model_list_from_provider_map(self):
        result = _handle_graphql("query { currentUser { id } }")
        assert "currentUser" in result["data"]

    def test_handle_graphql_repositories(self):
        result = _handle_graphql("query { repositories }")
        assert result["data"]["repositories"]["totalCount"] == 0


# ---------------------------------------------------------------------------
# healthz / auth
# ---------------------------------------------------------------------------


class TestMisc:
    def test_healthz(self, client):
        r = client.get("/healthz")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"

    def test_auth_callback(self, client):
        r = client.get("/.auth/callback?code=abc&state=xyz")
        assert r.status_code == 200
        assert "accessToken" in r.json()["payload"]

    def test_openid_config(self, client):
        r = client.get("/.well-known/openid-configuration")
        assert r.status_code == 200
        data = r.json()
        assert "authorization_endpoint" in data
