"""Authentication — Bearer token with multi-key support and rotation."""

from __future__ import annotations

import hmac
import logging
import threading
import time

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from mascarade.config import settings

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
            logger.warning(
                "No MASCARADE_API_KEY configured — all protected routes are PUBLIC"
            )

        _last_key_rotation = time.time()


def _rotate_keys_if_needed() -> None:
    """Rotate keys if needed (every hour) - thread-safe."""
    global _last_key_rotation

    should_reload = False
    with _keys_lock:
        should_reload = time.time() - _last_key_rotation > _KEY_ROTATION_INTERVAL

    if should_reload:
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
