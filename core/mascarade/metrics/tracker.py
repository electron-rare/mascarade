"""Système de tracking des métriques pour les providers LLM."""

from __future__ import annotations

from collections import deque
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
    response_times: deque[float] = field(default_factory=lambda: deque(maxlen=500))

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

        # Mettre à jour le taux d'erreur (running average)
        if not success:
            self.error_rate = (
                (self.error_rate * (self.total_requests - 1)) + 1.0
            ) / self.total_requests
        else:
            if self.total_requests > 1:
                self.error_rate = (
                    self.error_rate * (self.total_requests - 1)
                ) / self.total_requests

        self.last_used = datetime.now()


@dataclass
class ClassifierMetrics:
    """Métriques de performance pour le classifier ML."""

    total_predictions: int = 0
    correct_predictions: int = 0
    accuracy: float = 0.0
    avg_latency: float = 0.0
    latencies: deque[float] = field(default_factory=lambda: deque(maxlen=500))
    predictions_by_domain: dict[str, int] = field(default_factory=dict)
    last_used: datetime | None = None

    def update(
        self,
        latency: float,
        predicted_domain: str,
        was_correct: bool | None = None,
    ) -> None:
        """Mettre à jour les métriques avec les données d'une nouvelle prédiction.

        Args:
            latency: Temps d'inférence en secondes
            predicted_domain: Domaine prédit par le classifier
            was_correct: Si connu, indique si la prédiction était correcte (pour le calcul de l'accuracy)
        """
        self.total_predictions += 1
        self.latencies.append(latency)

        # Mettre à jour le compteur par domaine
        self.predictions_by_domain[predicted_domain] = (
            self.predictions_by_domain.get(predicted_domain, 0) + 1
        )

        # Mettre à jour la latence moyenne
        if self.total_predictions == 1:
            self.avg_latency = latency
        else:
            self.avg_latency = (
                (self.avg_latency * (self.total_predictions - 1)) + latency
            ) / self.total_predictions

        # Mettre à jour l'accuracy si on sait si la prédiction était correcte
        if was_correct is not None:
            if was_correct:
                self.correct_predictions += 1
            self.accuracy = self.correct_predictions / self.total_predictions

        self.last_used = datetime.now()


class MetricsTracker:
    """Système central de tracking des métriques."""

    def __init__(self) -> None:
        self.providers: dict[str, ProviderMetrics] = {}
        self.request_history: deque[dict] = deque(maxlen=1000)
        self.classifier: ClassifierMetrics = ClassifierMetrics()

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

    def track_classifier_prediction(
        self,
        latency: float,
        predicted_domain: str,
        was_correct: bool | None = None,
    ) -> None:
        """Suivre une prédiction du classifier ML.

        Args:
            latency: Temps d'inférence en secondes
            predicted_domain: Domaine prédit
            was_correct: Si connu, indique si la prédiction était correcte
        """
        self.classifier.update(latency, predicted_domain, was_correct)

        # Mettre à jour les métriques Prometheus si disponibles
        try:
            from mascarade.analytics.prometheus_metrics import (
                classifier_accuracy,
                classifier_latency,
                classifier_predictions_total,
            )

            if classifier_latency:
                classifier_latency.observe(latency)

            if classifier_predictions_total:
                classifier_predictions_total.labels(
                    predicted_domain=predicted_domain
                ).inc()

            if classifier_accuracy and self.classifier.total_predictions > 0:
                classifier_accuracy.set(self.classifier.accuracy)

        except ImportError:
            # Prometheus metrics not available
            pass

    def get_classifier_stats(self) -> dict:
        """Obtenir les statistiques du classifier ML."""
        return {
            "total_predictions": self.classifier.total_predictions,
            "correct_predictions": self.classifier.correct_predictions,
            "accuracy": round(self.classifier.accuracy, 4),
            "avg_latency_ms": round(self.classifier.avg_latency * 1000, 2),
            "predictions_by_domain": self.classifier.predictions_by_domain,
            "last_used": (
                self.classifier.last_used.isoformat()
                if self.classifier.last_used
                else None
            ),
        }

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
            "classifier": self.get_classifier_stats(),
        }

    def reset(self) -> None:
        """Reset all metrics."""
        self.providers.clear()
        self.request_history.clear()
        self.classifier = ClassifierMetrics()

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
