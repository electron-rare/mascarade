"""Langfuse tracing integration for Mascarade LLM orchestrator.

Provides opt-in observability via the Langfuse Python SDK:
- ``@observe()`` decorator-based tracing for router and agent calls
- Trace-level correlation: all calls within a single user prompt share a trace_id
- Tracks input/output tokens, cost, latency, model, and provider

Activation: set ``LANGFUSE_ENABLED=true`` plus valid public/secret keys.
When disabled, all helpers are transparent no-ops.
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from functools import lru_cache, wraps
from typing import Any

from mascarade.config import is_secret_configured, secret_value, settings

logger = logging.getLogger("mascarade.observability.langfuse")

# ---------------------------------------------------------------------------
# Optional import
# ---------------------------------------------------------------------------
try:  # pragma: no cover - optional dependency at import time
    from langfuse import Langfuse
    from langfuse.decorators import langfuse_context, observe  # noqa: F401
except ImportError:  # pragma: no cover - handled at runtime
    Langfuse = None  # type: ignore[assignment]
    langfuse_context = None  # type: ignore[assignment]
    observe = None  # type: ignore[assignment]

# ---------------------------------------------------------------------------
# Trace-id context variable for correlating all calls within one user request
# ---------------------------------------------------------------------------
_current_trace_id: ContextVar[str | None] = ContextVar("langfuse_trace_id", default=None)


def new_trace_id() -> str:
    """Generate and set a new trace_id for the current async context."""
    tid = uuid.uuid4().hex
    _current_trace_id.set(tid)
    return tid


def get_trace_id() -> str | None:
    """Return the current trace_id, or None if not set."""
    return _current_trace_id.get()


def set_trace_id(trace_id: str) -> None:
    """Explicitly set the trace_id for the current async context."""
    _current_trace_id.set(trace_id)


# ---------------------------------------------------------------------------
# Key resolution (supports both dedicated keys and init-project keys)
# ---------------------------------------------------------------------------
def _resolve_public_key() -> str:
    pk = settings.langfuse_public_key.strip()
    if pk:
        return pk
    return settings.langfuse_init_project_public_key.strip()


def _resolve_secret_key() -> str:
    sk = secret_value(settings.langfuse_secret_key).strip()
    if sk:
        return sk
    return secret_value(settings.langfuse_init_project_secret_key).strip()


def _resolve_host() -> str:
    return settings.langfuse_host.strip() or "http://langfuse-web:3000"


# ---------------------------------------------------------------------------
# Feature check
# ---------------------------------------------------------------------------
def langfuse_tracing_configured() -> bool:
    """Return True if Langfuse tracing is both enabled and properly configured."""
    if Langfuse is None:
        return False
    if not settings.langfuse_enabled:
        return False
    if not _resolve_public_key():
        return False
    return is_secret_configured(_resolve_secret_key())


# ---------------------------------------------------------------------------
# Singleton client
# ---------------------------------------------------------------------------
@lru_cache(maxsize=1)
def get_langfuse_client() -> Any | None:
    """Return the shared Langfuse client instance, or None if not configured."""
    if not langfuse_tracing_configured():
        return None

    try:
        client = Langfuse(
            public_key=_resolve_public_key(),
            secret_key=_resolve_secret_key(),
            host=_resolve_host(),
        )
        logger.info("Langfuse client initialised (host=%s)", _resolve_host())
        return client
    except Exception as exc:  # pragma: no cover - best effort only
        logger.warning("Langfuse client disabled: %s", exc)
        return None


def reset_langfuse_client() -> None:
    """Clear the cached client (useful after config changes or in tests)."""
    get_langfuse_client.cache_clear()


def flush_langfuse() -> None:
    """Flush any pending events to Langfuse."""
    client = get_langfuse_client()
    if client is not None:
        try:
            client.flush()
        except Exception as exc:  # pragma: no cover
            logger.debug("Langfuse flush failed: %s", exc)


# ---------------------------------------------------------------------------
# Trace / span / generation helpers (low-level, for manual instrumentation)
# ---------------------------------------------------------------------------
def create_trace(
    *,
    name: str,
    user_id: str | None = None,
    session_id: str | None = None,
    metadata: dict[str, Any] | None = None,
    tags: list[str] | None = None,
) -> Any | None:
    """Create a new Langfuse trace, setting the trace_id in context."""
    client = get_langfuse_client()
    if client is None:
        return None

    trace_id = new_trace_id()
    try:
        trace = client.trace(
            id=trace_id,
            name=name,
            user_id=user_id,
            session_id=session_id,
            metadata=metadata or {},
            tags=tags or [],
        )
        return trace
    except Exception as exc:  # pragma: no cover
        logger.debug("Langfuse trace creation skipped: %s", exc)
        return None


def create_generation(
    trace: Any | None,
    *,
    name: str,
    model: str,
    input: Any = None,
    metadata: dict[str, Any] | None = None,
) -> Any | None:
    """Create a generation span under the given trace."""
    if trace is None:
        return None
    try:
        return trace.generation(
            name=name,
            model=model,
            input=input,
            metadata=metadata or {},
        )
    except Exception as exc:  # pragma: no cover
        logger.debug("Langfuse generation creation skipped: %s", exc)
        return None


def end_generation(
    generation: Any | None,
    *,
    output: Any = None,
    usage: dict[str, int] | None = None,
    metadata: dict[str, Any] | None = None,
    level: str = "DEFAULT",
    status_message: str | None = None,
) -> None:
    """Finalise a generation with output, usage, and metadata."""
    if generation is None:
        return
    try:
        generation.end(
            output=output,
            usage=usage,
            metadata=metadata or {},
            level=level,
            status_message=status_message,
        )
        flush_langfuse()
    except Exception as exc:  # pragma: no cover
        logger.debug("Langfuse generation end skipped: %s", exc)


# ---------------------------------------------------------------------------
# Context-manager API (backward-compatible, used by router.py)
# ---------------------------------------------------------------------------
@contextmanager
def start_langfuse_generation(
    *,
    name: str,
    model: str,
    input: Any,
    metadata: dict[str, Any],
    trace_name: str | None = None,
    user_id: str | None = None,
    session_id: str | None = None,
    tags: list[str] | None = None,
) -> Iterator[Any | None]:
    """Context manager that wraps a generation inside an auto-created trace.

    If a trace_id already exists in context (e.g. set by an agent run), the
    generation attaches to the existing trace. Otherwise a new trace is created.
    """
    client = get_langfuse_client()
    if client is None:
        yield None
        return

    try:
        # Reuse or create a trace
        trace_id = get_trace_id()
        if trace_id is None:
            trace_id = new_trace_id()

        trace = client.trace(
            id=trace_id,
            name=trace_name or name,
            user_id=user_id,
            session_id=session_id,
            tags=tags or [],
        )
        generation = trace.generation(
            name=name,
            model=model,
            input=input,
            metadata=metadata,
        )
        yield generation
    except Exception as exc:  # pragma: no cover - best effort only
        logger.warning("Langfuse tracing skipped: %s", exc)
        yield None


def update_langfuse_generation(generation: Any | None, **kwargs: Any) -> None:
    """Update a generation with output/usage/metadata and flush."""
    if generation is None:
        return

    payload = {key: value for key, value in kwargs.items() if value is not None}
    if not payload:
        return

    try:
        generation.end(**payload)
        flush_langfuse()
    except Exception as exc:  # pragma: no cover - best effort only
        logger.debug("Langfuse generation update skipped: %s", exc)


# ---------------------------------------------------------------------------
# Decorator helper for agent-level tracing
# ---------------------------------------------------------------------------
def langfuse_trace_agent(agent_name: str | None = None):
    """Decorator that wraps an agent ``run()`` call in a Langfuse trace.

    Usage::

        @langfuse_trace_agent("my-agent")
        async def run(self, prompt, *, router, **kw):
            ...

    The trace_id is set in context so that any router.send() call inside
    the agent run automatically attaches to the same trace.
    """

    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            client = get_langfuse_client()
            if client is None:
                return await func(*args, **kwargs)

            resolved_name = agent_name
            # Try to get agent name from self if not provided
            if resolved_name is None and args:
                self = args[0]
                resolved_name = getattr(self, "name", None) or type(self).__name__

            trace_id = new_trace_id()
            try:
                # Extract prompt for trace input
                prompt_arg = None
                if len(args) > 1:
                    prompt_arg = args[1]
                elif "prompt" in kwargs:
                    prompt_arg = kwargs["prompt"]
                elif "messages" in kwargs:
                    prompt_arg = kwargs["messages"]

                client.trace(
                    id=trace_id,
                    name=f"agent/{resolved_name}",
                    input=prompt_arg,
                    metadata={"agent": resolved_name},
                    tags=["agent"],
                )
            except Exception as exc:  # pragma: no cover
                logger.debug("Langfuse agent trace skipped: %s", exc)

            try:
                result = await func(*args, **kwargs)
            except Exception:
                raise
            else:
                # Update trace with output
                try:
                    output_content = getattr(result, "content", None)
                    trace = client.trace(id=trace_id)
                    trace.update(output=output_content)
                    flush_langfuse()
                except Exception as exc:  # pragma: no cover
                    logger.debug("Langfuse trace output update skipped: %s", exc)
                return result

        return wrapper

    return decorator
