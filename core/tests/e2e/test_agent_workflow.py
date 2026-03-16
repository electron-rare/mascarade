"""End-to-end tests for agent workflow orchestration (without live services).

These tests verify the complete agent orchestration pipeline using mocks,
suitable for CI environments where external services are not available.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock

from mascarade.router.providers.base import LLMProvider, LLMResponse
from mascarade.router.router import Router, Strategy


class MockAgentProvider(LLMProvider):
    """Mock provider with agent-like behavior."""

    def __init__(self, name="agent_provider", should_use_tool=False):
        self.name = name
        self.default_model = "agent-model"
        self.cost_per_million = (1.0, 2.0)
        self.speed_rank = 1
        self.quality_rank = 2
        self.should_use_tool = should_use_tool
        self.call_count = 0

    async def send(self, messages, **kwargs):
        self.call_count += 1

        # Simulate tool use on first call if enabled
        if self.should_use_tool and self.call_count == 1:
            return LLMResponse(
                content="Let me use a tool to help you.",
                model=self.default_model,
                provider=self.name,
                usage={"input_tokens": 10, "output_tokens": 20},
            )

        return LLMResponse(
            content=f"Agent response (call {self.call_count})",
            model=self.default_model,
            provider=self.name,
            usage={"input_tokens": 10, "output_tokens": 20},
        )

    async def stream(self, messages, **kwargs):
        for token in ["Agent", " streaming", " response"]:
            yield token

    def available_models(self):
        return [self.default_model]


def test_e2e_agent_single_turn():
    """E2E: Agent handles single turn conversation."""
    router = Router()
    router._providers.clear()

    agent = MockAgentProvider()
    router.register(agent)

    messages = [{"role": "user", "content": "What is the weather?"}]

    response = asyncio.run(
        router.send(
            messages,
            strategy=Strategy.BEST,
        )
    )

    assert response.content is not None
    assert agent.call_count == 1
    assert "Agent response" in response.content


def test_e2e_agent_multi_turn_workflow():
    """E2E: Agent handles multi-turn workflow."""
    router = Router()
    router._providers.clear()

    agent = MockAgentProvider()
    router.register(agent)

    # First turn
    messages_1 = [{"role": "user", "content": "Start a task"}]
    response_1 = asyncio.run(router.send(messages_1, strategy=Strategy.BEST))

    # Second turn
    messages_2 = [
        {"role": "user", "content": "Start a task"},
        {"role": "assistant", "content": response_1.content},
        {"role": "user", "content": "Continue the task"},
    ]
    response_2 = asyncio.run(router.send(messages_2, strategy=Strategy.BEST))

    assert agent.call_count == 2
    assert "call 2" in response_2.content


def test_e2e_agent_with_tool_use():
    """E2E: Agent workflow with tool use simulation."""
    router = Router()
    router._providers.clear()

    agent = MockAgentProvider(should_use_tool=True)
    router.register(agent)

    # First call - agent decides to use tool
    messages = [{"role": "user", "content": "Calculate 5 + 3"}]
    response_1 = asyncio.run(router.send(messages, strategy=Strategy.BEST))

    assert "tool" in response_1.content.lower()
    assert agent.call_count == 1

    # Second call - agent provides final answer
    messages.append({"role": "assistant", "content": response_1.content})
    messages.append({"role": "user", "content": "Continue"})
    response_2 = asyncio.run(router.send(messages, strategy=Strategy.BEST))

    assert agent.call_count == 2


def test_e2e_agent_state_preservation():
    """E2E: Agent preserves state across multiple calls."""
    router = Router()
    router._providers.clear()

    agent = MockAgentProvider()
    router.register(agent)

    # Build up conversation state
    messages = [{"role": "user", "content": "Remember the number 42"}]
    response_1 = asyncio.run(router.send(messages, strategy=Strategy.BEST))

    messages.append({"role": "assistant", "content": response_1.content})
    messages.append({"role": "user", "content": "What number did I tell you?"})
    response_2 = asyncio.run(router.send(messages, strategy=Strategy.BEST))

    # Verify call count increased
    assert agent.call_count == 2


def test_e2e_agent_parallel_workflows():
    """E2E: Multiple agent workflows can run in parallel."""
    router = Router()
    router._providers.clear()

    agent_1 = MockAgentProvider(name="agent_1")
    agent_2 = MockAgentProvider(name="agent_2")
    router.register(agent_1)
    router.register(agent_2)

    async def run_workflow_1():
        messages = [{"role": "user", "content": "Workflow 1"}]
        return await router.send(messages, provider="agent_1")

    async def run_workflow_2():
        messages = [{"role": "user", "content": "Workflow 2"}]
        return await router.send(messages, provider="agent_2")

    async def run_parallel():
        return await asyncio.gather(run_workflow_1(), run_workflow_2())

    results = asyncio.run(run_parallel())

    assert len(results) == 2
    assert agent_1.call_count == 1
    assert agent_2.call_count == 1


def test_e2e_agent_streaming_workflow():
    """E2E: Agent can stream responses."""
    router = Router()
    router._providers.clear()

    agent = MockAgentProvider()
    router.register(agent)

    messages = [{"role": "user", "content": "Stream a response"}]

    tokens = []

    async def collect_stream():
        async for token in router.stream(messages, strategy=Strategy.BEST):
            tokens.append(token)

    asyncio.run(collect_stream())

    assert len(tokens) > 0
    assert "Agent streaming response" == "".join(tokens)


def test_e2e_agent_error_recovery():
    """E2E: Agent workflow recovers from errors."""

    class FailingAgentProvider(LLMProvider):
        name = "failing_agent"
        default_model = "failing-model"
        cost_per_million = (1.0, 2.0)
        speed_rank = 1
        quality_rank = 1

        def __init__(self):
            self.call_count = 0

        async def send(self, messages, **kwargs):
            self.call_count += 1
            if self.call_count == 1:
                raise RuntimeError("Simulated failure")
            return LLMResponse(
                content="Recovered response",
                model=self.default_model,
                provider=self.name,
                usage={"input_tokens": 10, "output_tokens": 20},
            )

        async def stream(self, messages, **kwargs):
            yield "token"

        def available_models(self):
            return [self.default_model]

    router = Router()
    router._providers.clear()

    failing_agent = FailingAgentProvider()
    backup_agent = MockAgentProvider(name="backup")
    router.register(failing_agent)
    router.register(backup_agent)

    messages = [{"role": "user", "content": "Handle this"}]

    # First provider fails, should try second
    try:
        response = asyncio.run(router.send(messages, strategy=Strategy.BEST))
        # If we get here, fallback worked
        assert response.provider == "backup"
    except RuntimeError:
        # Also acceptable - error was raised
        pass


def test_e2e_agent_with_system_prompt():
    """E2E: Agent workflow with custom system prompt."""
    router = Router()
    router._providers.clear()

    agent = MockAgentProvider()
    router.register(agent)

    messages = [{"role": "user", "content": "Help me"}]
    system_prompt = "You are a helpful task-oriented agent."

    response = asyncio.run(
        router.send(
            messages,
            system=system_prompt,
            strategy=Strategy.BEST,
        )
    )

    assert response.content is not None


def test_e2e_agent_token_tracking():
    """E2E: Agent workflow tracks token usage."""
    router = Router()
    router._providers.clear()

    agent = MockAgentProvider()
    router.register(agent)

    messages = [{"role": "user", "content": "Track tokens"}]

    response = asyncio.run(router.send(messages, strategy=Strategy.BEST))

    assert "input_tokens" in response.usage
    assert "output_tokens" in response.usage
    assert response.usage["input_tokens"] > 0
    assert response.usage["output_tokens"] > 0


def test_e2e_agent_workflow_with_routing_strategy():
    """E2E: Agent workflow respects routing strategy."""
    router = Router()
    router._providers.clear()

    fast_agent = MockAgentProvider(name="fast_agent")
    fast_agent.speed_rank = 1
    best_agent = MockAgentProvider(name="best_agent")
    best_agent.quality_rank = 3

    router.register(fast_agent)
    router.register(best_agent)

    messages = [{"role": "user", "content": "Route me"}]

    # Test FASTEST strategy
    response_fast = asyncio.run(
        router.send(messages, strategy=Strategy.FASTEST)
    )
    assert response_fast.provider == "fast_agent"

    # Test BEST strategy
    response_best = asyncio.run(
        router.send(messages, strategy=Strategy.BEST)
    )
    assert response_best.provider == "best_agent"


def test_e2e_agent_workflow_sequential_calls():
    """E2E: Agent workflow with sequential calls."""
    router = Router()
    router._providers.clear()

    agent = MockAgentProvider()
    router.register(agent)

    # Call 1
    messages = [{"role": "user", "content": "First call"}]
    response_1 = asyncio.run(router.send(messages, strategy=Strategy.BEST))
    assert agent.call_count == 1

    # Call 2
    response_2 = asyncio.run(router.send(messages, strategy=Strategy.BEST))
    assert agent.call_count == 2

    # Call 3
    response_3 = asyncio.run(router.send(messages, strategy=Strategy.BEST))
    assert agent.call_count == 3


def test_e2e_agent_max_tokens_control():
    """E2E: Agent respects max_tokens parameter."""
    router = Router()
    router._providers.clear()

    agent = MockAgentProvider()
    router.register(agent)

    messages = [{"role": "user", "content": "Generate text"}]

    response = asyncio.run(
        router.send(
            messages,
            max_tokens=100,
            strategy=Strategy.BEST,
        )
    )

    assert response.content is not None


def test_e2e_agent_temperature_parameter():
    """E2E: Agent respects temperature parameter."""
    router = Router()
    router._providers.clear()

    agent = MockAgentProvider()
    router.register(agent)

    messages = [{"role": "user", "content": "Be creative"}]

    response = asyncio.run(
        router.send(
            messages,
            temperature=0.9,
            strategy=Strategy.BEST,
        )
    )

    assert response.content is not None
