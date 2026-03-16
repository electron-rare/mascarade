"""Tests pour l'authentification Bearer token."""

from contextlib import asynccontextmanager

import httpx
import pytest

from mascarade.auth import (
    add_api_key,
    get_active_api_keys,
    get_rate_limit_metrics,
    is_valid_api_key,
    remove_api_key,
    reset_rate_limit,
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
        missing = await client.get("/v1/api-keys")
        invalid = await client.get(
            "/v1/api-keys",
            headers={"Authorization": "Bearer wrong-key-999"},
        )
        valid = await client.get(
            "/v1/api-keys",
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


def test_rate_limiting():
    """Test comprehensive rate limiting functionality."""
    import time

    from fastapi import HTTPException

    from mascarade.auth import RateLimiter

    # Test 1: Basic initialization with custom limits
    limiter = RateLimiter(per_user_limit=5, per_ip_limit=10, window_seconds=60)
    assert limiter._per_user_limit == 5
    assert limiter._per_ip_limit == 10
    assert limiter._window_seconds == 60

    # Test 2: Per-user rate limiting
    user_key = "test_user_123"

    # Should allow up to the limit
    for i in range(5):
        limiter.check_rate_limit(user_key=user_key)

    # 6th request should fail
    with pytest.raises(HTTPException) as exc_info:
        limiter.check_rate_limit(user_key=user_key)
    assert exc_info.value.status_code == 429
    assert "Rate limit exceeded" in exc_info.value.detail

    # Test 3: Per-IP rate limiting
    limiter2 = RateLimiter(per_user_limit=100, per_ip_limit=3, window_seconds=60)
    ip_address = "192.168.1.100"

    # Should allow up to the limit
    for i in range(3):
        limiter2.check_rate_limit(ip_address=ip_address)

    # 4th request should fail
    with pytest.raises(HTTPException) as exc_info:
        limiter2.check_rate_limit(ip_address=ip_address)
    assert exc_info.value.status_code == 429
    assert "Rate limit exceeded" in exc_info.value.detail

    # Test 4: Combined user + IP rate limiting
    limiter3 = RateLimiter(per_user_limit=5, per_ip_limit=5, window_seconds=60)
    user_key2 = "test_user_456"
    ip_address2 = "192.168.1.200"

    # Make 3 requests (both limits should track)
    for i in range(3):
        limiter3.check_rate_limit(user_key=user_key2, ip_address=ip_address2)

    # Verify both user and IP are being tracked
    metrics = limiter3.get_metrics()
    assert metrics["tracked_users"] >= 1
    assert metrics["tracked_ips"] >= 1
    assert metrics["total_user_requests"] >= 3
    assert metrics["total_ip_requests"] >= 3

    # Test 5: Rate limit reset for user
    limiter4 = RateLimiter(per_user_limit=2, per_ip_limit=100, window_seconds=60)
    user_key3 = "test_user_789"

    # Use up the limit
    for i in range(2):
        limiter4.check_rate_limit(user_key=user_key3)

    # Should be rate limited
    with pytest.raises(HTTPException) as exc_info:
        limiter4.check_rate_limit(user_key=user_key3)
    assert exc_info.value.status_code == 429

    # Reset the user's rate limit
    limiter4.reset(user_key=user_key3)

    # Should now succeed
    limiter4.check_rate_limit(user_key=user_key3)

    # Test 6: Rate limit reset for IP
    limiter5 = RateLimiter(per_user_limit=100, per_ip_limit=2, window_seconds=60)
    ip_address3 = "192.168.1.300"

    # Use up the limit
    for i in range(2):
        limiter5.check_rate_limit(ip_address=ip_address3)

    # Should be rate limited
    with pytest.raises(HTTPException) as exc_info:
        limiter5.check_rate_limit(ip_address=ip_address3)
    assert exc_info.value.status_code == 429

    # Reset the IP's rate limit
    limiter5.reset(ip_address=ip_address3)

    # Should now succeed
    limiter5.check_rate_limit(ip_address=ip_address3)

    # Test 7: Reset all rate limits
    limiter6 = RateLimiter(per_user_limit=1, per_ip_limit=1, window_seconds=60)

    limiter6.check_rate_limit(user_key="user_a")
    limiter6.check_rate_limit(user_key="user_b")
    limiter6.check_rate_limit(ip_address="10.0.0.1")
    limiter6.check_rate_limit(ip_address="10.0.0.2")

    # Verify tracking
    metrics = limiter6.get_metrics()
    assert metrics["tracked_users"] == 2
    assert metrics["tracked_ips"] == 2

    # Reset all
    limiter6.reset()

    # Verify all cleared
    metrics = limiter6.get_metrics()
    assert metrics["tracked_users"] == 0
    assert metrics["tracked_ips"] == 0

    # Test 8: Metrics retrieval
    limiter7 = RateLimiter(per_user_limit=10, per_ip_limit=10, window_seconds=60)

    # Make some requests
    limiter7.check_rate_limit(user_key="user_metrics_1")
    limiter7.check_rate_limit(user_key="user_metrics_1")
    limiter7.check_rate_limit(user_key="user_metrics_2")
    limiter7.check_rate_limit(ip_address="10.1.1.1")

    metrics = limiter7.get_metrics()
    assert metrics["tracked_users"] == 2
    assert metrics["tracked_ips"] == 1
    assert metrics["total_user_requests"] == 3
    assert metrics["total_ip_requests"] == 1

    # Test 9: Different users/IPs don't interfere
    limiter8 = RateLimiter(per_user_limit=2, per_ip_limit=2, window_seconds=60)

    # User A uses up their limit
    limiter8.check_rate_limit(user_key="user_a")
    limiter8.check_rate_limit(user_key="user_a")

    # User A is rate limited
    with pytest.raises(HTTPException):
        limiter8.check_rate_limit(user_key="user_a")

    # User B should still work
    limiter8.check_rate_limit(user_key="user_b")
    limiter8.check_rate_limit(user_key="user_b")

    # IP A uses up their limit
    limiter8.check_rate_limit(ip_address="10.0.0.1")
    limiter8.check_rate_limit(ip_address="10.0.0.1")

    # IP A is rate limited
    with pytest.raises(HTTPException):
        limiter8.check_rate_limit(ip_address="10.0.0.1")

    # IP B should still work
    limiter8.check_rate_limit(ip_address="10.0.0.2")
    limiter8.check_rate_limit(ip_address="10.0.0.2")

    # Test 10: Window expiration (requests outside window don't count)
    limiter9 = RateLimiter(per_user_limit=2, per_ip_limit=2, window_seconds=1)  # 1 second window
    user_key_expiry = "user_expiry"

    # Make 2 requests (at limit)
    limiter9.check_rate_limit(user_key=user_key_expiry)
    limiter9.check_rate_limit(user_key=user_key_expiry)

    # Should be rate limited immediately
    with pytest.raises(HTTPException):
        limiter9.check_rate_limit(user_key=user_key_expiry)

    # Wait for window to expire
    time.sleep(1.1)

    # Old requests should have expired, new request should succeed
    limiter9.check_rate_limit(user_key=user_key_expiry)


@pytest.mark.asyncio
async def test_rate_limiting_per_user():
    """Test que le rate limiting par utilisateur fonctionne correctement."""
    import os

    # Configure low rate limits for testing
    os.environ["MASCARADE_RATE_LIMIT_PER_USER"] = "3"
    os.environ["MASCARADE_RATE_LIMIT_PER_IP"] = "100"
    os.environ["MASCARADE_RATE_LIMIT_WINDOW"] = "60"

    # Need to reload the module to pick up new env vars
    from importlib import reload
    from mascarade import auth as auth_module

    reload(auth_module)
    from mascarade.auth import reset_rate_limit

    add_api_key(TEST_ADMIN_KEY)

    async with _client() as client:
        # First 3 requests should succeed
        for i in range(3):
            response = await client.get(
                "/v1/api-keys",
                headers={"Authorization": f"Bearer {TEST_ADMIN_KEY}"},
            )
            assert response.status_code == 200, f"Request {i+1} should succeed"

        # 4th request should be rate limited
        response = await client.get(
            "/v1/api-keys",
            headers={"Authorization": f"Bearer {TEST_ADMIN_KEY}"},
        )
        assert response.status_code == 429, "4th request should be rate limited"
        assert "Rate limit exceeded" in response.json()["detail"]

        # Reset rate limit and verify it works again
        import hashlib

        user_key = hashlib.sha256(TEST_ADMIN_KEY.encode()).hexdigest()
        reset_rate_limit(user_key=user_key)

        response = await client.get(
            "/v1/api-keys",
            headers={"Authorization": f"Bearer {TEST_ADMIN_KEY}"},
        )
        assert response.status_code == 200, "Request should succeed after reset"

    # Restore defaults
    os.environ["MASCARADE_RATE_LIMIT_PER_USER"] = "100"
    os.environ["MASCARADE_RATE_LIMIT_PER_IP"] = "200"
    reload(auth_module)


@pytest.mark.asyncio
async def test_rate_limiting_per_ip():
    """Test que le rate limiting par IP fonctionne correctement."""
    import os

    # Configure low IP rate limits for testing
    os.environ["MASCARADE_RATE_LIMIT_PER_USER"] = "100"
    os.environ["MASCARADE_RATE_LIMIT_PER_IP"] = "2"
    os.environ["MASCARADE_RATE_LIMIT_WINDOW"] = "60"

    from importlib import reload
    from mascarade import auth as auth_module

    reload(auth_module)
    from mascarade.auth import reset_rate_limit

    add_api_key(TEST_ADMIN_KEY)
    add_api_key(TEST_OPERATOR_KEY)

    async with _client() as client:
        # First 2 requests with different keys from same IP should succeed
        response1 = await client.get(
            "/v1/api-keys",
            headers={"Authorization": f"Bearer {TEST_ADMIN_KEY}"},
        )
        assert response1.status_code == 200

        response2 = await client.get(
            "/v1/api-keys",
            headers={"Authorization": f"Bearer {TEST_OPERATOR_KEY}"},
        )
        assert response2.status_code == 200

        # 3rd request from same IP should be rate limited
        response3 = await client.get(
            "/v1/api-keys",
            headers={"Authorization": f"Bearer {TEST_ADMIN_KEY}"},
        )
        assert response3.status_code == 429, "3rd request from same IP should be rate limited"
        assert "Rate limit exceeded" in response3.json()["detail"]

    # Restore defaults
    os.environ["MASCARADE_RATE_LIMIT_PER_USER"] = "100"
    os.environ["MASCARADE_RATE_LIMIT_PER_IP"] = "200"
    reload(auth_module)


def test_rate_limit_metrics():
    """Test que les métriques de rate limiting fonctionnent."""
    metrics = get_rate_limit_metrics()
    assert isinstance(metrics, dict)
    assert "tracked_users" in metrics
    assert "tracked_ips" in metrics
    assert "total_user_requests" in metrics
    assert "total_ip_requests" in metrics
