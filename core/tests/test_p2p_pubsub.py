"""Tests for PubSub relay behaviour."""

import asyncio
from types import SimpleNamespace

from mascarade.p2p.protocol import P2PMessage
from mascarade.p2p.pubsub import P2PPubSub


class _FakeTransport:
    def __init__(self):
        self.peers = {}

    def on_message(self, _msg_type, _handler):
        return None


class _FastPeer:
    def __init__(self, event: asyncio.Event):
        self._event = event

    async def send(self, _msg):
        self._event.set()
        return True


class _SlowPeer:
    async def send(self, _msg):
        await asyncio.sleep(10)
        return True


async def test_handle_publish_does_not_block_on_slow_relays():
    transport = _FakeTransport()
    fast_event = asyncio.Event()
    transport.peers = {
        "QmFast": _FastPeer(fast_event),
        "QmSlow": _SlowPeer(),
    }
    pubsub = P2PPubSub(local_peer_id="QmRelay", transport=transport)

    msg = P2PMessage(
        type="pubsub:publish",
        sender="QmOrigin",
        payload={"topic": "mesh", "data": {"value": "ok"}},
        nonce="nonce-1",
    )

    try:
        await asyncio.wait_for(
            pubsub._handle_publish(msg, SimpleNamespace()),
            timeout=1.0,
        )
        await asyncio.wait_for(fast_event.wait(), timeout=1.0)
    finally:
        for task in list(pubsub._relay_tasks):
            task.cancel()
        if pubsub._relay_tasks:
            await asyncio.gather(*pubsub._relay_tasks, return_exceptions=True)
