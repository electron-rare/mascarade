#!/usr/bin/env python3
"""Validate training/eval JSONL dataset format."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ALLOWED_ROLES = {"system", "user", "assistant", "tool"}


def err(msg: str) -> None:
    print(f"[ERROR] {msg}")


def ok(msg: str) -> None:
    print(f"[OK] {msg}")


def validate_line(obj: dict, idx: int) -> list[str]:
    errors: list[str] = []

    if not isinstance(obj.get("id"), str) or not obj["id"].strip():
        errors.append(f"line {idx}: missing/invalid 'id'")

    messages = obj.get("messages")
    if not isinstance(messages, list) or not messages:
        errors.append(f"line {idx}: missing/invalid 'messages'")
        return errors

    for j, message in enumerate(messages, start=1):
        if not isinstance(message, dict):
            errors.append(f"line {idx}: message {j} must be an object")
            continue
        role = message.get("role")
        content = message.get("content")
        if role not in ALLOWED_ROLES:
            errors.append(f"line {idx}: message {j} invalid role '{role}'")
        if not isinstance(content, str) or not content.strip():
            errors.append(f"line {idx}: message {j} missing/invalid content")

    expected = obj.get("expected")
    if expected is not None and not isinstance(expected, str):
        errors.append(f"line {idx}: 'expected' must be a string when present")

    return errors


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: validate_dataset.py <dataset.jsonl>")
        return 2

    path = Path(sys.argv[1])
    if not path.exists():
        err(f"file not found: {path}")
        return 2

    total = 0
    failed = 0
    ids: set[str] = set()
    duplicate_ids = 0

    with path.open("r", encoding="utf-8") as f:
        for idx, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            total += 1
            try:
                obj = json.loads(line)
            except json.JSONDecodeError as exc:
                err(f"line {idx}: invalid JSON ({exc})")
                failed += 1
                continue

            if not isinstance(obj, dict):
                err(f"line {idx}: top-level value must be an object")
                failed += 1
                continue

            row_errors = validate_line(obj, idx)
            row_id = obj.get("id")
            if isinstance(row_id, str) and row_id in ids:
                row_errors.append(f"line {idx}: duplicate id '{row_id}'")
                duplicate_ids += 1
            if isinstance(row_id, str):
                ids.add(row_id)

            if row_errors:
                for message in row_errors:
                    err(message)
                failed += 1

    ok(f"checked {total} samples")
    if duplicate_ids:
        err(f"duplicate ids: {duplicate_ids}")
    if failed:
        err(f"invalid rows: {failed}")
        return 1

    ok("dataset is valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
