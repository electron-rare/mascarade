"""Observability helpers for Mascarade.

Includes:
- AgentTraceBuffer / AgentTraceEvent: in-process trace ring buffer
- OTLP log export via schedule_otlp_log
- OpenLLMetry (traceloop-sdk): auto-instruments LLM provider calls (Anthropic,
  OpenAI, Mistral, etc.) via OpenTelemetry. Initialized in server.py at startup.
  Install with: pip install mascarade-core[observability]
- Langfuse: self-hosted LLM tracing with trace correlation, agent/router
  instrumentation. Install with: pip install mascarade-core[langfuse]
"""

from mascarade.observability.agent_trace import (
    AgentTraceBuffer,
    AgentTraceEvent,
    build_trace_message,
    iso_utc_now,
    new_run_id,
)
from mascarade.observability.langfuse import (
    flush_langfuse,
    get_trace_id,
    langfuse_trace_agent,
    langfuse_tracing_configured,
    new_trace_id,
    set_trace_id,
    start_langfuse_generation,
    update_langfuse_generation,
)
from mascarade.observability.openllmetry import init_openllmetry
from mascarade.observability.otel import schedule_otlp_log

__all__ = [
    "AgentTraceBuffer",
    "AgentTraceEvent",
    "build_trace_message",
    "flush_langfuse",
    "get_trace_id",
    "iso_utc_now",
    "langfuse_trace_agent",
    "langfuse_tracing_configured",
    "new_run_id",
    "new_trace_id",
    "init_openllmetry",
    "schedule_otlp_log",
    "set_trace_id",
    "start_langfuse_generation",
    "update_langfuse_generation",
]
