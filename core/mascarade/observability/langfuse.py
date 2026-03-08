"""Best-effort Langfuse tracing for LLM generations."""

from __future__ import annotations

import logging
from collections.abc import Iterator
from contextlib import contextmanager
from functools import lru_cache
from typing import Any

from mascarade.config import is_secret_configured, settings

logger = logging.getLogger("mascarade.observability.langfuse")

try:  # pragma: no cover - optional dependency at import time
    from langfuse import Langfuse
except ImportError:  # pragma: no cover - handled at runtime
    Langfuse = None  # type: ignore[assignment]


def _resolve_public_key() -> str:
    return (
        settings.langfuse_public_key.strip()
        or settings.langfuse_init_project_public_key.strip()
    )


def _resolve_secret_key() -> str:
    return (
        settings.langfuse_secret_key.strip()
        or settings.langfuse_init_project_secret_key.strip()
    )


def _resolve_host() -> str:
    return settings.langfuse_host.strip() or "http://langfuse-web:3000"


def langfuse_tracing_configured() -> bool:
    if Langfuse is None:
        return False
    if not _resolve_public_key():
        return False
    return is_secret_configured(_resolve_secret_key())


@lru_cache(maxsize=1)
def get_langfuse_client():
    if not langfuse_tracing_configured():
        return None

    try:
        return Langfuse(
            public_key=_resolve_public_key(),
            secret_key=_resolve_secret_key(),
            base_url=_resolve_host(),
        )
    except Exception as exc:  # pragma: no cover - best effort only
        logger.warning("Langfuse client disabled: %s", exc)
        return None


def reset_langfuse_client() -> None:
    get_langfuse_client.cache_clear()


@contextmanager
def start_langfuse_generation(
    *,
    name: str,
    model: str,
    input: Any,
    metadata: dict[str, Any],
) -> Iterator[Any | None]:
    client = get_langfuse_client()
    if client is None:
        yield None
        return

    try:
        with client.start_as_current_generation(
            name=name,
            model=model,
            input=input,
            metadata=metadata,
        ) as generation:
            yield generation
    except Exception as exc:  # pragma: no cover - best effort only
        logger.warning("Langfuse tracing skipped: %s", exc)
        yield None


def update_langfuse_generation(generation: Any | None, **kwargs: Any) -> None:
    if generation is None:
        return

    payload = {key: value for key, value in kwargs.items() if value is not None}
    if not payload:
        return

    try:
        generation.update(**payload)
        client = get_langfuse_client()
        if client is not None:
            client.flush()
    except Exception as exc:  # pragma: no cover - best effort only
        logger.debug("Langfuse generation update skipped: %s", exc)
