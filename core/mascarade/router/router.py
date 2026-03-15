"""Routeur LLM — dispatch intelligent entre providers."""

from __future__ import annotations

import logging
import re
import time
from collections.abc import AsyncIterator
from enum import StrEnum

from mascarade.cache.cache import ResponseCache
from mascarade.config import settings
from mascarade.load_balancer.balancer import LoadBalancer
from mascarade.metrics.tracker import MetricsTracker
from mascarade.observability.langfuse import (
    start_langfuse_generation,
    update_langfuse_generation,
)
from mascarade.router.fallback import FallbackState
from mascarade.router.providers.base import LLMProvider, LLMResponse

logger = logging.getLogger("mascarade.router")


class Strategy(StrEnum):
    BEST = "best"
    CHEAPEST = "cheapest"
    FASTEST = "fastest"
    SPECIFIC = "specific"
    ROUTELLM = "routellm"


class Router:
    """Routeur intelligent entre providers LLM."""

    def __init__(self) -> None:
        self._providers: dict[str, LLMProvider] = {}
        self.cache = ResponseCache()
        self.metrics = MetricsTracker()
        self.load_balancer = LoadBalancer()
        self.fallback = FallbackState(max_attempts=3)
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
            best_value = min(sum(p.cost_per_million) for p in providers)
            return [p for p in providers if sum(p.cost_per_million) == best_value]

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
        routing_policy: str | None = None,
        provider: str | None = None,
        model: str | None = None,
        system: str | None = None,
        response_format: dict | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
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

        cached = self.cache.retrieve(
            messages,
            strategy=cache_strategy,
            provider=effective_provider,
            model=effective_model,
            system=system,
            response_format=response_format,
            temperature=temperature,
            max_tokens=max_tokens,
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

        for attempt_strategy, attempt_provider in sequence:
            attempt_enum = Strategy(attempt_strategy)
            selected = self._select_provider(attempt_enum, attempt_provider)
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
                self.fallback.record_failure(selected.name)
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
                last_error = RuntimeError(
                    f"Strict provider mismatch: requested {effective_provider}, got {response.provider}"
                )
                continue

            elapsed = time.perf_counter() - started_at
            self.load_balancer.request_completed(
                selected.name, response_time=elapsed, success=True
            )

            usage = response.usage or {}
            self.metrics.track_request(
                provider_name=selected.name,
                tokens=self._usage_tokens(usage),
                cost=self._calculate_cost(selected, usage),
                response_time=elapsed,
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
                self.cache.store(
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
        routing_policy: str | None = None,
        provider: str | None = None,
        model: str | None = None,
        system: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
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

        if strict_provider:
            sequence = [(effective_strategy.value, effective_provider)]
        else:
            sequence = self.fallback.build_sequence(
                strategy=effective_strategy.value,
                provider=effective_provider,
                available_providers=self.available_providers,
            )

        last_error: Exception | None = None
        for attempt_strategy, attempt_provider in sequence:
            attempt_enum = Strategy(attempt_strategy)
            selected = self._select_provider(attempt_enum, attempt_provider)
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
                self.fallback.record_failure(selected.name)
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
            self.metrics.track_request(
                provider_name=selected.name,
                tokens=0,
                cost=0.0,
                response_time=elapsed,
                success=True,
            )
            return

        raise RuntimeError(
            "All fallback attempts failed for streaming."
            if last_error is None
            else f"All fallback attempts failed for streaming: {last_error}"
        )
