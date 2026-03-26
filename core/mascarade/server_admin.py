"""Admin protected routes: users, api-keys, auth, rate-limits, usage stats, providers, metrics, analytics, benchmarks."""

from __future__ import annotations

import asyncio
import json
import logging
import secrets
from datetime import datetime
from typing import TYPE_CHECKING

from fastapi import Depends, HTTPException, Query, Request
from fastapi.responses import Response

from mascarade.auth import (
    add_api_key,
    get_active_api_keys,
    get_current_user,
    remove_api_key,
    require_admin,
)
from mascarade.db.connection import get_db_pool
from mascarade.db.models import (
    ApiKey,
    ApiKeyCreate,
    ApiKeyCreateResponse,
    User,
    UserCreate,
    UserUpdate,
)
from mascarade.device_voice import DeviceVoiceService
from mascarade.provider_admin import (
    PROVIDER_REGISTRY,
    get_providers_status,
    update_provider_keys,
)
from mascarade.server_models import (
    APIKeyCreate as APIKeyCreateModel,
)
from mascarade.server_models import (
    APIKeyRemove,
    BenchmarkRunRequest,
    ComfyUIGenerateRequest,
    ComfyUIWorkflowRequest,
    CostAnalyticsResponse,
    ModelDeploymentWebhook,
    ProviderCostSummary,
    ProviderKeyUpdate,
    RateLimitUpdate,
    SendRequest,
)
from mascarade.usage_tracking import get_all_usage_stats

if TYPE_CHECKING:
    from fastapi import APIRouter, FastAPI

logger = logging.getLogger("mascarade.server")


def register_admin_routes(protected: APIRouter, app: FastAPI) -> None:
    """Register admin routes: users, api-keys, auth, rate-limits, usage, providers, metrics, analytics, benchmarks, comfyui, device voice."""

    from mascarade.server_protected import hash_api_key

    # --- API Key Management (legacy) ---

    @protected.post("/api-keys")
    async def create_api_key(req: APIKeyCreateModel):
        add_api_key(req.key)
        return {"status": "ok", "message": "API key added successfully"}

    @protected.post("/api-keys/remove")
    async def delete_api_key(req: APIKeyRemove):
        remove_api_key(req.key)
        return {"status": "ok", "message": "API key removed successfully"}

    @protected.get("/api-keys")
    async def list_api_keys():
        from mascarade.auth import mask_api_key

        keys = get_active_api_keys()
        return {"api_keys": [{"key": mask_api_key(k), "active": True} for k in keys]}

    @protected.get("/auth/me")
    async def get_me(current_user: User = Depends(get_current_user)):
        """Get current authenticated user information."""
        return {
            "id": current_user.id,
            "username": current_user.username,
            "email": current_user.email,
            "role_id": current_user.role_id,
            "is_active": current_user.is_active,
            "rate_limits": current_user.rate_limits,
        }

    # --- User Management ---

    @protected.get("/users")
    async def list_users(_: None = Depends(require_admin)):
        """List all users (admin only)."""
        pool = get_db_pool()
        if pool is None:
            raise HTTPException(status_code=500, detail="Database unavailable")

        try:
            async with pool.acquire() as conn:
                rows = await conn.fetch("""
                    SELECT id, username, email, role_id, is_active, created_at, updated_at
                    FROM users
                    ORDER BY created_at DESC
                    """)
                users = [User.from_record(dict(row)) for row in rows]
                return {"users": [user.model_dump() for user in users]}
        except Exception as e:
            logger.error("Error listing users: %s", str(e), exc_info=True)
            raise HTTPException(status_code=500, detail="Error listing users") from e

    @protected.post("/users")
    async def create_user(req: UserCreate, _: None = Depends(require_admin)):
        """Create a new user (admin only)."""
        pool = get_db_pool()
        if pool is None:
            raise HTTPException(status_code=500, detail="Database unavailable")

        try:
            async with pool.acquire() as conn:
                # Check if username already exists
                existing = await conn.fetchrow(
                    "SELECT id FROM users WHERE username = $1",
                    req.username,
                )
                if existing:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Username '{req.username}' already exists",
                    )

                # Check if email already exists
                existing_email = await conn.fetchrow(
                    "SELECT id FROM users WHERE email = $1",
                    req.email,
                )
                if existing_email:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Email '{req.email}' already exists",
                    )

                # Verify role exists
                role = await conn.fetchrow(
                    "SELECT id FROM roles WHERE id = $1",
                    req.role_id,
                )
                if not role:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Role ID {req.role_id} does not exist",
                    )

                # Create user
                row = await conn.fetchrow(
                    """
                    INSERT INTO users (username, email, role_id, is_active)
                    VALUES ($1, $2, $3, $4)
                    RETURNING id, username, email, role_id, is_active, created_at, updated_at
                    """,
                    req.username,
                    req.email,
                    req.role_id,
                    req.is_active,
                )

                user = User.from_record(dict(row))
                logger.info("User created: id=%d, username=%s", user.id, user.username)
                return user.model_dump()

        except HTTPException:
            raise
        except Exception as e:
            logger.error("Error creating user: %s", str(e), exc_info=True)
            raise HTTPException(status_code=500, detail="Error creating user") from e

    @protected.get("/users/{user_id}")
    async def get_user(user_id: int, _: None = Depends(require_admin)):
        """Get a user by ID (admin only)."""
        pool = get_db_pool()
        if pool is None:
            raise HTTPException(status_code=500, detail="Database unavailable")

        try:
            async with pool.acquire() as conn:
                row = await conn.fetchrow(
                    """
                    SELECT id, username, email, role_id, is_active, created_at, updated_at
                    FROM users
                    WHERE id = $1
                    """,
                    user_id,
                )

                if row is None:
                    raise HTTPException(
                        status_code=404,
                        detail=f"User with ID {user_id} not found",
                    )

                user = User.from_record(dict(row))
                return user.model_dump()

        except HTTPException:
            raise
        except Exception as e:
            logger.error("Error getting user: %s", str(e), exc_info=True)
            raise HTTPException(status_code=500, detail="Error getting user") from e

    @protected.put("/users/{user_id}")
    async def update_user(
        user_id: int,
        req: UserUpdate,
        _: None = Depends(require_admin),
    ):
        """Update a user (admin only)."""
        pool = get_db_pool()
        if pool is None:
            raise HTTPException(status_code=500, detail="Database unavailable")

        try:
            async with pool.acquire() as conn:
                # Check if user exists
                existing = await conn.fetchrow(
                    "SELECT id FROM users WHERE id = $1",
                    user_id,
                )
                if not existing:
                    raise HTTPException(
                        status_code=404,
                        detail=f"User with ID {user_id} not found",
                    )

                # Build update query dynamically based on provided fields
                updates = []
                params = []
                param_count = 1

                if req.username is not None:
                    # Check if new username is taken
                    username_check = await conn.fetchrow(
                        "SELECT id FROM users WHERE username = $1 AND id != $2",
                        req.username,
                        user_id,
                    )
                    if username_check:
                        raise HTTPException(
                            status_code=400,
                            detail=f"Username '{req.username}' already exists",
                        )
                    updates.append(f"username = ${param_count}")
                    params.append(req.username)
                    param_count += 1

                if req.email is not None:
                    # Check if new email is taken
                    email_check = await conn.fetchrow(
                        "SELECT id FROM users WHERE email = $1 AND id != $2",
                        req.email,
                        user_id,
                    )
                    if email_check:
                        raise HTTPException(
                            status_code=400,
                            detail=f"Email '{req.email}' already exists",
                        )
                    updates.append(f"email = ${param_count}")
                    params.append(req.email)
                    param_count += 1

                if req.role_id is not None:
                    # Verify role exists
                    role = await conn.fetchrow(
                        "SELECT id FROM roles WHERE id = $1",
                        req.role_id,
                    )
                    if not role:
                        raise HTTPException(
                            status_code=400,
                            detail=f"Role ID {req.role_id} does not exist",
                        )
                    updates.append(f"role_id = ${param_count}")
                    params.append(req.role_id)
                    param_count += 1

                if req.is_active is not None:
                    updates.append(f"is_active = ${param_count}")
                    params.append(req.is_active)
                    param_count += 1

                if not updates:
                    raise HTTPException(
                        status_code=400,
                        detail="No fields to update",
                    )

                # Always update updated_at
                updates.append("updated_at = NOW()")
                params.append(user_id)

                query = f"""
                    UPDATE users
                    SET {', '.join(updates)}
                    WHERE id = ${param_count}
                    RETURNING id, username, email, role_id, is_active, created_at, updated_at
                """

                row = await conn.fetchrow(query, *params)
                user = User.from_record(dict(row))
                logger.info("User updated: id=%d, username=%s", user.id, user.username)
                return user.model_dump()

        except HTTPException:
            raise
        except Exception as e:
            logger.error("Error updating user: %s", str(e), exc_info=True)
            raise HTTPException(status_code=500, detail="Error updating user") from e

    @protected.delete("/users/{user_id}")
    async def delete_user(user_id: int, _: None = Depends(require_admin)):
        """Delete a user (admin only)."""
        pool = get_db_pool()
        if pool is None:
            raise HTTPException(status_code=500, detail="Database unavailable")

        try:
            async with pool.acquire() as conn:
                # Check if user exists
                existing = await conn.fetchrow(
                    "SELECT id FROM users WHERE id = $1",
                    user_id,
                )
                if not existing:
                    raise HTTPException(
                        status_code=404,
                        detail=f"User with ID {user_id} not found",
                    )

                # Delete the user (cascading deletes will handle api_keys)
                await conn.execute(
                    "DELETE FROM users WHERE id = $1",
                    user_id,
                )

                logger.info("User deleted: id=%d", user_id)
                return {"status": "ok", "message": f"User {user_id} deleted successfully"}

        except HTTPException:
            raise
        except Exception as e:
            logger.error("Error deleting user: %s", str(e), exc_info=True)
            raise HTTPException(status_code=500, detail="Error deleting user") from e

    @protected.put("/users/{user_id}/rate-limit")
    async def update_user_rate_limit(
        user_id: int,
        req: RateLimitUpdate,
        _: None = Depends(require_admin),
    ):
        """Update rate limit for a user (admin only)."""
        pool = get_db_pool()
        if pool is None:
            raise HTTPException(status_code=500, detail="Database unavailable")

        try:
            async with pool.acquire() as conn:
                # Check if user exists
                existing = await conn.fetchrow(
                    "SELECT id, username FROM users WHERE id = $1",
                    user_id,
                )
                if not existing:
                    raise HTTPException(
                        status_code=404,
                        detail=f"User with ID {user_id} not found",
                    )

                # Build rate limits JSON
                rate_limits = {
                    "requests_per_minute": req.requests_per_minute,
                    "requests_per_hour": req.requests_per_hour,
                    "requests_per_day": req.requests_per_day,
                    "tokens_per_day": req.tokens_per_day,
                }

                # Update user's rate limits
                await conn.execute(
                    """
                    UPDATE users
                    SET rate_limits = $1::jsonb, updated_at = NOW()
                    WHERE id = $2
                    """,
                    json.dumps(rate_limits),
                    user_id,
                )

                logger.info(
                    "Rate limits updated for user: id=%d, username=%s",
                    user_id,
                    existing["username"],
                )
                return {
                    "status": "ok",
                    "message": f"Rate limits updated for user {user_id}",
                    "rate_limits": rate_limits,
                }

        except HTTPException:
            raise
        except Exception as e:
            logger.error("Error updating rate limits: %s", str(e), exc_info=True)
            raise HTTPException(status_code=500, detail="Error updating rate limits") from e

    # --- API Key Management (DB-backed) ---

    @protected.post("/users/{user_id}/api-keys", status_code=201)
    async def create_user_api_key(
        user_id: int,
        req: ApiKeyCreate,
        _: None = Depends(require_admin),
    ):
        """Create a new API key for a user (admin only)."""
        pool = get_db_pool()
        if pool is None:
            raise HTTPException(status_code=500, detail="Database unavailable")

        try:
            async with pool.acquire() as conn:
                # Check if user exists
                user_row = await conn.fetchrow(
                    "SELECT id FROM users WHERE id = $1",
                    user_id,
                )
                if not user_row:
                    raise HTTPException(
                        status_code=404,
                        detail=f"User with ID {user_id} not found",
                    )

                # Generate a secure random API key (32 bytes = 64 hex chars)
                api_key = secrets.token_hex(32)
                key_hash = hash_api_key(api_key)
                key_prefix = api_key[:8]

                # Insert the API key into the database
                row = await conn.fetchrow(
                    """
                    INSERT INTO api_keys (user_id, key_hash, key_prefix, name, is_active, expires_at)
                    VALUES ($1, $2, $3, $4, $5, $6)
                    RETURNING id, user_id, key_hash, key_prefix, name, is_active, created_at, expires_at, last_used_at
                    """,
                    user_id,
                    key_hash,
                    key_prefix,
                    req.name,
                    True,  # is_active
                    req.expires_at,
                )

                api_key_obj = ApiKey.from_record(dict(row))
                logger.info(
                    "API key created: id=%d, user_id=%d, name=%s",
                    api_key_obj.id,
                    user_id,
                    req.name,
                )

                # Return the API key object with the actual key (shown only once)
                return ApiKeyCreateResponse(
                    api_key=api_key_obj,
                    key=api_key,
                ).model_dump()

        except HTTPException:
            raise
        except Exception as e:
            logger.error("Error creating API key: %s", str(e), exc_info=True)
            raise HTTPException(status_code=500, detail="Error creating API key") from e

    @protected.get("/users/{user_id}/api-keys")
    async def list_user_api_keys(
        user_id: int,
        _: None = Depends(require_admin),
    ):
        """List all API keys for a user (admin only)."""
        pool = get_db_pool()
        if pool is None:
            raise HTTPException(status_code=500, detail="Database unavailable")

        try:
            async with pool.acquire() as conn:
                # Check if user exists
                user_row = await conn.fetchrow(
                    "SELECT id FROM users WHERE id = $1",
                    user_id,
                )
                if not user_row:
                    raise HTTPException(
                        status_code=404,
                        detail=f"User with ID {user_id} not found",
                    )

                # Fetch all API keys for the user
                rows = await conn.fetch(
                    """
                    SELECT id, user_id, key_hash, key_prefix, name, is_active, created_at, expires_at, last_used_at
                    FROM api_keys
                    WHERE user_id = $1
                    ORDER BY created_at DESC
                    """,
                    user_id,
                )

                api_keys = [ApiKey.from_record(dict(row)) for row in rows]
                return {"api_keys": [key.model_dump() for key in api_keys]}

        except HTTPException:
            raise
        except Exception as e:
            logger.error("Error listing API keys: %s", str(e), exc_info=True)
            raise HTTPException(status_code=500, detail="Error listing API keys") from e

    @protected.delete("/users/{user_id}/api-keys/{key_id}")
    async def revoke_user_api_key(
        user_id: int,
        key_id: int,
        _: None = Depends(require_admin),
    ):
        """Revoke (delete) an API key for a user (admin only)."""
        pool = get_db_pool()
        if pool is None:
            raise HTTPException(status_code=500, detail="Database unavailable")

        try:
            async with pool.acquire() as conn:
                # Check if API key exists and belongs to the user
                key_row = await conn.fetchrow(
                    """
                    SELECT id, user_id, name
                    FROM api_keys
                    WHERE id = $1 AND user_id = $2
                    """,
                    key_id,
                    user_id,
                )

                if not key_row:
                    raise HTTPException(
                        status_code=404,
                        detail=f"API key with ID {key_id} not found for user {user_id}",
                    )

                # Delete the API key
                await conn.execute(
                    "DELETE FROM api_keys WHERE id = $1",
                    key_id,
                )

                logger.info(
                    "API key revoked: id=%d, user_id=%d, name=%s",
                    key_id,
                    user_id,
                    key_row["name"],
                )
                return {
                    "status": "ok",
                    "message": f"API key {key_id} revoked successfully",
                }

        except HTTPException:
            raise
        except Exception as e:
            logger.error("Error revoking API key: %s", str(e), exc_info=True)
            raise HTTPException(status_code=500, detail="Error revoking API key") from e

    # --- Usage Statistics ---

    @protected.get("/admin/usage/stats")
    async def get_usage_statistics(
        start_date: datetime | None = Query(
            default=None, description="Start date for filtering (ISO format)"
        ),
        end_date: datetime | None = Query(
            default=None, description="End date for filtering (ISO format)"
        ),
        _: None = Depends(require_admin),
    ):
        """Get aggregated usage statistics for all users (admin only)."""
        try:
            stats = await get_all_usage_stats(start_date=start_date, end_date=end_date)
            return {"stats": [stat.model_dump() for stat in stats]}
        except RuntimeError as e:
            raise HTTPException(status_code=500, detail=str(e)) from e
        except Exception as e:
            logger.error("Error fetching usage statistics: %s", str(e), exc_info=True)
            raise HTTPException(status_code=500, detail="Error fetching usage statistics") from e

    # --- LLM ---

    @protected.post("/send")
    async def send(req: SendRequest):
        messages = [m.model_dump() for m in req.messages]
        try:
            response = await app.state.router.send(
                messages,
                strategy=req.strategy,
                routing_policy=req.routing_policy,
                provider=req.provider,
                model=req.model,
                system=req.system,
                response_format=req.response_format,
                temperature=req.temperature,
                max_tokens=req.max_tokens,
            )
        except ValueError as exc:
            logger.warning("Send request rejected: %s", exc)
            raise HTTPException(status_code=400, detail="Invalid request parameters") from exc
        return {
            "content": response.content,
            "model": response.model,
            "provider": response.provider,
            "usage": response.usage,
        }

    @protected.get("/providers")
    async def list_providers():
        return {"providers": app.state.router.available_providers}

    @protected.get("/providers/status")
    async def providers_status():
        return {"providers": get_providers_status(app.state.router)}

    @protected.put("/providers/{name}/key")
    async def update_provider(name: str, req: ProviderKeyUpdate):
        if name not in PROVIDER_REGISTRY:
            raise HTTPException(status_code=404, detail=f"Unknown provider: {name}")
        result = update_provider_keys(
            name,
            req.keys,
            app.state.router,
            persist_env=False,
        )
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
        return result

    @protected.get("/providers/bedrock/models")
    async def bedrock_models():
        """List Bedrock models including fine-tuned custom models."""
        provider = app.state.router._providers.get("bedrock")
        if not provider:
            raise HTTPException(status_code=503, detail="Bedrock provider not configured")
        return {
            "default": provider.default_model,
            "available": provider.available_models(),
            "custom": provider.custom_models(),
        }

    @protected.get("/providers/bedrock/finetune-jobs")
    async def bedrock_finetune_jobs():
        """Check status of Bedrock fine-tuning jobs."""
        provider = app.state.router._providers.get("bedrock")
        if not provider:
            raise HTTPException(status_code=503, detail="Bedrock provider not configured")
        jobs = await provider.finetune_jobs()
        return {"jobs": jobs}

    # --- Metrics ---

    @protected.get("/router/metrics")
    async def metrics_summary():
        return await app.state.router.metrics_summary()

    @protected.get("/router/metrics/{provider}")
    async def metrics_provider(provider: str):
        stats = app.state.router.provider_metrics(provider)
        if not stats:
            raise HTTPException(status_code=404, detail="Provider has no metrics yet")
        return stats

    @protected.post("/router/metrics/reset")
    async def metrics_reset():
        await app.state.router.reset_metrics()
        return {"status": "ok"}

    # --- Cache ---

    @protected.get("/cache/stats")
    async def cache_stats():
        return app.state.router.cache.get_stats()

    @protected.post("/cache/reset")
    async def cache_reset():
        app.state.router.cache.clear()
        return {"status": "ok"}

    # --- Load Balancer ---

    @protected.get("/load-balancer/stats")
    async def lb_stats():
        return app.state.router.load_balancer.get_load_stats()

    @protected.post("/load-balancer/reset")
    async def lb_reset():
        app.state.router.load_balancer.reset_stats()
        return {"status": "ok"}

    # --- Fallback ---

    @protected.get("/fallback/stats")
    async def fallback_stats():
        return app.state.router.fallback.get_failure_stats()

    @protected.post("/fallback/reset")
    async def fallback_reset():
        app.state.router.fallback.reset()
        return {"status": "ok"}

    # --- Analytics ---

    @protected.get("/v1/analytics/cost")
    async def get_cost_analytics(
        limit: int = Query(default=1000, ge=1, le=5000),
        run_id: str | None = Query(default=None, max_length=64),
    ):
        """
        Get cost analytics aggregated from trace events.

        Args:
            limit: Maximum number of events to analyze (default: 1000)
            run_id: Optional run ID to filter by

        Returns:
            Cost analytics with totals and breakdowns by provider/model
        """
        from mascarade.analytics import get_cost_calculator

        # Get recent trace events with token usage
        events = app.state.trace_buffer.recent(
            limit=limit,
            run_id=run_id,
        )

        # Filter events that have token usage
        events_with_usage = [e for e in events if e.token_usage]

        # Aggregate by (provider, model)
        aggregates: dict[tuple[str, str], dict] = {}
        cost_calc = get_cost_calculator()

        for event in events_with_usage:
            if not event.provider or not event.model:
                continue

            key = (event.provider, event.model)
            if key not in aggregates:
                aggregates[key] = {
                    "provider": event.provider,
                    "model": event.model,
                    "total_cost": 0.0,
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "request_count": 0,
                }

            input_tokens = event.token_usage.get("input_tokens", 0) or event.token_usage.get(
                "prompt_tokens", 0
            )
            output_tokens = event.token_usage.get("output_tokens", 0) or event.token_usage.get(
                "completion_tokens", 0
            )

            # Calculate cost for this event
            cost = cost_calc.calculate_cost(
                provider=event.provider,
                model=event.model,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
            )

            aggregates[key]["total_cost"] += cost
            aggregates[key]["input_tokens"] += input_tokens
            aggregates[key]["output_tokens"] += output_tokens
            aggregates[key]["request_count"] += 1

        # Calculate totals
        total_cost = sum(agg["total_cost"] for agg in aggregates.values())
        total_requests = sum(agg["request_count"] for agg in aggregates.values())
        total_input_tokens = sum(agg["input_tokens"] for agg in aggregates.values())
        total_output_tokens = sum(agg["output_tokens"] for agg in aggregates.values())

        # Convert to response models
        by_provider = [ProviderCostSummary(**agg) for agg in aggregates.values()]

        return CostAnalyticsResponse(
            total_cost=total_cost,
            total_requests=total_requests,
            total_input_tokens=total_input_tokens,
            total_output_tokens=total_output_tokens,
            by_provider=by_provider,
        )

    # --- Benchmark Analytics ---

    @protected.get("/v1/analytics/benchmarks")
    async def get_benchmark_results(
        domain: str | None = Query(default=None, max_length=50),
        limit: int = Query(default=10, ge=1, le=100),
        order_by: str = Query(default="quality_score", max_length=50),
    ):
        """
        Get benchmark results leaderboard.

        Query parameters:
        - domain: Filter by domain (optional)
        - limit: Maximum number of results (default: 10, max: 100)
        - order_by: Column to order by (default: quality_score, options: quality_score, latency_p50, cost)

        Returns:
            List of benchmark results with provider, model, domain, and performance metrics
        """
        from mascarade.benchmarks.storage import BenchmarkStorage

        # Validate order_by parameter
        valid_order_by = {"quality_score", "latency_p50", "latency_p95", "cost"}
        if order_by not in valid_order_by:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid order_by parameter. Must be one of: {', '.join(valid_order_by)}",
            )

        storage = BenchmarkStorage()

        try:
            results = storage.query_leaderboard(
                domain=domain,
                limit=limit,
                order_by=order_by,
            )

            return {
                "results": results,
                "count": len(results),
                "filters": {
                    "domain": domain,
                    "limit": limit,
                    "order_by": order_by,
                },
            }
        except Exception as e:
            logger.exception("Failed to query benchmark results")
            raise HTTPException(status_code=500, detail=str(e)) from e

    @protected.post("/v1/benchmarks/run", status_code=202)
    async def trigger_benchmark_run(req: BenchmarkRunRequest):
        """
        Trigger an on-demand benchmark run.

        Request body:
        - domain: Domain to benchmark (optional, runs all domains if not specified)
        - providers: List of providers to test (optional, tests all providers if not specified)
        - difficulty: Difficulty level to test (optional)
        - limit: Maximum number of prompts per provider (optional)

        Returns:
            202 Accepted with run_id for tracking the benchmark execution
        """
        from mascarade.benchmarks.suite import BenchmarkSuite

        # Initialize benchmark suite with router from app state
        suite = BenchmarkSuite(router=app.state.router)

        # Generate run_id for tracking
        run_id = suite._generate_run_id()

        # Define the background benchmark task
        async def run_benchmark_task():
            """Background task to execute the benchmark."""
            try:
                if req.domain:
                    # Run domain-specific benchmark
                    logger.info(
                        "Starting domain-specific benchmark (domain=%s, run_id=%s)",
                        req.domain,
                        run_id,
                    )
                    run = await suite.run_domain_benchmark(
                        domain=req.domain,
                        providers=req.providers,
                        difficulty=req.difficulty,
                        limit=req.limit,
                    )
                else:
                    # Run full suite benchmark
                    logger.info(
                        "Starting full suite benchmark (run_id=%s)",
                        run_id,
                    )
                    run = await suite.run_full_suite(
                        providers=req.providers,
                        difficulty=req.difficulty,
                        limit=req.limit,
                    )

                logger.info(
                    "Benchmark completed (run_id=%s, total=%d, successful=%d, failed=%d)",
                    run.run_id,
                    run.total_benchmarks,
                    run.successful_benchmarks,
                    run.failed_benchmarks,
                )

                # Store results in ClickHouse
                from mascarade.benchmarks.storage import BenchmarkStorage

                storage = BenchmarkStorage()
                for result in run.results:
                    try:
                        storage.write_result(result)
                    except Exception as e:
                        logger.warning(
                            "Failed to store benchmark result for %s/%s: %s",
                            result.provider,
                            result.model,
                            e,
                        )

            except Exception as e:
                logger.exception("Benchmark run failed (run_id=%s): %s", run_id, e)

        # Create background task (fire and forget)
        asyncio.create_task(run_benchmark_task())

        return {
            "status": "accepted",
            "run_id": run_id,
            "message": "Benchmark run started in background",
            "filters": {
                "domain": req.domain,
                "providers": req.providers,
                "difficulty": req.difficulty,
                "limit": req.limit,
            },
        }

    @protected.post("/v1/benchmarks/webhook/deployment", status_code=200)
    async def handle_model_deployment_webhook(webhook: ModelDeploymentWebhook):
        """
        Handle model deployment webhook to trigger automatic benchmarks.

        This endpoint is triggered when a new fine-tuned model is deployed
        and automatically runs benchmarks to evaluate its performance.

        Request body:
        - provider: Provider name (required)
        - model: Model identifier (required)
        - event_type: Type of deployment event (default: "deployment")
        - domain: Domain to benchmark (optional)
        - limit: Maximum number of prompts to test (optional)
        - background: Run benchmark in background (default: true)
        - metadata: Additional event metadata (optional)

        Returns:
            Webhook processing result with trigger status
        """
        from mascarade.benchmarks.triggers import BenchmarkTriggerError

        try:
            # Get trigger instance from app state
            trigger = app.state.benchmark_trigger

            # Process webhook
            result = await trigger.handle_webhook(
                payload={
                    "provider": webhook.provider,
                    "model": webhook.model,
                    "event_type": webhook.event_type,
                    "domain": webhook.domain,
                    "limit": webhook.limit,
                    "background": webhook.background,
                    "metadata": webhook.metadata,
                }
            )

            logger.info(
                "Model deployment webhook processed: %s/%s (status=%s)",
                webhook.provider,
                webhook.model,
                result.get("trigger_result", {}).get("status", "unknown"),
            )

            return result

        except BenchmarkTriggerError as exc:
            logger.error("Webhook processing failed: %s", exc)
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:
            logger.exception("Unexpected error processing webhook")
            raise HTTPException(status_code=500, detail="Internal server error") from exc

    # --- ComfyUI ---

    from mascarade.integrations.comfyui import ComfyUIClient  # noqa: E402

    def _require_comfyui_local() -> ComfyUIClient:
        if app.state.comfyui is None:
            raise HTTPException(status_code=503, detail="ComfyUI non configure (COMFYUI_URL manquant)")
        return app.state.comfyui

    @protected.get("/comfyui/status")
    async def comfyui_status():
        client = _require_comfyui_local()
        return await client.get_system_stats()

    @protected.get("/comfyui/queue")
    async def comfyui_queue():
        client = _require_comfyui_local()
        return await client.get_queue_status()

    @protected.get("/comfyui/models/{model_type}")
    async def comfyui_models(model_type: str = "checkpoints"):
        client = _require_comfyui_local()
        models = await client.list_models(model_type)
        return {"models": models, "type": model_type}

    @protected.post("/comfyui/generate")
    async def comfyui_generate(req: ComfyUIGenerateRequest):
        client = _require_comfyui_local()
        result = await client.generate_image(
            req.prompt,
            req.negative_prompt,
            checkpoint=req.checkpoint,
            width=req.width,
            height=req.height,
            steps=req.steps,
            cfg=req.cfg,
            seed=req.seed,
        )
        return result

    @protected.post("/comfyui/workflow")
    async def comfyui_workflow(req: ComfyUIWorkflowRequest):
        if not req.workflow or not isinstance(req.workflow, dict):
            raise HTTPException(status_code=400, detail="Workflow must be a non-empty object")
        if len(str(req.workflow)) > 500_000:
            raise HTTPException(status_code=400, detail="Workflow payload too large")
        client = _require_comfyui_local()
        prompt_id = await client.queue_prompt(req.workflow)
        return {"prompt_id": prompt_id}

    @protected.get("/comfyui/history/{prompt_id}")
    async def comfyui_history(prompt_id: str):
        client = _require_comfyui_local()
        return await client.get_history(prompt_id)

    @protected.get("/comfyui/image")
    async def comfyui_image(filename: str, subfolder: str = "", type: str = "output"):
        client = _require_comfyui_local()
        try:
            image_data = await client.get_image(filename, subfolder, type)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid image path parameters") from None
        return Response(content=image_data, media_type="image/png")

    @protected.post("/comfyui/interrupt")
    async def comfyui_interrupt():
        client = _require_comfyui_local()
        await client.interrupt()
        return {"status": "ok"}

    # --- Device voice ---

    @protected.get("/device/v1/voice/replies/{reply_id}.wav")
    async def device_voice_reply_audio(reply_id: str, request: Request):
        from fastapi.responses import Response as _Response

        service: DeviceVoiceService = request.app.state.device_voice
        audio = service.get_reply_audio(reply_id)
        if audio is None:
            raise HTTPException(status_code=404, detail="Reply audio not found or expired")
        return _Response(content=audio.payload, media_type=audio.content_type)
