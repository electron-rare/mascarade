"""Authentication — Bearer token with multi-key support and rotation."""

from __future__ import annotations

import hmac
import logging
import os
import threading
import time
from typing import Literal

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from mascarade.config import settings

logger = logging.getLogger("mascarade.auth")

_api_keys: set[str] = set()
_last_key_rotation = 0
_KEY_ROTATION_INTERVAL = 3600
_keys_lock = threading.Lock()
_MIN_API_KEY_LENGTH = 16
AuthRole = Literal["viewer", "operator", "admin"]
_ROLE_RANK: dict[AuthRole, int] = {"viewer": 1, "operator": 2, "admin": 3}


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
    normalized_path = (path or "").lower()

    if normalized_path.startswith("/api-keys"):
        return "admin"
    if normalized_path.startswith("/providers") and method != "GET":
        return "admin"
    if normalized_path.startswith("/mcp/industrial"):
        return "admin"
    if normalized_path.startswith("/cluster/forward/send"):
        return "admin"

    if method in {"GET", "HEAD", "OPTIONS"}:
        return "viewer"
    return "operator"


_load_api_keys()

_bearer_scheme = HTTPBearer(auto_error=False)


async def require_auth(
    request: Request,
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
