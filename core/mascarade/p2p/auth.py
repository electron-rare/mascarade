"""P2P message authentication using Ed25519 signatures."""

from __future__ import annotations

import base64
import logging
from typing import Any, Callable, Awaitable

from mascarade.p2p.identity import PeerIdentity
from mascarade.p2p.protocol import P2PMessage

logger = logging.getLogger("mascarade.p2p.auth")


def sign_message(identity: PeerIdentity, msg: P2PMessage) -> P2PMessage:
    """Sign a message's payload and set signature + public_key fields.

    Returns the same message object with signature and public_key populated.
    """
    data = msg.signing_payload()
    sig = identity.sign(data)
    msg.signature = base64.b64encode(sig).decode("ascii")
    msg.public_key = base64.b64encode(identity.public_key_bytes()).decode("ascii")
    return msg


def verify_message(msg: P2PMessage) -> bool:
    """Verify the signature on a message.

    Returns True if the signature is valid, or if the message is unsigned
    (backwards compatibility — unsigned messages are accepted).
    """
    if not msg.signature or not msg.public_key:
        return True  # unsigned messages pass (backwards compat)

    try:
        sig = base64.b64decode(msg.signature)
        pub_bytes = base64.b64decode(msg.public_key)
        data = msg.signing_payload()
        return PeerIdentity.verify(pub_bytes, sig, data)
    except Exception:
        logger.warning("Failed to verify message from %s", msg.sender)
        return False


# Type alias for message handler callbacks (matches transport.on_message signature)
MessageHandler = Callable[[P2PMessage, Any], Awaitable[None]]


class MessageAuthenticator:
    """Opt-in wrapper that auto-signs outgoing and verifies incoming messages.

    Usage::

        authenticator = MessageAuthenticator(identity)

        # Sign before sending
        signed_msg = authenticator.sign(msg)

        # Wrap a handler to auto-verify incoming messages
        @authenticator.verified
        async def handle_data(msg: P2PMessage, conn) -> None:
            ...  # only called if signature is valid
    """

    def __init__(
        self,
        identity: PeerIdentity,
        *,
        reject_unsigned: bool = False,
    ) -> None:
        self._identity = identity
        self._reject_unsigned = reject_unsigned

    def sign(self, msg: P2PMessage) -> P2PMessage:
        """Sign an outgoing message."""
        return sign_message(self._identity, msg)

    def verify(self, msg: P2PMessage) -> bool:
        """Verify an incoming message.

        When reject_unsigned is True, unsigned messages are rejected.
        """
        if not msg.signature and not msg.public_key:
            return not self._reject_unsigned
        return verify_message(msg)

    def verified(self, handler: MessageHandler) -> MessageHandler:
        """Decorator that drops messages with invalid signatures."""
        async def wrapper(msg: P2PMessage, conn: Any) -> None:
            if not self.verify(msg):
                logger.warning(
                    "Dropping message type=%s from %s: signature verification failed",
                    msg.type,
                    msg.sender,
                )
                return
            await handler(msg, conn)

        wrapper.__name__ = getattr(handler, "__name__", "wrapped")
        wrapper.__qualname__ = getattr(handler, "__qualname__", "wrapped")
        return wrapper
