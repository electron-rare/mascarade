"""Routeur LLM — dispatch intelligent entre providers."""

from __future__ import annotations

import logging
import re
import time
from collections.abc import AsyncIterator
from enum import StrEnum
from typing import Any

from mascarade.analytics import COST_METRICS
from mascarade.analytics.clickhouse_logger import get_cost_logger
from mascarade.analytics.cost_calculator import get_cost_calculator
from mascarade.cache.multi_tier_cache import MultiTierCache
from mascarade.config import settings
from mascarade.load_balancer.balancer import LoadBalancer
from mascarade.metrics.tracker import MetricsTracker
from mascarade.observability.langfuse import (
    start_langfuse_generation,
    update_langfuse_generation,
)
from mascarade.router.circuit_breaker import CircuitBreaker
from mascarade.router.fallback import FallbackState
from mascarade.router.model_registry import ModelRegistry
from mascarade.router.health_monitor import HealthMonitor
from mascarade.router.providers.base import LLMProvider, LLMResponse
from mascarade.usage_tracking import track_usage

try:
    from mascarade.router.classifier import get_classifier
except ImportError:
    get_classifier = None  # type: ignore[assignment,misc]

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
        self.cache = MultiTierCache()
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

        self._register_defaults()

    def _register_defaults(self) -> None:
        provider_specs = [
            ("mascarade.router.providers.claude", "ClaudeProvider"),
            ("mascarade.router.providers.openai", "OpenAIProvider"),
            ("mascarade.router.providers.mistral", "MistralProvider"),
            ("mascarade.router.providers.bedrock", "BedrockProvider"),
            ("mascarade.router.providers.google", "GoogleProvider"),
            ("mascarade.router.providers.huggingface", "HuggingFaceProvider"),
            ("mascarade.router.providers.ollama", "OllamaProvider"),
            ("mascarade.router.providers.llama_cpp", "LlamaCppProvider"),
            ("mascarade.router.providers.mlx_lm", "MLXLMProvider"),
            ("mascarade.router.providers.apple_coreml", "AppleCoreMLProvider"),
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
                m for m in self.model_registry.get_models()
                if m.domain == domain and m.health_status == "healthy"
            ]
            if domain_models:
                domain_providers = {m.provider for m in domain_models}
                providers = [
                    p for p in providers
                    if p.name in domain_providers
                ]
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
            p for p in providers
            if not self.circuit_breaker.is_open(p.name)
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
                "No benchmark data for domain '%s', falling back to quality_rank", domain
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
            logger.warning("Failed to query benchmarks for domain '%s': %s", domain, exc)
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

        # Try ML classifier first if enabled
        if self.use_classifier and self.classifier is not None:
            try:
                domain = self.classifier.predict(content)
                if domain:
                    logger.debug("ML classifier detected domain: %s", domain)
                    return domain
            except Exception as exc:
                logger.warning("ML classifier prediction failed: %s, falling back to keywords", exc)

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
    def _complexity_score(messages: list[dict], system: str | None = None) -> float:
        chunks: list[str] = []
        if system:
            chunks.append(system)
        for message in messages:
            chunks.append(str(message.get("content") or ""))
        text = "\n".join(chunks)
        if not text.strip():
            return 0.0
        length_score = min(len(text) / 6000.0, 1.0)
        code_score = 0.25 if re.search(r"```|class\s+|def\s+|function\s+", text, re.I) else 0.0
        math_score = 0.20 if re.search(r"\b(O\(|NP|FFT|integral|derive|proof)\b", text, re.I) else 0.0
        planning_score = 0.15 if re.search(r"\b(plan|todo|roadmap|architecture|threat model)\b", text, re.I) else 0.0
        multilingual_score = 0.10 if re.search(r"[\u0400-\u04FF\u4E00-\u9FFF]", text) else 0.0
        return max(0.0, min(length_score + code_score + math_score + planning_score + multilingual_score, 1.0))

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

        threshold = max(0.0, min(float(settings.routellm_threshold), 1.0))
        score = self._complexity_score(messages, system)
        if score >= threshold:
            strategy, chosen_provider, chosen_model = _strong_target()
            logger.debug(
                "RouteLLM strong route selected score=%.3f threshold=%.3f provider=%s model=%s",
                score, threshold, chosen_provider, chosen_model,
            )
            return strategy, chosen_provider, chosen_model

        strategy, chosen_provider, chosen_model = _cheap_target()
        logger.debug(
            "RouteLLM cheap route selected score=%.3f threshold=%.3f provider=%s model=%s",
            score, threshold, chosen_provider, chosen_model,
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
    ) -> LLMResponse:
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
        strict_provider = effective_strategy == Strategy.SPECIFIC and effective_provider is not None

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
        )
        if cached and (not strict_provider or cached.provider == effective_provider):
            return LLMResponse(
                content=cached.response,
                model=cached.model,
                provider=cached.provider,
                usage={"total_tokens": cached.tokens},
            )

        last_error: Exception | None = None
        if strict_provider:
            sequence = [(effective_strategy.value, effective_provider)]
        else:
            sequence = self.fallback.build_sequence(
                strategy=effective_strategy.value,
                provider=effective_provider,
                available_providers=self.available_providers,
            )

        # Detect domain for domain-aware routing
        detected_domain = self._detect_domain(messages) if strategy == Strategy.BEST else None

        for attempt_strategy, attempt_provider in sequence:
            attempt_enum = Strategy(attempt_strategy)
            selected = self._select_provider(attempt_enum, attempt_provider, domain)
            selected = self._select_provider(attempt_enum, attempt_provider, detected_domain)
            selected = self._select_provider(attempt_enum, attempt_provider)

            # Check circuit breaker for this specific provider
            if not self.circuit_breaker.can_execute(selected.name):
                logger.warning(
                    "Circuit breaker is open for provider %s, skipping", selected.name
                )
                last_error = RuntimeError(f"Circuit breaker is open for provider {selected.name}")
                continue

            started_at = time.perf_counter()
            self.load_balancer.request_started(selected.name)

            try:
                send_kwargs = {
                    "model": effective_model,
                    "system": system,
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                }
                if response_format is not None and selected.name in {"mistral", "ollama"}:
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
                    "Provider %s failed (%.2fs): %s", selected.name, elapsed, exc
                )
                self.load_balancer.request_completed(
                    selected.name, response_time=elapsed, success=False
                )
                self.metrics.track_request(
                    provider_name=selected.name,
                    tokens=0,
                    cost=0.0,
                    response_time=elapsed,
                    success=False,
                )
                COST_METRICS.track_request(
                    provider=selected.name,
                    model=model or "unknown",
                    input_tokens=0,
                    output_tokens=0,
                    cost=0.0,
                    duration=elapsed,
                    strategy=attempt_strategy,
                    success=False,
                )
                if self.cost_logger:
                    self.cost_logger.log_event(
                        provider=selected.name,
                        model=model or "unknown",
                        agent="",
                        input_tokens=0,
                        output_tokens=0,
                        cost=0.0,
                        strategy=attempt_strategy,
                        success=False,
                    )
                self.fallback.record_failure(selected.name)
                self.circuit_breaker.record_failure(selected.name)
                last_error = exc
                continue

            if strict_provider and response.provider != effective_provider:
                elapsed = time.perf_counter() - started_at
                logger.warning(
                    "Strict provider mismatch: requested %s but got %s",
                    effective_provider,
                    response.provider,
                )
                self.load_balancer.request_completed(
                    selected.name, response_time=elapsed, success=False
                )
                self.metrics.track_request(
                    provider_name=selected.name,
                    tokens=0,
                    cost=0.0,
                    response_time=elapsed,
                    success=False,
                )
                self.circuit_breaker.record_failure(selected.name)
                COST_METRICS.track_request(
                    provider=selected.name,
                    model=model or "unknown",
                    input_tokens=0,
                    output_tokens=0,
                    cost=0.0,
                    duration=elapsed,
                    strategy=attempt_strategy,
                    success=False,
                )
                if self.cost_logger:
                    self.cost_logger.log_event(
                        provider=selected.name,
                        model=model or "unknown",
                        agent="",
                        input_tokens=0,
                        output_tokens=0,
                        cost=0.0,
                        strategy=attempt_strategy,
                        success=False,
                    )
                last_error = RuntimeError(
                    f"Strict provider mismatch: requested {effective_provider}, got {response.provider}"
                )
                continue

            elapsed = time.perf_counter() - started_at
            self.load_balancer.request_completed(
                selected.name, response_time=elapsed, success=True
            )
            self.circuit_breaker.record_success(selected.name)

            usage = response.usage or {}
            cost = self._calculate_cost(selected, usage)
            self.metrics.track_request(
                provider_name=selected.name,
                tokens=self._usage_tokens(usage),
                cost=cost,
                response_time=elapsed,
                success=True,
            )
            COST_METRICS.track_request(
                provider=selected.name,
                model=response.model,
                input_tokens=usage.get("input_tokens", 0),
                output_tokens=usage.get("output_tokens", 0),
                cost=cost,
                duration=elapsed,
                strategy=attempt_strategy,
                success=True,
            )
            if self.cost_logger:
                self.cost_logger.log_event(
                    provider=selected.name,
                    model=response.model,
                    agent="",
                    input_tokens=usage.get("input_tokens", 0),
                    output_tokens=usage.get("output_tokens", 0),
                    cost=cost,
                    strategy=attempt_strategy,
                    success=True,
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
                    "cost": self._calculate_cost(selected, usage),
                },
            )

            if not strict_provider:
                await self.cache.store(
                    messages,
                    response.content,
                    tokens=self._usage_tokens(usage),
                    cost=self._calculate_cost(selected, usage),
                    ttl=3600,
                    strategy=cache_strategy,
                    provider=selected.name,
                    model=response.model,
                    system=system,
                    response_format=response_format,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    domain=domain,
                )

            # TODO: Add user_id parameter if needed for usage tracking
            # if user_id is not None:
            #     await track_usage(
            #         user_id=user_id,
            #         provider=selected.name,
            #         model=response.model,
            #         usage=response.usage or {},
            #         cost=self._calculate_cost(selected, response.usage or {}),
            #     )

            return response

        raise RuntimeError(
            "All fallback attempts failed."
            if last_error is None
            else f"All fallback attempts failed: {last_error}"
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
    ) -> AsyncIterator[str]:
        requested_strategy = Strategy(strategy)
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
                routing_policy=routing_policy,
            )
        strict_provider = effective_strategy == Strategy.SPECIFIC and effective_provider is not None

        cached = self.cache.retrieve(
            messages,
            strategy=strategy.value,
            provider=provider,
            model=model,
            system=system,
            response_format=None,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        if cached and (not strict_provider or cached.provider == provider):
            yield cached.response
            return

        if strict_provider:
            sequence = [(effective_strategy.value, effective_provider)]
        else:
            sequence = self.fallback.build_sequence(
                strategy=effective_strategy.value,
                provider=effective_provider,
                available_providers=self.available_providers,
            )

        # Detect domain for domain-aware routing
        detected_domain = self._detect_domain(messages) if strategy == Strategy.BEST else None

        last_error: Exception | None = None
        for attempt_strategy, attempt_provider in sequence:
            attempt_enum = Strategy(attempt_strategy)
            selected = self._select_provider(attempt_enum, attempt_provider, domain)
            selected = self._select_provider(attempt_enum, attempt_provider, detected_domain)
            selected = self._select_provider(attempt_enum, attempt_provider)

            # Check circuit breaker for this specific provider
            if not self.circuit_breaker.can_execute(selected.name):
                logger.warning(
                    "Circuit breaker is open for provider %s, skipping", selected.name
                )
                last_error = RuntimeError(f"Circuit breaker is open for provider {selected.name}")
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
                self.load_balancer.request_completed(
                    selected.name, response_time=elapsed, success=False
                )
                self.metrics.track_request(
                    provider_name=selected.name,
                    tokens=0,
                    cost=0.0,
                    response_time=elapsed,
                    success=False,
                )
                COST_METRICS.track_request(
                    provider=selected.name,
                    model=model or "unknown",
                    input_tokens=0,
                    output_tokens=0,
                    cost=0.0,
                    duration=elapsed,
                    strategy=attempt_strategy,
                    success=False,
                )
                if self.cost_logger:
                    self.cost_logger.log_event(
                        provider=selected.name,
                        model=model or "unknown",
                        agent="",
                        input_tokens=0,
                        output_tokens=0,
                        cost=0.0,
                        strategy=attempt_strategy,
                        success=False,
                    )
                self.fallback.record_failure(selected.name)
                self.circuit_breaker.record_failure(selected.name)
                if started_streaming:
                    # Already yielded tokens — cannot fallback without data corruption
                    logger.error(
                        "Provider %s stream failed mid-stream (%.2fs): %s — cannot fallback",
                        selected.name, elapsed, exc,
                    )
                    raise
                logger.warning(
                    "Provider %s stream failed before first token (%.2fs): %s — trying fallback",
                    selected.name, elapsed, exc,
                )
                last_error = exc
                continue

            elapsed = time.perf_counter() - started_at
            self.load_balancer.request_completed(
                selected.name, response_time=elapsed, success=True
            )
            self.circuit_breaker.record_success(selected.name)
            self.metrics.track_request(
                provider_name=selected.name,
                tokens=0,
                cost=0.0,
                response_time=elapsed,
                success=True,
            )

            # TODO: Add user_id parameter if needed for usage tracking
            # Note: streaming doesn't provide token counts, so we track 0 tokens
            # if user_id is not None:
            #     await track_usage(
            #         user_id=user_id,
            #         provider=selected.name,
            #         model=model or selected.default_model,
            #         usage={},
            #         cost=0.0,
            #     )

            COST_METRICS.track_request(
                provider=selected.name,
                model=model or selected.available_models()[0] if selected.available_models() else "unknown",
                input_tokens=0,
                output_tokens=0,
                cost=0.0,
                duration=elapsed,
                strategy=attempt_strategy,
                success=True,
            )
            if self.cost_logger:
                self.cost_logger.log_event(
                    provider=selected.name,
                    model=model or selected.available_models()[0] if selected.available_models() else "unknown",
                    agent="",
                    input_tokens=0,
                    output_tokens=0,
                    cost=0.0,
                    strategy=attempt_strategy,
                    success=True,
                )
            return

        raise RuntimeError(
            "All fallback attempts failed for streaming."
            if last_error is None
            else f"All fallback attempts failed for streaming: {last_error}"
        )
