"""Capability exchange — advertise and discover what each peer can do."""

from __future__ import annotations

import hashlib
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any

from mascarade.p2p.dht import P2PDHT
from mascarade.p2p.pubsub import P2PPubSub

logger = logging.getLogger("mascarade.p2p.capabilities")

_TOPIC_CAPABILITIES = "mascarade:capabilities"
_TOPIC_CAPABILITY_REQUEST = "mascarade:capability_request"


@dataclass
class PeerCapabilities:
    peer_id: str
    capabilities: list[str] = field(default_factory=list)
    providers: list[str] = field(default_factory=list)
    provider_models: dict[str, list[str]] = field(default_factory=dict)
    role: str = "general"
    label: str = ""
    http_base_url: str | None = None
    last_updated: float = 0.0
    # Hardware profile — advertised by each peer at startup
    gpu_vram_gb: float = 0.0
    chip_family: str = "cpu_only"
    ram_gb: float = 0.0


class P2PCapabilityExchange:
    """Advertise and discover capabilities across the P2P network via PubSub + DHT."""

    def __init__(
        self,
        *,
        local_peer_id: str,
        pubsub: P2PPubSub,
        dht: P2PDHT,
    ) -> None:
        self._local_peer_id = local_peer_id
        self._pubsub = pubsub
        self._dht = dht
        self._peer_caps: dict[str, PeerCapabilities] = {}
        self._local_caps: PeerCapabilities | None = None
        # P-08: Track seen capability hashes to skip replayed/identical updates
        self._seen_capabilities: dict[str, str] = {}  # peer_id -> hash of last update

        pubsub.subscribe(_TOPIC_CAPABILITIES, self._handle_capabilities)
        pubsub.subscribe(_TOPIC_CAPABILITY_REQUEST, self._handle_request)

    async def advertise_capabilities(
        self,
        *,
        capabilities: list[str],
        providers: list[str] | None = None,
        provider_models: dict[str, list[str]] | None = None,
        role: str = "general",
        label: str = "",
        http_base_url: str | None = None,
        gpu_vram_gb: float = 0.0,
        chip_family: str = "cpu_only",
        ram_gb: float = 0.0,
    ) -> int:
        self._local_caps = PeerCapabilities(
            peer_id=self._local_peer_id,
            capabilities=capabilities,
            providers=providers or [],
            provider_models=provider_models or {},
            role=role,
            label=label,
            http_base_url=http_base_url,
            last_updated=time.monotonic(),
            gpu_vram_gb=gpu_vram_gb,
            chip_family=chip_family,
            ram_gb=ram_gb,
        )

        # Announce to DHT too
        await self._dht.announce(
            capabilities=capabilities,
            metadata={
                "providers": providers or [],
                "provider_models": provider_models or {},
                "role": role,
                "label": label,
                "http_base_url": http_base_url or "",
                "gpu_vram_gb": gpu_vram_gb,
                "chip_family": chip_family,
                "ram_gb": ram_gb,
            },
        )

        # Publish to PubSub for gossip
        return await self._pubsub.publish(
            _TOPIC_CAPABILITIES,
            {
                "peer_id": self._local_peer_id,
                "capabilities": capabilities,
                "providers": providers or [],
                "provider_models": provider_models or {},
                "role": role,
                "label": label,
                "http_base_url": http_base_url or "",
                "gpu_vram_gb": gpu_vram_gb,
                "chip_family": chip_family,
                "ram_gb": ram_gb,
            },
        )

    async def request_all(self) -> None:
        """Ask all connected peers to re-announce their capabilities."""
        await self._pubsub.publish(
            _TOPIC_CAPABILITY_REQUEST,
            {
                "requested_by": self._local_peer_id,
                "capability": "*",
            },
        )

    async def request_capability(self, capability: str) -> list[PeerCapabilities]:
        # Check local cache first
        cached = [
            caps for caps in self._peer_caps.values() if capability in caps.capabilities
        ]
        if cached:
            return cached

        # Ask the network
        await self._pubsub.publish(
            _TOPIC_CAPABILITY_REQUEST,
            {
                "requested_by": self._local_peer_id,
                "capability": capability,
            },
        )

        # Also check DHT
        dht_matches = self._dht.routing_table.find_by_capability(capability)
        for entry in dht_matches:
            if entry.peer_id not in self._peer_caps:
                self._peer_caps[entry.peer_id] = PeerCapabilities(
                    peer_id=entry.peer_id,
                    capabilities=entry.capabilities,
                    providers=entry.metadata.get("providers", []),
                    provider_models=entry.metadata.get("provider_models", {}),
                    role=entry.metadata.get("role", "general"),
                    label=entry.metadata.get("label", ""),
                    http_base_url=entry.metadata.get("http_base_url"),
                    last_updated=entry.last_seen,
                    gpu_vram_gb=float(entry.metadata.get("gpu_vram_gb", 0.0)),
                    chip_family=str(entry.metadata.get("chip_family", "cpu_only")),
                    ram_gb=float(entry.metadata.get("ram_gb", 0.0)),
                )

        return [
            caps for caps in self._peer_caps.values() if capability in caps.capabilities
        ]

    def get_peer_capabilities(self, peer_id: str) -> PeerCapabilities | None:
        return self._peer_caps.get(peer_id)

    def all_capabilities(self) -> dict[str, PeerCapabilities]:
        return dict(self._peer_caps)

    def prune_stale(self, max_age: float = 300.0) -> int:
        """Remove peer capability entries not updated for longer than *max_age* seconds.

        Fix 2: prevent unbounded growth of _peer_caps for peers that have left
        the network without sending an explicit departure message.
        """
        cutoff = time.monotonic() - max_age
        stale = [
            pid for pid, caps in self._peer_caps.items() if caps.last_updated < cutoff
        ]
        for pid in stale:
            del self._peer_caps[pid]
        if stale:
            logger.debug("Capabilities: pruned %d stale peer entries", len(stale))
        return len(stale)

    def peers_with_provider(self, provider: str) -> list[PeerCapabilities]:
        return [c for c in self._peer_caps.values() if provider in c.providers]

    def peers_with_model(self, provider: str, model: str) -> list[PeerCapabilities]:
        return [
            c
            for c in self._peer_caps.values()
            if model in c.provider_models.get(provider, [])
        ]

    async def _handle_capabilities(
        self,
        topic: str,
        data: dict[str, Any],
        origin: str,
    ) -> None:
        peer_id = data.get("peer_id", origin)
        if peer_id == self._local_peer_id:
            return

        # P-08: Skip replayed/identical capability updates
        cap_hash = hashlib.sha256(
            json.dumps(data, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()[:16]
        if self._seen_capabilities.get(peer_id) == cap_hash:
            logger.debug("Skipping duplicate capability update from %s", peer_id)
            return
        self._seen_capabilities[peer_id] = cap_hash

        # Fix 2: prune stale entries on every incoming update
        self.prune_stale()

        self._peer_caps[peer_id] = PeerCapabilities(
            peer_id=peer_id,
            capabilities=data.get("capabilities", []),
            providers=data.get("providers", []),
            provider_models=data.get("provider_models", {}),
            role=data.get("role", "general"),
            label=data.get("label", ""),
            http_base_url=data.get("http_base_url"),
            last_updated=time.monotonic(),
            gpu_vram_gb=float(data.get("gpu_vram_gb", 0.0)),
            chip_family=str(data.get("chip_family", "cpu_only")),
            ram_gb=float(data.get("ram_gb", 0.0)),
        )
        logger.info(
            "Updated capabilities for peer %s: %s (VRAM=%.1fGB chip=%s)",
            peer_id,
            data.get("capabilities"),
            float(data.get("gpu_vram_gb", 0.0)),
            data.get("chip_family", "cpu_only"),
        )

    async def _handle_request(
        self,
        topic: str,
        data: dict[str, Any],
        origin: str,
    ) -> None:
        capability = data.get("capability", "")
        if not capability or not self._local_caps:
            return

        if capability == "*" or capability in self._local_caps.capabilities:
            await self.advertise_capabilities(
                capabilities=self._local_caps.capabilities,
                providers=self._local_caps.providers,
                provider_models=self._local_caps.provider_models,
                role=self._local_caps.role,
                label=self._local_caps.label,
                http_base_url=self._local_caps.http_base_url,
                gpu_vram_gb=self._local_caps.gpu_vram_gb,
                chip_family=self._local_caps.chip_family,
                ram_gb=self._local_caps.ram_gb,
            )
