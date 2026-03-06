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

    return Orchestrator(router=router, registry=registry, trace_buffer=AgentTraceBuffer())


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
