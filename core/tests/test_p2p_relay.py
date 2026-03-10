"""Tests for P2P relay protocol — NAT traversal via message forwarding."""

import asyncio

import pytest

from mascarade.p2p.dht import P2PDHT, DHTEntry
from mascarade.p2p.protocol import P2PMessage
from mascarade.p2p.relay import P2PRelay, RelayClient, RELAY_CAPABILITY
from mascarade.p2p.transport import P2PTransport


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _make_node(peer_id: str) -> P2PTransport:
    t = P2PTransport(local_peer_id=peer_id, listen_host="127.0.0.1", listen_port=0)
    await t.start()
    return t


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_relay_forward():
    """A sends a message to B through Relay.  B is only bootstrapped to
    Relay, NOT directly connected to A."""

    # Create three nodes
    node_a = await _make_node("QmA")
    node_relay = await _make_node("QmRelay")
    node_b = await _make_node("QmB")

    received_at_b = []

    try:
        # Wire up: A knows Relay, Relay knows B.  A does NOT know B directly.
        node_a.add_peer("QmRelay", "127.0.0.1", node_relay.listen_port)
        node_relay.add_peer("QmB", "127.0.0.1", node_b.listen_port)
        # Relay also knows A so it can forward replies
        node_relay.add_peer("QmA", "127.0.0.1", node_a.listen_port)

        # Set up relay service on the relay node
        relay = P2PRelay(
            local_peer_id="QmRelay",
            transport=node_relay,
        )

        # Set up relay client on A
        client_a = RelayClient(
            local_peer_id="QmA",
            transport=node_a,
        )
        client_a.add_known_relay("QmRelay")

        # Set up relay client on B to receive relayed messages
        client_b = RelayClient(
            local_peer_id="QmB",
            transport=node_b,
        )

        async def on_hello(msg: P2PMessage, conn):
            received_at_b.append(msg)

        client_b.on_relayed_message("hello", on_hello)

        # A requests a circuit to B through Relay
        ok = await client_a.connect_via_relay("QmB", relay_peer_id="QmRelay")
        assert ok

        await asyncio.sleep(0.3)

        # A sends data to B through Relay
        ok = await client_a.send_via_relay(
            "QmB",
            inner_type="hello",
            inner_payload={"text": "hi from A"},
        )
        assert ok

        await asyncio.sleep(0.5)

        # B should have received the relayed message
        assert len(received_at_b) == 1
        assert received_at_b[0].type == "hello"
        assert received_at_b[0].sender == "QmA"
        assert received_at_b[0].payload == {"text": "hi from A"}

        # Verify the relay created a circuit
        assert len(relay.circuits) >= 1

    finally:
        await node_a.stop()
        await node_relay.stop()
        await node_b.stop()


@pytest.mark.asyncio
async def test_relay_discovery():
    """A discovers the relay via DHT capabilities."""

    node_a = await _make_node("QmA")
    node_relay = await _make_node("QmRelay")

    try:
        # Wire A <-> Relay
        node_a.add_peer("QmRelay", "127.0.0.1", node_relay.listen_port)
        node_relay.add_peer("QmA", "127.0.0.1", node_a.listen_port)

        # Set up DHT on A (no bootstrap — we inject entries manually)
        dht_a = P2PDHT(
            local_peer_id="QmA",
            transport=node_a,
        )
        # Manually insert Relay with the relay capability
        dht_a.routing_table.upsert(DHTEntry(
            peer_id="QmRelay",
            host="127.0.0.1",
            port=node_relay.listen_port,
            capabilities=[RELAY_CAPABILITY],
        ))

        # Relay client on A with DHT
        client_a = RelayClient(
            local_peer_id="QmA",
            transport=node_a,
            dht=dht_a,
        )

        # find_relay should discover QmRelay via the capability
        relay_id = await client_a.find_relay()
        assert relay_id == "QmRelay"

        # It should be cached now
        assert "QmRelay" in client_a._known_relays

    finally:
        await node_a.stop()
        await node_relay.stop()


@pytest.mark.asyncio
async def test_relay_disconnect():
    """Clean teardown of a relay circuit."""

    node_a = await _make_node("QmA")
    node_relay = await _make_node("QmRelay")
    node_b = await _make_node("QmB")

    try:
        node_a.add_peer("QmRelay", "127.0.0.1", node_relay.listen_port)
        node_relay.add_peer("QmB", "127.0.0.1", node_b.listen_port)
        node_relay.add_peer("QmA", "127.0.0.1", node_a.listen_port)

        relay = P2PRelay(
            local_peer_id="QmRelay",
            transport=node_relay,
        )
        client_a = RelayClient(
            local_peer_id="QmA",
            transport=node_a,
        )
        client_a.add_known_relay("QmRelay")

        # Create circuit
        ok = await client_a.connect_via_relay("QmB", relay_peer_id="QmRelay")
        assert ok
        await asyncio.sleep(0.3)
        assert len(relay.circuits) == 1

        # Disconnect
        ok = await client_a.disconnect_via_relay("QmB")
        assert ok
        await asyncio.sleep(0.3)

        # Circuit should be torn down
        assert len(relay.circuits) == 0

    finally:
        await node_a.stop()
        await node_relay.stop()
        await node_b.stop()


@pytest.mark.asyncio
async def test_transport_send_to_via_relay():
    """send_to_via_relay on P2PTransport forwards through the relay."""

    node_a = await _make_node("QmA")
    node_relay = await _make_node("QmRelay")
    node_b = await _make_node("QmB")

    received_at_b = []

    try:
        node_a.add_peer("QmRelay", "127.0.0.1", node_relay.listen_port)
        node_relay.add_peer("QmB", "127.0.0.1", node_b.listen_port)
        node_relay.add_peer("QmA", "127.0.0.1", node_a.listen_port)

        relay = P2PRelay(
            local_peer_id="QmRelay",
            transport=node_relay,
        )
        client_a = RelayClient(
            local_peer_id="QmA",
            transport=node_a,
        )
        client_a.add_known_relay("QmRelay")
        node_a.set_relay_client(client_a)

        client_b = RelayClient(
            local_peer_id="QmB",
            transport=node_b,
        )

        async def on_ping(msg, conn):
            received_at_b.append(msg)

        client_b.on_relayed_message("ping", on_ping)

        # Use the transport-level relay method
        msg = P2PMessage(type="ping", sender="QmA", payload={"v": 1})
        ok = await node_a.send_to_via_relay("QmB", msg, relay_peer_id="QmRelay")
        assert ok

        await asyncio.sleep(0.5)

        assert len(received_at_b) == 1
        assert received_at_b[0].type == "ping"
        assert received_at_b[0].payload == {"v": 1}

    finally:
        await node_a.stop()
        await node_relay.stop()
        await node_b.stop()
