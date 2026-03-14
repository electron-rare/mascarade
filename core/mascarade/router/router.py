"""Routeur LLM — dispatch intelligent entre providers."""

from __future__ import annotations

import logging
import time
from collections.abc import AsyncIterator
from enum import StrEnum

from mascarade.analytics.clickhouse_logger import get_cost_logger
from mascarade.analytics.cost_calculator import get_cost_calculator
from mascarade.analytics.prometheus_metrics import COST_METRICS
from mascarade.cache.cache import ResponseCache
from mascarade.load_balancer.balancer import LoadBalancer
from mascarade.metrics.tracker import MetricsTracker
from mascarade.router.fallback import FallbackState
from mascarade.router.providers.base import LLMProvider, LLMResponse

logger = logging.getLogger("mascarade.router")


class Strategy(StrEnum):
    BEST = "best"
    CHEAPEST = "cheapest"
    FASTEST = "fastest"
    SPECIFIC = "specific"


class Router:
    """Routeur intelligent entre providers LLM."""

    def __init__(self) -> None:
        self._providers: dict[str, LLMProvider] = {}
        self.cache = ResponseCache()
        self.metrics = MetricsTracker()
        self.load_balancer = LoadBalancer()
        self.fallback = FallbackState(max_attempts=3)
        self.cost_logger = get_cost_logger()
        self.cost_calculator = get_cost_calculator()
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

        if strategy == Strategy.CHEAPEST:
            # Use actual measured cost when available, fall back to static cost
            best_value = min(self._get_effective_cost(p) for p in providers)
            return [p for p in providers if self._get_effective_cost(p) == best_value]

        if strategy == Strategy.FASTEST:
            best_value = min(p.speed_rank for p in providers)
            return [p for p in providers if p.speed_rank == best_value]

        best_value = max(p.quality_rank for p in providers)
        return [p for p in providers if p.quality_rank == best_value]

    def _select_provider(
        self,
        strategy: Strategy = Strategy.BEST,
        provider_name: str | None = None,
    ) -> LLMProvider:
        candidates = self._select_candidates(
            strategy=strategy, provider_name=provider_name
        )
        if len(candidates) == 1:
            return candidates[0]

        chosen_name = self.load_balancer.select_provider(
            [p.name for p in candidates], "round_robin"
        )
        return self._providers[chosen_name]

    @staticmethod
    def _usage_tokens(usage: dict[str, int]) -> int:
        return int(sum(usage.values())) if usage else 0

    @staticmethod
    def _calculate_cost(provider: LLMProvider, usage: dict[str, int]) -> float:
        input_tokens = usage.get("input_tokens", 0)
        output_tokens = usage.get("output_tokens", 0)
        in_cost, out_cost = provider.cost_per_million
        return ((input_tokens * in_cost) + (output_tokens * out_cost)) / 1_000_000

    def metrics_summary(self) -> dict:
        return {
            "providers": self.metrics.get_summary(),
            "cache": self.cache.get_stats(),
            "load_balancer": self.load_balancer.get_load_stats(),
            "fallback": self.fallback.get_failure_stats(),
        }

    def provider_metrics(self, provider_name: str) -> dict:
        return self.metrics.get_provider_stats(provider_name)

    def reset_metrics(self) -> None:
        self.metrics.reset()
        self.cache.clear()
        self.load_balancer.reset_stats()
        self.fallback.reset()

    async def send(
        self,
        messages: list[dict],
        *,
        strategy: Strategy | str = Strategy.BEST,
        provider: str | None = None,
        model: str | None = None,
        system: str | None = None,
        response_format: dict | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        strategy = Strategy(strategy)
        strict_provider = strategy == Strategy.SPECIFIC and provider is not None

        cached = self.cache.retrieve(
            messages,
            strategy=strategy.value,
            provider=provider,
            model=model,
            system=system,
            response_format=response_format,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        if cached and (not strict_provider or cached.provider == provider):
            return LLMResponse(
                content=cached.response,
                model=cached.model,
                provider=cached.provider,
                usage={"total_tokens": cached.tokens},
            )

        last_error: Exception | None = None
        if strict_provider:
            sequence = [(strategy.value, provider)]
        else:
            sequence = self.fallback.build_sequence(
                strategy=strategy.value,
                provider=provider,
                available_providers=self.available_providers,
            )

        for attempt_strategy, attempt_provider in sequence:
            attempt_enum = Strategy(attempt_strategy)
            selected = self._select_provider(attempt_enum, attempt_provider)
            started_at = time.perf_counter()
            self.load_balancer.request_started(selected.name)

            try:
                send_kwargs = {
                    "model": model,
                    "system": system,
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                }
                if response_format is not None and selected.name in {"mistral", "ollama"}:
                    send_kwargs["response_format"] = response_format
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
                last_error = exc
                continue

            if strict_provider and response.provider != provider:
                elapsed = time.perf_counter() - started_at
                logger.warning(
                    "Strict provider mismatch: requested %s but got %s",
                    provider,
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
                    f"Strict provider mismatch: requested {provider}, got {response.provider}"
                )
                continue

            elapsed = time.perf_counter() - started_at
            self.load_balancer.request_completed(
                selected.name, response_time=elapsed, success=True
            )

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

            # Store in cache with original strategy to enable cache hits
            # even after fallback to different provider
            # But store the actual provider that was used for accurate response metadata
            cache_strategy = strategy.value

            if not strict_provider:
                self.cache.store(
                    messages,
                    response.content,
                    tokens=self._usage_tokens(response.usage),
                    cost=self._calculate_cost(selected, response.usage),
                    ttl=3600,
                    strategy=cache_strategy,
                    provider=selected.name,  # Store actual provider used
                    model=response.model,
                    system=system,
                    response_format=response_format,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
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
        provider: str | None = None,
        model: str | None = None,
        system: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> AsyncIterator[str]:
        strategy = Strategy(strategy)
        strict_provider = strategy == Strategy.SPECIFIC and provider is not None

        if strict_provider:
            sequence = [(strategy.value, provider)]
        else:
            sequence = self.fallback.build_sequence(
                strategy=strategy.value,
                provider=provider,
                available_providers=self.available_providers,
            )

        last_error: Exception | None = None
        for attempt_strategy, attempt_provider in sequence:
            attempt_enum = Strategy(attempt_strategy)
            selected = self._select_provider(attempt_enum, attempt_provider)
            started_at = time.perf_counter()
            self.load_balancer.request_started(selected.name)

            try:
                async for token in selected.stream(
                    messages,
                    model=model,
                    system=system,
                    temperature=temperature,
                    max_tokens=max_tokens,
                ):
                    yield token
            except Exception as exc:
                elapsed = time.perf_counter() - started_at
                logger.warning(
                    "Provider %s stream failed (%.2fs): %s", selected.name, elapsed, exc
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
                last_error = exc
                continue

            elapsed = time.perf_counter() - started_at
            self.load_balancer.request_completed(
                selected.name, response_time=elapsed, success=True
            )
            self.metrics.track_request(
                provider_name=selected.name,
                tokens=0,
                cost=0.0,
                response_time=elapsed,
                success=True,
            )
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
