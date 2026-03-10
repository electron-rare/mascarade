"""Gossip-based PubSub for capability exchange and event broadcasting."""

from __future__ import annotations

import asyncio
import hashlib
import logging
import time
from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Callable, Coroutine

from mascarade.p2p.protocol import P2PMessage
from mascarade.p2p.transport import P2PTransport, PeerConnection

logger = logging.getLogger("mascarade.p2p.pubsub")

TopicHandler = Callable[[str, dict[str, Any], str], Coroutine[Any, Any, None]]

_SEEN_TTL = 300.0  # Deduplicate messages for 5 minutes
_MAX_SEEN = 10_000


@dataclass
class _SeenEntry:
    ts: float


class P2PPubSub:
    """Gossip protocol — subscribe to topics and broadcast messages to all peers."""

    def __init__(self, *, local_peer_id: str, transport: P2PTransport) -> None:
        self._local_peer_id = local_peer_id
        self._transport = transport
        self._subscriptions: dict[str, list[TopicHandler]] = defaultdict(list)
        self._seen: dict[str, _SeenEntry] = {}

        transport.on_message("pubsub:publish", self._handle_publish)
        transport.on_message("pubsub:subscribe", self._handle_subscribe)

    def subscribe(self, topic: str, handler: TopicHandler) -> None:
        self._subscriptions[topic].append(handler)
        logger.debug("Subscribed to topic: %s", topic)

    async def publish(self, topic: str, data: dict[str, Any]) -> int:
        nonce = self._make_nonce(topic, data)
        self._mark_seen(nonce)

        msg = P2PMessage(
            type="pubsub:publish",
            sender=self._local_peer_id,
            payload={"topic": topic, "data": data},
            nonce=nonce,
        )
        return await self._transport.broadcast(msg)

    async def _handle_publish(self, msg: P2PMessage, conn: PeerConnection) -> None:
        nonce = msg.nonce or self._make_nonce(
            msg.payload.get("topic", ""), msg.payload.get("data", {}),
        )

        if self._is_seen(nonce):
            return
        self._mark_seen(nonce)

        topic = msg.payload.get("topic", "")
        data = msg.payload.get("data", {})
        origin = msg.sender

        handlers = self._subscriptions.get(topic, [])
        for handler in handlers:
            try:
                await handler(topic, data, origin)
            except Exception:
                logger.exception("PubSub handler error on topic %s", topic)

        # Re-gossip to other peers (excluding sender)
        relay = P2PMessage(
            type="pubsub:publish",
            sender=msg.sender,
            payload=msg.payload,
            ts=msg.ts,
            nonce=nonce,
        )
        for peer_id, peer_conn in self._transport.peers.items():
            if peer_id != msg.sender and peer_id != self._local_peer_id:
                await peer_conn.send(relay)

    async def _handle_subscribe(self, msg: P2PMessage, conn: PeerConnection) -> None:
        # Remote peer declares interest in a topic — we track it for targeted gossip
        pass

    def _make_nonce(self, topic: str, data: dict[str, Any]) -> str:
        raw = f"{self._local_peer_id}:{topic}:{time.time()}:{id(data)}"
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    def _is_seen(self, nonce: str) -> bool:
        entry = self._seen.get(nonce)
        if not entry:
            return False
        if time.monotonic() - entry.ts > _SEEN_TTL:
            del self._seen[nonce]
            return False
        return True

    def _mark_seen(self, nonce: str) -> None:
        if len(self._seen) > _MAX_SEEN:
            cutoff = time.monotonic() - _SEEN_TTL
            self._seen = {k: v for k, v in self._seen.items() if v.ts > cutoff}
        self._seen[nonce] = _SeenEntry(ts=time.monotonic())
