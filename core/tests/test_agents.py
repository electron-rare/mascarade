"""Tests pour les agents et le registre."""

from mascarade.agents.base import Agent
from mascarade.agents.registry import AgentRegistry


def test_registry_register_and_get():
    reg = AgentRegistry(storage_path=None)
    agent = Agent(
        name="test", description="A test agent", system_prompt="You are a test."
    )
    reg.register(agent)
    assert reg.get("test") is agent
    assert len(reg) == 1


def test_registry_list():
    reg = AgentRegistry(storage_path=None)
    reg.register(Agent(name="a", description="Agent A", system_prompt="A"))
    reg.register(Agent(name="b", description="Agent B", system_prompt="B"))
    assert len(reg.list()) == 2


def test_registry_contains():
    reg = AgentRegistry(storage_path=None)
    reg.register(Agent(name="x", description="X", system_prompt="X"))
    assert "x" in reg
    assert "y" not in reg


def test_registry_remove():
    reg = AgentRegistry(storage_path=None)
    reg.register(Agent(name="rm", description="Remove me", system_prompt="RM"))
    reg.remove("rm")
    assert "rm" not in reg


def test_registry_get_missing():
    reg = AgentRegistry(storage_path=None)
    try:
        reg.get("missing")
        assert False, "Should have raised KeyError"
    except KeyError:
        pass


def test_registry_save_and_load(tmp_path):
    """Les agents dynamiques sont persistés et rechargés."""
    storage = tmp_path / "agents.json"

    reg = AgentRegistry(storage_path=storage)
    reg.register(
        Agent(name="builtin", description="B", system_prompt="B"), builtin=True
    )
    reg.register(Agent(name="dynamic", description="D", system_prompt="D"))
    reg.save()

    reg2 = AgentRegistry(storage_path=storage)
    reg2.load()
    assert "dynamic" in reg2
    assert "builtin" not in reg2  # Built-in non persisté


def test_registry_save_noop_when_disabled():
    """Pas d'erreur si storage_path=None."""
    reg = AgentRegistry(storage_path=None)
    reg.register(Agent(name="x", description="X", system_prompt="X"))
    reg.save()  # Ne doit pas lever d'erreur


def test_registry_load_noop_when_no_file(tmp_path):
    """Pas d'erreur si le fichier n'existe pas."""
    storage = tmp_path / "nonexistent.json"
    reg = AgentRegistry(storage_path=storage)
    reg.load()  # Ne doit pas lever d'erreur
    assert len(reg) == 0
