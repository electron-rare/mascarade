"""Helpers for writing small per-run manifests for local finetune workflows."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

SENSITIVE_FLAGS = {
    "--api-key",
    "--token",
    "--password",
    "--secret",
}


def now_ts() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S")


def write_manifest(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload["updated_at"] = now_ts()
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def load_json(path: Path) -> Any | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def redact_command(
    command: list[str], sensitive_flags: set[str] | None = None
) -> list[str]:
    sensitive = sensitive_flags or SENSITIVE_FLAGS
    redacted: list[str] = []
    redact_next = False
    for arg in command:
        if redact_next:
            redacted.append("<redacted>")
            redact_next = False
            continue
        if arg in sensitive:
            redacted.append(arg)
            redact_next = True
            continue
        matched = next(
            (flag for flag in sensitive if arg.startswith(f"{flag}=")),
            None,
        )
        if matched is not None:
            redacted.append(f"{matched}=<redacted>")
            continue
        redacted.append(arg)
    return redacted
