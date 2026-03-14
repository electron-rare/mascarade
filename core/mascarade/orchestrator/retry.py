"""Mécanisme de retry avec backoff configurable pour l'orchestration."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class BackoffStrategy(StrEnum):
    """Stratégie de backoff pour les retries."""

    EXPONENTIAL = "exponential"
    LINEAR = "linear"
    CONSTANT = "constant"


@dataclass
class RetryConfig:
    """Configuration des retries avec backoff."""

    max_retries: int = 3
    strategy: BackoffStrategy = BackoffStrategy.EXPONENTIAL
    initial_delay: float = 1.0  # secondes
    max_delay: float = 60.0  # secondes
    multiplier: float = 2.0  # pour exponential et linear
    jitter: bool = True  # ajouter un jitter aléatoire
    retry_on_timeout: bool = True
    retry_on_rate_limit: bool = True
    retry_on_server_error: bool = True

    def calculate_delay(self, attempt: int) -> float:
        """Calculer le délai avant le prochain retry."""
        if self.strategy == BackoffStrategy.CONSTANT:
            delay = self.initial_delay
        elif self.strategy == BackoffStrategy.LINEAR:
            delay = self.initial_delay + (attempt * self.multiplier)
        else:  # EXPONENTIAL
            delay = self.initial_delay * (self.multiplier**attempt)

        # Appliquer la limite maximale
        delay = min(delay, self.max_delay)

        # Ajouter du jitter si activé
        if self.jitter:
            import random

            delay *= random.uniform(0.5, 1.5)

        return delay

    def should_retry(self, error: Exception) -> bool:
        """Déterminer si l'erreur justifie un retry."""
        error_msg = str(error).lower()

        if self.retry_on_timeout and ("timeout" in error_msg or "timed out" in error_msg):
            return True

        if self.retry_on_rate_limit and (
            "rate limit" in error_msg or "429" in error_msg
        ):
            return True

        if self.retry_on_server_error and (
            "500" in error_msg
            or "502" in error_msg
            or "503" in error_msg
            or "504" in error_msg
            or "server error" in error_msg
        ):
            return True

        return False


@dataclass
class RetryState:
    """État des retries pour un agent donné."""

    agent_name: str
    attempts: int = 0
    total_delay: float = 0.0
    errors: list[str] = field(default_factory=list)

    def record_attempt(self, error: str | None = None, delay: float = 0.0) -> None:
        """Enregistrer une tentative de retry."""
        self.attempts += 1
        self.total_delay += delay
        if error:
            self.errors.append(error)

    def get_stats(self) -> dict:
        """Obtenir les statistiques des retries."""
        return {
            "agent_name": self.agent_name,
            "attempts": self.attempts,
            "total_delay": self.total_delay,
            "error_count": len(self.errors),
            "last_error": self.errors[-1] if self.errors else None,
        }

    def reset(self) -> None:
        """Réinitialiser l'état des retries."""
        self.attempts = 0
        self.total_delay = 0.0
        self.errors = []
