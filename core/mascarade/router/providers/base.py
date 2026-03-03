"""Interface abstraite pour les providers LLM."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import AsyncIterator

from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
)

logger = logging.getLogger("mascarade.providers")

# Exceptions transitoires communes (réseau, timeout OS)
RETRYABLE_EXCEPTIONS = (ConnectionError, TimeoutError, OSError)


def make_retry(*extra_exceptions: type[BaseException]):
    """Créer un décorateur retry avec exceptions spécifiques au provider."""
    return retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type(RETRYABLE_EXCEPTIONS + tuple(extra_exceptions)),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )


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
