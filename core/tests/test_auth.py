"""Tests pour l'authentification Bearer token."""

from contextlib import asynccontextmanager

import httpx
import pytest

from mascarade.auth import (
    add_api_key,
    get_active_api_keys,
    remove_api_key,
)
from mascarade.server import app

TEST_ADMIN_KEY = "test-admin-key-0001"
TEST_OPERATOR_KEY = "test-operator-key-01"
TEST_VIEWER_KEY = "test-viewer-key-0001"


@pytest.fixture(autouse=True)
def _clean_api_keys():
    """Ensure each test starts and ends with a clean key store."""
    for key in get_active_api_keys():
        remove_api_key(key)
    yield
    for key in get_active_api_keys():
        remove_api_key(key)


@asynccontextmanager
async def _client():
    """Provide an ASGI test client without relying on Starlette's TestClient.

    In the current toolchain, `TestClient` hangs inside AnyIO's blocking portal
    before dispatching requests. `httpx.ASGITransport` exercises the same app
    without that sync bridge.
    """
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            yield client


@pytest.mark.asyncio
async def test_health_open_without_auth():
    """Le endpoint /health est accessible sans token, même avec auth activée."""
    async with _client() as client:
        response = await client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_protected_routes_require_valid_bearer_token():
    """Les routes protégées refusent les tokens absents ou invalides."""
    add_api_key(TEST_ADMIN_KEY)

    async with _client() as client:
        await client.get("/v1/api-keys")
        await client.get(
            "/v1/api-keys",
            headers={"Authorization": "Bearer wrong-key-999"},
        )
