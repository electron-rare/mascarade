"""Tests pour les agents et le registre."""

from mascarade.agents.base import Agent
from mascarade.agents.registry import AgentRegistry


def test_registry_register_and_get():
    reg = AgentRegistry()
    agent = Agent(name="test", description="A test agent", system_prompt="You are a test.")
    reg.register(agent)
    assert reg.get("test") is agent
    assert len(reg) == 1


def test_registry_list():
    reg = AgentRegistry()
    reg.register(Agent(name="a", description="Agent A", system_prompt="A"))
    reg.register(Agent(name="b", description="Agent B", system_prompt="B"))
    assert len(reg.list()) == 2


def test_registry_contains():
    reg = AgentRegistry()
    reg.register(Agent(name="x", description="X", system_prompt="X"))
    assert "x" in reg
    assert "y" not in reg


def test_registry_remove():
    reg = AgentRegistry()
    reg.register(Agent(name="rm", description="Remove me", system_prompt="RM"))
    reg.remove("rm")
    assert "rm" not in reg


def test_registry_get_missing():
    reg = AgentRegistry()
    try:
        reg.get("missing")
        assert False, "Should have raised KeyError"
    except KeyError:
        pass
