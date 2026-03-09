#!/usr/bin/env python3
"""Helpers for ShareGPT-style fine-tuning datasets."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROLE_ALIASES = {
    "system": "system",
    "human": "human",
    "user": "human",
    "gpt": "gpt",
    "assistant": "gpt",
}

CHAT_ROLE_MAP = {
    "system": "system",
    "human": "user",
    "gpt": "assistant",
}


def load_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def normalize_text(value: str) -> str:
    return " ".join(value.strip().split())


def canonical_role(role: object) -> str | None:
    if not isinstance(role, str):
        return None
    return ROLE_ALIASES.get(role)


def normalize_conversations(conversations: object) -> list[dict]:
    normalized: list[dict] = []
    if not isinstance(conversations, list):
        return normalized

    for message in conversations:
        if not isinstance(message, dict):
            continue
        role = canonical_role(message.get("from"))
        if role is None:
            continue
        value = message.get("value")
        if isinstance(value, str):
            text = value.strip()
        elif value is None:
            text = ""
        else:
            text = str(value).strip()
        normalized.append({"from": role, "value": text})
    return normalized


def row_messages(row: dict) -> list[dict]:
    conversations = normalize_conversations(row.get("conversations", []))
    messages: list[dict] = []
    for message in conversations:
        value = message.get("value")
        role = CHAT_ROLE_MAP.get(message.get("from"))
        if role and isinstance(value, str) and value.strip():
            messages.append({"role": role, "content": value.strip()})
    return messages


def canonical_payload(system: str, user: str, assistant: str) -> str:
    return json.dumps(
        {
            "system": normalize_text(system),
            "user": normalize_text(user),
            "assistant": normalize_text(assistant),
        },
        ensure_ascii=False,
        sort_keys=True,
    )


def make_row(
    *,
    row_id: str,
    system: str,
    user: str,
    assistant: str,
    meta: dict | None = None,
) -> dict:
    row = {
        "id": row_id,
        "conversations": [
            {"from": "system", "value": system.strip()},
            {"from": "human", "value": user.strip()},
            {"from": "gpt", "value": assistant.strip()},
        ],
    }
    if meta:
        row["meta"] = meta
    return row


def validate_sharegpt_row(row: dict) -> list[str]:
    errors: list[str] = []
    if not isinstance(row.get("id"), str) or not row["id"].strip():
        errors.append("missing or invalid id")

    conversations = row.get("conversations")
    if not isinstance(conversations, list) or len(conversations) < 3:
        errors.append("conversations must contain at least system, human and gpt")
        return errors

    seen_roles: list[str] = []
    for message in conversations:
        if not isinstance(message, dict):
            errors.append("conversation message must be an object")
            continue
        role = canonical_role(message.get("from"))
        value = message.get("value")
        if role is None:
            errors.append(f"invalid role: {message.get('from')}")
        if not isinstance(value, str) or not value.strip():
            errors.append(f"invalid value for role: {message.get('from')}")
        if role in CHAT_ROLE_MAP:
            seen_roles.append(role)

    for required in ("system", "human", "gpt"):
        if required not in seen_roles:
            errors.append(f"missing role: {required}")

    return errors


def validate_rows(rows: list[dict]) -> list[str]:
    seen_ids: set[str] = set()
    errors: list[str] = []
    for index, row in enumerate(rows, start=1):
        row_errors = validate_sharegpt_row(row)
        row_id = row.get("id")
        if isinstance(row_id, str):
            if row_id in seen_ids:
                row_errors.append(f"duplicate id: {row_id}")
            seen_ids.add(row_id)
        if row_errors:
            errors.extend([f"row {index}: {message}" for message in row_errors])
    return errors


def fingerprint_row(row: dict) -> str:
    messages = row_messages(row)
    system = next((m["content"] for m in messages if m["role"] == "system"), "")
    user = next((m["content"] for m in messages if m["role"] == "user"), "")
    assistant = next(
        (m["content"] for m in reversed(messages) if m["role"] == "assistant"), ""
    )
    return hashlib.sha1(
        canonical_payload(system, user, assistant).encode("utf-8")
    ).hexdigest()


def dedupe_rows(rows: list[dict]) -> list[dict]:
    deduped: list[dict] = []
    seen_fingerprints: set[str] = set()
    for row in rows:
        fp = fingerprint_row(row)
        if fp in seen_fingerprints:
            continue
        deduped.append(row)
        seen_fingerprints.add(fp)
    return deduped


def dedupe_rows_with_stats(rows: list[dict]) -> tuple[list[dict], int]:
    deduped = dedupe_rows(rows)
    return deduped, max(0, len(rows) - len(deduped))


def ensure_row_ids_with_stats(rows: list[dict], prefix: str) -> tuple[list[dict], int]:
    normalized: list[dict] = []
    fixed_ids = 0
    for index, row in enumerate(rows, start=1):
        current = dict(row)
        current["conversations"] = normalize_conversations(
            current.get("conversations", [])
        )
        row_id = current.get("id")
        if not isinstance(row_id, str) or not row_id.strip():
            current["id"] = f"{prefix}-{index:05d}-{fingerprint_row(current)[:10]}"
            fixed_ids += 1
        normalized.append(current)
    return normalized, fixed_ids


def ensure_row_ids(rows: list[dict], prefix: str) -> list[dict]:
    normalized, _fixed_ids = ensure_row_ids_with_stats(rows, prefix)
    return normalized
