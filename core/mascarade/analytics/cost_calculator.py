"""Cost calculator with dynamic pricing support for LLM providers."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from functools import lru_cache
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mascarade.router.providers.base import LLMProvider

logger = logging.getLogger("mascarade.analytics.cost_calculator")


@dataclass
class PricingTier:
    """Pricing tier for a specific provider/model combination."""

    provider: str
    model: str
    input_cost_per_million: float
    output_cost_per_million: float

    def calculate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """
        Calculate total cost for given token usage.

        Args:
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens

        Returns:
            Cost in USD
        """
        input_cost = (input_tokens * self.input_cost_per_million) / 1_000_000
        output_cost = (output_tokens * self.output_cost_per_million) / 1_000_000
        return input_cost + output_cost


class CostCalculator:
    """
    Dynamic cost calculator for LLM providers.

    Supports:
    - Provider-specific pricing
    - Model-specific pricing overrides
    - Dynamic pricing updates
    - Fallback to provider defaults
    """

    def __init__(self) -> None:
        """Initialize cost calculator with empty pricing table."""
        # Model-specific pricing overrides: (provider, model) -> PricingTier
        self._pricing_table: dict[tuple[str, str], PricingTier] = {}

        # Provider default pricing: provider -> (input_cost, output_cost)
        self._provider_defaults: dict[str, tuple[float, float]] = {}

    def register_provider_pricing(
        self,
        provider: str,
        input_cost_per_million: float,
        output_cost_per_million: float,
    ) -> None:
        """
        Register default pricing for a provider.

        Args:
            provider: Provider name (e.g., "openai", "claude")
            input_cost_per_million: Cost per 1M input tokens in USD
            output_cost_per_million: Cost per 1M output tokens in USD
        """
        self._provider_defaults[provider] = (
            input_cost_per_million,
            output_cost_per_million,
        )
        logger.debug(
            "Registered default pricing for %s: $%.2f/$%.2f per 1M tokens",
            provider,
            input_cost_per_million,
            output_cost_per_million,
        )

    def register_model_pricing(
        self,
        provider: str,
        model: str,
        input_cost_per_million: float,
        output_cost_per_million: float,
    ) -> None:
        """
        Register specific pricing for a provider/model combination.

        Args:
            provider: Provider name (e.g., "openai", "claude")
            model: Model identifier (e.g., "gpt-4", "claude-sonnet-4")
            input_cost_per_million: Cost per 1M input tokens in USD
            output_cost_per_million: Cost per 1M output tokens in USD
        """
        tier = PricingTier(
            provider=provider,
            model=model,
            input_cost_per_million=input_cost_per_million,
            output_cost_per_million=output_cost_per_million,
        )
        self._pricing_table[(provider, model)] = tier
        logger.debug(
            "Registered model pricing for %s/%s: $%.2f/$%.2f per 1M tokens",
            provider,
            model,
            input_cost_per_million,
            output_cost_per_million,
        )

    def register_from_provider(self, provider: LLMProvider) -> None:
        """
        Register pricing from a provider instance.

        Args:
            provider: LLMProvider instance with cost_per_million attribute
        """
        input_cost, output_cost = provider.cost_per_million
        self.register_provider_pricing(
            provider=provider.name,
            input_cost_per_million=input_cost,
            output_cost_per_million=output_cost,
        )

    def get_pricing(self, provider: str, model: str) -> PricingTier | None:
        """
        Get pricing tier for a specific provider/model combination.

        Args:
            provider: Provider name
            model: Model identifier

        Returns:
            PricingTier if found, None otherwise
        """
        # Try model-specific pricing first
        if (provider, model) in self._pricing_table:
            return self._pricing_table[(provider, model)]

        # Fallback to provider default
        if provider in self._provider_defaults:
            input_cost, output_cost = self._provider_defaults[provider]
            return PricingTier(
                provider=provider,
                model=model,
                input_cost_per_million=input_cost,
                output_cost_per_million=output_cost,
            )

        return None

    def calculate_cost(
        self,
        provider: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
    ) -> float:
        """
        Calculate cost for a request.

        Args:
            provider: Provider name (e.g., "openai", "claude")
            model: Model identifier (e.g., "gpt-4", "claude-sonnet-4")
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens

        Returns:
            Cost in USD, or 0.0 if pricing not found
        """
        pricing = self.get_pricing(provider, model)
        if pricing is None:
            logger.warning(
                "No pricing found for %s/%s, returning 0.0",
                provider,
                model,
            )
            return 0.0

        return pricing.calculate_cost(input_tokens, output_tokens)

    def update_pricing_table(
        self,
        pricing_data: dict[tuple[str, str], tuple[float, float]],
    ) -> None:
        """
        Bulk update pricing table.

        Args:
            pricing_data: Dictionary mapping (provider, model) to
                         (input_cost_per_million, output_cost_per_million)
        """
        for (provider, model), (input_cost, output_cost) in pricing_data.items():
            self.register_model_pricing(
                provider=provider,
                model=model,
                input_cost_per_million=input_cost,
                output_cost_per_million=output_cost,
            )
        logger.info("Updated %d pricing entries", len(pricing_data))

    def get_all_pricing(self) -> dict[tuple[str, str], PricingTier]:
        """
        Get all registered pricing tiers.

        Returns:
            Dictionary of (provider, model) -> PricingTier
        """
        return self._pricing_table.copy()

    def clear_pricing(self) -> None:
        """Clear all pricing data."""
        self._pricing_table.clear()
        self._provider_defaults.clear()
        logger.info("Cleared all pricing data")


@lru_cache(maxsize=1)
def get_cost_calculator() -> CostCalculator:
    """
    Get or create the global cost calculator instance.

    Returns:
        Singleton CostCalculator instance
    """
    return CostCalculator()


def reset_cost_calculator() -> None:
    """Reset the cached cost calculator instance."""
    get_cost_calculator.cache_clear()
