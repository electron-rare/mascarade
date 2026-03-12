"""TCP transport layer — manages persistent connections to peers."""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Coroutine

from mascarade.p2p.auth import MessageAuthenticator
from mascarade.p2p.identity import PeerIdentity
from mascarade.p2p.protocol import P2PMessage, read_message, write_message

logger = logging.getLogger("mascarade.p2p.transport")

MessageHandler = Callable[[P2PMessage, "PeerConnection"], Coroutine[Any, Any, None]]
MessageTransform = Callable[[P2PMessage], P2PMessage]


@dataclass
class PeerConnection:
    peer_id: str
    host: str
    port: int
    reader: asyncio.StreamReader | None = None
    writer: asyncio.StreamWriter | None = None
    connected: bool = False
    last_seen: float = 0.0
    _reconnect_backoff: float = 1.0
    _write_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    message_transform: MessageTransform | None = None

    async def connect(self) -> bool:
        if self.connected:
            return True
        try:
            self.reader, self.writer = await asyncio.wait_for(
                asyncio.open_connection(self.host, self.port),
                timeout=5.0,
            )
            self.connected = True
            self.last_seen = time.monotonic()
            self._reconnect_backoff = 1.0
            logger.info("Connected to peer %s at %s:%d", self.peer_id, self.host, self.port)
            return True
        except (OSError, asyncio.TimeoutError) as exc:
            logger.debug("Failed to connect to %s: %s", self.peer_id, exc)
            self._reconnect_backoff = min(self._reconnect_backoff * 2, 60.0)
            return False

    async def send(self, msg: P2PMessage) -> bool:
        async with self._write_lock:
            if not self.connected or self.writer is None:
                if not await self.connect():
                    return False
            outgoing = self.message_transform(msg) if self.message_transform else msg
            ok = await write_message(self.writer, outgoing)
            if not ok:
                await self.disconnect()
            return ok

    async def disconnect(self) -> None:
        self.connected = False
        if self.writer:
            try:
                self.writer.close()
                await self.writer.wait_closed()
            except Exception:
                pass
        self.reader = None
        self.writer = None


class P2PTransport:
    """TCP server + outbound connection pool for P2P messaging."""

    def __init__(
        self,
        *,
        local_peer_id: str,
        listen_host: str = "0.0.0.0",
        listen_port: int = 4001,
    ) -> None:
        self._local_peer_id = local_peer_id
        self._listen_host = listen_host
        self._listen_port = listen_port
        self._server: asyncio.Server | None = None
        self._peers: dict[str, PeerConnection] = {}
        self._handlers: dict[str, MessageHandler] = {}
        self._default_handler: MessageHandler | None = None
        self._relay_client: Any | None = None  # Optional RelayClient
        self._inbound_tasks: set[asyncio.Task] = set()
        self._outbound_read_tasks: dict[str, asyncio.Task] = {}
        self._authenticator: MessageAuthenticator | None = None

    @property
    def listen_port(self) -> int:
        return self._listen_port

    @property
    def peers(self) -> dict[str, PeerConnection]:
        return dict(self._peers)

    def set_relay_client(self, client: Any) -> None:
        """Attach a :class:`RelayClient` for automatic relay fallback."""
        self._relay_client = client

    def on_message(self, msg_type: str, handler: MessageHandler) -> None:
        self._handlers[msg_type] = handler

    def on_default(self, handler: MessageHandler) -> None:
        self._default_handler = handler

    def enable_authentication(
        self,
        identity: PeerIdentity,
        *,
        reject_unsigned: bool = True,
    ) -> None:
        self._authenticator = MessageAuthenticator(identity, reject_unsigned=reject_unsigned)
        for conn in self._peers.values():
            conn.message_transform = self._prepare_outgoing

    def add_peer(self, peer_id: str, host: str, port: int) -> PeerConnection:
        if peer_id in self._peers:
            existing = self._peers[peer_id]
            existing.host = host
            existing.port = port
            return existing
        conn = PeerConnection(
            peer_id=peer_id,
            host=host,
            port=port,
            message_transform=self._prepare_outgoing,
        )
        self._peers[peer_id] = conn
        return conn

    def remove_peer(self, peer_id: str) -> None:
        conn = self._peers.pop(peer_id, None)
        if conn:
            asyncio.ensure_future(conn.disconnect())

    async def start(self) -> None:
        self._server = await asyncio.start_server(
            self._handle_inbound,
            self._listen_host,
            self._listen_port,
        )
        actual_port = self._server.sockets[0].getsockname()[1]
        self._listen_port = actual_port
        logger.info(
            "P2P transport listening on %s:%d",
            self._listen_host,
            self._listen_port,
        )

    async def stop(self) -> None:
        # Cancel inbound handler tasks first (unblocks wait_closed)
        for task in list(self._inbound_tasks):
            task.cancel()
        if self._inbound_tasks:
            await asyncio.gather(*self._inbound_tasks, return_exceptions=True)
        self._inbound_tasks.clear()
        # Cancel outbound read tasks
        for task in list(self._outbound_read_tasks.values()):
            task.cancel()
        if self._outbound_read_tasks:
            await asyncio.gather(*self._outbound_read_tasks.values(), return_exceptions=True)
        self._outbound_read_tasks.clear()
        # Close server
        if self._server:
            self._server.close()
            await self._server.wait_closed()
        # Disconnect all peers
        for conn in list(self._peers.values()):
            await conn.disconnect()
        self._peers.clear()

    async def broadcast(self, msg: P2PMessage) -> int:
        sent = 0
        for peer_id, conn in list(self._peers.items()):
            if await conn.send(msg):
                sent += 1
                self._ensure_outbound_reader(peer_id, conn)
        return sent

    async def send_to(self, peer_id: str, msg: P2PMessage) -> bool:
        outgoing = self._prepare_outgoing(msg)
        conn = self._peers.get(peer_id)
        if not conn:
            # Try relay fallback if available
            if self._relay_client is not None:
                return await self._relay_client.send_via_relay(
                    peer_id,
                    inner_type=outgoing.type,
                    inner_payload=outgoing.payload,
                    inner_ts=outgoing.ts,
                    inner_nonce=outgoing.nonce,
                    inner_signature=outgoing.signature,
                    inner_public_key=outgoing.public_key,
                )
            return False
        result = await conn.send(outgoing)
        if result:
            self._ensure_outbound_reader(peer_id, conn)
            return True
        # Direct send failed — try relay fallback
        if self._relay_client is not None:
            logger.debug("Direct send to %s failed, trying relay", peer_id)
            return await self._relay_client.send_via_relay(
                peer_id,
                inner_type=outgoing.type,
                inner_payload=outgoing.payload,
                inner_ts=outgoing.ts,
                inner_nonce=outgoing.nonce,
                inner_signature=outgoing.signature,
                inner_public_key=outgoing.public_key,
            )
        return False

    async def send_to_via_relay(
        self,
        peer_id: str,
        msg: P2PMessage,
        relay_peer_id: str,
    ) -> bool:
        """Send a message to *peer_id* explicitly through *relay_peer_id*."""
        if self._relay_client is None:
            logger.warning("No relay client configured")
            return False
        return await self._relay_client.send_via_relay(
            peer_id,
            inner_type=msg.type,
            inner_payload=msg.payload,
            inner_ts=msg.ts,
            inner_nonce=msg.nonce,
            inner_signature=msg.signature,
            inner_public_key=msg.public_key,
            relay_peer_id=relay_peer_id,
        )

    def _prepare_outgoing(self, msg: P2PMessage) -> P2PMessage:
        if self._authenticator is None:
            return msg
        if msg.signature and msg.public_key:
            return msg
        return self._authenticator.sign(msg)

    def _ensure_outbound_reader(self, peer_id: str, conn: PeerConnection) -> None:
        """Start a read loop for an outbound connection if not already running."""
        if peer_id in self._outbound_read_tasks:
            task = self._outbound_read_tasks[peer_id]
            if not task.done():
                return
        if conn.reader is None:
            return
        task = asyncio.ensure_future(self._outbound_read_loop(peer_id, conn))
        self._outbound_read_tasks[peer_id] = task

    async def _outbound_read_loop(self, peer_id: str, conn: PeerConnection) -> None:
        """Read messages from an outbound connection (responses from remote)."""
        try:
            while conn.connected and conn.reader is not None:
                try:
                    msg = await asyncio.wait_for(read_message(conn.reader), timeout=120.0)
                except asyncio.TimeoutError:
                    continue
                if msg is None:
                    break

                if self._authenticator is not None and not self._authenticator.verify(msg):
                    logger.warning(
                        "Dropping unsigned/invalid outbound message type=%s from=%s",
                        msg.type,
                        msg.sender,
                    )
                    continue

                handler = self._handlers.get(msg.type) or self._default_handler
                if handler:
                    try:
                        result = handler(msg, conn)
                        if asyncio.iscoroutine(result) or asyncio.isfuture(result):
                            await result
                    except Exception:
                        logger.exception("Outbound handler error for %s", msg.type)
        except asyncio.CancelledError:
            pass
        except Exception:
            logger.debug("Outbound read loop ended for %s", peer_id)
        finally:
            self._outbound_read_tasks.pop(peer_id, None)

    async def _handle_inbound(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        addr = writer.get_extra_info("peername")
        logger.debug("Inbound connection from %s", addr)
        task = asyncio.current_task()
        if task:
            self._inbound_tasks.add(task)

        # Ephemeral connection for replies — NOT added to outbound peer pool
        inbound_conn = PeerConnection(
            peer_id="unknown",
            host=addr[0] if addr else "127.0.0.1",
            port=0,
            reader=reader,
            writer=writer,
            connected=True,
            last_seen=time.monotonic(),
            message_transform=self._prepare_outgoing,
        )
        try:
            while True:
                try:
                    msg = await asyncio.wait_for(read_message(reader), timeout=120.0)
                except asyncio.TimeoutError:
                    continue
                if msg is None:
                    break

                if self._authenticator is not None and not self._authenticator.verify(msg):
                    logger.warning(
                        "Dropping unsigned/invalid inbound message type=%s from=%s",
                        msg.type,
                        msg.sender,
                    )
                    continue

                sender_id = msg.sender
                if sender_id and sender_id != self._local_peer_id:
                    inbound_conn.peer_id = sender_id
                    inbound_conn.last_seen = time.monotonic()

                conn = inbound_conn

                handler = self._handlers.get(msg.type) or self._default_handler
                if handler:
                    try:
                        result = handler(msg, conn)
                        if asyncio.iscoroutine(result) or asyncio.isfuture(result):
                            await result
                    except Exception:
                        logger.exception("Handler error for message type %s", msg.type)
        except asyncio.CancelledError:
            pass
        except Exception:
            logger.debug("Inbound connection closed from %s", addr)
        finally:
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass
            if task:
                self._inbound_tasks.discard(task)
