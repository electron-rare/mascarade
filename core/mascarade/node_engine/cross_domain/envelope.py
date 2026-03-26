"""Cross-domain data serialization envelope.

All data crossing domain boundaries is wrapped in this envelope
to ensure type safety, provenance tracking, and integrity validation.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any


@dataclass
class CrossDomainEnvelope:
    """Wraps data for cross-domain transfer.

    The envelope ensures:
    1. Source domain and type are preserved
    2. Target domain and type are declared
    3. Data integrity is verified via checksum
    4. Provenance chain tracks all transformations
    """

    source_domain: str
    source_type: str
    target_domain: str
    target_type: str
    payload: Any
    checksum: str = ""
    provenance: list[str] = field(default_factory=list)
    serialization_format: str = "json"  # "json", "msgpack", "arrow"

    def __post_init__(self) -> None:
        if not self.checksum:
            self.checksum = self._compute_checksum()

    def _compute_checksum(self) -> str:
        serialized = json.dumps(self.payload, sort_keys=True, default=str)
        return hashlib.sha256(serialized.encode()).hexdigest()[:16]

    def verify(self) -> bool:
        return self.checksum == self._compute_checksum()

    def serialize(self) -> bytes:
        """Serialize envelope for network transfer."""
        if self.serialization_format == "json":
            return json.dumps(
                {
                    "source_domain": self.source_domain,
                    "source_type": self.source_type,
                    "target_domain": self.target_domain,
                    "target_type": self.target_type,
                    "payload": self.payload,
                    "checksum": self.checksum,
                    "provenance": self.provenance,
                },
                default=str,
            ).encode()
        # msgpack and arrow formats for high-throughput scenarios
        raise NotImplementedError(f"Format {self.serialization_format} not yet implemented")

    @classmethod
    def deserialize(cls, data: bytes) -> CrossDomainEnvelope:
        parsed = json.loads(data)
        return cls(**parsed)
