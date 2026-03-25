"""OTLP HTTP log/trace export — compatible with Cowork (Claude Agent SDK) and Grafana Cloud.

Supports:
- Standard OTLP HTTP/protobuf log export
- Cowork/Claude Code event schema (prompt, tool_result, api_request, api_error)
- Bearer token auth via OTEL_EXPORTER_HEADERS
- Custom resource attributes for team/org tagging
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid

import httpx

from mascarade.config import settings

logger = logging.getLogger("mascarade.observability.otel")


def _severity_number(severity: str) -> int:
    normalized = severity.lower()
    if normalized == "debug":
        return 5
    if normalized == "info":
        return 9
    if normalized == "warning":
        return 13
    if normalized == "error":
        return 17
    if normalized == "critical":
        return 21
    return 9


def _parse_headers(headers_str: str) -> dict[str, str]:
    """Parse 'Key=Value,Key2=Value2' format into dict."""
    if not headers_str:
        return {}
    result = {}
    for pair in headers_str.split(","):
        if "=" in pair:
            key, _, value = pair.partition("=")
            result[key.strip()] = value.strip()
    return result


def _resource_attributes() -> list[dict]:
    """Build OTLP resource attributes from config."""
    attrs = [
        {"key": "service.name", "value": {"stringValue": settings.otel_service_name}},
        {"key": "service.version", "value": {"stringValue": "0.1.0"}},
    ]
    extra = settings.otel_resource_attributes
    if extra:
        for pair in extra.split(","):
            if "=" in pair:
                key, _, value = pair.partition("=")
                attrs.append(
                    {"key": key.strip(), "value": {"stringValue": value.strip()}}
                )
    return attrs


async def _post_otlp_log(
    *,
    service_name: str | None = None,
    body: str,
    severity: str,
    attributes: dict[str, str],
) -> None:
    endpoint = settings.otel_collector_http_endpoint.rstrip("/")
    if not endpoint:
        return

    now_ns = str(time.time_ns())
    resource_attrs = _resource_attributes()
    if service_name and service_name != settings.otel_service_name:
        resource_attrs = [
            a for a in resource_attrs if a["key"] != "service.name"
        ]
        resource_attrs.insert(
            0, {"key": "service.name", "value": {"stringValue": service_name}}
        )

    payload = {
        "resourceLogs": [
            {
                "resource": {"attributes": resource_attrs},
                "scopeLogs": [
                    {
                        "scope": {"name": "mascarade"},
                        "logRecords": [
                            {
                                "timeUnixNano": now_ns,
                                "severityText": severity.upper(),
                                "severityNumber": _severity_number(severity),
                                "body": {"stringValue": body},
                                "attributes": [
                                    {"key": key, "value": {"stringValue": str(value)}}
                                    for key, value in attributes.items()
                                    if value is not None
                                ],
                            }
                        ],
                    }
                ],
            }
        ]
    }

    headers = {"Content-Type": "application/json"}
    headers.update(_parse_headers(settings.otel_exporter_headers))

    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            await client.post(f"{endpoint}/v1/logs", json=payload, headers=headers)
    except Exception as exc:
        logger.debug("OTLP export skipped: %s", exc)


def schedule_otlp_log(
    *,
    service_name: str | None = None,
    body: str,
    severity: str,
    attributes: dict[str, str],
) -> None:
    """Schedule an OTLP log export (fire-and-forget)."""
    if not settings.otel_enabled:
        return

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return

    loop.create_task(
        _post_otlp_log(
            service_name=service_name,
            body=body,
            severity=severity,
            attributes=attributes,
        )
    )


# ── Cowork / Claude Code compatible event emitters ──


def emit_agent_prompt(
    *,
    prompt_id: str | None = None,
    session_id: str | None = None,
    agent_name: str,
    prompt_length: int,
) -> None:
    """Emit a user prompt event (claude_code.user_prompt schema)."""
    schedule_otlp_log(
        body=f"Agent prompt: {agent_name}",
        severity="info",
        attributes={
            "event.type": "mascarade.agent_prompt",
            "prompt.id": prompt_id or str(uuid.uuid4()),
            "session.id": session_id or "",
            "agent.name": agent_name,
            "prompt_length": str(prompt_length),
        },
    )


def emit_tool_result(
    *,
    prompt_id: str,
    tool_name: str,
    success: bool,
    duration_ms: float,
) -> None:
    """Emit a tool execution result (claude_code.tool_result schema)."""
    schedule_otlp_log(
        body=f"Tool result: {tool_name} {'ok' if success else 'error'}",
        severity="info" if success else "error",
        attributes={
            "event.type": "mascarade.tool_result",
            "prompt.id": prompt_id,
            "tool_name": tool_name,
            "success": str(success).lower(),
            "duration_ms": f"{duration_ms:.1f}",
        },
    )


def emit_api_request(
    *,
    prompt_id: str,
    provider: str,
    model: str,
    input_tokens: int,
    output_tokens: int,
    duration_ms: float,
    cost_usd: float = 0.0,
) -> None:
    """Emit an LLM API request event (claude_code.api_request schema)."""
    schedule_otlp_log(
        body=f"API request: {provider}/{model}",
        severity="info",
        attributes={
            "event.type": "mascarade.api_request",
            "prompt.id": prompt_id,
            "provider": provider,
            "model": model,
            "input_tokens": str(input_tokens),
            "output_tokens": str(output_tokens),
            "duration_ms": f"{duration_ms:.1f}",
            "cost_usd": f"{cost_usd:.6f}",
        },
    )


def emit_api_error(
    *,
    prompt_id: str,
    provider: str,
    model: str,
    error: str,
    status_code: int = 0,
    duration_ms: float = 0.0,
) -> None:
    """Emit an LLM API error event (claude_code.api_error schema)."""
    schedule_otlp_log(
        body=f"API error: {provider}/{model} — {error}",
        severity="error",
        attributes={
            "event.type": "mascarade.api_error",
            "prompt.id": prompt_id,
            "provider": provider,
            "model": model,
            "error": error,
            "status_code": str(status_code),
            "duration_ms": f"{duration_ms:.1f}",
        },
    )


def emit_routing_decision(
    *,
    prompt_id: str,
    strategy: str,
    selected_provider: str,
    selected_model: str,
    candidates: int,
    duration_ms: float,
) -> None:
    """Emit a routing decision event (mascarade-specific)."""
    schedule_otlp_log(
        body=f"Route: {strategy} → {selected_provider}/{selected_model}",
        severity="info",
        attributes={
            "event.type": "mascarade.routing_decision",
            "prompt.id": prompt_id,
            "strategy": strategy,
            "selected_provider": selected_provider,
            "selected_model": selected_model,
            "candidates": str(candidates),
            "duration_ms": f"{duration_ms:.1f}",
        },
    )
