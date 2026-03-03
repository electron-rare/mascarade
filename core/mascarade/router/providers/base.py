"""Interface abstraite pour les providers LLM."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import AsyncIterator


@dataclass
class LLMResponse:
    """Réponse normalisée d'un provider LLM."""

    content: str
    model: str
    provider: str
    usage: dict[str, int] = field(default_factory=dict)


class LLMProvider(ABC):
    """Interface commune pour tous les providers LLM."""

    name: str
    default_model: str

    # Cost per 1M tokens (input, output) — for routing decisions
    cost_per_million: tuple[float, float] = (0.0, 0.0)

    # Relative speed ranking (lower = faster)
    speed_rank: int = 0

    # Relative quality ranking (higher = better)
    quality_rank: int = 0

    @abstractmethod
    async def send(
        self,
        messages: list[dict],
        *,
        model: str | None = None,
        system: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        """Envoyer un message et recevoir une réponse complète."""
        ...

    @abstractmethod
    async def stream(
        self,
        messages: list[dict],
        *,
        model: str | None = None,
        system: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> AsyncIterator[str]:
        """Streamer la réponse token par token."""
        ...

    @abstractmethod
    def available_models(self) -> list[str]:
        """Liste des modèles disponibles pour ce provider."""
        ...

    @property
    def is_configured(self) -> bool:
        """Vérifie si le provider a une clé API configurée."""
        return True
