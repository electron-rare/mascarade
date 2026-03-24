#!/usr/bin/env python3
"""Ingest markdown documents into Qdrant for RAG.

Usage:
    python scripts/ingest-docs.py [--collection mascarade-rag] [--dry-run]

Ingests docs from:
  - docs/           (mascarade architecture, SOTA, specs)
  - ../Kill_LIFE/docs/  (plans, tasks, specs)
  - Site docs (if available)

Requires: MISTRAL_API_KEY or OPENAI_API_KEY in .env for embeddings.
Qdrant must be running (default: http://localhost:6333).
"""

from __future__ import annotations

import argparse
import hashlib
import logging
import os
import sys
import asyncio
from pathlib import Path

import httpx

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("ingest")

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
COLLECTION = "mascarade-rag"
CHUNK_SIZE = 512  # tokens (approx 4 chars/token)
CHUNK_OVERLAP = 64
EMBED_MODEL = "mistral-embed"  # 1024 dims
EMBED_DIM = 1024
BATCH_SIZE = 10


# ---------------------------------------------------------------------------
# Chunking
# ---------------------------------------------------------------------------

def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """Split text into chunks of approximately chunk_size tokens."""
    # Approximate: 1 token ~ 4 chars
    char_size = chunk_size * 4
    char_overlap = overlap * 4
    chunks = []
    start = 0
    while start < len(text):
        end = start + char_size
        chunk = text[start:end]
        if chunk.strip():
            chunks.append(chunk.strip())
        start = end - char_overlap
    return chunks


def doc_id(path: str, chunk_idx: int) -> str:
    """Deterministic ID for a document chunk."""
    h = hashlib.sha256(f"{path}:{chunk_idx}".encode()).hexdigest()[:16]
    return h


# ---------------------------------------------------------------------------
# Embeddings (Mistral or OpenAI)
# ---------------------------------------------------------------------------

async def embed_texts(texts: list[str], client: httpx.AsyncClient) -> list[list[float]]:
    """Generate embeddings via Ollama (bge-m3), Mistral, or OpenAI."""
    ollama_url = os.getenv("OLLAMA_URL", "http://localhost:11434")
    mistral_key = os.getenv("MISTRAL_API_KEY", "")
    openai_key = os.getenv("OPENAI_API_KEY", "")

    # Prefer Ollama local embeddings (bge-m3, no API key needed)
    try:
        vectors = []
        for text in texts:
            resp = await client.post(
                f"{ollama_url}/api/embed",
                json={"model": "bge-m3", "input": text},
                timeout=30.0,
            )
            resp.raise_for_status()
            data = resp.json()
            vectors.append(data["embeddings"][0])
        return vectors
    except Exception as exc:
        logger.debug("Ollama embed failed: %s, trying API providers", exc)

    if mistral_key:
        resp = await client.post(
            "https://api.mistral.ai/v1/embeddings",
            headers={"Authorization": f"Bearer {mistral_key}"},
            json={"model": EMBED_MODEL, "input": texts},
            timeout=30.0,
        )
        resp.raise_for_status()
        data = resp.json()
        return [item["embedding"] for item in data["data"]]

    if openai_key:
        resp = await client.post(
            "https://api.openai.com/v1/embeddings",
            headers={"Authorization": f"Bearer {openai_key}"},
            json={"model": "text-embedding-3-small", "input": texts},
            timeout=30.0,
        )
        resp.raise_for_status()
        data = resp.json()
        return [item["embedding"] for item in data["data"]]

    raise RuntimeError("No embedding provider available (Ollama/Mistral/OpenAI)")


# ---------------------------------------------------------------------------
# Qdrant operations
# ---------------------------------------------------------------------------

async def ensure_collection(client: httpx.AsyncClient) -> None:
    """Create the Qdrant collection if it doesn't exist."""
    resp = await client.get(f"{QDRANT_URL}/collections/{COLLECTION}")
    if resp.status_code == 200:
        logger.info("Collection %s already exists", COLLECTION)
        return

    logger.info("Creating collection %s (dim=%d)", COLLECTION, EMBED_DIM)
    resp = await client.put(
        f"{QDRANT_URL}/collections/{COLLECTION}",
        json={
            "vectors": {
                "size": EMBED_DIM,
                "distance": "Cosine",
            }
        },
    )
    resp.raise_for_status()
    logger.info("Collection created")


async def upsert_points(
    client: httpx.AsyncClient,
    points: list[dict],
) -> None:
    """Upsert points into Qdrant."""
    resp = await client.put(
        f"{QDRANT_URL}/collections/{COLLECTION}/points",
        json={"points": points},
        params={"wait": "true"},
        timeout=60.0,
    )
    resp.raise_for_status()


# ---------------------------------------------------------------------------
# Document discovery
# ---------------------------------------------------------------------------

def discover_docs(base_dirs: list[Path]) -> list[Path]:
    """Find all markdown files to ingest."""
    docs = []
    for base in base_dirs:
        if not base.exists():
            logger.warning("Skipping %s (not found)", base)
            continue
        for f in sorted(base.rglob("*.md")):
            if f.stat().st_size > 0 and f.stat().st_size < 500_000:
                docs.append(f)
    return docs


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

async def ingest(args: argparse.Namespace) -> None:
    """Main ingestion pipeline."""
    core_dir = Path(__file__).resolve().parent.parent / "core"
    base_dirs = [
        core_dir.parent / "docs",
        Path("/home/clems/Kill_LIFE/docs"),
    ]
    # Add site docs if available
    site_docs = Path("/Volumes/home/electron/electron-rare.github.io/docs")
    if site_docs.exists():
        base_dirs.append(site_docs)

    docs = discover_docs(base_dirs)
    logger.info("Found %d documents to ingest", len(docs))

    if args.dry_run:
        total_chunks = 0
        for doc in docs:
            text = doc.read_text(errors="replace")
            chunks = chunk_text(text)
            total_chunks += len(chunks)
            logger.info("  %s → %d chunks", doc.name, len(chunks))
        logger.info("DRY RUN: %d docs → %d chunks (no upload)", len(docs), total_chunks)
        return

    async with httpx.AsyncClient() as client:
        await ensure_collection(client)

        total_points = 0
        for i, doc in enumerate(docs):
            text = doc.read_text(errors="replace")
            chunks = chunk_text(text)
            if not chunks:
                continue

            # Process in batches
            for batch_start in range(0, len(chunks), BATCH_SIZE):
                batch = chunks[batch_start:batch_start + BATCH_SIZE]
                try:
                    vectors = await embed_texts(batch, client)
                except Exception as exc:
                    logger.error("Embedding failed for %s batch %d: %s", doc.name, batch_start, exc)
                    continue

                points = []
                for j, (chunk, vector) in enumerate(zip(batch, vectors)):
                    idx = batch_start + j
                    points.append({
                        "id": doc_id(str(doc), idx),
                        "vector": vector,
                        "payload": {
                            "text": chunk,
                            "source": str(doc),
                            "filename": doc.name,
                            "chunk_index": idx,
                            "total_chunks": len(chunks),
                        },
                    })

                try:
                    await upsert_points(client, points)
                    total_points += len(points)
                except Exception as exc:
                    logger.error("Upsert failed for %s: %s", doc.name, exc)

            if (i + 1) % 20 == 0:
                logger.info("Progress: %d/%d docs, %d points", i + 1, len(docs), total_points)

        logger.info("Done: %d docs → %d points in collection %s", len(docs), total_points, COLLECTION)


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest docs into Qdrant")
    parser.add_argument("--collection", default=COLLECTION)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    asyncio.run(ingest(args))


if __name__ == "__main__":
    main()
