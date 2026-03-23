"""Observability helpers for Mascarade.

Includes:
- AgentTraceBuffer / AgentTraceEvent: in-process trace ring buffer
- OTLP log export via schedule_otlp_log
- OpenLLMetry (traceloop-sdk): auto-instruments LLM provider calls (Anthropic,
  OpenAI, Mistral, etc.) via OpenTelemetry. Initialized in server.py at startup.
  Install with: pip install mascarade-core[observability]
"""

from mascarade.observability.agent_trace import (
    AgentTraceBuffer,
    AgentTraceEvent,
    build_trace_message,
    iso_utc_now,
    new_run_id,
)
from mascarade.observability.otel import schedule_otlp_log

__all__ = [
    "AgentTraceBuffer",
    "AgentTraceEvent",
    "build_trace_message",
    "iso_utc_now",
    "new_run_id",
    "schedule_otlp_log",
]
