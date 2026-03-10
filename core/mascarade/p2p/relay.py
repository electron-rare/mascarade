"""Relay protocol for NAT traversal — forwards messages between peers that
cannot connect directly.

Message types:
  relay:connect     — request to open a virtual circuit through the relay
  relay:data        — forward payload from one peer to another via the relay
  relay:disconnect  — tear down a relay circuit
  relay:ack         — acknowledge a relay:connect request
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any

from mascarade.p2p.dht import P2PDHT, DHTEntry
from mascarade.p2p.protocol import P2PMessage
from mascarade.p2p.transport import P2PTransport, PeerConnection

logger = logging.getLogger("mascarade.p2p.relay")

RELAY_CAPABILITY = "p2p-relay"


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class RelayCircuit:
    """A virtual circuit between two peers through this relay."""
    peer_a: str
    peer_b: str
    created: float = field(default_factory=time.monotonic)
    last_active: float = field(default_factory=time.monotonic)


# ---------------------------------------------------------------------------
# P2PRelay — runs on the relay node
# ---------------------------------------------------------------------------

class P2PRelay:
    """Relay service that forwards traffic between peers that cannot reach
    each other directly.  Registers itself in the DHT with the
    ``p2p-relay`` capability so clients can discover it.
    """

    def __init__(
        self,
        *,
        local_peer_id: str,
        transport: P2PTransport,
        dht: P2PDHT | None = None,
    ) -> None:
        self._local_peer_id = local_peer_id
        self._transport = transport
        self._dht = dht
        # circuit_key = frozenset({peer_a, peer_b})
        self._circuits: dict[frozenset[str], RelayCircuit] = {}

        # Register message handlers
        transport.on_message("relay:connect", self._handle_connect)
        transport.on_message("relay:data", self._handle_data)
        transport.on_message("relay:disconnect", self._handle_disconnect)

    # -- public API --

    async def announce(self) -> None:
        """Announce this node as a relay in the DHT."""
        if self._dht:
            await self._dht.announce(capabilities=[RELAY_CAPABILITY])
        logger.info("Relay %s announced", self._local_peer_id)

    @property
    def circuits(self) -> dict[frozenset[str], RelayCircuit]:
        return dict(self._circuits)

    # -- handlers --

    async def _handle_connect(self, msg: P2PMessage, conn: PeerConnection) -> None:
        """Handle relay:connect — create a virtual circuit between sender and
        the requested target peer."""
        target = msg.payload.get("target")
        if not target:
            logger.warning("relay:connect from %s missing target", msg.sender)
            return

        key = frozenset({msg.sender, target})
        self._circuits[key] = RelayCircuit(peer_a=msg.sender, peer_b=target)
        logger.info(
            "Relay circuit created: %s <-> %s (via %s)",
            msg.sender, target, self._local_peer_id,
        )

        # ACK back to the requester
        ack = P2PMessage(
            type="relay:ack",
            sender=self._local_peer_id,
            payload={
                "status": "ok",
                "target": target,
                "relay": self._local_peer_id,
            },
        )
        await conn.send(ack)

    async def _handle_data(self, msg: P2PMessage, conn: PeerConnection) -> None:
        """Handle relay:data — forward the inner payload to the destination."""
        target = msg.payload.get("target")
        if not target:
            logger.warning("relay:data from %s missing target", msg.sender)
            return

        key = frozenset({msg.sender, target})
        circuit = self._circuits.get(key)
        if not circuit:
            # Auto-create circuit on first data if we know both peers
            circuit = RelayCircuit(peer_a=msg.sender, peer_b=target)
            self._circuits[key] = circuit
            logger.debug("Auto-created relay circuit %s <-> %s", msg.sender, target)

        circuit.last_active = time.monotonic()

        # Build forwarded message — preserve original sender and inner payload
        forwarded = P2PMessage(
            type="relay:data",
            sender=self._local_peer_id,
            payload={
                "origin": msg.sender,
                "target": target,
                "inner_type": msg.payload.get("inner_type", ""),
                "inner_payload": msg.payload.get("inner_payload", {}),
            },
        )

        ok = await self._transport.send_to(target, forwarded)
        if ok:
            logger.debug("Relayed data %s -> %s", msg.sender, target)
        else:
            logger.warning("Failed to relay data %s -> %s", msg.sender, target)

    async def _handle_disconnect(self, msg: P2PMessage, conn: PeerConnection) -> None:
        """Handle relay:disconnect — tear down the circuit."""
        target = msg.payload.get("target")
        if not target:
            return

        key = frozenset({msg.sender, target})
        removed = self._circuits.pop(key, None)
        if removed:
            logger.info("Relay circuit torn down: %s <-> %s", msg.sender, target)


# ---------------------------------------------------------------------------
# RelayClient — used by peers that need to reach others via a relay
# ---------------------------------------------------------------------------

class RelayClient:
    """Helper for peers that need to send messages through a relay node
    when direct connections fail.
    """

    def __init__(
        self,
        *,
        local_peer_id: str,
        transport: P2PTransport,
        dht: P2PDHT | None = None,
    ) -> None:
        self._local_peer_id = local_peer_id
        self._transport = transport
        self._dht = dht
        # Cache of relay peer IDs we've successfully used
        self._known_relays: list[str] = []
        # target_peer_id -> relay_peer_id
        self._relay_routes: dict[str, str] = {}

        # Listen for relay:ack and relay:data (incoming relayed messages)
        transport.on_message("relay:ack", self._handle_ack)
        transport.on_message("relay:data", self._handle_relay_data)

        # Callbacks for receiving relayed data
        self._data_handlers: dict[str, Any] = {}
        self._default_data_handler: Any = None

    def on_relayed_message(self, inner_type: str, handler: Any) -> None:
        """Register a handler for relayed messages of a given inner type."""
        self._data_handlers[inner_type] = handler

    def on_relayed_default(self, handler: Any) -> None:
        """Register a default handler for relayed messages."""
        self._default_data_handler = handler

    async def find_relay(self) -> str | None:
        """Discover a relay peer via DHT capabilities."""
        if self._known_relays:
            return self._known_relays[0]

        if not self._dht:
            return None

        entries = self._dht.routing_table.find_by_capability(RELAY_CAPABILITY)
        for entry in entries:
            if entry.peer_id != self._local_peer_id:
                self._known_relays.append(entry.peer_id)
                return entry.peer_id

        return None

    def add_known_relay(self, relay_peer_id: str) -> None:
        """Manually register a known relay peer."""
        if relay_peer_id not in self._known_relays:
            self._known_relays.insert(0, relay_peer_id)

    async def connect_via_relay(
        self, target_peer_id: str, relay_peer_id: str | None = None,
    ) -> bool:
        """Request a relay circuit to *target_peer_id*.

        If *relay_peer_id* is not given, try to discover one via DHT.
        """
        if not relay_peer_id:
            relay_peer_id = await self.find_relay()
        if not relay_peer_id:
            logger.warning("No relay available for %s", target_peer_id)
            return False

        msg = P2PMessage(
            type="relay:connect",
            sender=self._local_peer_id,
            payload={"target": target_peer_id},
        )
        ok = await self._transport.send_to(relay_peer_id, msg)
        if ok:
            self._relay_routes[target_peer_id] = relay_peer_id
            logger.info(
                "Requested relay circuit to %s via %s", target_peer_id, relay_peer_id,
            )
        return ok

    async def send_via_relay(
        self,
        target_peer_id: str,
        inner_type: str,
        inner_payload: dict[str, Any],
        relay_peer_id: str | None = None,
    ) -> bool:
        """Send a message to *target_peer_id* through the relay."""
        if not relay_peer_id:
            relay_peer_id = self._relay_routes.get(target_peer_id)
        if not relay_peer_id:
            relay_peer_id = await self.find_relay()
        if not relay_peer_id:
            logger.warning("No relay route to %s", target_peer_id)
            return False

        msg = P2PMessage(
            type="relay:data",
            sender=self._local_peer_id,
            payload={
                "target": target_peer_id,
                "inner_type": inner_type,
                "inner_payload": inner_payload,
            },
        )
        ok = await self._transport.send_to(relay_peer_id, msg)
        if ok:
            self._relay_routes[target_peer_id] = relay_peer_id
        return ok

    async def disconnect_via_relay(self, target_peer_id: str) -> bool:
        """Tear down a relay circuit."""
        relay_peer_id = self._relay_routes.pop(target_peer_id, None)
        if not relay_peer_id:
            return False

        msg = P2PMessage(
            type="relay:disconnect",
            sender=self._local_peer_id,
            payload={"target": target_peer_id},
        )
        return await self._transport.send_to(relay_peer_id, msg)

    # -- internal handlers --

    async def _handle_ack(self, msg: P2PMessage, conn: PeerConnection) -> None:
        target = msg.payload.get("target", "")
        relay = msg.payload.get("relay", msg.sender)
        logger.info("Relay ACK: circuit to %s via %s", target, relay)
        if target:
            self._relay_routes[target] = relay

    async def _handle_relay_data(self, msg: P2PMessage, conn: PeerConnection) -> None:
        """Receive data forwarded through the relay."""
        origin = msg.payload.get("origin", msg.sender)
        inner_type = msg.payload.get("inner_type", "")
        inner_payload = msg.payload.get("inner_payload", {})

        handler = self._data_handlers.get(inner_type) or self._default_data_handler
        if handler:
            # Build a synthetic P2PMessage for the handler
            inner_msg = P2PMessage(
                type=inner_type,
                sender=origin,
                payload=inner_payload,
            )
            result = handler(inner_msg, conn)
            if asyncio.iscoroutine(result) or asyncio.isfuture(result):
                await result
        else:
            logger.debug(
                "No handler for relayed message type=%s from %s",
                inner_type, origin,
            )
