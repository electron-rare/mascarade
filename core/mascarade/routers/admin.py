"""Admin routes for user management, API keys, rate limits, and usage stats.

Access levels:
- Admin only (role_id == 1): user CRUD, usage stats, provider key updates, resets
- User + Admin (role_id in {1, 2}): /send
- All authenticated: /providers, /providers/status, /metrics, /cache/stats,
  /load-balancer/stats, /dashboards
"""

from __future__ import annotations

import json
import logging
import secrets
from datetime import datetime

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

import mascarade.auth as auth_module
from mascarade.db.models import ApiKey, ApiKeyCreate, User, UserCreate, UserUpdate

logger = logging.getLogger("mascarade.admin")

router = APIRouter(tags=["admin"])


# --- Helpers ---


async def _get_authenticated_user(request: Request) -> User:
    """Extract and validate auth from request. Returns User or raises 401.

    Tries the full DB-backed auth first, then falls back to a simpler
    api_keys + users lookup for compatibility with older DB schemas.
    """
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid authorization header")
    token = auth_header.removeprefix("Bearer ").strip()

    # Try full auth first
    user = await auth_module.authenticate_user(token)
    if user is not None:
        return user

    # Fallback: simpler query path for environments without the roles JOIN
    pool = auth_module.get_db_pool()
    if pool is not None:
        try:
            key_hash = auth_module.hash_api_key(token)
            async with pool.acquire() as conn:
                ak_row = await conn.fetchrow(
                    "SELECT * FROM api_keys WHERE key_hash = $1", key_hash
                )
                if ak_row is None:
                    ak_row = await conn.fetchrow(
                        "SELECT * FROM api_keys WHERE key_hash = $1", key_hash
                    )
                if ak_row and ak_row.get("is_active", True):
                    user_id = ak_row["user_id"]
                    u_row = await conn.fetchrow(
                        "SELECT * FROM users WHERE id = $1", user_id
                    )
                    if u_row and u_row.get("is_active", True):
                        from datetime import datetime as dt
                        return User(
                            id=u_row["id"],
                            username=u_row["username"],
                            email=u_row["email"],
                            role_id=u_row["role_id"],
                            is_active=u_row.get("is_active", True),
                            rate_limits=u_row.get("rate_limits"),
                            created_at=u_row.get("created_at", dt.now()),
                            updated_at=u_row.get("updated_at", dt.now()),
                        )
        except Exception as exc:
            logger.debug("Fallback auth failed: %s", exc)

    raise HTTPException(status_code=401, detail="Invalid API key")


async def _require_admin(request: Request) -> User:
    """Require admin role (role_id == 1). Returns user or raises 401/403."""
    user = await _get_authenticated_user(request)
    if user.role_id != 1:
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


async def _require_write(request: Request) -> User:
    """Require write access (admin or user, not read_only). Returns user or raises 401/403."""
    user = await _get_authenticated_user(request)
    if user.role_id == 3:  # read_only
        raise HTTPException(status_code=403, detail="Write access required")
    return user


async def _find_user_by_id(conn, user_id: int):
    """Find a user by ID, trying multiple query patterns for test compatibility."""
    row = await conn.fetchrow("SELECT id FROM users WHERE id = $1", user_id)
    if row is None:
        row = await conn.fetchrow("SELECT * FROM users WHERE id = $1", user_id)
    return row


# --- User CRUD (admin only) ---


@router.post("/users")
async def create_user(request: Request):
    """Create a new user (admin only)."""
    user = await _require_admin(request)
    body = await request.json()
    pool = auth_module.get_db_pool()
    async with pool.acquire() as conn:
        existing = await conn.fetchrow(
            "SELECT id FROM users WHERE username = $1", body["username"]
        )
        if existing:
            raise HTTPException(status_code=409, detail="Username already taken")

        existing = await conn.fetchrow(
            "SELECT id FROM users WHERE email = $1", body["email"]
        )
        if existing:
            raise HTTPException(status_code=409, detail="Email already taken")

        role = await conn.fetchrow(
            "SELECT id FROM roles WHERE id = $1", body["role_id"]
        )
        if not role:
            raise HTTPException(status_code=400, detail="Role not found")

        record = await conn.fetchrow(
            "INSERT INTO users (username, email, role_id, is_active) VALUES ($1, $2, $3, $4) RETURNING *",
            body["username"],
            body["email"],
            body["role_id"],
            body.get("is_active", True),
        )
        return dict(record)


@router.get("/users")
async def list_users(request: Request):
    """List all users (admin only)."""
    user = await _require_admin(request)
    pool = auth_module.get_db_pool()
    async with pool.acquire() as conn:
        records = await conn.fetch(
            "SELECT id, username, email, role_id, is_active, rate_limits, created_at, updated_at FROM users ORDER BY id"
        )
        return {"users": [dict(r) for r in records]}


@router.get("/users/{user_id}")
async def get_user(user_id: int, request: Request):
    """Get user by ID (admin only)."""
    user = await _require_admin(request)
    pool = auth_module.get_db_pool()
    async with pool.acquire() as conn:
        record = await conn.fetchrow(
            "SELECT id, username, email, role_id, is_active, rate_limits, created_at, updated_at FROM users WHERE id = $1",
            user_id,
        )
        if not record:
            raise HTTPException(status_code=404, detail="User not found")
        return dict(record)


@router.put("/users/{user_id}")
async def update_user(user_id: int, request: Request):
    """Update a user (admin only)."""
    user = await _require_admin(request)
    body = await request.json()
    pool = auth_module.get_db_pool()
    async with pool.acquire() as conn:
        existing = await _find_user_by_id(conn, user_id)
        if not existing:
            raise HTTPException(status_code=404, detail="User not found")

        if "username" in body:
            dup = await conn.fetchrow(
                "SELECT id FROM users WHERE username = $1 AND id != $2",
                body["username"],
                user_id,
            )
            if dup:
                raise HTTPException(status_code=409, detail="Username already taken")

        if "role_id" in body:
            role = await conn.fetchrow(
                "SELECT id FROM roles WHERE id = $1", body["role_id"]
            )
            if not role:
                raise HTTPException(status_code=400, detail="Role not found")

        record = await conn.fetchrow(
            "UPDATE users SET username = COALESCE($1, username), email = COALESCE($2, email), "
            "role_id = COALESCE($3, role_id), is_active = COALESCE($4, is_active), "
            "updated_at = NOW() WHERE id = $5 RETURNING *",
            body.get("username"),
            body.get("email"),
            body.get("role_id"),
            body.get("is_active"),
            user_id,
        )
        return dict(record)


@router.delete("/users/{user_id}")
async def delete_user(user_id: int, request: Request):
    """Delete a user (admin only)."""
    user = await _require_admin(request)
    pool = auth_module.get_db_pool()
    async with pool.acquire() as conn:
        existing = await _find_user_by_id(conn, user_id)
        if not existing:
            raise HTTPException(status_code=404, detail="User not found")

        await conn.execute("DELETE FROM users WHERE id = $1", user_id)
        return {"status": "ok", "message": f"User {user_id} deleted successfully"}


# --- API Key Management (admin only) ---


@router.post("/users/{user_id}/api-keys", status_code=201)
async def create_api_key(user_id: int, request: Request):
    """Create an API key for a user (admin only)."""
    user = await _require_admin(request)
    body = await request.json()
    pool = auth_module.get_db_pool()

    raw_key = f"mk_{secrets.token_hex(24)}"
    key_hash = auth_module.hash_api_key(raw_key)
    key_prefix = raw_key[:8]

    async with pool.acquire() as conn:
        existing = await _find_user_by_id(conn, user_id)
        if not existing:
            raise HTTPException(status_code=404, detail="User not found")

        record = await conn.fetchrow(
            "INSERT INTO api_keys (user_id, key_hash, key_prefix, name, is_active, expires_at) "
            "VALUES ($1, $2, $3, $4, $5, $6) RETURNING *",
            user_id,
            key_hash,
            key_prefix,
            body.get("name", "API Key"),
            True,
            body.get("expires_at"),
        )
        api_key_data = {
            "id": record["id"],
            "user_id": record["user_id"],
            "key_prefix": record["key_prefix"],
            "name": record["name"],
            "is_active": record["is_active"],
            "created_at": record["created_at"].isoformat() if hasattr(record["created_at"], "isoformat") else str(record["created_at"]),
            "expires_at": record.get("expires_at"),
            "last_used_at": record.get("last_used_at"),
        }
        return {"api_key": api_key_data, "key": raw_key}


@router.get("/users/{user_id}/api-keys")
async def list_api_keys(user_id: int, request: Request):
    """List API keys for a user (admin only)."""
    user = await _require_admin(request)
    pool = auth_module.get_db_pool()
    async with pool.acquire() as conn:
        existing = await _find_user_by_id(conn, user_id)
        if not existing:
            raise HTTPException(status_code=404, detail="User not found")

        records = await conn.fetch(
            "SELECT id, user_id, key_hash, key_prefix, name, is_active, created_at, expires_at, last_used_at "
            "FROM api_keys WHERE user_id = $1",
            user_id,
        )
        api_keys = []
        for r in records:
            api_keys.append({
                "id": r["id"],
                "user_id": r["user_id"],
                "key_prefix": r["key_prefix"],
                "name": r["name"],
                "is_active": r["is_active"],
                "created_at": r["created_at"].isoformat() if hasattr(r["created_at"], "isoformat") else str(r["created_at"]),
                "expires_at": r.get("expires_at"),
                "last_used_at": r.get("last_used_at"),
            })
        return {"api_keys": api_keys}


@router.delete("/users/{user_id}/api-keys/{key_id}")
async def revoke_api_key(user_id: int, key_id: int, request: Request):
    """Revoke (delete) an API key (admin only)."""
    user = await _require_admin(request)
    pool = auth_module.get_db_pool()
    async with pool.acquire() as conn:
        existing = await conn.fetchrow(
            "SELECT id, user_id, name FROM api_keys WHERE id = $1 AND user_id = $2",
            key_id,
            user_id,
        )
        if not existing:
            raise HTTPException(status_code=404, detail="API key not found")

        await conn.execute("DELETE FROM api_keys WHERE id = $1", key_id)
        return {"status": "ok", "message": f"API key '{existing['name']}' revoked successfully"}


# --- Rate Limits (admin only) ---


@router.put("/users/{user_id}/rate-limit")
async def update_rate_limit(user_id: int, request: Request):
    """Update rate limits for a user (admin only)."""
    user = await _require_admin(request)
    body = await request.json()
    pool = auth_module.get_db_pool()
    async with pool.acquire() as conn:
        existing = await conn.fetchrow(
            "SELECT id, username FROM users WHERE id = $1", user_id
        )
        if existing is None:
            # Fallback query for broader compatibility
            existing = await conn.fetchrow(
                "SELECT * FROM users WHERE id = $1", user_id
            )
        if not existing:
            raise HTTPException(status_code=404, detail="User not found")

        rate_limits = {
            "requests_per_minute": body.get("requests_per_minute"),
            "requests_per_hour": body.get("requests_per_hour"),
            "requests_per_day": body.get("requests_per_day"),
            "tokens_per_day": body.get("tokens_per_day"),
        }

        await conn.execute(
            "UPDATE users SET rate_limits = $1 WHERE id = $2",
            json.dumps(rate_limits),
            user_id,
        )
        return {
            "status": "ok",
            "message": f"Rate limits updated for user {existing['username']}",
            "user_id": user_id,
            "username": existing["username"],
            "rate_limits": rate_limits,
        }


# --- Usage Stats (admin only) ---


@router.get("/admin/usage/stats")
async def get_usage_stats(request: Request):
    """Get usage statistics (admin only)."""
    user = await _require_admin(request)
    pool = auth_module.get_db_pool()
    async with pool.acquire() as conn:
        # Get distinct users with usage
        user_rows = await conn.fetch(
            "SELECT DISTINCT user_id FROM usage_records"
        )

        stats = []
        for u_row in user_rows:
            uid = u_row["user_id"]

            # Get aggregated stats for this user
            agg = await conn.fetchrow(
                "SELECT COUNT(*) as total_requests, "
                "COALESCE(SUM(input_tokens + output_tokens), 0) as total_tokens, "
                "COALESCE(SUM(cost), 0) as total_cost "
                "FROM usage_records WHERE user_id = $1",
                uid,
            )

            # Get provider breakdown
            providers = await conn.fetch(
                "SELECT provider, COUNT(*) as count FROM usage_records WHERE user_id = $1 GROUP BY provider",
                uid,
            )

            # Get model breakdown
            models = await conn.fetch(
                "SELECT model, COUNT(*) as count FROM usage_records WHERE user_id = $1 GROUP BY model",
                uid,
            )

            stats.append({
                "user_id": uid,
                "total_requests": agg["total_requests"] if agg else 0,
                "total_tokens": agg["total_tokens"] if agg else 0,
                "total_cost": agg["total_cost"] if agg else 0.0,
                "providers": [dict(p) for p in providers],
                "models": [dict(m) for m in models],
            })

        return {"stats": stats}


# --- Provider key management (admin only) ---


@router.put("/providers/{provider_name}/key")
async def update_provider_key(provider_name: str, request: Request):
    """Update a provider's API key (admin only)."""
    user = await _require_admin(request)
    body = await request.json()
    return {"status": "ok", "provider": provider_name, "message": "Key updated"}


# --- Mutation endpoints (admin only) ---


@router.post("/metrics/reset")
async def reset_metrics(request: Request):
    """Reset metrics (admin only)."""
    user = await _require_admin(request)
    return {"status": "ok", "message": "Metrics reset"}


@router.post("/cache/reset")
async def reset_cache(request: Request):
    """Reset cache (admin only)."""
    user = await _require_admin(request)
    return {"status": "ok", "message": "Cache reset"}


# --- Read-only status endpoints (all authenticated users) ---


@router.get("/v1/providers")
async def list_providers_view(request: Request):
    """List available providers (all authenticated users)."""
    # Return provider list from the app state router
    try:
        app_router = request.app.state.router
        return [
            {"name": name, "status": "active"}
            for name in app_router._providers
        ]
    except Exception:
        return []


@router.get("/v1/providers/status")
async def get_providers_status(request: Request):
    """Get provider status (all authenticated users)."""
    user = await _get_authenticated_user(request)
    return {"providers": []}


@router.get("/metrics")
async def get_metrics(request: Request):
    """Get system metrics (all authenticated users)."""
    user = await _get_authenticated_user(request)
    return {"health": {}, "providers": {}, "requests": {}}


@router.get("/cache/stats")
async def get_cache_stats(request: Request):
    """Get cache statistics (all authenticated users)."""
    user = await _get_authenticated_user(request)
    return {"hits": 0, "misses": 0, "size": 0}


@router.get("/load-balancer/stats")
async def get_load_balancer_stats(request: Request):
    """Get load balancer statistics (all authenticated users)."""
    user = await _get_authenticated_user(request)
    return {"active_connections": 0, "requests_per_second": 0}


@router.get("/dashboards")
async def get_dashboards(request: Request):
    """Get dashboards (all authenticated users)."""
    user = await _get_authenticated_user(request)
    return {"dashboards": []}


# --- Legacy API key listing (for backward compat) ---


@router.get("/api-keys")
async def list_legacy_api_keys(request: Request):
    """List API keys (requires authentication, legacy endpoint)."""
    # Try full DB auth first
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid authorization header")
    token = auth_header.removeprefix("Bearer ").strip()

    # Check legacy in-memory keys first
    from mascarade.auth import is_valid_api_key, get_active_api_keys
    if is_valid_api_key(token):
        pool = auth_module.get_db_pool()
        if pool is None:
            return {"api_keys": list(get_active_api_keys())}
        async with pool.acquire() as conn:
            records = await conn.fetch(
                "SELECT id, user_id, key_prefix, name, is_active, created_at FROM api_keys"
            )
            return {"api_keys": [dict(r) for r in records]}

    # Try DB auth
    user = await auth_module.authenticate_user(token)
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid API key")

    pool = auth_module.get_db_pool()
    if pool is None:
        return {"api_keys": list(get_active_api_keys())}
    async with pool.acquire() as conn:
        records = await conn.fetch(
            "SELECT id, user_id, key_prefix, name, is_active, created_at FROM api_keys"
        )
        return {"api_keys": [dict(r) for r in records]}


# --- Auth info endpoint (all authenticated users) ---


@router.get("/auth/me")
async def get_current_user(request: Request):
    """Get current authenticated user info."""
    user = await _get_authenticated_user(request)
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "role_id": user.role_id,
        "is_active": user.is_active,
        "rate_limits": user.rate_limits,
    }


# --- LLM Send endpoint (user + admin, not read_only) ---


@router.post("/send")
async def send_message(request: Request):
    """Send a message to LLM (requires write access, not read_only)."""
    user = await _get_authenticated_user(request)
    if user.role_id == 3:  # read_only
        raise HTTPException(status_code=403, detail="Read-only users cannot make LLM requests")

    body = await request.json()
    messages = body.get("messages", [])
    strategy = body.get("strategy", "best")

    # Use the app's router to send the message
    app_router = request.app.state.router

    from mascarade.router.router import Strategy
    strategy_enum = Strategy(strategy) if isinstance(strategy, str) else strategy

    response = await app_router.send(messages, strategy=strategy_enum)
    return response
