"""Registre des modèles fine-tunés pour le routeur LLM."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger("mascarade.router.model_registry")


@dataclass
class ModelMetadata:
    """Métadonnées d'un modèle fine-tuné."""

    model_id: str
    domain: str | None = None
    provider: str = "ollama"
    deployment_url: str | None = None
    health_status: str = "unknown"
    created_at: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class ModelRegistry:
    """Registre central pour tracker les modèles fine-tunés avec métadonnées."""

    def __init__(self) -> None:
        """Initialiser le registre de modèles."""
        self._models: dict[str, ModelMetadata] = {}
        logger.debug("ModelRegistry initialized")
