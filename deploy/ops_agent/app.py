from __future__ import annotations

import asyncio
import json
import os
import re
import shutil
from collections import deque
from datetime import UTC, datetime
from typing import Any

import httpx
from fastapi import FastAPI, Query, Request
from fastapi.responses import StreamingResponse

app = FastAPI(title="Mascarade Ops Agent", version="0.1.0")

DOCKER_SOCKET_PATH = "/var/run/docker.sock"
LOKI_URL = (os.getenv("LOKI_URL") or "http://loki:3100").rstrip("/")
AGENTSIGHT_URL = (os.getenv("AGENTSIGHT_URL") or "").rstrip("/")

SEVERITY_RE = [
    (re.compile(r"\b(critical|fatal|panic)\b", re.I), "critical"),
    (re.compile(r"\b(error|exception|traceback|failed)\b", re.I), "error"),
    (re.compile(r"\b(warn|warning)\b", re.I), "warning"),
    (re.compile(r"\b(debug|trace)\b", re.I), "debug"),
]


def iso_utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def to_iso(value: str | None) -> str:
    if not value:
        return iso_utc_now()
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC).isoformat().replace("+00:00", "Z")
    except ValueError:
        return iso_utc_now()


def infer_severity(message: str) -> str:
    for pattern, severity in SEVERITY_RE:
        if pattern.search(message):
            return severity
    return "info"


def severity_rank(severity: str) -> int:
    if severity == "debug":
        return 10
    if severity == "info":
        return 20
    if severity == "warning":
        return 30
    if severity == "error":
        return 40
    if severity == "critical":
        return 50
    return 20


def parse_csv_set(value: str | None) -> set[str]:
    return {token.strip() for token in (value or "").split(",") if token.strip()}


def sse_frame(event: str, payload: Any) -> str:
    return f"event: {event}\ndata: {json.dumps(payload)}\n\n"


def remember_entry(
    entry_id: str,
    seen_ids: set[str],
    seen_order: deque[str],
    max_entries: int = 4000,
) -> None:
    seen_ids.add(entry_id)
    seen_order.append(entry_id)
    while len(seen_order) > max_entries:
        stale_id = seen_order.popleft()
        seen_ids.discard(stale_id)


def select_new_entries(
    entries: list[dict[str, Any]],
    *,
    seen_ids: set[str],
    seen_order: deque[str],
    service_filter: set[str],
    min_severity: str,
) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    minimum_rank = severity_rank(min_severity)

    for entry in sorted(entries, key=lambda item: str(item.get("ts", ""))):
        entry_id = str(entry.get("id") or "")
        if not entry_id or entry_id in seen_ids:
            continue

        source = str(entry.get("source") or "")
        service = str(entry.get("service") or "")
        if service_filter and source != "machine" and service not in service_filter:
            continue

        severity = str(entry.get("severity") or "info")
        if severity_rank(severity) < minimum_rank:
            continue

        remember_entry(entry_id, seen_ids, seen_order)
        selected.append(entry)

    return selected


def demux_docker_log_bytes(payload: bytes) -> list[str]:
    if not payload:
        return []

    if len(payload) >= 8 and payload[0] in (1, 2, 3):
        lines: list[str] = []
        offset = 0
        size = len(payload)
        while offset + 8 <= size:
            length = int.from_bytes(payload[offset + 4 : offset + 8], byteorder="big")
            chunk_start = offset + 8
            chunk_end = chunk_start + length
            if chunk_end > size:
                break
            chunk = payload[chunk_start:chunk_end].decode("utf-8", errors="replace")
            lines.extend(chunk.splitlines())
            offset = chunk_end
        return [line for line in lines if line.strip()]

    text = payload.decode("utf-8", errors="replace")
    return [line for line in text.splitlines() if line.strip()]


def parse_timestamped_line(line: str) -> tuple[str, str]:
    if " " not in line:
        return iso_utc_now(), line
    head, tail = line.split(" ", 1)
    if "T" in head and (head.endswith("Z") or "+" in head):
        return to_iso(head), tail.strip()
    return iso_utc_now(), line.strip()


async def docker_client() -> httpx.AsyncClient:
    transport = httpx.AsyncHTTPTransport(uds=DOCKER_SOCKET_PATH)
    return httpx.AsyncClient(transport=transport, base_url="http://docker", timeout=5.0)


async def docker_available() -> bool:
    if not os.path.exists(DOCKER_SOCKET_PATH):
        return False
    try:
        async with await docker_client() as client:
            response = await client.get("/_ping")
        return response.status_code == 200
    except Exception:
        return False


async def list_containers() -> list[dict[str, Any]]:
    async with await docker_client() as client:
        response = await client.get("/containers/json", params={"all": 0})
        response.raise_for_status()
        return response.json()


def service_name(container: dict[str, Any]) -> str:
    labels = container.get("Labels") or {}
    compose_name = labels.get("com.docker.compose.service")
    if compose_name:
        return compose_name
    names = container.get("Names") or []
    if names:
        return names[0].lstrip("/")
    return container.get("Id", "unknown")[:12]


def event_service_name(payload: dict[str, Any]) -> str:
    actor = payload.get("Actor") or {}
    attributes = actor.get("Attributes") or {}
    compose_name = attributes.get("com.docker.compose.service")
    if compose_name:
        return str(compose_name)
    name = attributes.get("name")
    if name:
        return str(name)
    container_id = actor.get("ID") or payload.get("id")
    if container_id:
        return str(container_id)[:12]
    return "docker"


async def fetch_container_logs(container_id: str, tail: int) -> list[str]:
    async with await docker_client() as client:
        response = await client.get(
            f"/containers/{container_id}/logs",
            params={
                "stdout": 1,
                "stderr": 1,
                "timestamps": 1,
                "tail": tail,
            },
        )
        response.raise_for_status()
        return demux_docker_log_bytes(response.content)


async def recent_docker_events(limit: int, since_seconds: int = 900) -> list[dict[str, Any]]:
    if not await docker_available():
        return []

    until = int(datetime.now(UTC).timestamp())
    since = max(0, until - max(30, since_seconds))

    async with await docker_client() as client:
        response = await client.get(
            "/events",
            params={
                "since": since,
                "until": until,
            },
        )
        response.raise_for_status()

    events: list[dict[str, Any]] = []
    for raw_line in response.text.splitlines():
        if not raw_line.strip():
            continue
        try:
            payload = json.loads(raw_line)
        except json.JSONDecodeError:
            continue

        event_ts = payload.get("timeNano") or payload.get("time")
        if isinstance(event_ts, (int, float)):
            divisor = 1_000_000_000 if payload.get("timeNano") else 1
            ts = datetime.fromtimestamp(float(event_ts) / divisor, tz=UTC).isoformat().replace("+00:00", "Z")
        else:
            ts = iso_utc_now()

        action = str(payload.get("Action") or payload.get("status") or "event")
        event_type = str(payload.get("Type") or "docker")
        service = event_service_name(payload)
        severity = "info"
        lowered_action = action.lower()
        if lowered_action in {"oom", "die", "kill"}:
            severity = "error"
        elif lowered_action in {"restart", "stop", "pause"}:
            severity = "warning"

        events.append(
            {
                "id": f"docker-event:{ts}:{len(events)}",
                "ts": ts,
                "source": "docker-event",
                "service": service,
                "severity": severity,
                "message": f"{event_type} {service} {action}",
                "labels": {
                    "action": action,
                    "type": event_type,
                    "actor_id": str((payload.get("Actor") or {}).get("ID") or payload.get("id") or "")[:12],
                },
            }
        )

    return sorted(events, key=lambda event: event["ts"], reverse=True)[:limit]


def journal_dirs() -> list[str]:
    return [path for path in ("/var/log/journal", "/run/log/journal") if os.path.isdir(path)]


def journalctl_available() -> bool:
    return shutil.which("journalctl") is not None and bool(journal_dirs())


async def recent_journal_logs(limit: int) -> list[dict[str, Any]]:
    if not journalctl_available():
        return []

    directory = journal_dirs()[0]
    process = await asyncio.create_subprocess_exec(
        "journalctl",
        f"--directory={directory}",
        "--no-pager",
        "-n",
        str(limit),
        "-o",
        "json",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, _stderr = await process.communicate()
    if process.returncode != 0:
        return []

    entries: list[dict[str, Any]] = []
    for raw_line in stdout.decode("utf-8", errors="replace").splitlines():
        if not raw_line.strip():
            continue
        try:
            payload = json.loads(raw_line)
        except json.JSONDecodeError:
            continue
        timestamp_us = payload.get("__REALTIME_TIMESTAMP")
        if timestamp_us:
            ts = datetime.fromtimestamp(int(timestamp_us) / 1_000_000, tz=UTC).isoformat().replace("+00:00", "Z")
        else:
            ts = iso_utc_now()
        priority = str(payload.get("PRIORITY", "6"))
        severity = {
            "0": "critical",
            "1": "critical",
            "2": "critical",
            "3": "error",
            "4": "warning",
            "5": "info",
            "6": "info",
            "7": "debug",
        }.get(priority, "info")
        message = str(payload.get("MESSAGE", "")).strip()
        if not message:
            continue
        entries.append(
            {
                "id": f"journal:{ts}:{len(entries)}",
                "ts": ts,
                "source": "machine",
                "service": payload.get("_SYSTEMD_UNIT") or payload.get("SYSLOG_IDENTIFIER") or "system",
                "severity": severity,
                "message": message,
                "labels": {
                    "host": str(payload.get("_HOSTNAME", "")),
                    "priority": priority,
                },
            }
        )
    return entries


async def agentsight_available() -> bool:
    if not AGENTSIGHT_URL:
        return False
    try:
        async with httpx.AsyncClient(timeout=1.2) as client:
            response = await client.get(f"{AGENTSIGHT_URL}/health")
        return response.is_success
    except Exception:
        return False


async def loki_available() -> bool:
    try:
        async with httpx.AsyncClient(timeout=1.2) as client:
            response = await client.get(f"{LOKI_URL}/ready")
        return response.is_success
    except Exception:
        return False


def gpu_available() -> bool:
    return shutil.which("nvidia-smi") is not None


@app.get("/health")
async def health():
    docker_ok = await docker_available()
    return {
        "status": "ok",
        "docker": docker_ok,
        "journald": journalctl_available(),
        "gpu": gpu_available(),
    }


@app.get("/sources")
async def sources():
    return {
        "docker_logs": {"available": await docker_available(), "kind": "docker-api"},
        "docker_events": {"available": await docker_available(), "kind": "docker-api-events"},
        "journald": {"available": journalctl_available(), "kind": "journalctl"},
        "gpu": {"available": gpu_available(), "kind": "nvidia-smi"},
        "loki": {"available": await loki_available(), "kind": "loki"},
        "agentsight": {
            "available": await agentsight_available(),
            "kind": "optional-complement",
        },
    }


@app.get("/summary")
async def summary():
    docker_ok = await docker_available()
    containers = await list_containers() if docker_ok else []
    recent = await logs_recent(limit=40, include_services=True, include_machine=True)
    events = await recent_docker_events(limit=20) if docker_ok else []
    return {
        "timestamp": iso_utc_now(),
        "container_count": len(containers),
        "services": sorted(service_name(container) for container in containers),
        "recent": recent,
        "events": events,
        "sources": await sources(),
    }


@app.get("/events/recent")
async def events_recent(
    limit: int = Query(default=40, ge=1, le=200),
    since_seconds: int = Query(default=900, ge=30, le=86400),
):
    events = await recent_docker_events(limit=limit, since_seconds=since_seconds)
    return {
        "events": events,
        "count": len(events),
        "timestamp": iso_utc_now(),
    }


@app.get("/logs/recent")
async def logs_recent(
    limit: int = Query(default=120, ge=1, le=500),
    services: str | None = Query(default=None),
    include_services: bool = Query(default=True),
    include_machine: bool = Query(default=True),
):
    service_filter = {token.strip() for token in (services or "").split(",") if token.strip()}
    entries: list[dict[str, Any]] = []

    if include_services and await docker_available():
        containers = await list_containers()
        selected = [
            container
            for container in containers
            if not service_filter or service_name(container) in service_filter
        ]
        per_container_tail = max(10, min(limit, 60))
        for container in selected:
            svc = service_name(container)
            for idx, line in enumerate(await fetch_container_logs(container["Id"], per_container_tail)):
                ts, message = parse_timestamped_line(line)
                entries.append(
                    {
                        "id": f"service:{svc}:{ts}:{idx}",
                        "ts": ts,
                        "source": "service",
                        "service": svc,
                        "severity": infer_severity(message),
                        "message": message,
                        "labels": {
                            "container_id": str(container.get("Id", ""))[:12],
                        },
                    }
                )

    if include_machine:
        entries.extend(await recent_journal_logs(min(limit, 120)))

    entries = sorted(entries, key=lambda entry: entry["ts"], reverse=True)[:limit]
    return {
        "entries": entries,
        "count": len(entries),
        "timestamp": iso_utc_now(),
    }


@app.get("/logs/stream")
async def logs_stream(
    request: Request,
    services: str | None = Query(default=None),
    include_services: bool = Query(default=True),
    include_machine: bool = Query(default=True),
    include_events: bool = Query(default=True),
    severity: str = Query(default="info"),
    backfill: int = Query(default=40, ge=0, le=200),
    poll_interval_ms: int = Query(default=1200, ge=250, le=10000),
):
    service_filter = parse_csv_set(services)
    min_severity = severity.strip().lower() or "info"

    async def collect_entries(limit: int, since_seconds: int) -> list[dict[str, Any]]:
        payload = await logs_recent(
            limit=limit,
            services=services,
            include_services=include_services,
            include_machine=include_machine,
        )
        entries = list(payload.get("entries", []))
        if include_events:
            entries.extend(await recent_docker_events(limit=max(10, min(limit, 80)), since_seconds=since_seconds))
        return entries

    async def event_stream():
        seen_ids: set[str] = set()
        seen_order: deque[str] = deque()
        heartbeat_deadline = asyncio.get_running_loop().time() + 15

        if backfill > 0:
            for entry in select_new_entries(
                await collect_entries(backfill, max(30, backfill * 2)),
                seen_ids=seen_ids,
                seen_order=seen_order,
                service_filter=service_filter,
                min_severity=min_severity,
            ):
                yield sse_frame("log", entry)

        while True:
            if await request.is_disconnected():
                break

            emitted = False
            window_seconds = max(30, int((poll_interval_ms / 1000) * 20))
            batch = await collect_entries(max(backfill, 60), window_seconds)
            for entry in select_new_entries(
                batch,
                seen_ids=seen_ids,
                seen_order=seen_order,
                service_filter=service_filter,
                min_severity=min_severity,
            ):
                emitted = True
                yield sse_frame("log", entry)

            now = asyncio.get_running_loop().time()
            if emitted:
                heartbeat_deadline = now + 15
            elif now >= heartbeat_deadline:
                heartbeat_deadline = now + 15
                yield sse_frame("heartbeat", {"ts": iso_utc_now()})

            await asyncio.sleep(poll_interval_ms / 1000)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
