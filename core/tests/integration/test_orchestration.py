"""Integration tests for agent orchestration flows."""

from __future__ import annotations

import asyncio

import pytest

from mascarade.agents.base import Agent
from mascarade.agents.registry import AgentRegistry
from mascarade.observability import AgentTraceBuffer
from mascarade.orchestrator.engine import Orchestrator
from mascarade.orchestrator.retry import RetryConfig, RetryExecutor
from mascarade.router.providers.base import LLMProvider, LLMResponse
from mascarade.router.router import Router


class IntegrationTestProvider(LLMProvider):
    """Test provider that simulates realistic LLM responses."""

    name = "integration-test"
    default_model = "test-model-v1"
    cost_per_million = (1.0, 2.0)
    speed_rank = 2
    quality_rank = 3

    def __init__(self, response_template: str = "Response: {content}"):
        self.response_template = response_template
        self.call_count = 0
        self.call_history: list[dict] = []

    async def send(self, messages, **kwargs):
        """Simulate a realistic send with slight delay."""
        self.call_count += 1
        content = messages[-1]["content"] if messages else ""

        # Record the call
        self.call_history.append(
            {
                "messages": messages,
                "kwargs": kwargs,
                "call_number": self.call_count,
            }
        )

        # Simulate network delay
        await asyncio.sleep(0.01)

        # Format response with available context
        format_kwargs = {
            "content": content,
            "system": kwargs.get("system", ""),
            "call_number": self.call_count,
        }
        try:
            response_content = self.response_template.format(**format_kwargs)
        except KeyError:
            # Fallback if template has unexpected placeholders
            response_content = self.response_template.format(content=content)

        return LLMResponse(
            content=response_content,
            model=kwargs.get("model") or self.default_model,
            provider=self.name,
            usage={"input_tokens": 10, "output_tokens": 15},
        )

    async def stream(self, messages, **kwargs):
        """Simulate streaming response."""
        content = messages[-1]["content"] if messages else ""
        response = self.response_template.format(content=content)

        for word in response.split():
            await asyncio.sleep(0.005)
            yield word + " "

    def available_models(self):
        return [self.default_model, "test-model-v2"]

    @property
    def is_configured(self):
        return True


class FailingIntegrationProvider(LLMProvider):
    """Provider that fails for integration testing."""

    name = "failing-integration"
    default_model = "failing-model"
    cost_per_million = (0.0, 0.0)
    speed_rank = 1
    quality_rank = 1

    def __init__(self, fail_count: int = 999):
        self.fail_count = fail_count
        self.attempt_count = 0

    async def send(self, messages, **kwargs):
        self.attempt_count += 1
        if self.attempt_count <= self.fail_count:
            await asyncio.sleep(0.01)
            raise RuntimeError(f"Integration test failure (attempt {self.attempt_count})")

        # Success after fail_count attempts
        return LLMResponse(
            content="Recovery successful",
            model=self.default_model,
            provider=self.name,
        )

    async def stream(self, messages, **kwargs):
        raise RuntimeError("Streaming not supported in failing provider")
        yield  # Unreachable but needed for generator

    def available_models(self):
        return [self.default_model]

    @property
    def is_configured(self):
        return True


def _make_integration_orchestrator(
    providers: list[LLMProvider] | None = None,
    agents: list[Agent] | None = None,
    retry_config: RetryConfig | None = None,
) -> Orchestrator:
    """Create an orchestrator for integration testing."""
    router = Router()
    router._providers.clear()

    if providers is None:
        providers = [IntegrationTestProvider()]

    for provider in providers:
        router.register(provider)

    registry = AgentRegistry()

    if agents is None:
        # Default agents for testing
        agents = [
            Agent(
                name="researcher",
                description="Researches topics",
                system_prompt="You are a thorough researcher. Analyze the topic deeply.",
            ),
            Agent(
                name="summarizer",
                description="Summarizes content",
                system_prompt="You are a concise summarizer. Extract key points.",
            ),
            Agent(
                name="reviewer",
                description="Reviews and critiques",
                system_prompt="You are a critical reviewer. Evaluate quality and accuracy.",
            ),
        ]

    for agent in agents:
        registry.register(agent)

    retry_executor = RetryExecutor(config=retry_config or RetryConfig(max_retries=0))

    return Orchestrator(
        router=router,
        registry=registry,
        trace_buffer=AgentTraceBuffer(),
        retry_executor=retry_executor,
    )


@pytest.mark.asyncio
async def test_sequential_orchestration_flow():
    """Test complete sequential orchestration with multiple agents."""
    orch = _make_integration_orchestrator()

    run = await orch.run(
        ["researcher", "summarizer", "reviewer"],
        "Analyze the importance of integration testing in software development",
        mode="sequential",
    )

    # Verify all agents executed in order
    assert len(run.results) == 3
    assert run.results[0].agent_name == "researcher"
    assert run.results[1].agent_name == "summarizer"
    assert run.results[2].agent_name == "reviewer"

    # Verify all succeeded
    for result in run.results:
        assert result.error is None
        assert result.response.content
        assert result.response.provider == "integration-test"
        assert result.response.usage["input_tokens"] > 0
        assert result.response.usage["output_tokens"] > 0


@pytest.mark.asyncio
async def test_parallel_orchestration_concurrent_execution():
    """Test parallel execution with concurrent agent runs."""
    import time

    orch = _make_integration_orchestrator()

    start_time = time.time()
    run = await orch.run(
        ["researcher", "summarizer", "reviewer"],
        "Test parallel execution",
        mode="parallel",
    )
    elapsed = time.time() - start_time

    # Verify all agents executed
    assert len(run.results) == 3
    agent_names = {r.agent_name for r in run.results}
    assert agent_names == {"researcher", "summarizer", "reviewer"}

    # Verify all succeeded
    for result in run.results:
        assert result.error is None
        assert result.response.content

    # Parallel should be faster than 3x sequential (with 0.01s delay each)
    # Allow margin for overhead but verify parallelism worked
    assert elapsed < 0.1  # Should be much less than 3 * 0.01 + overhead


@pytest.mark.asyncio
async def test_pipeline_orchestration_data_flow():
    """Test pipeline mode with data flowing between agents."""
    provider = IntegrationTestProvider(response_template="[Agent output] {content}")
    orch = _make_integration_orchestrator(providers=[provider])

    run = await orch.run(
        ["researcher", "summarizer", "reviewer"],
        "Initial research topic",
        mode="pipeline",
    )

    # Verify pipeline chain
    assert len(run.results) == 3

    # First agent receives initial input
    first_call = provider.call_history[0]
    assert "Initial research topic" in first_call["messages"][-1]["content"]

    # Second agent receives output from first
    second_call = provider.call_history[1]
    assert "[Agent output]" in second_call["messages"][-1]["content"]

    # Third agent receives output from second
    third_call = provider.call_history[2]
    assert "[Agent output]" in third_call["messages"][-1]["content"]


@pytest.mark.asyncio
async def test_orchestration_with_error_recovery():
    """Test error recovery in sequential mode with skip_on_error."""
    failing_provider = FailingIntegrationProvider(fail_count=1)
    success_provider = IntegrationTestProvider()

    agents = [
        Agent(
            name="good1",
            description="Works",
            system_prompt="You work fine.",
            preferred_provider="integration-test",
        ),
        Agent(
            name="failing",
            description="Fails",
            system_prompt="You fail.",
            preferred_provider="failing-integration",
            strategy="specific",
        ),
        Agent(
            name="good2",
            description="Works",
            system_prompt="You work fine.",
            preferred_provider="integration-test",
        ),
    ]

    orch = _make_integration_orchestrator(
        providers=[success_provider, failing_provider],
        agents=agents,
    )

    run = await orch.run(
        ["good1", "failing", "good2"],
        "Test error recovery",
        mode="sequential",
        skip_on_error=True,
    )

    # All three should have results
    assert len(run.results) == 3

    # First and third should succeed
    assert run.results[0].error is None
    assert run.results[0].agent_name == "good1"

    # Second should fail
    assert run.results[1].error is not None
    assert "Integration test failure" in run.results[1].error
    assert run.results[1].agent_name == "failing"

    # Third should still execute
    assert run.results[2].error is None
    assert run.results[2].agent_name == "good2"


@pytest.mark.asyncio
async def test_orchestration_trace_events_completeness():
    """Test that all trace events are properly recorded during orchestration."""
    orch = _make_integration_orchestrator()

    run = await orch.run(
        ["researcher", "summarizer"],
        "Test tracing",
        mode="pipeline",
    )

    # Get all events for this run
    events = orch.trace_buffer.run_events(run.run_id)
    event_types = [event.event_type for event in events]

    # Verify key events are present
    assert "run_started" in event_types
    assert "run_completed" in event_types

    # Should have agent_input and agent_output for each agent
    agent_inputs = [e for e in events if e.event_type == "agent_input"]
    agent_outputs = [e for e in events if e.event_type == "agent_output"]
    assert len(agent_inputs) == 2
    assert len(agent_outputs) == 2

    # Pipeline should have handoff event
    assert "handoff" in event_types

    # Verify event ordering
    event_order = [(e.event_type, e.agent_name) for e in events]

    # Should start with run_started
    assert event_order[0][0] == "run_started"

    # Should end with run_completed
    assert event_order[-1][0] == "run_completed"


@pytest.mark.asyncio
async def test_orchestration_with_fallback_agents():
    """Test fallback agent mechanism in pipeline mode."""
    failing_provider = FailingIntegrationProvider(fail_count=999)
    success_provider = IntegrationTestProvider(response_template="[Fallback] {content}")

    agents = [
        Agent(
            name="primary",
            description="Primary agent",
            system_prompt="Primary agent that fails.",
            preferred_provider="failing-integration",
            strategy="specific",
        ),
        Agent(
            name="backup",
            description="Backup agent",
            system_prompt="Backup agent that succeeds.",
            preferred_provider="integration-test",
        ),
    ]

    orch = _make_integration_orchestrator(
        providers=[failing_provider, success_provider],
        agents=agents,
    )

    run = await orch.run(
        ["primary"],
        "Test with fallback",
        mode="pipeline",
        fallback_map={"primary": "backup"},
    )

    # Should have one result
    assert len(run.results) == 1
    result = run.results[0]

    # Fallback should be used
    assert result.fallback_used is True
    assert result.fallback_agent == "backup"
    assert result.agent_name == "backup"
    assert result.error is None
    assert "[Fallback]" in result.response.content

    # Check trace events
    events = orch.trace_buffer.run_events(run.run_id)
    event_types = [e.event_type for e in events]
    assert "fallback_triggered" in event_types


@pytest.mark.asyncio
async def test_orchestration_dead_letter_recording():
    """Test that failures are recorded in dead letter store."""
    failing_provider = FailingIntegrationProvider()

    agents = [
        Agent(
            name="failing_agent",
            description="Always fails",
            system_prompt="Fails.",
            preferred_provider="failing-integration",
            strategy="specific",
        ),
    ]

    orch = _make_integration_orchestrator(
        providers=[failing_provider],
        agents=agents,
    )

    run = await orch.run(
        ["failing_agent"],
        "Test dead letter",
        mode="sequential",
        skip_on_error=True,
    )

    # Verify failure recorded
    assert len(run.results) == 1
    assert run.results[0].error is not None

    # Check dead letter store
    failures = orch.dead_letter_store.recent()
    run_failures = [f for f in failures if f.run_id == run.run_id]

    assert len(run_failures) > 0
    failure = run_failures[0]
    assert failure.agent_name == "failing_agent"
    assert "Integration test failure" in failure.error
    assert failure.mode == "sequential"


@pytest.mark.asyncio
async def test_multi_agent_pipeline_with_system_prompts():
    """Test that system prompts are correctly applied in pipeline."""
    provider = IntegrationTestProvider()

    agents = [
        Agent(
            name="agent1",
            description="First agent",
            system_prompt="SYSTEM_PROMPT_1",
        ),
        Agent(
            name="agent2",
            description="Second agent",
            system_prompt="SYSTEM_PROMPT_2",
        ),
    ]

    orch = _make_integration_orchestrator(
        providers=[provider],
        agents=agents,
    )

    run = await orch.run(
        ["agent1", "agent2"],
        "Test system prompts",
        mode="pipeline",
    )

    # Verify both agents executed
    assert len(run.results) == 2

    # Check that system prompts were used
    assert provider.call_count == 2

    # Verify each call had system context
    for _i, call in enumerate(provider.call_history):
        assert "kwargs" in call
        # Verify system prompt was passed
        assert "system" in call["kwargs"]
        # Each agent should have its own system prompt
        system_prompt = call["kwargs"]["system"]
        assert system_prompt in ["SYSTEM_PROMPT_1", "SYSTEM_PROMPT_2"]


@pytest.mark.asyncio
async def test_orchestration_with_routing_overrides():
    """Test that routing overrides are recorded in trace events."""
    provider1 = IntegrationTestProvider(response_template="[Provider1] {content}")
    provider1.name = "provider-1"

    provider2 = IntegrationTestProvider(response_template="[Provider2] {content}")
    provider2.name = "provider-2"

    agents = [
        Agent(
            name="agent1",
            description="Uses provider 1",
            system_prompt="Agent 1",
            preferred_provider="provider-1",
        ),
    ]

    orch = _make_integration_orchestrator(
        providers=[provider1, provider2],
        agents=agents,
    )

    # Run with routing override to use provider-2
    run = await orch.run(
        ["agent1"],
        "Test routing override",
        mode="sequential",
        routing_overrides={
            "agent1": {
                "preferred_provider": "provider-2",
            }
        },
    )

    # Verify run completed successfully
    assert len(run.results) == 1
    result = run.results[0]
    assert result.error is None

    # Check that routing override was recorded in trace events
    events = orch.trace_buffer.run_events(run.run_id)
    agent_input_events = [e for e in events if e.event_type == "agent_input"]

    assert len(agent_input_events) > 0
    # Routing override should be reflected in trace metadata
    assert agent_input_events[0].routing_provider == "provider-2"


@pytest.mark.asyncio
async def test_parallel_mode_partial_failures():
    """Test parallel mode returns both successes and failures."""
    failing_provider = FailingIntegrationProvider()
    success_provider = IntegrationTestProvider()

    agents = [
        Agent(
            name="good1",
            description="Works",
            system_prompt="Works.",
            preferred_provider="integration-test",
        ),
        Agent(
            name="failing",
            description="Fails",
            system_prompt="Fails.",
            preferred_provider="failing-integration",
            strategy="specific",
        ),
        Agent(
            name="good2",
            description="Works",
            system_prompt="Works.",
            preferred_provider="integration-test",
        ),
    ]

    orch = _make_integration_orchestrator(
        providers=[success_provider, failing_provider],
        agents=agents,
    )

    run = await orch.run(
        ["good1", "failing", "good2"],
        "Test partial failures",
        mode="parallel",
    )

    # All three should have results
    assert len(run.results) == 3

    # Check successes and failures
    successes = [r for r in run.results if r.error is None]
    failures = [r for r in run.results if r.error is not None]

    assert len(successes) == 2
    assert len(failures) == 1

    success_names = {r.agent_name for r in successes}
    failure_names = {r.agent_name for r in failures}

    assert success_names == {"good1", "good2"}
    assert failure_names == {"failing"}


@pytest.mark.asyncio
async def test_sequential_stops_on_first_error_by_default():
    """Test that sequential mode stops on first error without skip_on_error."""
    failing_provider = FailingIntegrationProvider()
    success_provider = IntegrationTestProvider()

    agents = [
        Agent(
            name="good1",
            description="Works",
            system_prompt="Works.",
            preferred_provider="integration-test",
        ),
        Agent(
            name="failing",
            description="Fails",
            system_prompt="Fails.",
            preferred_provider="failing-integration",
            strategy="specific",
        ),
        Agent(
            name="good2",
            description="Works",
            system_prompt="Works.",
            preferred_provider="integration-test",
        ),
    ]

    orch = _make_integration_orchestrator(
        providers=[success_provider, failing_provider],
        agents=agents,
    )

    run = await orch.run(
        ["good1", "failing", "good2"],
        "Test stop on error",
        mode="sequential",
        skip_on_error=False,  # Explicit default
    )

    # Should stop after second agent fails
    assert len(run.results) == 2
    assert run.results[0].agent_name == "good1"
    assert run.results[0].error is None
    assert run.results[1].agent_name == "failing"
    assert run.results[1].error is not None

    # good2 should not have been executed
    assert success_provider.call_count == 1  # Only good1


@pytest.mark.asyncio
async def test_pipeline_chain_with_context_accumulation():
    """Test that pipeline mode properly accumulates context through the chain."""
    provider = IntegrationTestProvider(
        response_template="[Step {call_number}] Processed: {content}"
    )

    orch = _make_integration_orchestrator(providers=[provider])

    run = await orch.run(
        ["researcher", "summarizer", "reviewer"],
        "Initial topic: Python testing",
        mode="pipeline",
    )

    # Verify the chain
    assert len(run.results) == 3

    # Each agent should see the output from the previous one
    # First sees initial input
    assert "Initial topic: Python testing" in provider.call_history[0]["messages"][-1]["content"]

    # Second sees first's output
    second_input = provider.call_history[1]["messages"][-1]["content"]
    assert "[Step 1]" in second_input or "Processed" in second_input

    # Third sees second's output
    third_input = provider.call_history[2]["messages"][-1]["content"]
    assert "[Step 2]" in third_input or "Processed" in third_input
