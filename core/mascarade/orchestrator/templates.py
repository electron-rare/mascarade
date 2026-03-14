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


# --- Built-in Templates ---


def register_builtin_templates(registry: TemplateRegistry) -> None:
    """Enregistrer tous les templates built-in dans le registre."""
    for template in BUILTIN_TEMPLATES:
        registry.register(template)


research_report = WorkflowTemplate(
    id="research-report",
    name="Research & Report",
    description="Analyse approfondie d'un sujet avec rapport structuré",
    agent_names=["agent-zero", "analyst", "knowledge-scribe"],
    mode=ExecutionMode.PIPELINE,
    documentation=(
        "Pipeline de recherche et rédaction de rapport:\n\n"
        "1. **agent-zero**: Cadre la demande, clarifie l'objectif et décompose le sujet\n"
        "2. **analyst**: Analyse approfondie avec points clés, tendances et recommandations\n"
        "3. **knowledge-scribe**: Formate le tout en rapport structuré pour la knowledge base\n\n"
        "Usage: Idéal pour produire des rapports d'analyse, études de cas ou documentation technique."
    ),
)

content_creation = WorkflowTemplate(
    id="content-creation",
    name="Content Creation Pipeline",
    description="Génération d'idées, rédaction et formatage pour publication",
    agent_names=["brainstorm", "writer", "knowledge-scribe"],
    mode=ExecutionMode.PIPELINE,
    documentation=(
        "Pipeline de création de contenu:\n\n"
        "1. **brainstorm**: Génère des idées créatives et variées sur le thème\n"
        "2. **writer**: Rédige le contenu avec style et structure adaptés\n"
        "3. **knowledge-scribe**: Formate pour publication dans la knowledge base\n\n"
        "Usage: Articles, posts, documentation créative, guides utilisateur."
    ),
)

translate_polish = WorkflowTemplate(
    id="translate-and-polish",
    name="Translate & Polish",
    description="Traduction naturelle suivie d'une révision stylistique",
    agent_names=["translator", "writer"],
    mode=ExecutionMode.SEQUENTIAL,
    documentation=(
        "Workflow de traduction professionnelle:\n\n"
        "1. **translator**: Traduit le texte de manière idiomatique\n"
        "2. **writer**: Révise et polit le style pour un rendu final impeccable\n\n"
        "Usage: Documentation multilingue, communication internationale, contenu marketing."
    ),
)

code_review_workflow = WorkflowTemplate(
    id="code-review-workflow",
    name="Code Review & Documentation",
    description="Review de code avec documentation des findings",
    agent_names=["coder", "knowledge-scribe"],
    mode=ExecutionMode.SEQUENTIAL,
    documentation=(
        "Workflow de code review documenté:\n\n"
        "1. **coder**: Review approfondie (bugs, security, performance, best practices)\n"
        "2. **knowledge-scribe**: Formate les findings en rapport structuré avec priorités\n\n"
        "Usage: Pull requests, audits de code, revues de sécurité."
    ),
)

summarize_document = WorkflowTemplate(
    id="summarize-and-document",
    name="Summarize & Document",
    description="Résumé intelligent suivi de formatage pour archivage",
    agent_names=["summarizer", "knowledge-scribe"],
    mode=ExecutionMode.SEQUENTIAL,
    documentation=(
        "Workflow de synthèse et archivage:\n\n"
        "1. **summarizer**: Extrait les points clés en bullet points concis\n"
        "2. **knowledge-scribe**: Formate pour archivage dans la knowledge base\n\n"
        "Usage: Notes de réunion, veille technologique, documentation de décisions."
    ),
)

incident_analysis = WorkflowTemplate(
    id="incident-analysis",
    name="Incident Analysis & Postmortem",
    description="Analyse d'incident avec recommandations et rapport",
    agent_names=["agent-zero", "analyst", "planner", "knowledge-scribe"],
    mode=ExecutionMode.PIPELINE,
    documentation=(
        "Pipeline d'analyse d'incident:\n\n"
        "1. **agent-zero**: Analyse logs/traces, distingue faits/hypothèses, identifie cause racine\n"
        "2. **analyst**: Évalue l'impact, identifie risques et opportunités d'amélioration\n"
        "3. **planner**: Décompose les actions correctives en tâches priorisées\n"
        "4. **knowledge-scribe**: Produit le postmortem final structuré\n\n"
        "Usage: Postmortems, analyses d'incidents, root cause analysis."
    ),
)

BUILTIN_TEMPLATES = [
    research_report,
    content_creation,
    translate_polish,
    code_review_workflow,
    summarize_document,
    incident_analysis,
]
