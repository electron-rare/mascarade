"""Benchmark runner pour évaluer les performances des providers LLM."""

from __future__ import annotations

import asyncio
import logging
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime

from mascarade.benchmarks.test_prompts import (
    get_all_prompts,
    get_prompts_by_difficulty,
    get_test_prompts,
)
from mascarade.router.router import Router, Strategy

logger = logging.getLogger("mascarade.benchmarks")


@dataclass
class BenchmarkResult:
    """Résultat d'un benchmark individuel."""

    prompt_id: str
    provider: str
    model: str
    domain: str
    difficulty: str
    latency: float
    tokens: int
    cost: float
    success: bool
    error_message: str | None = None
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class ProviderBenchmarkStats:
    """Statistiques de benchmark pour un provider."""

    provider_name: str
    total_runs: int = 0
    successful_runs: int = 0
    failed_runs: int = 0
    total_latency: float = 0.0
    avg_latency: float = 0.0
    min_latency: float = float("inf")
    max_latency: float = 0.0
    total_tokens: int = 0
    total_cost: float = 0.0
    latencies: deque[float] = field(default_factory=lambda: deque(maxlen=1000))

    def update(self, result: BenchmarkResult) -> None:
        """Mettre à jour les statistiques avec un nouveau résultat."""
        self.total_runs += 1

        if result.success:
            self.successful_runs += 1
            self.total_latency += result.latency
            self.latencies.append(result.latency)
            self.total_tokens += result.tokens
            self.total_cost += result.cost

            self.min_latency = min(self.min_latency, result.latency)
            self.max_latency = max(self.max_latency, result.latency)

            # Calculer la latence moyenne
            if self.successful_runs > 0:
                self.avg_latency = self.total_latency / self.successful_runs
        else:
            self.failed_runs += 1

    def get_summary(self) -> dict:
        """Obtenir un résumé des statistiques."""
        success_rate = (
            (self.successful_runs / self.total_runs * 100)
            if self.total_runs > 0
            else 0.0
        )

        return {
            "provider": self.provider_name,
            "total_runs": self.total_runs,
            "successful_runs": self.successful_runs,
            "failed_runs": self.failed_runs,
            "success_rate": round(success_rate, 2),
            "avg_latency": round(self.avg_latency, 2),
            "min_latency": (
                round(self.min_latency, 2) if self.min_latency != float("inf") else 0
            ),
            "max_latency": round(self.max_latency, 2),
            "total_tokens": self.total_tokens,
            "total_cost": round(self.total_cost, 4),
        }


class BenchmarkRunner:
    """Runner pour exécuter des benchmarks de performance sur les providers LLM."""

    def __init__(self, router: Router | None = None) -> None:
        """
        Initialiser le benchmark runner.

        Args:
            router: Instance du router LLM. Si None, en créer une nouvelle.
        """
        self.router = router or Router()
        self.results: list[BenchmarkResult] = []
        self.provider_stats: dict[str, ProviderBenchmarkStats] = {}
        self.domain_stats: dict[str, dict] = defaultdict(
            lambda: {"total": 0, "success": 0}
        )

    def _get_provider_stats(self, provider_name: str) -> ProviderBenchmarkStats:
        """Obtenir ou créer les statistiques pour un provider."""
        if provider_name not in self.provider_stats:
            self.provider_stats[provider_name] = ProviderBenchmarkStats(provider_name)
        return self.provider_stats[provider_name]

    async def run_single_benchmark(
        self,
        prompt: dict,
        provider_name: str,
        model: str | None = None,
    ) -> BenchmarkResult:
        """
        Exécuter un benchmark individuel.

        Args:
            prompt: Dictionnaire contenant les données du prompt de test
            provider_name: Nom du provider à tester
            model: Modèle spécifique à utiliser (optionnel)

        Returns:
            Résultat du benchmark
        """
        prompt_text = prompt["prompt"]
        prompt_id = prompt["id"]
        difficulty = prompt.get("difficulty", "unknown")

        # Extraire le domaine du prompt_id (ex: "elec-001" -> "electronics")
        domain = prompt_id.split("-")[0] if "-" in prompt_id else "unknown"

        start_time = time.perf_counter()
        error_message = None
        success = False
        tokens = 0
        cost = 0.0
        model_used = model or "default"

        try:
            response = await self.router.send(
                messages=[{"role": "user", "content": prompt_text}],
                strategy=Strategy.SPECIFIC,
                provider=provider_name,
                model=model,
                temperature=0.7,
                max_tokens=2048,
            )

            latency = time.perf_counter() - start_time
            success = True
            tokens = sum(response.usage.values()) if response.usage else 0
            model_used = response.model

            # Calculer le coût basé sur le provider
            if provider_name in self.router._providers:
                provider = self.router._providers[provider_name]
                input_tokens = response.usage.get("input_tokens", 0)
                output_tokens = response.usage.get("output_tokens", 0)
                in_cost, out_cost = provider.cost_per_million
                cost = (
                    (input_tokens * in_cost) + (output_tokens * out_cost)
                ) / 1_000_000

        except Exception as exc:
            latency = time.perf_counter() - start_time
            error_message = str(exc)
            logger.warning(
                "Benchmark failed for %s with provider %s: %s",
                prompt_id,
                provider_name,
                error_message,
            )

        result = BenchmarkResult(
            prompt_id=prompt_id,
            provider=provider_name,
            model=model_used,
            domain=domain,
            difficulty=difficulty,
            latency=latency,
            tokens=tokens,
            cost=cost,
            success=success,
            error_message=error_message,
        )

        # Mettre à jour les statistiques
        self._get_provider_stats(provider_name).update(result)
        self.domain_stats[domain]["total"] += 1
        if success:
            self.domain_stats[domain]["success"] += 1

        self.results.append(result)

        return result

    async def run_provider_benchmark(
        self,
        provider_name: str,
        *,
        domain: str | None = None,
        difficulty: str | None = None,
        model: str | None = None,
        limit: int | None = None,
    ) -> list[BenchmarkResult]:
        """
        Exécuter un benchmark complet pour un provider.

        Args:
            provider_name: Nom du provider à benchmarker
            domain: Domaine spécifique à tester (optionnel)
            difficulty: Niveau de difficulté à tester (optionnel)
            model: Modèle spécifique à utiliser (optionnel)
            limit: Nombre maximum de prompts à tester (optionnel)

        Returns:
            Liste des résultats de benchmark
        """
        if provider_name not in self.router.available_providers:
            raise ValueError(
                f"Provider '{provider_name}' non disponible. "
                f"Disponibles: {self.router.available_providers}"
            )

        # Sélectionner les prompts
        if domain:
            prompts = get_test_prompts(domain, difficulty)
        elif difficulty:
            prompts = get_prompts_by_difficulty(difficulty)
        else:
            prompts = get_all_prompts()

        if limit:
            prompts = prompts[:limit]

        logger.info(
            "Démarrage du benchmark pour %s avec %d prompts",
            provider_name,
            len(prompts),
        )

        # Exécuter les benchmarks
        tasks = [
            self.run_single_benchmark(prompt, provider_name, model)
            for prompt in prompts
        ]

        results = await asyncio.gather(*tasks, return_exceptions=False)

        logger.info(
            "Benchmark terminé pour %s: %d/%d réussis",
            provider_name,
            sum(1 for r in results if r.success),
            len(results),
        )

        return results

    async def run_all_providers_benchmark(
        self,
        *,
        domain: str | None = None,
        difficulty: str | None = None,
        limit: int | None = None,
    ) -> dict[str, list[BenchmarkResult]]:
        """
        Exécuter un benchmark sur tous les providers disponibles.

        Args:
            domain: Domaine spécifique à tester (optionnel)
            difficulty: Niveau de difficulté à tester (optionnel)
            limit: Nombre maximum de prompts par provider (optionnel)

        Returns:
            Dictionnaire des résultats par provider
        """
        available_providers = self.router.available_providers

        if not available_providers:
            raise RuntimeError("Aucun provider LLM configuré. Vérifiez vos clés API.")

        logger.info(
            "Démarrage du benchmark sur %d providers: %s",
            len(available_providers),
            ", ".join(available_providers),
        )

        results_by_provider = {}

        for provider_name in available_providers:
            try:
                results = await self.run_provider_benchmark(
                    provider_name,
                    domain=domain,
                    difficulty=difficulty,
                    limit=limit,
                )
                results_by_provider[provider_name] = results
            except Exception as exc:
                logger.error(
                    "Erreur lors du benchmark du provider %s: %s",
                    provider_name,
                    exc,
                )
                results_by_provider[provider_name] = []

        return results_by_provider

    def get_summary(self) -> dict:
        """
        Obtenir un résumé complet des benchmarks.

        Returns:
            Dictionnaire contenant les statistiques globales
        """
        return {
            "total_benchmarks": len(self.results),
            "successful_benchmarks": sum(1 for r in self.results if r.success),
            "failed_benchmarks": sum(1 for r in self.results if not r.success),
            "providers": {
                name: stats.get_summary() for name, stats in self.provider_stats.items()
            },
            "domains": dict(self.domain_stats),
        }

    def get_fastest_provider(self) -> str | None:
        """
        Identifier le provider le plus rapide basé sur la latence moyenne.

        Returns:
            Nom du provider le plus rapide ou None si aucun résultat
        """
        if not self.provider_stats:
            return None

        fastest = min(
            self.provider_stats.items(),
            key=lambda x: (
                x[1].avg_latency if x[1].successful_runs > 0 else float("inf")
            ),
        )

        return fastest[0] if fastest[1].successful_runs > 0 else None

    def get_cheapest_provider(self) -> str | None:
        """
        Identifier le provider le moins cher basé sur le coût total.

        Returns:
            Nom du provider le moins cher ou None si aucun résultat
        """
        if not self.provider_stats:
            return None

        cheapest = min(
            self.provider_stats.items(),
            key=lambda x: x[1].total_cost if x[1].successful_runs > 0 else float("inf"),
        )

        return cheapest[0] if cheapest[1].successful_runs > 0 else None

    def reset(self) -> None:
        """Réinitialiser toutes les statistiques et résultats."""
        self.results.clear()
        self.provider_stats.clear()
        self.domain_stats.clear()
