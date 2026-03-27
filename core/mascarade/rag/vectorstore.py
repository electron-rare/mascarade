"""Qdrant vector store client for RAG."""

from __future__ import annotations

import logging
import uuid
from typing import Any

import httpx

from mascarade.config import settings

logger = logging.getLogger("mascarade.rag.vectorstore")


class QdrantVectorStore:
    """Interface to Qdrant for document storage and retrieval.

    Uses httpx for all REST API calls — no SDK dependency.
    """

    def __init__(
        self,
        base_url: str | None = None,
        collection: str = "mascarade-rag",
        *,
        timeout: float = 30.0,
    ) -> None:
        self.base_url = (base_url or settings.qdrant_url).rstrip("/")
        self.collection = collection
        self._timeout = timeout
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=self._timeout,
            )
        return self._client

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    # ------------------------------------------------------------------
    # Collection management
    # ------------------------------------------------------------------

    async def ensure_collection(self, dimension: int = 1536) -> None:
        """Create the collection if it does not already exist."""
        client = await self._get_client()
        resp = await client.get(f"/collections/{self.collection}")
        if resp.status_code == 200:
            logger.debug("Collection %s already exists", self.collection)
            return

        logger.info("Creating Qdrant collection %s (dim=%d)", self.collection, dimension)
        resp = await client.put(
            f"/collections/{self.collection}",
            json={
                "vectors": {
                    "size": dimension,
                    "distance": "Cosine",
                },
            },
        )
        resp.raise_for_status()
        logger.info("Collection %s created", self.collection)

    async def list_collections(self) -> list[dict[str, Any]]:
        """List all Qdrant collections."""
        client = await self._get_client()
        resp = await client.get("/collections")
        resp.raise_for_status()
        data = resp.json()
        return data.get("result", {}).get("collections", [])

    async def collection_info(self) -> dict[str, Any]:
        """Get info about the current collection."""
        client = await self._get_client()
        resp = await client.get(f"/collections/{self.collection}")
        resp.raise_for_status()
        return resp.json().get("result", {})

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    async def upsert(
        self,
        documents: list[dict[str, Any]],
        embeddings: list[list[float]],
    ) -> int:
        """Upsert documents with embeddings into Qdrant.

        Each document dict should have at least ``text`` and optionally
        ``id`` and ``metadata`` keys.  Returns the number of points upserted.
        """
        if len(documents) != len(embeddings):
            raise ValueError("documents and embeddings must have the same length")

        points: list[dict[str, Any]] = []
        for doc, vector in zip(documents, embeddings, strict=False):
            point_id = doc.get("id", str(uuid.uuid4()))
            payload: dict[str, Any] = {
                "text": doc.get("text", ""),
                "source": doc.get("source", ""),
            }
            if "metadata" in doc:
                payload["metadata"] = doc["metadata"]
            points.append(
                {
                    "id": point_id,
                    "vector": vector,
                    "payload": payload,
                }
            )

        client = await self._get_client()
        resp = await client.put(
            f"/collections/{self.collection}/points",
            json={"points": points},
            params={"wait": "true"},
        )
        resp.raise_for_status()
        logger.info("Upserted %d points into %s", len(points), self.collection)
        return len(points)

    async def search(
        self,
        query_embedding: list[float],
        top_k: int = 5,
        filters: dict[str, Any] | None = None,
        score_threshold: float | None = None,
    ) -> list[dict[str, Any]]:
        """Semantic search. Returns scored matches with metadata."""
        body: dict[str, Any] = {
            "vector": query_embedding,
            "limit": top_k,
            "with_payload": True,
        }
        if score_threshold is not None:
            body["score_threshold"] = score_threshold
        if filters:
            body["filter"] = filters

        client = await self._get_client()
        resp = await client.post(
            f"/collections/{self.collection}/points/search",
            json=body,
        )
        resp.raise_for_status()
        results = resp.json().get("result", [])

        return [
            {
                "id": r["id"],
                "score": r["score"],
                "text": r.get("payload", {}).get("text", ""),
                "source": r.get("payload", {}).get("source", ""),
                "metadata": r.get("payload", {}).get("metadata", {}),
            }
            for r in results
        ]

    # ------------------------------------------------------------------
    # Hybrid search (dense + BM25 sparse via Qdrant Query API)
    # ------------------------------------------------------------------

    async def hybrid_search(
        self,
        query_embedding: list[float],
        query_text: str,
        top_k: int = 10,
        filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Hybrid search using dense vectors + BM25 full-text with RRF fusion.

        Requires Qdrant 1.15+ with text index on 'text' payload field.
        Falls back to dense-only search if hybrid query fails.
        """
        # Qdrant Query API with prefetch (dense + BM25) + RRF fusion
        body: dict[str, Any] = {
            "prefetch": [
                {
                    "query": query_embedding,
                    "using": "dense",
                    "limit": top_k * 2,
                },
                {
                    "query": query_text,
                    "using": "text",
                    "limit": top_k * 2,
                },
            ],
            "query": {"fusion": "rrf"},
            "limit": top_k,
            "with_payload": True,
        }
        if filters:
            body["filter"] = filters

        client = await self._get_client()
        try:
            resp = await client.post(
                f"/collections/{self.collection}/points/query",
                json=body,
            )
            resp.raise_for_status()
            results = resp.json().get("result", {}).get("points", [])
        except Exception:
            # Fallback to dense-only search if hybrid not supported
            logger.debug("Hybrid search failed, falling back to dense-only")
            return await self.search(query_embedding, top_k=top_k, filters=filters)

        return [
            {
                "id": r["id"],
                "score": r.get("score", 0.0),
                "text": r.get("payload", {}).get("text", ""),
                "source": r.get("payload", {}).get("source", ""),
                "metadata": r.get("payload", {}).get("metadata", {}),
            }
            for r in results
        ]

    async def delete(self, point_ids: list[str | int]) -> None:
        """Delete points by ID."""
        client = await self._get_client()
        resp = await client.post(
            f"/collections/{self.collection}/points/delete",
            json={"points": point_ids},
            params={"wait": "true"},
        )
        resp.raise_for_status()

    async def drop_collection(self) -> bool:
        """Delete the entire collection from Qdrant.

        Returns True if deleted, False if it did not exist.
        """
        client = await self._get_client()
        resp = await client.delete(f"/collections/{self.collection}")
        if resp.status_code == 404:
            return False
        resp.raise_for_status()
        logger.info("Dropped Qdrant collection %s", self.collection)
        return True

    async def count(self) -> int:
        """Return the number of points in the collection."""
        client = await self._get_client()
        resp = await client.post(
            f"/collections/{self.collection}/points/count",
            json={"exact": True},
        )
        if resp.status_code == 404:
            return 0
        resp.raise_for_status()
        return resp.json().get("result", {}).get("count", 0)
