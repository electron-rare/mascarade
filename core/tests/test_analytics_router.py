"""Tests for mascarade.routers.analytics — Benchmark leaderboard endpoint."""

from __future__ import annotations

from contextlib import asynccontextmanager
from unittest.mock import MagicMock, patch

import httpx
import pytest

from fastapi import FastAPI

from mascarade.routers.analytics import router as analytics_router


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_app():
    """Build a minimal FastAPI app with the analytics router."""
    test_app = FastAPI()
    test_app.include_router(analytics_router)
    return test_app


@asynccontextmanager
async def _client():
    test_app = _build_app()
    transport = httpx.ASGITransport(app=test_app)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://testserver",
    ) as client:
        yield client


def _fake_leaderboard(domain=None, limit=10, order_by="quality_score"):
    """Return dummy leaderboard rows."""
    return [
        {
            "provider": "openai",
            "model": "gpt-4",
            "domain": domain or "general",
            "quality_score": 0.95,
            "latency_p50": 250.0,
            "latency_p95": 500.0,
            "cost": 0.03,
            "error_rate": 0.01,
        },
    ]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestGetBenchmarks:
    @pytest.mark.asyncio
    async def test_defaults(self):
        with patch("mascarade.routers.analytics.BenchmarkStorage") as MockStorage:
            instance = MagicMock()
            instance.query_leaderboard = MagicMock(return_value=_fake_leaderboard())
            MockStorage.return_value = instance

            async with _client() as client:
                resp = await client.get("/v1/analytics/benchmarks")

        assert resp.status_code == 200
        body = resp.json()
        assert "results" in body
        assert body["count"] == 1
        assert body["filters"]["order_by"] == "quality_score"
        assert body["filters"]["limit"] == 10
        assert body["filters"]["domain"] is None

    @pytest.mark.asyncio
    async def test_with_domain_filter(self):
        with patch("mascarade.routers.analytics.BenchmarkStorage") as MockStorage:
            instance = MagicMock()
            instance.query_leaderboard = MagicMock(return_value=_fake_leaderboard(domain="code"))
            MockStorage.return_value = instance

            async with _client() as client:
                resp = await client.get("/v1/analytics/benchmarks?domain=code")

        assert resp.status_code == 200
        body = resp.json()
        assert body["filters"]["domain"] == "code"
        instance.query_leaderboard.assert_called_once_with(
            domain="code", limit=10, order_by="quality_score",
        )

    @pytest.mark.asyncio
    async def test_invalid_order_by_returns_400(self):
        async with _client() as client:
            resp = await client.get("/v1/analytics/benchmarks?order_by=invalid_field")

        assert resp.status_code == 400
        assert "Invalid order_by" in resp.json()["detail"]

    @pytest.mark.asyncio
    async def test_limit_clamped_to_bounds(self):
        """FastAPI query validation enforces ge=1, le=100."""
        async with _client() as client:
            resp = await client.get("/v1/analytics/benchmarks?limit=0")

        # FastAPI returns 422 for out-of-bounds query params
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_limit_upper_bound(self):
        async with _client() as client:
            resp = await client.get("/v1/analytics/benchmarks?limit=101")

        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_custom_limit_and_order(self):
        with patch("mascarade.routers.analytics.BenchmarkStorage") as MockStorage:
            instance = MagicMock()
            instance.query_leaderboard = MagicMock(return_value=[])
            MockStorage.return_value = instance

            async with _client() as client:
                resp = await client.get("/v1/analytics/benchmarks?limit=50&order_by=latency_p50")

        assert resp.status_code == 200
        body = resp.json()
        assert body["filters"]["limit"] == 50
        assert body["filters"]["order_by"] == "latency_p50"
        assert body["count"] == 0

    @pytest.mark.asyncio
    async def test_empty_results(self):
        with patch("mascarade.routers.analytics.BenchmarkStorage") as MockStorage:
            instance = MagicMock()
            instance.query_leaderboard = MagicMock(return_value=[])
            MockStorage.return_value = instance

            async with _client() as client:
                resp = await client.get("/v1/analytics/benchmarks?domain=nonexistent")

        assert resp.status_code == 200
        body = resp.json()
        assert body["results"] == []
        assert body["count"] == 0
