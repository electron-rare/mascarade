"""P2PNode — libp2p host running in a dedicated trio thread.

The trio ↔ asyncio bridge pattern:
  asyncio world  →  asyncio.to_thread(trio.from_thread.run, fn, trio_token=token)  →  trio world

This keeps the two event loops fully isolated. libp2p stays in trio-land,
the rest of Mascarade stays in asyncio-land.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import secrets
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import trio
import trio.from_thread
from libp2p import new_host
from libp2p.crypto.secp256k1 import create_new_key_pair
from libp2p.custom_types import TProtocol
from libp2p.network.stream.net_stream import INetStream
from libp2p.peer.peerinfo import info_from_p2p_addr
from libp2p.stream_muxer.mplex.mplex import MPLEX_PROTOCOL_ID, Mplex
from libp2p.utils.address_validation import get_available_interfaces

try:
    from libp2p.pubsub.gossipsub import GossipSub
    from libp2p.pubsub.pubsub import Pubsub
    from libp2p.tools.async_service.trio_service import background_trio_service

    _PUBSUB_AVAILABLE = True
except Exception:  # pragma: no cover
    _PUBSUB_AVAILABLE = False

import multiaddr as ma

from mascarade.p2p.libp2p_protocols import (
    IDENTITY_PROTOCOL,
    SEND_PROTOCOL,
    read_msg,
    write_msg,
)

logger = logging.getLogger("mascarade.p2p.node")

_GOSSIPSUB_PROTOCOL_ID = TProtocol("/meshsub/1.0.0")
_HEARTBEAT_TOPIC = "mascarade/heartbeat"
_CAPABILITIES_TOPIC = "mascarade/capabilities"


@dataclass
class P2PPeer:
    """A peer discovered via libp2p."""

    peer_id: str
    node_id: str
    role: str
    base_url: str
    libp2p_peer_id: str
    last_seen: float = field(default_factory=time.monotonic)


class P2PNode:
    """libp2p node running in a dedicated trio thread.

    Lifecycle (called from asyncio):
        node = P2PNode(settings)
        await node.start(identity_provider)
        ...
        await node.stop()
    """

    def __init__(self, settings: Any) -> None:
        self._settings = settings
        self._trio_token: trio.lowlevel.TrioToken | None = None
        self._thread: threading.Thread | None = None
        self._host: Any = None
        self._started = threading.Event()
        self._failed: Exception | None = None
        self._stop_event: trio.Event | None = None
        self._peers: dict[str, P2PPeer] = {}
        self._peer_lock = threading.Lock()
        self._identity_provider: Callable[[], dict] | None = None
        self._send_handler: Callable | None = None
        self._local_peer_id: str = ""
        self._pubsub: Any = None
        self._gossipsub: Any = None

    # ── Asyncio-facing API ────────────────────────────────────────────

    async def start(
        self,
        identity_provider: Callable[[], dict],
        send_handler: Callable | None = None,
    ) -> None:
        """Start the libp2p node. Called from asyncio."""
        self._identity_provider = identity_provider
        self._send_handler = send_handler
        self._thread = threading.Thread(target=self._run_trio, name="mascarade-p2p", daemon=True)
        self._thread.start()
        ok = await asyncio.to_thread(self._started.wait, 15)
        if not ok:
            raise RuntimeError("P2P node failed to start within 15 s")
        if self._failed:
            raise self._failed

    async def stop(self) -> None:
        """Stop the libp2p node. Called from asyncio."""
        if self._trio_token and self._stop_event:
            try:
                trio.from_thread.run_sync(self._stop_event.set, trio_token=self._trio_token)
            except trio.RunFinishedError:
                pass
        if self._thread:
            self._thread.join(timeout=5)
        logger.info("P2P node stopped")

    @property
    def peer_id(self) -> str:
        return self._local_peer_id

    @property
    def running(self) -> bool:
        return self._started.is_set() and self._thread is not None and self._thread.is_alive()

    def discovered_peers(self) -> list[P2PPeer]:
        """Return a snapshot of discovered peers (thread-safe)."""
        with self._peer_lock:
            cutoff = time.monotonic() - max(self._settings.p2p_peer_ttl_seconds, 30)
            return [p for p in self._peers.values() if p.last_seen > cutoff]

    async def request_identity(self, libp2p_peer_id: str) -> dict:
        """Request identity from a remote peer via libp2p stream."""
        if not self._trio_token:
            raise RuntimeError("P2P node not running")
        return await asyncio.to_thread(
            trio.from_thread.run,
            self._request_identity_trio,
            libp2p_peer_id,
            trio_token=self._trio_token,
        )

    async def forward_send(self, libp2p_peer_id: str, payload: dict) -> dict:
        """Forward a /send request to a remote peer via libp2p stream."""
        if not self._trio_token:
            raise RuntimeError("P2P node not running")
        return await asyncio.to_thread(
            trio.from_thread.run,
            self._forward_send_trio,
            libp2p_peer_id,
            payload,
            trio_token=self._trio_token,
        )

    def status(self) -> dict:
        """Return diagnostic status dict."""
        return {
            "running": self.running,
            "peer_id": self._local_peer_id,
            "listen_port": self._settings.p2p_listen_port,
            "discovered_peers": len(self.discovered_peers()),
            "pubsub_enabled": self._pubsub is not None,
        }

    # ── Trio internals ────────────────────────────────────────────────

    def _run_trio(self) -> None:
        try:
            trio.run(self._trio_main)
        except Exception as exc:
            logger.exception("P2P trio loop crashed: %s", exc)
            self._failed = exc
            self._started.set()

    async def _trio_main(self) -> None:
        self._trio_token = trio.lowlevel.current_trio_token()
        self._stop_event = trio.Event()

        secret = self._load_or_generate_key()
        key_pair = create_new_key_pair(secret)

        self._host = new_host(
            key_pair=key_pair,
            muxer_opt={MPLEX_PROTOCOL_ID: Mplex},
        )

        port = self._settings.p2p_listen_port
        listen_addrs = get_available_interfaces(port)

        async with self._host.run(listen_addrs=listen_addrs):
            self._local_peer_id = self._host.get_id().to_string()
            self._host.set_stream_handler(IDENTITY_PROTOCOL, self._handle_identity)
            self._host.set_stream_handler(SEND_PROTOCOL, self._handle_send)

            addrs = self._host.get_addrs()
            logger.info(
                "P2P node started — peer_id=%s listening on %s",
                self._local_peer_id,
                [str(a) for a in addrs],
            )

            if self._should_start_pubsub():
                await self._start_pubsub()

            self._started.set()

            async with trio.open_nursery() as nursery:
                nursery.start_soon(self._host.get_peerstore().start_cleanup_task, 60)
                nursery.start_soon(self._bootstrap_loop)
                if self._pubsub is not None:
                    nursery.start_soon(self._heartbeat_loop)
                    nursery.start_soon(self._heartbeat_receive_loop)
                await self._stop_event.wait()
                nursery.cancel_scope.cancel()

        logger.info("P2P trio loop exiting cleanly")

    def _should_start_pubsub(self) -> bool:
        return bool(_PUBSUB_AVAILABLE and getattr(self._settings, "p2p_pubsub_enabled", False))

    async def _start_pubsub(self) -> None:
        if not _PUBSUB_AVAILABLE:
            return
        self._gossipsub = GossipSub(
            protocols=[_GOSSIPSUB_PROTOCOL_ID],
            degree=3,
            degree_low=2,
            degree_high=4,
            time_to_live=60,
            gossip_window=2,
            gossip_history=5,
            heartbeat_initial_delay=2.0,
            heartbeat_interval=5,
        )
        self._pubsub = Pubsub(self._host, self._gossipsub)
        logger.info("GossipSub initialized")

    # ── Bootstrap ─────────────────────────────────────────────────────

    async def _bootstrap_loop(self) -> None:
        """Periodically connect to bootstrap peers."""
        while True:
            await self._connect_bootstrap_peers()
            await trio.sleep(self._settings.p2p_discovery_interval_seconds)

    async def _connect_bootstrap_peers(self) -> None:
        raw = self._settings.p2p_bootstrap_peers.strip()
        if not raw:
            return
        addrs = [a.strip() for a in raw.split(";") if a.strip()]
        for addr_str in addrs:
            try:
                maddr = ma.Multiaddr(addr_str)
                peer_info = info_from_p2p_addr(maddr)
                pid_str = peer_info.peer_id.to_string()
                if pid_str == self._local_peer_id:
                    continue
                await self._host.connect(peer_info)
                logger.debug("Connected to bootstrap peer %s", pid_str)
                # Probe identity
                await self._probe_peer(pid_str)
            except Exception as exc:
                logger.debug("Bootstrap connect failed for %s: %s", addr_str, exc)

    async def _probe_peer(self, libp2p_pid: str) -> None:
        """Open an identity stream to a peer and cache the result."""
        try:
            from libp2p.peer.id import ID

            pid = ID.from_base58(libp2p_pid)
            stream = await self._host.new_stream(pid, [IDENTITY_PROTOCOL])
            await write_msg(stream, {"type": "identity_request"})
            response = await read_msg(stream)
            await stream.close()

            node_id = response.get("node_id", libp2p_pid)
            role = response.get("role", "general")
            base_url = response.get("base_url", "")

            peer = P2PPeer(
                peer_id=node_id,
                node_id=node_id,
                role=role,
                base_url=base_url,
                libp2p_peer_id=libp2p_pid,
                last_seen=time.monotonic(),
            )
            with self._peer_lock:
                self._peers[node_id] = peer
            logger.info("Discovered peer via identity probe: %s (%s)", node_id, role)
        except Exception as exc:
            logger.debug("Identity probe failed for %s: %s", libp2p_pid, exc)

    # ── Stream handlers (trio side) ───────────────────────────────────

    async def _handle_identity(self, stream: INetStream) -> None:
        """Respond with local node identity."""
        try:
            _request = await read_msg(stream)
            identity = self._identity_provider() if self._identity_provider else {}
            await write_msg(stream, identity)
        except Exception as exc:
            logger.warning("Identity handler error: %s", exc)
        finally:
            await stream.close()

    async def _handle_send(self, stream: INetStream) -> None:
        """Handle a forwarded /send request."""
        try:
            payload = await read_msg(stream)
            if self._send_handler:
                # send_handler is an asyncio coroutine — we can't await it from trio.
                # Instead, run it in the asyncio thread via trio.to_thread.
                # But we don't have the asyncio loop reference here.
                # Simpler: the send_handler should be a sync wrapper that
                # schedules the asyncio coro and waits for it.
                result = self._send_handler(payload)
                if asyncio.iscoroutine(result):
                    # Fallback: run in a thread that drives the asyncio coro
                    loop = asyncio.new_event_loop()
                    try:
                        result = loop.run_until_complete(result)
                    finally:
                        loop.close()
            else:
                result = {"error": "No send handler registered"}
            await write_msg(stream, result)
        except Exception as exc:
            logger.warning("Send handler error: %s", exc)
            try:
                await write_msg(stream, {"error": str(exc)})
            except Exception:
                pass
        finally:
            await stream.close()

    # ── Trio-side request methods (called via bridge) ─────────────────

    async def _request_identity_trio(self, libp2p_pid_str: str) -> dict:
        from libp2p.peer.id import ID

        pid = ID.from_base58(libp2p_pid_str)
        stream = await self._host.new_stream(pid, [IDENTITY_PROTOCOL])
        try:
            await write_msg(stream, {"type": "identity_request"})
            return await read_msg(stream)
        finally:
            await stream.close()

    async def _forward_send_trio(self, libp2p_pid_str: str, payload: dict) -> dict:
        from libp2p.peer.id import ID

        pid = ID.from_base58(libp2p_pid_str)
        stream = await self._host.new_stream(pid, [SEND_PROTOCOL])
        try:
            await write_msg(stream, payload)
            return await read_msg(stream)
        finally:
            await stream.close()

    # ── Heartbeat (GossipSub) ─────────────────────────────────────────

    async def _heartbeat_loop(self) -> None:
        if self._pubsub is None:
            return
        async with background_trio_service(self._pubsub):
            async with background_trio_service(self._gossipsub):
                await self._pubsub.wait_until_ready()
                await self._pubsub.subscribe(_HEARTBEAT_TOPIC)
                logger.info("GossipSub heartbeat topic subscribed")
                while True:
                    identity = self._identity_provider() if self._identity_provider else {}
                    heartbeat = {
                        "type": "heartbeat",
                        "libp2p_peer_id": self._local_peer_id,
                        "timestamp": time.time(),
                        **identity,
                    }
                    try:
                        await self._pubsub.publish(
                            _HEARTBEAT_TOPIC,
                            json.dumps(heartbeat).encode("utf-8"),
                        )
                    except Exception as exc:
                        logger.debug("Heartbeat publish error: %s", exc)
                    await trio.sleep(self._settings.p2p_heartbeat_interval_seconds)

    async def _heartbeat_receive_loop(self) -> None:
        if self._pubsub is None:
            return
        # Wait for pubsub to be ready
        await trio.sleep(3)
        try:
            subscription = await self._pubsub.subscribe(_HEARTBEAT_TOPIC)
        except Exception as exc:
            logger.warning("Could not subscribe to heartbeat topic: %s", exc)
            return
        while True:
            try:
                message = await subscription.get()
                data = json.loads(message.data.decode("utf-8"))
                if data.get("type") != "heartbeat":
                    continue
                node_id = data.get("node_id", "")
                if not node_id or node_id == self._settings.node_id:
                    continue
                peer = P2PPeer(
                    peer_id=node_id,
                    node_id=node_id,
                    role=data.get("role", "general"),
                    base_url=data.get("base_url", ""),
                    libp2p_peer_id=data.get("libp2p_peer_id", ""),
                    last_seen=time.monotonic(),
                )
                with self._peer_lock:
                    self._peers[node_id] = peer
            except Exception as exc:
                logger.debug("Heartbeat receive error: %s", exc)
                await trio.sleep(1)

    # ── Key management ────────────────────────────────────────────────

    def _load_or_generate_key(self) -> bytes:
        key_path = self._settings.p2p_identity_key_path.strip()
        if not key_path:
            key_path = os.path.expanduser("~/.mascarade/p2p_key")

        path = Path(key_path)
        if path.exists():
            data = path.read_bytes()
            if len(data) == 32:
                logger.info("Loaded P2P identity key from %s", key_path)
                return data

        # Generate new key
        path.parent.mkdir(parents=True, exist_ok=True)
        secret = secrets.token_bytes(32)
        path.write_bytes(secret)
        path.chmod(0o600)
        logger.info("Generated new P2P identity key at %s", key_path)
        return secret
