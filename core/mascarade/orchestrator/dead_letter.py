"""Stockage des exécutions d'orchestration échouées (dead letter queue)."""

from __future__ import annotations

from collections import deque
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from threading import Lock
from uuid import uuid4


def iso_utc_now() -> str:
    """Return an ISO8601 UTC timestamp with a stable Z suffix."""
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


@dataclass(slots=True)
class DeadLetterEntry:
    """Représente une exécution d'orchestration échouée."""

    id: str
    ts: str
    run_id: str
    error: str
    mode: str
    context: dict
    agent_name: str | None = None
    step: int | None = None
    provider: str | None = None
    model: str | None = None

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return asdict(self)


@dataclass
class DeadLetterStore:
    """Stockage en mémoire des orchestrations échouées avec limite de taille."""

    max_entries: int = 1000
    _entries: deque[DeadLetterEntry] = field(init=False, repr=False)
    _lock: Lock = field(init=False, default_factory=Lock, repr=False)

    def __post_init__(self) -> None:
        self._entries = deque(maxlen=self.max_entries)

    def record_failure(
        self,
        *,
        run_id: str,
        error: str,
        context: dict,
        mode: str = "unknown",
        agent_name: str | None = None,
        step: int | None = None,
        provider: str | None = None,
        model: str | None = None,
    ) -> DeadLetterEntry:
        """Enregistrer une orchestration échouée."""
        entry = DeadLetterEntry(
            id=uuid4().hex,
            ts=iso_utc_now(),
            run_id=run_id,
            error=error,
            mode=mode,
            context=context,
            agent_name=agent_name,
            step=step,
            provider=provider,
            model=model,
        )

        with self._lock:
            self._entries.append(entry)

        return entry

    def recent(
        self,
        *,
        limit: int = 50,
        run_id: str | None = None,
        agent_name: str | None = None,
    ) -> list[DeadLetterEntry]:
        """Récupérer les entrées récentes, optionnellement filtrées."""
        with self._lock:
            entries = list(self._entries)

        filtered = [
            entry
            for entry in entries
            if (not run_id or entry.run_id == run_id)
            and (not agent_name or entry.agent_name == agent_name)
        ]
        return filtered[-max(1, limit) :]

    def get(self, entry_id: str) -> DeadLetterEntry | None:
        """Récupérer une entrée spécifique par ID."""
        with self._lock:
            entries = list(self._entries)

        for entry in entries:
            if entry.id == entry_id:
                return entry
        return None

    def count(self) -> int:
        """Retourner le nombre total d'entrées."""
        with self._lock:
            return len(self._entries)

    def clear(self) -> None:
        """Vider toutes les entrées (pour tests ou maintenance)."""
        with self._lock:
            self._entries.clear()
