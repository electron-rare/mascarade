"""Structured inter-agent trace events."""

from __future__ import annotations

import asyncio
import json
from collections import deque
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from threading import Lock
from uuid import uuid4

from mascarade.observability.otel import schedule_otlp_log


def iso_utc_now() -> str:
    """Return an ISO8601 UTC timestamp with a stable Z suffix."""
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def new_run_id() -> str:
    """Return a short but collision-resistant run identifier."""
    return uuid4().hex[:16]


def excerpt_text(value: str | None, limit: int = 220) -> str | None:
    """Trim noisy payloads while keeping the log line readable."""
    if value is None:
        return None

    compact = " ".join(value.split())
    if not compact:
        return None
    if len(compact) <= limit:
        return compact
    return f"{compact[: limit - 3]}..."


@dataclass(slots=True)
class AgentTraceEvent:
    """Structured orchestration event used for live inspection."""

    id: str
    ts: str
    run_id: str
    mode: str
    event_type: str
    step: int
    severity: str = "info"
    agent_name: str | None = None
    from_agent: str | None = None
    to_agent: str | None = None
    prompt_excerpt: str | None = None
    content_excerpt: str | None = None
    provider: str | None = None
    model: str | None = None
    routing_role: str | None = None
    routing_provider: str | None = None
    routing_model: str | None = None
    routing_selected_by: str | None = None
    routing_transport: str | None = None
    routing_latency_ms: float | None = None
    mcp_server: str | None = None
    mcp_tool: str | None = None
    mcp_status: str | None = None
    mcp_transport: str | None = None
    mcp_latency_ms: float | None = None
    mcp_protocol_version: str | None = None
    token_usage: dict[str, int] | None = None
    error: str | None = None

    def to_dict(self) -> dict:
        payload = asdict(self)
        payload["message"] = build_trace_message(self)
        return payload


def build_routing_suffix(event: AgentTraceEvent) -> str:
    parts: list[str] = []
    if event.routing_role:
        parts.append(f"role={event.routing_role}")
    if event.routing_provider:
        parts.append(f"provider={event.routing_provider}")
    if event.routing_model:
        parts.append(f"model={event.routing_model}")
    return f" [{', '.join(parts)}]" if parts else ""


def build_trace_message(event: AgentTraceEvent) -> str:
    """Build a compact operator-facing message for a trace event."""
    if event.event_type == "run_started":
        return f"run {event.run_id} started in {event.mode} mode" + (
            f" with {event.agent_name}" if event.agent_name else ""
        )
    if event.event_type == "step_started":
        return (
            f"step {event.step:02d} started for {event.agent_name or 'unknown-agent'}"
            + build_routing_suffix(event)
        )
    if event.event_type == "agent_input":
        return (
            f"{event.agent_name or 'agent'} received input"
            + (f' "{event.prompt_excerpt}"' if event.prompt_excerpt else "")
            + build_routing_suffix(event)
        )
    if event.event_type == "agent_output":
        summary = f"{event.agent_name or 'agent'} returned output"
        if event.provider or event.model:
            summary += f" via {event.provider or 'provider'}:{event.model or 'model'}"
        if event.routing_selected_by:
            summary += f" [{event.routing_selected_by}]"
        if event.routing_transport:
            summary += f" [{event.routing_transport}"
            if event.routing_latency_ms is not None:
                summary += f" {event.routing_latency_ms:.0f} ms"
            summary += "]"
        if event.content_excerpt:
            summary += f' "{event.content_excerpt}"'
        return summary
    if event.event_type == "handoff":
        return f"{event.from_agent or 'agent'} -> {event.to_agent or 'agent'} handoff" + (
            f' "{event.content_excerpt}"' if event.content_excerpt else ""
        )
    if event.event_type == "run_completed":
        return f"run {event.run_id} completed"
    if event.event_type == "run_failed":
        return f"run {event.run_id} failed" + (f" ({event.error})" if event.error else "")
    if event.event_type == "mcp_call_started":
        return f"MCP {event.mcp_server or 'server'}::{event.mcp_tool or 'tool'} started"
    if event.event_type == "mcp_call_completed":
        suffix = f" ({event.mcp_latency_ms:.1f} ms)" if event.mcp_latency_ms is not None else ""
        return f"MCP {event.mcp_server or 'server'}::{event.mcp_tool or 'tool'} completed{suffix}"
    if event.event_type == "mcp_call_failed":
        detail = f" ({event.error})" if event.error else ""
        return f"MCP {event.mcp_server or 'server'}::{event.mcp_tool or 'tool'} failed{detail}"
    return event.content_excerpt or event.prompt_excerpt or event.event_type


@dataclass(slots=True)
class _TraceSubscription:
    token: int
    queue: asyncio.Queue[AgentTraceEvent]
    run_id: str | None = None
    agent_name: str | None = None
    event_type: str | None = None

    def matches(self, event: AgentTraceEvent) -> bool:
        if self.run_id and event.run_id != self.run_id:
            return False
        if self.agent_name and event.agent_name != self.agent_name:
            return False
        if self.event_type and event.event_type != self.event_type:
            return False
        return True


@dataclass
class AgentTraceBuffer:
    """In-memory recent trace buffer with lightweight live subscriptions."""

    max_events: int = 4000
    _events: deque[AgentTraceEvent] = field(init=False, repr=False)
    _subscriptions: dict[int, _TraceSubscription] = field(
        init=False,
        default_factory=dict,
        repr=False,
    )
    _lock: Lock = field(init=False, default_factory=Lock, repr=False)
    _token: int = field(init=False, default=0, repr=False)

    def __post_init__(self) -> None:
        self._events = deque(maxlen=self.max_events)

    def emit(self, event: AgentTraceEvent) -> AgentTraceEvent:
        payload = event.to_dict()
        structured_log = {
            "source": "agent-trace",
            "service": "core",
            "severity": event.severity,
            "message": payload["message"],
            "run_id": event.run_id,
            "agent_name": event.agent_name,
            "from_agent": event.from_agent,
            "to_agent": event.to_agent,
            "event_type": event.event_type,
            "mode": event.mode,
            "provider": event.provider,
            "model": event.model,
            "routing_role": event.routing_role,
            "routing_provider": event.routing_provider,
            "routing_model": event.routing_model,
            "routing_selected_by": event.routing_selected_by,
            "routing_transport": event.routing_transport,
            "routing_latency_ms": event.routing_latency_ms,
            "mcp_server": event.mcp_server,
            "mcp_tool": event.mcp_tool,
            "mcp_status": event.mcp_status,
            "mcp_transport": event.mcp_transport,
            "mcp_latency_ms": event.mcp_latency_ms,
            "mcp_protocol_version": event.mcp_protocol_version,
            "ts": event.ts,
        }
        print(json.dumps(structured_log, ensure_ascii=True), flush=True)
        schedule_otlp_log(
            service_name="mascarade-core",
            body=payload["message"],
            severity=event.severity,
            attributes={
                "source": "agent-trace",
                "run_id": event.run_id,
                "agent_name": event.agent_name or "",
                "event_type": event.event_type,
                "mode": event.mode,
                "provider": event.provider or "",
                "model": event.model or "",
                "routing_role": event.routing_role or "",
                "routing_provider": event.routing_provider or "",
                "routing_model": event.routing_model or "",
                "routing_selected_by": event.routing_selected_by or "",
                "routing_transport": event.routing_transport or "",
                "routing_latency_ms": (
                    str(event.routing_latency_ms)
                    if event.routing_latency_ms is not None
                    else ""
                ),
                "mcp_server": event.mcp_server or "",
                "mcp_tool": event.mcp_tool or "",
                "mcp_status": event.mcp_status or "",
                "mcp_transport": event.mcp_transport or "",
                "mcp_protocol_version": event.mcp_protocol_version or "",
            },
        )

        with self._lock:
            self._events.append(event)
            subscriptions = list(self._subscriptions.values())

        for subscription in subscriptions:
            if not subscription.matches(event):
                continue
            try:
                subscription.queue.put_nowait(event)
            except asyncio.QueueFull:
                try:
                    subscription.queue.get_nowait()
                except asyncio.QueueEmpty:
                    pass
                try:
                    subscription.queue.put_nowait(event)
                except asyncio.QueueFull:
                    continue

        return event

    def record(
        self,
        *,
        run_id: str,
        mode: str,
        event_type: str,
        step: int,
        severity: str = "info",
        agent_name: str | None = None,
        from_agent: str | None = None,
        to_agent: str | None = None,
        prompt_excerpt: str | None = None,
        content_excerpt: str | None = None,
        provider: str | None = None,
        model: str | None = None,
        routing_role: str | None = None,
        routing_provider: str | None = None,
        routing_model: str | None = None,
        routing_selected_by: str | None = None,
        routing_transport: str | None = None,
        routing_latency_ms: float | None = None,
        mcp_server: str | None = None,
        mcp_tool: str | None = None,
        mcp_status: str | None = None,
        mcp_transport: str | None = None,
        mcp_latency_ms: float | None = None,
        mcp_protocol_version: str | None = None,
        token_usage: dict[str, int] | None = None,
        error: str | None = None,
    ) -> AgentTraceEvent:
        event = AgentTraceEvent(
            id=uuid4().hex,
            ts=iso_utc_now(),
            run_id=run_id,
            mode=mode,
            event_type=event_type,
            step=step,
            severity=severity,
            agent_name=agent_name,
            from_agent=from_agent,
            to_agent=to_agent,
            prompt_excerpt=excerpt_text(prompt_excerpt),
            content_excerpt=excerpt_text(content_excerpt),
            provider=provider,
            model=model,
            routing_role=excerpt_text(routing_role, limit=120),
            routing_provider=excerpt_text(routing_provider, limit=120),
            routing_model=excerpt_text(routing_model, limit=160),
            routing_selected_by=excerpt_text(routing_selected_by, limit=80),
            routing_transport=excerpt_text(routing_transport, limit=80),
            routing_latency_ms=routing_latency_ms,
            mcp_server=excerpt_text(mcp_server, limit=120),
            mcp_tool=excerpt_text(mcp_tool, limit=160),
            mcp_status=excerpt_text(mcp_status, limit=80),
            mcp_transport=excerpt_text(mcp_transport, limit=80),
            mcp_latency_ms=mcp_latency_ms,
            mcp_protocol_version=excerpt_text(mcp_protocol_version, limit=80),
            token_usage=token_usage,
            error=excerpt_text(error),
        )
        return self.emit(event)

    def recent(
        self,
        *,
        limit: int = 50,
        run_id: str | None = None,
        agent_name: str | None = None,
        event_type: str | None = None,
    ) -> list[AgentTraceEvent]:
        with self._lock:
            events = list(self._events)

        filtered = [
            event
            for event in events
            if (not run_id or event.run_id == run_id)
            and (not agent_name or event.agent_name == agent_name)
            and (not event_type or event.event_type == event_type)
        ]
        return filtered[-max(1, limit) :]

    def run_events(self, run_id: str, *, limit: int = 200) -> list[AgentTraceEvent]:
        return self.recent(limit=limit, run_id=run_id)

    def subscribe(
        self,
        *,
        run_id: str | None = None,
        agent_name: str | None = None,
        event_type: str | None = None,
        max_queue_size: int = 256,
    ) -> tuple[asyncio.Queue[AgentTraceEvent], Callable[[], None]]:
        queue: asyncio.Queue[AgentTraceEvent] = asyncio.Queue(maxsize=max_queue_size)
        with self._lock:
            self._token += 1
            token = self._token
            self._subscriptions[token] = _TraceSubscription(
                token=token,
                queue=queue,
                run_id=run_id,
                agent_name=agent_name,
                event_type=event_type,
            )

        def unsubscribe() -> None:
            with self._lock:
                self._subscriptions.pop(token, None)

        return queue, unsubscribe
