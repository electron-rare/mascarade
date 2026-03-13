"""Authentication — Bearer token with multi-key support and rotation."""

from __future__ import annotations

import hashlib
import hmac
import logging
import threading
import time
from datetime import datetime

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from mascarade.config import settings
from mascarade.db.connection import get_db_pool
from mascarade.db.models import ApiKeyRecord, RoleRecord, User, UserRecord

logger = logging.getLogger("mascarade.auth")

_api_keys: set[str] = set()
_last_key_rotation = 0
_KEY_ROTATION_INTERVAL = 3600
_keys_lock = threading.Lock()


def _load_api_keys() -> None:
    """Load API keys from configuration (thread-safe)."""
    global _api_keys, _last_key_rotation

    with _keys_lock:
        if settings.mascarade_api_key:
            new_keys = {
                key.strip()
                for key in settings.mascarade_api_key.split(",")
                if key.strip() and len(key.strip()) >= 8
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
    if not key or len(key.strip()) < 8:
        return False

    _rotate_keys_if_needed()
    candidate = key.strip()
    with _keys_lock:
        return any(_timing_safe_compare(candidate, k) for k in _api_keys)


_load_api_keys()

_bearer_scheme = HTTPBearer(auto_error=False)


async def require_auth(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> None:
    """Verify Bearer token if MASCARADE_API_KEY is configured."""
    if not _api_keys:
        return

    if credentials is None:
        raise HTTPException(status_code=401, detail="Missing token")

    if not is_valid_api_key(credentials.credentials):
        logger.warning("Invalid API key attempt")
        raise HTTPException(status_code=401, detail="Invalid token")


def add_api_key(key: str) -> None:
    """Add a new API key (for rotation) - thread-safe."""
    if not key or len(key.strip()) < 8:
        logger.warning(f"Attempt to add invalid API key (too short): {key[:10]}...")
        return

    with _keys_lock:
        if key.strip() not in _api_keys:
            _api_keys.add(key.strip())
            logger.info(f"API key added: {key[:5]}...{key[-3:]}")


def remove_api_key(key: str) -> None:
    """Remove an API key - thread-safe."""
    if not key:
        return

    with _keys_lock:
        if key.strip() in _api_keys:
            _api_keys.discard(key.strip())
            logger.info(f"API key removed: {key[:5]}...{key[-3:]}")


def get_active_api_keys() -> list[str]:
    """Get list of active API keys - thread-safe."""
    with _keys_lock:
        return list(_api_keys)


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
                    u.created_at,
                    u.updated_at
                FROM api_keys ak
                JOIN users u ON ak.user_id = u.id
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
            user_record: UserRecord = {
                "id": row["id"],
                "username": row["username"],
                "email": row["email"],
                "role_id": row["role_id"],
                "is_active": row["is_active"],
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
