"""Database module for Mascarade."""

from __future__ import annotations

# Lazy imports to avoid dependency issues during import
from typing import TYPE_CHECKING

# Import models separately to avoid circular dependencies
from mascarade.db.models import (
    ApiKey,
    ApiKeyCreate,
    ApiKeyCreateResponse,
    ApiKeyRecord,
    Role,
    RoleName,
    RoleRecord,
    User,
    UserCreate,
    UserRecord,
    UserUpdate,
)

if TYPE_CHECKING:
    from asyncpg import Pool


def get_db_pool() -> Pool | None:
    """Get the database connection pool (lazy import)."""
    from mascarade.db.connection import get_db_pool as _get_db_pool

    return _get_db_pool()


async def init_db_pool() -> Pool:
    """Initialize the database connection pool (lazy import)."""
    from mascarade.db.connection import init_db_pool as _init_db_pool

    return await _init_db_pool()


async def close_db_pool() -> None:
    """Close the database connection pool (lazy import)."""
    from mascarade.db.connection import close_db_pool as _close_db_pool

    return await _close_db_pool()


__all__ = [
    "get_db_pool",
    "init_db_pool",
    "close_db_pool",
    "User",
    "UserRecord",
    "UserCreate",
    "UserUpdate",
    "Role",
    "RoleRecord",
    "RoleName",
    "ApiKey",
    "ApiKeyRecord",
    "ApiKeyCreate",
    "ApiKeyCreateResponse",
]
