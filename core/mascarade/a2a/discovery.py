"""A2A Discovery — find agents on the network."""
from __future__ import annotations
import logging, time
from typing import Any
import httpx

logger = logging.getLogger("mascarade.a2a.discovery")

class A2ADiscovery:
    def __init__(self, known_peers: list[str] | None = None, cache_ttl: int = 300):
        self._peers = known_peers or []
        self._cache: dict[str, dict] = {}
        self._cache_ts: dict[str, float] = {}
        self._ttl = cache_ttl

    def add_peer(self, url: str) -> None:
        if url not in self._peers:
            self._peers.append(url)

    async def discover(self) -> list[dict]:
        agents = []
        for peer in self._peers:
            card = await self._fetch_card(peer)
            if card:
                agents.append(card)
        return agents

    async def _fetch_card(self, peer_url: str) -> dict | None:
        if peer_url in self._cache and time.time() - self._cache_ts.get(peer_url, 0) < self._ttl:
            return self._cache[peer_url]
        try:
            async with httpx.AsyncClient(timeout=5.0) as c:
                r = await c.get(f"{peer_url}/.well-known/agent.json")
                r.raise_for_status()
                card = r.json()
                self._cache[peer_url] = card
                self._cache_ts[peer_url] = time.time()
                return card
        except Exception as e:
            logger.debug("Failed to discover %s: %s", peer_url, e)
            return None
