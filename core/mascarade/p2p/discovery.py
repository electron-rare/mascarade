"""Multi-strategy peer discovery: mDNS (LAN) + DHT (WAN) + static bootstrap."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any

from mascarade.p2p.dht import P2PDHT

logger = logging.getLogger("mascarade.p2p.discovery")


@dataclass
class DiscoveredPeer:
    peer_id: str
    host: str
    port: int
    source: str  # "mdns", "dht", "static", "gossip"
    capabilities: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    last_seen: float = 0.0
    http_base_url: str | None = None


class P2PDiscovery:
    """Unified discovery that merges results from mDNS, DHT, and static peers."""

    def __init__(self, *, dht: P2PDHT, local_peer_id: str) -> None:
        self._dht = dht
        self._local_peer_id = local_peer_id
        self._known_peers: dict[str, DiscoveredPeer] = {}
        self._static_peers: list[DiscoveredPeer] = []

    def add_static_peer(
        self,
        peer_id: str,
        host: str,
        port: int,
        *,
        http_base_url: str | None = None,
    ) -> None:
        peer = DiscoveredPeer(
            peer_id=peer_id,
            host=host,
            port=port,
            source="static",
            last_seen=time.monotonic(),
            http_base_url=http_base_url,
        )
        self._static_peers.append(peer)
        self._known_peers[peer_id] = peer

    def add_mdns_peer(
        self,
        peer_id: str,
        host: str,
        port: int,
        *,
        capabilities: list[str] | None = None,
        http_base_url: str | None = None,
    ) -> None:
        existing = self._known_peers.get(peer_id)
        if existing and existing.source == "static":
            existing.last_seen = time.monotonic()
            return

        peer = DiscoveredPeer(
            peer_id=peer_id,
            host=host,
            port=port,
            source="mdns",
            capabilities=capabilities or [],
            last_seen=time.monotonic(),
            http_base_url=http_base_url,
        )
        self._known_peers[peer_id] = peer

    async def discover(self) -> list[DiscoveredPeer]:
        dht_entries = self._dht.routing_table.all_entries()
        for entry in dht_entries:
            if entry.peer_id == self._local_peer_id:
                continue
            existing = self._known_peers.get(entry.peer_id)
            if existing and existing.source in ("static", "mdns"):
                existing.capabilities = entry.capabilities or existing.capabilities
                continue

            self._known_peers[entry.peer_id] = DiscoveredPeer(
                peer_id=entry.peer_id,
                host=entry.host,
                port=entry.port,
                source="dht",
                capabilities=entry.capabilities,
                metadata=entry.metadata,
                last_seen=entry.last_seen,
            )

        return list(self._known_peers.values())

    def find_by_capability(self, capability: str) -> list[DiscoveredPeer]:
        return [
            p for p in self._known_peers.values()
            if capability in p.capabilities
        ]

    def get_peer(self, peer_id: str) -> DiscoveredPeer | None:
        return self._known_peers.get(peer_id)

    @property
    def peer_count(self) -> int:
        return len(self._known_peers)

    def all_peers(self) -> list[DiscoveredPeer]:
        return list(self._known_peers.values())
