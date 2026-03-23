"""Tests for P2P TCP transport — two nodes connecting and exchanging messages."""

import asyncio

from mascarade.p2p.protocol import P2PMessage
from mascarade.p2p.transport import P2PTransport


async def test_two_nodes_connect_and_exchange():
    """Two P2P transport nodes connect via TCP and exchange a message."""
    received = []

    node_a = P2PTransport(
        local_peer_id="QmNodeA", listen_host="127.0.0.1", listen_port=0
    )
    node_b = P2PTransport(
        local_peer_id="QmNodeB", listen_host="127.0.0.1", listen_port=0
    )

    async def handler(msg: P2PMessage, conn):
        received.append(msg)

    node_b.on_message("ping", handler)

    await node_a.start()
    await node_b.start()

    try:
        # A opens outbound connection to B's listen port
        node_a.add_peer("QmNodeB", "127.0.0.1", node_b.listen_port)

        msg = P2PMessage(type="ping", sender="QmNodeA", payload={"data": "hello"})
        ok = await node_a.send_to("QmNodeB", msg)
        assert ok

        await asyncio.sleep(0.5)

        assert len(received) == 1
        assert received[0].type == "ping"
        assert received[0].sender == "QmNodeA"
        assert received[0].payload == {"data": "hello"}
    finally:
        await node_a.stop()
        await node_b.stop()


async def test_broadcast():
    """Broadcast sends to all peers."""
    received_b = []
    received_c = []

    node_a = P2PTransport(local_peer_id="QmA", listen_host="127.0.0.1", listen_port=0)
    node_b = P2PTransport(local_peer_id="QmB", listen_host="127.0.0.1", listen_port=0)
    node_c = P2PTransport(local_peer_id="QmC", listen_host="127.0.0.1", listen_port=0)

    async def on_b(msg, conn):
        received_b.append(msg)

    async def on_c(msg, conn):
        received_c.append(msg)

    node_b.on_message("announce", on_b)
    node_c.on_message("announce", on_c)

    await node_a.start()
    await node_b.start()
    await node_c.start()

    try:
        node_a.add_peer("QmB", "127.0.0.1", node_b.listen_port)
        node_a.add_peer("QmC", "127.0.0.1", node_c.listen_port)

        msg = P2PMessage(type="announce", sender="QmA", payload={"caps": ["llm"]})
        sent = await node_a.broadcast(msg)
        assert sent == 2

        await asyncio.sleep(0.3)
        assert len(received_b) == 1
        assert len(received_c) == 1
    finally:
        await node_a.stop()
        await node_b.stop()
        await node_c.stop()


async def test_broadcast_skips_hung_peer():
    """Broadcast should return even if one peer send path stalls."""

    class SlowInboundPeer:
        async def send(self, msg):
            await asyncio.sleep(10)
            return True

    class FastInboundPeer:
        async def send(self, msg):
            return True

    node = P2PTransport(local_peer_id="QmA", listen_host="127.0.0.1", listen_port=0)
    node._inbound_peers = {
        "QmSlow": SlowInboundPeer(),
        "QmFast": FastInboundPeer(),
    }

    msg = P2PMessage(type="announce", sender="QmA", payload={"caps": ["llm"]})
    sent = await asyncio.wait_for(node.broadcast(msg), timeout=8.0)

    assert sent == 1


async def test_send_to_prefers_live_inbound_peer_over_stale_outbound():
    """send_to should reuse a live inbound socket when the outbound route is stale."""
    received = []

    node_a = P2PTransport(local_peer_id="QmA", listen_host="127.0.0.1", listen_port=0)
    node_b = P2PTransport(local_peer_id="QmB", listen_host="127.0.0.1", listen_port=0)

    async def on_ping(msg, conn):
        received.append(msg.payload["value"])

    async def on_probe(msg, conn):
        return None

    node_a.on_message("probe", on_probe)
    node_b.on_message("ping", on_ping)

    await node_a.start()
    await node_b.start()

    try:
        node_b.add_peer("QmA", "127.0.0.1", node_a.listen_port)
        ok = await node_b.send_to(
            "QmA", P2PMessage(type="probe", sender="QmB", payload={})
        )
        assert ok
        await asyncio.sleep(0.2)

        assert "QmB" in node_a._inbound_peers

        # Simulate a stale routing-table update that would otherwise shadow the
        # healthy inbound socket.
        node_a.add_peer("QmB", "203.0.113.77", 65500)

        ok = await node_a.send_to(
            "QmB",
            P2PMessage(type="ping", sender="QmA", payload={"value": "inbound-ok"}),
        )
        assert ok
        await asyncio.sleep(0.2)

        assert received == ["inbound-ok"]
    finally:
        await node_a.stop()
        await node_b.stop()


async def test_broadcast_prefers_live_inbound_peers_over_stale_outbound():
    """broadcast should fan out over inbound sockets when outbound entries are stale."""
    received_b = []
    received_c = []

    node_a = P2PTransport(local_peer_id="QmA", listen_host="127.0.0.1", listen_port=0)
    node_b = P2PTransport(local_peer_id="QmB", listen_host="127.0.0.1", listen_port=0)
    node_c = P2PTransport(local_peer_id="QmC", listen_host="127.0.0.1", listen_port=0)

    async def on_probe(msg, conn):
        return None

    async def on_broadcast_b(msg, conn):
        received_b.append(msg.payload["value"])

    async def on_broadcast_c(msg, conn):
        received_c.append(msg.payload["value"])

    node_a.on_message("probe", on_probe)
    node_b.on_message("announce", on_broadcast_b)
    node_c.on_message("announce", on_broadcast_c)

    await node_a.start()
    await node_b.start()
    await node_c.start()

    try:
        node_b.add_peer("QmA", "127.0.0.1", node_a.listen_port)
        node_c.add_peer("QmA", "127.0.0.1", node_a.listen_port)
        assert await node_b.send_to(
            "QmA", P2PMessage(type="probe", sender="QmB", payload={})
        )
        assert await node_c.send_to(
            "QmA", P2PMessage(type="probe", sender="QmC", payload={})
        )
        await asyncio.sleep(0.2)

        node_a.add_peer("QmB", "203.0.113.10", 65501)
        node_a.add_peer("QmC", "203.0.113.11", 65502)

        sent = await node_a.broadcast(
            P2PMessage(type="announce", sender="QmA", payload={"value": "fanout"})
        )
        assert sent == 2
        await asyncio.sleep(0.2)

        assert received_b == ["fanout"]
        assert received_c == ["fanout"]
    finally:
        await node_a.stop()
        await node_b.stop()
        await node_c.stop()
