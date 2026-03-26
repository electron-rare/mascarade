"""Tests for the RAG document library — ingest, search, collection management."""

from __future__ import annotations

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import mascarade.rag_library as rag


def _mock_httpx_client(*, get=None, post=None, put=None):
    """Return a patch context that replaces httpx.AsyncClient with a mock.

    The mock supports ``async with httpx.AsyncClient(...) as c:`` usage.
    """
    mock_instance = AsyncMock()
    if get is not None:
        mock_instance.get = get
    if post is not None:
        mock_instance.post = post
    if put is not None:
        mock_instance.put = put

    @asynccontextmanager
    async def _fake_client(*_args, **_kwargs):
        yield mock_instance

    patcher = patch("mascarade.rag_library.httpx.AsyncClient", side_effect=_fake_client)
    return patcher, mock_instance


class TestChunkText:
    """Tests for _chunk_text utility."""

    def test_short_text_single_chunk(self):
        text = "hello world"
        chunks = rag._chunk_text(text)
        assert len(chunks) == 1
        assert chunks[0] == "hello world"

    def test_empty_text_no_chunks(self):
        assert rag._chunk_text("") == []

    def test_whitespace_only_no_chunks(self):
        assert rag._chunk_text("   ") == []

    def test_long_text_produces_overlapping_chunks(self):
        words = [f"word{i}" for i in range(600)]
        text = " ".join(words)
        chunks = rag._chunk_text(text)
        assert len(chunks) >= 2
        # Second chunk should start at CHUNK_SIZE - CHUNK_OVERLAP offset
        second_start = rag.CHUNK_SIZE - rag.CHUNK_OVERLAP
        assert chunks[1].startswith(f"word{second_start}")

    def test_chunk_size_respected(self):
        words = [f"w{i}" for i in range(1000)]
        text = " ".join(words)
        chunks = rag._chunk_text(text)
        for chunk in chunks:
            assert len(chunk.split()) <= rag.CHUNK_SIZE


class TestEmbed:
    """Tests for the _embed async function."""

    @pytest.mark.asyncio
    async def test_embed_returns_vector_on_success(self):
        fake_response = MagicMock()
        fake_response.status_code = 200
        fake_response.raise_for_status = MagicMock()
        fake_response.json.return_value = {"embeddings": [[0.1] * 384]}

        post_fn = AsyncMock(return_value=fake_response)
        patcher, _ = _mock_httpx_client(post=post_fn)

        with patcher:
            result = await rag._embed("test text")

        assert len(result) == 384
        assert result[0] == 0.1

    @pytest.mark.asyncio
    async def test_embed_returns_zero_vector_on_empty_embeddings(self):
        fake_response = MagicMock()
        fake_response.status_code = 200
        fake_response.raise_for_status = MagicMock()
        fake_response.json.return_value = {"embeddings": []}

        post_fn = AsyncMock(return_value=fake_response)
        patcher, _ = _mock_httpx_client(post=post_fn)

        with patcher:
            result = await rag._embed("test")

        assert result == [0.0] * 384

    @pytest.mark.asyncio
    async def test_embed_returns_zero_vector_on_exception(self):
        post_fn = AsyncMock(side_effect=Exception("connection refused"))
        patcher, _ = _mock_httpx_client(post=post_fn)

        with patcher:
            result = await rag._embed("test")

        assert result == [0.0] * 384


class TestEnsureCollection:
    """Tests for _ensure_collection."""

    @pytest.mark.asyncio
    async def test_creates_collection_on_404(self):
        fake_get_resp = MagicMock()
        fake_get_resp.status_code = 404

        get_fn = AsyncMock(return_value=fake_get_resp)
        put_fn = AsyncMock(return_value=MagicMock(status_code=200))
        patcher, mock_inst = _mock_httpx_client(get=get_fn, put=put_fn)

        with patcher:
            await rag._ensure_collection()

        put_fn.assert_called_once()
        call_kwargs = put_fn.call_args.kwargs
        assert "vectors" in call_kwargs.get("json", {})

    @pytest.mark.asyncio
    async def test_skips_creation_when_collection_exists(self):
        fake_get_resp = MagicMock()
        fake_get_resp.status_code = 200

        get_fn = AsyncMock(return_value=fake_get_resp)
        put_fn = AsyncMock()
        patcher, _ = _mock_httpx_client(get=get_fn, put=put_fn)

        with patcher:
            await rag._ensure_collection()

        put_fn.assert_not_called()

    @pytest.mark.asyncio
    async def test_handles_connection_error_gracefully(self):
        get_fn = AsyncMock(side_effect=Exception("connection error"))
        patcher, _ = _mock_httpx_client(get=get_fn)

        with patcher:
            # Should not raise
            await rag._ensure_collection()


class TestIngest:
    """Tests for the ingest function."""

    @pytest.mark.asyncio
    async def test_ingest_returns_chunk_count(self):
        put_fn = AsyncMock(return_value=MagicMock(status_code=200))
        patcher, _ = _mock_httpx_client(put=put_fn)

        with (
            patch.object(rag, "_ensure_collection", new_callable=AsyncMock),
            patch.object(rag, "_embed", new_callable=AsyncMock, return_value=[0.0] * 384),
            patcher,
        ):
            result = await rag.ingest("some text to ingest")

        assert result["chunks"] == 1
        assert result["collection"] == rag.COLLECTION

    @pytest.mark.asyncio
    async def test_ingest_empty_text_returns_zero_chunks(self):
        with (
            patch.object(rag, "_ensure_collection", new_callable=AsyncMock),
            patch.object(rag, "_embed", new_callable=AsyncMock),
        ):
            result = await rag.ingest("")

        assert result["chunks"] == 0

    @pytest.mark.asyncio
    async def test_ingest_passes_metadata(self):
        put_fn = AsyncMock(return_value=MagicMock(status_code=200))
        patcher, _ = _mock_httpx_client(put=put_fn)

        with (
            patch.object(rag, "_ensure_collection", new_callable=AsyncMock),
            patch.object(rag, "_embed", new_callable=AsyncMock, return_value=[0.0] * 384),
            patcher,
        ):
            result = await rag.ingest("hello world", {"source": "test"})

        assert result["chunks"] == 1
        put_call = put_fn.call_args
        points = put_call.kwargs.get("json", {})["points"]
        assert points[0]["payload"]["source"] == "test"


class TestSearch:
    """Tests for the search function."""

    @pytest.mark.asyncio
    async def test_search_returns_results(self):
        fake_response = MagicMock()
        fake_response.status_code = 200
        fake_response.raise_for_status = MagicMock()
        fake_response.json.return_value = {
            "result": [
                {"score": 0.95, "payload": {"text": "match one", "source": "doc1"}},
                {"score": 0.80, "payload": {"text": "match two"}},
            ]
        }

        post_fn = AsyncMock(return_value=fake_response)
        patcher, _ = _mock_httpx_client(post=post_fn)

        with (
            patch.object(rag, "_embed", new_callable=AsyncMock, return_value=[0.0] * 384),
            patcher,
        ):
            results = await rag.search("my query", top_k=3)

        assert len(results) == 2
        assert results[0]["score"] == 0.95
        assert results[0]["text"] == "match one"
        assert results[0]["metadata"]["source"] == "doc1"

    @pytest.mark.asyncio
    async def test_search_returns_empty_on_error(self):
        post_fn = AsyncMock(side_effect=Exception("unavailable"))
        patcher, _ = _mock_httpx_client(post=post_fn)

        with (
            patch.object(rag, "_embed", new_callable=AsyncMock, return_value=[0.0] * 384),
            patcher,
        ):
            results = await rag.search("test query")

        assert results == []


class TestStatus:
    """Tests for the status function."""

    @pytest.mark.asyncio
    async def test_status_ok(self):
        fake_response = MagicMock()
        fake_response.status_code = 200
        fake_response.json.return_value = {"result": {"points_count": 42}}

        get_fn = AsyncMock(return_value=fake_response)
        patcher, _ = _mock_httpx_client(get=get_fn)

        with patcher:
            result = await rag.status()

        assert result["status"] == "ok"
        assert result["points"] == 42
        assert result["collection"] == rag.COLLECTION

    @pytest.mark.asyncio
    async def test_status_unavailable_on_error(self):
        get_fn = AsyncMock(side_effect=Exception("unreachable"))
        patcher, _ = _mock_httpx_client(get=get_fn)

        with patcher:
            result = await rag.status()

        assert result["status"] == "unavailable"
        assert result["points"] == 0
