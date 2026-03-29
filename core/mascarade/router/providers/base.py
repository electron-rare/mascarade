"""Interface abstraite pour les providers LLM."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

if TYPE_CHECKING:
    from aiobreaker import CircuitBreaker

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


def build_chat_messages(messages: list[dict], system: str | None = None) -> list[dict]:
    """Prepend a system message if provided, then extend with user messages."""
    chat: list[dict] = []
    if system:
        chat.append({"role": "system", "content": system})
    chat.extend(messages)
    return chat


@dataclass
class LLMResponse:
    """Réponse normalisée d'un provider LLM."""

    content: str
    model: str
    provider: str
    usage: dict[str, int] = field(default_factory=dict)
    metadata: dict = field(default_factory=dict)


@dataclass
class LLMStreamChunk:
    """Chunk de streaming pour les réponses LLM."""

    content: str
    model: str
    finish_reason: str | None = None


class LLMProvider(ABC):
    """
    Interface commune pour tous les providers LLM.

    Circuit Breaker Support:
        Les méthodes send() et stream() doivent être protégées par un circuit breaker
        pour prévenir les pannes en cascade. Le circuit breaker est automatiquement
        appliqué par le Router lors des appels aux providers.

        États du circuit breaker:
        - CLOSED: Fonctionnement normal
        - OPEN: Échecs répétés, appels rejetés immédiatement
        - HALF_OPEN: Test de récupération

        Configuration par défaut: fail_max=5, timeout=60s
    """

    name: str
    default_model: str

    # Cost per 1M tokens (input, output) — for routing decisions
    cost_per_million: tuple[float, float] = (0.0, 0.0)

    # Relative speed ranking (lower = faster)
    speed_rank: int = 0

    # Relative quality ranking (higher = better)
    quality_rank: int = 0

    # Circuit breaker instance (set by Router or CircuitBreakerManager)
    circuit_breaker: CircuitBreaker | None = None

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
        """
        Envoyer un message et recevoir une réponse complète.

        Note: Cette méthode est protégée par un circuit breaker au niveau du Router
        pour prévenir les pannes en cascade. Le circuit s'ouvre après 5 échecs
        consécutifs et rejette les appels pendant 60s avant de tester la récupération.

        Args:
            messages: Liste des messages de conversation
            model: Modèle spécifique à utiliser (optionnel)
            system: Message système (optionnel)
            temperature: Température de génération (0.0-1.0)
            max_tokens: Nombre maximum de tokens à générer

        Returns:
            LLMResponse avec le contenu et les métadonnées

        Raises:
            CircuitBreakerError: Si le circuit breaker est ouvert
            ConnectionError: Erreur de connexion au provider
            TimeoutError: Timeout de la requête
        """
        ...

    @abstractmethod
    def stream(
        self,
        messages: list[dict],
        *,
        model: str | None = None,
        system: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> AsyncIterator[str]:
        """
        Streamer la réponse token par token.

        Note: Cette méthode est protégée par un circuit breaker au niveau du Router
        pour prévenir les pannes en cascade. Le circuit s'ouvre après 5 échecs
        consécutifs et rejette les appels pendant 60s avant de tester la récupération.

        Args:
            messages: Liste des messages de conversation
            model: Modèle spécifique à utiliser (optionnel)
            system: Message système (optionnel)
            temperature: Température de génération (0.0-1.0)
            max_tokens: Nombre maximum de tokens à générer

        Yields:
            Chunks de texte au fur et à mesure de la génération

        Raises:
            CircuitBreakerError: Si le circuit breaker est ouvert
            ConnectionError: Erreur de connexion au provider
            TimeoutError: Timeout de la requête
        """
        ...

    @abstractmethod
    def available_models(self) -> list[str]:
        """Liste des modèles disponibles pour ce provider."""
        ...

    @property
    def is_configured(self) -> bool:
        """Vérifie si le provider a une clé API configurée."""
        return True
