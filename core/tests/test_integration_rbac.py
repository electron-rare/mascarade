"""Integration tests for RBAC multi-user authentication system.

This test suite verifies the complete end-to-end RBAC workflow:
- Admin user creation and authentication
- Full admin access to all endpoints
- User management operations (CRUD)
- API key management
- Rate limiting configuration
"""

from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from mascarade.auth import hash_api_key
from mascarade.db.models import User
from mascarade.server import app


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


def _mock_db_pool():
    """Create a mock database pool with common query responses."""
    mock_pool = MagicMock()
    mock_conn = AsyncMock()
    mock_pool.acquire.return_value.__aenter__.return_value = mock_conn
    return mock_pool, mock_conn


# --- Admin User Creation Tests ---


@pytest.mark.asyncio
async def test_create_admin_user():
    """Test creating an admin user via API."""
    mock_pool, mock_conn = _mock_db_pool()

    # Mock database queries
    async def mock_fetchrow(query, *args):
        if "SELECT id FROM roles WHERE name = 'admin'" in query:
            return {"id": 1}  # admin role exists
        elif "SELECT id FROM users WHERE username" in query:
            return None  # username not taken
        elif "SELECT id FROM users WHERE email" in query:
            return None  # email not taken
        elif "SELECT id FROM roles WHERE id" in query:
            return {"id": 1}  # role exists
        elif "INSERT INTO users" in query:
            return {
                "id": 1,
                "username": "admin_user",
                "email": "admin@example.com",
                "role_id": 1,
                "is_active": True,
                "rate_limits": None,
                "created_at": datetime.now(),
                "updated_at": datetime.now(),
            }
        return None

    mock_conn.fetchrow.side_effect = mock_fetchrow

    # Create a mock admin user for authentication
    admin_user = User(
        id=1,
        username="test_admin",
        email="test_admin@example.com",
        role_id=1,
        is_active=True,
        rate_limits=None,
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )

    with patch("mascarade.auth.get_db_pool", return_value=mock_pool):
        with patch("mascarade.auth.authenticate_user", return_value=admin_user):
            async with _client() as client:
                response = await client.post(
                    "/users",
                    json={
                        "username": "admin_user",
                        "email": "admin@example.com",
                        "role_id": 1,
                        "is_active": True,
                    },
                    headers={"Authorization": "Bearer test-admin-key"},
                )

                assert response.status_code == 200
                data = response.json()
                assert data["username"] == "admin_user"
                assert data["email"] == "admin@example.com"
                assert data["role_id"] == 1
                assert data["is_active"] is True


@pytest.mark.asyncio
async def test_create_admin_api_key():
    """Test creating an API key for an admin user."""
    mock_pool, mock_conn = _mock_db_pool()

    # Mock database queries
    async def mock_fetchrow(query, *args):
        if "SELECT id FROM users WHERE id" in query:
            return {"id": 1}  # user exists
        elif "INSERT INTO api_keys" in query:
            return {
                "id": 1,
                "user_id": 1,
                "key_hash": hash_api_key("test-key"),
                "key_prefix": "test-key"[:8],
                "name": "Admin API Key",
                "is_active": True,
                "created_at": datetime.now(),
                "expires_at": None,
                "last_used_at": None,
            }
        return None

    mock_conn.fetchrow.side_effect = mock_fetchrow

    # Create a mock admin user for authentication
    admin_user = User(
        id=1,
        username="test_admin",
        email="test_admin@example.com",
        role_id=1,
        is_active=True,
        rate_limits=None,
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )

    with patch("mascarade.auth.get_db_pool", return_value=mock_pool):
        with patch("mascarade.auth.authenticate_user", return_value=admin_user):
            async with _client() as client:
                response = await client.post(
                    "/users/1/api-keys",
                    json={
                        "name": "Admin API Key",
                        "expires_at": None,
                    },
                    headers={"Authorization": "Bearer test-admin-key"},
                )

                assert response.status_code == 201
                data = response.json()
                assert "api_key" in data
                assert "key" in data
                assert data["api_key"]["name"] == "Admin API Key"
                assert data["api_key"]["user_id"] == 1
                assert data["api_key"]["is_active"] is True


# --- Admin Access Verification Tests ---


@pytest.mark.asyncio
async def test_admin_can_list_users():
    """Test that admin can list all users."""
    mock_pool, mock_conn = _mock_db_pool()

    # Mock database queries
    async def mock_fetch(query, *args):
        if "SELECT id, username, email, role_id, is_active" in query:
            return [
                {
                    "id": 1,
                    "username": "admin_user",
                    "email": "admin@example.com",
                    "role_id": 1,
                    "is_active": True,
                    "rate_limits": None,
                    "created_at": datetime.now(),
                    "updated_at": datetime.now(),
                },
                {
                    "id": 2,
                    "username": "regular_user",
                    "email": "user@example.com",
                    "role_id": 2,
                    "is_active": True,
                    "rate_limits": None,
                    "created_at": datetime.now(),
                    "updated_at": datetime.now(),
                },
            ]
        return []

    mock_conn.fetch.side_effect = mock_fetch

    # Create a mock admin user for authentication
    admin_user = User(
        id=1,
        username="test_admin",
        email="test_admin@example.com",
        role_id=1,
        is_active=True,
        rate_limits=None,
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )

    with patch("mascarade.auth.get_db_pool", return_value=mock_pool):
        with patch("mascarade.auth.authenticate_user", return_value=admin_user):
            async with _client() as client:
                response = await client.get(
                    "/users",
                    headers={"Authorization": "Bearer test-admin-key"},
                )

                assert response.status_code == 200
                data = response.json()
                assert "users" in data
                assert len(data["users"]) == 2
                assert data["users"][0]["username"] == "admin_user"
                assert data["users"][1]["username"] == "regular_user"


@pytest.mark.asyncio
async def test_admin_can_get_user_by_id():
    """Test that admin can get a specific user by ID."""
    mock_pool, mock_conn = _mock_db_pool()

    # Mock database queries
    async def mock_fetchrow(query, *args):
        if "SELECT id, username, email, role_id, is_active" in query:
            return {
                "id": 1,
                "username": "admin_user",
                "email": "admin@example.com",
                "role_id": 1,
                "is_active": True,
                "rate_limits": None,
                "created_at": datetime.now(),
                "updated_at": datetime.now(),
            }
        return None

    mock_conn.fetchrow.side_effect = mock_fetchrow

    # Create a mock admin user for authentication
    admin_user = User(
        id=1,
        username="test_admin",
        email="test_admin@example.com",
        role_id=1,
        is_active=True,
        rate_limits=None,
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )

    with patch("mascarade.auth.get_db_pool", return_value=mock_pool):
        with patch("mascarade.auth.authenticate_user", return_value=admin_user):
            async with _client() as client:
                response = await client.get(
                    "/users/1",
                    headers={"Authorization": "Bearer test-admin-key"},
                )

                assert response.status_code == 200
                data = response.json()
                assert data["id"] == 1
                assert data["username"] == "admin_user"
                assert data["email"] == "admin@example.com"


@pytest.mark.asyncio
async def test_admin_can_update_user():
    """Test that admin can update a user."""
    mock_pool, mock_conn = _mock_db_pool()

    # Mock database queries
    async def mock_fetchrow(query, *args):
        if "SELECT id FROM users WHERE id" in query:
            return {"id": 2}  # user exists
        elif "SELECT id FROM users WHERE username" in query and "AND id !=" in query:
            return None  # username not taken by another user
        elif "SELECT id FROM roles WHERE id" in query:
            return {"id": 2}  # role exists
        elif "UPDATE users" in query:
            return {
                "id": 2,
                "username": "updated_user",
                "email": "user@example.com",
                "role_id": 2,
                "is_active": True,
                "rate_limits": None,
                "created_at": datetime.now(),
                "updated_at": datetime.now(),
            }
        return None

    mock_conn.fetchrow.side_effect = mock_fetchrow

    # Create a mock admin user for authentication
    admin_user = User(
        id=1,
        username="test_admin",
        email="test_admin@example.com",
        role_id=1,
        is_active=True,
        rate_limits=None,
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )

    with patch("mascarade.auth.get_db_pool", return_value=mock_pool):
        with patch("mascarade.auth.authenticate_user", return_value=admin_user):
            async with _client() as client:
                response = await client.put(
                    "/users/2",
                    json={"username": "updated_user"},
                    headers={"Authorization": "Bearer test-admin-key"},
                )

                assert response.status_code == 200
                data = response.json()
                assert data["id"] == 2
                assert data["username"] == "updated_user"


@pytest.mark.asyncio
async def test_admin_can_delete_user():
    """Test that admin can delete a user."""
    mock_pool, mock_conn = _mock_db_pool()

    # Mock database queries
    async def mock_fetchrow(query, *args):
        if "SELECT id FROM users WHERE id" in query:
            return {"id": 2}  # user exists
        return None

    mock_conn.fetchrow.side_effect = mock_fetchrow
    mock_conn.execute = AsyncMock()

    # Create a mock admin user for authentication
    admin_user = User(
        id=1,
        username="test_admin",
        email="test_admin@example.com",
        role_id=1,
        is_active=True,
        rate_limits=None,
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )

    with patch("mascarade.auth.get_db_pool", return_value=mock_pool):
        with patch("mascarade.auth.authenticate_user", return_value=admin_user):
            async with _client() as client:
                response = await client.delete(
                    "/users/2",
                    headers={"Authorization": "Bearer test-admin-key"},
                )

                assert response.status_code == 200
                data = response.json()
                assert data["status"] == "ok"
                assert "deleted successfully" in data["message"]


@pytest.mark.asyncio
async def test_admin_can_list_api_keys():
    """Test that admin can list API keys for a user."""
    mock_pool, mock_conn = _mock_db_pool()

    # Mock database queries
    async def mock_fetchrow(query, *args):
        if "SELECT id FROM users WHERE id" in query:
            return {"id": 1}  # user exists
        return None

    async def mock_fetch(query, *args):
        if "SELECT id, user_id, key_hash, key_prefix, name, is_active" in query:
            return [
                {
                    "id": 1,
                    "user_id": 1,
                    "key_hash": hash_api_key("key1"),
                    "key_prefix": "key1-pre",
                    "name": "Key 1",
                    "is_active": True,
                    "created_at": datetime.now(),
                    "expires_at": None,
                    "last_used_at": None,
                },
                {
                    "id": 2,
                    "user_id": 1,
                    "key_hash": hash_api_key("key2"),
                    "key_prefix": "key2-pre",
                    "name": "Key 2",
                    "is_active": True,
                    "created_at": datetime.now(),
                    "expires_at": None,
                    "last_used_at": None,
                },
            ]
        return []

    mock_conn.fetchrow.side_effect = mock_fetchrow
    mock_conn.fetch.side_effect = mock_fetch

    # Create a mock admin user for authentication
    admin_user = User(
        id=1,
        username="test_admin",
        email="test_admin@example.com",
        role_id=1,
        is_active=True,
        rate_limits=None,
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )

    with patch("mascarade.auth.get_db_pool", return_value=mock_pool):
        with patch("mascarade.auth.authenticate_user", return_value=admin_user):
            async with _client() as client:
                response = await client.get(
                    "/users/1/api-keys",
                    headers={"Authorization": "Bearer test-admin-key"},
                )

                assert response.status_code == 200
                data = response.json()
                assert "api_keys" in data
                assert len(data["api_keys"]) == 2
                assert data["api_keys"][0]["name"] == "Key 1"
                assert data["api_keys"][1]["name"] == "Key 2"


@pytest.mark.asyncio
async def test_admin_can_revoke_api_key():
    """Test that admin can revoke (delete) an API key."""
    mock_pool, mock_conn = _mock_db_pool()

    # Mock database queries
    async def mock_fetchrow(query, *args):
        if "SELECT id, user_id, name FROM api_keys" in query:
            return {
                "id": 1,
                "user_id": 1,
                "name": "Test Key",
            }
        return None

    mock_conn.fetchrow.side_effect = mock_fetchrow
    mock_conn.execute = AsyncMock()

    # Create a mock admin user for authentication
    admin_user = User(
        id=1,
        username="test_admin",
        email="test_admin@example.com",
        role_id=1,
        is_active=True,
        rate_limits=None,
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )

    with patch("mascarade.auth.get_db_pool", return_value=mock_pool):
        with patch("mascarade.auth.authenticate_user", return_value=admin_user):
            async with _client() as client:
                response = await client.delete(
                    "/users/1/api-keys/1",
                    headers={"Authorization": "Bearer test-admin-key"},
                )

                assert response.status_code == 200
                data = response.json()
                assert data["status"] == "ok"
                assert "revoked successfully" in data["message"]


@pytest.mark.asyncio
async def test_admin_can_update_rate_limits():
    """Test that admin can update rate limits for a user."""
    mock_pool, mock_conn = _mock_db_pool()

    # Mock database queries
    async def mock_fetchrow(query, *args):
        if "SELECT id, username FROM users WHERE id" in query:
            return {"id": 2, "username": "test_user"}
        return None

    mock_conn.fetchrow.side_effect = mock_fetchrow
    mock_conn.execute = AsyncMock()

    # Create a mock admin user for authentication
    admin_user = User(
        id=1,
        username="test_admin",
        email="test_admin@example.com",
        role_id=1,
        is_active=True,
        rate_limits=None,
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )

    with patch("mascarade.auth.get_db_pool", return_value=mock_pool):
        with patch("mascarade.auth.authenticate_user", return_value=admin_user):
            async with _client() as client:
                response = await client.put(
                    "/users/2/rate-limit",
                    json={
                        "requests_per_minute": 60,
                        "requests_per_hour": 1000,
                        "requests_per_day": 10000,
                        "tokens_per_day": 1000000,
                    },
                    headers={"Authorization": "Bearer test-admin-key"},
                )

                assert response.status_code == 200
                data = response.json()
                assert data["status"] == "ok"
                assert "rate_limits" in data
                assert data["rate_limits"]["requests_per_minute"] == 60
                assert data["rate_limits"]["requests_per_hour"] == 1000


# --- Admin Creating Other Users Tests ---


@pytest.mark.asyncio
async def test_admin_can_create_regular_user():
    """Test that admin can create a regular (non-admin) user."""
    mock_pool, mock_conn = _mock_db_pool()

    # Mock database queries
    async def mock_fetchrow(query, *args):
        if "SELECT id FROM users WHERE username" in query:
            return None  # username not taken
        elif "SELECT id FROM users WHERE email" in query:
            return None  # email not taken
        elif "SELECT id FROM roles WHERE id" in query:
            return {"id": 2}  # user role exists
        elif "INSERT INTO users" in query:
            return {
                "id": 3,
                "username": "regular_user",
                "email": "regular@example.com",
                "role_id": 2,
                "is_active": True,
                "rate_limits": None,
                "created_at": datetime.now(),
                "updated_at": datetime.now(),
            }
        return None

    mock_conn.fetchrow.side_effect = mock_fetchrow

    # Create a mock admin user for authentication
    admin_user = User(
        id=1,
        username="test_admin",
        email="test_admin@example.com",
        role_id=1,
        is_active=True,
        rate_limits=None,
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )

    with patch("mascarade.auth.get_db_pool", return_value=mock_pool):
        with patch("mascarade.auth.authenticate_user", return_value=admin_user):
            async with _client() as client:
                response = await client.post(
                    "/users",
                    json={
                        "username": "regular_user",
                        "email": "regular@example.com",
                        "role_id": 2,  # regular user role
                        "is_active": True,
                    },
                    headers={"Authorization": "Bearer test-admin-key"},
                )

                assert response.status_code == 200
                data = response.json()
                assert data["username"] == "regular_user"
                assert data["role_id"] == 2


@pytest.mark.asyncio
async def test_admin_can_create_read_only_user():
    """Test that admin can create a read-only user."""
    mock_pool, mock_conn = _mock_db_pool()

    # Mock database queries
    async def mock_fetchrow(query, *args):
        if "SELECT id FROM users WHERE username" in query:
            return None  # username not taken
        elif "SELECT id FROM users WHERE email" in query:
            return None  # email not taken
        elif "SELECT id FROM roles WHERE id" in query:
            return {"id": 3}  # read-only role exists
        elif "INSERT INTO users" in query:
            return {
                "id": 4,
                "username": "readonly_user",
                "email": "readonly@example.com",
                "role_id": 3,
                "is_active": True,
                "rate_limits": None,
                "created_at": datetime.now(),
                "updated_at": datetime.now(),
            }
        return None

    mock_conn.fetchrow.side_effect = mock_fetchrow

    # Create a mock admin user for authentication
    admin_user = User(
        id=1,
        username="test_admin",
        email="test_admin@example.com",
        role_id=1,
        is_active=True,
        rate_limits=None,
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )

    with patch("mascarade.auth.get_db_pool", return_value=mock_pool):
        with patch("mascarade.auth.authenticate_user", return_value=admin_user):
            async with _client() as client:
                response = await client.post(
                    "/users",
                    json={
                        "username": "readonly_user",
                        "email": "readonly@example.com",
                        "role_id": 3,  # read-only role
                        "is_active": True,
                    },
                    headers={"Authorization": "Bearer test-admin-key"},
                )

                assert response.status_code == 200
                data = response.json()
                assert data["username"] == "readonly_user"
                assert data["role_id"] == 3


# --- Authorization Tests ---


@pytest.mark.asyncio
async def test_non_admin_cannot_create_users():
    """Test that non-admin users cannot create users."""
    mock_pool, mock_conn = _mock_db_pool()

    # Mock database queries - user has role_id 2 (not admin)
    async def mock_fetchrow(query, *args):
        if "SELECT name FROM roles WHERE id" in query:
            return {"name": "user"}  # not admin
        return None

    mock_conn.fetchrow.side_effect = mock_fetchrow

    # Create a mock regular user (not admin)
    regular_user = User(
        id=2,
        username="regular_user",
        email="user@example.com",
        role_id=2,
        is_active=True,
        rate_limits=None,
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )

    with patch("mascarade.auth.get_db_pool", return_value=mock_pool):
        with patch("mascarade.auth.authenticate_user", return_value=regular_user):
            async with _client() as client:
                response = await client.post(
                    "/users",
                    json={
                        "username": "new_user",
                        "email": "new@example.com",
                        "role_id": 2,
                        "is_active": True,
                    },
                    headers={"Authorization": "Bearer regular-user-key"},
                )

                # Should be forbidden (403)
                assert response.status_code == 403


@pytest.mark.asyncio
async def test_unauthenticated_cannot_access_admin_endpoints():
    """Test that unauthenticated requests cannot access admin endpoints."""
    async with _client() as client:
        # Try to list users without authentication
        response = await client.get("/users")

        # Should require authentication (401)
        assert response.status_code == 401


# --- Complete Workflow Test ---


@pytest.mark.asyncio
async def test_complete_admin_workflow():
    """Test complete admin workflow: create admin, create users, manage API keys.

    This test simulates:
    1. Admin user exists
    2. Admin creates a regular user
    3. Admin creates an API key for the regular user
    4. Admin lists all users
    5. Admin lists API keys for the regular user
    6. Admin updates rate limits for the regular user
    """
    mock_pool, mock_conn = _mock_db_pool()

    # Track state for sequential operations
    users_db = {
        1: {
            "id": 1,
            "username": "admin_user",
            "email": "admin@example.com",
            "role_id": 1,
            "is_active": True,
            "rate_limits": None,
            "created_at": datetime.now(),
            "updated_at": datetime.now(),
        }
    }
    api_keys_db = {}
    next_user_id = [2]
    next_key_id = [1]

    # Mock database queries
    async def mock_fetchrow(query, *args):
        # User queries
        if "SELECT id FROM users WHERE username" in query:
            # Check if username exists
            username = args[0] if args else None
            for user in users_db.values():
                if user["username"] == username:
                    return {"id": user["id"]}
            return None
        elif "SELECT id FROM users WHERE email" in query:
            # Check if email exists
            email = args[0] if args else None
            for user in users_db.values():
                if user["email"] == email:
                    return {"id": user["id"]}
            return None
        elif "SELECT id FROM roles WHERE id" in query:
            # Roles exist
            return {"id": args[0]} if args else {"id": 1}
        elif "INSERT INTO users" in query:
            # Create new user
            user_id = next_user_id[0]
            next_user_id[0] += 1
            new_user = {
                "id": user_id,
                "username": args[0],
                "email": args[1],
                "role_id": args[2],
                "is_active": args[3],
                "rate_limits": None,
                "created_at": datetime.now(),
                "updated_at": datetime.now(),
            }
            users_db[user_id] = new_user
            return new_user
        elif "SELECT id FROM users WHERE id" in query:
            # Check if user exists
            user_id = args[0] if args else None
            return {"id": user_id} if user_id in users_db else None
        elif "SELECT id, username FROM users WHERE id" in query:
            # Get user info
            user_id = args[0] if args else None
            if user_id in users_db:
                user = users_db[user_id]
                return {"id": user["id"], "username": user["username"]}
            return None
        elif "INSERT INTO api_keys" in query:
            # Create API key
            key_id = next_key_id[0]
            next_key_id[0] += 1
            new_key = {
                "id": key_id,
                "user_id": args[0],
                "key_hash": args[1],
                "key_prefix": args[2],
                "name": args[3],
                "is_active": args[4],
                "created_at": datetime.now(),
                "expires_at": args[5],
                "last_used_at": None,
            }
            api_keys_db[key_id] = new_key
            return new_key
        return None

    async def mock_fetch(query, *args):
        # List users
        if "SELECT id, username, email, role_id, is_active" in query and "FROM users" in query:
            return list(users_db.values())
        # List API keys
        elif "SELECT id, user_id, key_hash, key_prefix, name, is_active" in query:
            user_id = args[0] if args else None
            return [k for k in api_keys_db.values() if k["user_id"] == user_id]
        return []

    mock_conn.fetchrow.side_effect = mock_fetchrow
    mock_conn.fetch.side_effect = mock_fetch
    mock_conn.execute = AsyncMock()

    # Create a mock admin user for authentication
    admin_user = User(
        id=1,
        username="admin_user",
        email="admin@example.com",
        role_id=1,
        is_active=True,
        rate_limits=None,
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )

    with patch("mascarade.auth.get_db_pool", return_value=mock_pool):
        with patch("mascarade.auth.authenticate_user", return_value=admin_user):
            async with _client() as client:
                # Step 1: Admin lists users (should see only themselves initially)
                response = await client.get(
                    "/users",
                    headers={"Authorization": "Bearer admin-key"},
                )
                assert response.status_code == 200
                assert len(response.json()["users"]) == 1

                # Step 2: Admin creates a regular user
                response = await client.post(
                    "/users",
                    json={
                        "username": "new_user",
                        "email": "newuser@example.com",
                        "role_id": 2,
                        "is_active": True,
                    },
                    headers={"Authorization": "Bearer admin-key"},
                )
                assert response.status_code == 200
                new_user_id = response.json()["id"]
                assert new_user_id == 2

                # Step 3: Admin creates an API key for the new user
                response = await client.post(
                    f"/users/{new_user_id}/api-keys",
                    json={
                        "name": "User API Key",
                        "expires_at": None,
                    },
                    headers={"Authorization": "Bearer admin-key"},
                )
                assert response.status_code == 201
                assert "key" in response.json()

                # Step 4: Admin lists all users (should see 2 now)
                response = await client.get(
                    "/users",
                    headers={"Authorization": "Bearer admin-key"},
                )
                assert response.status_code == 200
                assert len(response.json()["users"]) == 2

                # Step 5: Admin lists API keys for the new user
                response = await client.get(
                    f"/users/{new_user_id}/api-keys",
                    headers={"Authorization": "Bearer admin-key"},
                )
                assert response.status_code == 200
                assert len(response.json()["api_keys"]) == 1

                # Step 6: Admin updates rate limits for the new user
                response = await client.put(
                    f"/users/{new_user_id}/rate-limit",
                    json={
                        "requests_per_minute": 30,
                        "requests_per_hour": 500,
                        "requests_per_day": 5000,
                        "tokens_per_day": 500000,
                    },
                    headers={"Authorization": "Bearer admin-key"},
                )
                assert response.status_code == 200
                assert response.json()["rate_limits"]["requests_per_minute"] == 30


# --- Regular User Tests ---


@pytest.mark.asyncio
async def test_regular_user_can_make_llm_requests():
    """Test that regular users can make LLM requests via /send endpoint."""
    mock_pool, mock_conn = _mock_db_pool()

    # Mock database queries for regular user authentication
    async def mock_fetchrow(query, *args):
        if "SELECT * FROM api_keys" in query:
            # Return valid API key for regular user
            return {
                "id": 1,
                "user_id": 2,
                "key_hash": hash_api_key("user-key"),
                "key_prefix": "mk_test",
                "name": "User API Key",
                "expires_at": None,
                "is_active": True,
                "last_used_at": None,
                "created_at": datetime.now(),
            }
        elif "SELECT * FROM users WHERE id" in query:
            # Return regular user
            return {
                "id": 2,
                "username": "regular_user",
                "email": "user@example.com",
                "role_id": 2,  # User role
                "is_active": True,
                "rate_limits": None,
                "created_at": datetime.now(),
                "updated_at": datetime.now(),
            }
        return None

    mock_conn.fetchrow.side_effect = mock_fetchrow
    mock_conn.execute = AsyncMock()

    # Create a regular user
    regular_user = User(
        id=2,
        username="regular_user",
        email="user@example.com",
        role_id=2,
        is_active=True,
        rate_limits=None,
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )

    with patch("mascarade.auth.get_db_pool", return_value=mock_pool):
        with patch("mascarade.auth.authenticate_user", return_value=regular_user):
            with patch("mascarade.router.Router.send") as mock_send:
                # Mock router send to return a successful response
                mock_send.return_value = {
                    "role": "assistant",
                    "content": "Hello! How can I help you today?",
                    "model": "gpt-4",
                    "provider": "openai",
                    "usage": {"input_tokens": 10, "output_tokens": 8, "total_tokens": 18},
                }

                async with _client() as client:
                    response = await client.post(
                        "/send",
                        json={
                            "messages": [{"role": "user", "content": "Hello"}],
                            "strategy": "best",
                        },
                        headers={"Authorization": "Bearer user-key"},
                    )
                    assert response.status_code == 200
                    assert "content" in response.json()
                    assert response.json()["role"] == "assistant"


@pytest.mark.asyncio
async def test_regular_user_cannot_access_admin_endpoints():
    """Test that regular users cannot access admin-only endpoints."""
    mock_pool, mock_conn = _mock_db_pool()

    # Mock database queries for regular user authentication
    async def mock_fetchrow(query, *args):
        if "SELECT * FROM api_keys" in query:
            # Return valid API key for regular user
            return {
                "id": 1,
                "user_id": 2,
                "key_hash": hash_api_key("user-key"),
                "key_prefix": "mk_test",
                "name": "User API Key",
                "expires_at": None,
                "is_active": True,
                "last_used_at": None,
                "created_at": datetime.now(),
            }
        elif "SELECT * FROM users WHERE id" in query:
            # Return regular user
            return {
                "id": 2,
                "username": "regular_user",
                "email": "user@example.com",
                "role_id": 2,  # User role
                "is_active": True,
                "rate_limits": None,
                "created_at": datetime.now(),
                "updated_at": datetime.now(),
            }
        elif "SELECT name FROM roles WHERE id" in query:
            # Return "user" role (not admin)
            return {"name": "user"}
        return None

    mock_conn.fetchrow.side_effect = mock_fetchrow

    # Create a regular user
    regular_user = User(
        id=2,
        username="regular_user",
        email="user@example.com",
        role_id=2,
        is_active=True,
        rate_limits=None,
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )

    with patch("mascarade.auth.get_db_pool", return_value=mock_pool):
        with patch("mascarade.auth.authenticate_user", return_value=regular_user):
            async with _client() as client:
                # Test 1: Cannot list users (admin-only)
                response = await client.get(
                    "/users",
                    headers={"Authorization": "Bearer user-key"},
                )
                assert response.status_code == 403
                assert "admin" in response.json()["detail"].lower()

                # Test 2: Cannot create users (admin-only)
                response = await client.post(
                    "/users",
                    json={
                        "username": "another_user",
                        "email": "another@example.com",
                        "role_id": 2,
                        "is_active": True,
                    },
                    headers={"Authorization": "Bearer user-key"},
                )
                assert response.status_code == 403
                assert "admin" in response.json()["detail"].lower()

                # Test 3: Cannot access usage stats (admin-only)
                response = await client.get(
                    "/admin/usage/stats",
                    headers={"Authorization": "Bearer user-key"},
                )
                assert response.status_code == 403
                assert "admin" in response.json()["detail"].lower()

                # Test 4: Cannot update user info (admin-only)
                response = await client.put(
                    "/users/1",
                    json={"is_active": False},
                    headers={"Authorization": "Bearer user-key"},
                )
                assert response.status_code == 403

                # Test 5: Cannot delete users (admin-only)
                response = await client.delete(
                    "/users/1",
                    headers={"Authorization": "Bearer user-key"},
                )
                assert response.status_code == 403


@pytest.mark.asyncio
async def test_regular_user_cannot_modify_system_config():
    """Test that regular users cannot modify system configuration."""
    mock_pool, mock_conn = _mock_db_pool()

    # Mock database queries for regular user authentication
    async def mock_fetchrow(query, *args):
        if "SELECT * FROM api_keys" in query:
            # Return valid API key for regular user
            return {
                "id": 1,
                "user_id": 2,
                "key_hash": hash_api_key("user-key"),
                "key_prefix": "mk_test",
                "name": "User API Key",
                "expires_at": None,
                "is_active": True,
                "last_used_at": None,
                "created_at": datetime.now(),
            }
        elif "SELECT * FROM users WHERE id" in query:
            # Return regular user
            return {
                "id": 2,
                "username": "regular_user",
                "email": "user@example.com",
                "role_id": 2,  # User role
                "is_active": True,
                "rate_limits": None,
                "created_at": datetime.now(),
                "updated_at": datetime.now(),
            }
        elif "SELECT name FROM roles WHERE id" in query:
            # Return "user" role (not admin)
            return {"name": "user"}
        return None

    mock_conn.fetchrow.side_effect = mock_fetchrow

    # Create a regular user
    regular_user = User(
        id=2,
        username="regular_user",
        email="user@example.com",
        role_id=2,
        is_active=True,
        rate_limits=None,
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )

    with patch("mascarade.auth.get_db_pool", return_value=mock_pool):
        with patch("mascarade.auth.authenticate_user", return_value=regular_user):
            async with _client() as client:
                # Test: Cannot update provider keys (admin-only)
                response = await client.put(
                    "/providers/openai/key",
                    json={"key": "new-api-key"},
                    headers={"Authorization": "Bearer user-key"},
                )
                assert response.status_code == 403
                assert "admin" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_regular_user_can_view_providers():
    """Test that regular users can view provider information (read-only)."""
    mock_pool, mock_conn = _mock_db_pool()

    # Mock database queries for regular user authentication
    async def mock_fetchrow(query, *args):
        if "SELECT * FROM api_keys" in query:
            # Return valid API key for regular user
            return {
                "id": 1,
                "user_id": 2,
                "key_hash": hash_api_key("user-key"),
                "key_prefix": "mk_test",
                "name": "User API Key",
                "expires_at": None,
                "is_active": True,
                "last_used_at": None,
                "created_at": datetime.now(),
            }
        elif "SELECT * FROM users WHERE id" in query:
            # Return regular user
            return {
                "id": 2,
                "username": "regular_user",
                "email": "user@example.com",
                "role_id": 2,  # User role
                "is_active": True,
                "rate_limits": None,
                "created_at": datetime.now(),
                "updated_at": datetime.now(),
            }
        return None

    mock_conn.fetchrow.side_effect = mock_fetchrow

    # Create a regular user
    regular_user = User(
        id=2,
        username="regular_user",
        email="user@example.com",
        role_id=2,
        is_active=True,
        rate_limits=None,
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )

    with patch("mascarade.auth.get_db_pool", return_value=mock_pool):
        with patch("mascarade.auth.authenticate_user", return_value=regular_user):
            async with _client() as client:
                # Regular users can view providers
                response = await client.get(
                    "/providers",
                    headers={"Authorization": "Bearer user-key"},
                )
                assert response.status_code == 200
                assert isinstance(response.json(), list)


@pytest.mark.asyncio
async def test_complete_regular_user_workflow():
    """Test complete workflow for regular user with limited access."""
    mock_pool, mock_conn = _mock_db_pool()

    # Stateful mock to track user creation and authentication
    state = {
        "users": [
            {
                "id": 1,
                "username": "admin",
                "email": "admin@example.com",
                "role_id": 1,
                "is_active": True,
                "rate_limits": None,
                "created_at": datetime.now(),
                "updated_at": datetime.now(),
            }
        ],
        "api_keys": [],
    }

    async def mock_fetchrow(query, *args):
        if "SELECT id FROM roles WHERE name = 'admin'" in query:
            return {"id": 1}
        elif "SELECT id FROM roles WHERE name = 'user'" in query:
            return {"id": 2}
        elif "SELECT name FROM roles WHERE id = 1" in query:
            return {"name": "admin"}
        elif "SELECT name FROM roles WHERE id = 2" in query:
            return {"name": "user"}
        elif "SELECT id FROM users WHERE username" in query:
            # Check for existing username
            for u in state["users"]:
                if u["username"] == args[0]:
                    return {"id": u["id"]}
            return None
        elif "SELECT id FROM users WHERE email" in query:
            # Check for existing email
            for u in state["users"]:
                if u["email"] == args[0]:
                    return {"id": u["id"]}
            return None
        elif "SELECT id FROM roles WHERE id" in query:
            # Role exists
            if args[0] in [1, 2]:
                return {"id": args[0]}
            return None
        elif "INSERT INTO users" in query:
            # Create new user
            new_user = {
                "id": len(state["users"]) + 1,
                "username": args[0],
                "email": args[1],
                "role_id": args[2],
                "is_active": args[3] if len(args) > 3 else True,
                "rate_limits": None,
                "created_at": datetime.now(),
                "updated_at": datetime.now(),
            }
            state["users"].append(new_user)
            return new_user
        elif "SELECT * FROM users WHERE id" in query:
            # Find user by ID
            for u in state["users"]:
                if u["id"] == args[0]:
                    return u
            return None
        elif "INSERT INTO api_keys" in query:
            # Create API key
            new_key = {
                "id": len(state["api_keys"]) + 1,
                "user_id": args[0],
                "key_hash": args[1],
                "key_prefix": args[2],
                "name": args[3],
                "expires_at": args[4] if len(args) > 4 else None,
                "is_active": True,
                "last_used_at": None,
                "created_at": datetime.now(),
            }
            state["api_keys"].append(new_key)
            return new_key
        elif "SELECT * FROM api_keys WHERE key_hash" in query:
            # Find API key by hash
            for k in state["api_keys"]:
                if k["key_hash"] == args[0]:
                    return k
            return None
        return None

    async def mock_fetch(query, *args):
        if "SELECT * FROM users ORDER BY" in query:
            return state["users"]
        return []

    mock_conn.fetchrow.side_effect = mock_fetchrow
    mock_conn.fetch.side_effect = mock_fetch
    mock_conn.execute = AsyncMock()

    # Create admin user for authentication
    admin_user = User(
        id=1,
        username="admin",
        email="admin@example.com",
        role_id=1,
        is_active=True,
        rate_limits=None,
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )

    with patch("mascarade.auth.get_db_pool", return_value=mock_pool):
        # First, authenticate as admin to create regular user
        with patch("mascarade.auth.authenticate_user", return_value=admin_user):
            async with _client() as client:
                # Step 1: Admin creates a regular user
                response = await client.post(
                    "/users",
                    json={
                        "username": "regular_user",
                        "email": "user@example.com",
                        "role_id": 2,
                        "is_active": True,
                    },
                    headers={"Authorization": "Bearer admin-key"},
                )
                assert response.status_code == 200
                user_id = response.json()["id"]
                assert user_id == 2

                # Step 2: Admin creates API key for regular user
                response = await client.post(
                    f"/users/{user_id}/api-keys",
                    json={
                        "name": "User API Key",
                        "expires_at": None,
                    },
                    headers={"Authorization": "Bearer admin-key"},
                )
                assert response.status_code == 201
                user_api_key = response.json()["key"]
                assert user_api_key is not None

        # Now authenticate as regular user
        regular_user = User(
            id=2,
            username="regular_user",
            email="user@example.com",
            role_id=2,
            is_active=True,
            rate_limits=None,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

        with patch("mascarade.auth.authenticate_user", return_value=regular_user):
            with patch("mascarade.router.Router.send") as mock_send:
                # Mock router send to return a successful response
                mock_send.return_value = {
                    "role": "assistant",
                    "content": "Hello from regular user!",
                    "model": "gpt-4",
                    "provider": "openai",
                    "usage": {"input_tokens": 10, "output_tokens": 6, "total_tokens": 16},
                }

                async with _client() as client:
                    # Step 3: Regular user can make LLM requests
                    response = await client.post(
                        "/send",
                        json={
                            "messages": [{"role": "user", "content": "Hello"}],
                            "strategy": "best",
                        },
                        headers={"Authorization": f"Bearer {user_api_key}"},
                    )
                    assert response.status_code == 200
                    assert response.json()["role"] == "assistant"

                    # Step 4: Regular user can view providers
                    response = await client.get(
                        "/providers",
                        headers={"Authorization": f"Bearer {user_api_key}"},
                    )
                    assert response.status_code == 200

                    # Step 5: Regular user CANNOT access admin endpoints
                    response = await client.get(
                        "/users",
                        headers={"Authorization": f"Bearer {user_api_key}"},
                    )
                    assert response.status_code == 403

                    # Step 6: Regular user CANNOT modify system config
                    response = await client.put(
                        "/providers/openai/key",
                        json={"key": "new-key"},
                        headers={"Authorization": f"Bearer {user_api_key}"},
                    )
                    assert response.status_code == 403

                    # Step 7: Regular user CANNOT create other users
                    response = await client.post(
                        "/users",
                        json={
                            "username": "another_user",
                            "email": "another@example.com",
                            "role_id": 2,
                            "is_active": True,
                        },
                        headers={"Authorization": f"Bearer {user_api_key}"},
                    )
                    assert response.status_code == 403
