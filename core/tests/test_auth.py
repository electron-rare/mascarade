"""Tests pour l'authentification Bearer token."""

from contextlib import asynccontextmanager

import httpx
import pytest

from mascarade.auth import (
    add_api_key,
    get_active_api_keys,
    is_valid_api_key,
    remove_api_key,
)
from mascarade.server import app


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
    add_api_key("test-key-001")

    async with _client() as client:
        missing = await client.get("/v1/api-keys")
        invalid = await client.get(
            "/v1/api-keys",
            headers={"Authorization": "Bearer wrong-key-999"},
        )
        valid = await client.get(
            "/v1/api-keys",
            headers={"Authorization": "Bearer test-key-001"},
        )

    assert missing.status_code == 401
    assert missing.json()["detail"] == "Missing token"
    assert invalid.status_code == 401
    assert invalid.json()["detail"] == "Invalid token"
    assert valid.status_code == 200
    assert valid.json()["api_keys"][0]["active"] is True


def test_multi_key_support():
    """Test du support pour plusieurs clés API."""
    # Add multiple keys (must be >= 8 characters)
    add_api_key("test-key-001")
    add_api_key("test-key-002")

    # Verify both keys are active
    active_keys = get_active_api_keys()
    assert "test-key-001" in active_keys
    assert "test-key-002" in active_keys

    # Test validation
    assert is_valid_api_key("test-key-001")
    assert is_valid_api_key("test-key-002")
    assert not is_valid_api_key("test-key-003")

    # Remove one key
    remove_api_key("test-key-001")
    active_keys = get_active_api_keys()
    assert "test-key-001" not in active_keys
    assert "test-key-002" in active_keys
    assert not is_valid_api_key("test-key-001")
    assert is_valid_api_key("test-key-002")


def test_api_key_validation():
    """Test de la validation des clés API."""
    add_api_key("test-secret-12345")

    assert is_valid_api_key("test-secret-12345")
    assert not is_valid_api_key("wrong-key")
    assert not is_valid_api_key("")
    assert not is_valid_api_key("short")  # Too short (5 chars)
    assert not is_valid_api_key("7chars")  # Exactly 7 chars (still too short)
    assert not is_valid_api_key("valid-key-123")  # This key doesn't exist


def test_api_key_management_functions():
    """Test des fonctions de gestion des clés API."""
    # Test initial state
    assert len(get_active_api_keys()) == 0
    assert not is_valid_api_key("any-key")

    # Add keys (must be >= 8 characters)
    add_api_key("test-key-alpha")
    add_api_key("test-key-bravo")
    add_api_key("test-key-charlie")

    assert len(get_active_api_keys()) == 3
    assert is_valid_api_key("test-key-alpha")
    assert is_valid_api_key("test-key-bravo")
    assert is_valid_api_key("test-key-charlie")

    # Remove middle key
    remove_api_key("test-key-bravo")
    assert len(get_active_api_keys()) == 2
    assert is_valid_api_key("test-key-alpha")
    assert not is_valid_api_key("test-key-bravo")
    assert is_valid_api_key("test-key-charlie")

    # Remove all keys
    remove_api_key("test-key-alpha")
    remove_api_key("test-key-charlie")
    assert len(get_active_api_keys()) == 0
