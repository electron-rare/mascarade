"""Tests for P2P identity (Ed25519 keypair + PeerID)."""

import tempfile

from mascarade.p2p.identity import PeerIdentity


def test_generate_identity():
    identity = PeerIdentity.generate()
    assert identity.peer_id.startswith("Qm")
    assert len(identity.peer_id) > 10
    assert identity.public_key_bytes()
    assert len(identity.public_key_bytes()) == 32


def test_deterministic_peer_id():
    identity = PeerIdentity.generate()
    identity.public_key_bytes()
    # Same key should always produce the same peer_id

    from mascarade.p2p.identity import _peer_id_from_public_key

    pub = identity.public_key
    pid1 = _peer_id_from_public_key(pub)
    pid2 = _peer_id_from_public_key(pub)
    assert pid1 == pid2 == identity.peer_id


def test_sign_and_verify():
    identity = PeerIdentity.generate()
    data = b"hello mascarade p2p"
    sig = identity.sign(data)
    assert PeerIdentity.verify(identity.public_key_bytes(), sig, data)


def test_verify_bad_signature():
    identity = PeerIdentity.generate()
    data = b"hello"
    sig = identity.sign(data)
    assert not PeerIdentity.verify(identity.public_key_bytes(), sig, b"tampered")


def test_save_and_load():
    with tempfile.TemporaryDirectory() as tmpdir:
        id1 = PeerIdentity.load_or_generate(tmpdir)
        id2 = PeerIdentity.load_or_generate(tmpdir)
        assert id1.peer_id == id2.peer_id
        assert id1.public_key_bytes() == id2.public_key_bytes()


def test_two_identities_differ():
    id1 = PeerIdentity.generate()
    id2 = PeerIdentity.generate()
    assert id1.peer_id != id2.peer_id


def test_to_dict():
    identity = PeerIdentity.generate()
    d = identity.to_dict()
    assert "peer_id" in d
    assert "public_key" in d
    assert d["peer_id"] == identity.peer_id
