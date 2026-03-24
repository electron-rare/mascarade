"""Tests for mascarade.routers.admin — Admin user/key management endpoints."""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from mascarade.db.models import User
from mascarade.routers.admin import _get_authenticated_user, _require_admin
from mascarade.server import app


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _admin_user() -> User:
    return User(
        id=1,
        username="admin",
        email="admin@test.com",
        role_id=1,
        is_active=True,
        rate_limits=None,
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )


def _regular_user() -> User:
    return User(
        id=2,
        username="user",
        email="user@test.com",
        role_id=2,
        is_active=True,
        rate_limits=None,
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )


def _mock_pool(conn=None):
    """Build a mock asyncpg pool with acquire() as async context manager."""
    if conn is None:
        conn = AsyncMock()
    pool = MagicMock()
    cm = AsyncMock()
    cm.__aenter__ = AsyncMock(return_value=conn)
    cm.__aexit__ = AsyncMock(return_value=False)
    pool.acquire.return_value = cm
    return pool


@asynccontextmanager
async def _client(**state_overrides):
    async with app.router.lifespan_context(app):
        for k, v in state_overrides.items():
            setattr(app.state, k, v)
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            yield client


# ---------------------------------------------------------------------------
# _get_authenticated_user
# ---------------------------------------------------------------------------


class TestGetAuthenticatedUser:
    @pytest.mark.asyncio
    async def test_valid_bearer_token(self):
        user = _admin_user()
        request = MagicMock()
        request.headers = {"Authorization": "Bearer valid-key"}

        with patch("mascarade.routers.admin.auth_module.authenticate_user", new_callable=AsyncMock, return_value=user):
            result = await _get_authenticated_user(request)
        assert result.username == "admin"

    @pytest.mark.asyncio
    async def test_missing_auth_header(self):
        request = MagicMock()
        request.headers = {}

        with pytest.raises(Exception) as exc_info:
            await _get_authenticated_user(request)
        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_invalid_token_no_pool(self):
        request = MagicMock()
        request.headers = {"Authorization": "Bearer bad-key"}

        with patch("mascarade.routers.admin.auth_module.authenticate_user", new_callable=AsyncMock, return_value=None), \
             patch("mascarade.routers.admin.auth_module.get_db_pool", return_value=None):
            with pytest.raises(Exception) as exc_info:
                await _get_authenticated_user(request)
            assert exc_info.value.status_code == 401


# ---------------------------------------------------------------------------
# _require_admin
# ---------------------------------------------------------------------------


class TestRequireAdmin:
    @pytest.mark.asyncio
    async def test_admin_passes(self):
        user = _admin_user()
        request = MagicMock()
        request.headers = {"Authorization": "Bearer key"}

        with patch("mascarade.routers.admin.auth_module.authenticate_user", new_callable=AsyncMock, return_value=user):
            result = await _require_admin(request)
        assert result.role_id == 1

    @pytest.mark.asyncio
    async def test_non_admin_rejected(self):
        user = _regular_user()
        request = MagicMock()
        request.headers = {"Authorization": "Bearer key"}

        with patch("mascarade.routers.admin.auth_module.authenticate_user", new_callable=AsyncMock, return_value=user):
            with pytest.raises(Exception) as exc_info:
                await _require_admin(request)
            assert exc_info.value.status_code == 403


# ---------------------------------------------------------------------------
# HTTP endpoint tests
# ---------------------------------------------------------------------------


class TestListUsers:
    @pytest.mark.asyncio
    async def test_list_users_returns_list(self):
        admin = _admin_user()
        conn = AsyncMock()
        conn.fetch = AsyncMock(return_value=[
            {"id": 1, "username": "admin", "email": "a@b.com", "role_id": 1, "is_active": True, "rate_limits": None, "created_at": datetime.now(), "updated_at": datetime.now()},
        ])
        pool = _mock_pool(conn)

        with patch("mascarade.routers.admin.auth_module.authenticate_user", new_callable=AsyncMock, return_value=admin), \
             patch("mascarade.routers.admin.auth_module.get_db_pool", return_value=pool):
            async with _client() as client:
                resp = await client.get("/v1/users", headers={"Authorization": "Bearer test-key"})

        assert resp.status_code == 200
        body = resp.json()
        assert "users" in body
        assert len(body["users"]) == 1


class TestCreateUser:
    @pytest.mark.asyncio
    async def test_create_user_success(self):
        admin = _admin_user()
        now = datetime.now()
        conn = AsyncMock()
        conn.fetchrow = AsyncMock(side_effect=[
            None,  # username check
            None,  # email check
            {"id": 2},  # role check
            {"id": 3, "username": "newuser", "email": "new@test.com", "role_id": 2, "is_active": True, "created_at": now.isoformat(), "updated_at": now.isoformat()},  # INSERT RETURNING
        ])
        pool = _mock_pool(conn)

        with patch("mascarade.routers.admin.auth_module.authenticate_user", new_callable=AsyncMock, return_value=admin), \
             patch("mascarade.routers.admin.auth_module.get_db_pool", return_value=pool):
            async with _client() as client:
                resp = await client.post(
                    "/v1/users",
                    json={"username": "newuser", "email": "new@test.com", "role_id": 2},
                    headers={"Authorization": "Bearer test-key"},
                )

        assert resp.status_code == 200
        assert resp.json()["username"] == "newuser"

    @pytest.mark.asyncio
    async def test_create_user_duplicate_username(self):
        admin = _admin_user()
        conn = AsyncMock()
        conn.fetchrow = AsyncMock(side_effect=[
            {"id": 99},  # username already exists
        ])
        pool = _mock_pool(conn)

        with patch("mascarade.routers.admin.auth_module.authenticate_user", new_callable=AsyncMock, return_value=admin), \
             patch("mascarade.routers.admin.auth_module.get_db_pool", return_value=pool):
            async with _client() as client:
                resp = await client.post(
                    "/v1/users",
                    json={"username": "taken", "email": "x@x.com", "role_id": 2},
                    headers={"Authorization": "Bearer test-key"},
                )

        assert resp.status_code == 409
        assert "already taken" in resp.json()["detail"]


class TestDeleteUser:
    @pytest.mark.asyncio
    async def test_delete_user_success(self):
        admin = _admin_user()
        conn = AsyncMock()
        conn.fetchrow = AsyncMock(return_value={"id": 5})
        conn.execute = AsyncMock()
        pool = _mock_pool(conn)

        with patch("mascarade.routers.admin.auth_module.authenticate_user", new_callable=AsyncMock, return_value=admin), \
             patch("mascarade.routers.admin.auth_module.get_db_pool", return_value=pool):
            async with _client() as client:
                resp = await client.delete("/v1/users/5", headers={"Authorization": "Bearer test-key"})

        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"


class TestCreateApiKey:
    @pytest.mark.asyncio
    async def test_create_api_key_success(self):
        admin = _admin_user()
        now = datetime.now()
        conn = AsyncMock()
        conn.fetchrow = AsyncMock(side_effect=[
            {"id": 2},  # _find_user_by_id
            {"id": 10, "user_id": 2, "key_hash": "h", "key_prefix": "mk_abcde", "name": "Test Key", "is_active": True, "created_at": now, "expires_at": None, "last_used_at": None},  # INSERT RETURNING
        ])
        pool = _mock_pool(conn)

        with patch("mascarade.routers.admin.auth_module.authenticate_user", new_callable=AsyncMock, return_value=admin), \
             patch("mascarade.routers.admin.auth_module.get_db_pool", return_value=pool), \
             patch("mascarade.routers.admin.auth_module.hash_api_key", return_value="hashed"):
            async with _client() as client:
                resp = await client.post(
                    "/v1/users/2/api-keys",
                    json={"name": "Test Key"},
                    headers={"Authorization": "Bearer test-key"},
                )

        assert resp.status_code == 201
        body = resp.json()
        assert "key" in body
        assert body["key"].startswith("mk_")


class TestUsageStats:
    @pytest.mark.asyncio
    async def test_usage_stats_returns_aggregated(self):
        admin = _admin_user()
        conn = AsyncMock()
        conn.fetch = AsyncMock(side_effect=[
            [{"user_id": 1}],  # DISTINCT user_ids
            [{"provider": "openai", "count": 5}],  # provider breakdown
            [{"model": "gpt-4", "count": 5}],  # model breakdown
        ])
        conn.fetchrow = AsyncMock(return_value={
            "total_requests": 5,
            "total_tokens": 1000,
            "total_cost": 0.25,
        })
        pool = _mock_pool(conn)

        with patch("mascarade.routers.admin.auth_module.authenticate_user", new_callable=AsyncMock, return_value=admin), \
             patch("mascarade.routers.admin.auth_module.get_db_pool", return_value=pool):
            async with _client() as client:
                resp = await client.get("/v1/admin/usage/stats", headers={"Authorization": "Bearer test-key"})

        assert resp.status_code == 200
        body = resp.json()
        assert "stats" in body
        assert len(body["stats"]) == 1
        assert body["stats"][0]["total_requests"] == 5


class TestAuthRejection:
    @pytest.mark.asyncio
    async def test_no_auth_returns_401(self):
        async with _client() as client:
            resp = await client.get("/v1/users")

        assert resp.status_code == 401
