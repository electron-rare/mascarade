"""Tests for mascarade.agentic_rag — QueryRouter, RelevanceEvaluator,
MultiSourceSynthesizer, AgenticRAGPipeline."""

from __future__ import annotations

import time
from unittest.mock import AsyncMock, patch

import pytest

from mascarade.agentic_rag import (
    AgenticRAGPipeline,
    Chunk,
    MultiSourceSynthesizer,
    QueryRouter,
    RelevanceEvaluator,
    SourceType,
)

# ---------------------------------------------------------------------------
# Chunk dataclass
# ---------------------------------------------------------------------------


class TestChunk:
    def test_freshness_recent(self):
        c = Chunk(content="x", source=SourceType.QDRANT, metadata={"timestamp": time.time() - 3600})
        assert c.freshness == 1.0

    def test_freshness_week_old(self):
        c = Chunk(
            content="x", source=SourceType.QDRANT, metadata={"timestamp": time.time() - 3 * 86400}
        )
        assert c.freshness == 0.9

    def test_freshness_month_old(self):
        c = Chunk(
            content="x", source=SourceType.QDRANT, metadata={"timestamp": time.time() - 15 * 86400}
        )
        assert c.freshness == 0.7

    def test_freshness_old(self):
        c = Chunk(
            content="x", source=SourceType.QDRANT, metadata={"timestamp": time.time() - 100 * 86400}
        )
        assert c.freshness == 0.5

    def test_freshness_very_old(self):
        c = Chunk(
            content="x", source=SourceType.QDRANT, metadata={"timestamp": time.time() - 365 * 86400}
        )
        assert c.freshness == 0.3

    def test_freshness_no_timestamp(self):
        c = Chunk(content="x", source=SourceType.QDRANT, metadata={})
        assert c.freshness == 0.5

    def test_authority_spec(self):
        c = Chunk(content="x", source=SourceType.QDRANT, metadata={"source_type": "spec"})
        assert c.authority == 1.0

    def test_authority_unknown(self):
        c = Chunk(content="x", source=SourceType.QDRANT, metadata={"source_type": "random"})
        assert c.authority == 0.5

    def test_combined_score(self):
        c = Chunk(
            content="x",
            source=SourceType.QDRANT,
            score=0.9,
            metadata={"timestamp": time.time(), "source_type": "spec"},
        )
        expected = 0.9 * 0.5 + 1.0 * 0.25 + 1.0 * 0.25
        assert abs(c.combined_score - expected) < 0.01


# ---------------------------------------------------------------------------
# QueryRouter
# ---------------------------------------------------------------------------


class TestQueryRouter:
    def test_plain_query_routes_to_qdrant(self):
        r = QueryRouter()
        d = r.route("What is the capital of France?")
        assert SourceType.QDRANT in d.sources
        assert SourceType.MCP not in d.sources

    def test_kicad_keyword_routes_to_mcp(self):
        r = QueryRouter()
        d = r.route("show the PCB layout for board v3")
        assert SourceType.MCP in d.sources
        assert "kicad" in d.mcp_servers

    def test_memory_keyword_routes_to_memory(self):
        r = QueryRouter()
        d = r.route("remember what I said last time about the project")
        assert SourceType.MEMORY in d.sources

    def test_web_keyword_routes_to_web(self):
        r = QueryRouter()
        d = r.route("latest news about qdrant today")
        assert SourceType.WEB in d.sources

    def test_long_query_produces_variant(self):
        r = QueryRouter()
        d = r.route("a very long query with many words in it")
        assert len(d.query_variants) == 2

    def test_short_query_single_variant(self):
        r = QueryRouter()
        d = r.route("short query")
        assert len(d.query_variants) == 1

    def test_multiple_mcp_servers(self):
        r = QueryRouter()
        d = r.route("build workflow deploy kicad schematic")
        assert "kicad" in d.mcp_servers
        assert "github" in d.mcp_servers

    def test_no_duplicate_sources(self):
        r = QueryRouter()
        d = r.route("kicad pcb footprint symbol")
        # MCP should appear only once even though multiple keywords match
        assert d.sources.count(SourceType.MCP) == 1


# ---------------------------------------------------------------------------
# RelevanceEvaluator
# ---------------------------------------------------------------------------


class TestRelevanceEvaluator:
    def _make_chunk(
        self, score: float, ts: float | None = None, src_type: str = "generic"
    ) -> Chunk:
        meta = {"source_type": src_type}
        if ts is not None:
            meta["timestamp"] = ts
        return Chunk(content="text", source=SourceType.QDRANT, score=score, metadata=meta)

    def test_filters_below_threshold(self):
        ev = RelevanceEvaluator(threshold=0.5)
        chunks = [self._make_chunk(0.9), self._make_chunk(0.1)]
        result = ev.evaluate(chunks)
        assert all(c.combined_score >= 0.5 for c in result) or len(result) == 1

    def test_keeps_best_if_none_above_threshold(self):
        ev = RelevanceEvaluator(threshold=0.99)
        chunks = [self._make_chunk(0.3), self._make_chunk(0.2)]
        result = ev.evaluate(chunks)
        assert len(result) >= 1

    def test_quality_sufficient_true(self):
        ev = RelevanceEvaluator(threshold=0.4)
        chunks = [
            self._make_chunk(0.9, time.time(), "spec"),
            self._make_chunk(0.8, time.time(), "spec"),
        ]
        assert ev.quality_sufficient(chunks)

    def test_quality_sufficient_false_empty(self):
        ev = RelevanceEvaluator()
        assert not ev.quality_sufficient([])

    def test_quality_sufficient_false_single(self):
        ev = RelevanceEvaluator(threshold=0.4)
        chunks = [self._make_chunk(0.9, time.time(), "spec")]
        # Needs >= 2 chunks
        assert not ev.quality_sufficient(chunks)

    def test_sorted_by_combined_score(self):
        ev = RelevanceEvaluator(threshold=0.0)
        c1 = self._make_chunk(0.5)
        c2 = self._make_chunk(0.9)
        result = ev.evaluate([c1, c2])
        assert result[0].score >= result[-1].score


# ---------------------------------------------------------------------------
# MultiSourceSynthesizer
# ---------------------------------------------------------------------------


class TestMultiSourceSynthesizer:
    def test_empty_chunks_returns_empty(self):
        s = MultiSourceSynthesizer()
        assert s.synthesize([], "query") == ""

    def test_synthesis_contains_query(self):
        s = MultiSourceSynthesizer()
        chunks = [Chunk(content="answer", source=SourceType.QDRANT, source_id="col", score=0.8)]
        result = s.synthesize(chunks, "my question")
        assert "my question" in result

    def test_multiple_sources_appear(self):
        s = MultiSourceSynthesizer()
        chunks = [
            Chunk(content="from qdrant", source=SourceType.QDRANT, source_id="col", score=0.8),
            Chunk(content="from mcp", source=SourceType.MCP, source_id="kicad", score=0.7),
        ]
        result = s.synthesize(chunks, "query")
        assert "qdrant" in result
        assert "mcp" in result

    def test_content_truncated_at_2000(self):
        s = MultiSourceSynthesizer()
        long_content = "x" * 5000
        chunks = [Chunk(content=long_content, source=SourceType.QDRANT, score=0.8)]
        result = s.synthesize(chunks, "q")
        # The actual content in the output should be at most 2000 chars
        assert "x" * 2001 not in result


# ---------------------------------------------------------------------------
# AgenticRAGPipeline (async, mocked retrieval)
# ---------------------------------------------------------------------------


class TestAgenticRAGPipeline:
    @pytest.mark.asyncio
    async def test_full_retrieve_with_good_quality(self):
        """When quality is sufficient on first round, no re-route."""
        good_chunks = [
            Chunk(
                content="result1",
                source=SourceType.QDRANT,
                score=0.9,
                metadata={"timestamp": time.time(), "source_type": "spec"},
            ),
            Chunk(
                content="result2",
                source=SourceType.QDRANT,
                score=0.85,
                metadata={"timestamp": time.time(), "source_type": "docs"},
            ),
        ]
        with patch(
            "mascarade.agentic_rag.retrieve_qdrant",
            new_callable=AsyncMock,
            return_value=good_chunks,
        ):
            pipeline = AgenticRAGPipeline()
            result = await pipeline.retrieve("test query")
        assert "test query" in result
        assert "result1" in result

    @pytest.mark.asyncio
    async def test_no_results_returns_empty_or_minimal(self):
        with patch(
            "mascarade.agentic_rag.retrieve_qdrant", new_callable=AsyncMock, return_value=[]
        ):
            pipeline = AgenticRAGPipeline()
            result = await pipeline.retrieve("unknown topic")
        # With no chunks, synthesizer returns ""
        assert result == ""

    @pytest.mark.asyncio
    async def test_reroute_adds_web_and_memory(self):
        """When quality is insufficient, pipeline should add WEB and MEMORY sources."""
        weak_chunk = Chunk(content="weak", source=SourceType.QDRANT, score=0.3, metadata={})
        call_count = 0
        web_call_count = 0

        async def mock_qdrant(query, **kw):
            nonlocal call_count
            call_count += 1
            return [weak_chunk]

        async def mock_memory(query):
            return [
                Chunk(
                    content="from memory",
                    source=SourceType.MEMORY,
                    score=0.6,
                    metadata={"timestamp": time.time(), "source_type": "docs"},
                )
            ]

        async def mock_web(query):
            nonlocal web_call_count
            web_call_count += 1
            return [
                Chunk(
                    content="from web",
                    source=SourceType.WEB,
                    score=0.62,
                    metadata={"source_type": "web", "url": "https://example.test"},
                )
            ]

        with (
            patch("mascarade.agentic_rag.retrieve_qdrant", side_effect=mock_qdrant),
            patch("mascarade.agentic_rag.retrieve_memory", side_effect=mock_memory),
            patch("mascarade.agentic_rag.retrieve_web", side_effect=mock_web),
        ):
            pipeline = AgenticRAGPipeline()
            result = await pipeline.retrieve("obscure topic with extra words for variant")
        # Should have called qdrant multiple rounds
        assert call_count >= 2
        assert web_call_count >= 1
        assert "from web" in result

    @pytest.mark.asyncio
    async def test_all_sources_fail(self):
        """When all retrieval raises exceptions, pipeline should still return."""

        async def failing_qdrant(query, **kw):
            raise RuntimeError("qdrant down")

        with patch("mascarade.agentic_rag.retrieve_qdrant", side_effect=failing_qdrant):
            pipeline = AgenticRAGPipeline()
            result = await pipeline.retrieve("anything")
        # Exceptions are caught by gather, result should be empty
        assert result == ""

    @pytest.mark.asyncio
    async def test_mcp_route_included(self):
        """A PCB query should trigger MCP retrieval."""
        good_chunks = [
            Chunk(
                content="pcb info",
                source=SourceType.QDRANT,
                score=0.9,
                metadata={"timestamp": time.time(), "source_type": "spec"},
            ),
            Chunk(
                content="mcp hint",
                source=SourceType.MCP,
                source_id="kicad",
                score=0.7,
                metadata={"source_type": "mcp_hint"},
            ),
        ]
        with (
            patch(
                "mascarade.agentic_rag.retrieve_qdrant",
                new_callable=AsyncMock,
                return_value=good_chunks[:1],
            ),
            patch(
                "mascarade.agentic_rag.retrieve_mcp",
                new_callable=AsyncMock,
                return_value=good_chunks[1:],
            ),
        ):
            pipeline = AgenticRAGPipeline()
            result = await pipeline.retrieve("show pcb layout")
        assert "pcb" in result.lower() or "mcp" in result.lower()

    @pytest.mark.asyncio
    async def test_web_only_route_uses_web_results(self):
        with patch(
            "mascarade.agentic_rag.retrieve_web",
            new_callable=AsyncMock,
            return_value=[
                Chunk(
                    content="fresh web result",
                    source=SourceType.WEB,
                    score=0.8,
                    metadata={"source_type": "web", "url": "https://example.test"},
                )
            ],
        ):
            pipeline = AgenticRAGPipeline()
            result = await pipeline.retrieve("latest news about qdrant today")
        assert "fresh web result" in result
