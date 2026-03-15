"""Tests for backward compatibility with legacy API keys."""

import os
from contextlib import asynccontextmanager
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from mascarade.auth import (
    add_api_key,
    get_active_api_keys,
    hash_api_key,
    is_valid_api_key,
    migrate_legacy_keys,
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


@pytest.fixture(autouse=True)
def _clean_env():
    """Ensure MASCARADE_API_KEY env var is clean before/after tests."""
    original = os.environ.get("MASCARADE_API_KEY")
    yield
    if original is not None:
        os.environ["MASCARADE_API_KEY"] = original
    elif "MASCARADE_API_KEY" in os.environ:
        del os.environ["MASCARADE_API_KEY"]


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


# --- Legacy in-memory authentication tests ---


def test_legacy_api_key_in_memory():
    """Test that legacy API keys work with in-memory validation."""
    # Add a legacy key to the in-memory store
    add_api_key("test-legacy-key-12345")

    # Verify it's active
    assert is_valid_api_key("test-legacy-key-12345")
    assert "test-legacy-key-12345" in get_active_api_keys()

    # Verify invalid keys are rejected
    assert not is_valid_api_key("wrong-key")
    assert not is_valid_api_key("")

    # Remove the key
    remove_api_key("test-legacy-key-12345")
    assert not is_valid_api_key("test-legacy-key-12345")
    assert "test-legacy-key-12345" not in get_active_api_keys()


def test_legacy_api_key_minimum_length():
    """Test that legacy API keys enforce minimum length."""
    # Too short (< 8 characters)
    add_api_key("short")
    assert not is_valid_api_key("short")
    assert "short" not in get_active_api_keys()

    # Exactly 8 characters (should work)
    add_api_key("exact8ch")
    assert is_valid_api_key("exact8ch")
    assert "exact8ch" in get_active_api_keys()


@pytest.mark.asyncio
async def test_legacy_api_key_http_auth():
    """Test that legacy API keys work with HTTP Bearer authentication."""
    add_api_key("test-http-key-12345")

    async with _client() as client:
        # Request without token should fail
        no_token = await client.get("/api-keys")
        assert no_token.status_code == 401

        # Request with wrong token should fail
        wrong_token = await client.get(
            "/api-keys",
            headers={"Authorization": "Bearer wrong-token-999"},
        )
        assert wrong_token.status_code == 401

        # Request with valid legacy token should succeed
        valid_token = await client.get(
            "/api-keys",
            headers={"Authorization": "Bearer test-http-key-12345"},
        )
        assert valid_token.status_code == 200


# --- Migration tests ---


@pytest.mark.asyncio
async def test_migrate_legacy_keys_no_env_var():
    """Test migration when MASCARADE_API_KEY is not set."""
    # Clear any existing env var
    if "MASCARADE_API_KEY" in os.environ:
        del os.environ["MASCARADE_API_KEY"]

    # Mock the database pool
    with patch("mascarade.auth.get_db_pool") as mock_pool:
        mock_pool.return_value = MagicMock()

        result = await migrate_legacy_keys()

        # Should report nothing to migrate
        assert result["migrated"] == 0
        assert result["skipped"] == 0
        assert result["failed"] == 0
        assert result["details"] == []


@pytest.mark.asyncio
async def test_migrate_legacy_keys_empty_string():
    """Test migration when MASCARADE_API_KEY is empty string."""
    os.environ["MASCARADE_API_KEY"] = ""

    with patch("mascarade.auth.get_db_pool") as mock_pool:
        mock_pool.return_value = MagicMock()

        result = await migrate_legacy_keys()

        assert result["migrated"] == 0
        assert result["skipped"] == 0
        assert result["failed"] == 0


@pytest.mark.asyncio
async def test_migrate_legacy_keys_invalid_keys():
    """Test migration skips keys that are too short."""
    os.environ["MASCARADE_API_KEY"] = "short,toolong12345"

    # Mock database pool
    mock_pool = MagicMock()
    mock_conn = AsyncMock()
    mock_pool.acquire.return_value.__aenter__.return_value = mock_conn

    # Mock admin role query
    mock_conn.fetchrow = AsyncMock(
        return_value={"id": 1}  # admin role id
    )

    with patch("mascarade.auth.get_db_pool", return_value=mock_pool):
        with patch("mascarade.config.settings") as mock_settings:
            mock_settings.mascarade_api_key = "short,toolong12345"

            result = await migrate_legacy_keys()

            # Only "toolong12345" should be processed (>= 8 chars)
            # "short" should be filtered out before processing
            assert result["migrated"] + result["skipped"] >= 1


@pytest.mark.asyncio
async def test_migrate_legacy_keys_success():
    """Test successful migration of legacy API keys."""
    os.environ["MASCARADE_API_KEY"] = "legacy-key-12345"

    # Mock database pool and connection
    mock_pool = MagicMock()
    mock_conn = AsyncMock()
    mock_pool.acquire.return_value.__aenter__.return_value = mock_conn

    # Mock transaction
    mock_transaction = AsyncMock()
    mock_conn.transaction.return_value.__aenter__.return_value = mock_transaction
    mock_conn.transaction.return_value.__aexit__.return_value = None

    # Mock database queries
    async def mock_fetchrow(query, *args):
        if "SELECT id FROM roles WHERE name = 'admin'" in query:
            return {"id": 1}  # admin role
        elif "SELECT id FROM legacy_migrations" in query:
            return None  # not migrated yet
        elif "SELECT id, user_id FROM api_keys WHERE key_hash" in query:
            return None  # key doesn't exist yet
        elif "SELECT id FROM users WHERE username" in query:
            return None  # user doesn't exist
        elif "INSERT INTO users" in query:
            return {"id": 100}  # new user id
        return None

    mock_conn.fetchrow.side_effect = mock_fetchrow
    mock_conn.execute = AsyncMock()

    with patch("mascarade.auth.get_db_pool", return_value=mock_pool):
        with patch("mascarade.config.settings") as mock_settings:
            mock_settings.mascarade_api_key = "legacy-key-12345"

            result = await migrate_legacy_keys()

            # Should successfully migrate one key
            assert result["migrated"] == 1
            assert result["skipped"] == 0
            assert result["failed"] == 0
            assert len(result["details"]) == 1
            assert result["details"][0]["status"] == "migrated"
            assert result["details"][0]["key_prefix"] == "legacy-k"


@pytest.mark.asyncio
async def test_migrate_legacy_keys_prevents_duplicates():
    """Test that migration prevents duplicate migrations."""
    os.environ["MASCARADE_API_KEY"] = "duplicate-key-12345"

    # Mock database pool and connection
    mock_pool = MagicMock()
    mock_conn = AsyncMock()
    mock_pool.acquire.return_value.__aenter__.return_value = mock_conn

    # Mock database queries - return existing migration record
    async def mock_fetchrow(query, *args):
        if "SELECT id FROM roles WHERE name = 'admin'" in query:
            return {"id": 1}  # admin role
        elif "SELECT id FROM legacy_migrations" in query:
            return {"id": 1}  # already migrated!
        return None

    mock_conn.fetchrow.side_effect = mock_fetchrow

    with patch("mascarade.auth.get_db_pool", return_value=mock_pool):
        with patch("mascarade.config.settings") as mock_settings:
            mock_settings.mascarade_api_key = "duplicate-key-12345"

            result = await migrate_legacy_keys()

            # Should skip the already-migrated key
            assert result["migrated"] == 0
            assert result["skipped"] == 1
            assert result["failed"] == 0
            assert result["details"][0]["status"] == "skipped"
            assert result["details"][0]["reason"] == "already_migrated"


@pytest.mark.asyncio
async def test_migrate_legacy_keys_existing_in_database():
    """Test that migration skips keys that already exist in api_keys table."""
    os.environ["MASCARADE_API_KEY"] = "existing-key-12345"

    # Mock database pool and connection
    mock_pool = MagicMock()
    mock_conn = AsyncMock()
    mock_pool.acquire.return_value.__aenter__.return_value = mock_conn

    # Mock database queries
    async def mock_fetchrow(query, *args):
        if "SELECT id FROM roles WHERE name = 'admin'" in query:
            return {"id": 1}  # admin role
        elif "SELECT id FROM legacy_migrations" in query:
            return None  # not in migrations table
        elif "SELECT id, user_id FROM api_keys WHERE key_hash" in query:
            return {"id": 1, "user_id": 100}  # key exists!
        return None

    mock_conn.fetchrow.side_effect = mock_fetchrow

    with patch("mascarade.auth.get_db_pool", return_value=mock_pool):
        with patch("mascarade.config.settings") as mock_settings:
            mock_settings.mascarade_api_key = "existing-key-12345"

            result = await migrate_legacy_keys()

            # Should skip the existing key
            assert result["migrated"] == 0
            assert result["skipped"] == 1
            assert result["failed"] == 0
            assert result["details"][0]["status"] == "skipped"
            assert result["details"][0]["reason"] == "key_exists"


@pytest.mark.asyncio
async def test_migrate_legacy_keys_multiple():
    """Test migration of multiple legacy API keys."""
    os.environ["MASCARADE_API_KEY"] = "key-one-12345,key-two-67890"

    # Mock database pool and connection
    mock_pool = MagicMock()
    mock_conn = AsyncMock()
    mock_pool.acquire.return_value.__aenter__.return_value = mock_conn

    # Mock transaction
    mock_transaction = AsyncMock()
    mock_conn.transaction.return_value.__aenter__.return_value = mock_transaction
    mock_conn.transaction.return_value.__aexit__.return_value = None

    # Track user IDs
    user_counter = [100]

    # Mock database queries
    async def mock_fetchrow(query, *args):
        if "SELECT id FROM roles WHERE name = 'admin'" in query:
            return {"id": 1}  # admin role
        elif "SELECT id FROM legacy_migrations" in query:
            return None  # not migrated yet
        elif "SELECT id, user_id FROM api_keys WHERE key_hash" in query:
            return None  # key doesn't exist yet
        elif "SELECT id FROM users WHERE username" in query:
            return None  # user doesn't exist
        elif "INSERT INTO users" in query:
            user_id = user_counter[0]
            user_counter[0] += 1
            return {"id": user_id}  # new user id
        return None

    mock_conn.fetchrow.side_effect = mock_fetchrow
    mock_conn.execute = AsyncMock()

    with patch("mascarade.auth.get_db_pool", return_value=mock_pool):
        with patch("mascarade.config.settings") as mock_settings:
            mock_settings.mascarade_api_key = "key-one-12345,key-two-67890"

            result = await migrate_legacy_keys()

            # Should migrate both keys
            assert result["migrated"] == 2
            assert result["skipped"] == 0
            assert result["failed"] == 0
            assert len(result["details"]) == 2


@pytest.mark.asyncio
async def test_migrate_legacy_keys_db_not_initialized():
    """Test migration fails gracefully when database is not initialized."""
    os.environ["MASCARADE_API_KEY"] = "test-key-12345"

    with patch("mascarade.auth.get_db_pool", return_value=None):
        with pytest.raises(RuntimeError, match="Database pool not initialized"):
            await migrate_legacy_keys()


@pytest.mark.asyncio
async def test_migrate_legacy_keys_no_admin_role():
    """Test migration fails when admin role is missing from database."""
    os.environ["MASCARADE_API_KEY"] = "test-key-12345"

    # Mock database pool and connection
    mock_pool = MagicMock()
    mock_conn = AsyncMock()
    mock_pool.acquire.return_value.__aenter__.return_value = mock_conn

    # Mock admin role query to return None (role not found)
    mock_conn.fetchrow = AsyncMock(return_value=None)

    with patch("mascarade.auth.get_db_pool", return_value=mock_pool):
        with patch("mascarade.config.settings") as mock_settings:
            mock_settings.mascarade_api_key = "test-key-12345"

            with pytest.raises(RuntimeError, match="Admin role not found"):
                await migrate_legacy_keys()


# --- Hash function tests ---


def test_hash_api_key_consistency():
    """Test that hash_api_key produces consistent hashes."""
    key = "test-key-12345"
    hash1 = hash_api_key(key)
    hash2 = hash_api_key(key)

    assert hash1 == hash2
    assert len(hash1) == 64  # SHA-256 produces 64 hex characters


def test_hash_api_key_different_for_different_keys():
    """Test that different keys produce different hashes."""
    key1 = "test-key-12345"
    key2 = "test-key-67890"

    hash1 = hash_api_key(key1)
    hash2 = hash_api_key(key2)

    assert hash1 != hash2


# --- Integration tests ---


@pytest.mark.asyncio
async def test_backward_compatibility_workflow():
    """Test the complete backward compatibility workflow.

    This test simulates:
    1. Having a legacy API key in environment
    2. Migrating it to the database
    3. Verifying it still works for authentication
    """
    # Step 1: Set up legacy key
    legacy_key = "workflow-test-12345"
    add_api_key(legacy_key)

    # Verify legacy in-memory auth works
    assert is_valid_api_key(legacy_key)

    # Step 2: Mock database migration
    mock_pool = MagicMock()
    mock_conn = AsyncMock()
    mock_pool.acquire.return_value.__aenter__.return_value = mock_conn

    # Mock transaction
    mock_transaction = AsyncMock()
    mock_conn.transaction.return_value.__aenter__.return_value = mock_transaction
    mock_conn.transaction.return_value.__aexit__.return_value = None

    # Mock database queries
    async def mock_fetchrow(query, *args):
        if "SELECT id FROM roles WHERE name = 'admin'" in query:
            return {"id": 1}
        elif "SELECT id FROM legacy_migrations" in query:
            return None
        elif "SELECT id, user_id FROM api_keys WHERE key_hash" in query:
            return None
        elif "SELECT id FROM users WHERE username" in query:
            return None
        elif "INSERT INTO users" in query:
            return {"id": 100}
        return None

    mock_conn.fetchrow.side_effect = mock_fetchrow
    mock_conn.execute = AsyncMock()

    with patch("mascarade.auth.get_db_pool", return_value=mock_pool):
        with patch("mascarade.config.settings") as mock_settings:
            mock_settings.mascarade_api_key = legacy_key

            result = await migrate_legacy_keys()

            # Step 3: Verify migration succeeded
            assert result["migrated"] == 1
            assert result["details"][0]["status"] == "migrated"
            assert result["details"][0]["username"].startswith("legacy_admin_")

            # Step 4: Verify in-memory auth still works
            assert is_valid_api_key(legacy_key)
