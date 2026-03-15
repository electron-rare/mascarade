"""Tests for P2P wire protocol."""

import asyncio
import struct

from mascarade.p2p.protocol import P2PMessage, _HEADER_FMT, read_message, write_message


def test_message_encode_decode():
    msg = P2PMessage(
        type="test",
        sender="QmABC123",
        payload={"key": "value"},
        nonce="abc",
    )
    raw = msg.encode()
    # Should have 4-byte header + JSON body
    (length,) = struct.unpack(_HEADER_FMT, raw[:4])
    body = raw[4:]
    assert len(body) == length

    decoded = P2PMessage.decode(body)
    assert decoded.type == "test"
    assert decoded.sender == "QmABC123"
    assert decoded.payload == {"key": "value"}
    assert decoded.nonce == "abc"


async def test_read_write_message():
    reader = asyncio.StreamReader()
    msg = P2PMessage(
        type="hello",
        sender="QmPeer1",
        payload={"greeting": "hi"},
    )
    raw = msg.encode()
    reader.feed_data(raw)
    reader.feed_eof()

    received = await read_message(reader)
    assert received is not None
    assert received.type == "hello"
    assert received.sender == "QmPeer1"
    assert received.payload == {"greeting": "hi"}


async def test_read_message_eof():
    reader = asyncio.StreamReader()
    reader.feed_eof()
    result = await read_message(reader)
    assert result is None


async def test_write_message_times_out_on_stalled_drain():
    class SlowWriter:
        def __init__(self) -> None:
            self.buffer = []

        def write(self, data):
            self.buffer.append(data)

        async def drain(self):
            await asyncio.sleep(10)

    msg = P2PMessage(type="hello", sender="QmPeer1", payload={"greeting": "hi"})

    ok = await write_message(SlowWriter(), msg)

    assert ok is False
