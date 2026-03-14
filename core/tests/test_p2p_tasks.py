"""Tests for P2P task distribution."""

import asyncio
import tempfile

from mascarade.p2p.asyncio_node import MascaradeP2PNode
from mascarade.p2p.tasks import TaskStatus


async def test_distribute_task_to_capable_peer():
    """Submit a task from Node B, Node A (with matching capability) executes it."""
    with tempfile.TemporaryDirectory() as da, tempfile.TemporaryDirectory() as db:
        node_a = MascaradeP2PNode(listen_host="127.0.0.1", listen_port=0, key_dir=da)
        await node_a.start()

        node_b = MascaradeP2PNode(
            listen_host="127.0.0.1", listen_port=0, key_dir=db,
            bootstrap_peers=[(node_a.peer_id, "127.0.0.1", node_a.transport.listen_port)],
        )
        await node_b.start()

        try:
            await asyncio.sleep(1.5)

            # Node A advertises llm-inference capability
            await node_a.advertise_capabilities(
                capabilities=["llm-inference", "gpu"], role="gpu",
            )

            # Node A registers a task handler
            async def handle_task(payload, capability):
                assert capability == "llm-inference"
                prompt = payload.get("prompt", "")
                return {"response": f"Processed: {prompt}", "model": "test"}

            node_a.set_task_handler(handle_task)

            await asyncio.sleep(0.5)

            # Node B distributes a task requiring llm-inference
            task = await node_b.distribute_task(
                payload={"prompt": "Hello world"},
                capability="llm-inference",
                timeout=10.0,
            )

            assert task.status == TaskStatus.COMPLETED
            assert task.result is not None
            assert task.result["response"] == "Processed: Hello world"
            assert task.claimed_by == node_a.peer_id

        finally:
            await node_a.stop()
            await node_b.stop()


async def test_distribute_task_targeted():
    """Submit a task targeting a specific peer."""
    with tempfile.TemporaryDirectory() as da, tempfile.TemporaryDirectory() as db:
        node_a = MascaradeP2PNode(listen_host="127.0.0.1", listen_port=0, key_dir=da)
        await node_a.start()

        node_b = MascaradeP2PNode(
            listen_host="127.0.0.1", listen_port=0, key_dir=db,
            bootstrap_peers=[(node_a.peer_id, "127.0.0.1", node_a.transport.listen_port)],
        )
        await node_b.start()

        try:
            await asyncio.sleep(1.5)

            await node_a.advertise_capabilities(capabilities=["compute"], role="gpu")

            async def handle_task(payload, capability):
                return {"result": "targeted-ok"}

            node_a.set_task_handler(handle_task)
            await asyncio.sleep(0.5)

            task = await node_b.distribute_task(
                payload={"data": "test"},
                capability="compute",
                target_peer=node_a.peer_id,
                timeout=10.0,
            )

            assert task.status == TaskStatus.COMPLETED
            assert task.result["result"] == "targeted-ok"

        finally:
            await node_a.stop()
            await node_b.stop()


async def test_distribute_task_handler_error():
    """Task handler raises, submitter gets FAILED status."""
    with tempfile.TemporaryDirectory() as da, tempfile.TemporaryDirectory() as db:
        node_a = MascaradeP2PNode(listen_host="127.0.0.1", listen_port=0, key_dir=da)
        await node_a.start()

        node_b = MascaradeP2PNode(
            listen_host="127.0.0.1", listen_port=0, key_dir=db,
            bootstrap_peers=[(node_a.peer_id, "127.0.0.1", node_a.transport.listen_port)],
        )
        await node_b.start()

        try:
            await asyncio.sleep(1.5)

            await node_a.advertise_capabilities(capabilities=["failing-cap"], role="worker")

            async def bad_handler(payload, capability):
                raise RuntimeError("GPU exploded")

            node_a.set_task_handler(bad_handler)
            await asyncio.sleep(0.5)

            task = await node_b.distribute_task(
                payload={},
                capability="failing-cap",
                timeout=10.0,
            )

            assert task.status == TaskStatus.FAILED
            assert "GPU exploded" in (task.error or "")

        finally:
            await node_a.stop()
            await node_b.stop()


async def test_distribute_task_timeout():
    """Task times out if no capable peer claims it."""
    with tempfile.TemporaryDirectory() as da, tempfile.TemporaryDirectory() as db:
        node_a = MascaradeP2PNode(listen_host="127.0.0.1", listen_port=0, key_dir=da)
        await node_a.start()

        node_b = MascaradeP2PNode(
            listen_host="127.0.0.1", listen_port=0, key_dir=db,
            bootstrap_peers=[(node_a.peer_id, "127.0.0.1", node_a.transport.listen_port)],
        )
        await node_b.start()

        try:
            await asyncio.sleep(1.5)

            # Node A does NOT have the requested capability
            await node_a.advertise_capabilities(capabilities=["other-cap"], role="worker")
            await asyncio.sleep(0.5)

            task = await node_b.distribute_task(
                payload={},
                capability="nonexistent-cap",
                timeout=2.0,
            )

            assert task.status == TaskStatus.TIMEOUT

        finally:
            await node_a.stop()
            await node_b.stop()


async def test_distribute_task_three_nodes():
    """Three nodes: submitter sends task, only the capable peer executes."""
    with (
        tempfile.TemporaryDirectory() as da,
        tempfile.TemporaryDirectory() as db,
        tempfile.TemporaryDirectory() as dc,
    ):
        # Node A: GPU (llm-inference)
        a = MascaradeP2PNode(listen_host="127.0.0.1", listen_port=0, key_dir=da)
        await a.start()

        # Node B: Worker (kicad)
        b = MascaradeP2PNode(
            listen_host="127.0.0.1", listen_port=0, key_dir=db,
            bootstrap_peers=[(a.peer_id, "127.0.0.1", a.transport.listen_port)],
        )
        await b.start()

        # Node C: Submitter
        c = MascaradeP2PNode(
            listen_host="127.0.0.1", listen_port=0, key_dir=dc,
            bootstrap_peers=[(a.peer_id, "127.0.0.1", a.transport.listen_port)],
        )
        await c.start()

        try:
            await asyncio.sleep(1.5)

            await a.advertise_capabilities(capabilities=["llm-inference"], role="gpu")
            await b.advertise_capabilities(capabilities=["kicad"], role="worker")

            executed_by = []

            async def handler_a(payload, capability):
                executed_by.append("a")
                return {"from": "a", "echo": payload.get("msg")}

            async def handler_b(payload, capability):
                executed_by.append("b")
                return {"from": "b", "echo": payload.get("msg")}

            a.set_task_handler(handler_a)
            b.set_task_handler(handler_b)
            await asyncio.sleep(0.5)

            # C requests llm-inference → A should handle it
            task = await c.distribute_task(
                payload={"msg": "hello"},
                capability="llm-inference",
                timeout=10.0,
            )
            assert task.status == TaskStatus.COMPLETED
            assert task.result["from"] == "a"
            assert "a" in executed_by

            # C requests kicad → B should handle it
            executed_by.clear()
            task2 = await c.distribute_task(
                payload={"msg": "validate"},
                capability="kicad",
                timeout=10.0,
            )
            assert task2.status == TaskStatus.COMPLETED
            assert task2.result["from"] == "b"
            assert "b" in executed_by

        finally:
            await a.stop()
            await b.stop()
            await c.stop()
