"""Tests for P2P metrics."""

import asyncio
import tempfile

from mascarade.p2p.asyncio_node import MascaradeP2PNode
from mascarade.p2p.metrics import P2PMetricsCollector, P2PNodeMetrics
from mascarade.p2p.protocol import P2PMessage
from mascarade.p2p.transport import P2PTransport


def test_metrics_collector_basic():
    mc = P2PMetricsCollector("QmTEST123")
    mc.record_message_sent("dht:ping", 64)
    mc.record_message_sent("pubsub:publish", 256)
    mc.record_message_received("dht:pong", 32)
    mc.record_forward("success", 0.05)
    mc.record_forward("error", 0.0)

    snap = mc.snapshot(connected_peers=3, dht_entries=5, capabilities_known=2)
    assert isinstance(snap, P2PNodeMetrics)
    assert snap.peer_id == "QmTEST123"
    assert snap.messages_sent == 2
    assert snap.messages_received == 1
    assert snap.bytes_sent == 320
    assert snap.bytes_received == 32
    assert snap.forward_requests_total == 2
    assert snap.forward_errors == 1
    assert snap.connected_peers == 3
    assert snap.dht_entries == 5


async def test_node_status():
    """Node.status() returns metrics snapshot."""
    with tempfile.TemporaryDirectory() as d:
        node = MascaradeP2PNode(listen_host="127.0.0.1", listen_port=0, key_dir=d)
        await node.start()

        try:
            status = node.status()
            assert status["peer_id"] == node.peer_id
            assert status["backend"] == "asyncio"
            assert "uptime_seconds" in status
            assert "connected_peers" in status
            assert "dht_entries" in status
            assert isinstance(status["peer_details"], list)
        finally:
            await node.stop()


async def test_transport_metrics_wiring():
    """Transport records sent/received metrics when a collector is provided."""
    mc = P2PMetricsCollector("QmSender")
    received = []

    node_a = P2PTransport(
        local_peer_id="QmSender", listen_host="127.0.0.1", listen_port=0,
        metrics=mc,
    )
    node_b = P2PTransport(
        local_peer_id="QmReceiver", listen_host="127.0.0.1", listen_port=0,
        metrics=P2PMetricsCollector("QmReceiver"),
    )

    async def handler(msg, conn):
        received.append(msg)

    node_b.on_message("ping", handler)

    await node_a.start()
    await node_b.start()

    try:
        node_a.add_peer("QmReceiver", "127.0.0.1", node_b.listen_port)
        msg = P2PMessage(type="ping", sender="QmSender", payload={"v": 1})
        ok = await node_a.send_to("QmReceiver", msg)
        assert ok

        await asyncio.sleep(0.5)

        # Sender should have recorded sent
        assert mc._messages_sent >= 1
        # Receiver should have recorded received
        assert node_b._metrics._messages_received >= 1
    finally:
        await node_a.stop()
        await node_b.stop()


async def test_node_metrics_wired_to_transport():
    """MascaradeP2PNode wires its metrics collector to the transport."""
    with tempfile.TemporaryDirectory() as d:
        node = MascaradeP2PNode(listen_host="127.0.0.1", listen_port=0, key_dir=d)
        # Verify the transport has the metrics collector
        assert node.transport._metrics is node.metrics
        await node.start()
        try:
            # After start, the metrics should be accessible via status
            status = node.status()
            assert "messages_sent" in status
        finally:
            await node.stop()
