"""Tests for memory operations endpoints."""

from __future__ import annotations

from contextlib import asynccontextmanager
from unittest.mock import patch

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
async def test_memory_add_returns_201():
    """Test POST /api/memory/add returns 201 status code."""

    async def mock_mem0_request(*args, **kwargs):
        return {"id": "mem-12345", "status": "created"}

    with patch('mascarade.routers.memory._mem0_request', side_effect=mock_mem0_request):
        async with _client() as client:
            response = await client.post(
                "/api/memory/add",
                json={
                    "messages": [{"role": "user", "content": "test message"}],
                    "user_id": "test-user",
                    "project_id": "project-alpha",
                }
            )

    assert response.status_code == 201
    body = response.json()
    assert "memory_id" in body
    assert "status" in body
    assert "user_id" in body
    assert body["user_id"] == "test-user"
    assert body["project_id"] == "project-alpha"
    assert body["status"] == "created"


@pytest.mark.asyncio
async def test_memory_add_with_agent_id():
    """Test POST /api/memory/add with agent_id scoping."""

    calls = []

    async def mock_mem0_request(*args, **kwargs):
        calls.append((args, kwargs))
        return {"id": "mem-67890", "status": "created"}

    with patch('mascarade.routers.memory._mem0_request', side_effect=mock_mem0_request):
        async with _client() as client:
            response = await client.post(
                "/api/memory/add",
                json={
                    "messages": [{"role": "user", "content": "test message"}],
                    "user_id": "test-user",
                    "project_id": "project-alpha",
                    "agent_id": "test-agent"
                }
            )

    assert response.status_code == 201
    body = response.json()
    assert body["agent_id"] == "test-agent"
    payload = calls[0][1]["json_data"]
    assert payload["user_id"] == "project-alpha:test-user"
    assert payload["metadata"]["project_id"] == "project-alpha"
    assert payload["metadata"]["agent_id"] == "test-agent"


@pytest.mark.asyncio
async def test_memory_search():
    """Test POST /api/memory/search."""

    async def mock_mem0_request(*args, **kwargs):
        return {
            "results": [
                {"id": "mem-1", "content": "relevant memory 1", "score": 0.95},
                {"id": "mem-2", "content": "relevant memory 2", "score": 0.85}
            ]
        }

    with patch('mascarade.routers.memory._mem0_request', side_effect=mock_mem0_request):
        async with _client() as client:
            response = await client.post(
                "/api/memory/search",
                json={
                    "query": "test query",
                    "user_id": "test-user",
                    "project_id": "project-alpha",
                    "limit": 10
                }
            )

    assert response.status_code == 200
    body = response.json()
    assert "memories" in body
    assert "count" in body
    assert body["count"] == 2
    assert len(body["memories"]) == 2
    assert body["project_id"] == "project-alpha"


@pytest.mark.asyncio
async def test_memory_get_all():
    """Test POST /api/memory/get to retrieve all memories."""

    async def mock_mem0_request(*args, **kwargs):
        return {
            "results": [
                {"id": "mem-1", "content": "memory 1"},
                {"id": "mem-2", "content": "memory 2"},
                {"id": "mem-3", "content": "memory 3"}
            ]
        }

    with patch('mascarade.routers.memory._mem0_request', side_effect=mock_mem0_request):
        async with _client() as client:
            response = await client.post(
                "/api/memory/get",
                json={
                    "user_id": "test-user",
                    "project_id": "project-alpha",
                }
            )

    assert response.status_code == 200
    body = response.json()
    assert "memories" in body
    assert "count" in body
    assert body["count"] == 3
    assert body["project_id"] == "project-alpha"


@pytest.mark.asyncio
async def test_memory_delete():
    """Test DELETE /api/memory/delete."""

    async def mock_mem0_request(*args, **kwargs):
        return {"status": "deleted"}

    with patch('mascarade.routers.memory._mem0_request', side_effect=mock_mem0_request):
        async with _client() as client:
            # Use POST method with DELETE endpoint (since httpx DELETE doesn't support json body)
            response = await client.request(
                "DELETE",
                "/api/memory/delete",
                json={
                    "memory_id": "mem-12345",
                    "user_id": "test-user",
                    "project_id": "project-alpha",
                }
            )

    assert response.status_code == 200
    body = response.json()
    assert "message" in body
    assert "memory_id" in body
    assert body["memory_id"] == "mem-12345"
    assert body["project_id"] == "project-alpha"


@pytest.mark.asyncio
async def test_memory_add_validation_error():
    """Test POST /api/memory/add with invalid data."""
    async with _client() as client:
        # Missing required field 'user_id'
        response = await client.post(
            "/api/memory/add",
            json={
                "messages": [{"role": "user", "content": "test"}],
                "project_id": "project-alpha",
            }
        )

    assert response.status_code == 422  # Validation error


@pytest.mark.asyncio
async def test_memory_add_empty_messages():
    """Test POST /api/memory/add with empty messages."""
    async with _client() as client:
        response = await client.post(
            "/api/memory/add",
            json={
                "messages": [],
                "user_id": "test-user",
                "project_id": "project-alpha",
            }
        )

    assert response.status_code == 422  # Validation error


@pytest.mark.asyncio
async def test_memory_service_unavailable():
    """Test handling when Mem0 service is unavailable."""

    async def mock_mem0_request(*args, **kwargs):
        from fastapi import HTTPException, status
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Memory service unavailable"
        )

    with patch('mascarade.routers.memory._mem0_request', side_effect=mock_mem0_request):
        async with _client() as client:
            response = await client.post(
                "/api/memory/add",
                json={
                    "messages": [{"role": "user", "content": "test"}],
                    "user_id": "test-user",
                    "project_id": "project-alpha",
                }
            )

    assert response.status_code == 503  # Service unavailable
