"""Usage tracking module for per-user token and cost tracking."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import TypedDict

from pydantic import BaseModel

from mascarade.db.connection import get_db_pool

logger = logging.getLogger("mascarade.usage_tracking")


# --- Database Record Types (TypedDict for asyncpg records) ---


class UsageRecord(TypedDict):
    """Database record for usage_records table."""

    id: int
    user_id: int
    provider: str
    model: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    cost: float
    created_at: datetime


# --- Pydantic Models (API validation & serialization) ---


class Usage(BaseModel):
    """Usage model for API responses."""

    id: int
    user_id: int
    provider: str
    model: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    cost: float
    created_at: datetime

    @classmethod
    def from_record(cls, record: UsageRecord) -> Usage:
        """Create Usage from database record."""
        return cls(
            id=record["id"],
            user_id=record["user_id"],
            provider=record["provider"],
            model=record["model"],
            input_tokens=record["input_tokens"],
            output_tokens=record["output_tokens"],
            total_tokens=record["total_tokens"],
            cost=record["cost"],
            created_at=record["created_at"],
        )


class UsageStats(BaseModel):
    """Aggregated usage statistics for a user."""

    user_id: int
    total_requests: int
    total_tokens: int
    total_input_tokens: int
    total_output_tokens: int
    total_cost: float
    providers: dict[str, int]  # provider -> request count
    models: dict[str, int]  # model -> request count


# --- Usage Tracking Functions ---


async def track_usage(
    user_id: int,
    provider: str,
    model: str,
    usage: dict[str, int],
    cost: float,
) -> None:
    """Track LLM usage for a user.

    Args:
        user_id: The ID of the user making the request
        provider: The LLM provider used (e.g., "claude", "openai")
        model: The model used (e.g., "claude-3-5-sonnet-20241022")
        usage: Usage dictionary with token counts (input_tokens, output_tokens, total_tokens)
        cost: Calculated cost for this request in USD

    Raises:
        RuntimeError: If database pool is not initialized
    """
    pool = get_db_pool()
    if pool is None:
        logger.warning(
            "Database pool not initialized, skipping usage tracking for user %s",
            user_id,
        )
        return

    input_tokens = usage.get("input_tokens", 0)
    output_tokens = usage.get("output_tokens", 0)
    total_tokens = usage.get("total_tokens", 0) or (input_tokens + output_tokens)

    try:
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO usage_records
                (user_id, provider, model, input_tokens, output_tokens, total_tokens, cost)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                """,
                user_id,
                provider,
                model,
                input_tokens,
                output_tokens,
                total_tokens,
                cost,
            )
        logger.debug(
            "Tracked usage for user %s: %s/%s - %d tokens (cost: $%.6f)",
            user_id,
            provider,
            model,
            total_tokens,
            cost,
        )
    except Exception as e:
        logger.error("Failed to track usage for user %s: %s", user_id, e)
        # Don't raise - usage tracking should not break LLM requests


async def get_user_usage_stats(
    user_id: int,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
) -> UsageStats:
    """Get aggregated usage statistics for a user.

    Args:
        user_id: The ID of the user
        start_date: Optional start date for filtering (inclusive)
        end_date: Optional end date for filtering (inclusive)

    Returns:
        UsageStats: Aggregated statistics

    Raises:
        RuntimeError: If database pool is not initialized
    """
    pool = get_db_pool()
    if pool is None:
        raise RuntimeError("Database pool not initialized")

    # Build query with optional date filters
    query = """
        SELECT
            COUNT(*) as total_requests,
            COALESCE(SUM(total_tokens), 0) as total_tokens,
            COALESCE(SUM(input_tokens), 0) as total_input_tokens,
            COALESCE(SUM(output_tokens), 0) as total_output_tokens,
            COALESCE(SUM(cost), 0) as total_cost
        FROM usage_records
        WHERE user_id = $1
    """
    params = [user_id]

    if start_date:
        query += " AND created_at >= $2"
        params.append(start_date)
        if end_date:
            query += " AND created_at <= $3"
            params.append(end_date)
    elif end_date:
        query += " AND created_at <= $2"
        params.append(end_date)

    async with pool.acquire() as conn:
        row = await conn.fetchrow(query, *params)

        # Get provider breakdown
        provider_query = """
            SELECT provider, COUNT(*) as count
            FROM usage_records
            WHERE user_id = $1
        """
        if start_date:
            provider_query += " AND created_at >= $2"
            if end_date:
                provider_query += " AND created_at <= $3"
        elif end_date:
            provider_query += " AND created_at <= $2"
        provider_query += " GROUP BY provider"

        provider_rows = await conn.fetch(provider_query, *params)
        providers = {row["provider"]: row["count"] for row in provider_rows}

        # Get model breakdown
        model_query = """
            SELECT model, COUNT(*) as count
            FROM usage_records
            WHERE user_id = $1
        """
        if start_date:
            model_query += " AND created_at >= $2"
            if end_date:
                model_query += " AND created_at <= $3"
        elif end_date:
            model_query += " AND created_at <= $2"
        model_query += " GROUP BY model"

        model_rows = await conn.fetch(model_query, *params)
        models = {row["model"]: row["count"] for row in model_rows}

    return UsageStats(
        user_id=user_id,
        total_requests=row["total_requests"] or 0,
        total_tokens=row["total_tokens"] or 0,
        total_input_tokens=row["total_input_tokens"] or 0,
        total_output_tokens=row["total_output_tokens"] or 0,
        total_cost=float(row["total_cost"] or 0),
        providers=providers,
        models=models,
    )


async def get_all_usage_stats(
    start_date: datetime | None = None,
    end_date: datetime | None = None,
) -> list[UsageStats]:
    """Get aggregated usage statistics for all users.

    Args:
        start_date: Optional start date for filtering (inclusive)
        end_date: Optional end date for filtering (inclusive)

    Returns:
        list[UsageStats]: Statistics for each user

    Raises:
        RuntimeError: If database pool is not initialized
    """
    pool = get_db_pool()
    if pool is None:
        raise RuntimeError("Database pool not initialized")

    # Get all unique user IDs
    query = "SELECT DISTINCT user_id FROM usage_records"
    params = []

    if start_date:
        query += " WHERE created_at >= $1"
        params.append(start_date)
        if end_date:
            query += " AND created_at <= $2"
            params.append(end_date)
    elif end_date:
        query += " WHERE created_at <= $1"
        params.append(end_date)

    async with pool.acquire() as conn:
        rows = await conn.fetch(query, *params)

    user_ids = [row["user_id"] for row in rows]

    # Get stats for each user
    stats = []
    for user_id in user_ids:
        user_stats = await get_user_usage_stats(user_id, start_date, end_date)
        stats.append(user_stats)

    return stats
