from __future__ import annotations

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock

import httpx
import pytest

from mascarade.auth import add_api_key, get_active_api_keys, remove_api_key
from mascarade.server import app


@pytest.fixture(autouse=True)
def _clean_api_keys():
    for key in get_active_api_keys():
        remove_api_key(key)
    yield
    for key in get_active_api_keys():
        remove_api_key(key)


@asynccontextmanager
async def _client():
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            yield client


@pytest.mark.asyncio
async def test_knowledge_base_search_route_uses_mcp_client(
    monkeypatch: pytest.MonkeyPatch,
):
    add_api_key("test-key-001")
    fake_mcp = AsyncMock()
    fake_mcp.knowledge_base_search.return_value = {
        "results": [
            {"id": "memo-1", "title": "Release note", "url": "http://kb/memo-1"}
        ],
        "provider": "memos",
        "provider_label": "Memos",
    }
    monkeypatch.setattr("mascarade.server.knowledge_base_auth_configured", lambda: True)

    async with _client() as client:
        app.state.mcp = fake_mcp
        response = await client.get(
            "/knowledge-base/search?q=release&project_id=project-alpha",
            headers={"Authorization": "Bearer test-key-001"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["provider"] == "memos"
    fake_mcp.knowledge_base_search.assert_awaited_once_with(
        "release",
        limit=10,
        project_id="project-alpha",
        federation_scope=(),
        knowledge_scope="project",
    )


@pytest.mark.asyncio
async def test_knowledge_base_search_route_rejects_missing_project_id(
    monkeypatch: pytest.MonkeyPatch,
):
    add_api_key("test-key-001")
    fake_mcp = AsyncMock()
    monkeypatch.setattr("mascarade.server.knowledge_base_auth_configured", lambda: True)

    async with _client() as client:
        app.state.mcp = fake_mcp
        response = await client.get(
            "/knowledge-base/search?q=release",
            headers={"Authorization": "Bearer test-key-001"},
        )

    assert response.status_code == 422
    fake_mcp.knowledge_base_search.assert_not_awaited()


@pytest.mark.asyncio
async def test_knowledge_base_search_route_forwards_project_scope(
    monkeypatch: pytest.MonkeyPatch,
):
    add_api_key("test-key-001")
    fake_mcp = AsyncMock()
    fake_mcp.knowledge_base_search.return_value = {
        "results": [
            {"id": "chunk-1", "title": "Musique concrete", "url": "http://kb/chunk-1"}
        ],
        "provider": "kxkm",
        "provider_label": "kxkm",
    }
    monkeypatch.setattr("mascarade.server.knowledge_base_auth_configured", lambda: True)

    async with _client() as client:
        app.state.mcp = fake_mcp
        response = await client.get(
            "/knowledge-base/search?q=musique&limit=5&project_id=project-alpha&federation_scope=project-alpha,project-beta&knowledge_scope=federated",
            headers={"Authorization": "Bearer test-key-001"},
        )

    assert response.status_code == 200
    fake_mcp.knowledge_base_search.assert_awaited_once_with(
        "musique",
        limit=5,
        project_id="project-alpha",
        federation_scope=("project-alpha", "project-beta"),
        knowledge_scope="federated",
    )


@pytest.mark.asyncio
async def test_knowledge_scribe_push_uses_mcp_and_preserves_run_id(
    monkeypatch: pytest.MonkeyPatch,
):
    add_api_key("test-key-001")
    fake_mcp = AsyncMock()
    fake_mcp.knowledge_base_append.return_value = {
        "provider": "memos",
        "provider_label": "Memos",
    }
    monkeypatch.setattr("mascarade.server.knowledge_base_auth_configured", lambda: True)

    class _FakeAgent:
        async def run(
            self,
            prompt,
            *,
            router,
            context=None,
            project_id=None,
            federation_scope=None,
            knowledge_scope="project",
        ):
            return type(
                "Response",
                (),
                {
                    "content": "formatted note",
                    "model": "mock-model",
                    "provider": "mock-provider",
                    "usage": {"input_tokens": 1, "output_tokens": 2},
                },
            )()

    async with _client() as client:
        app.state.mcp = fake_mcp
        monkeypatch.setattr(app.state.registry, "get", lambda name: _FakeAgent())
        response = await client.post(
            "/agents/knowledge-scribe/run-and-push",
            headers={"Authorization": "Bearer test-key-001"},
            json={
                "messages": [{"role": "user", "content": "Draft the release note"}],
                "push_to": "memo-7",
                "run_id": "run-kb-007",
                "project_id": "project-alpha",
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["pushed_to_knowledge_base"] is True
    assert payload["run_id"] == "run-kb-007"
    fake_mcp.knowledge_base_append.assert_awaited_once()
    call = fake_mcp.knowledge_base_append.await_args
    assert call.args[:2] == ("memo-7", "formatted note")
    assert call.kwargs["run_id"] == "run-kb-007"
