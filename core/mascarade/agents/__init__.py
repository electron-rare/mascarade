from mascarade.agents.base import Agent
from mascarade.agents.components_agent import ComponentsAgent
from mascarade.agents.freecad_agent import FreeCADAgent
from mascarade.agents.kicad_agent import KiCadAgent
from mascarade.agents.registry import AgentRegistry
from mascarade.agents.skill import Skill
from mascarade.agents.skill_registry import SkillRegistry
from mascarade.agents.skills import ALL_SKILLS, register_default_skills, register_default_skills_v2
from mascarade.agents.spice_agent import SpiceAgent

try:
    from mascarade.agents.kicad_happy_agent import KiCadHappyAgent
except ImportError:
    KiCadHappyAgent = None  # type: ignore[assignment,misc]

__all__ = [
    "Agent",
    "AgentRegistry",
    "ALL_SKILLS",
    "register_default_skills",
    "register_default_skills_v2",
    "Skill",
    "SkillRegistry",
    "FreeCADAgent",
    "SpiceAgent",
    "KiCadAgent",
    "ComponentsAgent",
    "KiCadHappyAgent",
]
