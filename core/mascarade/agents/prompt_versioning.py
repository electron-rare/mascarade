"""Versionnage des prompts système — suivi des changements et rollback."""

from __future__ import annotations

import difflib
import json
import logging
import os
import tempfile
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

logger = logging.getLogger("mascarade.agents")


def iso_utc_now() -> str:
    """Retourne un timestamp ISO8601 UTC avec suffixe Z stable."""
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


@dataclass
class PromptVersion:
    """Version d'un prompt système avec métadonnées de changement."""

    version_number: int
    timestamp: str
    content: str
    author_hash: str
    diff: str | None = None
    note: str | None = None


DEFAULT_PROMPT_STORAGE_PATH = Path("data/prompt_history.json")


class PromptHistory:
    """Gestionnaire d'historique des versions de prompts."""

    def __init__(
        self,
        storage_path: Path | None = DEFAULT_PROMPT_STORAGE_PATH,
        max_versions: int | None = None,
    ) -> None:
        self._versions: list[PromptVersion] = []
        self._storage_path = storage_path
        self._max_versions = max_versions

    def add_version(
        self,
        content: str,
        author_hash: str,
        note: str | None = None,
    ) -> PromptVersion:
        """Ajouter une nouvelle version du prompt."""
        version_number = len(self._versions) + 1
        timestamp = iso_utc_now()

        # Calculer le diff si une version précédente existe
        diff = None
        if self._versions:
            previous_content = self._versions[-1].content
            diff = self._compute_diff(previous_content, content)

        version = PromptVersion(
            version_number=version_number,
            timestamp=timestamp,
            content=content,
            author_hash=author_hash,
            diff=diff,
            note=note,
        )
        self._versions.append(version)

        # Auto-prune if max_versions is set
        if self._max_versions is not None and self._max_versions > 0:
            self.prune(self._max_versions)

        return version

    def get_history(
        self,
        limit: int | None = None,
        since: str | None = None,
    ) -> list[PromptVersion]:
        """Récupérer l'historique des versions, optionnellement filtré."""
        versions = self._versions

        if since:
            versions = [v for v in versions if v.timestamp >= since]

        if limit is not None and limit > 0:
            versions = versions[-limit:]

        return list(versions)

    def get_diff(self, from_version: int, to_version: int) -> str:
        """Calculer le diff entre deux versions."""
        if from_version < 1 or from_version > len(self._versions):
            raise ValueError(f"Version {from_version} introuvable")
        if to_version < 1 or to_version > len(self._versions):
            raise ValueError(f"Version {to_version} introuvable")

        from_content = self._versions[from_version - 1].content
        to_content = self._versions[to_version - 1].content

        return self._compute_diff(from_content, to_content)

    def rollback(self, version_number: int) -> PromptVersion:
        """Restaurer le contenu d'une version précédente en créant une nouvelle version."""
        if version_number < 1 or version_number > len(self._versions):
            raise ValueError(f"Version {version_number} introuvable")

        target_version = self._versions[version_number - 1]

        # Créer une nouvelle version avec le contenu restauré
        new_version = self.add_version(
            content=target_version.content,
            author_hash=target_version.author_hash,
            note=f"Rollback to version {version_number}",
        )
        return new_version

    def prune(self, keep_count: int) -> int:
        """Supprimer les anciennes versions, en gardant les N plus récentes."""
        if keep_count < 1:
            raise ValueError("keep_count doit être >= 1")

        if len(self._versions) <= keep_count:
            return 0

        removed_count = len(self._versions) - keep_count
        self._versions = self._versions[-keep_count:]

        # Renuméroter les versions restantes
        for i, version in enumerate(self._versions, start=1):
            version.version_number = i

        return removed_count

    def _compute_diff(self, old_content: str, new_content: str) -> str:
        """Calculer un diff unifié entre deux contenus."""
        old_lines = old_content.splitlines(keepends=True)
        new_lines = new_content.splitlines(keepends=True)

        diff_lines = difflib.unified_diff(
            old_lines,
            new_lines,
            lineterm="",
        )
        return "".join(diff_lines)

    # --- Persistance ---

    def save(self) -> None:
        """Sauvegarder l'historique dans un fichier JSON."""
        if self._storage_path is None:
            return
        self._storage_path.parent.mkdir(parents=True, exist_ok=True)

        versions_data = [asdict(v) for v in self._versions]

        # Atomic write: write to temp file, then rename
        fd, tmp_path = tempfile.mkstemp(
            dir=str(self._storage_path.parent), suffix=".tmp"
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(versions_data, f, indent=2, ensure_ascii=False)
            os.replace(tmp_path, str(self._storage_path))
        except BaseException:
            os.unlink(tmp_path)
            raise

    def load(self) -> None:
        """Charger l'historique depuis le fichier JSON."""
        if self._storage_path is None or not self._storage_path.exists():
            return
        try:
            raw = json.loads(self._storage_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            logger.error(
                "Failed to load prompt history from %s: %s", self._storage_path, exc
            )
            return

        self._versions = []
        for data in raw:
            try:
                version = PromptVersion(**data)
                self._versions.append(version)
            except (KeyError, TypeError) as exc:
                logger.warning("Skipping invalid version entry: %s", exc)
