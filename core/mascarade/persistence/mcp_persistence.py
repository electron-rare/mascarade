"""MCP (Model Context Protocol) with Persistence Support."""

from __future__ import annotations

import logging
from typing import Any

import redis.asyncio as redis
from pydantic import BaseModel

from mascarade.router.providers.interop import ModelContextProtocol

logger = logging.getLogger("mascarade.persistence.mcp")


class PersistentModelContext(BaseModel):
    """Persistent version of MCP context with additional metadata."""

    context_id: str
    protocol: str = "MCP/1.0"
    model_id: str
    session_id: str
    parameters: dict[str, Any]
    metadata: dict[str, Any] = {}
    created_at: str
    updated_at: str
    persistence_flags: dict[str, bool] = {
        "persist_across_sessions": False,
        "shareable": False,
        "versioned": False,
    }

    class Config:
        json_schema_extra = {
            "examples": [
                {
                    "context_id": "mcp_ctx_12345",
                    "protocol": "MCP/1.0",
                    "model_id": "gpt-4",
                    "session_id": "session_789",
                    "parameters": {"temperature": 0.7},
                    "metadata": {"user_id": "user_123"},
                    "created_at": "2024-01-01T00:00:00Z",
                    "updated_at": "2024-01-01T00:00:00Z",
                    "persistence_flags": {
                        "persist_across_sessions": True,
                        "shareable": False,
                        "versioned": True,
                    },
                }
            ]
        }

    @classmethod
    def from_mcp_context(
        cls,
        mcp_context: dict[str, Any],
        context_id: str,
        created_at: str,
        updated_at: str,
    ) -> PersistentModelContext:
        """Create persistent context from MCP context."""
        return cls(
            context_id=context_id,
            protocol=mcp_context["protocol"],
            model_id=mcp_context["model_id"],
            session_id=mcp_context["session_id"],
            parameters=mcp_context["parameters"],
            metadata=mcp_context.get("metadata", {}),
            created_at=created_at,
            updated_at=updated_at,
        )

    def to_mcp_context(self) -> dict[str, Any]:
        """Convert back to standard MCP context."""
        return ModelContextProtocol.create_context(
            model_id=self.model_id,
            session_id=self.session_id,
            parameters=self.parameters,
            metadata=self.metadata,
        )


class MCPPersistenceManager:
    """Persistence manager for Model Context Protocol contexts."""

    def __init__(self, redis_url: str = "redis://localhost:6379", default_ttl: int = 86400) -> None:
        """Initialize MCP persistence manager.

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
            logger.info("Connected to Redis for MCP persistence")

    async def disconnect(self) -> None:
        """Close Redis connection."""
        if self._redis is not None:
            await self._redis.aclose()
            self._redis = None
            logger.info("Disconnected from Redis")

    # --- Context Persistence ---

    def _get_context_key(self, context_id: str) -> str:
        """Generate Redis key for MCP context."""
        return f"mcp:context:{context_id}"

    def _get_session_contexts_key(self, session_id: str) -> str:
        """Generate Redis key for session's contexts."""
        return f"mcp:session:{session_id}:contexts"

    def _get_model_contexts_key(self, model_id: str) -> str:
        """Generate Redis key for model's contexts."""
        return f"mcp:model:{model_id}:contexts"

    async def save_context(self, context: PersistentModelContext, ttl: int | None = None) -> str:
        """Save MCP context to persistence layer.

        Args:
            context: Context to save
            ttl: Optional TTL override in seconds

        Returns:
            context_id of the saved context
        """
        if self._redis is None:
            await self.connect()

        context_key = self._get_context_key(context.context_id)
        value = context.json()
        ttl_seconds = ttl or self.default_ttl

        # Use pipeline for atomic operations
        pipeline = self._redis.pipeline()

        # Save main context
        pipeline.set(context_key, value, ex=ttl_seconds)

        # Index by session if not persist_across_sessions
        if not context.persistence_flags.get("persist_across_sessions", False):
            session_key = self._get_session_contexts_key(context.session_id)
            pipeline.sadd(session_key, context.context_id)
            pipeline.expire(session_key, ttl_seconds)

        # Index by model
        model_key = self._get_model_contexts_key(context.model_id)
        pipeline.sadd(model_key, context.context_id)
        pipeline.expire(model_key, ttl_seconds)

        await pipeline.execute()

        logger.info(
            f"Saved MCP context {context.context_id} "
            f"(model: {context.model_id}, session: {context.session_id})"
        )

        return context.context_id

    async def get_context(self, context_id: str) -> PersistentModelContext | None:
        """Retrieve MCP context from persistence layer.

        Args:
            context_id: ID of context to retrieve

        Returns:
            PersistentModelContext object or None if not found
        """
        if self._redis is None:
            await self.connect()

        key = self._get_context_key(context_id)
        value = await self._redis.get(key)

        if value is None:
            logger.warning(f"MCP context {context_id} not found")
            return None

        try:
            context = PersistentModelContext.parse_raw(value)
            logger.info(f"Retrieved MCP context {context_id}")
            return context
        except Exception as e:
            logger.error(f"Failed to deserialize MCP context {context_id}: {e}")
            return None

    async def update_context(self, context_id: str, update_data: dict[str, Any]) -> bool:
        """Update existing MCP context.

        Args:
            context_id: ID of context to update
            update_data: Dictionary of fields to update

        Returns:
            True if update succeeded, False if context not found
        """
        if self._redis is None:
            await self.connect()

        # Retrieve existing context
        existing_context = await self.get_context(context_id)
        if existing_context is None:
            return False

        # Update fields
        for field, value in update_data.items():
            if hasattr(existing_context, field):
                setattr(existing_context, field, value)

        # Update timestamp
        from datetime import datetime

        existing_context.updated_at = datetime.utcnow().isoformat() + "Z"

        # Save updated context
        await self.save_context(existing_context)
        logger.info(f"Updated MCP context {context_id}")

        return True

    async def delete_context(self, context_id: str) -> bool:
        """Delete MCP context from persistence layer.

        Args:
            context_id: ID of context to delete

        Returns:
            True if deletion succeeded, False if context not found
        """
        if self._redis is None:
            await self.connect()

        # Get context first to clean up indexes
        context = await self.get_context(context_id)
        if context is None:
            return False

        context_key = self._get_context_key(context_id)

        # Use pipeline for atomic cleanup
        pipeline = self._redis.pipeline()

        # Delete main context
        pipeline.delete(context_key)

        # Clean up session index
        if not context.persistence_flags.get("persist_across_sessions", False):
            session_key = self._get_session_contexts_key(context.session_id)
            pipeline.srem(session_key, context_id)

        # Clean up model index
        model_key = self._get_model_contexts_key(context.model_id)
        pipeline.srem(model_key, context_id)

        await pipeline.execute()

        logger.info(f"Deleted MCP context {context_id}")
        return True

    # --- Session Management ---

    async def get_session_contexts(self, session_id: str) -> list[PersistentModelContext]:
        """Get all contexts for a session.

        Args:
            session_id: ID of session

        Returns:
            List of PersistentModelContext objects
        """
        if self._redis is None:
            await self.connect()

        session_key = self._get_session_contexts_key(session_id)
        context_ids = await self._redis.smembers(session_key)

        contexts = []
        for ctx_id in context_ids:
            context = await self.get_context(ctx_id)
            if context:
                contexts.append(context)

        logger.info(f"Retrieved {len(contexts)} contexts for session {session_id}")
        return contexts

    async def get_model_contexts(self, model_id: str) -> list[PersistentModelContext]:
        """Get all contexts for a model.

        Args:
            model_id: ID of model

        Returns:
            List of PersistentModelContext objects
        """
        if self._redis is None:
            await self.connect()

        model_key = self._get_model_contexts_key(model_id)
        context_ids = await self._redis.smembers(model_key)

        contexts = []
        for ctx_id in context_ids:
            context = await self.get_context(ctx_id)
            if context:
                contexts.append(context)

        logger.info(f"Retrieved {len(contexts)} contexts for model {model_id}")
        return contexts

    # --- Advanced MCP Features ---

    async def create_persistent_context(
        self,
        mcp_context: dict[str, Any],
        persistence_flags: dict[str, bool] = None,
        ttl: int | None = None,
    ) -> str:
        """Create a new persistent MCP context.

        Args:
            mcp_context: Standard MCP context dictionary
            persistence_flags: Persistence configuration
            ttl: Optional TTL override

        Returns:
            context_id of the created context
        """
        import uuid
        from datetime import datetime

        now = datetime.utcnow().isoformat() + "Z"

        persistent_context = PersistentModelContext(
            context_id=f"mcp_{uuid.uuid4().hex[:8]}",
            protocol=mcp_context["protocol"],
            model_id=mcp_context["model_id"],
            session_id=mcp_context["session_id"],
            parameters=mcp_context["parameters"],
            metadata=mcp_context.get("metadata", {}),
            created_at=now,
            updated_at=now,
            persistence_flags=persistence_flags or {},
        )

        return await self.save_context(persistent_context, ttl)

    async def search_contexts(
        self,
        model_id: str | None = None,
        session_id: str | None = None,
        persist_across_sessions: bool | None = None,
        limit: int = 10,
    ) -> list[PersistentModelContext]:
        """Search MCP contexts with advanced filters.

        Args:
            model_id: Optional model filter
            session_id: Optional session filter
            persist_across_sessions: Optional persistence flag filter
            limit: Maximum number of results

        Returns:
            List of matching PersistentModelContext objects
        """
        if self._redis is None:
            await self.connect()

        pattern = "mcp:context:*"
        results = []

        async for key in self._redis.scan_iter(match=pattern):
            context_id = key.replace("mcp:context:", "")
            context = await self.get_context(context_id)

            if context is None:
                continue

            # Apply filters
            if model_id and context.model_id != model_id:
                continue

            if session_id and context.session_id != session_id:
                continue

            if (
                persist_across_sessions is not None
                and context.persistence_flags.get("persist_across_sessions")
                != persist_across_sessions
            ):
                continue

            results.append(context)

            if len(results) >= limit:
                break

        return results

    async def get_context_stats(self) -> dict[str, Any]:
        """Get statistics about stored MCP contexts.

        Returns:
            Dictionary with usage statistics
        """
        if self._redis is None:
            await self.connect()

        # Count total contexts
        total_contexts = 0
        async for key in self._redis.scan_iter(match="mcp:context:*"):
            total_contexts += 1

        # Count by model
        model_stats = {}
        async for key in self._redis.scan_iter(match="mcp:model:*"):
            model_id = key.replace("mcp:model:", "").replace(":contexts", "")
            count = await self._redis.scard(key)
            model_stats[model_id] = count

        # Count by session
        session_stats = {}
        async for key in self._redis.scan_iter(match="mcp:session:*"):
            session_id = key.replace("mcp:session:", "").replace(":contexts", "")
            count = await self._redis.scard(key)
            session_stats[session_id] = count

        return {
            "total_contexts": total_contexts,
            "models": model_stats,
            "sessions": session_stats,
            "model_count": len(model_stats),
            "session_count": len(session_stats),
        }

    # --- Context Versioning ---

    async def version_context(self, context_id: str, version_notes: str = "") -> str | None:
        """Create a new version of an existing context.

        Args:
            context_id: ID of context to version
            version_notes: Notes about this version

        Returns:
            context_id of the new version or None if original not found
        """
        if self._redis is None:
            await self.connect()

        # Get original context
        original = await self.get_context(context_id)
        if original is None:
            return None

        # Check if versioning is enabled
        if not original.persistence_flags.get("versioned", False):
            logger.warning(f"Context {context_id} is not versioned")
            return None

        import uuid
        from datetime import datetime

        # Create new version
        new_context_id = f"mcp_{uuid.uuid4().hex[:8]}"
        now = datetime.utcnow().isoformat() + "Z"

        versioned_context = PersistentModelContext(
            context_id=new_context_id,
            protocol=original.protocol,
            model_id=original.model_id,
            session_id=original.session_id,
            parameters=dict(original.parameters),  # Copy parameters
            metadata={
                **original.metadata,
                "version_of": context_id,
                "version_notes": version_notes,
                "version_timestamp": now,
            },
            created_at=now,
            updated_at=now,
            persistence_flags=dict(original.persistence_flags),
        )

        # Save new version
        await self.save_context(versioned_context)

        logger.info(f"Created version {new_context_id} of context {context_id}")
        return new_context_id

    async def get_context_versions(self, context_id: str) -> list[PersistentModelContext]:
        """Get all versions of a context.

        Args:
            context_id: ID of original context

        Returns:
            List of version contexts
        """
        if self._redis is None:
            await self.connect()

        versions = []
        pattern = "mcp:context:*"

        async for key in self._redis.scan_iter(match=pattern):
            ctx_id = key.replace("mcp:context:", "")
            context = await self.get_context(ctx_id)

            if context and context.metadata.get("version_of") == context_id:
                versions.append(context)

        # Sort by creation date (newest first)
        versions.sort(key=lambda x: x.created_at, reverse=True)

        logger.info(f"Found {len(versions)} versions of context {context_id}")
        return versions

    # --- Cleanup Operations ---

    async def clear_session_contexts(self, session_id: str) -> int:
        """Clear all contexts for a session.

        Args:
            session_id: ID of session

        Returns:
            Number of contexts deleted
        """
        if self._redis is None:
            await self.connect()

        # Get all context IDs for session
        session_key = self._get_session_contexts_key(session_id)
        context_ids = await self._redis.smembers(session_key)

        deleted_count = 0

        # Delete each context
        for ctx_id in context_ids:
            if await self.delete_context(ctx_id):
                deleted_count += 1

        # Delete session index
        await self._redis.delete(session_key)

        logger.info(f"Cleared {deleted_count} contexts for session {session_id}")
        return deleted_count

    async def clear_all_contexts(self) -> int:
        """Clear all MCP contexts (for testing/debugging).

        Returns:
            Number of contexts deleted
        """
        if self._redis is None:
            await self.connect()

        # Delete all context records
        context_keys = []
        async for key in self._redis.scan_iter(match="mcp:context:*"):
            context_keys.append(key)

        # Delete all session indexes
        session_keys = []
        async for key in self._redis.scan_iter(match="mcp:session:*"):
            session_keys.append(key)

        # Delete all model indexes
        model_keys = []
        async for key in self._redis.scan_iter(match="mcp:model:*"):
            model_keys.append(key)

        all_keys = context_keys + session_keys + model_keys

        if all_keys:
            result = await self._redis.delete(*all_keys)
            logger.info(f"Cleared {result} MCP context records")
            return result

        return 0


# Utility functions for MCP persistence


async def create_persistent_mcp_context(
    manager: MCPPersistenceManager,
    model_id: str,
    session_id: str,
    parameters: dict[str, Any],
    metadata: dict[str, Any] | None = None,
    persistence_flags: dict[str, bool] | None = None,
    ttl: int | None = None,
) -> str:
    """Create a new persistent MCP context with automatic IDs."""
    # Create standard MCP context
    mcp_context = ModelContextProtocol.create_context(
        model_id=model_id,
        session_id=session_id,
        parameters=parameters,
        metadata=metadata,
    )

    # Create persistent version
    return await manager.create_persistent_context(
        mcp_context=mcp_context, persistence_flags=persistence_flags, ttl=ttl
    )


async def load_mcp_context_with_persistence(
    manager: MCPPersistenceManager, context_id: str
) -> dict[str, Any] | None:
    """Load MCP context from persistence, falling back to standard format."""
    persistent_context = await manager.get_context(context_id)
    return persistent_context.to_mcp_context() if persistent_context else None


async def update_mcp_context_with_persistence(
    manager: MCPPersistenceManager,
    context_id: str,
    parameters: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
) -> bool:
    """Update MCP context parameters and metadata with persistence."""
    update_data = {}

    if parameters is not None:
        update_data["parameters"] = parameters

    if metadata is not None:
        update_data["metadata"] = metadata

    if not update_data:
        return False

    return await manager.update_context(context_id, update_data)
