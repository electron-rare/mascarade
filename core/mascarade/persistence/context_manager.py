"""Advanced Context Persistence Manager for Mascarade."""

from __future__ import annotations

import json
import logging
from typing import Any, TypeVar

import redis.asyncio as redis
from pydantic import BaseModel

from mascarade.orchestrator.context import OrchestrationContext

logger = logging.getLogger("mascarade.persistence.context")

T = TypeVar("T", bound="BaseContext")


class BaseContext(BaseModel):
    """Base class for all context types with persistence support."""

    context_id: str
    context_type: str
    created_at: str
    updated_at: str
    metadata: dict[str, Any] = {}

    class Config:
        json_schema_extra = {
            "examples": [
                {
                    "context_id": "ctx_12345",
                    "context_type": "orchestration",
                    "created_at": "2024-01-01T00:00:00Z",
                    "updated_at": "2024-01-01T00:00:00Z",
                    "metadata": {},
                }
            ]
        }


class PersistentOrchestrationContext(BaseContext):
    """Persistent version of OrchestrationContext with additional metadata."""

    prompt: str
    agent_names: list[str] = []
    mode: str | None = None
    current_input: str | None = None
    initial_prompt: str | None = None
    execution_history: list[dict[str, Any]] = []

    @classmethod
    def from_orchestration_context(
        cls,
        context: OrchestrationContext,
        context_id: str,
        created_at: str,
        updated_at: str,
    ) -> PersistentOrchestrationContext:
        """Create persistent context from orchestration context."""
        return cls(
            context_id=context_id,
            context_type="orchestration",
            created_at=created_at,
            updated_at=updated_at,
            prompt=context.prompt,
            agent_names=context.agent_names,
            mode=context.mode,
            current_input=context.current_input,
            initial_prompt=context.initial_prompt,
            execution_history=[],
        )

    def to_orchestration_context(self) -> OrchestrationContext:
        """Convert back to OrchestrationContext."""
        return OrchestrationContext(
            prompt=self.prompt,
            agent_names=self.agent_names,
            mode=self.mode,
            current_input=self.current_input,
            initial_prompt=self.initial_prompt,
        )


class ContextPersistenceManager:
    """Multi-backend context persistence manager."""

    def __init__(
        self, redis_url: str = "redis://localhost:6379", default_ttl: int = 86400
    ) -> None:
        """Initialize context persistence manager.

        Args:
            redis_url: Redis connection URL
            default_ttl: Default time-to-live in seconds (24h)
        """
        self.redis_url = redis_url
        self.default_ttl = default_ttl
        self._redis: redis.Redis | None = None

    async def connect(self) -> None:
        """Establish Redis connection."""
        if self._redis is None:
            self._redis = await redis.from_url(
                self.redis_url,
                encoding="utf-8",
                decode_responses=True,
            )
            logger.info("Connected to Redis for context persistence")

    async def disconnect(self) -> None:
        """Close Redis connection."""
        if self._redis is not None:
            await self._redis.aclose()
            self._redis = None
            logger.info("Disconnected from Redis")

    def _get_key(self, context_id: str) -> str:
        """Generate Redis key for context storage."""
        return f"context:{context_id}"

    async def save_context(self, context: BaseContext, ttl: int | None = None) -> str:
        """Save context to persistence layer.

        Args:
            context: Context to save
            ttl: Optional TTL override in seconds

        Returns:
            context_id of the saved context
        """
        if self._redis is None:
            await self.connect()

        key = self._get_key(context.context_id)
        value = context.json()
        ttl_seconds = ttl or self.default_ttl

        await self._redis.set(key, value, ex=ttl_seconds)
        logger.info(f"Saved context {context.context_id} (TTL: {ttl_seconds}s)")

        return context.context_id

    async def get_context(self, context_id: str, context_class: type[T]) -> T | None:
        """Retrieve context from persistence layer.

        Args:
            context_id: ID of context to retrieve
            context_class: Expected context class for deserialization

        Returns:
            Context object or None if not found
        """
        if self._redis is None:
            await self.connect()

        key = self._get_key(context_id)
        value = await self._redis.get(key)

        if value is None:
            logger.warning(f"Context {context_id} not found")
            return None

        try:
            context = context_class.parse_raw(value)
            logger.info(f"Retrieved context {context_id}")
            return context
        except Exception as e:
            logger.error(f"Failed to deserialize context {context_id}: {e}")
            return None

    async def update_context(
        self, context: BaseContext, update_data: dict[str, Any]
    ) -> bool:
        """Update existing context.

        Args:
            context: Context to update
            update_data: Dictionary of fields to update

        Returns:
            True if update succeeded, False if context not found
        """
        if self._redis is None:
            await self.connect()

        key = self._get_key(context.context_id)

        # Check if context exists
        if await self._redis.exists(key) == 0:
            return False

        # Update context
        for field, value in update_data.items():
            if hasattr(context, field):
                setattr(context, field, value)

        # Update timestamp
        from datetime import datetime

        context.updated_at = datetime.utcnow().isoformat() + "Z"

        # Save updated context
        await self._redis.set(key, context.json(), ex=self.default_ttl)
        logger.info(f"Updated context {context.context_id}")

        return True

    async def delete_context(self, context_id: str) -> bool:
        """Delete context from persistence layer.

        Args:
            context_id: ID of context to delete

        Returns:
            True if deletion succeeded, False if context not found
        """
        if self._redis is None:
            await self.connect()

        key = self._get_key(context_id)
        result = await self._redis.delete(key)

        if result > 0:
            logger.info(f"Deleted context {context_id}")
            return True

        logger.warning(f"Context {context_id} not found for deletion")
        return False

    async def list_contexts(self, context_type: str | None = None) -> list[str]:
        """List all context IDs, optionally filtered by type.

        Args:
            context_type: Optional type filter

        Returns:
            List of context IDs
        """
        if self._redis is None:
            await self.connect()

        pattern = "context:*"
        context_ids = []

        async for key in self._redis.scan_iter(match=pattern):
            context_id = key.replace("context:", "")

            if context_type is None:
                context_ids.append(context_id)
            else:
                # Check context type
                context_data = await self._redis.get(key)
                if context_data:
                    try:
                        context_json = json.loads(context_data)
                        if context_json.get("context_type") == context_type:
                            context_ids.append(context_id)
                    except (json.JSONDecodeError, KeyError, TypeError):
                        continue

        return sorted(context_ids)

    async def get_context_metadata(self, context_id: str) -> dict[str, Any] | None:
        """Get context metadata without loading full context.

        Args:
            context_id: ID of context

        Returns:
            Dictionary with metadata or None if not found
        """
        if self._redis is None:
            await self.connect()

        key = self._get_key(context_id)
        value = await self._redis.get(key)

        if value is None:
            return None

        try:
            context_data = json.loads(value)
            return {
                "context_id": context_data["context_id"],
                "context_type": context_data["context_type"],
                "created_at": context_data["created_at"],
                "updated_at": context_data["updated_at"],
                "metadata": context_data.get("metadata", {}),
            }
        except Exception as e:
            logger.error(f"Failed to get metadata for context {context_id}: {e}")
            return None

    async def clear_all_contexts(self) -> int:
        """Clear all contexts (for testing/debugging).

        Returns:
            Number of contexts deleted
        """
        if self._redis is None:
            await self.connect()

        keys = []
        async for key in self._redis.scan_iter(match="context:*"):
            keys.append(key)

        if keys:
            result = await self._redis.delete(*keys)
            logger.info(f"Cleared {result} contexts")
            return result

        return 0


# Utility functions for common context operations


async def save_orchestration_context(
    manager: ContextPersistenceManager,
    context: OrchestrationContext,
    context_id: str,
    ttl: int | None = None,
) -> str:
    """Utility function to save orchestration context."""
    from datetime import datetime

    persistent_context = PersistentOrchestrationContext.from_orchestration_context(
        context=context,
        context_id=context_id,
        created_at=datetime.utcnow().isoformat() + "Z",
        updated_at=datetime.utcnow().isoformat() + "Z",
    )

    return await manager.save_context(persistent_context, ttl)


async def load_orchestration_context(
    manager: ContextPersistenceManager, context_id: str
) -> OrchestrationContext | None:
    """Utility function to load orchestration context."""
    context = await manager.get_context(context_id, PersistentOrchestrationContext)
    return context.to_orchestration_context() if context else None
