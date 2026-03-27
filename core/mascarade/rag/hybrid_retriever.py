"""Hybrid retriever — parallel vector + graph + SQL with RRF fusion.

Runs three retrieval backends concurrently (Qdrant vector, LightRAG graph,
Grist SQL) and merges results using Reciprocal Rank Fusion.  Any backend
that is unavailable, unconfigured, or times out is silently skipped so the
pipeline always returns the best context it can.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger("mascarade.rag.hybrid_retriever")


# ------------------------------------------------------------------
# Data types
# ------------------------------------------------------------------

@dataclass(slots=True)
class RetrievalChunk:
    """A single retrieval result from any backend."""

    text: str
    source: str
    score: float
    backend: str  # "vector" | "graph" | "sql"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class HybridResult:
    """Merged result from all backends."""

    chunks: list[RetrievalChunk]
    backends_used: list[str]
    backends_failed: dict[str, str]  # backend -> error message


# ------------------------------------------------------------------
# RRF merger
# ------------------------------------------------------------------

_RRF_K = 60  # standard constant for reciprocal rank fusion


def _reciprocal_rank_fusion(
    ranked_lists: dict[str, list[RetrievalChunk]],
    weights: dict[str, float],
    top_k: int,
) -> list[RetrievalChunk]:
    """Merge multiple ranked lists using weighted RRF.

    For each chunk, score = sum over backends of weight / (k + rank).
    Chunks are deduplicated by (text[:200], source) fingerprint.
    """
    # Accumulate RRF scores keyed by dedup fingerprint
    scores: dict[str, float] = {}
    best_chunk: dict[str, RetrievalChunk] = {}

    for backend, chunks in ranked_lists.items():
        w = weights.get(backend, 0.0)
        for rank, chunk in enumerate(chunks, start=1):
            fp = (chunk.text[:200], chunk.source)
            key = hash(fp)
            rrf = w / (_RRF_K + rank)
            scores[key] = scores.get(key, 0.0) + rrf
            # Keep the highest-original-score variant
            if key not in best_chunk or chunk.score > best_chunk[key].score:
                best_chunk[key] = chunk

    # Sort by fused score descending
    sorted_keys = sorted(scores, key=scores.__getitem__, reverse=True)[:top_k]
    result = []
    for key in sorted_keys:
        chunk = best_chunk[key]
        chunk.score = round(scores[key], 6)
        result.append(chunk)
    return result


# ------------------------------------------------------------------
# HybridRetriever
# ------------------------------------------------------------------

class HybridRetriever:
    """Runs vector + graph + SQL retrieval in parallel, merges results."""

    def __init__(
        self,
        *,
        vectorstore: Any | None = None,
        embeddings: Any | None = None,
        weights: dict[str, float] | None = None,
        timeout: float = 15.0,
    ) -> None:
        self._vectorstore = vectorstore
        self._embeddings = embeddings
        self._weights = weights or {"vector": 0.4, "graph": 0.4, "sql": 0.2}
        self._timeout = timeout

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def retrieve(
        self,
        query: str,
        *,
        top_k: int = 10,
        query_embedding: list[float] | None = None,
        grist_doc_id: str | None = None,
        grist_sql: str | None = None,
    ) -> HybridResult:
        """Run all backends in parallel and return fused results.

        Args:
            query: Natural-language query.
            top_k: Final number of chunks to return after fusion.
            query_embedding: Pre-computed embedding (avoids double embed).
            grist_doc_id: Grist document ID for SQL backend.
            grist_sql: Raw SQL to execute on Grist.  When *None* the SQL
                backend is skipped (no auto-SQL-generation).
        """
        ranked_lists: dict[str, list[RetrievalChunk]] = {}
        backends_used: list[str] = []
        backends_failed: dict[str, str] = {}

        # Build coroutines for available backends
        tasks: dict[str, asyncio.Task[list[RetrievalChunk]]] = {}

        # 1. Vector
        if self._vectorstore is not None:
            tasks["vector"] = asyncio.create_task(
                self._vector_search(query, query_embedding, top_k=top_k * 2)
            )

        # 2. Graph (LightRAG)
        tasks["graph"] = asyncio.create_task(
            self._graph_search(query, top_k=top_k * 2)
        )

        # 3. SQL (Grist)
        if grist_doc_id and grist_sql:
            tasks["sql"] = asyncio.create_task(
                self._sql_search(grist_doc_id, grist_sql)
            )

        # Await all with per-backend timeout
        for backend, task in tasks.items():
            try:
                result = await asyncio.wait_for(asyncio.shield(task), self._timeout)
                if result:
                    ranked_lists[backend] = result
                    backends_used.append(backend)
            except asyncio.TimeoutError:
                backends_failed[backend] = f"timeout ({self._timeout}s)"
                task.cancel()
                logger.warning("Hybrid retriever: %s backend timed out", backend)
            except Exception as exc:
                backends_failed[backend] = str(exc)
                logger.warning("Hybrid retriever: %s backend failed: %s", backend, exc)

        # Fuse
        if not ranked_lists:
            return HybridResult(chunks=[], backends_used=[], backends_failed=backends_failed)

        fused = _reciprocal_rank_fusion(ranked_lists, self._weights, top_k)
        return HybridResult(
            chunks=fused,
            backends_used=backends_used,
            backends_failed=backends_failed,
        )

    # ------------------------------------------------------------------
    # Backend implementations
    # ------------------------------------------------------------------

    async def _vector_search(
        self,
        query: str,
        query_embedding: list[float] | None,
        *,
        top_k: int,
    ) -> list[RetrievalChunk]:
        """Qdrant dense+BM25 hybrid search via existing vectorstore."""
        if self._vectorstore is None:
            return []

        if query_embedding is None and self._embeddings is not None:
            query_embedding = await self._embeddings.embed_query(query)
        if query_embedding is None:
            return []

        results = await self._vectorstore.hybrid_search(
            query_embedding, query_text=query, top_k=top_k, filters=None,
        )
        return [
            RetrievalChunk(
                text=r.get("text", ""),
                source=r.get("source", r.get("id", "qdrant")),
                score=r.get("score", 0.0),
                backend="vector",
                metadata={k: v for k, v in r.items() if k not in ("text", "source", "score")},
            )
            for r in results
        ]

    async def _graph_search(self, query: str, *, top_k: int) -> list[RetrievalChunk]:
        """LightRAG graph retrieval — imported conditionally."""
        try:
            from mascarade.config import settings

            if not settings.lightrag_enabled:
                return []

            from mascarade.rag.lightrag_backend import LightRAGBackend, LIGHTRAG_AVAILABLE

            if not LIGHTRAG_AVAILABLE:
                return []

            backend = LightRAGBackend()
            result = await backend.query(query, mode="hybrid", top_k=top_k)
            if result.get("status") != "ok" or not result.get("answer"):
                return []

            # LightRAG returns a single synthesised answer; wrap as one chunk
            return [
                RetrievalChunk(
                    text=result["answer"],
                    source="lightrag",
                    score=1.0,
                    backend="graph",
                    metadata={"mode": result.get("mode", "hybrid")},
                )
            ]
        except Exception as exc:
            logger.debug("Graph search unavailable: %s", exc)
            return []

    async def _sql_search(self, doc_id: str, sql: str) -> list[RetrievalChunk]:
        """Grist SQL query — imported conditionally."""
        try:
            from mascarade.mcp.grist_mcp import get_client

            client = get_client()
            if client is None:
                return []

            result = await client.sql_query(doc_id, sql)
            records = result.get("records", [])
            columns = result.get("columns", [])

            chunks: list[RetrievalChunk] = []
            for i, record in enumerate(records):
                fields = record.get("fields", record) if isinstance(record, dict) else record
                # Format row as readable text
                if isinstance(fields, dict):
                    text = " | ".join(f"{k}: {v}" for k, v in fields.items())
                elif isinstance(fields, (list, tuple)) and columns:
                    text = " | ".join(
                        f"{columns[j]}: {v}" for j, v in enumerate(fields) if j < len(columns)
                    )
                else:
                    text = str(fields)

                chunks.append(
                    RetrievalChunk(
                        text=text,
                        source=f"grist:{doc_id}",
                        score=1.0 - (i * 0.01),  # preserve SQL ordering
                        backend="sql",
                    )
                )
            return chunks
        except Exception as exc:
            logger.debug("SQL search unavailable: %s", exc)
            return []
