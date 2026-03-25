"""Pytest configuration for Mascarade core tests."""

from __future__ import annotations

import sys
import types
from contextlib import asynccontextmanager
from pathlib import Path
from unittest.mock import patch

import httpx
import pytest

# Add project root to Python path so that deploy module can be imported
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))


if "asyncpg" not in sys.modules:
    asyncpg_stub = types.ModuleType("asyncpg")
    asyncpg_stub.Pool = object
    asyncpg_stub.Record = dict

    async def _create_pool(*args, **kwargs):
        raise RuntimeError("asyncpg is not installed in the test environment")

    asyncpg_stub.create_pool = _create_pool
    sys.modules["asyncpg"] = asyncpg_stub


@pytest.fixture
def bypass_auth():
    """Bypass auth middleware for tests that don't test auth itself.

    Usage:
        async def test_something(bypass_auth):
            async with authed_client() as client:
                resp = await client.get("/v1/agents")
    """
    with patch("mascarade.auth.is_valid_api_key", return_value=True), \
         patch("mascarade.auth._resolve_role", return_value="admin"):
        yield


@asynccontextmanager
async def authed_client():
    """ASGI test client with auth bypassed for Mascarade app."""
    from mascarade.server import app

    with patch("mascarade.auth.is_valid_api_key", return_value=True), \
         patch("mascarade.auth._resolve_role", return_value="admin"):
        async with app.router.lifespan_context(app):
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(
                transport=transport,
                base_url="http://testserver",
                headers={"Authorization": "Bearer test-key"},
            ) as client:
                yield client
