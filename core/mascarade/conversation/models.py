"""Conversation data models for persistent memory."""

from __future__ import annotations

import time
from dataclasses import dataclass, field


@dataclass
class ConversationMessage:
    """Single message in a conversation."""

    role: str  # user, assistant, system
    content: str
    timestamp: float = field(default_factory=time.time)
    tokens: int = 0

    def to_dict(self) -> dict:
        """Convert to dictionary format."""
        return {
            "role": self.role,
            "content": self.content,
            "timestamp": self.timestamp,
            "tokens": self.tokens,
        }

    @classmethod
    def from_dict(cls, data: dict) -> ConversationMessage:
        """Create from dictionary format."""
        return cls(
            role=data["role"],
            content=data["content"],
            timestamp=data.get("timestamp", time.time()),
            tokens=data.get("tokens", 0),
        )


@dataclass
class Conversation:
    """Conversation with message history and metadata."""

    id: str
    messages: list[ConversationMessage] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    ttl: float = 86400.0  # 24 hours default
    metadata: dict = field(default_factory=dict)

    def add_message(self, message: ConversationMessage) -> None:
        """Add a message to the conversation."""
        self.messages.append(message)
        self.updated_at = time.time()

    def get_total_tokens(self) -> int:
        """Calculate total tokens across all messages."""
        return sum(msg.tokens for msg in self.messages)

    def is_expired(self) -> bool:
        """Check if the conversation has expired based on TTL."""
        return time.time() > (self.updated_at + self.ttl)

    def to_dict(self) -> dict:
        """Convert to dictionary format for serialization."""
        return {
            "id": self.id,
            "messages": [msg.to_dict() for msg in self.messages],
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "ttl": self.ttl,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict) -> Conversation:
        """Create from dictionary format."""
        messages = [
            ConversationMessage.from_dict(msg) for msg in data.get("messages", [])
        ]
        return cls(
            id=data["id"],
            messages=messages,
            created_at=data.get("created_at", time.time()),
            updated_at=data.get("updated_at", time.time()),
            ttl=data.get("ttl", 86400.0),
            metadata=data.get("metadata", {}),
        )
