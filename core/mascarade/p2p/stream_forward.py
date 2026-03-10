"""P2P Stream Forwarding — send/receive LLM requests via P2P transport instead of HTTP.

This replaces httpx-based cluster forwarding with direct P2P messages for peers
that are reachable via the P2P network, reducing latency and removing the need
for HTTP authentication between peers.

Protocol:
    send:request   → peer receives an LLM request
    send:response  → peer sends back the LLM response
    send:error     → peer sends back an error
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from mascarade.p2p.protocol import P2PMessage
from mascarade.p2p.transport import P2PTransport, PeerConnection

logger = logging.getLogger("mascarade.p2p.stream_forward")

MSG_SEND_REQUEST = "send:request"
MSG_SEND_RESPONSE = "send:response"
MSG_SEND_ERROR = "send:error"


@dataclass(slots=True)
class PendingRequest:
    request_id: str
    peer_id: str
    future: asyncio.Future
    created_at: float = field(default_factory=time.monotonic)
    timeout: float = 120.0


class P2PStreamForwarder:
    """Forward LLM requests over P2P transport instead of HTTP."""

    def __init__(
        self,
        *,
        local_peer_id: str,
        transport: P2PTransport,
    ) -> None:
        self._local_peer_id = local_peer_id
        self._transport = transport
        self._pending: dict[str, PendingRequest] = {}
        self._request_handler: Any = None

        transport.on_message(MSG_SEND_REQUEST, self._handle_request)
        transport.on_message(MSG_SEND_RESPONSE, self._handle_response)
        transport.on_message(MSG_SEND_ERROR, self._handle_error)

    def set_request_handler(self, handler: Any) -> None:
        """Set the handler that processes incoming LLM requests.

        Handler signature: async def handler(request_data: dict) -> dict
        Should return the LLM response dict or raise an exception.
        """
        self._request_handler = handler

    async def forward_request(
        self,
        peer_id: str,
        request_data: dict[str, Any],
        *,
        timeout: float = 120.0,
    ) -> dict[str, Any]:
        """Forward an LLM request to a peer via P2P and wait for the response.

        Args:
            peer_id: Target peer's ID
            request_data: The SendRequest-compatible dict
            timeout: Max seconds to wait for response

        Returns:
            The response dict from the remote peer

        Raises:
            TimeoutError: If no response within timeout
            ConnectionError: If peer is not reachable
            RuntimeError: If peer returned an error
        """
        request_id = uuid.uuid4().hex[:12]
        loop = asyncio.get_running_loop()
        future: asyncio.Future = loop.create_future()

        self._pending[request_id] = PendingRequest(
            request_id=request_id,
            peer_id=peer_id,
            future=future,
            timeout=timeout,
        )

        msg = P2PMessage(
            type=MSG_SEND_REQUEST,
            sender=self._local_peer_id,
            payload={
                "request_id": request_id,
                "request": request_data,
            },
        )

        sent = await self._transport.send_to(peer_id, msg)
        if not sent:
            self._pending.pop(request_id, None)
            raise ConnectionError(f"Cannot reach peer {peer_id} via P2P transport")

        try:
            result = await asyncio.wait_for(future, timeout=timeout)
            return result
        except asyncio.TimeoutError:
            self._pending.pop(request_id, None)
            raise TimeoutError(
                f"P2P request {request_id} to {peer_id} timed out after {timeout}s"
            )

    def can_forward(self, peer_id: str) -> bool:
        """Check if a peer is reachable via P2P transport."""
        conn = self._transport.peers.get(peer_id)
        return conn is not None

    @property
    def pending_count(self) -> int:
        return len(self._pending)

    # --- Handlers ---

    async def _handle_request(self, msg: P2PMessage, conn: PeerConnection) -> None:
        """Handle an incoming LLM request from a peer."""
        request_id = msg.payload.get("request_id", "")
        request_data = msg.payload.get("request", {})

        if not self._request_handler:
            await self._send_error(
                conn, request_id, msg.sender, "No request handler configured"
            )
            return

        try:
            t0 = time.monotonic()
            result = await self._request_handler(request_data)
            elapsed_ms = (time.monotonic() - t0) * 1000

            response_msg = P2PMessage(
                type=MSG_SEND_RESPONSE,
                sender=self._local_peer_id,
                payload={
                    "request_id": request_id,
                    "response": result,
                    "latency_ms": round(elapsed_ms, 1),
                },
            )
            await conn.send(response_msg)
            logger.info(
                "P2P send:response %s → %s (%.0fms)",
                request_id, msg.sender, elapsed_ms,
            )
        except Exception as exc:
            logger.exception("P2P request handler error for %s", request_id)
            await self._send_error(conn, request_id, msg.sender, str(exc))

    async def _handle_response(self, msg: P2PMessage, conn: PeerConnection) -> None:
        """Handle an LLM response from a peer."""
        request_id = msg.payload.get("request_id", "")
        pending = self._pending.pop(request_id, None)
        if not pending:
            logger.warning("Received response for unknown request %s", request_id)
            return

        if not pending.future.done():
            response = msg.payload.get("response", {})
            response["_p2p_meta"] = {
                "peer_id": msg.sender,
                "request_id": request_id,
                "remote_latency_ms": msg.payload.get("latency_ms", 0),
                "round_trip_ms": round(
                    (time.monotonic() - pending.created_at) * 1000, 1
                ),
            }
            pending.future.set_result(response)

    async def _handle_error(self, msg: P2PMessage, conn: PeerConnection) -> None:
        """Handle an error response from a peer."""
        request_id = msg.payload.get("request_id", "")
        error = msg.payload.get("error", "Unknown error")
        pending = self._pending.pop(request_id, None)
        if pending and not pending.future.done():
            pending.future.set_exception(RuntimeError(f"Remote peer error: {error}"))

    async def _send_error(
        self, conn: PeerConnection, request_id: str, target: str, error: str,
    ) -> None:
        msg = P2PMessage(
            type=MSG_SEND_ERROR,
            sender=self._local_peer_id,
            payload={"request_id": request_id, "error": error},
        )
        await conn.send(msg)
