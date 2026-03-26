"""RAG pipeline — multi-tool orchestration with retrieval."""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from mascarade.router.router import Router

from mascarade.rag.embeddings import EmbeddingProvider
from mascarade.rag.vectorstore import QdrantVectorStore

logger = logging.getLogger("mascarade.rag.pipeline")

# Intent classification prompt
_INTENT_PROMPT = """\
Classify the user's query into exactly one category. Reply with ONLY the category name.

Categories:
- rag: The query asks about specific documents, knowledge, internal data, or stored information.
- web: The query asks about current events, live data, or needs a web search.
- general: The query is a general question or creative task that does not need retrieval.

User query: {query}
Category:"""

# RAG system prompt template
_RAG_SYSTEM_PROMPT = """\
You are a helpful assistant with access to a knowledge base.
Answer the user's question using ONLY the context provided below.
If the context does not contain enough information, say so clearly.

--- Retrieved Context ---
{context}
--- End Context ---"""


class RAGPipeline:
    """Orchestrate retrieval + generation with tool routing."""

    def __init__(
        self,
        router: Router,
        vectorstore: QdrantVectorStore | None = None,
        embeddings: EmbeddingProvider | None = None,
    ) -> None:
        self.router = router
        self.vectorstore = vectorstore or QdrantVectorStore()
        self.embeddings = embeddings or EmbeddingProvider()

    async def close(self) -> None:
        await self.vectorstore.close()
        await self.embeddings.close()

    # ------------------------------------------------------------------
    # Query pipeline
    # ------------------------------------------------------------------

    async def query(
        self,
        user_query: str,
        *,
        tools: list[str] | None = None,
        top_k: int = 5,
        score_threshold: float | None = None,
        provider: str | None = None,
        model: str | None = None,
        collection: str | None = None,
        skip_classification: bool = False,
    ) -> dict[str, Any]:
        """Smart query pipeline.

        1. Classify query intent (RAG vs general vs web search)
        2. If RAG: embed query, search Qdrant, build context
        3. If web: delegate to web search tool (placeholder)
        4. Generate response with retrieved context
        5. Return response + sources + tool calls used
        """
        t0 = time.monotonic()
        tool_calls: list[str] = []
        sources: list[dict[str, Any]] = []

        # Use a specific collection if requested
        vs = self.vectorstore
        if collection and collection != vs.collection:
            vs = QdrantVectorStore(base_url=vs.base_url, collection=collection)

        # Step 1 — classify intent
        if skip_classification:
            intent = "rag"
        else:
            intent = await self._classify_intent(user_query, provider=provider, model=model)
        tool_calls.append(f"classify:{intent}")

        # Step 2 — retrieve context if RAG (hybrid search + reranking)
        context_text = ""
        if intent == "rag":
            query_embedding = await self.embeddings.embed_query(user_query)
            tool_calls.append("embed_query")

            # Hybrid search: dense + BM25 with RRF fusion
            results = await vs.hybrid_search(
                query_embedding,
                query_text=user_query,
                top_k=top_k * 2,  # over-retrieve for reranking
                filters=None,
            )
            tool_calls.append("hybrid_search")

            # Rerank: use LLM to score relevance (lightweight CRAG pattern)
            if results and len(results) > top_k:
                results = await self._rerank(user_query, results, top_k=top_k)
                tool_calls.append("rerank")

            # CRAG: check if results are relevant enough
            if results and results[0].get("score", 0) < 0.3:
                # Low confidence — try web search fallback
                tool_calls.append("crag:low_confidence")
                web_context = await self._web_search_fallback(user_query)
                if web_context:
                    context_text = web_context
                    tool_calls.append("web_search_fallback")

            if not context_text:
                sources = results[:top_k]
                if sources:
                    context_text = "\n\n".join(
                        f"[{i+1}] (score={r['score']:.3f}) {r['text']}"
                        for i, r in enumerate(sources)
                    )
                else:
                    context_text = "(No relevant documents found in the knowledge base.)"

        elif intent == "web":
            web_context = await self._web_search_fallback(user_query)
            context_text = web_context or "(Web search returned no results.)"
            tool_calls.append("web_search")

        # Step 3 — generate
        system_prompt = _RAG_SYSTEM_PROMPT.format(context=context_text) if context_text else None
        messages = [{"role": "user", "content": user_query}]

        llm_response = await self.router.send(
            messages,
            system=system_prompt,
            provider=provider,
            model=model,
        )
        tool_calls.append("llm_generate")

        elapsed = time.monotonic() - t0

        return {
            "answer": llm_response.text,
            "intent": intent,
            "sources": sources,
            "tool_calls": tool_calls,
            "provider": llm_response.provider,
            "model": llm_response.model,
            "usage": {
                "prompt_tokens": (
                    llm_response.usage.get("prompt_tokens", 0) if llm_response.usage else 0
                ),
                "completion_tokens": (
                    llm_response.usage.get("completion_tokens", 0) if llm_response.usage else 0
                ),
            },
            "elapsed_seconds": round(elapsed, 3),
        }

    # ------------------------------------------------------------------
    # Ingest
    # ------------------------------------------------------------------

    async def ingest(
        self,
        documents: list[dict[str, Any]],
        *,
        model: str = "text-embedding-3-small",
        collection: str | None = None,
    ) -> int:
        """Ingest documents into the vector store for future retrieval.

        Each document dict should contain at least ``text``.
        Optional keys: ``id``, ``source``, ``metadata``.
        """
        if not documents:
            return 0

        vs = self.vectorstore
        if collection and collection != vs.collection:
            vs = QdrantVectorStore(base_url=vs.base_url, collection=collection)

        # Ensure collection exists with the right dimension
        dimension = self.embeddings.dimension_for_model(model)
        await vs.ensure_collection(dimension=dimension)

        texts = [doc.get("text", "") for doc in documents]
        embeddings = await self.embeddings.embed(texts, model=model)

        count = await vs.upsert(documents, embeddings)
        logger.info("Ingested %d documents into %s", count, vs.collection)
        return count

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    async def _rerank(
        self,
        query: str,
        results: list[dict[str, Any]],
        *,
        top_k: int = 5,
    ) -> list[dict[str, Any]]:
        """Rerank results using LLM-based relevance scoring.

        Lightweight cross-encoder approximation: asks the LLM to score
        each result's relevance to the query on a 0-10 scale.
        """
        if not results:
            return results

        # Build scoring prompt
        docs_text = "\n".join(f"DOC_{i}: {r['text'][:300]}" for i, r in enumerate(results))
        prompt = (
            f"Rate each document's relevance to the query on a scale 0-10. "
            f"Reply with ONLY comma-separated scores (e.g. 8,3,9,1,7).\n\n"
            f"Query: {query}\n\n{docs_text}"
        )

        try:
            resp = await self.router.send(
                [{"role": "user", "content": prompt}],
                temperature=0.0,
                max_tokens=100,
            )
            scores_text = resp.text.strip()
            scores = [float(s.strip()) for s in scores_text.split(",") if s.strip()]
            if len(scores) == len(results):
                for i, score in enumerate(scores):
                    results[i]["rerank_score"] = score
                results.sort(key=lambda r: r.get("rerank_score", 0), reverse=True)
        except Exception as exc:
            logger.debug("Reranking failed (%s), keeping original order", exc)

        return results[:top_k]

    async def _web_search_fallback(self, query: str) -> str:
        """Search the web via SearXNG as a CRAG fallback.

        Returns formatted search results text, or empty string if unavailable.
        """
        try:
            from mascarade.mcp.searxng import SearXNGMcpClient

            searxng = SearXNGMcpClient()
            if not searxng.is_configured:
                return ""
            return await searxng.search_text(query, limit=5)
        except Exception as exc:
            logger.debug("Web search fallback failed: %s", exc)
            return ""

    async def _classify_intent(
        self,
        query: str,
        *,
        provider: str | None = None,
        model: str | None = None,
    ) -> str:
        """Use the LLM router to classify query intent."""
        try:
            resp = await self.router.send(
                [{"role": "user", "content": _INTENT_PROMPT.format(query=query)}],
                temperature=0.0,
                max_tokens=16,
                provider=provider,
                model=model,
            )
            intent = resp.text.strip().lower()
            if intent in {"rag", "web", "general"}:
                return intent
            logger.debug("Unexpected intent classification %r, defaulting to rag", intent)
            return "rag"
        except Exception as exc:
            logger.warning("Intent classification failed (%s), defaulting to rag", exc)
            return "rag"
