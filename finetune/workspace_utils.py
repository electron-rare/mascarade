#!/usr/bin/env python3
"""Helpers to route large training outputs away from a full repo filesystem."""

from __future__ import annotations

import os
import shutil
import time
from pathlib import Path

TRAIN_WORKDIR_ENV = "MASCARADE_TRAIN_WORKDIR"
TRAIN_REQUIRED_BYTES_ENV = "MASCARADE_TRAIN_REQUIRED_BYTES"
DEFAULT_TRAIN_WORKDIR = Path("/dev/shm/mascarade-train")
DEFAULT_TRAIN_REQUIRED_BYTES = 2 * 1024**3


def disk_free_bytes(path: Path) -> int:
    probe = path
    while not probe.exists() and probe != probe.parent:
        probe = probe.parent
    return shutil.disk_usage(probe).free


def _required_bytes(required_bytes: int | None = None) -> int:
    if required_bytes is not None:
        return required_bytes
    raw_value = os.environ.get(TRAIN_REQUIRED_BYTES_ENV)
    if raw_value:
        try:
            return max(1, int(raw_value))
        except ValueError:
            pass
    return DEFAULT_TRAIN_REQUIRED_BYTES


def _unique_child_path(root: Path, preferred_name: str) -> Path:
    candidate = root / preferred_name
    if not candidate.exists():
        return candidate
    stamp = time.strftime("%Y%m%d_%H%M%S")
    return root / f"{preferred_name}_{stamp}"


def prepare_training_output_dir(
    requested_output_dir: Path,
    *,
    required_bytes: int | None = None,
) -> dict[str, object]:
    requested_output_dir = requested_output_dir.resolve()
    requested_root = requested_output_dir.parent
    needed_bytes = _required_bytes(required_bytes)
    requested_free = disk_free_bytes(requested_root)
    if requested_free >= needed_bytes:
        return {
            "requested_output_dir": requested_output_dir,
            "output_dir": requested_output_dir,
            "mode": "requested",
            "root": requested_root,
            "required_bytes": needed_bytes,
            "requested_free_bytes": requested_free,
            "scratch_free_bytes": None,
            "reason": (
                f"using requested training output directory under {requested_root} "
                f"(free={requested_free} bytes)"
            ),
        }

    scratch_root = Path(os.environ.get(TRAIN_WORKDIR_ENV, str(DEFAULT_TRAIN_WORKDIR)))
    scratch_free = disk_free_bytes(scratch_root)
    if scratch_free < needed_bytes:
        raise RuntimeError(
            "training workspace is full: "
            f"need about {needed_bytes} bytes, "
            f"requested_free={requested_free}, scratch_free={scratch_free}"
        )
    output_dir = _unique_child_path(scratch_root, requested_output_dir.name)
    return {
        "requested_output_dir": requested_output_dir,
        "output_dir": output_dir,
        "mode": "scratch",
        "root": scratch_root,
        "required_bytes": needed_bytes,
        "requested_free_bytes": requested_free,
        "scratch_free_bytes": scratch_free,
        "reason": (
            f"using scratch training workspace under {scratch_root} because "
            f"requested_free={requested_free} bytes"
        ),
    }
