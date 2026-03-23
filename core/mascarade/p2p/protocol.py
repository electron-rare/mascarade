"""Wire protocol for P2P TCP connections — length-prefixed JSON frames."""

from __future__ import annotations

import asyncio
import json
import logging
import struct
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger("mascarade.p2p.protocol")

_HEADER_FMT = "!I"  # 4-byte big-endian unsigned int
_HEADER_SIZE = struct.calcsize(_HEADER_FMT)
_MAX_FRAME_SIZE = 16 * 1024 * 1024  # 16 MiB
_WRITE_TIMEOUT_SECONDS = 5.0


@dataclass
class P2PMessage:
    type: str
    sender: str
    payload: dict[str, Any] = field(default_factory=dict)
    ts: float = field(default_factory=time.time)
    nonce: str = ""
    signature: str = ""
    public_key: str = ""

    def encode(self) -> bytes:
        raw = json.dumps(
            {
                "type": self.type,
                "sender": self.sender,
                "payload": self.payload,
                "ts": self.ts,
                "nonce": self.nonce,
                "signature": self.signature,
                "public_key": self.public_key,
            },
            separators=(",", ":"),
        ).encode("utf-8")
        return struct.pack(_HEADER_FMT, len(raw)) + raw

    def signing_payload(self) -> bytes:
        """Return the canonical bytes used for signing (excludes signature/public_key)."""
        return json.dumps(
            {
                "type": self.type,
                "sender": self.sender,
                "payload": self.payload,
                "ts": self.ts,
                "nonce": self.nonce,
            },
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")

    @classmethod
    def decode(cls, data: bytes) -> P2PMessage:
        obj = json.loads(data)
        # Validate required field types
        if not isinstance(obj.get("type"), str):
            raise ValueError(f"Invalid message: 'type' must be str, got {type(obj.get('type')).__name__}")
        if not isinstance(obj.get("sender"), str):
            raise ValueError(f"Invalid message: 'sender' must be str, got {type(obj.get('sender')).__name__}")
        if "payload" in obj and not isinstance(obj["payload"], dict):
            raise ValueError(f"Invalid message: 'payload' must be dict, got {type(obj['payload']).__name__}")
        return cls(
            type=obj["type"],
            sender=obj["sender"],
            payload=obj.get("payload", {}),
            ts=obj.get("ts", 0),
            nonce=obj.get("nonce", ""),
            signature=obj.get("signature", ""),
            public_key=obj.get("public_key", ""),
        )


async def read_message(reader: asyncio.StreamReader) -> P2PMessage | None:
    try:
        header = await reader.readexactly(_HEADER_SIZE)
    except (asyncio.IncompleteReadError, ConnectionError):
        return None

    (length,) = struct.unpack(_HEADER_FMT, header)
    if length > _MAX_FRAME_SIZE:
        logger.warning("Frame too large: %d bytes", length)
        # Drain the oversized frame to keep the stream in sync
        try:
            await reader.readexactly(length)
        except (asyncio.IncompleteReadError, ConnectionError):
            pass
        return None

    try:
        data = await reader.readexactly(length)
    except (asyncio.IncompleteReadError, ConnectionError):
        return None

    return P2PMessage.decode(data)


async def write_message(writer: asyncio.StreamWriter, msg: P2PMessage) -> bool:
    try:
        writer.write(msg.encode())
        await asyncio.wait_for(writer.drain(), timeout=_WRITE_TIMEOUT_SECONDS)
        return True
    except (TimeoutError, ConnectionError, OSError):
        return False
