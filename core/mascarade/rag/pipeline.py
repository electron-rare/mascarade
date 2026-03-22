"""RAG pipeline — multi-tool orchestration with retrieval."""

from __future__ import annotations

import logging
import time
from typing import Any, TYPE_CHECKING

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

        # Step 2 — retrieve context if RAG
        context_text = ""
        if intent == "rag":
            query_embedding = await self.embeddings.embed_query(user_query)
            tool_calls.append("embed_query")

            results = await vs.search(
                query_embedding,
                top_k=top_k,
                score_threshold=score_threshold,
            )
            tool_calls.append("vector_search")

            sources = results
            if results:
                context_text = "\n\n".join(
                    f"[{i+1}] (score={r['score']:.3f}) {r['text']}"
                    for i, r in enumerate(results)
                )
            else:
                context_text = "(No relevant documents found in the knowledge base.)"

        elif intent == "web":
            tool_calls.append("web_search:placeholder")
            context_text = "(Web search is not yet implemented. Answering from general knowledge.)"

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
                "prompt_tokens": llm_response.usage.get("prompt_tokens", 0) if llm_response.usage else 0,
                "completion_tokens": llm_response.usage.get("completion_tokens", 0) if llm_response.usage else 0,
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
