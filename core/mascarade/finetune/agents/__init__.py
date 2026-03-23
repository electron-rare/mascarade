"""Fine-tuning agents — specialized roles for the distributed pipeline."""

from mascarade.finetune.agents.documentalist import DocumentalistAgent
from mascarade.finetune.agents.researcher import ResearcherAgent

__all__ = ["ResearcherAgent", "DocumentalistAgent"]
