"""Unified knowledge base search handler with multi-tier fallback.

Fallback chain:
    1. KnowledgeBaseClient (Memos / Docmost / kxkm) — primary provider
    2. Qdrant vector search (collection: settings.kb_qdrant_collection) — local fallback
    3. SearXNG web search — last resort if Qdrant confidence is too low

Each result includes a ``source`` field: "kb", "qdrant", or "web".
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from mascarade.config import settings

logger = logging.getLogger("mascarade.integrations.kb_handler")


class KBSearchHandler:
    """Orchestrates KB search across provider, Qdrant, and optional web fallback."""

    async def search(
        self,
        query: str,
        limit: int = 10,
        *,
        project_id: str | None = None,
        federation_scope: list[str] | tuple[str, ...] | None = None,
        knowledge_scope: str = "project",
    ) -> list[dict[str, Any]]:
        """Return results from the best available source.

        Tries each tier in order and stops as soon as useful results are found,
        unless the Qdrant score is below the configured threshold, in which case
        web results are appended.
        """
        if not query.strip():
            return []

        limit = max(1, min(limit, 50))

        # Tier 1: KB provider (Memos / Docmost / kxkm)
        try:
            results = await self._search_kb(
                query,
                limit,
                project_id=project_id,
                federation_scope=federation_scope,
                knowledge_scope=knowledge_scope,
            )
            results = [r for r in results if isinstance(r, dict)]
            if results:
                return results
            logger.debug("KB provider returned no results for %r; trying Qdrant", query)
        except TimeoutError:
            logger.warning("KB provider timed out for %r; falling back to Qdrant", query)
        except Exception as exc:
            logger.warning("KB provider error (%s); falling back to Qdrant", exc)

        # Tier 2: Qdrant vector search
        qdrant_results: list[dict[str, Any]] = []
        try:
            qdrant_results = await self._search_qdrant(query, limit)
            qdrant_results = [r for r in qdrant_results if isinstance(r, dict)]
        except Exception as exc:
            logger.warning("Qdrant search error (%s); continuing without vector results", exc)

        # Tier 3: Web fallback when Qdrant confidence is insufficient
        if settings.kb_enable_web_fallback:
            max_score = max(
                (r.get("score", 0.0) for r in qdrant_results),
                default=0.0,
            )
            if max_score < settings.kb_qdrant_score_threshold:
                try:
                    web_results = await self._search_web(query)
                except Exception as exc:
                    logger.warning("Web fallback failed (%s); returning Qdrant results", exc)
                    return qdrant_results
                return qdrant_results + web_results

        return qdrant_results

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _search_kb(
        self,
        query: str,
        limit: int,
        *,
        project_id: str | None,
        federation_scope: list[str] | tuple[str, ...] | None,
        knowledge_scope: str,
    ) -> list[dict[str, Any]]:
        from mascarade.integrations.knowledge_base import KnowledgeBaseClient

        kb = KnowledgeBaseClient()
        try:
            results: list[dict[str, Any]] = await asyncio.wait_for(
                kb.search(
                    query,
                    limit=limit,
                    project_id=project_id,
                    federation_scope=federation_scope,
                    knowledge_scope=knowledge_scope,
                ),
                timeout=settings.kb_search_timeout_seconds,
            )
        finally:
            await kb.close()

        valid = [r for r in results if isinstance(r, dict)]
        return [{**r, "source": "kb"} for r in valid]

    async def _search_qdrant(self, query: str, limit: int) -> list[dict[str, Any]]:
        from mascarade.rag.embeddings import EmbeddingProvider
        from mascarade.rag.vectorstore import QdrantVectorStore

        embedder = EmbeddingProvider()
        try:
            embeddings = await embedder.embed([query])
        finally:
            await embedder.close()

        store = QdrantVectorStore(
            collection=settings.kb_qdrant_collection,
            timeout=settings.kb_search_timeout_seconds,
        )
        try:
            try:
                results = await store.hybrid_search(
                    query_embedding=embeddings[0],
                    query_text=query,
                    top_k=limit,
                )
            except Exception:
                # hybrid_search requires Qdrant 1.15+ with sparse index; fall back to dense
                results = await store.search(
                    query_embedding=embeddings[0],
                    top_k=limit,
                )
        finally:
            await store.close()

        valid = [r for r in results if isinstance(r, dict)]
        return [{**r, "source": "qdrant"} for r in valid]

    async def _search_web(self, query: str) -> list[dict[str, Any]]:
        try:
            from mascarade.mcp.searxng import SearXNGMcpClient

            searxng = SearXNGMcpClient()
            if not searxng.is_configured:
                return []
            text = await searxng.search_text(query, limit=5)
            if text:
                return [{"source": "web", "text": text, "score": 0.0}]
        except Exception as exc:
            logger.debug("Web search fallback failed: %s", exc)
        return []
