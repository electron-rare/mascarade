"""Database migrations management."""

from __future__ import annotations

import logging
from pathlib import Path

import asyncpg

from mascarade.db.connection import get_db_pool

logger = logging.getLogger(__name__)

MIGRATIONS_DIR = Path(__file__).parent / "migrations"


async def _ensure_migrations_table(conn: asyncpg.Connection) -> None:
    """Ensure the migrations tracking table exists.

    Args:
        conn: Database connection
    """
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS schema_migrations (
            id SERIAL PRIMARY KEY,
            migration_name VARCHAR(255) UNIQUE NOT NULL,
            applied_at TIMESTAMP NOT NULL DEFAULT NOW()
        )
        """)


async def _get_applied_migrations(conn: asyncpg.Connection) -> list[str]:
    """Get list of already applied migration names.

    Args:
        conn: Database connection

    Returns:
        List of migration names that have been applied
    """
    rows = await conn.fetch(
        "SELECT migration_name FROM schema_migrations ORDER BY migration_name"
    )
    return [row["migration_name"] for row in rows]


async def _get_pending_migrations(applied: list[str]) -> list[Path]:
    """Get list of pending migration files.

    Args:
        applied: List of already applied migration names

    Returns:
        List of migration file paths that haven't been applied yet
    """
    if not MIGRATIONS_DIR.exists():
        return []

    all_migrations = sorted(MIGRATIONS_DIR.glob("*.sql"))
    pending = [m for m in all_migrations if m.name not in applied]
    return pending


async def _apply_migration(conn: asyncpg.Connection, migration_path: Path) -> None:
    """Apply a single migration file.

    Args:
        conn: Database connection
        migration_path: Path to the migration SQL file
    """
    migration_name = migration_path.name
    logger.info(f"Applying migration: {migration_name}")

    sql = migration_path.read_text()

    async with conn.transaction():
        await conn.execute(sql)
        await conn.execute(
            "INSERT INTO schema_migrations (migration_name) VALUES ($1)",
            migration_name,
        )

    logger.info(f"Migration applied: {migration_name}")


async def run_migrations() -> None:
    """Run all pending database migrations.

    This function:
    1. Creates the migrations tracking table if needed
    2. Checks which migrations have been applied
    3. Applies any pending migrations in order

    Raises:
        RuntimeError: If database pool is not initialized
    """
    pool = get_db_pool()
    if pool is None:
        raise RuntimeError("Database pool not initialized. Call init_db_pool() first.")

    async with pool.acquire() as conn:
        await _ensure_migrations_table(conn)
        applied = await _get_applied_migrations(conn)
        pending = await _get_pending_migrations(applied)

        if not pending:
            logger.info("No pending migrations")
            return

        logger.info(f"Found {len(pending)} pending migration(s)")

        for migration_path in pending:
            await _apply_migration(conn, migration_path)

        logger.info("All migrations applied successfully")


async def get_migration_status() -> dict:
    """Get current migration status.

    Returns:
        Dictionary with migration information:
        - applied: List of applied migration names
        - pending: List of pending migration names
        - total: Total number of migration files

    Raises:
        RuntimeError: If database pool is not initialized
    """
    pool = get_db_pool()
    if pool is None:
        raise RuntimeError("Database pool not initialized. Call init_db_pool() first.")

    async with pool.acquire() as conn:
        await _ensure_migrations_table(conn)
        applied = await _get_applied_migrations(conn)
        pending = await _get_pending_migrations(applied)

        return {
            "applied": applied,
            "pending": [p.name for p in pending],
            "total": len(applied) + len(pending),
        }
