"""Benchmark suite orchestrator pour coordonner les benchmarks et agréger les résultats."""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum

from mascarade.benchmarks.runner import BenchmarkResult, BenchmarkRunner
from mascarade.benchmarks.test_prompts import get_all_domains
from mascarade.router import Router

logger = logging.getLogger("mascarade.benchmarks.suite")


class BenchmarkScope(StrEnum):
    """Portée d'exécution du benchmark."""

    SINGLE_PROVIDER = "single_provider"
    ALL_PROVIDERS = "all_providers"
    DOMAIN_SPECIFIC = "domain_specific"
    FULL_SUITE = "full_suite"


@dataclass
class BenchmarkRun:
    """Représente une exécution complète de benchmark."""

    run_id: str
    scope: BenchmarkScope
    start_time: datetime
    end_time: datetime | None = None
    total_benchmarks: int = 0
    successful_benchmarks: int = 0
    failed_benchmarks: int = 0
    providers_tested: list[str] = field(default_factory=list)
    domains_tested: list[str] = field(default_factory=list)
    results: list[BenchmarkResult] = field(default_factory=list)
    error: str | None = None

    @property
    def duration_seconds(self) -> float:
        """Durée de l'exécution en secondes."""
        if self.end_time is None:
            return 0.0
        return (self.end_time - self.start_time).total_seconds()

    @property
    def success_rate(self) -> float:
        """Taux de réussite en pourcentage."""
        if self.total_benchmarks == 0:
            return 0.0
        return (self.successful_benchmarks / self.total_benchmarks) * 100


@dataclass
class BenchmarkSuite:
    """Orchestrateur de benchmark suite pour coordonner les tests de performance."""

    router: Router | None = None
    runner: BenchmarkRunner | None = None
    run_history: list[BenchmarkRun] = field(default_factory=list)
    max_history: int = 100

    def __post_init__(self) -> None:
        """Initialiser les composants après création."""
        if self.router is None:
            self.router = Router()
        if self.runner is None:
            self.runner = BenchmarkRunner(router=self.router)

    def _generate_run_id(self) -> str:
        """Générer un ID unique pour une exécution de benchmark."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"bench_{timestamp}_{len(self.run_history)}"

    def _record_run(self, run: BenchmarkRun) -> None:
        """Enregistrer une exécution dans l'historique."""
        self.run_history.append(run)
        # Limiter la taille de l'historique
        if len(self.run_history) > self.max_history:
            self.run_history = self.run_history[-self.max_history :]

    async def run_single_provider(
        self,
        provider_name: str,
        *,
        domain: str | None = None,
        difficulty: str | None = None,
        model: str | None = None,
        limit: int | None = None,
    ) -> BenchmarkRun:
        """
        Exécuter un benchmark pour un seul provider.

        Args:
            provider_name: Nom du provider à benchmarker
            domain: Domaine spécifique à tester (optionnel)
            difficulty: Niveau de difficulté à tester (optionnel)
            model: Modèle spécifique à utiliser (optionnel)
            limit: Nombre maximum de prompts à tester (optionnel)

        Returns:
            BenchmarkRun contenant les résultats
        """
        run_id = self._generate_run_id()
        start_time = datetime.now()

        logger.info(
            "Démarrage du benchmark suite pour provider %s (run_id=%s)",
            provider_name,
            run_id,
        )

        run = BenchmarkRun(
            run_id=run_id,
            scope=BenchmarkScope.SINGLE_PROVIDER,
            start_time=start_time,
            providers_tested=[provider_name],
        )

        try:
            results = await self.runner.run_provider_benchmark(
                provider_name,
                domain=domain,
                difficulty=difficulty,
                model=model,
                limit=limit,
            )

            run.results = results
            run.total_benchmarks = len(results)
            run.successful_benchmarks = sum(1 for r in results if r.success)
            run.failed_benchmarks = sum(1 for r in results if not r.success)

            # Collecter les domaines testés
            domains = set(r.domain for r in results)
            run.domains_tested = sorted(domains)

        except Exception as exc:
            logger.error("Erreur lors du benchmark pour %s: %s", provider_name, exc)
            run.error = str(exc)

        run.end_time = datetime.now()
        self._record_run(run)

        logger.info(
            "Benchmark terminé pour %s: %d/%d réussis en %.2fs",
            provider_name,
            run.successful_benchmarks,
            run.total_benchmarks,
            run.duration_seconds,
        )

        return run

    async def run_all_providers(
        self,
        *,
        domain: str | None = None,
        difficulty: str | None = None,
        limit: int | None = None,
    ) -> BenchmarkRun:
        """
        Exécuter un benchmark sur tous les providers disponibles.

        Args:
            domain: Domaine spécifique à tester (optionnel)
            difficulty: Niveau de difficulté à tester (optionnel)
            limit: Nombre maximum de prompts par provider (optionnel)

        Returns:
            BenchmarkRun contenant les résultats agrégés
        """
        run_id = self._generate_run_id()
        start_time = datetime.now()

        logger.info("Démarrage du benchmark suite pour tous les providers (run_id=%s)", run_id)

        run = BenchmarkRun(
            run_id=run_id,
            scope=BenchmarkScope.ALL_PROVIDERS,
            start_time=start_time,
        )

        try:
            results_by_provider = await self.runner.run_all_providers_benchmark(
                domain=domain,
                difficulty=difficulty,
                limit=limit,
            )

            # Agréger tous les résultats
            all_results = []
            providers_tested = []

            for provider_name, results in results_by_provider.items():
                all_results.extend(results)
                if results:
                    providers_tested.append(provider_name)

            run.results = all_results
            run.total_benchmarks = len(all_results)
            run.successful_benchmarks = sum(1 for r in all_results if r.success)
            run.failed_benchmarks = sum(1 for r in all_results if not r.success)
            run.providers_tested = sorted(providers_tested)

            # Collecter les domaines testés
            domains = set(r.domain for r in all_results)
            run.domains_tested = sorted(domains)

        except Exception as exc:
            logger.error("Erreur lors du benchmark de tous les providers: %s", exc)
            run.error = str(exc)

        run.end_time = datetime.now()
        self._record_run(run)

        logger.info(
            "Benchmark terminé pour %d providers: %d/%d réussis en %.2fs",
            len(run.providers_tested),
            run.successful_benchmarks,
            run.total_benchmarks,
            run.duration_seconds,
        )

        return run

    async def run_domain_benchmark(
        self,
        domain: str,
        *,
        providers: list[str] | None = None,
        difficulty: str | None = None,
        limit: int | None = None,
    ) -> BenchmarkRun:
        """
        Exécuter un benchmark pour un domaine spécifique.

        Args:
            domain: Domaine à tester (electronics, spice, kicad, stm32, code, general)
            providers: Liste de providers à tester (tous si None)
            difficulty: Niveau de difficulté à tester (optionnel)
            limit: Nombre maximum de prompts par provider (optionnel)

        Returns:
            BenchmarkRun contenant les résultats
        """
        run_id = self._generate_run_id()
        start_time = datetime.now()

        logger.info(
            "Démarrage du benchmark suite pour domaine %s (run_id=%s)",
            domain,
            run_id,
        )

        run = BenchmarkRun(
            run_id=run_id,
            scope=BenchmarkScope.DOMAIN_SPECIFIC,
            start_time=start_time,
            domains_tested=[domain],
        )

        try:
            # Déterminer les providers à tester
            if providers is None:
                providers = self.router.available_providers

            all_results = []
            providers_tested = []

            # Exécuter pour chaque provider
            for provider_name in providers:
                try:
                    results = await self.runner.run_provider_benchmark(
                        provider_name,
                        domain=domain,
                        difficulty=difficulty,
                        limit=limit,
                    )
                    all_results.extend(results)
                    if results:
                        providers_tested.append(provider_name)
                except Exception as exc:
                    logger.warning(
                        "Erreur lors du benchmark de %s pour domaine %s: %s",
                        provider_name,
                        domain,
                        exc,
                    )

            run.results = all_results
            run.total_benchmarks = len(all_results)
            run.successful_benchmarks = sum(1 for r in all_results if r.success)
            run.failed_benchmarks = sum(1 for r in all_results if not r.success)
            run.providers_tested = sorted(providers_tested)

        except Exception as exc:
            logger.error("Erreur lors du benchmark du domaine %s: %s", domain, exc)
            run.error = str(exc)

        run.end_time = datetime.now()
        self._record_run(run)

        logger.info(
            "Benchmark terminé pour domaine %s: %d/%d réussis en %.2fs",
            domain,
            run.successful_benchmarks,
            run.total_benchmarks,
            run.duration_seconds,
        )

        return run

    async def run_full_suite(
        self,
        *,
        providers: list[str] | None = None,
        limit_per_domain: int | None = None,
    ) -> BenchmarkRun:
        """
        Exécuter la suite complète de benchmarks sur tous les domaines.

        Args:
            providers: Liste de providers à tester (tous si None)
            limit_per_domain: Limite de prompts par domaine (optionnel)

        Returns:
            BenchmarkRun contenant les résultats agrégés
        """
        run_id = self._generate_run_id()
        start_time = datetime.now()

        logger.info("Démarrage du benchmark suite complet (run_id=%s)", run_id)

        run = BenchmarkRun(
            run_id=run_id,
            scope=BenchmarkScope.FULL_SUITE,
            start_time=start_time,
        )

        try:
            # Déterminer les providers à tester
            if providers is None:
                providers = self.router.available_providers

            all_results = []
            domains_tested = set()
            providers_tested = set()

            # Exécuter pour chaque domaine
            for domain in get_all_domains():
                logger.info("Benchmark du domaine %s...", domain)

                for provider_name in providers:
                    try:
                        results = await self.runner.run_provider_benchmark(
                            provider_name,
                            domain=domain,
                            limit=limit_per_domain,
                        )
                        all_results.extend(results)
                        if results:
                            domains_tested.add(domain)
                            providers_tested.add(provider_name)
                    except Exception as exc:
                        logger.warning(
                            "Erreur lors du benchmark de %s/%s: %s",
                            provider_name,
                            domain,
                            exc,
                        )

            run.results = all_results
            run.total_benchmarks = len(all_results)
            run.successful_benchmarks = sum(1 for r in all_results if r.success)
            run.failed_benchmarks = sum(1 for r in all_results if not r.success)
            run.providers_tested = sorted(providers_tested)
            run.domains_tested = sorted(domains_tested)

        except Exception as exc:
            logger.error("Erreur lors du benchmark suite complet: %s", exc)
            run.error = str(exc)

        run.end_time = datetime.now()
        self._record_run(run)

        logger.info(
            "Benchmark suite complet terminé: %d providers, %d domaines, %d/%d réussis en %.2fs",
            len(run.providers_tested),
            len(run.domains_tested),
            run.successful_benchmarks,
            run.total_benchmarks,
            run.duration_seconds,
        )

        return run

    def get_leaderboard(
        self,
        *,
        domain: str | None = None,
        metric: str = "latency",
    ) -> list[dict]:
        """
        Obtenir le classement des providers basé sur les résultats.

        Args:
            domain: Filtrer par domaine (optionnel)
            metric: Métrique à utiliser (latency, cost, success_rate)

        Returns:
            Liste de dictionnaires avec les résultats classés
        """
        if not self.runner or not self.runner.provider_stats:
            return []

        # Collecter les statistiques par provider
        leaderboard = []

        for provider_name, stats in self.runner.provider_stats.items():
            if stats.successful_runs == 0:
                continue

            entry = {
                "provider": provider_name,
                "avg_latency": stats.avg_latency,
                "min_latency": stats.min_latency if stats.min_latency != float("inf") else 0,
                "max_latency": stats.max_latency,
                "total_cost": stats.total_cost,
                "success_rate": (stats.successful_runs / stats.total_runs * 100)
                if stats.total_runs > 0
                else 0,
                "total_runs": stats.total_runs,
                "successful_runs": stats.successful_runs,
            }

            leaderboard.append(entry)

        # Trier selon la métrique choisie
        if metric == "latency":
            leaderboard.sort(key=lambda x: x["avg_latency"])
        elif metric == "cost":
            leaderboard.sort(key=lambda x: x["total_cost"])
        elif metric == "success_rate":
            leaderboard.sort(key=lambda x: x["success_rate"], reverse=True)

        return leaderboard

    def get_domain_stats(self) -> dict[str, dict]:
        """
        Obtenir les statistiques par domaine.

        Returns:
            Dictionnaire avec les stats de chaque domaine
        """
        domain_stats = defaultdict(
            lambda: {
                "total": 0,
                "successful": 0,
                "failed": 0,
                "avg_latency": 0.0,
                "total_cost": 0.0,
            }
        )

        # Agréger les résultats
        for result in self.runner.results:
            stats = domain_stats[result.domain]
            stats["total"] += 1

            if result.success:
                stats["successful"] += 1
                stats["avg_latency"] += result.latency
                stats["total_cost"] += result.cost
            else:
                stats["failed"] += 1

        # Calculer les moyennes
        for domain, stats in domain_stats.items():
            if stats["successful"] > 0:
                stats["avg_latency"] /= stats["successful"]
                stats["success_rate"] = (stats["successful"] / stats["total"]) * 100
            else:
                stats["success_rate"] = 0.0

        return dict(domain_stats)

    def get_run_by_id(self, run_id: str) -> BenchmarkRun | None:
        """
        Retrouver une exécution par son ID.

        Args:
            run_id: ID de l'exécution

        Returns:
            BenchmarkRun si trouvé, None sinon
        """
        for run in self.run_history:
            if run.run_id == run_id:
                return run
        return None

    def get_latest_run(self) -> BenchmarkRun | None:
        """
        Obtenir la dernière exécution de benchmark.

        Returns:
            BenchmarkRun le plus récent ou None
        """
        if not self.run_history:
            return None
        return self.run_history[-1]

    def clear_history(self) -> None:
        """Effacer l'historique des exécutions."""
        self.run_history.clear()
        logger.info("Historique des benchmarks effacé")

    def get_summary(self) -> dict:
        """
        Obtenir un résumé global de tous les benchmarks.

        Returns:
            Dictionnaire avec les statistiques globales
        """
        return {
            "total_runs": len(self.run_history),
            "latest_run": (
                {
                    "run_id": self.run_history[-1].run_id,
                    "scope": self.run_history[-1].scope,
                    "success_rate": self.run_history[-1].success_rate,
                    "duration_seconds": self.run_history[-1].duration_seconds,
                }
                if self.run_history
                else None
            ),
            "runner_stats": self.runner.get_summary() if self.runner else {},
            "domain_stats": self.get_domain_stats(),
            "leaderboard": self.get_leaderboard(),
        }
