"""Helpers to materialize default seed datasets when they are missing."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def seed_builder_for_domain(script_dir: Path, domain: str) -> Path | None:
    candidate = script_dir / "datasets" / f"build_{domain}_dataset.py"
    if candidate.exists():
        return candidate
    return None


def ensure_seed_dataset(script_dir: Path, domain: str, dataset_path: Path) -> Path | None:
    """Build the default seed dataset when the canonical JSONL is missing."""

    if dataset_path.exists():
        return None

    builder = seed_builder_for_domain(script_dir, domain)
    if builder is None:
        return None

    completed = subprocess.run(
        [sys.executable, str(builder)],
        cwd=script_dir.parent,
    )
    if completed.returncode != 0:
        raise RuntimeError(f"Seed dataset bootstrap failed: {builder.name}")
    if not dataset_path.exists():
        raise RuntimeError(
            f"Seed dataset bootstrap did not create expected file: {dataset_path}"
        )
    return builder
