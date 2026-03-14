"""Système de templates pour orchestrations multi-agents."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class ExecutionMode(StrEnum):
    """Mode d'exécution pour l'orchestration."""

    SEQUENTIAL = "sequential"
    PARALLEL = "parallel"
    PIPELINE = "pipeline"


class WorkflowTemplate(BaseModel):
    """Template de workflow orchestré — définit une pipeline réutilisable."""

    id: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=200)
    description: str = Field(max_length=1000)
    agent_names: list[str] = Field(min_length=1, max_length=20)
    mode: ExecutionMode = ExecutionMode.SEQUENTIAL
    routing_overrides: dict[str, dict[str, str | None]] | None = Field(default=None)
    documentation: str = Field(max_length=5000)

    class Config:
        use_enum_values = False


class TemplateRegistry:
    """Registre des templates d'orchestration."""

    def __init__(self):
        self._templates: dict[str, WorkflowTemplate] = {}

    def register(self, template: WorkflowTemplate) -> None:
        """Enregistrer un nouveau template."""
        self._templates[template.id] = template

    def get(self, template_id: str) -> WorkflowTemplate:
        """Récupérer un template par son ID."""
        if template_id not in self._templates:
            raise KeyError(f"Template not found: {template_id}")
        return self._templates[template_id]

    def list(self) -> list[WorkflowTemplate]:
        """Lister tous les templates disponibles."""
        return list(self._templates.values())
