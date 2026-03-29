"""Agentic RAG pipeline for Mascarade.

Implements a retrieve - evaluate - re-route - synthesize loop:
  1. QueryRouter     - decides which sources to consult
  2. RelevanceEval   - scores & filters retrieved chunks
  3. MultiSynthesizer - merges results from multiple sources
  4. AgenticRAGPipeline - orchestrates the full loop
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import httpx

from mascarade.mcp.searxng import SearXNGMcpClient
from mascarade.rag.vectorstore import QdrantVectorStore

logger = logging.getLogger("mascarade.agentic_rag")

QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
QDRANT_COLLECTION = os.getenv("QDRANT_COLLECTION", "mascarade-rag")
EMBEDDING_DIM = 384
TOP_K = 8
RELEVANCE_THRESHOLD = 0.55
MAX_REROUTE_ROUNDS = 2

# Compute backends — KXKM (RTX 4090) for embeddings + inference
KXKM_OLLAMA_URL = os.getenv("KXKM_OLLAMA_URL", "http://kxkm-ai:11434")
LOCAL_OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
EMBED_MODEL = os.getenv("RAG_EMBED_MODEL", "nomic-embed-text")
SYNTH_MODEL = os.getenv("RAG_SYNTH_MODEL", "devstral")


class SourceType(str, Enum):
    QDRANT = "qdrant"
    MCP = "mcp"
    MEMORY = "memory"
    WEB = "web"


@dataclass
class Chunk:
    content: str
    source: SourceType
    source_id: str = ""
    score: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def freshness(self) -> float:
        ts = self.metadata.get("timestamp", 0)
        if not ts:
            return 0.5
        age_days = (time.time() - ts) / 86400
        if age_days < 1:
            return 1.0
        if age_days < 7:
            return 0.9
        if age_days < 30:
            return 0.7
        if age_days < 180:
            return 0.5
        return 0.3

    @property
    def authority(self) -> float:
        src = self.metadata.get("source_type", "")
        weights = {
            "spec": 1.0,
            "datasheet": 0.95,
            "docs": 0.85,
            "code": 0.8,
            "web": 0.6,
            "mcp_hint": 0.35,
            "forum": 0.6,
            "generic": 0.4,
        }
        return weights.get(src, 0.5)

    @property
    def combined_score(self) -> float:
        return self.score * 0.5 + self.freshness * 0.25 + self.authority * 0.25


async def _embed(text: str) -> list[float]:
    """Get embeddings — try KXKM (fast GPU) first, fallback to local."""
    for url in [KXKM_OLLAMA_URL, LOCAL_OLLAMA_URL]:
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                r = await client.post(
                    f"{url}/api/embed", json={"model": EMBED_MODEL, "input": text}
                )
                r.raise_for_status()
                embeddings = r.json().get("embeddings", [])
                if embeddings:
                    return embeddings[0]
        except Exception as exc:
            logger.debug("Embedding via %s failed: %s", url, exc)
    logger.warning("All embedding backends failed")
    return [0.0] * EMBEDDING_DIM


async def _synthesize_with_llm(context: str, query: str) -> str:
    """Use KXKM devstral to synthesize a final answer from retrieved context."""
    prompt = f"""Based on the following retrieved context, provide a concise and accurate answer to the query.

Query: {query}

Context:
{context[:6000]}

Answer:"""
    for url in [KXKM_OLLAMA_URL, LOCAL_OLLAMA_URL]:
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                r = await client.post(
                    f"{url}/api/generate",
                    json={
                        "model": SYNTH_MODEL,
                        "prompt": prompt,
                        "stream": False,
                    },
                )
                r.raise_for_status()
                return r.json().get("response", "")
        except Exception as exc:
            logger.debug("Synthesis via %s failed: %s", url, exc)
    return context  # fallback: return raw context


_MCP_KEYWORDS = {
    "kicad": ["pcb", "schematic", "kicad", "footprint", "symbol", "layout", "gerber", "drc"],
    "freecad": ["3d", "cad", "freecad", "model", "stl", "step"],
    "openscad": ["openscad", "parametric", "scad"],
    "knowledge": ["doc", "spec", "note", "wiki", "knowledge", "outline", "memo"],
    "github": ["workflow", "ci", "action", "dispatch", "deploy", "build"],
    "huggingface": ["model", "dataset", "huggingface", "hf", "finetune"],
    "apify": ["scrape", "datasheet", "component", "forum", "monitor"],
}


@dataclass
class RouteDecision:
    sources: list[SourceType]
    mcp_servers: list[str] = field(default_factory=list)
    query_variants: list[str] = field(default_factory=list)


class QueryRouter:
    def route(self, query: str) -> RouteDecision:
        q_lower = query.lower()
        sources: list[SourceType] = [SourceType.QDRANT]
        mcp_servers: list[str] = []
        for server, keywords in _MCP_KEYWORDS.items():
            if any(kw in q_lower for kw in keywords):
                if SourceType.MCP not in sources:
                    sources.append(SourceType.MCP)
                mcp_servers.append(server)
        if any(w in q_lower for w in ["remember", "last time", "previously", "history", "project"]):
            sources.append(SourceType.MEMORY)
        if any(w in q_lower for w in ["current", "today", "latest", "news", "web", "live"]):
            sources.append(SourceType.WEB)
        variants = [query]
        if len(query.split()) > 5:
            variants.append(" ".join(query.split()[:5]))
        return RouteDecision(
            sources=list(dict.fromkeys(sources)), mcp_servers=mcp_servers, query_variants=variants
        )


class RelevanceEvaluator:
    def __init__(self, threshold: float = RELEVANCE_THRESHOLD):
        self.threshold = threshold

    def evaluate(self, chunks: list[Chunk]) -> list[Chunk]:
        scored = sorted(chunks, key=lambda c: c.combined_score, reverse=True)
        filtered = [c for c in scored if c.combined_score >= self.threshold]
        if not filtered and scored:
            filtered = scored[:1]
        return filtered

    def quality_sufficient(self, chunks: list[Chunk]) -> bool:
        if not chunks:
            return False
        avg = sum(c.combined_score for c in chunks) / len(chunks)
        return avg >= self.threshold and len(chunks) >= 2


class MultiSourceSynthesizer:
    def synthesize(self, chunks: list[Chunk], query: str) -> str:
        if not chunks:
            return ""
        by_source: dict[str, list[Chunk]] = {}
        for c in chunks:
            key = f"{c.source.value}/{c.source_id}" if c.source_id else c.source.value
            by_source.setdefault(key, []).append(c)
        parts = [f"# Retrieved context for: {query}\n"]
        for source_key, source_chunks in by_source.items():
            parts.append(f"\n## Source: {source_key}")
            for i, chunk in enumerate(source_chunks[:5], 1):
                parts.append(f"\n### [{i}] (relevance: {chunk.combined_score:.2f})")
                parts.append(chunk.content[:2000])
        return "\n".join(parts)


async def retrieve_qdrant(
    query: str, collection: str = QDRANT_COLLECTION, top_k: int = TOP_K
) -> list[Chunk]:
    vector = await _embed(query)
    if all(v == 0.0 for v in vector):
        return []
    vectorstore = QdrantVectorStore(base_url=QDRANT_URL, collection=collection, timeout=10.0)
    try:
        results = await vectorstore.hybrid_search(vector, query, top_k=top_k)
        chunks = []
        for point in results:
            metadata = point.get("metadata", {})
            chunks.append(
                Chunk(
                    content=point.get("text", ""),
                    source=SourceType.QDRANT,
                    source_id=collection,
                    score=point.get("score", 0.0),
                    metadata={
                        "timestamp": metadata.get("timestamp", 0),
                        "source_type": metadata.get("source_type", "generic"),
                        "file": metadata.get("file", ""),
                        "retrieval": "hybrid_search",
                    },
                )
            )
        return chunks
    except Exception as exc:
        logger.warning("Qdrant search failed: %s", exc)
        return []
    finally:
        await vectorstore.close()


async def retrieve_memory(query: str) -> list[Chunk]:
    return await retrieve_qdrant(query, collection="openmemory", top_k=3)


async def retrieve_web(query: str, top_k: int = 5) -> list[Chunk]:
    client = SearXNGMcpClient()
    if not client.is_configured:
        return []

    try:
        results = await client.search(query, limit=top_k)
    except Exception as exc:
        logger.debug("Web search failed: %s", exc)
        return []

    chunks: list[Chunk] = []
    for index, result in enumerate(results):
        content_parts = [part for part in [result.get("title", ""), result.get("content", "")] if part]
        if not content_parts:
            continue
        chunks.append(
            Chunk(
                content="\n\n".join(content_parts),
                source=SourceType.WEB,
                source_id=result.get("engine", "searxng") or "searxng",
                score=max(0.4, 0.8 - index * 0.08),
                metadata={
                    "source_type": "web",
                    "url": result.get("url", ""),
                    "title": result.get("title", ""),
                    "engine": result.get("engine", ""),
                },
            )
        )
    return chunks


async def retrieve_mcp(query: str, servers: list[str]) -> list[Chunk]:
    return [
        Chunk(
            content=f"[MCP hint] Query relevant to '{s}' MCP server. Use {s} tools for domain-specific results.",
            source=SourceType.MCP,
            source_id=s,
            score=0.7,
            metadata={"source_type": "mcp_hint"},
        )
        for s in servers
    ]


class AgenticRAGPipeline:
    def __init__(
        self,
        router: QueryRouter | None = None,
        evaluator: RelevanceEvaluator | None = None,
        synthesizer: MultiSourceSynthesizer | None = None,
    ):
        self.router = router or QueryRouter()
        self.evaluator = evaluator or RelevanceEvaluator()
        self.synthesizer = synthesizer or MultiSourceSynthesizer()

    async def retrieve(self, query: str) -> str:
        decision = self.router.route(query)
        all_chunks: list[Chunk] = []
        for round_num in range(MAX_REROUTE_ROUNDS + 1):
            tasks = []
            for variant in decision.query_variants:
                if SourceType.QDRANT in decision.sources:
                    tasks.append(retrieve_qdrant(variant))
                if SourceType.MEMORY in decision.sources:
                    tasks.append(retrieve_memory(variant))
                if SourceType.WEB in decision.sources:
                    tasks.append(retrieve_web(variant))
                if SourceType.MCP in decision.sources and decision.mcp_servers:
                    tasks.append(retrieve_mcp(variant, decision.mcp_servers))
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for result in results:
                if isinstance(result, list):
                    all_chunks.extend(result)
            all_chunks = self.evaluator.evaluate(all_chunks)
            if self.evaluator.quality_sufficient(all_chunks) or round_num >= MAX_REROUTE_ROUNDS:
                break
            logger.info(
                "RAG round %d: quality insufficient (%d chunks), re-routing",
                round_num,
                len(all_chunks),
            )
            if SourceType.WEB not in decision.sources:
                decision.sources.append(SourceType.WEB)
            if SourceType.MEMORY not in decision.sources:
                decision.sources.append(SourceType.MEMORY)
            if len(decision.query_variants) == 1:
                words = query.split()
                if len(words) > 3:
                    decision.query_variants.append(" ".join(words[:3]))
        return self.synthesizer.synthesize(all_chunks, query)


def mount_agentic_rag(app: Any) -> None:
    from fastapi import Body

    pipeline = AgenticRAGPipeline()

    @app.post("/v1/rag/retrieve")
    async def rag_retrieve(query: str = Body(..., embed=True)):
        context = await pipeline.retrieve(query)
        return {"query": query, "context": context}

    @app.post("/v1/rag/route")
    async def rag_route(query: str = Body(..., embed=True)):
        decision = pipeline.router.route(query)
        return {
            "query": query,
            "sources": [s.value for s in decision.sources],
            "mcp_servers": decision.mcp_servers,
            "query_variants": decision.query_variants,
        }

    @app.post("/v1/rag/ask")
    async def rag_ask(query: str = Body(..., embed=True)):
        """Full RAG: retrieve context then synthesize answer via KXKM."""
        context = await pipeline.retrieve(query)
        if not context:
            return {"query": query, "answer": "", "context": ""}
        answer = await _synthesize_with_llm(context, query)
        return {"query": query, "answer": answer, "context": context}

    logger.info(
        "Agentic RAG mounted (/v1/rag/retrieve, /v1/rag/route, /v1/rag/ask) — KXKM compute: %s",
        KXKM_OLLAMA_URL,
    )
