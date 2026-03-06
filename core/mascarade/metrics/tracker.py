"""Système de tracking des métriques pour les providers LLM."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class ProviderMetrics:
    """Métriques de performance pour un provider individuel."""

    provider_name: str
    total_requests: int = 0
    total_tokens: int = 0
    total_cost: float = 0.0
    avg_response_time: float = 0.0
    error_rate: float = 0.0
    last_used: datetime | None = None
    response_times: list[float] = field(default_factory=list)

    def update(
        self, tokens: int, cost: float, response_time: float, success: bool
    ) -> None:
        """Mettre à jour les métriques avec les données d'une nouvelle requête."""
        self.total_requests += 1
        self.total_tokens += tokens
        self.total_cost += cost
        self.response_times.append(response_time)

        # Mettre à jour le temps de réponse moyen
        if self.total_requests == 1:
            self.avg_response_time = response_time
        else:
            self.avg_response_time = (
                (self.avg_response_time * (self.total_requests - 1)) + response_time
            ) / self.total_requests

        # Mettre à jour le taux d'erreur
        if not success:
            self.error_rate = (
                (self.error_rate * (self.total_requests - 1)) + 1
            ) / self.total_requests

        self.last_used = datetime.now()


class MetricsTracker:
    """Système central de tracking des métriques."""

    def __init__(self) -> None:
        self.providers: dict[str, ProviderMetrics] = {}
        self.request_history: list[dict] = []
        self.max_history = 1000

    def track_request(
        self,
        provider_name: str,
        tokens: int,
        cost: float,
        response_time: float,
        success: bool,
        strategy: str | None = None,
    ) -> None:
        """Suivre une requête terminée."""
        if provider_name not in self.providers:
            self.providers[provider_name] = ProviderMetrics(provider_name)

        self.providers[provider_name].update(tokens, cost, response_time, success)

        # Stocker dans l'historique
        request_data = {
            "timestamp": datetime.now(),
            "provider": provider_name,
            "tokens": tokens,
            "cost": cost,
            "response_time": response_time,
            "success": success,
            "strategy": strategy,
        }

        self.request_history.append(request_data)
        if len(self.request_history) > self.max_history:
            self.request_history.pop(0)

    def get_provider_stats(self, provider_name: str) -> dict:
        """Obtenir les statistiques pour un provider spécifique."""
        if provider_name not in self.providers:
            return {}

        metrics = self.providers[provider_name]
        return {
            "total_requests": metrics.total_requests,
            "total_tokens": metrics.total_tokens,
            "total_cost": round(metrics.total_cost, 4),
            "avg_response_time": round(metrics.avg_response_time, 2),
            "error_rate": round(metrics.error_rate * 100, 2),
            "last_used": metrics.last_used.isoformat() if metrics.last_used else None,
        }

    def get_summary(self) -> dict:
        """Obtenir un résumé des métriques du système."""
        return {
            "providers": {
                name: self.get_provider_stats(name) for name in self.providers
            },
            "total_requests": sum(p.total_requests for p in self.providers.values()),
            "total_cost": round(sum(p.total_cost for p in self.providers.values()), 4),
            "best_performer": self._get_best_performer(),
        }

    def reset(self) -> None:
        """Reset all metrics."""
        self.providers.clear()
        self.request_history.clear()

    def _get_best_performer(self) -> str | None:
        """Déterminer le meilleur provider."""
        if not self.providers:
            return None

        # Score basé sur le temps de réponse et le taux d'erreur
        best_provider = None
        best_score = float("inf")

        for name, metrics in self.providers.items():
            if metrics.total_requests < 5:  # Besoin de données minimales
                continue

            score = metrics.avg_response_time * (
                1 + metrics.error_rate * 10
            )  # Pénaliser les erreurs

            if score < best_score:
                best_score = score
                best_provider = name

        return best_provider
