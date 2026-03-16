"""Authentication — Bearer token with multi-key support and rotation."""

from __future__ import annotations

import hashlib
import hmac
import logging
import os
import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from mascarade.config import settings
from mascarade.db.connection import get_db_pool
from mascarade.db.models import ApiKeyRecord, RoleRecord, User, UserRecord

logger = logging.getLogger("mascarade.auth")

_api_keys: set[str] = set()
_last_key_rotation = 0
_KEY_ROTATION_INTERVAL = 3600
_keys_lock = threading.Lock()
_MIN_API_KEY_LENGTH = 16
AuthRole = Literal["viewer", "operator", "admin"]
_ROLE_RANK: dict[AuthRole, int] = {"viewer": 1, "operator": 2, "admin": 3}


# --- Rate Limiting ---


@dataclass
class RateLimitConfig:
    """Configuration for rate limiting."""

    per_user_limit: int
    per_ip_limit: int
    window_seconds: int


class RateLimiter:
    """
    Thread-safe rate limiter with per-user and per-IP tracking.

    Implements sliding window rate limiting to prevent abuse and ensure fair
    resource usage across users and IP addresses.

    Configuration via environment variables:
    - MASCARADE_RATE_LIMIT_PER_USER: Max requests per user per window (default: 100)
    - MASCARADE_RATE_LIMIT_PER_IP: Max requests per IP per window (default: 200)
    - MASCARADE_RATE_LIMIT_WINDOW: Time window in seconds (default: 60)

    States tracked:
    - Per-user: Tracks requests by API key hash
    - Per-IP: Tracks requests by client IP address
    - Automatic cleanup: Removes expired timestamps periodically

    Usage:
        limiter = RateLimiter()
        limiter.check_rate_limit(user_key="user123", ip_address="192.168.1.1")
        # Raises HTTPException(429) if rate limit exceeded
    """

    def __init__(
        self,
        per_user_limit: int | None = None,
        per_ip_limit: int | None = None,
        window_seconds: int | None = None,
    ) -> None:
        """
        Initialize the rate limiter.

        Args:
            per_user_limit: Max requests per user per window (from env if None)
            per_ip_limit: Max requests per IP per window (from env if None)
            window_seconds: Time window in seconds (from env if None)
        """
        self._per_user_limit = per_user_limit or int(
            os.getenv("MASCARADE_RATE_LIMIT_PER_USER", "100")
        )
        self._per_ip_limit = per_ip_limit or int(
            os.getenv("MASCARADE_RATE_LIMIT_PER_IP", "200")
        )
        self._window_seconds = window_seconds or int(
            os.getenv("MASCARADE_RATE_LIMIT_WINDOW", "60")
        )

        # Track request timestamps per user and per IP
        self._user_requests: dict[str, deque[float]] = defaultdict(lambda: deque())
        self._ip_requests: dict[str, deque[float]] = defaultdict(lambda: deque())

        # Locks for thread-safe access
        self._user_lock = threading.Lock()
        self._ip_lock = threading.Lock()

        # Last cleanup timestamp
        self._last_cleanup = time.time()
        self._cleanup_interval = 300  # Clean up every 5 minutes

        logger.info(
            f"RateLimiter initialized: per_user={self._per_user_limit}/min, "
            f"per_ip={self._per_ip_limit}/min, window={self._window_seconds}s"
        )

    def _cleanup_old_requests(self) -> None:
        """Remove expired request timestamps (older than the window)."""
        now = time.time()
        if now - self._last_cleanup < self._cleanup_interval:
            return

        cutoff = now - self._window_seconds

        # Clean up user requests
        with self._user_lock:
            for user_key in list(self._user_requests.keys()):
                requests = self._user_requests[user_key]
                # Remove timestamps older than cutoff
                while requests and requests[0] < cutoff:
                    requests.popleft()
                # Remove empty entries
                if not requests:
                    del self._user_requests[user_key]

        # Clean up IP requests
        with self._ip_lock:
            for ip_addr in list(self._ip_requests.keys()):
                requests = self._ip_requests[ip_addr]
                # Remove timestamps older than cutoff
                while requests and requests[0] < cutoff:
                    requests.popleft()
                # Remove empty entries
                if not requests:
                    del self._ip_requests[ip_addr]

        self._last_cleanup = now
        logger.debug("Rate limiter cleanup completed")

    def _check_limit(
        self,
        key: str,
        requests: deque[float],
        limit: int,
        limit_type: str,
    ) -> None:
        """
        Check if a key has exceeded the rate limit.

        Args:
            key: User key or IP address
            requests: Deque of request timestamps
            limit: Maximum allowed requests
            limit_type: "user" or "ip" for logging

        Raises:
            HTTPException: 429 if rate limit exceeded
        """
        now = time.time()
        cutoff = now - self._window_seconds

        # Remove old timestamps
        while requests and requests[0] < cutoff:
            requests.popleft()

        # Check if limit exceeded
        if len(requests) >= limit:
            logger.warning(
                f"Rate limit exceeded for {limit_type}: {key} "
                f"({len(requests)}/{limit} requests in {self._window_seconds}s)"
            )
            raise HTTPException(
                status_code=429,
                detail=f"Rate limit exceeded. Max {limit} requests per {self._window_seconds} seconds.",
            )

        # Add current timestamp
        requests.append(now)

    def check_rate_limit(
        self,
        user_key: str | None = None,
        ip_address: str | None = None,
    ) -> None:
        """
        Check rate limits for a request.

        Args:
            user_key: Unique identifier for the user (e.g., API key hash)
            ip_address: Client IP address

        Raises:
            HTTPException: 429 if rate limit exceeded for user or IP
        """
        # Periodic cleanup
        self._cleanup_old_requests()

        # Check per-user limit
        if user_key:
            with self._user_lock:
                requests = self._user_requests[user_key]
                self._check_limit(user_key, requests, self._per_user_limit, "user")

        # Check per-IP limit
        if ip_address:
            with self._ip_lock:
                requests = self._ip_requests[ip_address]
                self._check_limit(ip_address, requests, self._per_ip_limit, "IP")

    def get_metrics(self) -> dict[str, int]:
        """
        Get current rate limiter metrics.

        Returns:
            Dictionary with metrics:
            - tracked_users: Number of users being tracked
            - tracked_ips: Number of IPs being tracked
            - total_user_requests: Total active user request timestamps
            - total_ip_requests: Total active IP request timestamps
        """
        with self._user_lock:
            tracked_users = len(self._user_requests)
            total_user_requests = sum(len(reqs) for reqs in self._user_requests.values())

        with self._ip_lock:
            tracked_ips = len(self._ip_requests)
            total_ip_requests = sum(len(reqs) for reqs in self._ip_requests.values())

        return {
            "tracked_users": tracked_users,
            "tracked_ips": tracked_ips,
            "total_user_requests": total_user_requests,
            "total_ip_requests": total_ip_requests,
        }

    def reset(self, user_key: str | None = None, ip_address: str | None = None) -> None:
        """
        Reset rate limit counters for a specific user or IP.

        Args:
            user_key: User key to reset (resets all if None and ip_address is None)
            ip_address: IP address to reset
        """
        if user_key:
            with self._user_lock:
                if user_key in self._user_requests:
                    del self._user_requests[user_key]
                    logger.info(f"Rate limit reset for user: {user_key}")

        if ip_address:
            with self._ip_lock:
                if ip_address in self._ip_requests:
                    del self._ip_requests[ip_address]
                    logger.info(f"Rate limit reset for IP: {ip_address}")

        if not user_key and not ip_address:
            # Reset all
            with self._user_lock:
                self._user_requests.clear()
            with self._ip_lock:
                self._ip_requests.clear()
            logger.info("All rate limits reset")


# Global rate limiter instance
_rate_limiter = RateLimiter()


def _load_api_keys() -> None:
    """Load API keys from configuration (thread-safe)."""
    global _api_keys, _last_key_rotation

    with _keys_lock:
        if settings.mascarade_api_key:
            new_keys = {
                key.strip()
                for key in settings.mascarade_api_key.split(",")
                if key.strip() and len(key.strip()) >= _MIN_API_KEY_LENGTH
            }
            if new_keys != _api_keys:
                logger.info("Loading API keys: %d keys configured", len(new_keys))
                _api_keys.clear()
                _api_keys.update(new_keys)
        else:
            if _api_keys:
                logger.info("Clearing all API keys (none configured)")
                _api_keys.clear()
            logger.warning("No MASCARADE_API_KEY configured — all protected routes are PUBLIC")

        _last_key_rotation = time.time()


def _rotate_keys_if_needed() -> None:
    """Rotate keys if needed (every hour) - thread-safe."""
    with _keys_lock:
        if time.time() - _last_key_rotation > _KEY_ROTATION_INTERVAL:
            # Release lock before reload (load_api_keys acquires it)
            pass
        else:
            return
    _load_api_keys()


def _timing_safe_compare(a: str, b: str) -> bool:
    """Constant-time string comparison to prevent timing attacks."""
    return hmac.compare_digest(a.encode(), b.encode())


def is_valid_api_key(key: str) -> bool:
    """Check if an API key is valid (thread-safe, timing-safe)."""
    if not key or len(key.strip()) < _MIN_API_KEY_LENGTH:
        return False

    _rotate_keys_if_needed()
    candidate = key.strip()
    with _keys_lock:
        return any(_timing_safe_compare(candidate, k) for k in _api_keys)


def _configured_role_keys(env_name: str) -> list[str]:
    return [
        key.strip()
        for key in str(os.getenv(env_name, "")).split(",")
        if key.strip() and len(key.strip()) >= _MIN_API_KEY_LENGTH
    ]


def _resolve_role(token: str) -> AuthRole | None:
    admin_keys = _configured_role_keys("MASCARADE_RBAC_ADMIN_KEYS")
    operator_keys = _configured_role_keys("MASCARADE_RBAC_OPERATOR_KEYS")
    viewer_keys = _configured_role_keys("MASCARADE_RBAC_VIEWER_KEYS")
    rbac_enabled = (
        str(os.getenv("MASCARADE_RBAC_ENABLED", "")).strip().lower() in {"1", "true", "yes"}
        or bool(admin_keys or operator_keys or viewer_keys)
    )

    if not rbac_enabled:
        return "admin"
    if any(_timing_safe_compare(token, key) for key in admin_keys):
        return "admin"
    if any(_timing_safe_compare(token, key) for key in operator_keys):
        return "operator"
    if any(_timing_safe_compare(token, key) for key in viewer_keys):
        return "viewer"
    return None


def _required_role_for_request(method: str, path: str) -> AuthRole:
    normalized_method = (method or "").upper()
    normalized_path = (path or "").lower()

    if normalized_path.startswith("/api-keys"):
        return "admin"
    if normalized_path.startswith("/providers") and normalized_method not in {"GET", "HEAD", "OPTIONS"}:
        return "admin"
    if normalized_path.startswith("/runtime-secrets"):
        return "admin"
    if normalized_path.startswith("/mcp/industrial"):
        return "admin"
    if normalized_path.startswith("/cluster/forward"):
        return "admin"
    if normalized_path.startswith("/cluster") or normalized_path.startswith("/p2p"):
        return "viewer" if normalized_method in {"GET", "HEAD", "OPTIONS"} else "operator"

    if normalized_method in {"GET", "HEAD", "OPTIONS"}:
        return "viewer"
    return "operator"


_load_api_keys()

_bearer_scheme = HTTPBearer(auto_error=False)


async def require_auth(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> None:
    """Verify Bearer token if MASCARADE_API_KEY is configured."""
    # Extract client IP address
    client_ip = request.client.host if request.client else None

    # Rate limiting check (applies to all requests, even without API keys)
    if credentials:
        # Use hash of API key as user identifier for rate limiting
        user_key = hashlib.sha256(credentials.credentials.strip().encode()).hexdigest()
        _rate_limiter.check_rate_limit(user_key=user_key, ip_address=client_ip)
    else:
        # Only IP-based rate limiting for requests without credentials
        _rate_limiter.check_rate_limit(ip_address=client_ip)

    if not _api_keys:
        return

    if credentials is None:
        raise HTTPException(status_code=401, detail="Missing token")

    if not is_valid_api_key(credentials.credentials):
        logger.warning("Invalid API key attempt")
        raise HTTPException(status_code=401, detail="Invalid token")

    role = _resolve_role(credentials.credentials.strip())
    if role is None:
        raise HTTPException(status_code=403, detail="Role non assigne pour ce token")

    required_role = _required_role_for_request(request.method.upper(), request.url.path)
    if _ROLE_RANK[role] < _ROLE_RANK[required_role]:
        raise HTTPException(status_code=403, detail="Permissions insuffisantes")


def add_api_key(key: str) -> None:
    """Add a new API key (for rotation) - thread-safe."""
    if not key or len(key.strip()) < _MIN_API_KEY_LENGTH:
        logger.warning("Attempt to add invalid API key (too short)")
        return

    with _keys_lock:
        if key.strip() not in _api_keys:
            _api_keys.add(key.strip())
            logger.info("API key added")


def remove_api_key(key: str) -> None:
    """Remove an API key - thread-safe."""
    if not key:
        return

    with _keys_lock:
        if key.strip() in _api_keys:
            _api_keys.discard(key.strip())
            logger.info("API key removed")


def get_active_api_keys() -> list[str]:
    """Get list of active API keys - thread-safe."""
    with _keys_lock:
        return list(_api_keys)


def get_rate_limit_metrics() -> dict[str, int]:
    """Get current rate limiter metrics.

    Returns:
        Dictionary with rate limiter metrics
    """
    return _rate_limiter.get_metrics()


def reset_rate_limit(user_key: str | None = None, ip_address: str | None = None) -> None:
    """Reset rate limit counters.

    Args:
        user_key: User key to reset (resets all if None and ip_address is None)
        ip_address: IP address to reset
    """
    _rate_limiter.reset(user_key=user_key, ip_address=ip_address)


# --- Database-backed authentication ---


def hash_api_key(key: str) -> str:
    """Hash an API key using SHA-256.

    Args:
        key: The API key to hash

    Returns:
        Hex-encoded SHA-256 hash of the key
    """
    return hashlib.sha256(key.encode()).hexdigest()


async def authenticate_user(api_key: str) -> User | None:
    """Authenticate a user via their API key from the database.

    Validates the API key against the database, checks expiration and active status,
    and returns the associated user if valid.

    Args:
        api_key: The API key to authenticate

    Returns:
        User object if authentication succeeds, None otherwise

    Note:
        This function also updates the last_used_at timestamp for the API key.
    """
    if not api_key or len(api_key.strip()) < 8:
        logger.warning("API key authentication failed: key too short")
        return None

    pool = get_db_pool()
    if pool is None:
        logger.error("Database pool not initialized")
        return None

    try:
        key_hash = hash_api_key(api_key.strip())

        async with pool.acquire() as conn:
            # Query for the API key and associated user/role in a single query
            # Include rate_limits from user (if set) and role (as fallback)
            row = await conn.fetchrow(
                """
                SELECT
                    ak.id as api_key_id,
                    ak.user_id,
                    ak.key_hash,
                    ak.key_prefix,
                    ak.name as api_key_name,
                    ak.is_active as api_key_active,
                    ak.created_at as api_key_created_at,
                    ak.expires_at,
                    ak.last_used_at,
                    u.id,
                    u.username,
                    u.email,
                    u.role_id,
                    u.is_active,
                    u.rate_limits,
                    u.created_at,
                    u.updated_at,
                    r.rate_limits as role_rate_limits
                FROM api_keys ak
                JOIN users u ON ak.user_id = u.id
                JOIN roles r ON u.role_id = r.id
                WHERE ak.key_hash = $1
                """,
                key_hash,
            )

            if row is None:
                logger.warning("API key authentication failed: key not found")
                return None

            # Check if API key is active
            if not row["api_key_active"]:
                logger.warning(
                    "API key authentication failed: key is inactive (user_id=%d)",
                    row["user_id"],
                )
                return None

            # Check if API key is expired
            if row["expires_at"] is not None and row["expires_at"] < datetime.now():
                logger.warning(
                    "API key authentication failed: key expired (user_id=%d)",
                    row["user_id"],
                )
                return None

            # Check if user is active
            if not row["is_active"]:
                logger.warning(
                    "API key authentication failed: user is inactive (user_id=%d)",
                    row["user_id"],
                )
                return None

            # Update last_used_at timestamp (fire and forget)
            await conn.execute(
                """
                UPDATE api_keys
                SET last_used_at = NOW()
                WHERE id = $1
                """,
                row["api_key_id"],
            )

            # Create User object from the row
            # Use user-specific rate_limits if set, otherwise fallback to role rate_limits
            effective_rate_limits = row["rate_limits"] or row["role_rate_limits"]

            user_record: UserRecord = {
                "id": row["id"],
                "username": row["username"],
                "email": row["email"],
                "role_id": row["role_id"],
                "is_active": row["is_active"],
                "rate_limits": effective_rate_limits,
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
            }

            user = User.from_record(user_record)
            logger.info(
                "User authenticated successfully: user_id=%d, username=%s",
                user.id,
                user.username,
            )
            return user

    except Exception as e:
        logger.error("Error authenticating user: %s", str(e), exc_info=True)
        return None


# --- FastAPI Dependencies for User Context & Permissions ---


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> User:
    """FastAPI dependency to get the current authenticated user.

    Extracts the Bearer token from the request, authenticates the user
    via the database, and returns the User object.

    Args:
        credentials: HTTP Authorization credentials from the request

    Returns:
        User object for the authenticated user

    Raises:
        HTTPException: 401 if token is missing or authentication fails
    """
    if credentials is None:
        raise HTTPException(status_code=401, detail="Missing authentication token")

    user = await authenticate_user(credentials.credentials)
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    return user


async def require_admin(
    current_user: User = Depends(get_current_user),
) -> User:
    """FastAPI dependency to require admin privileges.

    Checks if the current user has the admin role. Returns the user
    if they are an admin, otherwise raises a 403 Forbidden exception.

    Args:
        current_user: The authenticated user (from get_current_user dependency)

    Returns:
        User object if the user is an admin

    Raises:
        HTTPException: 403 if the user does not have admin privileges
    """
    pool = get_db_pool()
    if pool is None:
        logger.error("Database pool not initialized")
        raise HTTPException(status_code=500, detail="Database unavailable")

    try:
        async with pool.acquire() as conn:
            # Fetch the role name for the user's role_id
            role_row = await conn.fetchrow(
                """
                SELECT name
                FROM roles
                WHERE id = $1
                """,
                current_user.role_id,
            )

            if role_row is None:
                logger.error(
                    "Role not found for user_id=%d, role_id=%d",
                    current_user.id,
                    current_user.role_id,
                )
                raise HTTPException(status_code=403, detail="User role not found")

            # Check if the role is admin
            if role_row["name"] != "admin":
                logger.warning(
                    "Access denied: user_id=%d (role=%s) attempted admin-only operation",
                    current_user.id,
                    role_row["name"],
                )
                raise HTTPException(
                    status_code=403, detail="Admin privileges required"
                )

            logger.info(
                "Admin access granted: user_id=%d, username=%s",
                current_user.id,
                current_user.username,
            )
            return current_user

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error checking admin privileges: %s", str(e), exc_info=True)
        raise HTTPException(status_code=500, detail="Error checking permissions")


# --- Legacy API Key Migration ---


async def migrate_legacy_keys() -> dict:
    """Migrate legacy MASCARADE_API_KEY values to database as admin users.

    This function reads API keys from the MASCARADE_API_KEY environment variable
    (comma-separated) and creates admin users with API keys in the database.
    It tracks which keys have been migrated to prevent duplicates.

    Returns:
        Dictionary with migration results:
        - migrated: Number of keys successfully migrated
        - skipped: Number of keys already migrated
        - failed: Number of keys that failed to migrate
        - details: List of migration details per key

    Raises:
        RuntimeError: If database pool is not initialized
    """
    pool = get_db_pool()
    if pool is None:
        raise RuntimeError("Database pool not initialized. Call init_db_pool() first.")

    if not settings.mascarade_api_key:
        logger.info("No legacy API keys configured (MASCARADE_API_KEY is empty)")
        return {
            "migrated": 0,
            "skipped": 0,
            "failed": 0,
            "details": [],
        }

    # Parse legacy API keys
    legacy_keys = [
        key.strip()
        for key in settings.mascarade_api_key.split(",")
        if key.strip() and len(key.strip()) >= 8
    ]

    if not legacy_keys:
        logger.info("No valid legacy API keys found")
        return {
            "migrated": 0,
            "skipped": 0,
            "failed": 0,
            "details": [],
        }

    logger.info(f"Starting migration of {len(legacy_keys)} legacy API key(s)")

    results = {
        "migrated": 0,
        "skipped": 0,
        "failed": 0,
        "details": [],
    }

    async with pool.acquire() as conn:
        # Get admin role ID
        admin_role = await conn.fetchrow(
            """
            SELECT id FROM roles WHERE name = 'admin'
            """
        )

        if admin_role is None:
            logger.error("Admin role not found in database")
            raise RuntimeError("Admin role not found. Run migrations first.")

        admin_role_id = admin_role["id"]

        # Process each legacy key
        for idx, key in enumerate(legacy_keys, 1):
            key_prefix = key[:8] if len(key) >= 8 else key
            key_hash = hash_api_key(key)

            try:
                # Check if this key has already been migrated
                existing_migration = await conn.fetchrow(
                    """
                    SELECT id FROM legacy_migrations
                    WHERE migration_type = 'api_key' AND key_prefix = $1
                    """,
                    key_prefix,
                )

                if existing_migration is not None:
                    logger.info(
                        f"Legacy key {idx}/{len(legacy_keys)} already migrated (prefix: {key_prefix})"
                    )
                    results["skipped"] += 1
                    results["details"].append({
                        "key_prefix": key_prefix,
                        "status": "skipped",
                        "reason": "already_migrated",
                    })
                    continue

                # Check if this key already exists in api_keys table
                existing_key = await conn.fetchrow(
                    """
                    SELECT id, user_id FROM api_keys WHERE key_hash = $1
                    """,
                    key_hash,
                )

                if existing_key is not None:
                    logger.info(
                        f"Legacy key {idx}/{len(legacy_keys)} already exists in database (prefix: {key_prefix})"
                    )
                    results["skipped"] += 1
                    results["details"].append({
                        "key_prefix": key_prefix,
                        "status": "skipped",
                        "reason": "key_exists",
                    })
                    continue

                # Create migration transaction
                async with conn.transaction():
                    # Create a system admin user for this legacy key
                    username = f"legacy_admin_{idx}"
                    email = f"legacy_admin_{idx}@mascarade.local"

                    # Check if user already exists
                    existing_user = await conn.fetchrow(
                        """
                        SELECT id FROM users WHERE username = $1
                        """,
                        username,
                    )

                    if existing_user is not None:
                        user_id = existing_user["id"]
                        logger.info(
                            f"Using existing user {username} (id: {user_id}) for legacy key {idx}"
                        )
                    else:
                        # Create new user
                        user = await conn.fetchrow(
                            """
                            INSERT INTO users (username, email, role_id, is_active)
                            VALUES ($1, $2, $3, true)
                            RETURNING id
                            """,
                            username,
                            email,
                            admin_role_id,
                        )
                        user_id = user["id"]
                        logger.info(
                            f"Created user {username} (id: {user_id}) for legacy key {idx}"
                        )

                    # Create API key entry
                    await conn.execute(
                        """
                        INSERT INTO api_keys (user_id, key_hash, key_prefix, name, is_active)
                        VALUES ($1, $2, $3, $4, true)
                        """,
                        user_id,
                        key_hash,
                        key_prefix,
                        f"Legacy API Key {idx}",
                    )

                    # Track the migration
                    await conn.execute(
                        """
                        INSERT INTO legacy_migrations (migration_type, key_prefix, user_id, notes)
                        VALUES ($1, $2, $3, $4)
                        """,
                        "api_key",
                        key_prefix,
                        user_id,
                        f"Migrated from MASCARADE_API_KEY environment variable",
                    )

                    logger.info(
                        f"Successfully migrated legacy key {idx}/{len(legacy_keys)} (prefix: {key_prefix})"
                    )
                    results["migrated"] += 1
                    results["details"].append({
                        "key_prefix": key_prefix,
                        "status": "migrated",
                        "user_id": user_id,
                        "username": username,
                    })

            except Exception as e:
                logger.error(
                    f"Failed to migrate legacy key {idx}/{len(legacy_keys)} (prefix: {key_prefix}): {str(e)}",
                    exc_info=True,
                )
                results["failed"] += 1
                results["details"].append({
                    "key_prefix": key_prefix,
                    "status": "failed",
                    "error": str(e),
                })

    logger.info(
        f"Legacy key migration complete: {results['migrated']} migrated, "
        f"{results['skipped']} skipped, {results['failed']} failed"
    )

    return results
