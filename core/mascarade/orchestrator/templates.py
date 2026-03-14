"""Système de templates pour orchestrations multi-agents."""

from __future__ import annotations

import json
import logging
import os
import tempfile
from enum import StrEnum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger("mascarade.orchestrator")

DEFAULT_STORAGE_PATH = Path("data/templates.json")


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
    """Registre centralisé pour gérer les templates d'orchestration."""

    def __init__(self, storage_path: Path | None = DEFAULT_STORAGE_PATH) -> None:
        self._templates: dict[str, WorkflowTemplate] = {}
        self._builtin_ids: set[str] = set()
        self._storage_path = storage_path

    def register(self, template: WorkflowTemplate, *, builtin: bool = False) -> None:
        """Enregistrer un nouveau template."""
        self._templates[template.id] = template
        if builtin:
            self._builtin_ids.add(template.id)

    def get(self, template_id: str) -> WorkflowTemplate:
        """Récupérer un template par son ID."""
        if template_id not in self._templates:
            raise KeyError(
                f"Template '{template_id}' non trouvé. Disponibles: {list(self._templates.keys())}"
            )
        return self._templates[template_id]

    def list(self) -> list[WorkflowTemplate]:
        """Lister tous les templates disponibles."""
        return list(self._templates.values())

    def remove(self, template_id: str) -> None:
        """Retirer un template du registre."""
        self._templates.pop(template_id, None)
        self._builtin_ids.discard(template_id)

    def __contains__(self, template_id: str) -> bool:
        return template_id in self._templates

    def __len__(self) -> int:
        return len(self._templates)

    def is_builtin(self, template_id: str) -> bool:
        """Vérifie si un template est built-in (non modifiable)."""
        return template_id in self._builtin_ids

    # --- Persistance ---

    def save(self) -> None:
        """Sauvegarder les templates dynamiques dans un fichier JSON."""
        if self._storage_path is None:
            return
        self._storage_path.parent.mkdir(parents=True, exist_ok=True)
        templates_data = []
        for template in self._templates.values():
            if template.id in self._builtin_ids:
                continue
            data = template.model_dump()
            data["mode"] = template.mode.value if isinstance(template.mode, ExecutionMode) else str(template.mode)
            templates_data.append(data)
        # Atomic write: write to temp file, then rename
        fd, tmp_path = tempfile.mkstemp(
            dir=str(self._storage_path.parent), suffix=".tmp"
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(templates_data, f, indent=2, ensure_ascii=False)
            os.replace(tmp_path, str(self._storage_path))
        except BaseException:
            os.unlink(tmp_path)
            raise

    def load(self) -> None:
        """Charger les templates dynamiques depuis le fichier JSON."""
        if self._storage_path is None or not self._storage_path.exists():
            return
        try:
            raw = json.loads(self._storage_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            logger.error("Failed to load templates from %s: %s", self._storage_path, exc)
            return
        for data in raw:
            try:
                data["mode"] = ExecutionMode(data["mode"])
                template = WorkflowTemplate(**data)
                self.register(template)
            except (KeyError, TypeError, ValueError) as exc:
                logger.warning("Skipping invalid template entry: %s", exc)


# --- Built-in Templates ---


def register_builtin_templates(registry: TemplateRegistry) -> None:
    """Enregistrer tous les templates built-in dans le registre."""
    for template in BUILTIN_TEMPLATES:
        registry.register(template, builtin=True)


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
