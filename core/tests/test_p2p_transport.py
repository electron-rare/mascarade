"""Tests for P2P TCP transport — two nodes connecting and exchanging messages."""

import asyncio

from mascarade.p2p.protocol import P2PMessage
from mascarade.p2p.transport import P2PTransport


async def test_two_nodes_connect_and_exchange():
    """Two P2P transport nodes connect via TCP and exchange a message."""
    received = []

    node_a = P2PTransport(local_peer_id="QmNodeA", listen_host="127.0.0.1", listen_port=0)
    node_b = P2PTransport(local_peer_id="QmNodeB", listen_host="127.0.0.1", listen_port=0)

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
