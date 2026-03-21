"""Comprehensive tests for the orchestrator engine module."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mascarade.agents.base import Agent
from mascarade.agents.registry import AgentRegistry
from mascarade.observability import AgentTraceBuffer
from mascarade.orchestrator.engine import (
    ExecutionMode,
    OrchestrationRun,
    Orchestrator,
    TaskResult,
)
from mascarade.orchestrator.retry import RetryConfig, RetryExecutor
from mascarade.router.providers.base import LLMResponse


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class RecordingRouter:
    """Router mock that records calls and returns predictable responses."""

    def __init__(self, prefix: str = "mock"):
        self.calls: list[dict] = []
        self._prefix = prefix

    async def send(self, messages, **kwargs):
        self.calls.append({"messages": messages, **kwargs})
        content = messages[-1]["content"] if messages else ""
        return LLMResponse(
            content=f"[{self._prefix}] {content}",
            model=kwargs.get("model") or "mock-model",
            provider=kwargs.get("provider") or "mock",
            usage={"input_tokens": 2, "output_tokens": 5},
        )


def _make_registry(*names: str) -> AgentRegistry:
    registry = AgentRegistry(storage_path=None)
    for name in names:
        registry.register(
            Agent(name=name, description=f"Agent {name}", system_prompt=f"You are {name}.")
        )
    return registry


def _make_orchestrator(
    agent_names: tuple[str, ...] = ("analyst", "writer"),
    router: RecordingRouter | None = None,
) -> Orchestrator:
    router = router or RecordingRouter()
    registry = _make_registry(*agent_names)
    return Orchestrator(
        router=router,  # type: ignore[arg-type]
        registry=registry,
        trace_buffer=AgentTraceBuffer(),
        retry_executor=RetryExecutor(config=RetryConfig(max_retries=0)),
    )


# ---------------------------------------------------------------------------
# ExecutionMode enum
# ---------------------------------------------------------------------------


class TestExecutionMode:
    def test_sequential_value(self):
        assert ExecutionMode.SEQUENTIAL == "sequential"

    def test_parallel_value(self):
        assert ExecutionMode.PARALLEL == "parallel"

    def test_pipeline_value(self):
        assert ExecutionMode.PIPELINE == "pipeline"

    def test_from_string(self):
        assert ExecutionMode("sequential") is ExecutionMode.SEQUENTIAL
        assert ExecutionMode("parallel") is ExecutionMode.PARALLEL
        assert ExecutionMode("pipeline") is ExecutionMode.PIPELINE

    def test_invalid_mode_raises(self):
        with pytest.raises(ValueError):
            ExecutionMode("invalid_mode")


# ---------------------------------------------------------------------------
# TaskResult dataclass
# ---------------------------------------------------------------------------


class TestTaskResult:
    def test_creation_minimal(self):
        resp = LLMResponse(content="ok", model="m", provider="p")
        tr = TaskResult(agent_name="a", response=resp)
        assert tr.agent_name == "a"
        assert tr.response.content == "ok"

    def test_defaults(self):
        resp = LLMResponse(content="ok", model="m", provider="p")
        tr = TaskResult(agent_name="a", response=resp)
        assert tr.step == 0
        assert tr.error is None
        assert tr.remote is False
        assert tr.selected_by == "local-direct"
        assert tr.peer_id is None
        assert tr.node_id is None
        assert tr.role is None
        assert tr.transport is None
        assert tr.latency_ms is None
        assert tr.fallback_used is False
        assert tr.fallback_agent is None

    def test_creation_with_all_fields(self):
        resp = LLMResponse(content="ok", model="m", provider="p")
        tr = TaskResult(
            agent_name="a",
            response=resp,
            step=3,
            error="oops",
            remote=True,
            selected_by="cluster",
            peer_id="peer1",
            node_id="node1",
            role="gpu",
            transport="p2p",
            latency_ms=42,
            fallback_used=True,
            fallback_agent="backup",
        )
        assert tr.step == 3
        assert tr.error == "oops"
        assert tr.remote is True
        assert tr.fallback_agent == "backup"


# ---------------------------------------------------------------------------
# OrchestrationRun dataclass
# ---------------------------------------------------------------------------


class TestOrchestrationRun:
    def test_creation(self):
        run = OrchestrationRun(run_id="abc", mode=ExecutionMode.SEQUENTIAL, results=[])
        assert run.run_id == "abc"
        assert run.mode == ExecutionMode.SEQUENTIAL
        assert run.results == []


# ---------------------------------------------------------------------------
# Orchestrator initialization
# ---------------------------------------------------------------------------


class TestOrchestratorInit:
    def test_default_trace_buffer(self):
        """__post_init__ creates a trace buffer if none is provided."""
        orch = Orchestrator()
        assert orch.trace_buffer is not None

    def test_explicit_trace_buffer_preserved(self):
        buf = AgentTraceBuffer()
        orch = Orchestrator(trace_buffer=buf)
        assert orch.trace_buffer is buf


# ---------------------------------------------------------------------------
# Sequential execution
# ---------------------------------------------------------------------------


class TestSequentialExecution:
    async def test_basic_sequential(self):
        orch = _make_orchestrator()
        run = await orch.run(["analyst", "writer"], "hello", mode="sequential")
        assert run.mode == ExecutionMode.SEQUENTIAL
        assert len(run.results) == 2
        assert run.results[0].agent_name == "analyst"
        assert run.results[1].agent_name == "writer"
        # Each agent receives the original prompt
        assert "[mock] hello" in run.results[0].response.content
        assert "[mock] hello" in run.results[1].response.content

    async def test_sequential_records_traces(self):
        orch = _make_orchestrator()
        run = await orch.run(["analyst"], "trace me", mode="sequential")
        events = orch.trace_buffer.run_events(run.run_id)
        event_types = {e.event_type for e in events}
        assert "run_started" in event_types
        assert "agent_input" in event_types
        assert "agent_output" in event_types
        assert "run_completed" in event_types


# ---------------------------------------------------------------------------
# Parallel execution
# ---------------------------------------------------------------------------


class TestParallelExecution:
    async def test_basic_parallel(self):
        orch = _make_orchestrator()
        run = await orch.run(["analyst", "writer"], "parallel", mode="parallel")
        assert run.mode == ExecutionMode.PARALLEL
        assert len(run.results) == 2
        names = {r.agent_name for r in run.results}
        assert names == {"analyst", "writer"}

    async def test_parallel_all_receive_same_prompt(self):
        router = RecordingRouter()
        orch = _make_orchestrator(router=router)
        await orch.run(["analyst", "writer"], "same prompt", mode="parallel")
        for call in router.calls:
            assert call["messages"][-1]["content"] == "same prompt"


# ---------------------------------------------------------------------------
# Pipeline execution
# ---------------------------------------------------------------------------


class TestPipelineExecution:
    async def test_pipeline_chains_output(self):
        orch = _make_orchestrator()
        run = await orch.run(["analyst", "writer"], "start", mode="pipeline")
        assert len(run.results) == 2
        # Second agent receives output of first
        assert "[mock]" in run.results[1].response.content
        # The input to writer should contain the output of analyst
        first_output = run.results[0].response.content
        assert first_output in run.results[1].response.content

    async def test_pipeline_handoff_trace(self):
        orch = _make_orchestrator()
        run = await orch.run(["analyst", "writer"], "go", mode="pipeline")
        events = orch.trace_buffer.run_events(run.run_id)
        event_types = [e.event_type for e in events]
        assert "handoff" in event_types


# ---------------------------------------------------------------------------
# Agent not found
# ---------------------------------------------------------------------------


class TestAgentNotFound:
    async def test_unknown_agent_raises_key_error(self):
        orch = _make_orchestrator()
        with pytest.raises(KeyError, match="non_existent"):
            await orch.run(["non_existent"], "test", mode="sequential")


# ---------------------------------------------------------------------------
# Empty agent list
# ---------------------------------------------------------------------------


class TestEmptyAgentList:
    async def test_empty_list_sequential(self):
        orch = _make_orchestrator()
        run = await orch.run([], "test", mode="sequential")
        assert run.results == []

    async def test_empty_list_parallel(self):
        orch = _make_orchestrator()
        run = await orch.run([], "test", mode="parallel")
        assert run.results == []

    async def test_empty_list_pipeline(self):
        orch = _make_orchestrator()
        run = await orch.run([], "test", mode="pipeline")
        assert run.results == []


# ---------------------------------------------------------------------------
# Routing overrides
# ---------------------------------------------------------------------------


class TestRoutingOverrides:
    async def test_override_provider_and_model(self):
        router = RecordingRouter()
        orch = _make_orchestrator(router=router)
        await orch.run(
            ["analyst"],
            "override test",
            mode="sequential",
            routing_overrides={
                "analyst": {
                    "preferred_provider": "mistral",
                    "preferred_model": "mistral-large",
                }
            },
        )
        assert len(router.calls) == 1
        assert router.calls[0]["provider"] == "mistral"
        assert router.calls[0]["model"] == "mistral-large"

    async def test_override_routing_policy(self):
        router = RecordingRouter()
        orch = _make_orchestrator(router=router)
        await orch.run(
            ["analyst"],
            "policy test",
            mode="sequential",
            routing_overrides={
                "analyst": {"routing_policy": "strong"}
            },
        )
        assert router.calls[0]["routing_policy"] == "strong"

    async def test_override_traces_include_routing_info(self):
        orch = _make_orchestrator()
        run = await orch.run(
            ["analyst"],
            "trace override",
            mode="sequential",
            routing_overrides={
                "analyst": {
                    "preferred_role": "gpu",
                    "preferred_provider": "ollama",
                    "preferred_model": "llama3",
                }
            },
        )
        events = orch.trace_buffer.run_events(run.run_id)
        input_event = next(e for e in events if e.event_type == "agent_input")
        assert input_event.routing_role == "gpu"
        assert input_event.routing_provider == "ollama"
        assert input_event.routing_model == "llama3"


# ---------------------------------------------------------------------------
# Skill registry integration
# ---------------------------------------------------------------------------


class TestSkillRegistryIntegration:
    async def test_skill_registry_passed_to_build_send_payload(self):
        """Verify the orchestrator passes skill_registry when building payloads."""
        fake_skill_registry = MagicMock()
        router = RecordingRouter()
        registry = AgentRegistry(storage_path=None)

        agent = Agent(
            name="skilled",
            description="Agent with skills",
            system_prompt="base prompt",
            skills=["skill_a"],
        )
        registry.register(agent)

        orch = Orchestrator(
            router=router,  # type: ignore[arg-type]
            registry=registry,
            trace_buffer=AgentTraceBuffer(),
            skill_registry=fake_skill_registry,
            retry_executor=RetryExecutor(config=RetryConfig(max_retries=0)),
        )

        # Patch build_send_payload to verify skill_registry is passed
        original = agent.build_send_payload
        calls = []

        def tracking_build(prompt, *, context=None, skill_registry=None):
            calls.append(skill_registry)
            return original(prompt, context=context, skill_registry=skill_registry)

        agent.build_send_payload = tracking_build  # type: ignore[assignment]

        await orch.run(["skilled"], "test", mode="sequential")

        assert len(calls) == 1
        assert calls[0] is fake_skill_registry
