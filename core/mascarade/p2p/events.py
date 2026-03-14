"""P2P event bus — real-time event streaming for the P2P dashboard."""

from __future__ import annotations

import asyncio
import logging
import time
from collections import deque
from dataclasses import asdict, dataclass, field
from typing import Any

logger = logging.getLogger("mascarade.p2p.events")

# Recognised event types
EVENT_PEER_JOINED = "peer_joined"
EVENT_PEER_LEFT = "peer_left"
EVENT_CAPABILITY_UPDATE = "capability_update"
EVENT_TASK_SUBMITTED = "task_submitted"
EVENT_TASK_COMPLETED = "task_completed"
EVENT_FORWARD_REQUEST = "forward_request"
EVENT_FORWARD_RESPONSE = "forward_response"
EVENT_HEARTBEAT = "heartbeat"

ALL_EVENT_TYPES = frozenset({
    EVENT_PEER_JOINED,
    EVENT_PEER_LEFT,
    EVENT_CAPABILITY_UPDATE,
    EVENT_TASK_SUBMITTED,
    EVENT_TASK_COMPLETED,
    EVENT_FORWARD_REQUEST,
    EVENT_FORWARD_RESPONSE,
    EVENT_HEARTBEAT,
})

_RING_BUFFER_SIZE = 200


@dataclass
class P2PEvent:
    """A single P2P event."""

    type: str
    timestamp: float = field(default_factory=time.time)
    data: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class P2PEventBus:
    """Fan-out event bus with ring buffer and async subscriber queues."""

    def __init__(self, max_history: int = _RING_BUFFER_SIZE) -> None:
        self._history: deque[P2PEvent] = deque(maxlen=max_history)
        self._subscribers: set[asyncio.Queue[P2PEvent]] = set()

    def emit(self, event: P2PEvent) -> None:
        """Store event and notify all subscribers."""
        self._history.append(event)
        for queue in self._subscribers:
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                # Drop oldest to make room
                try:
                    queue.get_nowait()
                except asyncio.QueueEmpty:
                    pass
                try:
                    queue.put_nowait(event)
                except asyncio.QueueFull:
                    pass

    def subscribe(self) -> asyncio.Queue[P2PEvent]:
        """Create and return a new subscriber queue."""
        queue: asyncio.Queue[P2PEvent] = asyncio.Queue(maxsize=256)
        self._subscribers.add(queue)
        logger.debug("New SSE subscriber (total=%d)", len(self._subscribers))
        return queue

    def unsubscribe(self, queue: asyncio.Queue[P2PEvent]) -> None:
        """Remove a subscriber queue."""
        self._subscribers.discard(queue)
        logger.debug("SSE subscriber removed (total=%d)", len(self._subscribers))

    def recent(self, limit: int = 50) -> list[P2PEvent]:
        """Return the last *limit* events from the ring buffer."""
        items = list(self._history)
        return items[-limit:] if limit < len(items) else items
