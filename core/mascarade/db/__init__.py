"""Database module for Mascarade."""

from mascarade.db.connection import get_db_pool, init_db_pool, close_db_pool

__all__ = ["get_db_pool", "init_db_pool", "close_db_pool"]
