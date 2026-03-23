"""Système de monitoring de la santé des providers LLM."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mascarade.load_balancer.balancer import LoadBalancer
    from mascarade.metrics.tracker import MetricsTracker
    from mascarade.router.providers.base import LLMProvider

logger = logging.getLogger("mascarade.health_monitor")


@dataclass
class ProviderHealth:
    """Métriques de santé pour un provider individuel."""

    provider_name: str
    health_score: float = 1.0  # 0.0 - 1.0, where 1.0 is perfect health
    latency_p50: float = 0.0
    latency_p95: float = 0.0
    latency_p99: float = 0.0
    error_rate: float = 0.0
    availability: float = 1.0
    total_requests: int = 0


class HealthMonitor:
    """Système central de monitoring de la santé des providers."""

    def __init__(
        self,
        metrics_tracker: MetricsTracker | None = None,
        load_balancer: LoadBalancer | None = None,
        health_check_interval: float = 30.0,
    ) -> None:
        self.metrics = metrics_tracker
        self.load_balancer = load_balancer
        self._health_cache: dict[str, ProviderHealth] = {}
        self._health_check_interval = health_check_interval
        self._health_check_task: asyncio.Task | None = None
        self._providers: list[LLMProvider] = []
        self._running = False

    def get_provider_health(self, provider_name: str) -> ProviderHealth:
        """Obtenir les métriques de santé pour un provider spécifique."""
        # Récupérer les données du MetricsTracker
        if self.metrics and provider_name in self.metrics.providers:
            provider_metrics = self.metrics.providers[provider_name]

            # Calculer les percentiles de latence
            p50, p95, p99 = self._calculate_percentiles(
                list(provider_metrics.response_times)
            )

            # Calculer le score de santé
            health_score = self._calculate_health_score(
                p95,
                provider_metrics.error_rate,
                provider_metrics.total_requests,
            )

            health = ProviderHealth(
                provider_name=provider_name,
                health_score=health_score,
                latency_p50=p50,
                latency_p95=p95,
                latency_p99=p99,
                error_rate=provider_metrics.error_rate,
                availability=1.0 - provider_metrics.error_rate,
                total_requests=provider_metrics.total_requests,
            )

            self._health_cache[provider_name] = health
            return health

        # Retourner un état de santé par défaut si pas de données
        if provider_name in self._health_cache:
            return self._health_cache[provider_name]

        return ProviderHealth(provider_name=provider_name)

    def get_all_health(self) -> dict[str, ProviderHealth]:
        """Obtenir les métriques de santé pour tous les providers."""
        health_stats = {}

        if self.metrics:
            for provider_name in self.metrics.providers:
                health_stats[provider_name] = self.get_provider_health(provider_name)

        return health_stats

    def _calculate_percentiles(
        self, response_times: list[float]
    ) -> tuple[float, float, float]:
        """Calculer les percentiles P50, P95, P99 des temps de réponse."""
        if not response_times:
            return 0.0, 0.0, 0.0

        sorted_times = sorted(response_times)
        n = len(sorted_times)

        p50_idx = int(n * 0.50)
        p95_idx = int(n * 0.95)
        p99_idx = int(n * 0.99)

        p50 = sorted_times[min(p50_idx, n - 1)]
        p95 = sorted_times[min(p95_idx, n - 1)]
        p99 = sorted_times[min(p99_idx, n - 1)]

        return p50, p95, p99

    def _calculate_health_score(
        self, latency_p95: float, error_rate: float, total_requests: int
    ) -> float:
        """Calculer le score de santé global (0.0 - 1.0)."""
        # Pas assez de données pour un score fiable
        if total_requests < 5:
            return 1.0

        # Score de latence (pénalise les latences élevées)
        # Latence cible: < 1s = bon, > 5s = mauvais
        if latency_p95 < 1.0:
            latency_score = 1.0
        elif latency_p95 < 5.0:
            latency_score = 1.0 - ((latency_p95 - 1.0) / 4.0) * 0.5
        else:
            latency_score = 0.5 - min((latency_p95 - 5.0) / 10.0, 0.5)

        # Score d'erreur (pénalise fortement les erreurs)
        error_score = 1.0 - (error_rate * 10.0)  # 10% erreurs = score 0

        # Score de santé combiné (60% latence, 40% erreurs)
        health_score = (latency_score * 0.6) + (error_score * 0.4)

        # Limiter entre 0.0 et 1.0
        return max(0.0, min(1.0, health_score))

    def get_healthiest_providers(
        self, provider_names: list[str], min_score: float = 0.5
    ) -> list[str]:
        """Retourner les providers les plus sains, triés par score de santé."""
        health_scores = []

        for provider_name in provider_names:
            health = self.get_provider_health(provider_name)
            if health.health_score >= min_score:
                health_scores.append((provider_name, health.health_score))

        # Trier par score décroissant (meilleur en premier)
        health_scores.sort(key=lambda x: x[1], reverse=True)

        return [name for name, _ in health_scores]

    def start_health_checks(self, providers: list[LLMProvider]) -> None:
        """Start background health check task for all providers."""
        if self._health_check_task is not None:
            logger.warning("Health checks already running")
            return

        self._providers = providers
        self._running = True
        self._health_check_task = asyncio.create_task(self._health_check_loop())
        logger.info(
            "Health checks started — interval=%ss, providers=%d",
            self._health_check_interval,
            len(self._providers),
        )

    async def stop_health_checks(self) -> None:
        """Stop background health check task."""
        self._running = False
        if self._health_check_task:
            self._health_check_task.cancel()
            try:
                await self._health_check_task
            except asyncio.CancelledError:
                pass
            self._health_check_task = None
            logger.info("Health checks stopped")

    async def _health_check_loop(self) -> None:
        """Background loop that periodically probes provider health."""
        while self._running:
            try:
                await asyncio.sleep(self._health_check_interval)
                await self._probe_all_providers()
            except asyncio.CancelledError:
                logger.debug("Health check loop cancelled")
                break
            except Exception as exc:
                logger.warning("Health check loop error: %s", exc)

    async def _probe_all_providers(self) -> None:
        """Run lightweight health probes on all providers."""
        for provider in self._providers:
            try:
                await self._probe_provider(provider)
            except Exception as exc:
                logger.debug(
                    "Health probe failed for %s: %s", provider.name, exc
                )

    async def _probe_provider(self, provider: LLMProvider) -> None:
        """Execute a lightweight health probe for a single provider."""
        try:
            # Lightweight probe: simple request with minimal content
            # This is just a connectivity check, not a full request
            import time

            start = time.perf_counter()

            # Try to get a simple completion as a health probe
            # Use the provider's send method with a minimal message
            await provider.send(
                messages=[{"role": "user", "content": "ping"}],
                model=None,  # Let provider choose default model
                max_tokens=1,
                temperature=0.0,
            )

            elapsed = time.perf_counter() - start

            # Successful probe - update health cache with good latency
            if provider.name in self._health_cache:
                self._health_cache[provider.name]
                # Keep existing health score but note the successful probe
                logger.debug(
                    "Health probe success — provider=%s latency=%.3fs",
                    provider.name,
                    elapsed,
                )
            else:
                logger.debug(
                    "Health probe success — provider=%s latency=%.3fs",
                    provider.name,
                    elapsed,
                )

        except Exception as exc:
            # Failed probe - log but don't crash
            logger.debug(
                "Health probe failed — provider=%s error=%s",
                provider.name,
                str(exc)[:100],
            )
