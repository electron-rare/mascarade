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
        missing = await client.get("/api-keys")
        invalid = await client.get(
            "/api-keys",
            headers={"Authorization": "Bearer wrong-key-999999"},
        )
        valid = await client.get(
            "/api-keys",
            headers={"Authorization": f"Bearer {TEST_ADMIN_KEY}"},
        )

    assert missing.status_code == 401
    assert missing.json()["detail"] == "Missing token"
    assert invalid.status_code == 401
    assert invalid.json()["detail"] == "Invalid token"
    assert valid.status_code == 200
    assert valid.json()["api_keys"][0]["active"] is True


def test_multi_key_support():
    """Test du support pour plusieurs clés API."""
    add_api_key(TEST_OPERATOR_KEY)
    add_api_key(TEST_VIEWER_KEY)

    # Verify both keys are active
    active_keys = get_active_api_keys()
    assert TEST_OPERATOR_KEY in active_keys
    assert TEST_VIEWER_KEY in active_keys

    # Test validation
    assert is_valid_api_key(TEST_OPERATOR_KEY)
    assert is_valid_api_key(TEST_VIEWER_KEY)
    assert not is_valid_api_key("test-key-003333")

    # Remove one key
    remove_api_key(TEST_OPERATOR_KEY)
    active_keys = get_active_api_keys()
    assert TEST_OPERATOR_KEY not in active_keys
    assert TEST_VIEWER_KEY in active_keys
    assert not is_valid_api_key(TEST_OPERATOR_KEY)
    assert is_valid_api_key(TEST_VIEWER_KEY)


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

    add_api_key("test-key-alpha-0001")
    add_api_key("test-key-bravo-0001")
    add_api_key("test-key-charlie-01")

    assert len(get_active_api_keys()) == 3
    assert is_valid_api_key("test-key-alpha-0001")
    assert is_valid_api_key("test-key-bravo-0001")
    assert is_valid_api_key("test-key-charlie-01")

    # Remove middle key
    remove_api_key("test-key-bravo-0001")
    assert len(get_active_api_keys()) == 2
    assert is_valid_api_key("test-key-alpha-0001")
    assert not is_valid_api_key("test-key-bravo-0001")
    assert is_valid_api_key("test-key-charlie-01")

    # Remove all keys
    remove_api_key("test-key-alpha-0001")
    remove_api_key("test-key-charlie-01")
    assert len(get_active_api_keys()) == 0
