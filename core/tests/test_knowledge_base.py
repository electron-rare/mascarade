from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from mascarade.config import settings
from mascarade.integrations.knowledge_base import (
    DocmostClient,
    KnowledgeBaseClient,
    MemosClient,
    knowledge_base_auth_configured,
)

KB_SETTING_NAMES = [
    "knowledge_base_provider",
    "knowledge_base_smoke_page_id",
    "memos_base_url",
    "memos_public_url",
    "memos_access_token",
    "memos_default_visibility",
    "docmost_base_url",
    "docmost_email",
    "docmost_password",
    "docmost_space_id",
]


@pytest.fixture(autouse=True)
def restore_kb_settings():
    snapshot = {name: getattr(settings, name) for name in KB_SETTING_NAMES}
    yield
    for name, value in snapshot.items():
        setattr(settings, name, value)


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def json(self):
        return self._payload

    def raise_for_status(self):
        return None


def test_knowledge_base_auth_configured_for_memos():
    settings.knowledge_base_provider = "memos"
    settings.memos_base_url = "http://memos:5230"
    settings.memos_access_token = "memos_pat_123456"  # noqa: S105

    assert knowledge_base_auth_configured() is True


def test_knowledge_base_auth_configured_for_docmost():
    settings.knowledge_base_provider = "docmost"
    settings.docmost_base_url = "https://docmost.example.test"
    settings.docmost_email = "ops@example.test"
    settings.docmost_password = "docmost-secret-123456"  # noqa: S105

    assert knowledge_base_auth_configured() is True


@pytest.mark.asyncio
async def test_memos_client_maps_search_results():
    settings.memos_base_url = "http://memos:5230"
    settings.memos_public_url = "http://127.0.0.1:5230"
    settings.memos_access_token = "memos_pat_123456"  # noqa: S105

    with (
        patch("mascarade.integrations.knowledge_base._url_host_resolves") as resolves,
        patch("mascarade.integrations.knowledge_base.httpx.AsyncClient") as async_client_cls,
    ):
        resolves.side_effect = lambda url: url.startswith("http://127.0.0.1:")
        fake_client = async_client_cls.return_value
        fake_client.aclose = AsyncMock()
        fake_client.get = AsyncMock(
            return_value=_FakeResponse(
                {
                    "memos": [
                        {"name": "memos/abc123", "content": "# Release notes\ncontent"},
                    ]
                }
            )
        )
        client = MemosClient()
        try:
            results = await client.search("release", limit=5)
        finally:
            await client.close()

    _, kwargs = async_client_cls.call_args
    assert kwargs["base_url"] == "http://127.0.0.1:5230"
    assert results == [
        {
            "id": "abc123",
            "title": "Release notes",
            "url": "http://127.0.0.1:5230/memos/abc123",
            "provider": "memos",
        }
    ]


@pytest.mark.asyncio
async def test_memos_client_append_updates_content_mask():
    settings.memos_base_url = "http://memos:5230"
    settings.memos_access_token = "memos_pat_123456"  # noqa: S105

    with patch("mascarade.integrations.knowledge_base.httpx.AsyncClient") as async_client_cls:
        fake_client = async_client_cls.return_value
        fake_client.aclose = AsyncMock()
        fake_client.get = AsyncMock(
            return_value=_FakeResponse({"name": "memos/abc123", "content": "before"})
        )
        fake_client.patch = AsyncMock(return_value=_FakeResponse({"name": "memos/abc123"}))
        client = MemosClient()
        try:
            await client.append_to_page("abc123", "after")
        finally:
            await client.close()

    fake_client.patch.assert_awaited_once()
    _, kwargs = fake_client.patch.await_args
    assert kwargs["json"]["memo"]["name"] == "memos/abc123"
    assert kwargs["json"]["updateMask"] == "content"
    assert "after" in kwargs["json"]["memo"]["content"]


@pytest.mark.asyncio
async def test_docmost_client_create_page_uses_parent_space():
    settings.docmost_base_url = "https://docs.example.test"
    settings.docmost_email = "ops@example.test"
    settings.docmost_password = "docmost-secret-123456"  # noqa: S105

    with patch("mascarade.integrations.knowledge_base.httpx.AsyncClient") as async_client_cls:
        fake_client = async_client_cls.return_value
        fake_client.aclose = AsyncMock()
        fake_client.post = AsyncMock(
            side_effect=[
                _FakeResponse({}),
                _FakeResponse({"id": "parent-1", "spaceId": "space-1"}),
                _FakeResponse({"id": "page-2"}),
            ]
        )
        client = DocmostClient()
        try:
            page_id = await client.create_page("parent-1", "Child page", "Body")
        finally:
            await client.close()

    assert page_id == "page-2"
    create_call = fake_client.post.await_args_list[-1]
    _, kwargs = create_call
    assert kwargs["json"]["parentPageId"] == "parent-1"
    assert kwargs["json"]["spaceId"] == "space-1"
    assert kwargs["json"]["title"] == "Child page"


def test_knowledge_base_client_dispatches_to_memos():
    settings.knowledge_base_provider = "memos"
    settings.memos_base_url = "http://memos:5230"
    settings.memos_access_token = "memos_pat_123456"  # noqa: S105

    with patch("mascarade.integrations.knowledge_base.MemosClient") as memos_cls:
        client = KnowledgeBaseClient()

    assert client.provider == "memos"
    assert client.label == "Memos"
    memos_cls.assert_called_once_with()
