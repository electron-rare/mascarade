"""LightRAG graph-augmented RAG backend for mascarade.

Wraps the lightrag-hku library to provide knowledge-graph-enhanced retrieval.
Uses Neo4J for graph storage and Qdrant for vector storage when available,
with graceful fallbacks to local storage backends.
"""

from __future__ import annotations

import logging
import os
from typing import Any

from mascarade.config import settings

logger = logging.getLogger("mascarade.rag.lightrag_backend")

# Graceful import — lightrag-hku is an optional dependency
try:
    from lightrag import LightRAG, QueryParam
    from lightrag.utils import EmbeddingFunc

    LIGHTRAG_AVAILABLE = True
except ImportError:
    LIGHTRAG_AVAILABLE = False
    LightRAG = None  # type: ignore[assignment,misc]
    QueryParam = None  # type: ignore[assignment,misc]
    EmbeddingFunc = None  # type: ignore[assignment,misc]

# Valid query modes
_VALID_MODES = {"naive", "local", "global", "hybrid", "mix"}


class LightRAGBackend:
    """Graph-augmented RAG using LightRAG (HKU).

    Provides entity extraction, knowledge graph construction, and
    multi-mode retrieval (naive / local / global / hybrid / mix).

    Configuration is pulled from mascarade settings:
    - ``LIGHTRAG_ENABLED``: master toggle (default False)
    - ``LIGHTRAG_WORKING_DIR``: persistent storage directory
    - ``LIGHTRAG_EXTRACTION_MODEL``: Ollama model for entity extraction
    """

    def __init__(
        self,
        working_dir: str | None = None,
        llm_model: str | None = None,
    ) -> None:
        if not LIGHTRAG_AVAILABLE:
            raise ImportError(
                "lightrag-hku is not installed. "
                "Install with: pip install lightrag-hku"
            )

        self._working_dir = working_dir or settings.lightrag_working_dir
        self._llm_model = llm_model or settings.lightrag_extraction_model
        self._rag: LightRAG | None = None

    async def _ensure_rag(self) -> LightRAG:
        """Lazy-init the LightRAG instance."""
        if self._rag is not None:
            return self._rag

        os.makedirs(self._working_dir, exist_ok=True)

        # Determine storage backends based on environment
        graph_storage = "NetworkXStorage"
        vector_storage = "NanoVectorDBStorage"
        kv_storage = "JsonKVStorage"

        # Use Neo4J if available
        neo4j_uri = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
        neo4j_user = os.environ.get("NEO4J_USER", "neo4j")
        neo4j_password = os.environ.get("NEO4J_PASSWORD", "")
        if neo4j_password:
            graph_storage = "Neo4JStorage"

        # Build LLM function that routes through Ollama
        ollama_base = settings.ollama_base_url.rstrip("/")
        model_name = self._llm_model

        async def llm_model_func(
            prompt: str,
            system_prompt: str | None = None,
            history_messages: list[dict[str, str]] | None = None,
            **kwargs: Any,
        ) -> str:
            """Route LLM calls through Ollama."""
            import httpx

            messages: list[dict[str, str]] = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            if history_messages:
                messages.extend(history_messages)
            messages.append({"role": "user", "content": prompt})

            async with httpx.AsyncClient(timeout=180.0) as client:
                resp = await client.post(
                    f"{ollama_base}/api/chat",
                    json={
                        "model": model_name,
                        "messages": messages,
                        "stream": False,
                        "options": {"temperature": 0.0},
                    },
                )
                resp.raise_for_status()
                return resp.json()["message"]["content"]

        # Build embedding function using mascarade's EmbeddingProvider
        async def embedding_func(texts: list[str]) -> Any:
            """Route embeddings through mascarade's EmbeddingProvider.

            Returns numpy ndarray as required by LightRAG.
            """
            import numpy as np

            from mascarade.rag.embeddings import EmbeddingProvider

            provider = EmbeddingProvider()
            try:
                result = await provider.embed(texts)
                return np.array(result, dtype=np.float32)
            finally:
                await provider.close()

        # Detect embedding dimension from configured model
        from mascarade.rag.embeddings import EmbeddingProvider

        embed_provider = EmbeddingProvider()
        embed_dim = embed_provider.dimension_for_model(
            settings.rag_embedding_model or "text-embedding-3-small"
        )

        rag_kwargs: dict[str, Any] = {
            "working_dir": self._working_dir,
            "llm_model_func": llm_model_func,
            "llm_model_name": model_name,
            "embedding_func": EmbeddingFunc(
                embedding_dim=embed_dim,
                max_token_size=8192,
                func=embedding_func,
            ),
            "graph_storage": graph_storage,
            "vector_storage": vector_storage,
            "kv_storage": kv_storage,
            "chunk_token_size": settings.rag_chunk_size,
            "chunk_overlap_token_size": settings.rag_chunk_overlap,
        }

        # Neo4J connection params
        if graph_storage == "Neo4JStorage":
            rag_kwargs["vector_db_storage_cls_kwargs"] = {
                "neo4j_uri": neo4j_uri,
                "neo4j_user": neo4j_user,
                "neo4j_password": neo4j_password,
            }

        self._rag = LightRAG(**rag_kwargs)
        await self._rag.initialize_storages()
        logger.info(
            "LightRAG initialized: dir=%s, graph=%s, vector=%s, llm=%s",
            self._working_dir,
            graph_storage,
            vector_storage,
            model_name,
        )
        return self._rag

    async def ingest(self, text: str, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        """Ingest a text document into the knowledge graph.

        LightRAG will extract entities and relations, build the graph,
        and index chunks for retrieval.

        Args:
            text: The document text to ingest.
            metadata: Optional metadata (stored alongside but not used by LightRAG).

        Returns:
            Dict with ingestion status and stats.
        """
        rag = await self._ensure_rag()
        try:
            await rag.ainsert(text)
            return {
                "status": "ok",
                "chars_ingested": len(text),
                "metadata": metadata or {},
            }
        except Exception as exc:
            logger.error("LightRAG ingest failed: %s", exc)
            return {"status": "error", "error": str(exc)}

    async def query(
        self,
        text: str,
        mode: str = "hybrid",
        top_k: int = 5,
    ) -> dict[str, Any]:
        """Query the knowledge graph with multi-mode retrieval.

        Args:
            text: The query text.
            mode: Retrieval mode — one of naive, local, global, hybrid, mix.
            top_k: Number of results to return.

        Returns:
            Dict with answer, mode used, and metadata.
        """
        if mode not in _VALID_MODES:
            mode = "hybrid"

        rag = await self._ensure_rag()
        try:
            param = QueryParam(mode=mode, top_k=top_k, only_need_context=False)
            result = await rag.aquery(text, param=param)

            return {
                "answer": result if isinstance(result, str) else str(result),
                "mode": mode,
                "top_k": top_k,
                "status": "ok",
            }
        except Exception as exc:
            logger.error("LightRAG query failed (mode=%s): %s", mode, exc)
            return {"answer": "", "mode": mode, "status": "error", "error": str(exc)}

    async def get_stats(self) -> dict[str, Any]:
        """Return basic statistics about the knowledge graph.

        Returns:
            Dict with storage info, entity/relation counts where available.
        """
        stats: dict[str, Any] = {
            "available": LIGHTRAG_AVAILABLE,
            "enabled": settings.lightrag_enabled,
            "working_dir": self._working_dir,
            "llm_model": self._llm_model,
            "initialized": self._rag is not None,
        }

        if self._rag is not None:
            stats["graph_storage"] = self._rag.graph_storage
            stats["vector_storage"] = self._rag.vector_storage

            # Try to get graph node/edge counts from working dir
            import json
            import pathlib

            wd = pathlib.Path(self._working_dir)
            graph_file = wd / "graph_chunk_entity_relation.graphml"
            if graph_file.exists():
                stats["graph_file_size_bytes"] = graph_file.stat().st_size

            # Count KV entries
            kv_file = wd / "kv_store_full_docs.json"
            if kv_file.exists():
                try:
                    data = json.loads(kv_file.read_text())
                    stats["documents_count"] = len(data)
                except Exception:
                    pass

        return stats
