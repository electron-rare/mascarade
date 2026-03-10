"""Tests for P2P message authentication (Ed25519 signatures)."""

import base64

from mascarade.p2p.auth import sign_message, verify_message, MessageAuthenticator
from mascarade.p2p.identity import PeerIdentity
from mascarade.p2p.protocol import P2PMessage


def _make_msg(**overrides) -> P2PMessage:
    defaults = dict(type="test", sender="QmABC123", payload={"data": "hello"}, ts=1000.0)
    defaults.update(overrides)
    return P2PMessage(**defaults)


def test_sign_and_verify_message():
    identity = PeerIdentity.generate()
    msg = _make_msg(sender=identity.peer_id)
    sign_message(identity, msg)

    assert msg.signature != ""
    assert msg.public_key != ""
    assert verify_message(msg) is True


def test_tampered_message_rejected():
    identity = PeerIdentity.generate()
    msg = _make_msg(sender=identity.peer_id)
    sign_message(identity, msg)

    # Tamper with the payload after signing
    msg.payload["data"] = "tampered"
    assert verify_message(msg) is False


def test_unsigned_message_accepted():
    """Unsigned messages should be accepted for backwards compatibility."""
    msg = _make_msg()
    assert msg.signature == ""
    assert msg.public_key == ""
    assert verify_message(msg) is True


def test_wrong_key_rejected():
    identity_a = PeerIdentity.generate()
    identity_b = PeerIdentity.generate()

    msg = _make_msg(sender=identity_a.peer_id)
    sign_message(identity_a, msg)

    # Replace public_key with a different identity's key
    msg.public_key = base64.b64encode(identity_b.public_key_bytes()).decode("ascii")
    assert verify_message(msg) is False


def test_authenticator_sign_and_verify():
    identity = PeerIdentity.generate()
    auth = MessageAuthenticator(identity)

    msg = _make_msg(sender=identity.peer_id)
    auth.sign(msg)
    assert auth.verify(msg) is True


def test_authenticator_reject_unsigned_when_strict():
    identity = PeerIdentity.generate()
    auth = MessageAuthenticator(identity, reject_unsigned=True)

    msg = _make_msg()
    assert auth.verify(msg) is False


def test_message_encode_decode_preserves_signature():
    identity = PeerIdentity.generate()
    msg = _make_msg(sender=identity.peer_id)
    sign_message(identity, msg)

    # Round-trip through encode/decode
    raw = msg.encode()
    import struct
    from mascarade.p2p.protocol import _HEADER_FMT
    body = raw[struct.calcsize(_HEADER_FMT):]
    decoded = P2PMessage.decode(body)

    assert decoded.signature == msg.signature
    assert decoded.public_key == msg.public_key
    assert verify_message(decoded) is True
