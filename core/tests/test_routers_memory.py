"""Tests for memory router endpoints."""

from __future__ import annotations

from contextlib import asynccontextmanager

import httpx
import pytest

from mascarade.server import app


@asynccontextmanager
async def _client():
    """Create test client."""
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            yield client


@pytest.mark.asyncio
async def test_memory_status_basic():
    """Test basic memory status endpoint."""
    async with _client() as client:
        response = await client.get("/v1/memory/status")

    assert response.status_code == 200
    body = response.json()
    assert "status" in body
    assert "service" in body
    assert "description" in body
    assert body["status"] == "ok"
    assert body["service"] == "mem0"


@pytest.mark.asyncio
async def test_memory_status_structure():
    """Test memory status response structure."""
    async with _client() as client:
        response = await client.get("/v1/memory/status")

    assert response.status_code == 200
    body = response.json()

    # Verify required fields
    assert isinstance(body["status"], str)
    assert isinstance(body["service"], str)
    assert isinstance(body["description"], str)

    # Verify description mentions Mem0
    assert "mem0" in body["description"].lower()


@pytest.mark.asyncio
async def test_memory_status_no_auth_required():
    """Test that memory status endpoint doesn't require authentication."""
    # Memory status is currently open (no auth dependency)
    async with _client() as client:
        response = await client.get("/v1/memory/status")

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_memory_status_multiple_calls():
    """Test multiple calls to memory status endpoint."""
    async with _client() as client:
        # Make multiple calls
        responses = []
        for _ in range(3):
            response = await client.get("/v1/memory/status")
            responses.append(response)

    # All should succeed
    for response in responses:
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "ok"
