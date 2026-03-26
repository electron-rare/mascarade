"""Redis-backed conversation memory storage."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import redis.asyncio as redis

from mascarade.project_scope import normalize_scope, scoped_resource_key

if TYPE_CHECKING:
    from mascarade.conversation.models import Conversation, ConversationMessage


class ConversationMemory:
    """Redis-backed storage for conversation history."""

    def __init__(self, redis_url: str = "redis://localhost:6379", default_ttl: int = 86400) -> None:
        """Initialize conversation memory with Redis connection.

        Args:
            redis_url: Redis connection URL
            default_ttl: Default time-to-live for conversations in seconds (default: 24h)
        """
        self.redis_url = redis_url
        self.default_ttl = default_ttl
        self._redis: redis.Redis | None = None

    async def connect(self) -> None:
        """Establish Redis connection."""
        if self._redis is None:
            self._redis = redis.from_url(
                self.redis_url,
                encoding="utf-8",
                decode_responses=True,
            )

    async def disconnect(self) -> None:
        """Close Redis connection."""
        if self._redis is not None:
            await self._redis.aclose()
            self._redis = None

    def _conversation_key(self, conversation_id: str, *, project_id: str | None = None) -> str:
        """Generate Redis key for a conversation."""
        return scoped_resource_key(
            "conversation",
            conversation_id,
            project_id=project_id,
        )

    async def store_message(
        self,
        conversation_id: str,
        message: ConversationMessage,
        ttl: int | None = None,
        project_id: str | None = None,
    ) -> None:
        """Store a message in a conversation.

        Args:
            conversation_id: Unique conversation identifier
            message: Message to store
            ttl: Optional TTL override for this conversation
        """
        if self._redis is None:
            await self.connect()

        from mascarade.conversation.models import Conversation

        # Get existing conversation or create new one
        normalized_project, _, _ = normalize_scope(project_id=project_id)
        conversation = await self.get_conversation(conversation_id, project_id=normalized_project)
        if conversation is None:
            conversation = Conversation(
                id=conversation_id,
                ttl=float(ttl or self.default_ttl),
            )

        # Add message to conversation
        conversation.add_message(message)

        # Store in Redis
        key = self._conversation_key(conversation_id, project_id=normalized_project)
        value = json.dumps(conversation.to_dict())
        ttl_seconds = int(ttl or conversation.ttl)

        await self._redis.set(key, value, ex=ttl_seconds)

    async def get_conversation(
        self,
        conversation_id: str,
        *,
        project_id: str | None = None,
    ) -> Conversation | None:
        """Retrieve a conversation by ID.

        Args:
            conversation_id: Unique conversation identifier

        Returns:
            Conversation object or None if not found
        """
        if self._redis is None:
            await self.connect()

        from mascarade.conversation.models import Conversation

        normalized_project, _, _ = normalize_scope(project_id=project_id)
        key = self._conversation_key(conversation_id, project_id=normalized_project)
        value = await self._redis.get(key)

        if value is None:
            return None

        data = json.loads(value)
        return Conversation.from_dict(data)

    async def delete_conversation(
        self,
        conversation_id: str,
        *,
        project_id: str | None = None,
    ) -> bool:
        """Delete a conversation.

        Args:
            conversation_id: Unique conversation identifier

        Returns:
            True if conversation was deleted, False if not found
        """
        if self._redis is None:
            await self.connect()

        normalized_project, _, _ = normalize_scope(project_id=project_id)
        key = self._conversation_key(conversation_id, project_id=normalized_project)
        result = await self._redis.delete(key)
        return result > 0

    async def list_conversations(self, *, project_id: str | None = None) -> list[str]:
        """List all conversation IDs.

        Returns:
            List of conversation IDs
        """
        if self._redis is None:
            await self.connect()

        # Scan for all conversation keys
        normalized_project, _, _ = normalize_scope(project_id=project_id)
        pattern = f"conversation:{normalized_project}:*"
        conversation_ids = []

        async for key in self._redis.scan_iter(match=pattern):
            # Extract conversation ID from key
            conversation_id = key.replace(f"conversation:{normalized_project}:", "")
            conversation_ids.append(conversation_id)

        return sorted(conversation_ids)

    async def get_conversation_metadata(
        self,
        conversation_id: str,
        *,
        project_id: str | None = None,
    ) -> dict | None:
        """Get conversation metadata without loading full message history.

        Args:
            conversation_id: Unique conversation identifier

        Returns:
            Dictionary with metadata (id, message_count, created_at, updated_at, ttl)
        """
        conversation = await self.get_conversation(conversation_id, project_id=project_id)
        if conversation is None:
            return None

        return {
            "id": conversation.id,
            "message_count": len(conversation.messages),
            "created_at": conversation.created_at,
            "updated_at": conversation.updated_at,
            "ttl": conversation.ttl,
            "total_tokens": conversation.get_total_tokens(),
        }

    async def clear_all(self, *, project_id: str | None = None) -> int:
        """Clear all conversations (for testing/debugging).

        Returns:
            Number of conversations deleted
        """
        if self._redis is None:
            await self.connect()

        normalized_project, _, _ = normalize_scope(project_id=project_id)
        keys = []
        async for key in self._redis.scan_iter(match=f"conversation:{normalized_project}:*"):
            keys.append(key)

        if keys:
            return await self._redis.delete(*keys)
        return 0
