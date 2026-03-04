"""Tests pour les skills pré-construits."""

from mascarade.agents.registry import AgentRegistry
from mascarade.agents.skills import ALL_SKILLS, register_default_skills


def test_all_skills_have_unique_names():
    names = [s.name for s in ALL_SKILLS]
    assert len(names) == len(set(names)), f"Noms dupliqués: {names}"


def test_register_default_skills():
    reg = AgentRegistry()
    register_default_skills(reg)
    assert len(reg) == len(ALL_SKILLS)


def test_all_skills_accessible_by_name():
    reg = AgentRegistry()
    register_default_skills(reg)
    for skill in ALL_SKILLS:
        assert skill.name in reg
        assert reg.get(skill.name) is skill


def test_skills_have_required_fields():
    for skill in ALL_SKILLS:
        assert skill.name, f"Skill sans nom: {skill}"
        assert skill.description, f"{skill.name} sans description"
        assert skill.system_prompt, f"{skill.name} sans system_prompt"
        assert 0.0 <= skill.temperature <= 2.0, f"{skill.name} température invalide"
        assert skill.max_tokens > 0, f"{skill.name} max_tokens invalide"


def test_expected_skills_present():
    names = {s.name for s in ALL_SKILLS}
    expected = {
        "summarizer",
        "writer",
        "coder",
        "translator",
        "analyst",
        "brainstorm",
        "notion-scribe",
        "planner",
        "classifier",
        "image-generator",
    }
    assert expected == names
