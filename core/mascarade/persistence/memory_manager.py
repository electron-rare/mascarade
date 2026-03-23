"""Multi-Backend Memory Management System for Mascarade."""

from __future__ import annotations

import json
import logging
from typing import Any

import redis.asyncio as redis
from pydantic import BaseModel

from mascarade.conversation.memory import ConversationMemory
from mascarade.project_scope import normalize_scope, scoped_resource_key

logger = logging.getLogger("mascarade.persistence.memory")


class MemoryEntry(BaseModel):
    """Standardized memory entry with metadata."""

    memory_id: str
    content: str | dict[str, Any]
    memory_type: str = "generic"
    created_at: str
    updated_at: str
    metadata: dict[str, Any] = {}
    tags: list[str] = []

    class Config:
        json_schema_extra = {
            "examples": [
                {
                    "memory_id": "mem_12345",
                    "content": "Sample memory content",
                    "memory_type": "conversation",
                    "created_at": "2024-01-01T00:00:00Z",
                    "updated_at": "2024-01-01T00:00:00Z",
                    "metadata": {"user_id": "user_123"},
                    "tags": ["important", "recent"]
                }
            ]
        }


class MultiBackendMemoryManager:
    """Multi-backend memory manager supporting Redis and other backends."""

    def __init__(
        self,
        redis_url: str = "redis://localhost:6379",
        default_ttl: int = 86400
    ) -> None:
        """Initialize multi-backend memory manager.

        Args:
            redis_url: Redis connection URL
            default_ttl: Default time-to-live in seconds (24h)
        """
        self.redis_url = redis_url
        self.default_ttl = default_ttl
        self._redis: redis.Redis | None = None
        self._conversation_memory: ConversationMemory | None = None

    async def connect(self) -> None:
        """Establish connections to all backends."""
        if self._redis is None:
            self._redis = redis.from_url(
                self.redis_url,
                encoding="utf-8",
                decode_responses=True,
            )
            logger.info("Connected to Redis for memory storage")

        if self._conversation_memory is None:
            self._conversation_memory = ConversationMemory(
                redis_url=self.redis_url,
                default_ttl=self.default_ttl
            )
            await self._conversation_memory.connect()
            logger.info("Connected to ConversationMemory backend")

    async def disconnect(self) -> None:
        """Close all backend connections."""
        if self._redis is not None:
            await self._redis.aclose()
            self._redis = None

        if self._conversation_memory is not None:
            await self._conversation_memory.disconnect()
            self._conversation_memory = None

        logger.info("Disconnected from all memory backends")

    # --- Generic Memory Operations ---

    def _get_memory_key(self, memory_id: str, *, project_id: str | None = None) -> str:
        """Generate Redis key for memory storage."""
        return scoped_resource_key("memory", memory_id, project_id=project_id)

    async def store_memory(
        self,
        memory_entry: MemoryEntry,
        ttl: int | None = None,
        project_id: str | None = None,
    ) -> str:
        """Store memory in persistence layer.

        Args:
            memory_entry: Memory entry to store
            ttl: Optional TTL override in seconds

        Returns:
            memory_id of the stored memory
        """
        if self._redis is None:
            await self.connect()

        normalized_project, _, _ = normalize_scope(
            project_id=project_id or str(memory_entry.metadata.get("project_id") or ""),
        )
        memory_entry.metadata["project_id"] = normalized_project
        key = self._get_memory_key(memory_entry.memory_id, project_id=normalized_project)
        value = memory_entry.json()
        ttl_seconds = ttl or self.default_ttl

        await self._redis.set(key, value, ex=ttl_seconds)
        logger.info(f"Stored memory {memory_entry.memory_id} (type: {memory_entry.memory_type})")

        return memory_entry.memory_id

    async def retrieve_memory(
        self,
        memory_id: str,
        project_id: str | None = None,
    ) -> MemoryEntry | None:
        """Retrieve memory from persistence layer.

        Args:
            memory_id: ID of memory to retrieve

        Returns:
            MemoryEntry object or None if not found
        """
        if self._redis is None:
            await self.connect()

        normalized_project, _, _ = normalize_scope(project_id=project_id)
        key = self._get_memory_key(memory_id, project_id=normalized_project)
        value = await self._redis.get(key)

        if value is None:
            logger.warning(f"Memory {memory_id} not found")
            return None

        try:
            memory_entry = MemoryEntry.parse_raw(value)
            logger.info(f"Retrieved memory {memory_id}")
            return memory_entry
        except Exception as e:
            logger.error(f"Failed to deserialize memory {memory_id}: {e}")
            return None

    async def update_memory(
        self,
        memory_id: str,
        update_data: dict[str, Any],
        project_id: str | None = None,
    ) -> bool:
        """Update existing memory.

        Args:
            memory_id: ID of memory to update
            update_data: Dictionary of fields to update

        Returns:
            True if update succeeded, False if memory not found
        """
        if self._redis is None:
            await self.connect()

        # Retrieve existing memory
        existing_memory = await self.retrieve_memory(memory_id, project_id=project_id)
        if existing_memory is None:
            return False

        # Update fields
        for field, value in update_data.items():
            if hasattr(existing_memory, field):
                setattr(existing_memory, field, value)

        # Update timestamp
        from datetime import datetime
        existing_memory.updated_at = datetime.utcnow().isoformat() + "Z"

        # Save updated memory
        await self.store_memory(existing_memory, project_id=project_id)
        logger.info(f"Updated memory {memory_id}")

        return True

    async def delete_memory(
        self,
        memory_id: str,
        project_id: str | None = None,
    ) -> bool:
        """Delete memory from persistence layer.

        Args:
            memory_id: ID of memory to delete

        Returns:
            True if deletion succeeded, False if memory not found
        """
        if self._redis is None:
            await self.connect()

        normalized_project, _, _ = normalize_scope(project_id=project_id)
        key = self._get_memory_key(memory_id, project_id=normalized_project)
        result = await self._redis.delete(key)

        if result > 0:
            logger.info(f"Deleted memory {memory_id}")
            return True

        logger.warning(f"Memory {memory_id} not found for deletion")
        return False

    # --- Advanced Memory Operations ---

    async def search_memories(
        self,
        query: str,
        memory_type: str | None = None,
        tags: list[str] | None = None,
        limit: int = 10,
        project_id: str | None = None,
    ) -> list[MemoryEntry]:
        """Search memories using metadata and tags.

        Args:
            query: Search query (currently matches against content)
            memory_type: Optional type filter
            tags: Optional tag filter
            limit: Maximum number of results

        Returns:
            List of matching MemoryEntry objects
        """
        if self._redis is None:
            await self.connect()

        normalized_project, _, _ = normalize_scope(project_id=project_id)
        pattern = f"memory:{normalized_project}:*"
        results = []

        async for key in self._redis.scan_iter(match=pattern):
            memory_id = str(key).replace(f"memory:{normalized_project}:", "")
            memory_entry = await self.retrieve_memory(memory_id, project_id=normalized_project)

            if memory_entry is None:
                continue

            # Apply filters
            if memory_type and memory_entry.memory_type != memory_type:
                continue

            if tags and not any(tag in memory_entry.tags for tag in tags):
                continue

            # Simple text matching (could be enhanced with vector search)
            content_str = memory_entry.content
            if isinstance(content_str, dict):
                content_str = json.dumps(content_str)

            if query.lower() in content_str.lower():
                results.append(memory_entry)

                if len(results) >= limit:
                    break

        return results

    async def list_memories(
        self,
        memory_type: str | None = None,
        tags: list[str] | None = None,
        project_id: str | None = None,
    ) -> list[str]:
        """List all memory IDs, optionally filtered.

        Args:
            memory_type: Optional type filter
            tags: Optional tag filter

        Returns:
            List of memory IDs
        """
        if self._redis is None:
            await self.connect()

        normalized_project, _, _ = normalize_scope(project_id=project_id)
        pattern = f"memory:{normalized_project}:*"
        memory_ids = []

        async for key in self._redis.scan_iter(match=pattern):
            memory_id = str(key).replace(f"memory:{normalized_project}:", "")
            memory_entry = await self.retrieve_memory(memory_id, project_id=normalized_project)

            if memory_entry is None:
                continue

            # Apply filters
            if memory_type and memory_entry.memory_type != memory_type:
                continue

            if tags and not any(tag in memory_entry.tags for tag in tags):
                continue

            memory_ids.append(memory_id)

        return sorted(memory_ids)

    async def get_memory_metadata(
        self,
        memory_id: str,
        project_id: str | None = None,
    ) -> dict[str, Any] | None:
        """Get memory metadata without loading full content.

        Args:
            memory_id: ID of memory

        Returns:
            Dictionary with metadata or None if not found
        """
        if self._redis is None:
            await self.connect()

        normalized_project, _, _ = normalize_scope(project_id=project_id)
        key = self._get_memory_key(memory_id, project_id=normalized_project)
        value = await self._redis.get(key)

        if value is None:
            return None

        try:
            memory_data = json.loads(value)
            return {
                "memory_id": memory_data["memory_id"],
                "memory_type": memory_data["memory_type"],
                "created_at": memory_data["created_at"],
                "updated_at": memory_data["updated_at"],
                "metadata": memory_data.get("metadata", {}),
                "tags": memory_data.get("tags", [])
            }
        except Exception as e:
            logger.error(f"Failed to get metadata for memory {memory_id}: {e}")
            return None

    # --- Conversation Memory Integration ---

    async def store_conversation_message(
        self,
        conversation_id: str,
        message: Any,
        ttl: int | None = None,
        project_id: str | None = None,
    ) -> None:
        """Store conversation message using ConversationMemory backend."""
        if self._conversation_memory is None:
            await self.connect()

        await self._conversation_memory.store_message(
            conversation_id=conversation_id,
            message=message,
            ttl=ttl,
            project_id=project_id,
        )

        logger.info(f"Stored conversation message for {conversation_id}")

    async def get_conversation(
        self,
        conversation_id: str,
        project_id: str | None = None,
    ) -> Any | None:
        """Retrieve conversation using ConversationMemory backend."""
        if self._conversation_memory is None:
            await self.connect()

        return await self._conversation_memory.get_conversation(
            conversation_id,
            project_id=project_id,
        )

    async def delete_conversation(
        self,
        conversation_id: str,
        project_id: str | None = None,
    ) -> bool:
        """Delete conversation using ConversationMemory backend."""
        if self._conversation_memory is None:
            await self.connect()

        return await self._conversation_memory.delete_conversation(
            conversation_id,
            project_id=project_id,
        )

    # --- Batch Operations ---

    async def batch_store_memories(
        self,
        memories: list[MemoryEntry],
        ttl: int | None = None,
        project_id: str | None = None,
    ) -> list[str]:
        """Store multiple memories in a batch operation.

        Args:
            memories: List of MemoryEntry objects
            ttl: Optional TTL override

        Returns:
            List of successfully stored memory IDs
        """
        if self._redis is None:
            await self.connect()

        normalized_project, _, _ = normalize_scope(project_id=project_id)
        pipeline = self._redis.pipeline()
        stored_ids = []

        for memory in memories:
            memory.metadata["project_id"] = normalized_project
            key = self._get_memory_key(memory.memory_id, project_id=normalized_project)
            value = memory.json()
            ttl_seconds = ttl or self.default_ttl

            pipeline.set(key, value, ex=ttl_seconds)
            stored_ids.append(memory.memory_id)

        await pipeline.execute()
        logger.info(f"Batch stored {len(stored_ids)} memories")

        return stored_ids

    async def batch_delete_memories(
        self,
        memory_ids: list[str],
        project_id: str | None = None,
    ) -> int:
        """Delete multiple memories in a batch operation.

        Args:
            memory_ids: List of memory IDs to delete

        Returns:
            Number of successfully deleted memories
        """
        if self._redis is None:
            await self.connect()

        if not memory_ids:
            return 0

        normalized_project, _, _ = normalize_scope(project_id=project_id)
        keys = [
            self._get_memory_key(memory_id, project_id=normalized_project)
            for memory_id in memory_ids
        ]
        result = await self._redis.delete(*keys)

        logger.info(f"Batch deleted {result} memories")
        return result

    async def clear_all_memories(self, project_id: str | None = None) -> int:
        """Clear all memories (for testing/debugging).

        Returns:
            Number of memories deleted
        """
        if self._redis is None:
            await self.connect()

        normalized_project, _, _ = normalize_scope(project_id=project_id)
        keys = []
        async for key in self._redis.scan_iter(match=f"memory:{normalized_project}:*"):
            keys.append(key)

        if keys:
            result = await self._redis.delete(*keys)
            logger.info(f"Cleared {result} memories")
            return result

        return 0


# Utility functions for common memory operations

async def create_memory_entry(
    content: str | dict[str, Any],
    memory_type: str = "generic",
    memory_id: str | None = None,
    metadata: dict[str, Any] | None = None,
    tags: list[str] | None = None
) -> MemoryEntry:
    """Create a new MemoryEntry with automatic IDs and timestamps."""
    import uuid
    from datetime import datetime

    now = datetime.utcnow().isoformat() + "Z"

    return MemoryEntry(
        memory_id=memory_id or f"mem_{uuid.uuid4().hex[:8]}",
        content=content,
        memory_type=memory_type,
        created_at=now,
        updated_at=now,
        metadata=metadata or {},
        tags=tags or []
    )


async def create_conversation_memory(
    manager: MultiBackendMemoryManager,
    conversation_id: str,
    user_id: str,
    initial_message: str,
    metadata: dict[str, Any] | None = None,
    project_id: str | None = None,
) -> str:
    """Create a new conversation with initial memory."""
    from mascarade.conversation.models import ConversationMessage
    normalized_project, _, _ = normalize_scope(project_id=project_id)

    # Create conversation memory entry
    memory_entry = await create_memory_entry(
        content={"initial_message": initial_message},
        memory_type="conversation",
        metadata={"user_id": user_id, "project_id": normalized_project, **(metadata or {})},
        tags=["conversation", "active"]
    )

    # Store in memory system
    await manager.store_memory(memory_entry, project_id=normalized_project)

    # Create initial conversation message
    message = ConversationMessage(
        role="user",
        content=initial_message,
        timestamp=memory_entry.created_at
    )

    # Store in conversation system
    await manager.store_conversation_message(
        conversation_id,
        message,
        project_id=normalized_project,
    )

    return memory_entry.memory_id
