"""Versionnage des prompts système — suivi des changements et rollback."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime


def iso_utc_now() -> str:
    """Retourne un timestamp ISO8601 UTC avec suffixe Z stable."""
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


@dataclass
class PromptVersion:
    """Version d'un prompt système avec métadonnées de changement."""

    version_number: int
    timestamp: str
    content: str
    author_hash: str
    diff: str | None = None
    note: str | None = None
