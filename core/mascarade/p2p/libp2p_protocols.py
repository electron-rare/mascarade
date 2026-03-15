"""Stream protocol definitions for Mascarade P2P.

Each protocol uses length-prefixed framing: 4-byte big-endian length + payload.
"""

from __future__ import annotations

import json
import struct
import logging

from libp2p.custom_types import TProtocol
from libp2p.network.stream.net_stream import INetStream

logger = logging.getLogger("mascarade.p2p.protocols")

IDENTITY_PROTOCOL = TProtocol("/mascarade/identity/1.0.0")
SEND_PROTOCOL = TProtocol("/mascarade/send/1.0.0")

MAX_MSG_BYTES = 16 * 1024 * 1024  # 16 MiB
HEADER_SIZE = 4


async def write_msg(stream: INetStream, data: dict) -> None:
    """Write a length-prefixed JSON message to a stream."""
    payload = json.dumps(data).encode("utf-8")
    header = struct.pack(">I", len(payload))
    await stream.write(header + payload)


async def read_msg(stream: INetStream) -> dict:
    """Read a length-prefixed JSON message from a stream."""
    header = await stream.read(HEADER_SIZE)
    if len(header) < HEADER_SIZE:
        raise ValueError("Incomplete message header")
    length = struct.unpack(">I", header[:HEADER_SIZE])[0]
    if length > MAX_MSG_BYTES:
        raise ValueError(f"Message too large: {length} bytes")
    payload = await stream.read(length)
    if len(payload) < length:
        raise ValueError(f"Incomplete message body: expected {length}, got {len(payload)}")
    return json.loads(payload)
