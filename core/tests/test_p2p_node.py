"""Integration test — MascaradeP2PNode instances discover each other."""

import asyncio
import tempfile

from mascarade.p2p.asyncio_node import MascaradeP2PNode


async def test_two_nodes_discover_and_exchange_capabilities():
    """Two nodes start, discover via bootstrap, exchange capabilities."""
    with tempfile.TemporaryDirectory() as dir_a, tempfile.TemporaryDirectory() as dir_b:
        node_a = MascaradeP2PNode(
            listen_host="127.0.0.1",
            listen_port=0,
            key_dir=dir_a,
        )
        await node_a.start()

        node_b = MascaradeP2PNode(
            listen_host="127.0.0.1",
            listen_port=0,
            key_dir=dir_b,
            bootstrap_peers=[
                (node_a.peer_id, "127.0.0.1", node_a.transport.listen_port)
            ],
        )
        await node_b.start()

        try:
            assert node_a.peer_id != node_b.peer_id
            await asyncio.sleep(1.5)

            await node_a.advertise_capabilities(
                capabilities=["llm-inference", "gpu"],
                providers=["claude"],
                role="gpu",
                label="GPU Node",
            )
            await asyncio.sleep(0.5)

            caps = node_b.capabilities.all_capabilities()
            assert node_a.peer_id in caps
            assert "llm-inference" in caps[node_a.peer_id].capabilities
            assert caps[node_a.peer_id].role == "gpu"

            await node_b.advertise_capabilities(
                capabilities=["mcp-host"],
                role="worker",
            )
            await asyncio.sleep(0.5)

            caps_a = node_a.capabilities.all_capabilities()
            assert node_b.peer_id in caps_a
            assert "mcp-host" in caps_a[node_b.peer_id].capabilities
        finally:
            await node_a.stop()
            await node_b.stop()


async def test_find_capable_peers():
    """Search for peers with a specific capability."""
    with tempfile.TemporaryDirectory() as dir_a, tempfile.TemporaryDirectory() as dir_b:
        node_a = MascaradeP2PNode(
            listen_host="127.0.0.1",
            listen_port=0,
            key_dir=dir_a,
        )
        await node_a.start()

        node_b = MascaradeP2PNode(
            listen_host="127.0.0.1",
            listen_port=0,
            key_dir=dir_b,
            bootstrap_peers=[
                (node_a.peer_id, "127.0.0.1", node_a.transport.listen_port)
            ],
        )
        await node_b.start()

        try:
            await asyncio.sleep(1.5)
            await node_a.advertise_capabilities(capabilities=["llm-inference"])
            await asyncio.sleep(0.5)

            peers = await node_b.find_capable_peers("llm-inference")
            assert len(peers) >= 1
            assert any(p.peer_id == node_a.peer_id for p in peers)

            empty = await node_b.find_capable_peers("quantum-computing")
            assert len(empty) == 0
        finally:
            await node_a.stop()
            await node_b.stop()


async def test_three_node_mesh():
    """Three nodes form a mesh and exchange capabilities."""
    with (
        tempfile.TemporaryDirectory() as da,
        tempfile.TemporaryDirectory() as db,
        tempfile.TemporaryDirectory() as dc,
    ):
        a = MascaradeP2PNode(listen_host="127.0.0.1", listen_port=0, key_dir=da)
        await a.start()

        b = MascaradeP2PNode(
            listen_host="127.0.0.1",
            listen_port=0,
            key_dir=db,
            bootstrap_peers=[(a.peer_id, "127.0.0.1", a.transport.listen_port)],
        )
        await b.start()

        c = MascaradeP2PNode(
            listen_host="127.0.0.1",
            listen_port=0,
            key_dir=dc,
            bootstrap_peers=[(a.peer_id, "127.0.0.1", a.transport.listen_port)],
        )
        await c.start()

        try:
            await asyncio.sleep(1.5)

            await a.advertise_capabilities(capabilities=["llm"], role="gpu")
            await b.advertise_capabilities(capabilities=["kicad"], role="worker")
            await c.advertise_capabilities(capabilities=["gateway"], role="gateway")
            await asyncio.sleep(1.0)

            # Each node should see the other two
            for node in [a, b, c]:
                caps = node.capabilities.all_capabilities()
                assert (
                    len(caps) >= 2
                ), f"Node {node.peer_id[:10]} sees only {len(caps)} caps"

            # Capability search
            llm_peers = await c.find_capable_peers("llm")
            assert any(p.peer_id == a.peer_id for p in llm_peers)
        finally:
            await a.stop()
            await b.stop()
            await c.stop()
