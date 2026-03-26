"""Tests for agent delegation, capabilities, and cluster system."""

from __future__ import annotations

import pytest

from mascarade.agents.base import Agent
from mascarade.agents.registry import AgentRegistry
from mascarade.router.router import Strategy


def _agent(name: str, **kw) -> Agent:
    defaults = {
        "description": f"Agent {name}",
        "system_prompt": f"You are {name}.",
        "strategy": Strategy.BEST,
    }
    defaults.update(kw)
    return Agent(name=name, **defaults)


@pytest.fixture
def registry():
    r = AgentRegistry(storage_path=None)
    r.register(_agent("coder", capabilities=["code", "debug", "review"], cluster="code"))
    r.register(_agent("writer", capabilities=["text", "email", "redaction"], cluster="general"))
    r.register(_agent("kicad", capabilities=["pcb", "schematic", "drc"], cluster="electronics"))
    r.register(
        _agent("spice", capabilities=["simulation", "netlist", "spice"], cluster="electronics")
    )
    r.register(_agent("analyst", capabilities=["data", "kpi", "analysis"], cluster="ops"))
    r.register(
        _agent("planner", capabilities=["planning", "decompose", "roadmap"], cluster="general")
    )
    return r


class TestCapabilities:
    def test_find_by_capability(self, registry):
        agents = registry.find_by_capability("pcb")
        assert len(agents) == 1
        assert agents[0].name == "kicad"

    def test_find_by_capability_multiple(self, registry):
        agents = registry.find_by_capability("code")
        assert len(agents) == 1
        assert agents[0].name == "coder"

    def test_find_by_capability_none(self, registry):
        agents = registry.find_by_capability("nonexistent")
        assert agents == []


class TestClusters:
    def test_find_by_cluster(self, registry):
        electronics = registry.find_by_cluster("electronics")
        assert len(electronics) == 2
        names = {a.name for a in electronics}
        assert names == {"kicad", "spice"}

    def test_find_by_cluster_general(self, registry):
        general = registry.find_by_cluster("general")
        assert len(general) == 2

    def test_clusters_returns_groups(self, registry):
        groups = registry.clusters()
        assert "electronics" in groups
        assert "code" in groups
        assert "general" in groups
        assert "ops" in groups
        assert len(groups["electronics"]) == 2


class TestFindBestFor:
    def test_finds_coder_for_code_task(self, registry):
        agent = registry.find_best_for("debug this python code")
        assert agent is not None
        assert agent.name == "coder"

    def test_finds_kicad_for_pcb_task(self, registry):
        agent = registry.find_best_for("review my PCB schematic for DRC errors")
        assert agent is not None
        assert agent.name == "kicad"

    def test_finds_analyst_for_data_task(self, registry):
        agent = registry.find_best_for("analyse les KPI de performance")
        assert agent is not None
        assert agent.name == "analyst"

    def test_finds_writer_for_email(self, registry):
        agent = registry.find_best_for("redige un email de prospection")
        assert agent is not None
        assert agent.name == "writer"

    def test_returns_none_for_no_match(self):
        empty = AgentRegistry(storage_path=None)
        assert empty.find_best_for("anything") is None


class TestAgentFields:
    def test_capabilities_field(self):
        a = _agent("test", capabilities=["a", "b"])
        assert a.capabilities == ["a", "b"]

    def test_cluster_field(self):
        a = _agent("test", cluster="electronics")
        assert a.cluster == "electronics"

    def test_defaults_empty(self):
        a = _agent("test")
        assert a.capabilities == []
        assert a.cluster is None
