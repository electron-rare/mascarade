"""Best-effort OTLP HTTP log export for observability complements."""

from __future__ import annotations

import asyncio
import logging
import time

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


async def _post_otlp_log(
    *,
    service_name: str,
    body: str,
    severity: str,
    attributes: dict[str, str],
) -> None:
    endpoint = settings.otel_collector_http_endpoint.rstrip("/")
    if not endpoint:
        return

    now_ns = str(time.time_ns())
    payload = {
        "resourceLogs": [
            {
                "resource": {
                    "attributes": [
                        {"key": "service.name", "value": {"stringValue": service_name}},
                    ]
                },
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
                                    {"key": key, "value": {"stringValue": value}}
                                    for key, value in attributes.items()
                                    if value
                                ],
                            }
                        ],
                    }
                ],
            }
        ]
    }

    try:
        async with httpx.AsyncClient(timeout=1.2) as client:
            await client.post(f"{endpoint}/v1/logs", json=payload)
    except Exception as exc:  # pragma: no cover - best effort only
        logger.debug("OTLP export skipped: %s", exc)


def schedule_otlp_log(
    *,
    service_name: str,
    body: str,
    severity: str,
    attributes: dict[str, str],
) -> None:
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
