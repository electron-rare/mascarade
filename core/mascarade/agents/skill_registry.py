"""Skill registry — registration, discovery and persistence."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import tempfile
from dataclasses import asdict
from pathlib import Path

from mascarade.agents.skill import Skill

logger = logging.getLogger("mascarade.skills")

DEFAULT_STORAGE_PATH = Path("data/skills.json")


class SkillRegistry:
    """Centralized registry for managing available skills."""

    def __init__(self, storage_path: Path | None = DEFAULT_STORAGE_PATH) -> None:
        self._skills: dict[str, Skill] = {}
        self._builtin_names: set[str] = set()
        self._storage_path = storage_path
        self._lock = asyncio.Lock()

    def register(self, skill: Skill, *, builtin: bool = False) -> None:
        """Register a skill in the registry."""
        self._skills[skill.name] = skill
        if builtin:
            self._builtin_names.add(skill.name)

    async def async_register(self, skill: Skill, *, builtin: bool = False) -> None:
        """Thread-safe register for use from async contexts."""
        async with self._lock:
            self.register(skill, builtin=builtin)

    def get(self, name: str) -> Skill:
        """Get a skill by name."""
        if name not in self._skills:
            raise KeyError(
                f"Skill '{name}' non trouvé. Disponibles: {list(self._skills.keys())}"
            )
        return self._skills[name]

    def list(self) -> list[Skill]:
        """List all registered skills."""
        return list(self._skills.values())

    def remove(self, name: str) -> None:
        """Remove a skill from the registry."""
        self._skills.pop(name, None)
        self._builtin_names.discard(name)

    async def async_remove(self, name: str) -> None:
        """Thread-safe remove for use from async contexts."""
        async with self._lock:
            self.remove(name)

    def __contains__(self, name: str) -> bool:
        return name in self._skills

    def __len__(self) -> int:
        return len(self._skills)

    def is_builtin(self, name: str) -> bool:
        """Check if a skill is builtin (read-only)."""
        return name in self._builtin_names

    # --- Persistence ---

    async def async_save(self) -> None:
        """Thread-safe save for use from async contexts."""
        async with self._lock:
            self.save()

    async def async_load(self) -> None:
        """Thread-safe load for use from async contexts."""
        async with self._lock:
            self.load()

    def save(self) -> None:
        """Save dynamic skills to JSON file (atomic write)."""
        if self._storage_path is None:
            return

        self._storage_path.parent.mkdir(parents=True, exist_ok=True)
        skills_data = []
        for skill in self._skills.values():
            if skill.name in self._builtin_names:
                continue
            skills_data.append(asdict(skill))

        # Atomic write: write to temp file, then rename
        fd, tmp_path = tempfile.mkstemp(
            dir=str(self._storage_path.parent), suffix=".tmp"
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(skills_data, f, indent=2, ensure_ascii=False)
            os.replace(tmp_path, str(self._storage_path))
        except BaseException:
            os.unlink(tmp_path)
            raise

    def load(self) -> None:
        """Load dynamic skills from JSON file."""
        if self._storage_path is None or not self._storage_path.exists():
            return
        try:
            raw = json.loads(self._storage_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            logger.error("Failed to load skills from %s: %s", self._storage_path, exc)
            return
        for data in raw:
            try:
                skill = Skill(**data)
                self.register(skill)
            except (KeyError, TypeError, ValueError) as exc:
                logger.warning("Skipping invalid skill entry: %s", exc)
