"""
Wizard Run Storage — task persistence and status tracking in PostgreSQL.

Handles CRUD operations for wizard runs, agent results, and status polling.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any, Optional
from uuid import uuid4

from sqlalchemy import Column, DateTime, Float, Integer, String, Text, create_engine
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.dialects.postgresql import JSON, UUID

from mascarade.agents.wizard_schemas import (
    WizardAgentResult,
    WizardRunResult,
    WizardRunStatus,
)

logger = logging.getLogger("mascarade.wizard")

Base = declarative_base()


class WizardRunRecord(Base):
    """SQLAlchemy model for persisting wizard runs."""

    __tablename__ = "wizard_runs"

    id = Column(String(256), primary_key=True, index=True)
    task_id = Column(String(256), index=True, unique=True)
    status = Column(String(50), default="pending", index=True)
    execution_mode = Column(String(50))
    total_duration_ms = Column(Float, default=0.0)
    total_cost_usd = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    completed_at = Column(DateTime, nullable=True)
    error_reason = Column(Text, nullable=True)
    results = Column(JSON, default={})  # Serialized WizardAgentResult list
    aggregated_analysis = Column(JSON, nullable=True)
    progress_percent = Column(Integer, default=0, index=True)


class WizardRunStorage:
    """Storage layer for wizard runs using PostgreSQL."""

    def __init__(self, database_url: str = "postgresql+asyncpg://mascarade:secret@localhost/mascarade") -> None:
        self.database_url = database_url
        self.engine = None
        self.session_factory = None

    async def initialize(self) -> None:
        """Initialize async database connection and create tables."""
        self.engine = create_async_engine(
            self.database_url,
            echo=False,
            pool_size=10,
            max_overflow=20,
        )
        self.session_factory = sessionmaker(
            self.engine, class_=AsyncSession, expire_on_commit=False
        )

        # Create tables if not exist
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        logger.info("Wizard storage initialized")

    async def close(self) -> None:
        """Close database connection."""
        if self.engine:
            await self.engine.dispose()

    async def create_run(
        self,
        task_id: str,
        execution_mode: str,
        initial_status: str = "pending",
    ) -> str:
        """Create a new wizard run record. Returns the run ID."""
        run_id = f"run-{uuid4().hex[:8]}"

        async with self.session_factory() as session:
            record = WizardRunRecord(
                id=run_id,
                task_id=task_id,
                status=initial_status,
                execution_mode=execution_mode,
                created_at=datetime.utcnow(),
                progress_percent=0,
            )
            session.add(record)
            await session.commit()

        logger.info(f"Created wizard run {run_id} for task {task_id}")
        return run_id

    async def get_run(self, task_id: str) -> Optional[dict]:
        """Retrieve a wizard run by task_id."""
        async with self.session_factory() as session:
            from sqlalchemy import select

            stmt = select(WizardRunRecord).where(WizardRunRecord.task_id == task_id)
            result = await session.execute(stmt)
            record = result.scalars().first()

            if not record:
                return None

            return self._record_to_dict(record)

    async def save_run(self, result: WizardRunResult) -> None:
        """Save or update a wizard run result."""
        async with self.session_factory() as session:
            from sqlalchemy import select

            stmt = select(WizardRunRecord).where(
                WizardRunRecord.task_id == result.task_id
            )
            record = await session.execute(stmt)
            existing = record.scalars().first()

            if existing:
                # Update existing
                existing.status = result.status.value
                existing.total_duration_ms = result.total_duration_ms
                existing.total_cost_usd = result.total_cost_usd
                existing.completed_at = result.completion_timestamp
                existing.error_reason = result.error_reason
                existing.progress_percent = 100 if result.status != "running" else existing.progress_percent
                existing.results = [r.model_dump(mode="json") for r in result.results]
                existing.aggregated_analysis = (
                    result.aggregated_analysis.model_dump(mode="json")
                    if result.aggregated_analysis
                    else None
                )
                await session.commit()
                logger.debug(f"Updated wizard run {result.task_id}")
            else:
                # Create new
                new_record = WizardRunRecord(
                    id=f"run-{uuid4().hex[:8]}",
                    task_id=result.task_id,
                    status=result.status.value,
                    execution_mode=result.execution_mode.value,
                    total_duration_ms=result.total_duration_ms,
                    total_cost_usd=result.total_cost_usd,
                    completed_at=result.completion_timestamp,
                    error_reason=result.error_reason,
                    results=[r.model_dump(mode="json") for r in result.results],
                    aggregated_analysis=(
                        result.aggregated_analysis.model_dump(mode="json")
                        if result.aggregated_analysis
                        else None
                    ),
                    progress_percent=100,
                )
                session.add(new_record)
                await session.commit()
                logger.debug(f"Saved new wizard run {result.task_id}")

    async def update_progress(self, task_id: str, progress_percent: int) -> None:
        """Update progress for a running execution."""
        async with self.session_factory() as session:
            from sqlalchemy import select, update

            stmt = (
                update(WizardRunRecord)
                .where(WizardRunRecord.task_id == task_id)
                .values(progress_percent=min(progress_percent, 99))
            )
            await session.execute(stmt)
            await session.commit()

    async def list_runs(
        self,
        status: Optional[str] = None,
        limit: int = 100,
    ) -> list[dict]:
        """List wizard runs, optionally filtered by status."""
        async with self.session_factory() as session:
            from sqlalchemy import select

            query = select(WizardRunRecord)
            if status:
                query = query.where(WizardRunRecord.status == status)
            query = query.order_by(WizardRunRecord.created_at.desc()).limit(limit)

            result = await session.execute(query)
            records = result.scalars().all()

            return [self._record_to_dict(r) for r in records]

    async def delete_run(self, task_id: str) -> bool:
        """Delete a wizard run. Returns True if deleted, False if not found."""
        async with self.session_factory() as session:
            from sqlalchemy import delete

            stmt = delete(WizardRunRecord).where(
                WizardRunRecord.task_id == task_id
            )
            result = await session.execute(stmt)
            await session.commit()

            deleted = result.rowcount > 0
            if deleted:
                logger.info(f"Deleted wizard run {task_id}")
            return deleted

    @staticmethod
    def _record_to_dict(record: WizardRunRecord) -> dict[str, Any]:
        """Convert database record to dict."""
        return {
            "id": record.id,
            "task_id": record.task_id,
            "status": record.status,
            "execution_mode": record.execution_mode,
            "total_duration_ms": record.total_duration_ms,
            "total_cost_usd": record.total_cost_usd,
            "created_at": record.created_at.isoformat() if record.created_at else None,
            "completed_at": record.completed_at.isoformat() if record.completed_at else None,
            "error_reason": record.error_reason,
            "progress_percent": record.progress_percent,
            "results": record.results or [],
            "aggregated_analysis": record.aggregated_analysis,
        }


# Singleton instance (lazy initialization)
_storage_instance: Optional[WizardRunStorage] = None


async def get_wizard_storage(
    database_url: Optional[str] = None,
) -> WizardRunStorage:
    """Get or create the wizard storage singleton."""
    global _storage_instance

    if _storage_instance is None:
        _storage_instance = WizardRunStorage(database_url or "postgresql+asyncpg://mascarade:secret@localhost/mascarade")
        await _storage_instance.initialize()

    return _storage_instance
