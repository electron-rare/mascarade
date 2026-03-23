"""Routeur LLM — dispatch intelligent entre providers."""

from __future__ import annotations

import logging
import re
import time
from collections.abc import AsyncIterator
from enum import StrEnum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    pass

from mascarade.analytics import COST_METRICS
from mascarade.analytics.clickhouse_logger import get_cost_logger
from mascarade.analytics.cost_calculator import get_cost_calculator
from mascarade.cache.multi_tier_cache import MultiTierCache
from mascarade.config import secret_value, settings
from mascarade.load_balancer.balancer import LoadBalancer
from mascarade.metrics.tracker import MetricsTracker
from mascarade.observability.langfuse import (
    start_langfuse_generation,
    update_langfuse_generation,
)
from mascarade.project_scope import normalize_scope
from mascarade.router.circuit_breaker import CircuitBreaker
from mascarade.router.fallback import FallbackState
from mascarade.router.health_monitor import HealthMonitor
from mascarade.router.model_registry import ModelRegistry
from mascarade.router.providers.base import LLMProvider, LLMResponse

try:
    from mascarade.router.classifier import get_classifier
except ImportError:
    get_classifier = None  # type: ignore[assignment,misc]

try:
    from mascarade.router.ml_classifier import get_routing_classifier
except ImportError:
    get_routing_classifier = None  # type: ignore[assignment,misc]

logger = logging.getLogger("mascarade.router")

try:
    from mascarade.benchmarks.storage import BenchmarkStorage
except ImportError:
    BenchmarkStorage = None  # type: ignore[assignment,misc]


class Strategy(StrEnum):
    BEST = "best"
    CHEAPEST = "cheapest"
    DOMAIN = "domain"
    FASTEST = "fastest"
    SPECIFIC = "specific"
    ROUTELLM = "routellm"


def detect_domain(content: str) -> str | None:
    """
    Detect domain from message content based on keywords.

    Args:
        content: Text content to analyze

    Returns:
        Detected domain or None
    """
    # Keywords for each domain
    domain_keywords = {
        "spice": ["spice", "simulation", "ngspice", "ltspice", "circuit simulation"],
        "kicad": ["kicad", "pcb", "schematic", "footprint", "kicad_pcb"],
        "stm32": ["stm32", "arm cortex", "hal", "cubemx", "stm32f", "stm32l"],
        "electronics": [
            "circuit",
            "resistor",
            "capacitor",
            "transistor",
            "voltage",
            "current",
            "amplifier",
            "oscillator",
        ],
        "code": [
            "python",
            "javascript",
            "function",
            "class",
            "api",
            "algorithm",
            "debug",
            "refactor",
        ],
    }

    # Normalize content to lowercase for matching
    content_lower = content.lower()

    # Check for domain keywords
    for domain, keywords in domain_keywords.items():
        if any(keyword in content_lower for keyword in keywords):
            return domain

    return None


class Router:
    """Routeur intelligent entre providers LLM."""

    def __init__(self) -> None:
        self._providers: dict[str, LLMProvider] = {}
        self.cache = self._initialize_cache()
        self.metrics = MetricsTracker()
        self.load_balancer = LoadBalancer()
        self.fallback = FallbackState(max_attempts=3)
        self.model_registry = ModelRegistry()
        self.benchmark_storage = BenchmarkStorage() if BenchmarkStorage else None
        self.circuit_breaker = CircuitBreaker()
        self.health_monitor = HealthMonitor(
            metrics_tracker=self.metrics,
            load_balancer=self.load_balancer,
        )
        self.cost_logger = get_cost_logger()
        self.cost_calculator = get_cost_calculator()
        self.scheduler = None  # Set by server.py when scheduler_enabled

        # ML classifier for domain detection (optional)
        self.use_classifier = settings.use_ml_classifier
        self.classifier = None
        if self.use_classifier and get_classifier is not None:
            try:
                self.classifier = get_classifier()
                if self.classifier.is_loaded:
                    logger.info("ML classifier loaded for domain detection")
                else:
                    logger.info("ML classifier enabled but model not trained/loaded")
            except Exception as exc:
                logger.warning("Failed to initialize ML classifier: %s", exc)
                self.use_classifier = False

        # BERT classifier for domain detection (optional)
        self.use_bert_classifier = settings.use_bert_classifier
        self.bert_classifier = None
        if self.use_bert_classifier:
            try:
                from mascarade.router.bert_classifier import get_bert_classifier

                self.bert_classifier = get_bert_classifier()
                if self.bert_classifier.is_loaded:
                    logger.info("BERT classifier loaded for domain detection")
                else:
                    logger.info("BERT classifier enabled but model not trained/loaded")
            except Exception as exc:
                logger.warning("Failed to initialize BERT classifier: %s", exc)
                self.use_bert_classifier = False

        # ML routing classifier for tier prediction (strong/cheap/fast)
        self.routing_classifier = None
        if (
            settings.ml_routing_classifier_enabled
            and get_routing_classifier is not None
        ):
            try:
                from pathlib import Path

                model_path = (
                    Path(settings.ml_routing_classifier_path)
                    if settings.ml_routing_classifier_path.strip()
                    else None
                )
                self.routing_classifier = get_routing_classifier(model_path)
                logger.info(
                    "ML routing classifier initialised (loaded=%s)",
                    self.routing_classifier.is_loaded,
                )
            except Exception as exc:
                logger.warning("Failed to initialize ML routing classifier: %s", exc)

        self._register_defaults()

    def _initialize_cache(self) -> MultiTierCache:
        """
        Initialize the multi-tier cache with configuration from settings.

        Returns:
            Configured MultiTierCache instance
        """
        from mascarade.cache import InMemoryCache
        from mascarade.cache.redis_cache import RedisCache
        from mascarade.cache.semantic_cache import SemanticCache

        # L1: In-memory cache (always enabled)
        l1 = InMemoryCache(max_size=settings.cache_l1_size)

        # L2: Redis cache (optional)
        l2 = None
        if settings.cache_l2_enabled:
            try:
                l2 = RedisCache(
                    host=settings.cache_l2_host,
                    port=settings.cache_l2_port,
                    password=secret_value(settings.cache_l2_password),
                    db=settings.cache_l2_db,
                )
                logger.info("L2 Redis cache enabled")
            except Exception as exc:
                logger.warning("Failed to initialize L2 Redis cache: %s", exc)
                l2 = None

        # L3: Semantic cache (optional)
        l3 = None
        if settings.cache_l3_enabled:
            try:
                l3 = SemanticCache(
                    similarity_threshold=settings.cache_l3_similarity_threshold
                )
                logger.info("L3 Semantic cache enabled")
            except Exception as exc:
                logger.warning("Failed to initialize L3 Semantic cache: %s", exc)
                l3 = None

        # Create and return multi-tier cache
        cache = MultiTierCache(l1=l1, l2=l2, l3=l3)
        logger.info(
            "Multi-tier cache initialized: L1=enabled, L2=%s, L3=%s",
            "enabled" if l2 else "disabled",
            "enabled" if l3 else "disabled",
        )

        return cache

    def _register_defaults(self) -> None:
        provider_specs = [
            ("mascarade.router.providers.claude", "ClaudeProvider"),
            ("mascarade.router.providers.openai", "OpenAIProvider"),
            ("mascarade.router.providers.mistral", "MistralProvider"),
            ("mascarade.router.providers.mistral_agents", "MistralAgentsProvider"),
            ("mascarade.router.providers.bedrock", "BedrockProvider"),
            ("mascarade.router.providers.google", "GoogleProvider"),
            ("mascarade.router.providers.huggingface", "HuggingFaceProvider"),
            ("mascarade.router.providers.ollama", "OllamaProvider"),
            ("mascarade.router.providers.exo", "ExoProvider"),
            ("mascarade.router.providers.llama_cpp", "LlamaCppProvider"),
            ("mascarade.router.providers.mlx_lm", "MLXLMProvider"),
            ("mascarade.router.providers.apple_coreml", "AppleCoreMLProvider"),
            ("mascarade.router.providers.litellm", "LiteLLMProvider"),
            ("mascarade.router.providers.codestral", "CodestralProvider"),
        ]

        for module_name, class_name in provider_specs:
            try:
                module = __import__(module_name, fromlist=[class_name])
                provider_cls = getattr(module, class_name)
            except (ImportError, AttributeError) as exc:
                logger.warning(
                    "Skipping provider %s (%s): %s", class_name, module_name, exc
                )
                continue

            try:
                provider = provider_cls()
            except Exception as exc:
                logger.warning("Failed to initialize provider %s: %s", class_name, exc)
                continue

            if provider.is_configured:
                self.register(provider)

    def register(self, provider: LLMProvider) -> None:
        self._providers[provider.name] = provider
        self.load_balancer.register_provider(provider.name)

    @property
    def available_providers(self) -> list[str]:
        return list(self._providers.keys())

    def provider_model_map(self) -> dict[str, list[str]]:
        return {
            name: provider.available_models()
            for name, provider in self._providers.items()
        }

    def _get_effective_cost(self, provider: LLMProvider) -> float:
        """
        Get effective cost for a provider.

        Uses actual measured cost per request if sufficient data is available,
        otherwise falls back to static cost_per_million.

        Args:
            provider: LLMProvider instance

        Returns:
            Effective cost metric for comparison
        """
        MIN_REQUESTS_FOR_MEASURED_COST = 5

        # Try to get measured cost data
        stats = self.metrics.get_provider_stats(provider.name)
        if stats and stats.get("total_requests", 0) >= MIN_REQUESTS_FOR_MEASURED_COST:
            total_cost = stats.get("total_cost", 0.0)
            total_requests = stats.get("total_requests", 1)
            avg_cost_per_request = total_cost / total_requests
            logger.debug(
                "Using measured cost for %s: $%.6f per request (based on %d requests)",
                provider.name,
                avg_cost_per_request,
                total_requests,
            )
            return avg_cost_per_request

        # Fallback to static cost_per_million
        # Use sum as a proxy for comparison (input + output cost per million)
        static_cost = sum(provider.cost_per_million)
        logger.debug(
            "Using static cost for %s: $%.2f per 1M tokens (insufficient measured data)",
            provider.name,
            static_cost,
        )
        return static_cost

    def _select_candidates(
        self,
        strategy: Strategy = Strategy.BEST,
        provider_name: str | None = None,
        domain: str | None = None,
    ) -> list[LLMProvider]:
        if not self._providers:
            raise RuntimeError("Aucun provider LLM configuré. Vérifiez vos clés API.")

        if strategy == Strategy.SPECIFIC:
            if not provider_name or provider_name not in self._providers:
                raise ValueError(
                    f"Provider '{provider_name}' non disponible. "
                    f"Disponibles: {self.available_providers}"
                )
            return [self._providers[provider_name]]

        providers = list(self._providers.values())

        # Filter by domain if specified
        if domain:
            domain_models = [
                m
                for m in self.model_registry.get_models()
                if m.domain == domain and m.health_status == "healthy"
            ]
            if domain_models:
                domain_providers = {m.provider for m in domain_models}
                providers = [p for p in providers if p.name in domain_providers]
                logger.info(
                    "Filtered to %d provider(s) for domain '%s': %s",
                    len(providers),
                    domain,
                    [p.name for p in providers],
                )
            else:
                logger.warning(
                    "No healthy models found for domain '%s', using all providers",
                    domain,
                )

        # Filter out providers with OPEN circuits
        # Allow HALF_OPEN providers for recovery testing
        healthy_providers = [
            p for p in providers if not self.circuit_breaker.is_open(p.name)
        ]

        # If all providers have OPEN circuits, fall back to all providers
        # to allow recovery attempts
        if not healthy_providers:
            healthy_providers = providers
        if strategy == Strategy.CHEAPEST:
            # Use actual measured cost when available, fall back to static cost
            best_value = min(self._get_effective_cost(p) for p in providers)
            return [p for p in providers if self._get_effective_cost(p) == best_value]

        if strategy == Strategy.DOMAIN:
            # Prefer Ollama provider for domain-specific mascarade-* models
            # If Ollama not available, fallback to BEST strategy
            ollama_providers = [p for p in providers if p.name == "ollama"]
            if ollama_providers:
                return ollama_providers
            # Fallback to BEST strategy
            best_value = max(p.quality_rank for p in providers)
            return [p for p in providers if p.quality_rank == best_value]

        if strategy == Strategy.FASTEST:
            best_value = min(p.speed_rank for p in providers)
            return [p for p in providers if p.speed_rank == best_value]

        # Strategy is BEST - use domain-aware ranking if available
        if domain and self.benchmark_storage:
            benchmark_candidates = self._select_by_benchmarks(domain)
            if benchmark_candidates:
                logger.debug(
                    "Using benchmark data for domain '%s': selected %s",
                    domain,
                    [p.name for p in benchmark_candidates],
                )
                return benchmark_candidates
            logger.debug(
                "No benchmark data for domain '%s', falling back to quality_rank",
                domain,
            )

        # Fallback to static quality_rank
        best_value = max(p.quality_rank for p in healthy_providers)
        return [p for p in healthy_providers if p.quality_rank == best_value]

    def _select_by_benchmarks(self, domain: str) -> list[LLMProvider]:
        """
        Select provider candidates based on benchmark data for a specific domain.

        Args:
            domain: The domain to query benchmarks for

        Returns:
            List of best-performing providers based on benchmark quality scores,
            or empty list if no benchmark data available
        """
        if not self.benchmark_storage:
            return []

        try:
            # Query leaderboard for this domain, ordered by quality score
            leaderboard = self.benchmark_storage.query_leaderboard(
                domain=domain,
                limit=10,
                order_by="avg_quality_score",
            )

            if not leaderboard:
                return []

            # Get the top quality score
            top_score = leaderboard[0]["avg_quality_score"]

            # Find all providers with the top score (within 1% tolerance)
            tolerance = 1.0
            top_providers = [
                entry["provider"]
                for entry in leaderboard
                if abs(entry["avg_quality_score"] - top_score) <= tolerance
            ]

            # Return LLMProvider instances for these providers
            candidates = [
                self._providers[name]
                for name in top_providers
                if name in self._providers
            ]

            return candidates if candidates else []

        except Exception as exc:
            logger.warning(
                "Failed to query benchmarks for domain '%s': %s", domain, exc
            )
            return []

    def _detect_domain(self, messages: list[dict]) -> str | None:
        """
        Detect domain from message content using ML classifier (if enabled) or keywords.

        Args:
            messages: List of message dictionaries

        Returns:
            Detected domain or None
        """
        # Combine all message content
        content = " ".join(
            msg.get("content", "")
            for msg in messages
            if isinstance(msg.get("content"), str)
        )

        if not content.strip():
            return None

        # Try BERT classifier first if enabled
        if self.use_bert_classifier and self.bert_classifier is not None:
            try:
                domain = self.bert_classifier.predict(content)
                if domain:
                    logger.debug("BERT classifier detected domain: %s", domain)
                    return domain
            except Exception as exc:
                logger.warning(
                    "BERT classifier prediction failed: %s, falling back to ML classifier",
                    exc,
                )

        # Try ML classifier if enabled
        if self.use_classifier and self.classifier is not None:
            try:
                domain = self.classifier.predict(content)
                if domain:
                    logger.debug("ML classifier detected domain: %s", domain)
                    return domain
            except Exception as exc:
                logger.warning(
                    "ML classifier prediction failed: %s, falling back to keywords", exc
                )

        # Fallback to keyword-based detection
        return detect_domain(content)

    def _select_provider(
        self,
        strategy: Strategy = Strategy.BEST,
        provider_name: str | None = None,
        domain: str | None = None,
    ) -> LLMProvider:
        candidates = self._select_candidates(
            strategy=strategy, provider_name=provider_name, domain=domain
        )
        if len(candidates) == 1:
            return candidates[0]

        chosen_name = self.load_balancer.select_provider(
            [p.name for p in candidates], "round_robin"
        )
        return self._providers[chosen_name]

    @staticmethod
    def _estimate_tokens(messages: list[dict], system: str | None = None) -> int:
        chunks: list[str] = []
        if system:
            chunks.append(system)
        for message in messages:
            chunks.append(str(message.get("content") or ""))
        text = "\n".join(chunks)
        return max(1, int(len(text) / 4))

    @staticmethod
    def _joined_message_text(messages: list[dict], system: str | None = None) -> str:
        chunks: list[str] = []
        if system:
            chunks.append(system)
        for message in messages:
            chunks.append(str(message.get("content") or ""))
        return "\n".join(chunks)

    @classmethod
    def _routellm_heuristic_policy(
        cls,
        messages: list[dict],
        system: str | None = None,
    ) -> str | None:
        normalized = (
            re.sub(r"\s+", " ", cls._joined_message_text(messages, system))
            .strip()
            .lower()
        )
        if not normalized:
            return None
        if len(normalized) < 50:
            return "cheap"
        if len(normalized) > 200:
            return "strong"
        if re.search(
            r"\b(explique|explain|analyse|analyze|compare|comparison|comparez|pourquoi|why)\b",
            normalized,
            re.I,
        ):
            return "strong"
        return None

    @staticmethod
    def _complexity_score(messages: list[dict], system: str | None = None) -> float:
        text = Router._joined_message_text(messages, system)
        if not text.strip():
            return 0.0
        length_score = min(len(text) / 6000.0, 1.0)
        code_score = (
            0.25 if re.search(r"```|class\s+|def\s+|function\s+", text, re.I) else 0.0
        )
        math_score = (
            0.20
            if re.search(r"\b(O\(|NP|FFT|integral|derive|proof)\b", text, re.I)
            else 0.0
        )
        planning_score = (
            0.15
            if re.search(
                r"\b(plan|todo|roadmap|architecture|threat model)\b", text, re.I
            )
            else 0.0
        )
        multilingual_score = (
            0.10 if re.search(r"[\u0400-\u04FF\u4E00-\u9FFF]", text) else 0.0
        )
        return max(
            0.0,
            min(
                length_score
                + code_score
                + math_score
                + planning_score
                + multilingual_score,
                1.0,
            ),
        )

    @staticmethod
    def _normalize_scope(
        *,
        project_id: str | None,
        federation_scope: list[str] | tuple[str, ...] | None,
        knowledge_scope: str,
    ) -> tuple[str, tuple[str, ...], str]:
        return normalize_scope(
            project_id=project_id,
            federation_scope=federation_scope,
            knowledge_scope=knowledge_scope,
        )

    def _resolve_routellm_target(
        self,
        *,
        messages: list[dict],
        system: str | None,
        provider: str | None,
        model: str | None,
        routing_policy: str | None,
    ) -> tuple[Strategy, str | None, str | None]:
        policy = (routing_policy or "auto").strip().lower()
        if policy not in {"auto", "strong", "cheap", "fast"}:
            policy = "auto"

        if provider:
            return Strategy.SPECIFIC, provider, model

        def _strong_target() -> tuple[Strategy, str | None, str | None]:
            chosen_provider = settings.routellm_strong_provider.strip() or None
            chosen_model = settings.routellm_strong_model.strip() or None
            strategy = Strategy.SPECIFIC if chosen_provider else Strategy.BEST
            return strategy, chosen_provider, (model or chosen_model)

        def _cheap_target() -> tuple[Strategy, str | None, str | None]:
            chosen_provider = settings.routellm_cheap_provider.strip() or None
            chosen_model = settings.routellm_cheap_model.strip() or None
            strategy = Strategy.SPECIFIC if chosen_provider else Strategy.CHEAPEST
            return strategy, chosen_provider, (model or chosen_model)

        if not settings.routellm_enabled:
            if policy == "cheap":
                return Strategy.CHEAPEST, None, model
            if policy == "fast":
                return Strategy.FASTEST, None, model
            return Strategy.BEST, None, model

        if policy == "strong":
            strategy, chosen_provider, chosen_model = _strong_target()
            logger.debug(
                "RouteLLM policy strong selected provider=%s model=%s",
                chosen_provider,
                chosen_model,
            )
            return strategy, chosen_provider, chosen_model

        if policy == "cheap":
            strategy, chosen_provider, chosen_model = _cheap_target()
            logger.debug(
                "RouteLLM policy cheap selected provider=%s model=%s",
                chosen_provider,
                chosen_model,
            )
            return strategy, chosen_provider, chosen_model

        if policy == "fast":
            logger.debug("RouteLLM policy fast selected")
            return Strategy.FASTEST, None, model

        heuristic_policy = self._routellm_heuristic_policy(messages, system)
        if heuristic_policy == "strong":
            strategy, chosen_provider, chosen_model = _strong_target()
            logger.debug(
                "RouteLLM heuristic strong selected provider=%s model=%s",
                chosen_provider,
                chosen_model,
            )
            return strategy, chosen_provider, chosen_model
        if heuristic_policy == "cheap":
            strategy, chosen_provider, chosen_model = _cheap_target()
            logger.debug(
                "RouteLLM heuristic cheap selected provider=%s model=%s",
                chosen_provider,
                chosen_model,
            )
            return strategy, chosen_provider, chosen_model

        # --- ML routing classifier (if enabled and loaded) --------
        if self.routing_classifier is not None and self.routing_classifier.is_loaded:
            try:
                joined = self._joined_message_text(messages, system)
                ml_tier, ml_confidence = (
                    self.routing_classifier.predict_with_confidence(joined)
                )
                logger.debug(
                    "ML routing classifier: tier=%s confidence=%.3f",
                    ml_tier,
                    ml_confidence,
                )
                # Only use ML prediction when confidence exceeds threshold
                if ml_confidence >= max(
                    0.0, min(float(settings.routellm_threshold), 1.0)
                ):
                    if ml_tier == "strong":
                        strategy, chosen_provider, chosen_model = _strong_target()
                    elif ml_tier == "fast":
                        return Strategy.FASTEST, None, model
                    else:
                        strategy, chosen_provider, chosen_model = _cheap_target()
                    logger.debug(
                        "RouteLLM ML classifier selected tier=%s provider=%s model=%s",
                        ml_tier,
                        chosen_provider,
                        chosen_model,
                    )
                    return strategy, chosen_provider, chosen_model
            except Exception as exc:
                logger.warning(
                    "ML routing classifier failed, falling back to heuristic: %s", exc
                )

        # --- Rule-based complexity score fallback ------------------
        threshold = max(0.0, min(float(settings.routellm_threshold), 1.0))
        score = self._complexity_score(messages, system)
        if score >= threshold:
            strategy, chosen_provider, chosen_model = _strong_target()
            logger.debug(
                "RouteLLM strong route selected score=%.3f threshold=%.3f provider=%s model=%s",
                score,
                threshold,
                chosen_provider,
                chosen_model,
            )
            return strategy, chosen_provider, chosen_model

        strategy, chosen_provider, chosen_model = _cheap_target()
        logger.debug(
            "RouteLLM cheap route selected score=%.3f threshold=%.3f provider=%s model=%s",
            score,
            threshold,
            chosen_provider,
            chosen_model,
        )
        return strategy, chosen_provider, chosen_model

    @staticmethod
    def _usage_tokens(usage: dict[str, int]) -> int:
        return int(sum(usage.values())) if usage else 0

    @staticmethod
    def _calculate_cost(provider: LLMProvider, usage: dict[str, int]) -> float:
        input_tokens = usage.get("input_tokens", 0)
        output_tokens = usage.get("output_tokens", 0)
        in_cost, out_cost = provider.cost_per_million
        return ((input_tokens * in_cost) + (output_tokens * out_cost)) / 1_000_000

    async def metrics_summary(self) -> dict:
        return {
            "providers": self.metrics.get_summary(),
            "cache": await self.cache.get_stats(),
            "load_balancer": self.load_balancer.get_load_stats(),
            "fallback": self.fallback.get_failure_stats(),
            "health": self.health_monitor.get_all_health(),
            "circuit_breaker": self.circuit_breaker.get_stats(),
        }

    def provider_metrics(self, provider_name: str) -> dict:
        return self.metrics.get_provider_stats(provider_name)

    async def reset_metrics(self) -> None:
        self.metrics.reset()
        await self.cache.clear()
        self.load_balancer.reset_stats()
        self.fallback.reset()
        self.circuit_breaker.reset()
        self.health_monitor._health_cache.clear()

    def register_finetuned_model(
        self,
        model_id: str,
        *,
        domain: str | None = None,
        provider: str = "ollama",
        deployment_url: str | None = None,
        verify_health: bool = True,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Enregistrer un modèle fine-tuné avec métadonnées et vérification de santé.

        Args:
            model_id: Identifiant unique du modèle (ex: 'mascarade-spice:latest')
            domain: Domaine métier du modèle (ex: 'spice', 'electronics')
            provider: Provider de déploiement (défaut: 'ollama')
            deployment_url: URL du service de déploiement
            verify_health: Vérifier la santé du modèle après enregistrement
            metadata: Métadonnées additionnelles
        """
        reg_metadata: dict[str, Any] = metadata.copy() if metadata else {}

        if domain is not None:
            reg_metadata["domain"] = domain
        if provider is not None:
            reg_metadata["provider"] = provider
        if deployment_url is not None:
            reg_metadata["deployment_url"] = deployment_url

        self.model_registry.register_model(model_id, reg_metadata)
        logger.info("Registered finetuned model: %s (domain=%s)", model_id, domain)

        if verify_health:
            health_status = self.model_registry.verify_health(model_id)
            logger.info("Health check for %s: %s", model_id, health_status)

    # ------------------------------------------------------------------
    # Shared helpers for send() / stream() to avoid code duplication
    # ------------------------------------------------------------------

    async def _prepare_request(
        self,
        messages: list[dict],
        *,
        strategy: Strategy | str,
        routing_policy: str | None,
        provider: str | None,
        model: str | None,
        system: str | None,
        response_format: dict | None,
        temperature: float,
        max_tokens: int,
        domain: str | None,
        project_id: str | None,
        federation_scope: list[str] | tuple[str, ...] | None,
        knowledge_scope: str,
    ) -> dict[str, Any]:
        """Resolve routing parameters, check cache, build fallback sequence.

        Returns a dict with all resolved parameters needed by send()/stream().
        """
        normalized_project, normalized_federation, normalized_scope = (
            self._normalize_scope(
                project_id=project_id,
                federation_scope=federation_scope,
                knowledge_scope=knowledge_scope,
            )
        )
        cache_scope = {
            "project_id": normalized_project,
            "knowledge_scope": normalized_scope,
            "federation_scope": ",".join(normalized_federation),
        }
        requested_strategy = Strategy(strategy)
        policy = (routing_policy or "auto").strip().lower() or "auto"
        if policy not in {"auto", "strong", "cheap", "fast"}:
            policy = "auto"
        cache_strategy = (
            f"{requested_strategy.value}:{policy}"
            if requested_strategy == Strategy.ROUTELLM
            else requested_strategy.value
        )
        effective_strategy = requested_strategy
        effective_provider = provider
        effective_model = model
        if requested_strategy == Strategy.ROUTELLM:
            (
                effective_strategy,
                effective_provider,
                effective_model,
            ) = self._resolve_routellm_target(
                messages=messages,
                system=system,
                provider=provider,
                model=model,
                routing_policy=policy,
            )
        strict_provider = (
            effective_strategy == Strategy.SPECIFIC and effective_provider is not None
        )

        cached = await self.cache.retrieve(
            messages,
            strategy=cache_strategy,
            provider=effective_provider,
            model=effective_model,
            system=system,
            response_format=response_format,
            temperature=temperature,
            max_tokens=max_tokens,
            domain=domain,
            **cache_scope,
        )

        if strict_provider:
            sequence = [(effective_strategy.value, effective_provider)]
        else:
            sequence = self.fallback.build_sequence(
                strategy=effective_strategy.value,
                provider=effective_provider,
                available_providers=self.available_providers,
            )

        detected_domain = (
            self._detect_domain(messages) if strategy == Strategy.BEST else None
        )

        return {
            "normalized_project": normalized_project,
            "normalized_federation": normalized_federation,
            "normalized_scope": normalized_scope,
            "cache_scope": cache_scope,
            "cache_strategy": cache_strategy,
            "effective_strategy": effective_strategy,
            "effective_provider": effective_provider,
            "effective_model": effective_model,
            "strict_provider": strict_provider,
            "cached": cached,
            "sequence": sequence,
            "detected_domain": detected_domain,
        }

    def _track_failure(
        self,
        *,
        provider_name: str,
        model_name: str,
        elapsed: float,
        attempt_strategy: str,
        record_fallback: bool = True,
    ) -> None:
        """Record a failed attempt across all tracking systems."""
        self.load_balancer.request_completed(
            provider_name,
            response_time=elapsed,
            success=False,
        )
        self.metrics.track_request(
            provider_name=provider_name,
            tokens=0,
            cost=0.0,
            response_time=elapsed,
            success=False,
        )
        COST_METRICS.track_request(
            provider=provider_name,
            model=model_name,
            input_tokens=0,
            output_tokens=0,
            cost=0.0,
            duration=elapsed,
            strategy=attempt_strategy,
            success=False,
        )
        if self.cost_logger:
            self.cost_logger.log_event(
                provider=provider_name,
                model=model_name,
                agent="",
                input_tokens=0,
                output_tokens=0,
                cost=0.0,
                strategy=attempt_strategy,
                success=False,
            )
        if record_fallback:
            self.fallback.record_failure(provider_name)
        self.circuit_breaker.record_failure(provider_name)

    def _track_success(
        self,
        *,
        provider_name: str,
        model_name: str,
        elapsed: float,
        attempt_strategy: str,
        usage: dict[str, int],
        cost: float,
    ) -> None:
        """Record a successful attempt across all tracking systems."""
        self.load_balancer.request_completed(
            provider_name,
            response_time=elapsed,
            success=True,
        )
        self.circuit_breaker.record_success(provider_name)
        self.metrics.track_request(
            provider_name=provider_name,
            tokens=self._usage_tokens(usage),
            cost=cost,
            response_time=elapsed,
            success=True,
        )
        COST_METRICS.track_request(
            provider=provider_name,
            model=model_name,
            input_tokens=usage.get("input_tokens", 0),
            output_tokens=usage.get("output_tokens", 0),
            cost=cost,
            duration=elapsed,
            strategy=attempt_strategy,
            success=True,
        )
        if self.cost_logger:
            self.cost_logger.log_event(
                provider=provider_name,
                model=model_name,
                agent="",
                input_tokens=usage.get("input_tokens", 0),
                output_tokens=usage.get("output_tokens", 0),
                cost=cost,
                strategy=attempt_strategy,
                success=True,
            )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def send(
        self,
        messages: list[dict],
        *,
        strategy: Strategy | str = Strategy.BEST,
        routing_policy: str | None = None,
        provider: str | None = None,
        model: str | None = None,
        system: str | None = None,
        response_format: dict | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        domain: str | None = None,
        project_id: str | None = None,
        federation_scope: list[str] | tuple[str, ...] | None = None,
        knowledge_scope: str = "project",
    ) -> LLMResponse:
        ctx = await self._prepare_request(
            messages,
            strategy=strategy,
            routing_policy=routing_policy,
            provider=provider,
            model=model,
            system=system,
            response_format=response_format,
            temperature=temperature,
            max_tokens=max_tokens,
            domain=domain,
            project_id=project_id,
            federation_scope=federation_scope,
            knowledge_scope=knowledge_scope,
        )

        cached = ctx["cached"]
        strict_provider = ctx["strict_provider"]
        effective_provider = ctx["effective_provider"]
        effective_model = ctx["effective_model"]
        effective_strategy = ctx["effective_strategy"]
        cache_strategy = ctx["cache_strategy"]
        cache_scope = ctx["cache_scope"]

        if cached and (not strict_provider or cached.provider == effective_provider):
            return LLMResponse(
                content=cached.response,
                model=cached.model,
                provider=cached.provider,
                usage={"total_tokens": cached.tokens},
            )

        last_error: Exception | None = None
        for attempt_strategy, attempt_provider in ctx["sequence"]:
            attempt_enum = Strategy(attempt_strategy)
            selected = self._select_provider(
                attempt_enum,
                attempt_provider,
                domain or ctx["detected_domain"],
            )

            if not self.circuit_breaker.can_execute(selected.name):
                logger.warning(
                    "Circuit breaker is open for provider %s, skipping",
                    selected.name,
                )
                last_error = RuntimeError(
                    f"Circuit breaker is open for provider {selected.name}"
                )
                continue

            started_at = time.perf_counter()
            self.load_balancer.request_started(selected.name)

            # Distributed scheduling
            if (
                self.scheduler is not None
                and selected.name in ("ollama", "mlx_lm", "llama_cpp")
                and self.scheduler.workers
            ):
                distributed = await self._try_distributed_send(
                    selected,
                    messages,
                    effective_model,
                    system,
                    temperature,
                    max_tokens,
                    response_format,
                    ctx["normalized_project"],
                    ctx["normalized_federation"],
                    ctx["normalized_scope"],
                )
                if distributed is not None:
                    elapsed = time.perf_counter() - started_at
                    self.load_balancer.request_completed(
                        selected.name,
                        response_time=elapsed,
                        success=True,
                    )
                    return distributed

            try:
                send_kwargs: dict[str, Any] = {
                    "model": effective_model,
                    "system": system,
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                }
                if response_format is not None and selected.name in {
                    "mistral",
                    "ollama",
                }:
                    send_kwargs["response_format"] = response_format

                with start_langfuse_generation(
                    name=f"router.send/{selected.name}",
                    model=effective_model or selected.name,
                    input=messages,
                    metadata={
                        "strategy": effective_strategy.value,
                        "provider": selected.name,
                        "temperature": temperature,
                        "max_tokens": max_tokens,
                    },
                ) as generation:
                    response = await selected.send(messages, **send_kwargs)

            except Exception as exc:
                elapsed = time.perf_counter() - started_at
                logger.warning(
                    "Provider %s failed (%.2fs): %s",
                    selected.name,
                    elapsed,
                    exc,
                )
                self._track_failure(
                    provider_name=selected.name,
                    model_name=model or "unknown",
                    elapsed=elapsed,
                    attempt_strategy=attempt_strategy,
                )
                last_error = exc
                continue

            if strict_provider and response.provider != effective_provider:
                elapsed = time.perf_counter() - started_at
                logger.warning(
                    "Strict provider mismatch: requested %s but got %s",
                    effective_provider,
                    response.provider,
                )
                self._track_failure(
                    provider_name=selected.name,
                    model_name=model or "unknown",
                    elapsed=elapsed,
                    attempt_strategy=attempt_strategy,
                    record_fallback=False,
                )
                last_error = RuntimeError(
                    f"Strict provider mismatch: requested {effective_provider}, got {response.provider}"
                )
                continue

            elapsed = time.perf_counter() - started_at
            usage = response.usage or {}
            cost = self._calculate_cost(selected, usage)

            self._track_success(
                provider_name=selected.name,
                model_name=response.model,
                elapsed=elapsed,
                attempt_strategy=attempt_strategy,
                usage=usage,
                cost=cost,
            )

            update_langfuse_generation(
                generation,
                output=response.content,
                usage={
                    "input": usage.get("input_tokens", 0),
                    "output": usage.get("output_tokens", 0),
                    "total": self._usage_tokens(usage),
                },
                metadata={
                    "provider": response.provider,
                    "model": response.model,
                    "response_time_s": round(elapsed, 3),
                    "cost": cost,
                },
            )

            if not strict_provider:
                await self.cache.store(
                    messages,
                    response.content,
                    tokens=self._usage_tokens(usage),
                    cost=cost,
                    ttl=3600,
                    strategy=cache_strategy,
                    provider=selected.name,
                    model=response.model,
                    system=system,
                    response_format=response_format,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    domain=domain,
                    **cache_scope,
                )

            return response

        raise RuntimeError(
            "All fallback attempts failed."
            if last_error is None
            else f"All fallback attempts failed: {last_error}"
        )

    async def _try_distributed_send(
        self,
        selected: LLMProvider,
        messages: list[dict],
        model: str | None,
        system: str | None,
        temperature: float,
        max_tokens: int,
        response_format: dict | None,
        project_id: str,
        federation_scope: tuple[str, ...],
        knowledge_scope: str,
    ) -> LLMResponse | None:
        """Try to dispatch to a distributed worker via the scheduler.

        Returns LLMResponse if successful, None to fall back to local provider.
        """
        import httpx

        from mascarade.scheduler.scheduler import ScheduledRequest

        req = ScheduledRequest(
            model=model or selected.default_model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
        )

        try:
            worker = self.scheduler.select_worker(req)
        except Exception:
            logger.debug("Scheduler: no suitable worker, falling back to local")
            return None

        worker.request_started()
        started = time.perf_counter()

        try:
            payload: dict[str, Any] = {
                "model": model or selected.default_model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "project_id": project_id,
                "knowledge_scope": knowledge_scope,
            }
            if federation_scope:
                payload["federation_scope"] = list(federation_scope)
            if system:
                payload["messages"] = [{"role": "system", "content": system}] + messages
            if response_format:
                payload["response_format"] = response_format

            async with httpx.AsyncClient(timeout=httpx.Timeout(120.0)) as client:
                resp = await client.post(
                    f"{worker.url}/v1/chat/completions",
                    json=payload,
                )

            if resp.status_code != 200:
                raise RuntimeError(
                    f"Worker {worker.node_id} returned {resp.status_code}"
                )

            data = resp.json()
            elapsed_ms = (time.perf_counter() - started) * 1000
            worker.request_completed(latency_ms=elapsed_ms, success=True)

            # Parse OpenAI-compatible response
            choice = data.get("choices", [{}])[0]
            content = choice.get("message", {}).get("content", "")
            usage = data.get("usage", {})

            logger.info(
                "Distributed send → %s (%.0f ms, %d tokens)",
                worker.node_id,
                elapsed_ms,
                usage.get("total_tokens", 0),
            )

            return LLMResponse(
                content=content,
                model=data.get("model", model or ""),
                provider=f"distributed:{worker.node_id}",
                usage=usage,
            )

        except Exception as exc:
            elapsed_ms = (time.perf_counter() - started) * 1000
            worker.request_completed(latency_ms=elapsed_ms, success=False)
            logger.warning("Distributed send to %s failed: %s", worker.node_id, exc)
            return None  # fall back to local

    async def fill_in_middle(
        self,
        prompt: str,
        *,
        suffix: str = "",
        provider: str = "codestral",
        model: str | None = None,
        temperature: float = 0.0,
        max_tokens: int = 1024,
        stop: list[str] | None = None,
    ) -> LLMResponse:
        """Expose provider-native Fill-in-the-Middle without duplicating providers."""
        if not prompt.strip():
            raise ValueError("prompt is required")

        selected = self._providers.get(provider)
        if selected is None:
            raise ValueError(f"Provider '{provider}' is not available")

        fill_in_middle = getattr(selected, "fill_in_middle", None)
        if not callable(fill_in_middle):
            raise ValueError(
                f"Provider '{provider}' does not support fill-in-the-middle"
            )

        started_at = time.perf_counter()
        self.load_balancer.request_started(selected.name)
        try:
            content = await fill_in_middle(
                prompt=prompt,
                suffix=suffix,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                stop=stop,
            )
        except Exception:
            elapsed = time.perf_counter() - started_at
            self.load_balancer.request_completed(
                selected.name,
                response_time=elapsed,
                success=False,
            )
            raise

        elapsed = time.perf_counter() - started_at
        self.load_balancer.request_completed(
            selected.name,
            response_time=elapsed,
            success=True,
        )
        return LLMResponse(
            content=content,
            model=model or getattr(selected, "default_model", provider),
            provider=selected.name,
            usage={},
        )

    async def stream(
        self,
        messages: list[dict],
        *,
        strategy: Strategy | str = Strategy.BEST,
        routing_policy: str | None = None,
        provider: str | None = None,
        model: str | None = None,
        system: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        domain: str | None = None,
        project_id: str | None = None,
        federation_scope: list[str] | tuple[str, ...] | None = None,
        knowledge_scope: str = "project",
    ) -> AsyncIterator[str]:
        ctx = await self._prepare_request(
            messages,
            strategy=strategy,
            routing_policy=routing_policy,
            provider=provider,
            model=model,
            system=system,
            response_format=None,
            temperature=temperature,
            max_tokens=max_tokens,
            domain=domain,
            project_id=project_id,
            federation_scope=federation_scope,
            knowledge_scope=knowledge_scope,
        )

        cached = ctx["cached"]
        strict_provider = ctx["strict_provider"]
        effective_provider = ctx["effective_provider"]
        effective_model = ctx["effective_model"]

        if cached and (not strict_provider or cached.provider == effective_provider):
            yield cached.response
            return

        last_error: Exception | None = None
        for attempt_strategy, attempt_provider in ctx["sequence"]:
            attempt_enum = Strategy(attempt_strategy)
            selected = self._select_provider(
                attempt_enum,
                attempt_provider,
                domain or ctx["detected_domain"],
            )

            if not self.circuit_breaker.can_execute(selected.name):
                logger.warning(
                    "Circuit breaker is open for provider %s, skipping",
                    selected.name,
                )
                last_error = RuntimeError(
                    f"Circuit breaker is open for provider {selected.name}"
                )
                continue

            started_at = time.perf_counter()
            self.load_balancer.request_started(selected.name)

            try:
                started_streaming = False
                async for token in selected.stream(
                    messages,
                    model=effective_model,
                    system=system,
                    temperature=temperature,
                    max_tokens=max_tokens,
                ):
                    started_streaming = True
                    yield token
            except Exception as exc:
                elapsed = time.perf_counter() - started_at
                self._track_failure(
                    provider_name=selected.name,
                    model_name=model or "unknown",
                    elapsed=elapsed,
                    attempt_strategy=attempt_strategy,
                )
                if started_streaming:
                    logger.error(
                        "Provider %s stream failed mid-stream (%.2fs): %s — cannot fallback",
                        selected.name,
                        elapsed,
                        exc,
                    )
                    raise
                logger.warning(
                    "Provider %s stream failed before first token (%.2fs): %s — trying fallback",
                    selected.name,
                    elapsed,
                    exc,
                )
                last_error = exc
                continue

            elapsed = time.perf_counter() - started_at
            # Streaming doesn't provide token counts, so track with zero usage
            stream_model = model or (
                selected.available_models()[0]
                if selected.available_models()
                else "unknown"
            )
            self._track_success(
                provider_name=selected.name,
                model_name=stream_model,
                elapsed=elapsed,
                attempt_strategy=attempt_strategy,
                usage={},
                cost=0.0,
            )
            return

        raise RuntimeError(
            "All fallback attempts failed for streaming."
            if last_error is None
            else f"All fallback attempts failed for streaming: {last_error}"
        )
