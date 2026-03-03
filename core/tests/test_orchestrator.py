"""Tests pour l'orchestrateur."""

from mascarade.agents.base import Agent
from mascarade.agents.registry import AgentRegistry
from mascarade.orchestrator.engine import Orchestrator, ExecutionMode
from mascarade.router.router import Router
from mascarade.router.providers.base import LLMProvider, LLMResponse


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
    registry.register(Agent(name="analyst", description="Analyzes", system_prompt="Analyze."))
    registry.register(Agent(name="writer", description="Writes", system_prompt="Write."))

    return Orchestrator(router=router, registry=registry)


async def test_sequential():
    orch = _make_orchestrator()
    results = await orch.run(["analyst", "writer"], "test", mode="sequential")
    assert len(results) == 2
    assert results[0].agent_name == "analyst"
    assert results[1].agent_name == "writer"


async def test_parallel():
    orch = _make_orchestrator()
    results = await orch.run(["analyst", "writer"], "test", mode="parallel")
    assert len(results) == 2
    agent_names = {r.agent_name for r in results}
    assert agent_names == {"analyst", "writer"}


async def test_pipeline():
    orch = _make_orchestrator()
    results = await orch.run(["analyst", "writer"], "start", mode="pipeline")
    assert len(results) == 2
    # Pipeline: output of first becomes input of second
    assert "[mock]" in results[1].response.content
