"""Database connection pool management using asyncpg."""

from __future__ import annotations

from typing import Optional

import asyncpg

from mascarade.config import settings

_pool: Optional[asyncpg.Pool] = None


async def init_db_pool() -> asyncpg.Pool:
    """Initialize the database connection pool.

    Returns:
        asyncpg.Pool: The initialized connection pool
    """
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(
            dsn=settings.database_url,
            min_size=2,
            max_size=10,
            command_timeout=60,
        )
    return _pool


async def close_db_pool() -> None:
    """Close the database connection pool."""
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


def get_db_pool() -> Optional[asyncpg.Pool]:
    """Get the current database connection pool.

    Returns:
        Optional[asyncpg.Pool]: The connection pool if initialized, None otherwise
    """
    return _pool
