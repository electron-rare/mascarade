from __future__ import annotations

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from fastapi import FastAPI

from mascarade.auth import add_api_key, get_active_api_keys, remove_api_key
from mascarade.routers.knowledge_base import router as kb_router


@pytest.fixture(autouse=True)
def _clean_api_keys():
    for key in get_active_api_keys():
        remove_api_key(key)
    yield
    for key in get_active_api_keys():
        remove_api_key(key)


def _make_app():
    """Create a standalone test app with the knowledge base router."""
    test_app = FastAPI()
    test_app.include_router(kb_router)
    # Provide a fake router and registry on app.state
    test_app.state.router = MagicMock()
    test_app.state.registry = MagicMock()
    return test_app


@asynccontextmanager
async def _client():
    with (
        patch("mascarade.auth.is_valid_api_key", return_value=True),
        patch("mascarade.auth._resolve_role", return_value="admin"),
    ):
        test_app = _make_app()
        transport = httpx.ASGITransport(app=test_app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            client._test_app = test_app
            yield client


@pytest.mark.asyncio
async def test_knowledge_base_search_route_uses_mcp_client(
    monkeypatch: pytest.MonkeyPatch,
):
    add_api_key("test-key-001")
    fake_mcp = AsyncMock()
    fake_mcp.knowledge_base_search.return_value = {
        "results": [{"id": "memo-1", "title": "Release note", "url": "http://kb/memo-1"}],
        "provider": "memos",
        "provider_label": "Memos",
    }
    monkeypatch.setattr("mascarade.routers.knowledge_base.knowledge_base_auth_configured", lambda: True)

    async with _client() as client:
        client._test_app.state.mcp = fake_mcp
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
    monkeypatch.setattr("mascarade.routers.knowledge_base.knowledge_base_auth_configured", lambda: True)

    async with _client() as client:
        client._test_app.state.mcp = fake_mcp
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
        "results": [{"id": "chunk-1", "title": "Musique concrete", "url": "http://kb/chunk-1"}],
        "provider": "kxkm",
        "provider_label": "kxkm",
    }
    monkeypatch.setattr("mascarade.routers.knowledge_base.knowledge_base_auth_configured", lambda: True)

    async with _client() as client:
        client._test_app.state.mcp = fake_mcp
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
    monkeypatch.setattr("mascarade.routers.knowledge_base.knowledge_base_auth_configured", lambda: True)

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
        client._test_app.state.mcp = fake_mcp
        client._test_app.state.registry.get = lambda name: _FakeAgent()
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


# ---------------------------------------------------------------------------
# Contrats d'erreur harmonisés (ajoutés avec I3)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_knowledge_base_search_blank_query_returns_400(
    monkeypatch: pytest.MonkeyPatch,
):
    """Une query vide ou uniquement des espaces doit retourner 400."""
    add_api_key("test-key-001")
    fake_mcp = AsyncMock()
    monkeypatch.setattr(
        "mascarade.routers.knowledge_base.knowledge_base_auth_configured", lambda: True
    )

    async with _client() as client:
        client._test_app.state.mcp = fake_mcp
        response = await client.get(
            "/knowledge-base/search?q=   &project_id=project-alpha",
            headers={"Authorization": "Bearer test-key-001"},
        )

    assert response.status_code == 400
    fake_mcp.knowledge_base_search.assert_not_awaited()


@pytest.mark.asyncio
async def test_knowledge_base_search_limit_out_of_range_returns_422(
    monkeypatch: pytest.MonkeyPatch,
):
    """Un limit=0 ou limit>50 doit retourner 422 (validation Query)."""
    add_api_key("test-key-001")
    fake_mcp = AsyncMock()
    monkeypatch.setattr(
        "mascarade.routers.knowledge_base.knowledge_base_auth_configured", lambda: True
    )

    async with _client() as client:
        client._test_app.state.mcp = fake_mcp

        r_low = await client.get(
            "/knowledge-base/search?q=test&project_id=proj&limit=0",
            headers={"Authorization": "Bearer test-key-001"},
        )
        r_high = await client.get(
            "/knowledge-base/search?q=test&project_id=proj&limit=99",
            headers={"Authorization": "Bearer test-key-001"},
        )

    assert r_low.status_code == 422
    assert r_high.status_code == 422
    fake_mcp.knowledge_base_search.assert_not_awaited()


@pytest.mark.asyncio
async def test_knowledge_base_search_not_configured_returns_503(
    monkeypatch: pytest.MonkeyPatch,
):
    """Quand KB n'est pas configuré, le routeur doit retourner 503."""
    add_api_key("test-key-001")
    monkeypatch.setattr(
        "mascarade.routers.knowledge_base.knowledge_base_auth_configured", lambda: False
    )

    async with _client() as client:
        response = await client.get(
            "/knowledge-base/search?q=hello&project_id=proj",
            headers={"Authorization": "Bearer test-key-001"},
        )

    assert response.status_code == 503


@pytest.mark.asyncio
async def test_knowledge_base_search_falls_back_to_kb_handler_when_mcp_absent(
    monkeypatch: pytest.MonkeyPatch,
):
    """Sans MCP dans l'état de l'app, le fallback kb_handler doit être utilisé."""
    add_api_key("test-key-001")
    monkeypatch.setattr(
        "mascarade.routers.knowledge_base.knowledge_base_auth_configured", lambda: True
    )
    fake_handler = AsyncMock()
    fake_handler.search.return_value = [{"id": "qdrant-1", "text": "fallback result"}]

    with patch(
        "mascarade.integrations.kb_handler.KBSearchHandler", return_value=fake_handler
    ):
        async with _client() as client:
            client._test_app.state.mcp = None  # pas de client MCP
            response = await client.get(
                "/knowledge-base/search?q=fallback&project_id=project-alpha",
                headers={"Authorization": "Bearer test-key-001"},
            )

    assert response.status_code == 200
    data = response.json()
    assert data["count"] == 1
    fake_handler.search.assert_awaited_once()
