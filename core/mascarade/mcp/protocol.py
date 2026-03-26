"""Low-level MCP stdio protocol helpers."""

from __future__ import annotations

import asyncio
import json
from typing import Any

from mascarade.config import settings


def _message_text(payload: dict[str, Any]) -> str:
    content = payload.get("content")
    if isinstance(content, list):
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                text = str(item.get("text") or "").strip()
                if text:
                    return text
    return ""


def _normalize_scope(
    *,
    project_id: str | None = None,
    federation_scope: list[str] | tuple[str, ...] | None = None,
    knowledge_scope: str = "project",
) -> tuple[str, list[str], str]:
    normalized_project = (project_id or settings.mascarade_project_id).strip() or "default"
    normalized_scope = (knowledge_scope or "project").strip().lower() or "project"
    if normalized_scope not in {"project", "federated"}:
        raise ValueError(f"Unsupported knowledge_scope: {knowledge_scope}")

    cleaned_federation = [item.strip() for item in (federation_scope or []) if str(item).strip()]
    if normalized_scope == "project":
        cleaned_federation = [normalized_project]
    elif not cleaned_federation:
        raise ValueError("federation_scope is required when knowledge_scope is federated")
    elif normalized_project not in cleaned_federation:
        cleaned_federation = [normalized_project, *cleaned_federation]

    return normalized_project, list(dict.fromkeys(cleaned_federation)), normalized_scope


async def _read_message(
    stdout: asyncio.StreamReader,
) -> dict[str, Any] | None:
    headers: dict[str, str] = {}
    first_line: bytes | None = None
    while True:
        line = await stdout.readline()
        if not line:
            return None
        if first_line is None:
            first_line = line
            if line.lstrip().startswith(b"{"):
                return json.loads(line.decode("utf-8"))
        if line in (b"\r\n", b"\n"):
            break
        key, _, value = line.decode("utf-8").partition(":")
        headers[key.strip().lower()] = value.strip()

    content_length = int(headers.get("content-length", "0") or "0")
    if content_length <= 0:
        return None

    body = await stdout.readexactly(content_length)
    return json.loads(body.decode("utf-8"))


async def _write_message(
    stdin: asyncio.StreamWriter,
    payload: dict[str, Any],
) -> None:
    body = json.dumps(payload).encode("utf-8")
    stdin.write(f"Content-Length: {len(body)}\r\n\r\n".encode())
    stdin.write(body)
    await stdin.drain()
