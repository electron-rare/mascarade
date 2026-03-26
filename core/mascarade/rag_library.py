"""RAG Document Library — ingest + search documents via Qdrant."""

from __future__ import annotations

import logging
import os
import time
import uuid
from typing import Any

import httpx

logger = logging.getLogger("mascarade.rag_library")
QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
COLLECTION = "mascarade-library"
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
EMBED_MODEL = os.getenv("RAG_EMBED_MODEL", "nomic-embed-text")
CHUNK_SIZE = 500
CHUNK_OVERLAP = 50


async def _embed(text: str) -> list[float]:
    try:
        async with httpx.AsyncClient(timeout=15.0) as c:
            r = await c.post(f"{OLLAMA_URL}/api/embed", json={"model": EMBED_MODEL, "input": text})
            r.raise_for_status()
            embs = r.json().get("embeddings", [])
            return embs[0] if embs else [0.0] * 384
    except Exception:
        return [0.0] * 384


def _chunk_text(text: str) -> list[str]:
    words = text.split()
    chunks = []
    for i in range(0, len(words), CHUNK_SIZE - CHUNK_OVERLAP):
        chunk = " ".join(words[i : i + CHUNK_SIZE])
        if chunk.strip():
            chunks.append(chunk)
    return chunks


async def _ensure_collection():
    try:
        async with httpx.AsyncClient(timeout=5.0) as c:
            r = await c.get(f"{QDRANT_URL}/collections/{COLLECTION}")
            if r.status_code == 404:
                await c.put(
                    f"{QDRANT_URL}/collections/{COLLECTION}",
                    json={"vectors": {"size": 384, "distance": "Cosine"}},
                )
    except Exception as e:
        logger.warning("Collection check failed: %s", e)


async def ingest(text: str, metadata: dict | None = None) -> dict:
    await _ensure_collection()
    chunks = _chunk_text(text)
    meta = metadata or {}
    points = []
    for i, chunk in enumerate(chunks):
        vec = await _embed(chunk)
        points.append(
            {
                "id": str(uuid.uuid4()),
                "vector": vec,
                "payload": {"text": chunk, "chunk_index": i, "timestamp": time.time(), **meta},
            }
        )
    if points:
        async with httpx.AsyncClient(timeout=30.0) as c:
            await c.put(f"{QDRANT_URL}/collections/{COLLECTION}/points", json={"points": points})
    return {"chunks": len(points), "collection": COLLECTION}


async def search(query: str, top_k: int = 5) -> list[dict]:
    vec = await _embed(query)
    try:
        async with httpx.AsyncClient(timeout=10.0) as c:
            r = await c.post(
                f"{QDRANT_URL}/collections/{COLLECTION}/points/search",
                json={
                    "vector": vec,
                    "limit": top_k,
                    "with_payload": True,
                },
            )
            r.raise_for_status()
            return [
                {
                    "score": p["score"],
                    "text": p["payload"].get("text", ""),
                    "metadata": p["payload"],
                }
                for p in r.json().get("result", [])
            ]
    except Exception:
        return []


async def status() -> dict:
    try:
        async with httpx.AsyncClient(timeout=5.0) as c:
            r = await c.get(f"{QDRANT_URL}/collections/{COLLECTION}")
            if r.status_code == 200:
                info = r.json().get("result", {})
                return {
                    "collection": COLLECTION,
                    "points": info.get("points_count", 0),
                    "status": "ok",
                }
    except Exception:
        pass
    return {"collection": COLLECTION, "points": 0, "status": "unavailable"}


def mount_rag_library(app: Any) -> None:
    from fastapi import Body

    @app.post("/v1/library/ingest")
    async def library_ingest(text: str = Body(..., embed=True), source: str = Body("", embed=True)):
        result = await ingest(text, {"source": source})
        return result

    @app.post("/v1/library/search")
    async def library_search(query: str = Body(..., embed=True), top_k: int = Body(5, embed=True)):
        return await search(query, top_k)

    @app.get("/v1/library/status")
    async def library_status():
        return await status()

    logger.info("RAG Library mounted (/v1/library/ingest, /v1/library/search, /v1/library/status)")
