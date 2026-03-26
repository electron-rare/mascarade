"""Comprehensive security tests for mascarade.auth module.

Covers: hash_api_key, mask_api_key, is_valid_api_key, _resolve_role,
require_auth, require_admin, RateLimiter, add/remove_api_key thread safety,
migrate_legacy_keys.
"""

from __future__ import annotations

import hashlib
import hmac
import threading
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from mascarade.auth import (
    RateLimiter,
    _required_role_for_request,
    _resolve_role,
    _timing_safe_compare,
    add_api_key,
    get_active_api_keys,
    hash_api_key,
    is_valid_api_key,
    mask_api_key,
    migrate_legacy_keys,
    remove_api_key,
    require_admin,
    require_auth,
    reset_rate_limit,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

TEST_KEY = "test-key-abcdef12"
TEST_KEY_SHORT = "abc"  # Below 8-char minimum


@pytest.fixture(autouse=True)
def _clean_api_keys():
    """Ensure each test starts and ends with a clean key store."""
    for key in get_active_api_keys():
        remove_api_key(key)
    reset_rate_limit()
    yield
    for key in get_active_api_keys():
        remove_api_key(key)
    reset_rate_limit()


# ---------------------------------------------------------------------------
# 1. hash_api_key
# ---------------------------------------------------------------------------


class TestHashApiKey:
    def test_returns_hex_string(self):
        result = hash_api_key("my-secret-key")
        assert isinstance(result, str)
        assert len(result) == 64  # SHA-256 hex

    def test_deterministic(self):
        assert hash_api_key("same") == hash_api_key("same")

    def test_different_keys_different_hashes(self):
        assert hash_api_key("key-alpha-01") != hash_api_key("key-beta-002")

    @patch.dict("os.environ", {"MASCARADE_KEY_HASH_SECRET": "my-prod-secret"})
    def test_uses_env_secret(self):
        expected = hmac.new(b"my-prod-secret", b"key123", hashlib.sha256).hexdigest()
        assert hash_api_key("key123") == expected

    @patch.dict("os.environ", {"MASCARADE_KEY_HASH_SECRET": ""}, clear=False)
    def test_default_pepper_warning(self, caplog):
        """When MASCARADE_KEY_HASH_SECRET is empty, a CRITICAL log is emitted."""
        with caplog.at_level("CRITICAL", logger="mascarade.auth"):
            result = hash_api_key("some-key")
        assert "INSECURE" in caplog.text or "insecure" in caplog.text.lower()
        # Still returns a valid hash
        assert len(result) == 64


# ---------------------------------------------------------------------------
# 2. mask_api_key
# ---------------------------------------------------------------------------


class TestMaskApiKey:
    def test_long_key_masked(self):
        assert mask_api_key("abcdefghijklmnop") == "abcd...mnop"

    def test_short_key_fully_masked(self):
        assert mask_api_key("12345678") == "****"

    def test_very_short_key(self):
        assert mask_api_key("abc") == "****"

    def test_empty_string(self):
        assert mask_api_key("") == "****"

    def test_exactly_nine_chars(self):
        result = mask_api_key("123456789")
        assert result == "1234...6789"


# ---------------------------------------------------------------------------
# 3. is_valid_api_key (timing-safe comparison)
# ---------------------------------------------------------------------------


class TestIsValidApiKey:
    def test_valid_key(self):
        add_api_key(TEST_KEY)
        assert is_valid_api_key(TEST_KEY) is True

    def test_invalid_key(self):
        add_api_key(TEST_KEY)
        assert is_valid_api_key("wrong-key-xxxxxxxx") is False

    def test_empty_key(self):
        assert is_valid_api_key("") is False

    def test_short_key_rejected(self):
        assert is_valid_api_key(TEST_KEY_SHORT) is False

    def test_whitespace_stripped(self):
        add_api_key(TEST_KEY)
        assert is_valid_api_key(f"  {TEST_KEY}  ") is True

    def test_no_keys_configured(self):
        """When no keys are loaded, any key is invalid."""
        assert is_valid_api_key(TEST_KEY) is False

    def test_timing_safe_compare_equal(self):
        assert _timing_safe_compare("abc", "abc") is True

    def test_timing_safe_compare_not_equal(self):
        assert _timing_safe_compare("abc", "xyz") is False


# ---------------------------------------------------------------------------
# 4. _resolve_role (RBAC key resolution)
# ---------------------------------------------------------------------------


class TestResolveRole:
    @patch.dict(
        "os.environ",
        {
            "MASCARADE_RBAC_ENABLED": "true",
            "MASCARADE_RBAC_ADMIN_KEYS": "admin-key-00001",
            "MASCARADE_RBAC_OPERATOR_KEYS": "oper-key-000001",
            "MASCARADE_RBAC_VIEWER_KEYS": "viewer-key-0001",
        },
    )
    def test_admin_key_resolves(self):
        assert _resolve_role("admin-key-00001") == "admin"

    @patch.dict(
        "os.environ",
        {
            "MASCARADE_RBAC_ENABLED": "true",
            "MASCARADE_RBAC_ADMIN_KEYS": "admin-key-00001",
            "MASCARADE_RBAC_OPERATOR_KEYS": "oper-key-000001",
            "MASCARADE_RBAC_VIEWER_KEYS": "viewer-key-0001",
        },
    )
    def test_operator_key_resolves(self):
        assert _resolve_role("oper-key-000001") == "operator"

    @patch.dict(
        "os.environ",
        {
            "MASCARADE_RBAC_ENABLED": "true",
            "MASCARADE_RBAC_ADMIN_KEYS": "admin-key-00001",
            "MASCARADE_RBAC_OPERATOR_KEYS": "oper-key-000001",
            "MASCARADE_RBAC_VIEWER_KEYS": "viewer-key-0001",
        },
    )
    def test_viewer_key_resolves(self):
        assert _resolve_role("viewer-key-0001") == "viewer"

    @patch.dict(
        "os.environ",
        {
            "MASCARADE_RBAC_ENABLED": "true",
            "MASCARADE_RBAC_ADMIN_KEYS": "admin-key-00001",
            "MASCARADE_RBAC_OPERATOR_KEYS": "",
            "MASCARADE_RBAC_VIEWER_KEYS": "",
        },
    )
    def test_unknown_key_returns_none(self):
        assert _resolve_role("unknown-key-xxx") is None

    @patch.dict(
        "os.environ",
        {
            "MASCARADE_RBAC_ENABLED": "",
            "MASCARADE_RBAC_ADMIN_KEYS": "",
            "MASCARADE_RBAC_OPERATOR_KEYS": "",
            "MASCARADE_RBAC_VIEWER_KEYS": "",
        },
    )
    def test_rbac_disabled_returns_admin(self):
        """When RBAC is disabled (no keys, no flag), everyone is admin."""
        assert _resolve_role("any-token-here!") == "admin"


# ---------------------------------------------------------------------------
# 5. _required_role_for_request
# ---------------------------------------------------------------------------


class TestRequiredRoleForRequest:
    def test_api_keys_requires_admin(self):
        assert _required_role_for_request("GET", "/api-keys") == "admin"

    def test_providers_post_requires_admin(self):
        assert _required_role_for_request("POST", "/providers/x") == "admin"

    def test_providers_get_requires_viewer(self):
        assert _required_role_for_request("GET", "/providers/x") == "viewer"

    def test_cluster_get_requires_viewer(self):
        assert _required_role_for_request("GET", "/cluster/status") == "viewer"

    def test_cluster_post_requires_operator(self):
        assert _required_role_for_request("POST", "/cluster/action") == "operator"

    def test_generic_get_requires_viewer(self):
        assert _required_role_for_request("GET", "/some/path") == "viewer"

    def test_generic_post_requires_operator(self):
        assert _required_role_for_request("POST", "/some/path") == "operator"

    def test_runtime_secrets_requires_admin(self):
        assert _required_role_for_request("GET", "/runtime-secrets") == "admin"


# ---------------------------------------------------------------------------
# 6. require_auth flow
# ---------------------------------------------------------------------------


class TestRequireAuth:
    @pytest.mark.asyncio
    async def test_no_keys_configured_passes(self):
        """When no API keys are configured, require_auth is a no-op."""
        request = MagicMock()
        request.client = MagicMock(host="127.0.0.1")
        await require_auth(request, credentials=None)

    @pytest.mark.asyncio
    async def test_missing_token_raises_401(self):
        add_api_key(TEST_KEY)
        request = MagicMock()
        request.client = MagicMock(host="127.0.0.1")
        request.headers = MagicMock()
        request.headers.get = MagicMock(return_value=None)
        with pytest.raises(HTTPException) as exc_info:
            await require_auth(request, credentials=None)
        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_invalid_token_raises_401(self):
        add_api_key(TEST_KEY)
        request = MagicMock()
        request.client = MagicMock(host="127.0.0.1")
        request.headers = MagicMock()
        request.headers.get = MagicMock(return_value=None)
        creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials="wrong-key-xxxxxxxx")
        with pytest.raises(HTTPException) as exc_info:
            await require_auth(request, credentials=creds)
        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    @patch.dict(
        "os.environ",
        {
            "MASCARADE_RBAC_ENABLED": "",
            "MASCARADE_RBAC_ADMIN_KEYS": "",
            "MASCARADE_RBAC_OPERATOR_KEYS": "",
            "MASCARADE_RBAC_VIEWER_KEYS": "",
        },
    )
    async def test_valid_token_passes(self):
        add_api_key(TEST_KEY)
        request = MagicMock()
        request.client = MagicMock(host="127.0.0.1")
        request.method = "GET"
        request.url = MagicMock(path="/health")
        creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=TEST_KEY)
        # Should not raise
        await require_auth(request, credentials=creds)

    @pytest.mark.asyncio
    async def test_x_api_key_header_fallback(self):
        """require_auth falls back to X-API-Key header."""
        add_api_key(TEST_KEY)
        request = MagicMock()
        request.client = MagicMock(host="127.0.0.1")
        request.headers = MagicMock()
        request.headers.get = MagicMock(return_value=TEST_KEY)
        request.method = "GET"
        request.url = MagicMock(path="/health")

        with patch.dict(
            "os.environ",
            {
                "MASCARADE_RBAC_ENABLED": "",
                "MASCARADE_RBAC_ADMIN_KEYS": "",
                "MASCARADE_RBAC_OPERATOR_KEYS": "",
                "MASCARADE_RBAC_VIEWER_KEYS": "",
            },
        ):
            await require_auth(request, credentials=None)

    @pytest.mark.asyncio
    @patch.dict(
        "os.environ",
        {
            "MASCARADE_RBAC_ENABLED": "true",
            "MASCARADE_RBAC_ADMIN_KEYS": "",
            "MASCARADE_RBAC_OPERATOR_KEYS": "",
            "MASCARADE_RBAC_VIEWER_KEYS": TEST_KEY,
        },
    )
    async def test_insufficient_role_raises_403(self):
        """A viewer key trying to access an admin route gets 403."""
        add_api_key(TEST_KEY)
        request = MagicMock()
        request.client = MagicMock(host="127.0.0.1")
        request.method = "POST"
        request.url = MagicMock(path="/api-keys")
        creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=TEST_KEY)
        with pytest.raises(HTTPException) as exc_info:
            await require_auth(request, credentials=creds)
        assert exc_info.value.status_code == 403


# ---------------------------------------------------------------------------
# 7. require_admin flow
# ---------------------------------------------------------------------------


class TestRequireAdmin:
    @pytest.mark.asyncio
    async def test_no_db_pool_raises_500(self):
        user = MagicMock()
        user.id = 1
        user.role_id = 1
        with patch("mascarade.auth.get_db_pool", return_value=None):
            with pytest.raises(HTTPException) as exc_info:
                await require_admin(current_user=user)
            assert exc_info.value.status_code == 500

    @pytest.mark.asyncio
    async def test_admin_role_passes(self):
        user = MagicMock()
        user.id = 1
        user.username = "admin_user"
        user.role_id = 1

        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(return_value={"name": "admin"})

        mock_pool = AsyncMock()
        mock_pool.acquire = MagicMock(return_value=_async_ctx(mock_conn))

        with patch("mascarade.auth.get_db_pool", return_value=mock_pool):
            result = await require_admin(current_user=user)
        assert result is user

    @pytest.mark.asyncio
    async def test_non_admin_role_raises_403(self):
        user = MagicMock()
        user.id = 2
        user.username = "reader"
        user.role_id = 3

        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(return_value={"name": "read_only"})

        mock_pool = AsyncMock()
        mock_pool.acquire = MagicMock(return_value=_async_ctx(mock_conn))

        with patch("mascarade.auth.get_db_pool", return_value=mock_pool):
            with pytest.raises(HTTPException) as exc_info:
                await require_admin(current_user=user)
            assert exc_info.value.status_code == 403


# ---------------------------------------------------------------------------
# 8. RateLimiter
# ---------------------------------------------------------------------------


class TestRateLimiter:
    def test_allows_under_limit(self):
        limiter = RateLimiter(per_user_limit=5, per_ip_limit=10, window_seconds=60)
        # Should not raise for 5 requests
        for _ in range(5):
            limiter.check_rate_limit(user_key="u1")

    def test_blocks_over_user_limit(self):
        limiter = RateLimiter(per_user_limit=3, per_ip_limit=100, window_seconds=60)
        for _ in range(3):
            limiter.check_rate_limit(user_key="u1")
        with pytest.raises(HTTPException) as exc_info:
            limiter.check_rate_limit(user_key="u1")
        assert exc_info.value.status_code == 429

    def test_blocks_over_ip_limit(self):
        limiter = RateLimiter(per_user_limit=100, per_ip_limit=2, window_seconds=60)
        for _ in range(2):
            limiter.check_rate_limit(ip_address="10.0.0.1")
        with pytest.raises(HTTPException) as exc_info:
            limiter.check_rate_limit(ip_address="10.0.0.1")
        assert exc_info.value.status_code == 429

    def test_different_users_independent(self):
        limiter = RateLimiter(per_user_limit=2, per_ip_limit=100, window_seconds=60)
        limiter.check_rate_limit(user_key="a")
        limiter.check_rate_limit(user_key="a")
        # User "b" should still be allowed
        limiter.check_rate_limit(user_key="b")

    def test_reset_specific_user(self):
        limiter = RateLimiter(per_user_limit=2, per_ip_limit=100, window_seconds=60)
        limiter.check_rate_limit(user_key="u1")
        limiter.check_rate_limit(user_key="u1")
        limiter.reset(user_key="u1")
        # Should be allowed again
        limiter.check_rate_limit(user_key="u1")

    def test_reset_all(self):
        limiter = RateLimiter(per_user_limit=1, per_ip_limit=1, window_seconds=60)
        limiter.check_rate_limit(user_key="u1", ip_address="10.0.0.1")
        limiter.reset()
        # Both should work again
        limiter.check_rate_limit(user_key="u1", ip_address="10.0.0.1")

    def test_metrics(self):
        limiter = RateLimiter(per_user_limit=100, per_ip_limit=100, window_seconds=60)
        limiter.check_rate_limit(user_key="u1", ip_address="10.0.0.1")
        limiter.check_rate_limit(user_key="u2")
        metrics = limiter.get_metrics()
        assert metrics["tracked_users"] == 2
        assert metrics["tracked_ips"] == 1
        assert metrics["total_user_requests"] == 2
        assert metrics["total_ip_requests"] == 1

    def test_no_key_or_ip_is_noop(self):
        limiter = RateLimiter(per_user_limit=1, per_ip_limit=1, window_seconds=60)
        # Should not raise when neither key nor IP provided
        limiter.check_rate_limit()


# ---------------------------------------------------------------------------
# 9. add_api_key / remove_api_key thread safety
# ---------------------------------------------------------------------------


class TestApiKeyManagement:
    def test_add_and_remove(self):
        add_api_key(TEST_KEY)
        assert TEST_KEY in get_active_api_keys()
        remove_api_key(TEST_KEY)
        assert TEST_KEY not in get_active_api_keys()

    def test_add_short_key_ignored(self):
        add_api_key("short")
        assert "short" not in get_active_api_keys()

    def test_add_empty_key_ignored(self):
        add_api_key("")
        assert len(get_active_api_keys()) == 0

    def test_remove_nonexistent_key(self):
        # Should not raise
        remove_api_key("nonexistent-key-xxx")

    def test_remove_empty_key(self):
        remove_api_key("")

    def test_concurrent_add_remove(self):
        """Thread safety: concurrent add/remove should not corrupt state."""
        keys = [f"thread-key-{i:04d}" for i in range(20)]
        errors: list[Exception] = []

        def _add_keys():
            try:
                for k in keys:
                    add_api_key(k)
            except Exception as e:
                errors.append(e)

        def _remove_keys():
            try:
                for k in keys:
                    remove_api_key(k)
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=_add_keys),
            threading.Thread(target=_remove_keys),
            threading.Thread(target=_add_keys),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)

        assert not errors, f"Thread safety errors: {errors}"

    def test_add_duplicate_key_idempotent(self):
        add_api_key(TEST_KEY)
        add_api_key(TEST_KEY)
        keys = get_active_api_keys()
        assert keys.count(TEST_KEY) == 1


# ---------------------------------------------------------------------------
# 10. migrate_legacy_keys
# ---------------------------------------------------------------------------


class TestMigrateLegacyKeys:
    @pytest.mark.asyncio
    async def test_no_db_pool_raises(self):
        with patch("mascarade.auth.get_db_pool", return_value=None):
            with pytest.raises(RuntimeError, match="Database pool not initialized"):
                await migrate_legacy_keys()

    @pytest.mark.asyncio
    async def test_no_configured_keys_returns_empty(self):
        mock_pool = AsyncMock()
        with (
            patch("mascarade.auth.get_db_pool", return_value=mock_pool),
            patch("mascarade.auth._configured_api_keys_string", return_value=""),
        ):
            result = await migrate_legacy_keys()
        assert result["migrated"] == 0
        assert result["skipped"] == 0
        assert result["failed"] == 0

    @pytest.mark.asyncio
    async def test_skips_already_migrated_keys(self):
        mock_conn = AsyncMock()
        # fetchrow returns existing migration record
        mock_conn.fetchrow = AsyncMock(return_value={"id": 1})

        mock_pool = AsyncMock()
        mock_pool.acquire = MagicMock(return_value=_async_ctx(mock_conn))

        with (
            patch("mascarade.auth.get_db_pool", return_value=mock_pool),
            patch(
                "mascarade.auth._configured_api_keys_string",
                return_value="legacy-key-0001",
            ),
        ):
            result = await migrate_legacy_keys()
        # First fetchrow is for admin role, second is for checking migration
        # The mock returns {"id": 1} for both, so admin_role check passes
        # and migration check finds existing -> skipped
        assert result["skipped"] == 1


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _async_ctx:
    """Minimal async context manager wrapping a value for pool.acquire()."""

    def __init__(self, value: Any) -> None:
        self._value = value

    async def __aenter__(self) -> Any:
        return self._value

    async def __aexit__(self, *args: Any) -> None:
        pass
