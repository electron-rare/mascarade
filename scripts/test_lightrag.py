#!/usr/bin/env python3
"""Test LightRAG integration by ingesting Kill_LIFE specs and querying.

Usage:
    pip install lightrag-hku nano-vectordb networkx
    python scripts/test_lightrag.py

Requires Ollama running with a model (mistral:7b or bge-m3:latest for embeddings).
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
import time
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger("test_lightrag")

# Paths to Kill_LIFE spec files
SPEC_DIR = Path("/Users/electron/Kill_LIFE/specs")
SPEC_FILES = ["00_intake.md", "01_spec.md", "02_arch.md"]

# Ollama config — Tower has mistral:7b and bge-m3
OLLAMA_BASE = os.environ.get("OLLAMA_BASE_URL", "http://192.168.0.120:11434")
LLM_MODEL = os.environ.get("LIGHTRAG_LLM_MODEL", "qwen3:4b")
EMBED_MODEL = os.environ.get("LIGHTRAG_EMBED_MODEL", "bge-m3:latest")
WORKING_DIR = "/tmp/mascarade_lightrag_test"

# Test queries
TEST_QUERIES = [
    ("What components in Kill_LIFE handle firmware validation?", "hybrid"),
    ("How do the BMAD agents interact with the spec documents?", "hybrid"),
    ("What are the risks identified in the intake document?", "local"),
    ("How does the spec-driven chain work from intake to tasks?", "global"),
    ("Compare the architecture decisions with the non-objectives", "mix"),
]


def check_dependencies() -> bool:
    """Verify required packages are installed."""
    missing = []
    try:
        import lightrag  # noqa: F401
    except ImportError:
        missing.append("lightrag-hku")
    try:
        import nano_vectordb  # noqa: F401
    except ImportError:
        missing.append("nano-vectordb")
    try:
        import networkx  # noqa: F401
    except ImportError:
        missing.append("networkx")

    if missing:
        logger.error(
            "Missing dependencies: %s\nInstall with: pip install %s",
            ", ".join(missing),
            " ".join(missing),
        )
        return False
    return True


async def check_ollama() -> bool:
    """Check that Ollama is reachable and has the required models."""
    import httpx

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"{OLLAMA_BASE}/api/tags")
            resp.raise_for_status()
            models = [m["name"] for m in resp.json().get("models", [])]
            logger.info("Ollama models available: %s", models)

            # Check LLM model
            llm_ok = any(LLM_MODEL.split(":")[0] in m for m in models)
            if not llm_ok:
                logger.error("LLM model %s not found in Ollama", LLM_MODEL)
                return False

            # Check embedding model
            embed_ok = any(EMBED_MODEL.split(":")[0] in m for m in models)
            if not embed_ok:
                logger.warning("Embedding model %s not found — will try anyway", EMBED_MODEL)

            return True
    except Exception as exc:
        logger.error("Cannot reach Ollama at %s: %s", OLLAMA_BASE, exc)
        return False


async def run_test() -> None:
    """Main test: ingest specs, query, report."""
    from lightrag import LightRAG, QueryParam
    from lightrag.utils import EmbeddingFunc
    import httpx

    os.makedirs(WORKING_DIR, exist_ok=True)

    # --- LLM function via Ollama ---
    async def llm_func(
        prompt: str,
        system_prompt: str | None = None,
        history_messages: list[dict[str, str]] | None = None,
        **kwargs,
    ) -> str:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        if history_messages:
            messages.extend(history_messages)
        messages.append({"role": "user", "content": prompt})

        async with httpx.AsyncClient(timeout=300.0) as client:
            resp = await client.post(
                f"{OLLAMA_BASE}/api/chat",
                json={"model": LLM_MODEL, "messages": messages, "stream": False,
                       "options": {"temperature": 0.0}},
            )
            resp.raise_for_status()
            return resp.json()["message"]["content"]

    # --- Embedding function via Ollama ---
    async def embed_func(texts: list[str]) -> "np.ndarray":
        import numpy as np
        embeddings = []
        async with httpx.AsyncClient(timeout=60.0) as client:
            for text in texts:
                resp = await client.post(
                    f"{OLLAMA_BASE}/api/embed",
                    json={"model": EMBED_MODEL, "input": text},
                )
                resp.raise_for_status()
                data = resp.json()
                # Ollama /api/embed returns {"embeddings": [[...]]}
                emb = data.get("embeddings", [data.get("embedding", [])])
                if isinstance(emb[0], list):
                    embeddings.append(emb[0])
                else:
                    embeddings.append(emb)
        return np.array(embeddings, dtype=np.float32)

    # Detect embedding dimension
    logger.info("Detecting embedding dimension for %s ...", EMBED_MODEL)
    test_emb = await embed_func(["test"])
    embed_dim = len(test_emb[0])
    logger.info("Embedding dimension: %d", embed_dim)

    # Initialize LightRAG
    logger.info("Initializing LightRAG (working_dir=%s, llm=%s) ...", WORKING_DIR, LLM_MODEL)
    rag = LightRAG(
        working_dir=WORKING_DIR,
        llm_model_func=llm_func,
        llm_model_name=LLM_MODEL,
        embedding_func=EmbeddingFunc(
            embedding_dim=embed_dim,
            max_token_size=8192,
            func=embed_func,
        ),
        graph_storage="NetworkXStorage",
        vector_storage="NanoVectorDBStorage",
        kv_storage="JsonKVStorage",
        chunk_token_size=1200,
        chunk_overlap_token_size=100,
    )
    await rag.initialize_storages()

    # --- INGEST ---
    logger.info("=" * 60)
    logger.info("PHASE 1: INGESTING Kill_LIFE SPECS")
    logger.info("=" * 60)

    for spec_file in SPEC_FILES:
        path = SPEC_DIR / spec_file
        if not path.exists():
            logger.warning("Spec file not found: %s", path)
            continue

        text = path.read_text(encoding="utf-8")
        logger.info("Ingesting %s (%d chars) ...", spec_file, len(text))
        t0 = time.monotonic()
        await rag.ainsert(text)
        elapsed = time.monotonic() - t0
        logger.info("  -> Ingested in %.1fs", elapsed)

    # --- STATS ---
    logger.info("")
    logger.info("=" * 60)
    logger.info("PHASE 2: GRAPH STATISTICS")
    logger.info("=" * 60)

    wd = Path(WORKING_DIR)
    graph_file = wd / "graph_chunk_entity_relation.graphml"
    if graph_file.exists():
        logger.info("Graph file size: %d bytes", graph_file.stat().st_size)
        # Parse with networkx for stats
        import networkx as nx
        G = nx.read_graphml(str(graph_file))
        logger.info("Graph nodes (entities): %d", G.number_of_nodes())
        logger.info("Graph edges (relations): %d", G.number_of_edges())
        # Sample some entities
        nodes = list(G.nodes(data=True))[:10]
        logger.info("Sample entities:")
        for node_id, attrs in nodes:
            entity_type = attrs.get("entity_type", "unknown")
            desc = attrs.get("description", "")[:100]
            logger.info("  - [%s] %s: %s", entity_type, node_id, desc)
    else:
        logger.warning("No graph file found at %s", graph_file)

    kv_file = wd / "kv_store_full_docs.json"
    if kv_file.exists():
        data = json.loads(kv_file.read_text())
        logger.info("KV store documents: %d", len(data))

    # --- QUERY ---
    logger.info("")
    logger.info("=" * 60)
    logger.info("PHASE 3: MULTI-MODE QUERIES")
    logger.info("=" * 60)

    results = []
    for query_text, mode in TEST_QUERIES:
        logger.info("")
        logger.info("Query [%s]: %s", mode, query_text)
        t0 = time.monotonic()
        try:
            param = QueryParam(mode=mode, top_k=5, only_need_context=False)
            answer = await rag.aquery(query_text, param=param)
            elapsed = time.monotonic() - t0
            logger.info("  -> Answer (%.1fs, %d chars):", elapsed, len(str(answer)))
            # Print first 500 chars
            answer_str = str(answer)[:500]
            for line in answer_str.split("\n"):
                logger.info("     %s", line)
            results.append({"query": query_text, "mode": mode, "answer": answer_str,
                            "elapsed": elapsed, "status": "ok"})
        except Exception as exc:
            elapsed = time.monotonic() - t0
            logger.error("  -> FAILED (%.1fs): %s", elapsed, exc)
            results.append({"query": query_text, "mode": mode, "error": str(exc),
                            "elapsed": elapsed, "status": "error"})

    # --- COMPARISON: naive vs hybrid ---
    logger.info("")
    logger.info("=" * 60)
    logger.info("PHASE 4: NAIVE vs HYBRID COMPARISON")
    logger.info("=" * 60)

    comparison_query = "How does the spec-driven chain work from intake to tasks?"
    for mode in ("naive", "hybrid"):
        t0 = time.monotonic()
        try:
            param = QueryParam(mode=mode, top_k=5, only_need_context=False)
            answer = await rag.aquery(comparison_query, param=param)
            elapsed = time.monotonic() - t0
            logger.info("[%s] (%.1fs) %s", mode.upper(), elapsed, str(answer)[:300])
        except Exception as exc:
            logger.error("[%s] FAILED: %s", mode.upper(), exc)

    # --- SUMMARY ---
    logger.info("")
    logger.info("=" * 60)
    logger.info("SUMMARY")
    logger.info("=" * 60)
    ok_count = sum(1 for r in results if r["status"] == "ok")
    logger.info("Queries: %d/%d successful", ok_count, len(results))
    logger.info("Working dir: %s", WORKING_DIR)
    if graph_file.exists():
        import networkx as nx
        G = nx.read_graphml(str(graph_file))
        logger.info("Final graph: %d entities, %d relations", G.number_of_nodes(), G.number_of_edges())


async def main():
    if not check_dependencies():
        logger.info("")
        logger.info("ACTIVATION CHECKLIST:")
        logger.info("1. pip install lightrag-hku nano-vectordb networkx")
        logger.info("2. Set LIGHTRAG_ENABLED=true in mascarade .env")
        logger.info("3. Add 'lightrag-hku' to pyproject.toml [project.optional-dependencies]")
        logger.info("4. Rebuild Docker image and redeploy")
        logger.info("5. Re-run this script")
        sys.exit(1)

    if not await check_ollama():
        logger.error("Ollama check failed. Ensure Ollama is running with %s and %s", LLM_MODEL, EMBED_MODEL)
        sys.exit(1)

    await run_test()


if __name__ == "__main__":
    asyncio.run(main())
