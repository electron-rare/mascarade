"""End-to-end tests for basic chat workflows (without live services).

These tests verify the complete chat pipeline using mocks,
suitable for CI environments where external providers are not available.
"""

import asyncio
import time

from mascarade.router.providers.base import LLMProvider, LLMResponse
from mascarade.router.router import Router, Strategy


class MockOpenAIProvider(LLMProvider):
    """Mock OpenAI provider for testing."""

    def __init__(self):
        self.name = "openai"
        self.default_model = "gpt-3.5-turbo"
        self.cost_per_million = (0.5, 1.5)
        self.speed_rank = 2
        self.quality_rank = 2
        self.last_call = {}

    async def send(self, messages, **kwargs):
        model = kwargs.get("model") or self.default_model
        self.last_call = {"messages": messages, "model": model, "kwargs": kwargs}
        return LLMResponse(
            content=f"OpenAI response from {model}",
            model=model,
            provider=self.name,
            usage={"input_tokens": 15, "output_tokens": 25},
        )

    async def stream(self, messages, **kwargs):
        model = kwargs.get("model", self.default_model)
        for token in ["Hello", " from", " OpenAI"]:
            yield token

    def available_models(self):
        return ["gpt-3.5-turbo", "gpt-4", "gpt-4-turbo"]


class MockClaudeProvider(LLMProvider):
    """Mock Claude provider for testing."""

    name = "claude"
    default_model = "claude-3.5-sonnet"
    cost_per_million = (5.0, 10.0)
    speed_rank = 3
    quality_rank = 3

    async def send(self, messages, **kwargs):
        return LLMResponse(
            content="Claude response: This is a thoughtful answer.",
            model=self.default_model,
            provider=self.name,
            usage={"input_tokens": 20, "output_tokens": 30},
        )

    async def stream(self, messages, **kwargs):
        for token in ["Claude", " streaming", " response"]:
            yield token

    def available_models(self):
        return [self.default_model, "claude-3-opus"]


def test_e2e_basic_chat_completion():
    """E2E: Basic chat completion with single message."""
    router = Router()
    router._providers.clear()

    openai = MockOpenAIProvider()
    router.register(openai)

    messages = [{"role": "user", "content": "Hello, how are you?"}]

    response = asyncio.run(
        router.send(
            messages,
            strategy=Strategy.FASTEST,
            max_tokens=100,
        )
    )

    # Verify basic response structure
    assert response.content is not None
    assert response.provider == "openai"
    assert response.model in openai.available_models()
    assert "input_tokens" in response.usage
    assert "output_tokens" in response.usage


def test_e2e_multi_turn_conversation():
    """E2E: Multi-turn conversation preserves context."""
    router = Router()
    router._providers.clear()

    openai = MockOpenAIProvider()
    router.register(openai)

    # Multi-turn conversation
    messages = [
        {"role": "user", "content": "What is Python?"},
        {"role": "assistant", "content": "Python is a programming language."},
        {"role": "user", "content": "Tell me more about it."},
    ]

    response = asyncio.run(
        router.send(
            messages,
            strategy=Strategy.BEST,
            temperature=0.7,
        )
    )

    assert response.content is not None
    assert len(openai.last_call["messages"]) == 3
    assert openai.last_call["kwargs"]["temperature"] == 0.7


def test_e2e_system_message_handling():
    """E2E: System message is properly included."""
    router = Router()
    router._providers.clear()

    openai = MockOpenAIProvider()
    router.register(openai)

    messages = [{"role": "user", "content": "Help me write code"}]

    response = asyncio.run(
        router.send(
            messages,
            system="You are a helpful coding assistant.",
            strategy=Strategy.BEST,
        )
    )

    assert response.content is not None
    assert "system" in openai.last_call["kwargs"]
    assert openai.last_call["kwargs"]["system"] == "You are a helpful coding assistant."


def test_e2e_streaming_chat():
    """E2E: Streaming chat works correctly."""
    router = Router()
    router._providers.clear()

    openai = MockOpenAIProvider()
    router.register(openai)

    messages = [{"role": "user", "content": "Tell me a story"}]

    tokens = []

    async def collect_tokens():
        async for token in router.stream(
            messages,
            strategy=Strategy.FASTEST,
        ):
            tokens.append(token)

    asyncio.run(collect_tokens())

    # Verify streaming worked
    assert len(tokens) > 0
    assert "".join(tokens) == "Hello from OpenAI"


def test_e2e_best_strategy_selects_highest_quality():
    """E2E: BEST strategy selects provider with highest quality rank."""
    router = Router()
    router._providers.clear()

    openai = MockOpenAIProvider()
    claude = MockClaudeProvider()
    router.register(openai)
    router.register(claude)

    messages = [{"role": "user", "content": "What is the meaning of life?"}]

    response = asyncio.run(
        router.send(
            messages,
            strategy=Strategy.BEST,
        )
    )

    # Claude has higher quality_rank (3 vs 2)
    assert response.provider == "claude"


def test_e2e_fastest_strategy_selects_lowest_speed_rank():
    """E2E: FASTEST strategy selects provider with lowest speed rank."""
    router = Router()
    router._providers.clear()

    openai = MockOpenAIProvider()
    claude = MockClaudeProvider()
    router.register(openai)
    router.register(claude)

    messages = [{"role": "user", "content": "Quick question"}]

    response = asyncio.run(
        router.send(
            messages,
            strategy=Strategy.FASTEST,
        )
    )

    # OpenAI has lower speed_rank (2 vs 3)
    assert response.provider == "openai"


def test_e2e_cheapest_strategy_selects_lowest_cost():
    """E2E: CHEAPEST strategy selects provider with lowest cost."""
    router = Router()
    router._providers.clear()

    openai = MockOpenAIProvider()
    claude = MockClaudeProvider()
    router.register(openai)
    router.register(claude)

    messages = [{"role": "user", "content": "Budget question"}]

    response = asyncio.run(
        router.send(
            messages,
            strategy=Strategy.CHEAPEST,
            max_tokens=100,
        )
    )

    # OpenAI is cheaper (0.5/1.5 vs 5.0/10.0)
    assert response.provider == "openai"


def test_e2e_specific_strategy_with_model_override():
    """E2E: SPECIFIC strategy with explicit model selection."""
    router = Router()
    router._providers.clear()

    openai = MockOpenAIProvider()
    router.register(openai)

    messages = [{"role": "user", "content": "Use GPT-4"}]

    response = asyncio.run(
        router.send(
            messages,
            strategy=Strategy.SPECIFIC,
            model="gpt-4",
        )
    )

    assert response.model == "gpt-4"
    assert response.provider == "openai"


def test_e2e_temperature_control():
    """E2E: Temperature parameter is passed correctly."""
    router = Router()
    router._providers.clear()

    openai = MockOpenAIProvider()
    router.register(openai)

    messages = [{"role": "user", "content": "Creative writing task"}]

    # High temperature for creative output
    response = asyncio.run(
        router.send(
            messages,
            temperature=1.2,
            strategy=Strategy.BEST,
        )
    )

    assert openai.last_call["kwargs"]["temperature"] == 1.2


def test_e2e_max_tokens_limit():
    """E2E: max_tokens parameter is respected."""
    router = Router()
    router._providers.clear()

    openai = MockOpenAIProvider()
    router.register(openai)

    messages = [{"role": "user", "content": "Short answer please"}]

    response = asyncio.run(
        router.send(
            messages,
            max_tokens=50,
            strategy=Strategy.FASTEST,
        )
    )

    assert openai.last_call["kwargs"]["max_tokens"] == 50


def test_e2e_empty_provider_list_raises_error():
    """E2E: Empty provider list raises appropriate error."""
    router = Router()
    router._providers.clear()

    messages = [{"role": "user", "content": "Hello"}]

    try:
        asyncio.run(
            router.send(
                messages,
                strategy=Strategy.BEST,
            )
        )
        assert False, "Should have raised an error"
    except (ValueError, RuntimeError):
        # Expected - no providers available
        pass


def test_e2e_multiple_providers_all_registered():
    """E2E: Multiple providers can be registered and accessed."""
    router = Router()
    router._providers.clear()

    openai = MockOpenAIProvider()
    claude = MockClaudeProvider()
    router.register(openai)
    router.register(claude)

    # Verify both providers are registered
    assert "openai" in router._providers
    assert "claude" in router._providers
    assert len(router._providers) == 2


def test_e2e_token_usage_tracking():
    """E2E: Token usage is tracked correctly."""
    router = Router()
    router._providers.clear()

    openai = MockOpenAIProvider()
    router.register(openai)

    messages = [{"role": "user", "content": "Track my tokens"}]

    response = asyncio.run(
        router.send(
            messages,
            strategy=Strategy.FASTEST,
        )
    )

    # Verify token usage is reported
    assert response.usage["input_tokens"] > 0
    assert response.usage["output_tokens"] > 0


def test_e2e_basic_performance_tracking():
    """E2E: Basic performance metrics are reasonable."""
    router = Router()
    router._providers.clear()

    openai = MockOpenAIProvider()
    router.register(openai)

    messages = [{"role": "user", "content": "Performance check"}]

    # Measure basic request latency
    start = time.perf_counter()
    response = asyncio.run(
        router.send(
            messages,
            strategy=Strategy.FASTEST,
        )
    )
    elapsed_ms = (time.perf_counter() - start) * 1000

    # Basic sanity check - mock should be fast
    assert elapsed_ms < 100, f"Mock request took {elapsed_ms:.2f}ms, expected < 100ms"
    assert response.content is not None
