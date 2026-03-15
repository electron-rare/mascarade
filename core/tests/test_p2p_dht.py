"""Tests for P2P DHT — address validation and routing table."""

import asyncio

import pytest

from mascarade.p2p.dht import P2PDHT, DHTEntry, DHTRoutingTable
from mascarade.p2p.identity import PeerIdentity
from mascarade.p2p.protocol import P2PMessage
from mascarade.p2p.transport import P2PTransport, PeerConnection


async def _make_node() -> tuple[PeerIdentity, P2PTransport]:
    identity = PeerIdentity.generate()
    t = P2PTransport(local_peer_id=identity.peer_id, listen_host="127.0.0.1", listen_port=0)
    t.enable_authentication(identity)
    await t.start()
    return identity, t


@pytest.mark.asyncio
async def test_dht_rejects_invalid_port():
    """Announce with port outside 1-65535 is rejected."""
    identity, transport = await _make_node()
    try:
        dht = P2PDHT(local_peer_id=identity.peer_id, transport=transport)
        fake_conn = PeerConnection(peer_id="QmFake", host="127.0.0.1", port=4001,
                                    connected=False)

        # Port 0
        msg = P2PMessage(
            type="dht:announce", sender="QmFake",
            payload={"host": "127.0.0.1", "port": 0, "capabilities": []},
        )
        await dht._handle_announce(msg, fake_conn)
        assert "QmFake" not in {e.peer_id for e in dht.routing_table.all_entries()}

        # Port > 65535
        msg2 = P2PMessage(
            type="dht:announce", sender="QmFake2",
            payload={"host": "127.0.0.1", "port": 70000, "capabilities": []},
        )
        await dht._handle_announce(msg2, fake_conn)
        assert "QmFake2" not in {e.peer_id for e in dht.routing_table.all_entries()}

        # Port -1
        msg3 = P2PMessage(
            type="dht:announce", sender="QmFake3",
            payload={"host": "127.0.0.1", "port": -1, "capabilities": []},
        )
        await dht._handle_announce(msg3, fake_conn)
        assert "QmFake3" not in {e.peer_id for e in dht.routing_table.all_entries()}
    finally:
        await transport.stop()


@pytest.mark.asyncio
async def test_dht_rejects_spoofed_host():
    """Announce with a routable host that doesn't match conn source is rejected."""
    identity, transport = await _make_node()
    try:
        dht = P2PDHT(local_peer_id=identity.peer_id, transport=transport)
        fake_conn = PeerConnection(peer_id="QmFake", host="10.0.0.1", port=4001,
                                    connected=False)

        msg = P2PMessage(
            type="dht:announce", sender="QmFake",
            payload={"host": "192.168.1.100", "port": 4001, "capabilities": []},
        )
        await dht._handle_announce(msg, fake_conn)
        assert "QmFake" not in {e.peer_id for e in dht.routing_table.all_entries()}
    finally:
        await transport.stop()


@pytest.mark.asyncio
async def test_dht_accepts_valid_announce():
    """Announce with matching host and valid port is accepted."""
    identity, transport = await _make_node()
    try:
        dht = P2PDHT(local_peer_id=identity.peer_id, transport=transport)
        fake_conn = PeerConnection(peer_id="QmGood", host="192.168.0.50", port=4001,
                                    connected=False)

        msg = P2PMessage(
            type="dht:announce", sender="QmGood",
            payload={"host": "192.168.0.50", "port": 4001, "capabilities": ["llm"]},
        )
        await dht._handle_announce(msg, fake_conn)

        entries = {e.peer_id for e in dht.routing_table.all_entries()}
        assert "QmGood" in entries
    finally:
        await transport.stop()


@pytest.mark.asyncio
async def test_dht_accepts_wildcard_host():
    """Announce with 0.0.0.0 host is accepted and resolved to conn.host."""
    identity, transport = await _make_node()
    try:
        dht = P2PDHT(local_peer_id=identity.peer_id, transport=transport)
        fake_conn = PeerConnection(peer_id="QmWild", host="10.0.0.5", port=4001,
                                    connected=False)

        msg = P2PMessage(
            type="dht:announce", sender="QmWild",
            payload={"host": "0.0.0.0", "port": 4001, "capabilities": []},
        )
        await dht._handle_announce(msg, fake_conn)

        entries = {e.peer_id: e for e in dht.routing_table.all_entries()}
        assert "QmWild" in entries
        assert entries["QmWild"].host == "10.0.0.5"  # resolved from conn
    finally:
        await transport.stop()


def test_routing_table_prune_stale():
    """Stale entries beyond max_age are pruned."""
    import time
    rt = DHTRoutingTable("QmLocal")
    rt.upsert(DHTEntry(peer_id="QmOld", host="1.2.3.4", port=4001))

    # Hack last_seen to make it stale
    rt._entries["QmOld"].last_seen = time.monotonic() - 600

    pruned = rt.prune_stale(max_age=300.0)
    assert pruned == 1
    assert len(rt) == 0
