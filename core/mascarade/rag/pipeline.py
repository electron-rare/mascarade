"""RAG pipeline — multi-tool orchestration with retrieval."""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from mascarade.router.router import Router

from mascarade.config import settings
from mascarade.rag.embeddings import EmbeddingProvider
from mascarade.rag.query_cache import RAGQueryCache
from mascarade.rag.reranker import CrossEncoderReranker
from mascarade.rag.vectorstore import QdrantVectorStore

# LightRAG — optional graph-augmented backend
_lightrag_backend = None
if settings.lightrag_enabled:
    try:
        from mascarade.rag.lightrag_backend import LightRAGBackend, LIGHTRAG_AVAILABLE

        if LIGHTRAG_AVAILABLE:
            _lightrag_backend = LightRAGBackend()
            logger.info("LightRAG backend enabled")
        else:
            logger.warning("LightRAG enabled in config but lightrag-hku not installed")
    except Exception as exc:
        logger.warning("LightRAG init failed: %s", exc)

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
_CONTEXTUAL_PREAMBLE_PROMPT = """\
Generate a brief 1-2 sentence context description for this text chunk that will be \
prepended to improve search retrieval accuracy. Focus on what the chunk is about and \
its key information. Reply with ONLY the context description, no preamble.

Chunk:
{chunk_text}"""

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
        self._reranker = CrossEncoderReranker(settings.rag_reranker_model)
        self._query_cache: RAGQueryCache | None = (
            RAGQueryCache(
                similarity_threshold=settings.rag_cache_similarity_threshold,
                ttl=settings.rag_cache_ttl,
            )
            if settings.rag_cache_enabled
            else None
        )

    async def close(self) -> None:
        await self.vectorstore.close()
        await self.embeddings.close()
        if self._query_cache:
            await self._query_cache.close()

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

        # Step 0 — semantic query cache check (skip only classification + embed cost)
        _cache_embedding: list[float] | None = None
        if self._query_cache:
            _cache_embedding = await self.embeddings.embed_query(user_query)
            cached = await self._query_cache.get(user_query, _cache_embedding)
            if cached is not None:
                cached["tool_calls"] = ["cache_hit"]
                cached["elapsed_seconds"] = round(time.monotonic() - t0, 3)
                return cached

        # Step 0b — LightRAG for complex queries (multi-hop, question words)
        if _lightrag_backend and self._is_complex_query(user_query):
            try:
                lg_result = await _lightrag_backend.query(
                    user_query, mode="hybrid", top_k=top_k
                )
                if lg_result.get("status") == "ok" and lg_result.get("answer"):
                    lg_result["tool_calls"] = ["lightrag_hybrid"]
                    lg_result["elapsed_seconds"] = round(time.monotonic() - t0, 3)
                    lg_result["intent"] = "lightrag"
                    lg_result["sources"] = []
                    return lg_result
            except Exception as exc:
                logger.debug("LightRAG query failed, falling back to vector: %s", exc)
                tool_calls.append("lightrag_fallback")

        # Step 1 — classify intent
        if skip_classification:
            intent = "rag"
        else:
            intent = await self._classify_intent(user_query, provider=provider, model=model)
        tool_calls.append(f"classify:{intent}")

        # Step 2 — retrieve context if RAG (hybrid search + reranking)
        context_text = ""
        if intent == "rag":
            # Reuse embedding computed for cache check if available
            query_embedding = _cache_embedding or await self.embeddings.embed_query(user_query)
            if _cache_embedding is None:
                tool_calls.append("embed_query")

            # Hybrid search: dense + BM25 with RRF fusion
            results = await vs.hybrid_search(
                query_embedding,
                query_text=user_query,
                top_k=top_k * 2,  # over-retrieve for reranking
                filters=None,
            )
            tool_calls.append("hybrid_search")

            # Rerank: true cross-encoder (bge-reranker-v2-m3) or LLM fallback
            if results and len(results) > top_k:
                if settings.rag_reranker_enabled:
                    results = await self._rerank(user_query, results, top_k=top_k)
                    tool_calls.append(
                        "rerank:cross_encoder"
                        if self._reranker.is_available
                        else "rerank:llm_fallback"
                    )
                else:
                    results = results[:top_k]

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

        result = {
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

        # Store in semantic cache for future similar queries
        if self._query_cache and _cache_embedding is not None:
            import asyncio as _asyncio

            _asyncio.ensure_future(self._query_cache.set(user_query, _cache_embedding, result))

        return result

    # ------------------------------------------------------------------
    # Ingest
    # ------------------------------------------------------------------

    async def ingest(
        self,
        documents: list[dict[str, Any]],
        *,
        model: str = "text-embedding-3-small",
        collection: str | None = None,
        contextual_retrieval: bool | None = None,
    ) -> int:
        """Ingest documents into the vector store for future retrieval.

        Each document dict should contain at least ``text``.
        Optional keys: ``id``, ``source``, ``metadata``.

        Args:
            contextual_retrieval: If True (or None and
                ``settings.rag_contextual_retrieval_enabled`` is True), generate
                an LLM context preamble for each chunk before embedding.
                This reduces failed retrievals by ~49% (Anthropic research).
        """
        if not documents:
            return 0

        vs = self.vectorstore
        if collection and collection != vs.collection:
            vs = QdrantVectorStore(base_url=vs.base_url, collection=collection)

        # Contextual Retrieval: prepend LLM-generated preamble to each chunk
        use_ctx = (
            contextual_retrieval
            if contextual_retrieval is not None
            else settings.rag_contextual_retrieval_enabled
        )
        if use_ctx:
            documents = await self._add_contextual_preambles(documents)

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
        """Rerank with true cross-encoder (bge-reranker-v2-m3), LLM fallback.

        Cross-encoder gives +10-30% precision vs dense-only retrieval.
        Falls back to LLM scoring when sentence-transformers is not installed.
        """
        if not results:
            return results

        # Attempt true cross-encoder reranking
        if self._reranker.is_available:
            try:
                return await self._reranker.rerank(query, results, top_k=top_k)
            except Exception as exc:
                logger.debug("Cross-encoder reranking failed (%s), falling back to LLM", exc)

        # LLM fallback: ask the LLM to score relevance on 0-10 scale
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
            scores = [float(s.strip()) for s in resp.text.strip().split(",") if s.strip()]
            if len(scores) == len(results):
                for i, score in enumerate(scores):
                    results[i]["rerank_score"] = score
                results.sort(key=lambda r: r.get("rerank_score", 0), reverse=True)
        except Exception as exc:
            logger.debug("LLM reranking fallback failed (%s), keeping original order", exc)

        return results[:top_k]

    async def _add_contextual_preambles(
        self, documents: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Prepend an LLM-generated context description to each chunk's text.

        Implements the Anthropic Contextual Retrieval pattern:
        https://www.anthropic.com/news/contextual-retrieval

        Reduces failed retrievals by ~49% at indexation cost of ~1 token/chunk.
        Uses ``settings.rag_contextual_retrieval_model`` (default: claude-haiku).
        """
        enriched: list[dict[str, Any]] = []
        model = settings.rag_contextual_retrieval_model
        # Extract provider from model prefix if present (e.g. "anthropic/claude-haiku")
        provider: str | None = None
        if "/" in model:
            provider, model = model.split("/", 1)

        for doc in documents:
            chunk_text = doc.get("text", "")
            if not chunk_text.strip():
                enriched.append(doc)
                continue
            try:
                resp = await self.router.send(
                    [
                        {
                            "role": "user",
                            "content": _CONTEXTUAL_PREAMBLE_PROMPT.format(
                                chunk_text=chunk_text[:2000]
                            ),
                        }
                    ],
                    temperature=0.0,
                    max_tokens=120,
                    provider=provider,
                    model=model,
                )
                preamble = resp.text.strip()
                enriched_doc = {**doc, "text": f"{preamble}\n\n{chunk_text}"}
            except Exception as exc:
                logger.debug("Contextual preamble generation failed (%s), using raw chunk", exc)
                enriched_doc = doc
            enriched.append(enriched_doc)

        logger.info("Contextual retrieval: enriched %d/%d chunks", len(enriched), len(documents))
        return enriched

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

    @staticmethod
    def _is_complex_query(query: str) -> bool:
        """Detect complex queries that benefit from graph-augmented retrieval.

        Heuristic: question words, multi-hop patterns, comparison queries.
        """
        q = query.lower().strip()
        # Question words suggesting multi-hop or relational queries
        question_patterns = (
            "how", "why", "what is the relationship",
            "compare", "difference between", "connection between",
            "explain how", "what causes", "what are the",
            "who", "which", "where does", "when did",
        )
        return any(q.startswith(p) or f" {p} " in f" {q} " for p in question_patterns)

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
