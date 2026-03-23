"""Peer identity based on Ed25519 keypairs."""

from __future__ import annotations

import base64
import hashlib
import logging
import os
from dataclasses import dataclass
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    NoEncryption,
    PrivateFormat,
    PublicFormat,
)

logger = logging.getLogger("mascarade.p2p.identity")

_DEFAULT_KEY_DIR = Path.home() / ".mascarade" / "p2p"
_KEY_FILE = "identity.key"


def _peer_id_from_public_key(pub: Ed25519PublicKey) -> str:
    raw = pub.public_bytes(Encoding.Raw, PublicFormat.Raw)
    digest = hashlib.sha256(raw).digest()[:20]
    return "Qm" + base64.b32encode(digest).decode("ascii").rstrip("=")


@dataclass(frozen=True)
class PeerIdentity:
    peer_id: str
    private_key: Ed25519PrivateKey
    public_key: Ed25519PublicKey

    @classmethod
    def generate(cls) -> PeerIdentity:
        private_key = Ed25519PrivateKey.generate()
        public_key = private_key.public_key()
        peer_id = _peer_id_from_public_key(public_key)
        return cls(peer_id=peer_id, private_key=private_key, public_key=public_key)

    @classmethod
    def load_or_generate(cls, key_dir: Path | str | None = None) -> PeerIdentity:
        key_dir = Path(key_dir) if key_dir else _DEFAULT_KEY_DIR
        key_path = key_dir / _KEY_FILE

        if key_path.exists():
            return cls._load_from_file(key_path)

        identity = cls.generate()
        identity._save_to_file(key_path)
        logger.info("Generated new P2P identity: %s", identity.peer_id)
        return identity

    @classmethod
    def _load_from_file(cls, path: Path) -> PeerIdentity:
        raw = path.read_bytes()
        private_key = Ed25519PrivateKey.from_private_bytes(raw)
        public_key = private_key.public_key()
        peer_id = _peer_id_from_public_key(public_key)
        logger.info("Loaded P2P identity: %s", peer_id)
        return cls(peer_id=peer_id, private_key=private_key, public_key=public_key)

    def _save_to_file(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        raw = self.private_key.private_bytes(
            Encoding.Raw, PrivateFormat.Raw, NoEncryption()
        )
        path.write_bytes(raw)
        os.chmod(path, 0o600)

    def public_key_bytes(self) -> bytes:
        return self.public_key.public_bytes(Encoding.Raw, PublicFormat.Raw)

    def sign(self, data: bytes) -> bytes:
        return self.private_key.sign(data)

    @staticmethod
    def verify(public_key_bytes: bytes, signature: bytes, data: bytes) -> bool:
        pub = Ed25519PublicKey.from_public_bytes(public_key_bytes)
        try:
            pub.verify(signature, data)
            return True
        except Exception:
            return False

    def to_dict(self) -> dict[str, str]:
        return {
            "peer_id": self.peer_id,
            "public_key": base64.b64encode(self.public_key_bytes()).decode("ascii"),
        }
