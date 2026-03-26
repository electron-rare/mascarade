"""Kademlia-style DHT for peer discovery beyond the local network."""

from __future__ import annotations

import asyncio
import hashlib
import logging
import time
from dataclasses import dataclass, field
from typing import Any

from mascarade.p2p.protocol import P2PMessage
from mascarade.p2p.transport import P2PTransport, PeerConnection

logger = logging.getLogger("mascarade.p2p.dht")

_K = 20  # Kademlia bucket size
_ALPHA = 3  # Parallel lookups


@dataclass
class DHTEntry:
    peer_id: str
    host: str
    port: int
    last_seen: float = 0.0
    capabilities: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def distance_to(self, target_id: str) -> int:
        a = int(hashlib.sha256(self.peer_id.encode()).hexdigest(), 16)
        b = int(hashlib.sha256(target_id.encode()).hexdigest(), 16)
        return a ^ b


class DHTRoutingTable:
    """Simplified Kademlia routing table — flat list with K-closest eviction."""

    def __init__(self, local_id: str, k: int = _K) -> None:
        self._local_id = local_id
        self._k = k
        self._entries: dict[str, DHTEntry] = {}

    def upsert(self, entry: DHTEntry) -> None:
        if entry.peer_id == self._local_id:
            return
        entry.last_seen = time.monotonic()
        self._entries[entry.peer_id] = entry
        # Fix 2: prune stale entries on every upsert to prevent unbounded growth
        self.prune_stale()

    def remove(self, peer_id: str) -> None:
        self._entries.pop(peer_id, None)

    def prune_stale(self, max_age: float = 300.0) -> int:
        """Remove entries not seen for longer than *max_age* seconds."""
        cutoff = time.monotonic() - max_age
        stale = [pid for pid, e in self._entries.items() if e.last_seen < cutoff]
        for pid in stale:
            del self._entries[pid]
        if stale:
            logger.debug("DHT: pruned %d stale routing-table entries", len(stale))
        return len(stale)

    def closest(self, target_id: str, count: int = _K) -> list[DHTEntry]:
        entries = sorted(
            self._entries.values(),
            key=lambda e: e.distance_to(target_id),
        )
        return entries[:count]

    def find_by_capability(self, capability: str) -> list[DHTEntry]:
        return [e for e in self._entries.values() if capability in e.capabilities]

    def all_entries(self) -> list[DHTEntry]:
        return list(self._entries.values())

    def __len__(self) -> int:
        return len(self._entries)


class P2PDHT:
    """DHT service running on top of the P2P transport layer."""

    def __init__(
        self,
        *,
        local_peer_id: str,
        transport: P2PTransport,
        bootstrap_peers: list[tuple[str, str, int]] | None = None,
        public_key: str = "",
        pubsub: Any | None = None,
    ) -> None:
        self._local_peer_id = local_peer_id
        self._transport = transport
        self._public_key = public_key
        self._pubsub = pubsub
        self._table = DHTRoutingTable(local_peer_id)
        self._bootstrap_peers = bootstrap_peers or []
        self._seen_announces: dict[str, float] = {}

        transport.on_message("dht:find_node", self._handle_find_node)
        transport.on_message("dht:find_node_reply", self._handle_find_node_reply)
        transport.on_message("dht:announce", self._handle_announce)
        transport.on_message("dht:ping", self._handle_ping)
        transport.on_message("dht:pong", self._handle_pong)

        if pubsub is not None:
            pubsub.subscribe("dht:peer_discovered", self._handle_peer_discovered)

    @property
    def routing_table(self) -> DHTRoutingTable:
        return self._table

    async def bootstrap(self) -> None:
        for peer_id, host, port in self._bootstrap_peers:
            self._transport.add_peer(peer_id, host, port)
            self._table.upsert(DHTEntry(peer_id=peer_id, host=host, port=port))

        await self._announce_self()

        for peer_id, _, _ in self._bootstrap_peers:
            await self.find_node(self._local_peer_id, target_peer=peer_id)

    async def find_node(self, target_id: str, target_peer: str | None = None) -> list[DHTEntry]:
        msg = P2PMessage(
            type="dht:find_node",
            sender=self._local_peer_id,
            payload={
                "target": target_id,
                "host": self._transport._listen_host,
                "port": self._transport.listen_port,
            },
        )

        if target_peer:
            await self._transport.send_to(target_peer, msg)
        else:
            closest = self._table.closest(target_id, count=_ALPHA)
            for entry in closest:
                await self._transport.send_to(entry.peer_id, msg)

        await asyncio.sleep(0.5)
        return self._table.closest(target_id)

    async def announce(
        self, capabilities: list[str], metadata: dict[str, Any] | None = None
    ) -> int:
        return await self._announce_self(capabilities=capabilities, metadata=metadata)

    async def _announce_self(
        self,
        capabilities: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> int:
        msg = P2PMessage(
            type="dht:announce",
            sender=self._local_peer_id,
            payload={
                "host": self._transport._listen_host,
                "port": self._transport.listen_port,
                "capabilities": capabilities or [],
                "metadata": metadata or {},
                "public_key": self._public_key,
            },
        )
        return await self._transport.broadcast(msg)

    @staticmethod
    def _resolve_host(announced_host: str, conn_host: str) -> str:
        """Use the connection's real IP if the announced host is unroutable."""
        if announced_host in ("0.0.0.0", "::", "::0", "", "localhost", "127.0.0.1"):
            return conn_host
        return announced_host

    async def _handle_find_node(self, msg: P2PMessage, conn: PeerConnection) -> None:
        target = msg.payload.get("target", "")
        host = self._resolve_host(msg.payload.get("host", conn.host), conn.host)
        port = msg.payload.get("port", conn.port)

        self._table.upsert(
            DHTEntry(
                peer_id=msg.sender,
                host=host,
                port=port,
            )
        )
        # Register as transport peer so we can send messages back
        self._transport.add_peer(msg.sender, host, port)

        closest = self._table.closest(target)
        reply = P2PMessage(
            type="dht:find_node_reply",
            sender=self._local_peer_id,
            payload={
                "target": target,
                "peers": [{"peer_id": e.peer_id, "host": e.host, "port": e.port} for e in closest],
            },
        )
        await conn.send(reply)

    async def _handle_find_node_reply(self, msg: P2PMessage, conn: PeerConnection) -> None:
        peers = msg.payload.get("peers", [])
        for peer_data in peers:
            pid = peer_data.get("peer_id", "")
            if pid and pid != self._local_peer_id:
                host = peer_data.get("host", "")
                port = peer_data.get("port", 0)
                if host and port:
                    self._table.upsert(DHTEntry(peer_id=pid, host=host, port=port))
                    self._transport.add_peer(pid, host, port)

    async def _handle_announce(self, msg: P2PMessage, conn: PeerConnection) -> None:
        announced_host = msg.payload.get("host", "")
        resolved_host = self._resolve_host(announced_host, conn.host)

        # Fix 1: DHT poisoning — reject announcements where the announced host is
        # a routable address that does not match the actual connection source IP.
        # Unroutable/wildcard values (0.0.0.0, localhost, etc.) are allowed because
        # _resolve_host already replaces them with conn.host.
        if (
            announced_host
            and announced_host not in ("0.0.0.0", "::", "::0", "", "localhost")
            and announced_host != conn.host
        ):
            logger.warning(
                "DHT: rejected announce from %s — announced host %s does not match "
                "connection source %s",
                msg.sender,
                announced_host,
                conn.host,
            )
            return

        host = resolved_host
        port = msg.payload.get("port", conn.port)

        # Validate port range
        if not isinstance(port, int) or port < 1 or port > 65535:
            logger.warning(
                "DHT: rejected announce from %s — invalid port %s",
                msg.sender,
                port,
            )
            return

        # Validate host format (must be non-empty after resolution)
        if not host or not isinstance(host, str):
            logger.warning(
                "DHT: rejected announce from %s — empty or invalid host",
                msg.sender,
            )
            return
        capabilities = msg.payload.get("capabilities", [])
        metadata = msg.payload.get("metadata", {})
        public_key = msg.payload.get("public_key", "")
        if public_key:
            metadata["public_key"] = public_key

        self._table.upsert(
            DHTEntry(
                peer_id=msg.sender,
                host=host,
                port=port,
                capabilities=capabilities,
                metadata=metadata,
            )
        )
        self._transport.add_peer(msg.sender, host, port)
        logger.info(
            "DHT: peer %s announced at %s:%d caps=%s",
            msg.sender,
            host,
            port,
            capabilities,
        )

        # Re-broadcast discovery info via PubSub (which handles signature
        # relay correctly) so peers behind different network segments discover
        # each other through intermediate bridge nodes.
        announce_key = f"{msg.sender}:{msg.ts}"
        if announce_key in self._seen_announces:
            return
        self._seen_announces[announce_key] = time.monotonic()
        if len(self._seen_announces) > 500:
            cutoff = time.monotonic() - 120.0
            self._seen_announces = {k: v for k, v in self._seen_announces.items() if v > cutoff}

        if self._pubsub is not None:
            await self._pubsub.publish(
                "dht:peer_discovered",
                {
                    "peer_id": msg.sender,
                    "host": host,
                    "port": port,
                    "capabilities": capabilities,
                },
            )

    async def _handle_peer_discovered(
        self,
        topic: str,
        data: dict[str, Any],
        origin: str,
    ) -> None:
        """Handle a peer discovery event relayed via PubSub."""
        peer_id = data.get("peer_id", "")
        host = data.get("host", "")
        port = data.get("port", 0)
        capabilities = data.get("capabilities", [])
        if not peer_id or peer_id == self._local_peer_id or not host or not port:
            return
        self._table.upsert(
            DHTEntry(
                peer_id=peer_id,
                host=host,
                port=port,
                capabilities=capabilities,
            )
        )
        self._transport.add_peer(peer_id, host, port)
        logger.info(
            "DHT: discovered peer %s at %s:%d via PubSub caps=%s",
            peer_id,
            host,
            port,
            capabilities,
        )

    async def _handle_ping(self, msg: P2PMessage, conn: PeerConnection) -> None:
        pong = P2PMessage(
            type="dht:pong",
            sender=self._local_peer_id,
            payload={"echo": msg.payload.get("nonce", "")},
        )
        await conn.send(pong)

    async def _handle_pong(self, msg: P2PMessage, conn: PeerConnection) -> None:
        self._table.upsert(
            DHTEntry(
                peer_id=msg.sender,
                host=conn.host,
                port=conn.port,
            )
        )
