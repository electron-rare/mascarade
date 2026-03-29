"""Tests d'intégration HTTP pour mascarade.routers.rag."""

from __future__ import annotations

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from fastapi import FastAPI

from mascarade.routers.rag import router as rag_router

# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------


def _make_app(*, router_available: bool = True) -> FastAPI:
    """Crée une app FastAPI standalone avec le routeur RAG."""
    app = FastAPI()
    app.include_router(rag_router)
    app.state.router = MagicMock() if router_available else None
    app.state.registry = MagicMock()
    return app


@asynccontextmanager
async def _client(*, router_available: bool = True):
    app = _make_app(router_available=router_available)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        client._test_app = app  # type: ignore[attr-defined]
        yield client


# ---------------------------------------------------------------------------
# POST /v1/api/rag/query
# ---------------------------------------------------------------------------


class TestRagQuery:
    @pytest.mark.asyncio
    async def test_query_success(self):
        fake_pipeline = AsyncMock()
        fake_pipeline.query.return_value = {
            "answer": "42",
            "intent": "factual",
            "sources": [{"id": "doc-1", "text": "Douglas Adams"}],
            "tool_calls": [],
            "provider": "openai",
            "model": "gpt-4o-mini",
            "usage": {"prompt_tokens": 10, "completion_tokens": 5},
            "elapsed_seconds": 0.42,
        }
        fake_pipeline.close = AsyncMock()

        with patch("mascarade.routers.rag.RAGPipeline", return_value=fake_pipeline):
            async with _client() as c:
                resp = await c.post(
                    "/v1/api/rag/query",
                    json={"query": "What is the answer?", "top_k": 3},
                )

        assert resp.status_code == 200
        data = resp.json()
        assert data["answer"] == "42"
        assert data["intent"] == "factual"
        assert len(data["sources"]) == 1
        fake_pipeline.query.assert_awaited_once()
        fake_pipeline.close.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_query_router_not_initialised_returns_503(self):
        async with _client(router_available=False) as c:
            resp = await c.post(
                "/v1/api/rag/query",
                json={"query": "test"},
            )

        assert resp.status_code == 503
        assert "router" in resp.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_query_pipeline_exception_returns_500(self):
        fake_pipeline = AsyncMock()
        fake_pipeline.query.side_effect = RuntimeError("embedding service down")
        fake_pipeline.close = AsyncMock()

        with patch("mascarade.routers.rag.RAGPipeline", return_value=fake_pipeline):
            async with _client() as c:
                resp = await c.post("/v1/api/rag/query", json={"query": "boom"})

        assert resp.status_code == 500
        assert "embedding service down" in resp.json()["detail"]

    @pytest.mark.asyncio
    async def test_query_top_k_bounds(self):
        """top_k < 1 ou > 50 doit retourner 422."""
        async with _client() as c:
            r_low = await c.post("/v1/api/rag/query", json={"query": "x", "top_k": 0})
            r_high = await c.post("/v1/api/rag/query", json={"query": "x", "top_k": 51})

        assert r_low.status_code == 422
        assert r_high.status_code == 422


# ---------------------------------------------------------------------------
# POST /v1/api/rag/ingest
# ---------------------------------------------------------------------------


class TestRagIngest:
    @pytest.mark.asyncio
    async def test_ingest_success(self):
        fake_pipeline = AsyncMock()
        fake_pipeline.ingest.return_value = 3
        fake_pipeline.vectorstore.collection = "mascarade-rag"
        fake_pipeline.close = AsyncMock()

        with patch("mascarade.routers.rag.RAGPipeline", return_value=fake_pipeline):
            async with _client() as c:
                resp = await c.post(
                    "/v1/api/rag/ingest",
                    json={
                        "documents": [
                            {"text": "doc A"},
                            {"text": "doc B"},
                            {"text": "doc C"},
                        ]
                    },
                )

        assert resp.status_code == 200
        data = resp.json()
        assert data["ingested"] == 3
        assert data["collection"] == "mascarade-rag"
        fake_pipeline.ingest.assert_awaited_once()
        fake_pipeline.close.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_ingest_empty_documents_returns_400(self):
        async with _client() as c:
            resp = await c.post("/v1/api/rag/ingest", json={"documents": []})

        assert resp.status_code == 400
        assert "No documents" in resp.json()["detail"]

    @pytest.mark.asyncio
    async def test_ingest_router_not_initialised_returns_503(self):
        async with _client(router_available=False) as c:
            resp = await c.post(
                "/v1/api/rag/ingest",
                json={"documents": [{"text": "hello"}]},
            )

        assert resp.status_code == 503

    @pytest.mark.asyncio
    async def test_ingest_with_explicit_collection(self):
        fake_pipeline = AsyncMock()
        fake_pipeline.ingest.return_value = 1
        fake_pipeline.vectorstore.collection = "mascarade-rag"
        fake_pipeline.close = AsyncMock()

        with patch("mascarade.routers.rag.RAGPipeline", return_value=fake_pipeline):
            async with _client() as c:
                resp = await c.post(
                    "/v1/api/rag/ingest",
                    json={"documents": [{"text": "x"}], "collection": "custom-col"},
                )

        assert resp.status_code == 200
        assert resp.json()["collection"] == "custom-col"


# ---------------------------------------------------------------------------
# GET /v1/api/rag/collections
# ---------------------------------------------------------------------------


class TestRagCollections:
    @pytest.mark.asyncio
    async def test_list_collections_success(self):
        fake_vs = AsyncMock()
        fake_vs.list_collections.return_value = [
            {"name": "col-a"},
            {"name": "col-b"},
        ]
        fake_vs.close = AsyncMock()

        # collection_info appelé pour chaque collection
        fake_col_vs = AsyncMock()
        fake_col_vs.collection_info.return_value = {"vectors_count": 10, "points_count": 10}
        fake_col_vs.close = AsyncMock()

        def _vs_factory(collection: str | None = None, **_):
            return fake_col_vs if collection else fake_vs

        with patch("mascarade.routers.rag.QdrantVectorStore", side_effect=_vs_factory):
            async with _client() as c:
                resp = await c.get("/v1/api/rag/collections")

        assert resp.status_code == 200
        data = resp.json()
        assert len(data["collections"]) == 2
        names = {c["name"] for c in data["collections"]}
        assert "col-a" in names and "col-b" in names

    @pytest.mark.asyncio
    async def test_list_collections_qdrant_error_returns_502(self):
        fake_vs = AsyncMock()
        fake_vs.list_collections.side_effect = RuntimeError("qdrant unreachable")
        fake_vs.close = AsyncMock()

        with patch("mascarade.routers.rag.QdrantVectorStore", return_value=fake_vs):
            async with _client() as c:
                resp = await c.get("/v1/api/rag/collections")

        assert resp.status_code == 502
        assert "Qdrant" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# GET /v1/api/rag/collections/{name}
# ---------------------------------------------------------------------------


class TestRagCollectionInfo:
    @pytest.mark.asyncio
    async def test_collection_info_success(self):
        fake_vs = AsyncMock()
        fake_vs.collection_info.return_value = {"vectors_count": 42, "points_count": 42}
        fake_vs.close = AsyncMock()

        with patch("mascarade.routers.rag.QdrantVectorStore", return_value=fake_vs):
            async with _client() as c:
                resp = await c.get("/v1/api/rag/collections/my-collection")

        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "my-collection"
        assert data["vectors_count"] == 42

    @pytest.mark.asyncio
    async def test_collection_info_not_found_returns_404(self):
        fake_vs = AsyncMock()
        fake_vs.collection_info.side_effect = RuntimeError("collection not found")
        fake_vs.close = AsyncMock()

        with patch("mascarade.routers.rag.QdrantVectorStore", return_value=fake_vs):
            async with _client() as c:
                resp = await c.get("/v1/api/rag/collections/ghost-col")

        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_collection_info_qdrant_generic_error_returns_502(self):
        fake_vs = AsyncMock()
        fake_vs.collection_info.side_effect = RuntimeError("timeout")
        fake_vs.close = AsyncMock()

        with patch("mascarade.routers.rag.QdrantVectorStore", return_value=fake_vs):
            async with _client() as c:
                resp = await c.get("/v1/api/rag/collections/slow-col")

        assert resp.status_code == 502


# ---------------------------------------------------------------------------
# DELETE /v1/api/rag/collections/{name}
# ---------------------------------------------------------------------------


class TestRagCollectionDelete:
    @pytest.mark.asyncio
    async def test_delete_reserved_collection_returns_403(self):
        async with _client() as c:
            resp = await c.delete("/v1/api/rag/collections/rag-query-cache")

        assert resp.status_code == 403
        assert "reserved" in resp.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_delete_missing_collection_returns_404(self):
        fake_vs = AsyncMock()
        fake_vs.drop_collection.return_value = False
        fake_vs.close = AsyncMock()

        with patch("mascarade.routers.rag.QdrantVectorStore", return_value=fake_vs):
            async with _client() as c:
                resp = await c.delete("/v1/api/rag/collections/ghost-col")

        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_success(self):
        fake_vs = AsyncMock()
        fake_vs.drop_collection.return_value = True
        fake_vs.close = AsyncMock()

        with patch("mascarade.routers.rag.QdrantVectorStore", return_value=fake_vs):
            async with _client() as c:
                resp = await c.delete("/v1/api/rag/collections/my-old-index")

        assert resp.status_code == 200
        data = resp.json()
        assert data["deleted"] is True
        assert data["collection"] == "my-old-index"

    @pytest.mark.asyncio
    async def test_delete_qdrant_error_returns_502(self):
        fake_vs = AsyncMock()
        fake_vs.drop_collection.side_effect = RuntimeError("connection refused")
        fake_vs.close = AsyncMock()

        with patch("mascarade.routers.rag.QdrantVectorStore", return_value=fake_vs):
            async with _client() as c:
                resp = await c.delete("/v1/api/rag/collections/fragile-col")

        assert resp.status_code == 502


# ---------------------------------------------------------------------------
# POST /v1/api/rag/search
# ---------------------------------------------------------------------------


class TestRagSearch:
    @pytest.mark.asyncio
    async def test_search_success(self):
        fake_vs = AsyncMock()
        fake_vs.search.return_value = [
            {"id": "p1", "score": 0.91, "payload": {"text": "result A"}},
        ]
        fake_vs.close = AsyncMock()

        fake_emb = AsyncMock()
        fake_emb.embed_query.return_value = [0.1] * 1536
        fake_emb.close = AsyncMock()

        with (
            patch("mascarade.routers.rag.QdrantVectorStore", return_value=fake_vs),
            patch("mascarade.routers.rag.EmbeddingProvider", return_value=fake_emb),
        ):
            async with _client() as c:
                resp = await c.post(
                    "/v1/api/rag/search",
                    json={"query": "apple pie", "top_k": 5},
                )

        assert resp.status_code == 200
        data = resp.json()
        assert len(data["results"]) == 1
        assert data["results"][0]["score"] == pytest.approx(0.91)
        assert data["collection"] == "mascarade-rag"

    @pytest.mark.asyncio
    async def test_search_with_custom_collection(self):
        fake_vs = AsyncMock()
        fake_vs.search.return_value = []
        fake_vs.close = AsyncMock()

        fake_emb = AsyncMock()
        fake_emb.embed_query.return_value = [0.0] * 1536
        fake_emb.close = AsyncMock()

        with (
            patch("mascarade.routers.rag.QdrantVectorStore", return_value=fake_vs),
            patch("mascarade.routers.rag.EmbeddingProvider", return_value=fake_emb),
        ):
            async with _client() as c:
                resp = await c.post(
                    "/v1/api/rag/search",
                    json={"query": "x", "collection": "custom-index"},
                )

        assert resp.status_code == 200
        assert resp.json()["collection"] == "custom-index"

    @pytest.mark.asyncio
    async def test_search_top_k_bounds(self):
        """top_k hors [1,50] → 422."""
        async with _client() as c:
            r_low = await c.post("/v1/api/rag/search", json={"query": "x", "top_k": 0})
            r_high = await c.post("/v1/api/rag/search", json={"query": "x", "top_k": 51})

        assert r_low.status_code == 422
        assert r_high.status_code == 422

    @pytest.mark.asyncio
    async def test_search_exception_returns_500(self):
        fake_vs = AsyncMock()
        fake_vs.close = AsyncMock()

        fake_emb = AsyncMock()
        fake_emb.embed_query.side_effect = RuntimeError("embed failed")
        fake_emb.close = AsyncMock()

        with (
            patch("mascarade.routers.rag.QdrantVectorStore", return_value=fake_vs),
            patch("mascarade.routers.rag.EmbeddingProvider", return_value=fake_emb),
        ):
            async with _client() as c:
                resp = await c.post("/v1/api/rag/search", json={"query": "boom"})

        assert resp.status_code == 500


# ---------------------------------------------------------------------------
# POST /v1/api/rag/eval
# ---------------------------------------------------------------------------


class TestRagEval:
    @pytest.mark.asyncio
    async def test_eval_empty_dataset_returns_400(self):
        async with _client() as c:
            resp = await c.post("/v1/api/rag/eval", json={"dataset": []})

        assert resp.status_code == 400
        assert "Empty" in resp.json()["detail"]

    @pytest.mark.asyncio
    async def test_eval_router_not_initialised_returns_503(self):
        async with _client(router_available=False) as c:
            resp = await c.post(
                "/v1/api/rag/eval",
                json={
                    "dataset": [
                        {
                            "question": "What is 2+2?",
                            "ground_truth": "4",
                            "answer": "4",
                            "contexts": ["Math is fun"],
                        }
                    ]
                },
            )

        assert resp.status_code == 503

    @pytest.mark.asyncio
    async def test_eval_success(self):
        fake_pipeline = AsyncMock()
        fake_pipeline.close = AsyncMock()

        fake_evaluator = AsyncMock()
        fake_evaluator.evaluate.return_value = {
            "metrics": {"faithfulness": 0.9},
            "thresholds": {"faithfulness": 0.7},
            "status": {"faithfulness": "pass"},
            "overall": "pass",
            "n_items": 1,
            "n_errors": 0,
            "elapsed_seconds": 1.1,
        }

        with (
            patch("mascarade.routers.rag.RAGPipeline", return_value=fake_pipeline),
            patch("mascarade.rag.eval.RAGEvaluator", return_value=fake_evaluator),
        ):
            async with _client() as c:
                resp = await c.post(
                    "/v1/api/rag/eval",
                    json={
                        "dataset": [
                            {
                                "question": "What is Mascarade?",
                                "ground_truth": "An agentic orchestration system.",
                                "answer": "An agentic orchestration system.",
                                "contexts": ["Mascarade is personal AI infra."],
                            }
                        ],
                        "run_pipeline": False,
                    },
                )

        assert resp.status_code == 200
        data = resp.json()
        assert data["overall"] == "pass"
        assert data["n_items"] == 1
        assert data["n_errors"] == 0
