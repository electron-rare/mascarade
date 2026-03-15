"""Mécanisme de fallback pour le routeur LLM."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mascarade.router.health_monitor import HealthMonitor


@dataclass
class FallbackState:
    """Etat du mecanisme de fallback."""

    max_attempts: int = 3
    failed_attempts: dict[str, int] = field(default_factory=dict)

    def build_sequence(
        self,
        strategy: str,
        provider: str | None,
        available_providers: list[str],
        health_monitor: HealthMonitor | None = None,
    ) -> list[tuple[str, str | None]]:
        """Construire la séquence de fallback."""

        if strategy == "specific" and provider:
            return [(strategy, provider)]

        # Trier les providers par santé si health_monitor est disponible
        sorted_providers = available_providers
        if health_monitor:
            sorted_providers = health_monitor.get_healthiest_providers(
                available_providers
            )

        sequence: list[tuple[str, str | None]] = []

        # Premier essai : la requête originale
        if provider:
            sequence.append((strategy, provider))
        else:
            sequence.append((strategy, None))

        # Essais supplémentaires : essayer d'autres stratégies
        fallback_strategies = ["best", "cheapest", "fastest"]
        for fallback_strategy in fallback_strategies:
            if fallback_strategy != strategy:
                sequence.append((fallback_strategy, None))

        # Dernier essai : essayer des providers spécifiques (triés par santé)
        for available_provider in sorted_providers:
            if not provider or available_provider != provider:
                sequence.append((strategy, available_provider))

        # Limiter au nombre maximum d'essais
        return sequence[: self.max_attempts]

    def record_failure(self, provider_name: str) -> None:
        """Enregistrer un échec pour un provider."""
        self.failed_attempts[provider_name] = (
            self.failed_attempts.get(provider_name, 0) + 1
        )

    def get_failure_stats(self) -> dict:
        """Obtenir les statistiques des échecs."""
        return {
            "failed_attempts": dict(self.failed_attempts),
            "total_failures": sum(self.failed_attempts.values()),
        }

    def reset(self) -> None:
        """Réinitialiser les statistiques des échecs."""
        self.failed_attempts = {}
