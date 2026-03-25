"""Focused tests for the multi-project execution contract on current core routes."""

from __future__ import annotations

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import httpx
import pytest

from mascarade.auth import add_api_key, get_active_api_keys, remove_api_key
from mascarade.router.providers.base import LLMResponse
from mascarade.server import app

TEST_API_KEY = "test-multi-project-key-001"


class _FakeRouter:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    async def send(self, messages: list[dict], **kwargs) -> LLMResponse:
        self.calls.append({"messages": messages, **kwargs})
        return LLMResponse(
            content="ok",
            model="test-model",
            provider="test-provider",
            usage={"input_tokens": 1, "output_tokens": 1, "total_tokens": 2},
        )

    async def stream(self, messages: list[dict], **kwargs):
        self.calls.append({"messages": messages, **kwargs, "stream": True})
        yield "ok"

    async def fill_in_middle(self, prompt: str, **kwargs) -> LLMResponse:
        self.calls.append({"prompt": prompt, **kwargs, "fim": True})
        return LLMResponse(
            content="    return total\n",
            model="codestral-latest",
            provider="codestral",
            usage={},
        )


@pytest.fixture(autouse=True)
def _clean_api_keys():
    for key in get_active_api_keys():
        remove_api_key(key)
    add_api_key(TEST_API_KEY)
    yield
    for key in get_active_api_keys():
        remove_api_key(key)


@asynccontextmanager
async def _client(fake_router: _FakeRouter | None = None):
    with patch("mascarade.auth.is_valid_api_key", return_value=True), \
         patch("mascarade.auth._resolve_role", return_value="admin"):
        async with app.router.lifespan_context(app):
            original_router = app.state.router if fake_router else None
            if fake_router:
                app.state.router = fake_router
            try:
                transport = httpx.ASGITransport(app=app)
                async with httpx.AsyncClient(
                    transport=transport,
                    base_url="http://testserver",
                ) as client:
                    yield client
            finally:
                if original_router:
                    app.state.router = original_router


@pytest.mark.asyncio
async def test_v1_api_agent_run_forwards_project_scope():
    fake_router = _FakeRouter()
    agent_name = f"scope-agent-{uuid4().hex[:8]}"

    async with _client(fake_router) as client:
        create = await client.post(
            "/v1/api/agents",
            headers={"Authorization": f"Bearer {TEST_API_KEY}"},
            json={
                "name": agent_name,
                "description": "Test",
                "system_prompt": "You are helpful",
            },
        )
        assert create.status_code == 200

        response = await client.post(
            f"/v1/api/agents/{agent_name}/run",
            headers={"Authorization": f"Bearer {TEST_API_KEY}"},
            json={
                "project_id": "project-alpha",
                "knowledge_scope": "federated",
                "federation_scope": ["project-alpha", "project-beta"],
                "messages": [{"role": "user", "content": "Hello"}],
            },
        )

    assert response.status_code == 200
    assert fake_router.calls[0]["project_id"] == "project-alpha"
    assert fake_router.calls[0]["knowledge_scope"] == "federated"
    assert fake_router.calls[0]["federation_scope"] == ("project-alpha", "project-beta")


@pytest.mark.asyncio
async def test_v1_api_memory_add_scopes_user_to_project():
    calls: list[dict] = []

    async def mock_mem0_request(*args, **kwargs):
        calls.append(kwargs["json_data"])
        return {"id": "mem-123", "status": "created"}

    with patch("mascarade.routers.memory._mem0_request", side_effect=mock_mem0_request):
        async with _client() as client:
            response = await client.post(
                "/v1/api/memory/add",
                headers={"Authorization": f"Bearer {TEST_API_KEY}"},
                json={
                    "project_id": "project-alpha",
                    "user_id": "user-42",
                    "agent_id": "scope-agent",
                    "messages": [{"role": "user", "content": "remember this"}],
                },
            )

    assert response.status_code == 201
    assert calls[0]["user_id"] == "project-alpha:user-42"
    assert calls[0]["metadata"]["project_id"] == "project-alpha"
    assert calls[0]["metadata"]["agent_id"] == "scope-agent"


@pytest.mark.asyncio
async def test_v1_chat_completion_requires_project_scope():
    async with _client() as client:
        response = await client.post(
            "/v1/chat/completions",
            headers={"Authorization": f"Bearer {TEST_API_KEY}"},
            json={
                "model": "openai:gpt-4.1-mini",
                "messages": [{"role": "user", "content": "hello"}],
            },
        )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_knowledge_base_search_requires_project_scope(
    monkeypatch: pytest.MonkeyPatch,
):
    add_api_key(TEST_API_KEY)
    fake_mcp = AsyncMock()
    fake_mcp.knowledge_base_search.return_value = {"results": []}
    monkeypatch.setattr("mascarade.server.knowledge_base_auth_configured", lambda: True)

    async with _client() as client:
        app.state.mcp = fake_mcp
        response = await client.get(
            "/knowledge-base/search?q=release",
            headers={"Authorization": f"Bearer {TEST_API_KEY}"},
        )

    assert response.status_code == 422
    fake_mcp.knowledge_base_search.assert_not_awaited()


@pytest.mark.asyncio
async def test_v1_api_codestral_fim_uses_router_surface():
    fake_router = _FakeRouter()

    async with _client(fake_router) as client:
        response = await client.post(
            "/v1/api/providers/codestral/fim",
            headers={"Authorization": f"Bearer {TEST_API_KEY}"},
            json={
                "prompt": "def add(a, b):\n",
                "suffix": "\nresult = add(1, 2)\n",
                "max_tokens": 64,
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["provider"] == "codestral"
    assert fake_router.calls[0]["fim"] is True
    assert fake_router.calls[0]["max_tokens"] == 64


@pytest.mark.asyncio
async def test_v1_api_codestral_fim_requires_prompt():
    async with _client() as client:
        response = await client.post(
            "/v1/api/providers/codestral/fim",
            headers={"Authorization": f"Bearer {TEST_API_KEY}"},
            json={"prompt": "", "suffix": ""},
        )

    assert response.status_code == 422
