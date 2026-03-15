"""Tests for P2P stream forwarding."""

import asyncio
import tempfile

from mascarade.p2p.asyncio_node import MascaradeP2PNode


async def test_stream_forward_between_nodes():
    """Node A sends an LLM request to Node B via P2P, gets response back."""
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

            # Set up request handler on Node A (the "GPU" node)
            async def handle_request(request_data):
                return {
                    "content": f"Response to: {request_data.get('messages', [{}])[-1].get('content', '')}",
                    "model": "test-model",
                    "provider": "test",
                }

            node_a.forwarder.set_request_handler(handle_request)

            # Node B forwards a request to Node A
            result = await node_b.forwarder.forward_request(
                node_a.peer_id,
                {
                    "messages": [{"role": "user", "content": "Hello"}],
                    "model": "test-model",
                },
            )

            assert result["content"] == "Response to: Hello"
            assert result["model"] == "test-model"
            assert "_p2p_meta" in result
            assert result["_p2p_meta"]["peer_id"] == node_a.peer_id

        finally:
            await node_a.stop()
            await node_b.stop()


async def test_stream_forward_timeout():
    """Forward request times out if handler is slow."""
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

            async def slow_handler(request_data):
                await asyncio.sleep(10)
                return {"content": "too late"}

            node_a.forwarder.set_request_handler(slow_handler)

            try:
                await node_b.forwarder.forward_request(
                    node_a.peer_id, {"messages": []}, timeout=0.5,
                )
                assert False, "Should have raised TimeoutError"
            except TimeoutError:
                pass  # Expected

        finally:
            await node_a.stop()
            await node_b.stop()


async def test_stream_forward_error():
    """Forward returns error when handler raises."""
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

            async def error_handler(request_data):
                raise ValueError("GPU out of memory")

            node_a.forwarder.set_request_handler(error_handler)

            try:
                await node_b.forwarder.forward_request(
                    node_a.peer_id, {"messages": []}, timeout=5.0,
                )
                assert False, "Should have raised RuntimeError"
            except RuntimeError as exc:
                assert "GPU out of memory" in str(exc)

        finally:
            await node_a.stop()
            await node_b.stop()


async def test_can_forward():
    """can_forward returns True for connected peers."""
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
            assert node_b.forwarder.can_forward(node_a.peer_id)
            assert not node_b.forwarder.can_forward("QmNONEXISTENTPEER")
        finally:
            await node_a.stop()
            await node_b.stop()
