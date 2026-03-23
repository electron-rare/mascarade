"""Tests for the RAG multi-tool orchestration module."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mascarade.rag.embeddings import EmbeddingProvider
from mascarade.rag.pipeline import RAGPipeline
from mascarade.rag.vectorstore import QdrantVectorStore

# ---------------------------------------------------------------------------
# EmbeddingProvider
# ---------------------------------------------------------------------------


class TestEmbeddingProvider:
    """Tests for the EmbeddingProvider class."""

    def test_dimension_for_model_known(self):
        ep = EmbeddingProvider()
        assert ep.dimension_for_model("text-embedding-3-small") == 1536
        assert ep.dimension_for_model("mistral-embed") == 1024

    def test_dimension_for_model_unknown_defaults(self):
        ep = EmbeddingProvider()
        assert ep.dimension_for_model("unknown-model") == 1536

    @pytest.mark.asyncio
    async def test_embed_empty_list(self):
        ep = EmbeddingProvider()
        result = await ep.embed([])
        assert result == []

    @pytest.mark.asyncio
    async def test_embed_openai_called_when_key_configured(self):
        ep = EmbeddingProvider()
        fake_embeddings = [[0.1, 0.2, 0.3]]
        ep._embed_openai = AsyncMock(return_value=fake_embeddings)

        with patch("mascarade.rag.embeddings.is_secret_configured", return_value=True):
            result = await ep.embed(["hello world"])
        assert result == fake_embeddings
        ep._embed_openai.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_embed_query_single(self):
        ep = EmbeddingProvider()
        ep.embed = AsyncMock(return_value=[[0.5, 0.6]])
        result = await ep.embed_query("test query")
        assert result == [0.5, 0.6]
        ep.embed.assert_awaited_once_with(
            ["test query"], model="text-embedding-3-small"
        )

    @pytest.mark.asyncio
    async def test_embed_fallback_chain(self):
        """When OpenAI fails, try Mistral, then HuggingFace, then Qdrant."""
        ep = EmbeddingProvider()
        ep._embed_openai = AsyncMock(side_effect=RuntimeError("openai down"))
        ep._embed_mistral = AsyncMock(side_effect=RuntimeError("mistral down"))
        ep._embed_huggingface = AsyncMock(side_effect=RuntimeError("hf down"))
        ep._embed_qdrant_fastembed = AsyncMock(return_value=[[0.1]])

        with patch("mascarade.rag.embeddings.is_secret_configured", return_value=True):
            result = await ep.embed(["test"])

        assert result == [[0.1]]
        ep._embed_qdrant_fastembed.assert_awaited_once()


# ---------------------------------------------------------------------------
# QdrantVectorStore
# ---------------------------------------------------------------------------


class TestQdrantVectorStore:
    """Tests for the QdrantVectorStore class."""

    def test_init_defaults(self):
        vs = QdrantVectorStore()
        assert vs.collection == "mascarade-rag"
        assert "qdrant" in vs.base_url

    def test_init_custom(self):
        vs = QdrantVectorStore(base_url="http://localhost:6333", collection="my-col")
        assert vs.base_url == "http://localhost:6333"
        assert vs.collection == "my-col"

    @pytest.mark.asyncio
    async def test_upsert_length_mismatch(self):
        vs = QdrantVectorStore()
        with pytest.raises(ValueError, match="same length"):
            await vs.upsert([{"text": "a"}], [[0.1], [0.2]])


# ---------------------------------------------------------------------------
# RAGPipeline
# ---------------------------------------------------------------------------


class TestRAGPipeline:
    """Tests for the RAGPipeline class."""

    def _make_llm_response(
        self, text: str = "answer", provider: str = "mock", model: str = "mock-model"
    ):
        resp = MagicMock()
        resp.text = text
        resp.provider = provider
        resp.model = model
        resp.usage = {"prompt_tokens": 10, "completion_tokens": 20}
        return resp

    @pytest.mark.asyncio
    async def test_query_rag_flow(self):
        """Full RAG flow: classify -> embed -> search -> generate."""
        mock_router = AsyncMock()
        # First call: classification; second call: generation
        mock_router.send = AsyncMock(
            side_effect=[
                self._make_llm_response(text="rag"),
                self._make_llm_response(text="Here is the answer based on context."),
            ]
        )

        mock_embeddings = AsyncMock(spec=EmbeddingProvider)
        mock_embeddings.embed_query = AsyncMock(return_value=[0.1, 0.2, 0.3])
        mock_embeddings.dimension_for_model = MagicMock(return_value=1536)

        mock_vs = AsyncMock(spec=QdrantVectorStore)
        mock_vs.collection = "mascarade-rag"
        mock_vs.base_url = "http://qdrant:6333"
        mock_vs.search = AsyncMock(
            return_value=[
                {
                    "id": "1",
                    "score": 0.95,
                    "text": "Doc content",
                    "source": "test.md",
                    "metadata": {},
                },
            ]
        )

        pipeline = RAGPipeline(
            router=mock_router, vectorstore=mock_vs, embeddings=mock_embeddings
        )
        result = await pipeline.query("What is mascarade?")

        assert result["intent"] == "rag"
        assert "answer" in result
        assert len(result["sources"]) == 1
        assert "vector_search" in result["tool_calls"]
        assert "llm_generate" in result["tool_calls"]

    @pytest.mark.asyncio
    async def test_query_skip_classification(self):
        """When skip_classification=True, go straight to RAG."""
        mock_router = AsyncMock()
        mock_router.send = AsyncMock(
            return_value=self._make_llm_response(text="Direct RAG answer")
        )

        mock_embeddings = AsyncMock(spec=EmbeddingProvider)
        mock_embeddings.embed_query = AsyncMock(return_value=[0.1])

        mock_vs = AsyncMock(spec=QdrantVectorStore)
        mock_vs.collection = "mascarade-rag"
        mock_vs.base_url = "http://qdrant:6333"
        mock_vs.search = AsyncMock(return_value=[])

        pipeline = RAGPipeline(
            router=mock_router, vectorstore=mock_vs, embeddings=mock_embeddings
        )
        result = await pipeline.query("test", skip_classification=True)

        assert result["intent"] == "rag"
        # Only one LLM call (generation), no classification call
        assert mock_router.send.await_count == 1

    @pytest.mark.asyncio
    async def test_query_general_intent(self):
        """When intent is general, no vector search happens."""
        mock_router = AsyncMock()
        mock_router.send = AsyncMock(
            side_effect=[
                self._make_llm_response(text="general"),
                self._make_llm_response(text="General answer"),
            ]
        )

        mock_embeddings = AsyncMock(spec=EmbeddingProvider)
        mock_vs = AsyncMock(spec=QdrantVectorStore)
        mock_vs.collection = "mascarade-rag"
        mock_vs.base_url = "http://qdrant:6333"

        pipeline = RAGPipeline(
            router=mock_router, vectorstore=mock_vs, embeddings=mock_embeddings
        )
        result = await pipeline.query("Hello, how are you?")

        assert result["intent"] == "general"
        assert result["sources"] == []
        mock_embeddings.embed_query.assert_not_awaited()
        mock_vs.search.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_ingest(self):
        """Ingest documents calls embed + upsert."""
        mock_router = AsyncMock()
        mock_embeddings = AsyncMock(spec=EmbeddingProvider)
        mock_embeddings.embed = AsyncMock(return_value=[[0.1, 0.2], [0.3, 0.4]])
        mock_embeddings.dimension_for_model = MagicMock(return_value=1536)

        mock_vs = AsyncMock(spec=QdrantVectorStore)
        mock_vs.collection = "mascarade-rag"
        mock_vs.base_url = "http://qdrant:6333"
        mock_vs.upsert = AsyncMock(return_value=2)

        pipeline = RAGPipeline(
            router=mock_router, vectorstore=mock_vs, embeddings=mock_embeddings
        )
        docs = [{"text": "Doc 1"}, {"text": "Doc 2"}]
        count = await pipeline.ingest(docs)

        assert count == 2
        mock_vs.ensure_collection.assert_awaited_once_with(dimension=1536)
        mock_embeddings.embed.assert_awaited_once()
        mock_vs.upsert.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_ingest_empty(self):
        """Ingesting nothing returns 0."""
        pipeline = RAGPipeline(
            router=AsyncMock(), vectorstore=AsyncMock(), embeddings=AsyncMock()
        )
        count = await pipeline.ingest([])
        assert count == 0
