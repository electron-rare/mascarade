"""Prometheus metrics for LLM provider cost tracking."""

from __future__ import annotations

try:
    from prometheus_client import Counter, Gauge, Histogram
except ImportError:
    # Graceful fallback if prometheus_client is not installed
    Counter = None  # type: ignore
    Gauge = None  # type: ignore
    Histogram = None  # type: ignore


# Request counters
llm_requests_total = Counter(
    "mascarade_llm_requests_total",
    "Total number of LLM requests",
    ["provider", "model", "strategy", "status"],
) if Counter else None

# Token counters
llm_tokens_total = Counter(
    "mascarade_llm_tokens_total",
    "Total number of tokens processed",
    ["provider", "model", "token_type"],
) if Counter else None

# Cost counter
llm_cost_total = Counter(
    "mascarade_llm_cost_total",
    "Total cost in USD for LLM requests",
    ["provider", "model"],
) if Counter else None

# Response time histogram
llm_response_duration_seconds = Histogram(
    "mascarade_llm_response_duration_seconds",
    "LLM request duration in seconds",
    ["provider", "model"],
    buckets=(0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0, 120.0),
) if Histogram else None

# Current provider metrics (gauges)
llm_provider_error_rate = Gauge(
    "mascarade_llm_provider_error_rate",
    "Current error rate for provider (0.0 to 1.0)",
    ["provider"],
) if Gauge else None

llm_provider_avg_cost_per_request = Gauge(
    "mascarade_llm_provider_avg_cost_per_request",
    "Average cost per request for provider in USD",
    ["provider"],
) if Gauge else None

llm_provider_avg_tokens_per_request = Gauge(
    "mascarade_llm_provider_avg_tokens_per_request",
    "Average tokens per request for provider",
    ["provider", "token_type"],
) if Gauge else None


class CostMetrics:
    """Wrapper class for cost tracking metrics."""

    def __init__(self) -> None:
        """Initialize cost metrics wrapper."""
        self.requests_total = llm_requests_total
        self.tokens_total = llm_tokens_total
        self.cost_total = llm_cost_total
        self.response_duration = llm_response_duration_seconds
        self.provider_error_rate = llm_provider_error_rate
        self.provider_avg_cost = llm_provider_avg_cost_per_request
        self.provider_avg_tokens = llm_provider_avg_tokens_per_request
        self._enabled = Counter is not None

    def is_enabled(self) -> bool:
        """Check if Prometheus metrics are available."""
        return self._enabled

    def track_request(
        self,
        provider: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
        cost: float,
        duration: float,
        strategy: str | None = None,
        success: bool = True,
    ) -> None:
        """Track a completed LLM request.

        Args:
            provider: Provider name (e.g., 'openai', 'anthropic')
            model: Model name (e.g., 'gpt-4', 'claude-3-opus')
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            cost: Cost in USD
            duration: Request duration in seconds
            strategy: Routing strategy used (e.g., 'cheapest', 'fastest')
            success: Whether the request succeeded
        """
        if not self._enabled:
            return

        status = "success" if success else "error"
        strategy_label = strategy or "default"

        # Increment request counter
        if self.requests_total:
            self.requests_total.labels(
                provider=provider,
                model=model,
                strategy=strategy_label,
                status=status,
            ).inc()

        # Track tokens
        if self.tokens_total:
            self.tokens_total.labels(
                provider=provider,
                model=model,
                token_type="input",
            ).inc(input_tokens)

            self.tokens_total.labels(
                provider=provider,
                model=model,
                token_type="output",
            ).inc(output_tokens)

        # Track cost
        if self.cost_total:
            self.cost_total.labels(
                provider=provider,
                model=model,
            ).inc(cost)

        # Track response time
        if self.response_duration:
            self.response_duration.labels(
                provider=provider,
                model=model,
            ).observe(duration)

    def update_provider_metrics(
        self,
        provider: str,
        error_rate: float,
        avg_cost: float,
        avg_input_tokens: float,
        avg_output_tokens: float,
    ) -> None:
        """Update provider-level gauge metrics.

        Args:
            provider: Provider name
            error_rate: Error rate (0.0 to 1.0)
            avg_cost: Average cost per request in USD
            avg_input_tokens: Average input tokens per request
            avg_output_tokens: Average output tokens per request
        """
        if not self._enabled:
            return

        if self.provider_error_rate:
            self.provider_error_rate.labels(provider=provider).set(error_rate)

        if self.provider_avg_cost:
            self.provider_avg_cost.labels(provider=provider).set(avg_cost)

        if self.provider_avg_tokens:
            self.provider_avg_tokens.labels(
                provider=provider,
                token_type="input",
            ).set(avg_input_tokens)

            self.provider_avg_tokens.labels(
                provider=provider,
                token_type="output",
            ).set(avg_output_tokens)


# Global instance
COST_METRICS = CostMetrics()

# Alias for backward compatibility
total_cost_counter = llm_cost_total


__all__ = [
    "COST_METRICS",
    "CostMetrics",
    "llm_requests_total",
    "llm_tokens_total",
    "llm_cost_total",
    "llm_response_duration_seconds",
    "llm_provider_error_rate",
    "llm_provider_avg_cost_per_request",
    "llm_provider_avg_tokens_per_request",
    "total_cost_counter",
]
