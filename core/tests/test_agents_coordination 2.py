"""Tests for the multi-agent coordination engine."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

from mascarade.agents.base import Agent
from mascarade.agents.coordination import (
    CoordinationContext,
    CoordinationEngine,
    CoordinationRequest,
)
from mascarade.agents.registry import AgentRegistry
from mascarade.orchestrator.engine import ExecutionMode


def _agent(name: str, *, cluster: str | None = None, capabilities: list[str] | None = None) -> Agent:
    return Agent(
        name=name,
        description=f"Agent {name}",
        system_prompt=f"You are {name}.",
        cluster=cluster,
        capabilities=capabilities or [],
    )


def _registry_with_defaults() -> AgentRegistry:
    registry = AgentRegistry(storage_path=None)
    registry.register(_agent("agent-zero", cluster="general"))
    registry.register(_agent("coder", cluster="code", capabilities=["code", "debug"]))
    registry.register(_agent("kicad", cluster="electronics", capabilities=["pcb"]))
    registry.register(_agent("spice", cluster="electronics", capabilities=["simulation"]))
    registry.register(_agent("ops-monitor", cluster="ops", capabilities=["alerts"]))
    return registry


def _mock_run_result(*names: str) -> SimpleNamespace:
    results = []
    for name in names:
        response = SimpleNamespace(content=f"out-{name}", provider="mock", model="m")
        results.append(SimpleNamespace(agent_name=name, response=response, error=None))
    return SimpleNamespace(results=results)


def test_select_agents_uses_explicit_list_filtered_and_deduped() -> None:
    registry = _registry_with_defaults()
    engine = CoordinationEngine(registry, orchestrator=SimpleNamespace(run=AsyncMock()))

    request = CoordinationRequest(
        task="whatever",
        agent_names=["kicad", "unknown", "kicad", "spice"],
    )

    assert engine.select_agents(request) == ["kicad", "spice"]


def test_select_agents_by_domain_cluster() -> None:
    registry = _registry_with_defaults()
    engine = CoordinationEngine(registry, orchestrator=SimpleNamespace(run=AsyncMock()))

    request = CoordinationRequest(task="review netlist", domain="kicad")

    assert set(engine.select_agents(request)) == {"kicad", "spice"}


def test_select_agents_falls_back_to_best_for_task() -> None:
    registry = _registry_with_defaults()
    engine = CoordinationEngine(registry, orchestrator=SimpleNamespace(run=AsyncMock()))

    request = CoordinationRequest(task="debug this code")

    assert engine.select_agents(request) == ["coder"]


def test_select_agents_falls_back_to_agent_zero_when_no_match() -> None:
    registry = AgentRegistry(storage_path=None)
    registry.register(_agent("agent-zero", cluster="general"))
    engine = CoordinationEngine(registry, orchestrator=SimpleNamespace(run=AsyncMock()))

    request = CoordinationRequest(task="no obvious match")

    assert engine.select_agents(request) == ["agent-zero"]


def test_select_agents_falls_back_to_first_sorted_name_without_agent_zero() -> None:
    registry = AgentRegistry(storage_path=None)
    registry.register(_agent("zzz"))
    registry.register(_agent("aaa"))
    engine = CoordinationEngine(registry, orchestrator=SimpleNamespace(run=AsyncMock()))

    request = CoordinationRequest(task="nothing")

    assert engine.select_agents(request) == ["aaa"]


async def test_run_sequential_delegates_to_orchestrator() -> None:
    registry = _registry_with_defaults()
    orchestrator = SimpleNamespace(run=AsyncMock(return_value=_mock_run_result("coder", "kicad")))
    engine = CoordinationEngine(registry, orchestrator=orchestrator)

    context = CoordinationContext(prompt="build and review")
    result = await engine.run_sequential(["coder", "kicad"], context)

    orchestrator.run.assert_awaited_once()
    _, kwargs = orchestrator.run.call_args
    assert kwargs["mode"] == ExecutionMode.SEQUENTIAL
    assert result.mode == ExecutionMode.SEQUENTIAL
    assert result.agents_used == ["coder", "kicad"]
    assert result.outputs[0]["content"] == "out-coder"


async def test_run_parallel_delegates_to_orchestrator() -> None:
    registry = _registry_with_defaults()
    orchestrator = SimpleNamespace(run=AsyncMock(return_value=_mock_run_result("kicad", "spice")))
    engine = CoordinationEngine(registry, orchestrator=orchestrator)

    context = CoordinationContext(prompt="simulate and verify")
    result = await engine.run_parallel(["kicad", "spice"], context)

    _, kwargs = orchestrator.run.call_args
    assert kwargs["mode"] == ExecutionMode.PARALLEL
    assert result.mode == ExecutionMode.PARALLEL
    assert set(result.agents_used) == {"kicad", "spice"}


async def test_coordinate_uses_sequential_mode() -> None:
    registry = _registry_with_defaults()
    orchestrator = SimpleNamespace(run=AsyncMock(return_value=_mock_run_result("coder")))
    engine = CoordinationEngine(registry, orchestrator=orchestrator)

    request = CoordinationRequest(task="debug", mode=ExecutionMode.SEQUENTIAL)
    context = CoordinationContext(prompt="debug this")
    result = await engine.coordinate(request, context)

    assert result.mode == ExecutionMode.SEQUENTIAL
    _, kwargs = orchestrator.run.call_args
    assert kwargs["mode"] == ExecutionMode.SEQUENTIAL


async def test_coordinate_uses_parallel_mode() -> None:
    registry = _registry_with_defaults()
    orchestrator = SimpleNamespace(run=AsyncMock(return_value=_mock_run_result("kicad", "spice")))
    engine = CoordinationEngine(registry, orchestrator=orchestrator)

    request = CoordinationRequest(task="pcb checks", domain="kicad", mode=ExecutionMode.PARALLEL)
    context = CoordinationContext(prompt="run checks")
    result = await engine.coordinate(request, context)

    assert result.mode == ExecutionMode.PARALLEL
    _, kwargs = orchestrator.run.call_args
    assert kwargs["mode"] == ExecutionMode.PARALLEL


async def test_coordinate_uses_pipeline_mode() -> None:
    registry = _registry_with_defaults()
    orchestrator = SimpleNamespace(run=AsyncMock(return_value=_mock_run_result("coder", "ops-monitor")))
    engine = CoordinationEngine(registry, orchestrator=orchestrator)

    request = CoordinationRequest(task="plan then monitor", mode=ExecutionMode.PIPELINE)
    context = CoordinationContext(prompt="complex task")
    result = await engine.coordinate(request, context)

    assert result.mode == ExecutionMode.PIPELINE
    _, kwargs = orchestrator.run.call_args
    assert kwargs["mode"] == ExecutionMode.PIPELINE


async def test_context_fields_pass_through_to_orchestrator() -> None:
    registry = _registry_with_defaults()
    orchestrator = SimpleNamespace(run=AsyncMock(return_value=_mock_run_result("coder")))
    engine = CoordinationEngine(registry, orchestrator=orchestrator)

    request = CoordinationRequest(task="debug", mode=ExecutionMode.SEQUENTIAL)
    context = CoordinationContext(
        prompt="dbg",
        project_id="p1",
        federation_scope=["tower", "grosmac"],
        knowledge_scope="global",
    )
    await engine.coordinate(request, context)

    _, kwargs = orchestrator.run.call_args
    assert kwargs["project_id"] == "p1"
    assert kwargs["federation_scope"] == ["tower", "grosmac"]
    assert kwargs["knowledge_scope"] == "global"


async def test_coordinate_returns_empty_when_registry_is_empty() -> None:
    registry = AgentRegistry(storage_path=None)
    orchestrator = SimpleNamespace(run=AsyncMock())
    engine = CoordinationEngine(registry, orchestrator=orchestrator)

    request = CoordinationRequest(task="anything", mode=ExecutionMode.SEQUENTIAL)
    result = await engine.coordinate(request, CoordinationContext(prompt="x"))

    assert result.agents_used == []
    assert result.outputs == []
    orchestrator.run.assert_not_awaited()


async def test_coordinate_with_explicit_agents_bypasses_domain_selection() -> None:
    registry = _registry_with_defaults()
    orchestrator = SimpleNamespace(run=AsyncMock(return_value=_mock_run_result("ops-monitor")))
    engine = CoordinationEngine(registry, orchestrator=orchestrator)

    request = CoordinationRequest(
        task="any",
        domain="kicad",
        mode=ExecutionMode.SEQUENTIAL,
        agent_names=["ops-monitor"],
    )
    result = await engine.coordinate(request, CoordinationContext(prompt="x"))

    assert result.agents_used == ["ops-monitor"]


async def test_coordinate_explicit_unknown_agents_returns_empty_without_run() -> None:
    registry = _registry_with_defaults()
    orchestrator = SimpleNamespace(run=AsyncMock())
    engine = CoordinationEngine(registry, orchestrator=orchestrator)

    request = CoordinationRequest(task="x", mode=ExecutionMode.SEQUENTIAL, agent_names=["unknown"])
    result = await engine.coordinate(request, CoordinationContext(prompt="x"))

    assert result.agents_used == []
    orchestrator.run.assert_not_awaited()


def test_to_result_captures_error_field() -> None:
    registry = _registry_with_defaults()
    orchestrator = SimpleNamespace(run=AsyncMock())
    engine = CoordinationEngine(registry, orchestrator=orchestrator)

    response = SimpleNamespace(content="oops", provider="mock", model="m")
    run = SimpleNamespace(results=[SimpleNamespace(agent_name="coder", response=response, error="boom")])
    result = engine._to_result(run, ExecutionMode.SEQUENTIAL)

    assert result.outputs[0]["error"] == "boom"


def test_select_agents_domain_case_insensitive() -> None:
    registry = _registry_with_defaults()
    engine = CoordinationEngine(registry, orchestrator=SimpleNamespace(run=AsyncMock()))

    request = CoordinationRequest(task="run checks", domain="KiCaD")
    assert set(engine.select_agents(request)) == {"kicad", "spice"}


def test_select_agents_unknown_domain_keeps_task_fallback() -> None:
    registry = _registry_with_defaults()
    engine = CoordinationEngine(registry, orchestrator=SimpleNamespace(run=AsyncMock()))

    request = CoordinationRequest(task="debug python", domain="unknown-domain")
    assert engine.select_agents(request) == ["coder"]


def test_select_agents_with_whitespace_domain_uses_task_fallback() -> None:
    registry = _registry_with_defaults()
    engine = CoordinationEngine(registry, orchestrator=SimpleNamespace(run=AsyncMock()))

    request = CoordinationRequest(task="debug python", domain="   ")
    assert engine.select_agents(request) == ["coder"]


def test_select_agents_dedupes_cluster_members() -> None:
    registry = AgentRegistry(storage_path=None)
    registry.register(_agent("agent-zero", cluster="electronics"))
    registry.register(_agent("kicad", cluster="electronics", capabilities=["pcb"]))
    registry.register(_agent("spice", cluster="electronics", capabilities=["simulation"]))
    engine = CoordinationEngine(registry, orchestrator=SimpleNamespace(run=AsyncMock()))

    request = CoordinationRequest(task="pcb", domain="kicad")
    selected = engine.select_agents(request)
    assert selected == ["agent-zero", "kicad", "spice"]


def test_to_result_handles_empty_orchestration_results() -> None:
    registry = _registry_with_defaults()
    engine = CoordinationEngine(registry, orchestrator=SimpleNamespace(run=AsyncMock()))

    run = SimpleNamespace(results=[])
    result = engine._to_result(run, ExecutionMode.SEQUENTIAL)

    assert result.agents_used == []
    assert result.outputs == []
