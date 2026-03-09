"""Tests pour l'intégration Notion."""

from unittest.mock import AsyncMock, patch

import pytest

from mascarade.integrations.notion import NotionClient


@pytest.fixture
def notion_client():
    with patch("mascarade.integrations.notion.AsyncClient") as async_client_cls:
        client = NotionClient(api_key="fake-key")
        client._client = async_client_cls.return_value
        client._client_token = "fake-key"  # noqa: S105
        return client


def test_blocks_to_text():
    blocks = [
        {"type": "paragraph", "paragraph": {"rich_text": [{"plain_text": "Hello"}]}},
        {"type": "heading_1", "heading_1": {"rich_text": [{"plain_text": "Title"}]}},
        {"type": "paragraph", "paragraph": {"rich_text": []}},
    ]
    result = NotionClient._blocks_to_text(blocks)
    assert result == "Hello\nTitle"


def test_blocks_to_text_empty():
    assert NotionClient._blocks_to_text([]) == ""


def test_extract_title():
    page = {
        "properties": {
            "Name": {
                "type": "title",
                "title": [{"plain_text": "My Page"}],
            }
        }
    }
    assert NotionClient._extract_title(page) == "My Page"


def test_extract_title_missing():
    assert NotionClient._extract_title({"properties": {}}) == ""


@pytest.mark.asyncio
async def test_search(notion_client):
    notion_client._client.search = AsyncMock(
        return_value={
            "results": [
                {
                    "object": "page",
                    "id": "abc-123",
                    "url": "https://notion.so/abc",
                    "properties": {
                        "title": {
                            "type": "title",
                            "title": [{"plain_text": "Test Page"}],
                        }
                    },
                },
                {
                    "object": "database",
                    "id": "db-456",
                },
            ]
        }
    )
    results = await notion_client.search("test")
    assert len(results) == 1
    assert results[0]["id"] == "abc-123"
    assert results[0]["title"] == "Test Page"


@pytest.mark.asyncio
async def test_read_page(notion_client):
    notion_client._client.blocks.children.list = AsyncMock(
        return_value={
            "results": [
                {
                    "type": "paragraph",
                    "paragraph": {"rich_text": [{"plain_text": "Content here"}]},
                },
            ]
        }
    )
    content = await notion_client.read_page("page-id")
    assert content == "Content here"


@pytest.mark.asyncio
async def test_append_to_page(notion_client):
    notion_client._client.blocks.children.append = AsyncMock()
    await notion_client.append_to_page("page-id", "New content")
    notion_client._client.blocks.children.append.assert_called_once()


@pytest.mark.asyncio
async def test_create_page(notion_client):
    notion_client._client.pages.create = AsyncMock(return_value={"id": "new-page-id"})
    notion_client._client.blocks.children.append = AsyncMock()
    page_id = await notion_client.create_page("parent-id", "Title", "Content")
    assert page_id == "new-page-id"
    notion_client._client.blocks.children.append.assert_called_once()
