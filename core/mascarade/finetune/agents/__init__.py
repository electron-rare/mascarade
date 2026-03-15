"""Fine-tuning agents — specialized roles for the distributed pipeline."""

from mascarade.finetune.agents.researcher import ResearcherAgent
from mascarade.finetune.agents.documentalist import DocumentalistAgent

__all__ = ["ResearcherAgent", "DocumentalistAgent"]
