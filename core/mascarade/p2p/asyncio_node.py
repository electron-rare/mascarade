"""MascaradeP2PNode — top-level entry point that wires all P2P components."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any

from mascarade.p2p.capabilities import P2PCapabilityExchange
from mascarade.p2p.dht import P2PDHT
from mascarade.p2p.discovery import P2PDiscovery
from mascarade.p2p.events import (
    EVENT_CAPABILITY_UPDATE,
    EVENT_HEARTBEAT,
    EVENT_PEER_JOINED,
    EVENT_PEER_LEFT,
    EVENT_TASK_COMPLETED,
    EVENT_TASK_SUBMITTED,
    P2PEvent,
    P2PEventBus,
)
from mascarade.p2p.identity import PeerIdentity
from mascarade.p2p.metrics import P2PMetricsCollector, P2PNodeMetrics
from mascarade.p2p.pubsub import P2PPubSub
from mascarade.p2p.stream_forward import P2PStreamForwarder
from mascarade.p2p.tasks import P2PTaskDistribution
from mascarade.p2p.transport import P2PTransport

logger = logging.getLogger("mascarade.p2p.node")


class MascaradeP2PNode:
    """Full P2P node with identity, transport, DHT, PubSub, capabilities, and tasks."""

    def __init__(
        self,
        *,
        listen_host: str = "0.0.0.0",
        listen_port: int = 4001,
        key_dir: str | Path | None = None,
        bootstrap_peers: list[tuple[str, str, int]] | None = None,
    ) -> None:
        self._identity = PeerIdentity.load_or_generate(key_dir)
        self._transport = P2PTransport(
            local_peer_id=self._identity.peer_id,
            listen_host=listen_host,
            listen_port=listen_port,
        )
        self._dht = P2PDHT(
            local_peer_id=self._identity.peer_id,
            transport=self._transport,
            bootstrap_peers=bootstrap_peers,
        )
        self._pubsub = P2PPubSub(
            local_peer_id=self._identity.peer_id,
            transport=self._transport,
        )
        self._discovery = P2PDiscovery(
            dht=self._dht,
            local_peer_id=self._identity.peer_id,
        )
        self._capabilities = P2PCapabilityExchange(
            local_peer_id=self._identity.peer_id,
            pubsub=self._pubsub,
            dht=self._dht,
        )
        self._tasks = P2PTaskDistribution(
            local_peer_id=self._identity.peer_id,
            pubsub=self._pubsub,
            capability_exchange=self._capabilities,
        )
        self._forwarder = P2PStreamForwarder(
            local_peer_id=self._identity.peer_id,
            transport=self._transport,
        )
        self._metrics = P2PMetricsCollector(self._identity.peer_id)
        self._event_bus = P2PEventBus()
        self._heartbeat_task: asyncio.Task | None = None
        self._running = False
        self._known_peers: set[str] = set()

    # --- Properties ---

    @property
    def peer_id(self) -> str:
        return self._identity.peer_id

    @property
    def identity(self) -> PeerIdentity:
        return self._identity

    @property
    def transport(self) -> P2PTransport:
        return self._transport

    @property
    def dht(self) -> P2PDHT:
        return self._dht

    @property
    def pubsub(self) -> P2PPubSub:
        return self._pubsub

    @property
    def discovery(self) -> P2PDiscovery:
        return self._discovery

    @property
    def capabilities(self) -> P2PCapabilityExchange:
        return self._capabilities

    @property
    def tasks(self) -> P2PTaskDistribution:
        return self._tasks

    @property
    def forwarder(self) -> P2PStreamForwarder:
        return self._forwarder

    @property
    def metrics(self) -> P2PMetricsCollector:
        return self._metrics

    @property
    def running(self) -> bool:
        return self._running

    @property
    def events(self) -> P2PEventBus:
        return self._event_bus

    # --- Lifecycle ---

    async def start(self) -> None:
        logger.info("Starting P2P node %s on port %d", self.peer_id, self._transport.listen_port)
        await self._transport.start()
        await self._dht.bootstrap()
        # Request capabilities from existing peers so we catch up on what we missed
        await self._capabilities.request_all()
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
        self._running = True
        logger.info(
            "P2P node %s started — listening on :%d, %d bootstrap peers",
            self.peer_id,
            self._transport.listen_port,
            len(self._dht.routing_table),
        )

    async def stop(self) -> None:
        self._running = False
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass
        await self._transport.stop()
        logger.info("P2P node %s stopped", self.peer_id)

    # --- High-level API ---

    async def advertise_capabilities(
        self,
        capabilities: list[str],
        *,
        providers: list[str] | None = None,
        provider_models: dict[str, list[str]] | None = None,
        role: str = "general",
        label: str = "",
        http_base_url: str | None = None,
    ) -> int:
        result = await self._capabilities.advertise_capabilities(
            capabilities=capabilities,
            providers=providers,
            provider_models=provider_models,
            role=role,
            label=label,
            http_base_url=http_base_url,
        )
        self._event_bus.emit(P2PEvent(
            type=EVENT_CAPABILITY_UPDATE,
            data={
                "peer_id": self.peer_id,
                "capabilities": capabilities,
                "role": role,
                "label": label,
            },
        ))
        return result

    async def discover_peers(self) -> list:
        return await self._discovery.discover()

    async def find_capable_peers(self, capability: str) -> list:
        return await self._capabilities.request_capability(capability)

    async def distribute_task(
        self,
        payload: dict[str, Any],
        capability: str,
        *,
        task_id: str | None = None,
        timeout: float = 300.0,
        target_peer: str | None = None,
    ):
        self._event_bus.emit(P2PEvent(
            type=EVENT_TASK_SUBMITTED,
            data={
                "task_id": task_id,
                "capability": capability,
                "target_peer": target_peer,
            },
        ))
        result = await self._tasks.distribute_task(
            task_id=task_id,
            payload=payload,
            capability=capability,
            timeout=timeout,
            target_peer=target_peer,
        )
        self._event_bus.emit(P2PEvent(
            type=EVENT_TASK_COMPLETED,
            data={
                "task_id": task_id,
                "capability": capability,
                "target_peer": target_peer,
            },
        ))
        return result

    def set_stream_handler(self, protocol: str, handler: Any) -> None:
        self._transport.on_message(protocol, handler)

    async def send_request(self, peer_id: str, protocol: str, data: bytes) -> None:
        from mascarade.p2p.protocol import P2PMessage
        msg = P2PMessage(
            type=protocol,
            sender=self.peer_id,
            payload={"data": data.decode("utf-8", errors="replace")},
        )
        await self._transport.send_to(peer_id, msg)

    def set_task_handler(self, handler: Any) -> None:
        """Set the handler for incoming distributed tasks.

        Handler signature: async def handler(payload: dict, capability: str) -> dict
        """
        self._tasks.set_task_handler(handler)

    def add_peer(self, peer_id: str, host: str, port: int) -> None:
        self._transport.add_peer(peer_id, host, port)

    def status(self) -> dict:
        """Return a metrics snapshot as a dict."""
        connected = sum(1 for c in self._transport.peers.values() if c.connected)
        dht_count = len(self._dht.routing_table)
        caps_count = len(self._capabilities.all_capabilities())
        topics = list(self._pubsub._subscriptions.keys())
        peer_details = []
        for pid, c in self._capabilities.all_capabilities().items():
            peer_details.append({
                "peer_id": pid,
                "label": c.label,
                "role": c.role,
                "capabilities": c.capabilities,
                "http_base_url": c.http_base_url,
            })
        self._metrics.update_gauges(connected, dht_count, caps_count)
        snap = self._metrics.snapshot(
            connected_peers=connected,
            dht_entries=dht_count,
            capabilities_known=caps_count,
            pubsub_topics=topics,
            peer_details=peer_details,
        )
        return snap.__dict__

    # --- Internals ---

    async def _heartbeat_loop(self) -> None:
        while self._running:
            try:
                await asyncio.sleep(30)
                if not self._running:
                    break
                # Re-announce to DHT + PubSub
                if self._capabilities._local_caps:
                    caps = self._capabilities._local_caps
                    await self._capabilities.advertise_capabilities(
                        capabilities=caps.capabilities,
                        providers=caps.providers,
                        provider_models=caps.provider_models,
                        role=caps.role,
                        label=caps.label,
                        http_base_url=caps.http_base_url,
                    )
                # Discover new peers via DHT
                await self._dht.find_node(self.peer_id)
                # Update Prometheus gauges
                connected = sum(1 for c in self._transport.peers.values() if c.connected)
                self._metrics.update_gauges(
                    connected_peers=connected,
                    dht_entries=len(self._dht.routing_table),
                    capabilities_known=len(self._capabilities.all_capabilities()),
                )
                # Detect peer joins/leaves and emit events
                current_peers = {
                    pid for pid, c in self._transport.peers.items() if c.connected
                }
                for pid in current_peers - self._known_peers:
                    self._event_bus.emit(P2PEvent(
                        type=EVENT_PEER_JOINED,
                        data={"peer_id": pid},
                    ))
                for pid in self._known_peers - current_peers:
                    self._event_bus.emit(P2PEvent(
                        type=EVENT_PEER_LEFT,
                        data={"peer_id": pid},
                    ))
                self._known_peers = current_peers
                # Heartbeat event for SSE keep-alive
                self._event_bus.emit(P2PEvent(
                    type=EVENT_HEARTBEAT,
                    data={"connected_peers": connected},
                ))
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("Heartbeat error")
