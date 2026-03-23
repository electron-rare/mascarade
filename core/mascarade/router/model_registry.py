"""Registre des modèles fine-tunés pour le routeur LLM."""

from __future__ import annotations

import json
import logging
import os
import tempfile
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

logger = logging.getLogger("mascarade.router.model_registry")

DEFAULT_STORAGE_PATH = Path("data/models.json")


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

    def __init__(self, storage_path: Path | None = DEFAULT_STORAGE_PATH) -> None:
        """Initialiser le registre de modèles."""
        self._models: dict[str, ModelMetadata] = {}
        self._storage_path = storage_path
        logger.debug("ModelRegistry initialized")
        self._load()

    def register_model(self, model_id: str, metadata: dict[str, Any]) -> None:
        """Enregistrer un modèle fine-tuné avec ses métadonnées.

        Args:
            model_id: Identifiant unique du modèle
            metadata: Dictionnaire contenant les métadonnées (domain, provider, etc.)
        """
        # Merge with existing metadata if model already exists
        existing_metadata = {}
        if model_id in self._models:
            existing_metadata = asdict(self._models[model_id])

        # Create timestamp if not provided
        if "created_at" not in metadata and "created_at" not in existing_metadata:
            metadata["created_at"] = datetime.now(UTC).isoformat()

        # Merge metadata
        merged = {**existing_metadata, **metadata, "model_id": model_id}

        # Create ModelMetadata instance
        model_metadata = ModelMetadata(**merged)
        self._models[model_id] = model_metadata

        logger.info("Registered model: %s (domain=%s)", model_id, model_metadata.domain)
        self._save()

    def get_models(self) -> list[ModelMetadata]:
        """Récupérer la liste de tous les modèles enregistrés.

        Returns:
            Liste des métadonnées de tous les modèles
        """
        return list(self._models.values())

    def verify_health(self, model_id: str) -> str:
        """Vérifier le statut de santé d'un modèle déployé.

        Args:
            model_id: Identifiant du modèle à vérifier

        Returns:
            Le statut de santé: "healthy", "unhealthy", "not_deployed", ou "unknown"
        """
        if model_id not in self._models:
            logger.warning("Model %s not found in registry", model_id)
            return "unknown"

        model = self._models[model_id]

        if not model.deployment_url:
            logger.debug("Model %s has no deployment_url", model_id)
            model.health_status = "not_deployed"
            self._save()
            return "not_deployed"

        # Try to connect to deployment URL
        base_url = model.deployment_url.rstrip("/")
        try:
            with httpx.Client(base_url=base_url, timeout=5.0) as client:
                # For Ollama-based deployments, check /api/tags
                resp = client.get("/api/tags")
                resp.raise_for_status()
                model.health_status = "healthy"
                logger.info("Model %s is healthy at %s", model_id, base_url)
        except Exception as exc:
            logger.warning(
                "Health check failed for model %s at %s: %s",
                model_id,
                base_url,
                exc,
            )
            model.health_status = "unhealthy"

        self._save()
        return model.health_status

    def _save(self) -> None:
        """Sauvegarder les modèles dans un fichier JSON."""
        if self._storage_path is None:
            return

        self._storage_path.parent.mkdir(parents=True, exist_ok=True)
        models_data = [asdict(model) for model in self._models.values()]

        # Atomic write: write to temp file, then rename
        fd, tmp_path = tempfile.mkstemp(
            dir=str(self._storage_path.parent), suffix=".tmp"
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(models_data, f, indent=2, ensure_ascii=False)
            os.replace(tmp_path, str(self._storage_path))
            logger.debug(
                "Saved %d model(s) to %s", len(models_data), self._storage_path
            )
        except BaseException:
            os.unlink(tmp_path)
            raise

    def _load(self) -> None:
        """Charger les modèles depuis le fichier JSON."""
        if self._storage_path is None or not self._storage_path.exists():
            return

        try:
            raw = json.loads(self._storage_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            logger.error("Failed to load models from %s: %s", self._storage_path, exc)
            return

        for data in raw:
            try:
                model = ModelMetadata(**data)
                self._models[model.model_id] = model
            except (KeyError, TypeError, ValueError) as exc:
                logger.warning("Skipping invalid model entry: %s", exc)

        logger.debug(
            "Loaded %d model(s) from %s", len(self._models), self._storage_path
        )
