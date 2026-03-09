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
    assert result.response.provider == "ollama"
    assert result.response.model == "llama3.2:3b"
    assert result.response.content == "[remote:gpu] cluster test"


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
    assert agent_input.routing_role == "gpu"
    assert agent_input.routing_provider == "mistral"
    assert agent_input.routing_model == "mistral-large-latest"


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
