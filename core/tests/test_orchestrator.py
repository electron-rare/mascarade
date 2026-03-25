"""Tests pour l'orchestrateur."""

import asyncio

from mascarade.agents.base import Agent
from mascarade.agents.registry import AgentRegistry
from mascarade.observability import AgentTraceBuffer
from mascarade.orchestrator.engine import Orchestrator
from mascarade.router.providers.base import LLMProvider, LLMResponse
from mascarade.router.router import Router


class MockProvider(LLMProvider):
    name = "mock"
    default_model = "mock-model"
    cost_per_million = (0.0, 0.0)
    speed_rank = 1
    quality_rank = 1

    async def send(self, messages, **kwargs):
        content = messages[-1]["content"] if messages else ""
        return LLMResponse(
            content=f"[mock] {content}",
            model=self.default_model,
            provider=self.name,
        )

    async def stream(self, messages, **kwargs):
        yield "[mock]"

    def available_models(self):
        return [self.default_model]

    @property
    def is_configured(self):
        return True


class FailingProvider(LLMProvider):
    """Provider that always fails for testing error handling."""

    name = "failing"
    default_model = "failing-model"
    cost_per_million = (0.0, 0.0)
    speed_rank = 1
    quality_rank = 1

    async def send(self, messages, **kwargs):
        raise RuntimeError("Simulated agent failure")

    async def stream(self, messages, **kwargs):
        raise RuntimeError("Simulated agent failure")
        yield  # Unreachable but needed for generator

    def available_models(self):
        return [self.default_model]

    @property
    def is_configured(self):
        return True


class FakeCluster:
    enabled = True

    async def forward_send(
        self,
        *,
        peer_id=None,
        preferred_role=None,
        allow_local=True,
        payload=None,
    ):
        return {
            "content": f"[remote:{preferred_role}] {payload['messages'][-1]['content']}",
            "model": payload.get("model") or "remote-model",
            "provider": payload.get("provider") or "remote-provider",
            "usage": {"input_tokens": 4, "output_tokens": 9},
            "remote": True,
            "selected_by": "auto-peer",
            "peer_id": "node-gpu",
            "node_id": "node-gpu",
            "role": preferred_role or "gpu",
            "transport": "p2p",
            "latency_ms": 18,
        }


class RecordingCluster(FakeCluster):
    def __init__(self) -> None:
        self.calls: list[dict] = []

    async def forward_send(
        self,
        *,
        peer_id=None,
        preferred_role=None,
        allow_local=True,
        payload=None,
    ):
        self.calls.append(
            {
                "peer_id": peer_id,
                "preferred_role": preferred_role,
                "allow_local": allow_local,
                "payload": payload,
            }
        )
        return await super().forward_send(
            peer_id=peer_id,
            preferred_role=preferred_role,
            allow_local=allow_local,
            payload=payload,
        )


class RecordingRouter:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    async def send(self, messages, **kwargs):
        self.calls.append({"messages": messages, **kwargs})
        return LLMResponse(
            content=f"[local:{kwargs.get('provider')}:{kwargs.get('model')}] {messages[-1]['content']}",
            model=kwargs.get("model") or "mock-model",
            provider=kwargs.get("provider") or "mock",
            usage={"input_tokens": 2, "output_tokens": 5},
        )


def _make_orchestrator() -> Orchestrator:
    router = Router()
    router._providers.clear()
    router.register(MockProvider())

    registry = AgentRegistry()
    registry.register(
        Agent(name="analyst", description="Analyzes", system_prompt="Analyze.")
    )
    registry.register(
        Agent(name="writer", description="Writes", system_prompt="Write.")
    )

    return Orchestrator(
        router=router, registry=registry, trace_buffer=AgentTraceBuffer()
    )


def test_sequential():
    orch = _make_orchestrator()
    run = asyncio.run(orch.run(["analyst", "writer"], "test", mode="sequential"))
    assert run.run_id
    assert run.mode.value == "sequential"
    assert len(run.results) == 2
    assert run.results[0].agent_name == "analyst"
    assert run.results[1].agent_name == "writer"


def test_parallel():
    orch = _make_orchestrator()
    run = asyncio.run(orch.run(["analyst", "writer"], "test", mode="parallel"))
    assert run.run_id
    assert len(run.results) == 2
    agent_names = {r.agent_name for r in run.results}
    assert agent_names == {"analyst", "writer"}


def test_pipeline():
    orch = _make_orchestrator()
    run = asyncio.run(orch.run(["analyst", "writer"], "start", mode="pipeline"))
    assert len(run.results) == 2
    # Pipeline: output of first becomes input of second
    assert "[mock]" in run.results[1].response.content


def test_traces_are_recorded_for_pipeline_runs():
    orch = _make_orchestrator()
    run = asyncio.run(orch.run(["analyst", "writer"], "start", mode="pipeline"))

    events = orch.trace_buffer.run_events(run.run_id)
    event_types = [event.event_type for event in events]

    assert "run_started" in event_types
    assert "agent_input" in event_types
    assert "agent_output" in event_types
    assert "handoff" in event_types
    assert "run_completed" in event_types


def test_orchestrator_uses_cluster_auto_routing_when_enabled():
    router = Router()
    router._providers.clear()
    router.register(MockProvider())

    registry = AgentRegistry()
    registry.register(
        Agent(
            name="gpu-agent",
            description="GPU lane",
            system_prompt="Route to GPU.",
            preferred_provider="ollama",
            preferred_model="llama3.2:3b",
            preferred_role="gpu",
        )
    )

    orch = Orchestrator(
        router=router,
        registry=registry,
        trace_buffer=AgentTraceBuffer(),
        cluster=FakeCluster(),
    )

    run = asyncio.run(orch.run(["gpu-agent"], "cluster test", mode="sequential"))

    assert len(run.results) == 1
    result = run.results[0]
    assert result.remote is True
    assert result.selected_by == "auto-peer"
    assert result.peer_id == "node-gpu"
    assert result.node_id == "node-gpu"
    assert result.role == "gpu"
    assert result.transport == "p2p"
    assert result.latency_ms == 18
    assert result.response.provider == "ollama"
    assert result.response.model == "llama3.2:3b"
    assert result.response.content == "[remote:gpu] cluster test"
    agent_output = next(
        event
        for event in orch.trace_buffer.run_events(run.run_id)
        if event.event_type == "agent_output"
    )
    assert agent_output.routing_selected_by == "auto-peer"
    assert agent_output.routing_transport == "p2p"
    assert agent_output.routing_latency_ms == 18


def test_orchestrator_routing_override_takes_precedence_over_agent_profile():
    router = Router()
    router._providers.clear()
    router.register(MockProvider())

    registry = AgentRegistry()
    registry.register(
        Agent(
            name="hybrid-agent",
            description="Hybrid lane",
            system_prompt="Route me.",
            preferred_provider="ollama",
            preferred_model="llama3.2:3b",
            preferred_role="general",
        )
    )

    cluster = RecordingCluster()
    orch = Orchestrator(
        router=router,
        registry=registry,
        trace_buffer=AgentTraceBuffer(),
        cluster=cluster,
    )

    run = asyncio.run(
        orch.run(
            ["hybrid-agent"],
            "override test",
            mode="sequential",
            routing_overrides={
                "hybrid-agent": {
                    "preferred_role": "gpu",
                    "preferred_provider": "mistral",
                    "preferred_model": "mistral-large-latest",
                }
            },
        )
    )

    assert len(cluster.calls) == 1
    assert cluster.calls[0]["preferred_role"] == "gpu"
    assert cluster.calls[0]["payload"]["provider"] == "mistral"
    assert cluster.calls[0]["payload"]["model"] == "mistral-large-latest"
    assert run.results[0].role == "gpu"
    assert run.results[0].response.content == "[remote:gpu] override test"
    events = orch.trace_buffer.run_events(run.run_id)
    agent_input = next(event for event in events if event.event_type == "agent_input")
    agent_output = next(event for event in events if event.event_type == "agent_output")
    assert agent_input.routing_role == "gpu"
    assert agent_input.routing_provider == "mistral"
    assert agent_input.routing_model == "mistral-large-latest"
    assert agent_output.routing_selected_by == "auto-peer"
    assert agent_output.routing_transport == "p2p"
    assert agent_output.routing_latency_ms == 18


def test_orchestrator_applies_provider_model_override_locally_when_cluster_disabled():
    router = RecordingRouter()
    registry = AgentRegistry()
    registry.register(
        Agent(
            name="local-agent",
            description="Local lane",
            system_prompt="Local route.",
            preferred_provider="ollama",
            preferred_model="llama3.2:3b",
            preferred_role="general",
        )
    )

    orch = Orchestrator(
        router=router,  # type: ignore[arg-type]
        registry=registry,
        trace_buffer=AgentTraceBuffer(),
        cluster=None,
    )

    run = asyncio.run(
        orch.run(
            ["local-agent"],
            "local override",
            mode="sequential",
            routing_overrides={
                "local-agent": {
                    "preferred_role": "gpu",
                    "preferred_provider": "mistral",
                    "preferred_model": "mistral-large-latest",
                }
            },
        )
    )

    assert len(router.calls) == 1
    assert router.calls[0]["provider"] == "mistral"
    assert router.calls[0]["model"] == "mistral-large-latest"
    assert run.results[0].remote is False
    assert run.results[0].response.provider == "mistral"
    assert run.results[0].response.model == "mistral-large-latest"


def test_skip_on_error_sequential():
    """Test sequential mode continues after agent failure when skip_on_error=True."""
    from mascarade.orchestrator.retry import RetryConfig

    router = Router()
    router._providers.clear()
    router.register(MockProvider())
    router.register(FailingProvider())

    registry = AgentRegistry()
    registry.register(
        Agent(
            name="good1",
            description="Good",
            system_prompt="Good.",
            preferred_provider="mock",
        )
    )
    registry.register(
        Agent(
            name="bad",
            description="Bad",
            system_prompt="Bad.",
            strategy="specific",
            preferred_provider="failing",
            preferred_model="failing-model",
        )
    )
    registry.register(
        Agent(
            name="good2",
            description="Good",
            system_prompt="Good.",
            preferred_provider="mock",
        )
    )

    # Configure retry executor with 0 retries for faster tests
    from mascarade.orchestrator.retry import RetryExecutor

    retry_executor = RetryExecutor(config=RetryConfig(max_retries=0))

    orch = Orchestrator(
        router=router,
        registry=registry,
        trace_buffer=AgentTraceBuffer(),
        retry_executor=retry_executor,
    )

    run = asyncio.run(
        orch.run(
            ["good1", "bad", "good2"], "test", mode="sequential", skip_on_error=True
        )
    )

    # Should have 3 results: 2 successful, 1 failed
    assert len(run.results) == 3
    assert run.results[0].agent_name == "good1"
    assert run.results[0].error is None
    assert run.results[1].agent_name == "bad"
    assert run.results[1].error is not None
    assert "Simulated agent failure" in run.results[1].error
    assert run.results[2].agent_name == "good2"
    assert run.results[2].error is None


def test_sequential_stops_on_error_by_default():
    """Test sequential mode stops on first error when skip_on_error=False (default)."""
    from mascarade.orchestrator.retry import RetryConfig, RetryExecutor

    router = Router()
    router._providers.clear()
    router.register(MockProvider())
    router.register(FailingProvider())

    registry = AgentRegistry()
    registry.register(
        Agent(
            name="good1",
            description="Good",
            system_prompt="Good.",
            preferred_provider="mock",
        )
    )
    registry.register(
        Agent(
            name="bad",
            description="Bad",
            system_prompt="Bad.",
            strategy="specific",
            preferred_provider="failing",
            preferred_model="failing-model",
        )
    )
    registry.register(
        Agent(
            name="good2",
            description="Good",
            system_prompt="Good.",
            preferred_provider="mock",
        )
    )

    retry_executor = RetryExecutor(config=RetryConfig(max_retries=0))

    orch = Orchestrator(
        router=router,
        registry=registry,
        trace_buffer=AgentTraceBuffer(),
        retry_executor=retry_executor,
    )

    run = asyncio.run(
        orch.run(
            ["good1", "bad", "good2"], "test", mode="sequential", skip_on_error=False
        )
    )

    # Should have 2 results: 1 successful, 1 failed, and stop before good2
    assert len(run.results) == 2
    assert run.results[0].agent_name == "good1"
    assert run.results[0].error is None
    assert run.results[1].agent_name == "bad"
    assert run.results[1].error is not None
    assert "Simulated agent failure" in run.results[1].error


def test_skip_on_error_pipeline():
    """Test pipeline mode continues after agent failure when skip_on_error=True."""
    from mascarade.orchestrator.retry import RetryConfig, RetryExecutor

    router = Router()
    router._providers.clear()
    router.register(MockProvider())
    router.register(FailingProvider())

    registry = AgentRegistry()
    registry.register(
        Agent(
            name="good1",
            description="Good",
            system_prompt="Good.",
            preferred_provider="mock",
        )
    )
    registry.register(
        Agent(
            name="bad",
            description="Bad",
            system_prompt="Bad.",
            strategy="specific",
            preferred_provider="failing",
            preferred_model="failing-model",
        )
    )
    registry.register(
        Agent(
            name="good2",
            description="Good",
            system_prompt="Good.",
            preferred_provider="mock",
        )
    )

    retry_executor = RetryExecutor(config=RetryConfig(max_retries=0))

    orch = Orchestrator(
        router=router,
        registry=registry,
        trace_buffer=AgentTraceBuffer(),
        retry_executor=retry_executor,
    )

    run = asyncio.run(
        orch.run(
            ["good1", "bad", "good2"], "initial", mode="pipeline", skip_on_error=True
        )
    )

    # Should have 3 results: good1 succeeds, bad fails, good2 succeeds
    assert len(run.results) == 3
    assert run.results[0].agent_name == "good1"
    assert run.results[0].error is None
    assert "[mock] initial" in run.results[0].response.content
    assert run.results[1].agent_name == "bad"
    assert run.results[1].error is not None
    assert run.results[2].agent_name == "good2"
    assert run.results[2].error is None
    # good2 should receive output from good1 (not from bad, which failed)
    assert "[mock]" in run.results[2].response.content


def test_pipeline_stops_on_error_by_default():
    """Test pipeline mode stops on first error when skip_on_error=False (default)."""
    from mascarade.orchestrator.retry import RetryConfig, RetryExecutor

    router = Router()
    router._providers.clear()
    router.register(MockProvider())
    router.register(FailingProvider())

    registry = AgentRegistry()
    registry.register(
        Agent(
            name="good1",
            description="Good",
            system_prompt="Good.",
            preferred_provider="mock",
        )
    )
    registry.register(
        Agent(
            name="bad",
            description="Bad",
            system_prompt="Bad.",
            strategy="specific",
            preferred_provider="failing",
            preferred_model="failing-model",
        )
    )
    registry.register(
        Agent(
            name="good2",
            description="Good",
            system_prompt="Good.",
            preferred_provider="mock",
        )
    )

    retry_executor = RetryExecutor(config=RetryConfig(max_retries=0))

    orch = Orchestrator(
        router=router,
        registry=registry,
        trace_buffer=AgentTraceBuffer(),
        retry_executor=retry_executor,
    )

    run = asyncio.run(
        orch.run(
            ["good1", "bad", "good2"], "initial", mode="pipeline", skip_on_error=False
        )
    )

    # Should have 2 results: good1 succeeds, bad fails, and stop before good2
    assert len(run.results) == 2
    assert run.results[0].agent_name == "good1"
    assert run.results[0].error is None
    assert run.results[1].agent_name == "bad"
    assert run.results[1].error is not None


def test_parallel_returns_partial_results():
    """Test parallel mode returns both successful and failed results."""
    from mascarade.orchestrator.retry import RetryConfig, RetryExecutor

    router = Router()
    router._providers.clear()
    router.register(MockProvider())
    router.register(FailingProvider())

    registry = AgentRegistry()
    registry.register(
        Agent(
            name="good1",
            description="Good",
            system_prompt="Good.",
            preferred_provider="mock",
        )
    )
    registry.register(
        Agent(
            name="bad",
            description="Bad",
            system_prompt="Bad.",
            strategy="specific",
            preferred_provider="failing",
            preferred_model="failing-model",
        )
    )
    registry.register(
        Agent(
            name="good2",
            description="Good",
            system_prompt="Good.",
            preferred_provider="mock",
        )
    )

    retry_executor = RetryExecutor(config=RetryConfig(max_retries=0))

    orch = Orchestrator(
        router=router,
        registry=registry,
        trace_buffer=AgentTraceBuffer(),
        retry_executor=retry_executor,
    )

    run = asyncio.run(orch.run(["good1", "bad", "good2"], "test", mode="parallel"))

    # Should have 3 results: 2 successful, 1 failed
    assert len(run.results) == 3

    # Check we have both successes and failures
    good_results = [r for r in run.results if r.error is None]
    bad_results = [r for r in run.results if r.error is not None]

    assert len(good_results) == 2
    assert len(bad_results) == 1

    good_names = {r.agent_name for r in good_results}
    bad_names = {r.agent_name for r in bad_results}

    assert good_names == {"good1", "good2"}
    assert bad_names == {"bad"}
    assert "Simulated agent failure" in bad_results[0].error


def test_error_details_in_task_result():
    """Test that error information is properly recorded in TaskResult."""
    from mascarade.orchestrator.retry import RetryConfig, RetryExecutor

    router = Router()
    router._providers.clear()
    router.register(FailingProvider())

    registry = AgentRegistry()
    registry.register(
        Agent(
            name="bad",
            description="Bad",
            system_prompt="Bad.",
            strategy="specific",
            preferred_provider="failing",
            preferred_model="failing-model",
        )
    )

    retry_executor = RetryExecutor(config=RetryConfig(max_retries=0))

    orch = Orchestrator(
        router=router,
        registry=registry,
        trace_buffer=AgentTraceBuffer(),
        retry_executor=retry_executor,
    )

    run = asyncio.run(orch.run(["bad"], "test", mode="sequential", skip_on_error=True))

    assert len(run.results) == 1
    result = run.results[0]

    # Verify error is recorded
    assert result.error is not None
    assert "Simulated agent failure" in result.error
    assert result.agent_name == "bad"

    # Verify response fields are present but empty for failed agents
    assert result.response.content == ""
    assert result.response.model == ""
    assert result.response.provider == ""


def test_dead_letter_store_records_failures():
    """Test that failed orchestrations are recorded in dead letter store."""
    from mascarade.orchestrator.retry import RetryConfig, RetryExecutor

    router = Router()
    router._providers.clear()
    router.register(FailingProvider())

    registry = AgentRegistry()
    registry.register(
        Agent(
            name="bad",
            description="Bad",
            system_prompt="Bad.",
            strategy="specific",
            preferred_provider="failing",
            preferred_model="failing-model",
        )
    )

    retry_executor = RetryExecutor(config=RetryConfig(max_retries=0))

    orch = Orchestrator(
        router=router,
        registry=registry,
        trace_buffer=AgentTraceBuffer(),
        retry_executor=retry_executor,
    )

    run = asyncio.run(orch.run(["bad"], "test", mode="sequential", skip_on_error=True))

    # Check dead letter store has the failure
    failures = orch.dead_letter_store.recent()
    assert len(failures) > 0

    # Find failure for this run
    run_failures = [f for f in failures if f.run_id == run.run_id]
    assert len(run_failures) > 0

    failure = run_failures[0]
    assert failure.agent_name == "bad"
    assert "Simulated agent failure" in failure.error
    assert failure.mode == "sequential"


def test_fallback_agent_fields_in_task_result():
    """Test that fallback_used and fallback_agent fields exist in TaskResult."""
    orch = _make_orchestrator()
    run = asyncio.run(orch.run(["analyst"], "test", mode="sequential"))

    assert len(run.results) == 1
    result = run.results[0]

    # Verify fallback fields exist and have default values
    assert hasattr(result, "fallback_used")
    assert hasattr(result, "fallback_agent")
    assert result.fallback_used is False
    assert result.fallback_agent is None


def test_pipeline_fallback_agent_success():
    """Test that fallback agent is used when primary agent fails."""
    from mascarade.orchestrator.retry import RetryConfig, RetryExecutor

    router = Router()
    router._providers.clear()
    router.register(MockProvider())
    router.register(FailingProvider())

    registry = AgentRegistry()
    # Primary agent that will fail
    registry.register(
        Agent(
            name="primary",
            description="Primary agent that fails",
            system_prompt="You are primary",
            strategy="specific",
            preferred_provider="failing",
            preferred_model="failing-model",
        )
    )
    # Fallback agent that will succeed
    registry.register(
        Agent(
            name="fallback",
            description="Fallback agent that works",
            system_prompt="You are fallback",
            preferred_provider="mock",
        )
    )

    retry_executor = RetryExecutor(config=RetryConfig(max_retries=0))

    orch = Orchestrator(
        router=router,
        registry=registry,
        trace_buffer=AgentTraceBuffer(),
        retry_executor=retry_executor,
    )

    # Run pipeline with fallback configuration
    run = asyncio.run(
        orch.run(
            ["primary"],
            "test prompt",
            mode="pipeline",
            fallback_map={"primary": "fallback"},
        )
    )

    assert len(run.results) == 1
    result = run.results[0]

    # Verify fallback was used
    assert result.fallback_used is True
    assert result.fallback_agent == "fallback"
    assert "[mock]" in result.response.content
    assert result.error is None
    # Agent name should be the fallback agent name
    assert result.agent_name == "fallback"


def test_pipeline_fallback_agent_both_fail():
    """Test that pipeline fails when both primary and fallback fail."""
    from mascarade.orchestrator.retry import RetryConfig, RetryExecutor

    router = Router()
    router._providers.clear()
    router.register(FailingProvider())

    registry = AgentRegistry()
    # Both agents will fail
    registry.register(
        Agent(
            name="primary",
            description="Primary agent that fails",
            system_prompt="You are primary",
            strategy="specific",
            preferred_provider="failing",
            preferred_model="failing-model",
        )
    )
    registry.register(
        Agent(
            name="fallback",
            description="Fallback agent that also fails",
            system_prompt="You are fallback",
            strategy="specific",
            preferred_provider="failing",
            preferred_model="failing-model",
        )
    )

    retry_executor = RetryExecutor(config=RetryConfig(max_retries=0))

    orch = Orchestrator(
        router=router,
        registry=registry,
        trace_buffer=AgentTraceBuffer(),
        retry_executor=retry_executor,
    )

    # Run should produce an error result
    run = asyncio.run(
        orch.run(
            ["primary"],
            "test prompt",
            mode="pipeline",
            fallback_map={"primary": "fallback"},
            skip_on_error=True,  # Allow run to complete despite errors
        )
    )

    # Verify we got an error result
    assert len(run.results) == 1
    result = run.results[0]
    assert result.error is not None
    # Error message should mention both failures
    assert "Primary agent 'primary' failed" in result.error
    assert "Fallback agent 'fallback' also failed" in result.error


def test_pipeline_fallback_agent_not_configured():
    """Test that pipeline fails normally when no fallback is configured."""
    from mascarade.orchestrator.retry import RetryConfig, RetryExecutor

    router = Router()
    router._providers.clear()
    router.register(FailingProvider())

    registry = AgentRegistry()
    registry.register(
        Agent(
            name="failing_agent",
            description="Agent that fails",
            system_prompt="You are failing",
            strategy="specific",
            preferred_provider="failing",
            preferred_model="failing-model",
        )
    )

    retry_executor = RetryExecutor(config=RetryConfig(max_retries=0))

    orch = Orchestrator(
        router=router,
        registry=registry,
        trace_buffer=AgentTraceBuffer(),
        retry_executor=retry_executor,
    )

    # Run without fallback_map should produce error result
    run = asyncio.run(
        orch.run(
            ["failing_agent"],
            "test prompt",
            mode="pipeline",
            fallback_map=None,  # No fallback
            skip_on_error=True,  # Allow run to complete despite errors
        )
    )

    assert len(run.results) == 1
    result = run.results[0]
    assert result.error is not None
    assert "Simulated agent failure" in result.error
    # Should NOT use fallback
    assert result.fallback_used is False
    assert result.fallback_agent is None


def test_pipeline_fallback_trace_event_emitted():
    """Test that fallback_triggered trace event is emitted."""
    from mascarade.orchestrator.retry import RetryConfig, RetryExecutor

    router = Router()
    router._providers.clear()
    router.register(MockProvider())
    router.register(FailingProvider())

    registry = AgentRegistry()
    registry.register(
        Agent(
            name="primary",
            description="Primary agent that fails",
            system_prompt="You are primary",
            strategy="specific",
            preferred_provider="failing",
            preferred_model="failing-model",
        )
    )
    registry.register(
        Agent(
            name="fallback",
            description="Fallback agent that works",
            system_prompt="You are fallback",
            preferred_provider="mock",
        )
    )

    retry_executor = RetryExecutor(config=RetryConfig(max_retries=0))

    orch = Orchestrator(
        router=router,
        registry=registry,
        trace_buffer=AgentTraceBuffer(),
        retry_executor=retry_executor,
    )

    run = asyncio.run(
        orch.run(
            ["primary"],
            "test prompt",
            mode="pipeline",
            fallback_map={"primary": "fallback"},
        )
    )

    # Check trace buffer for fallback_triggered event
    events = orch.trace_buffer.run_events(run.run_id)
    event_types = [event.event_type for event in events]

    assert "fallback_triggered" in event_types

    # Find the fallback event
    fallback_events = [e for e in events if e.event_type == "fallback_triggered"]
    assert len(fallback_events) > 0

    fallback_event = fallback_events[0]
    assert fallback_event.agent_name == "primary"
    assert "fallback" in fallback_event.error.lower()
