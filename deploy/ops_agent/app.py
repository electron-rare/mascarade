from __future__ import annotations

import asyncio
import hmac
import json
import os
import re
import secrets
import shutil
import time
from collections import deque
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import Response, StreamingResponse
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from pydantic import BaseModel, Field
from mascarade.provider_admin import resolve_provider_meta, valid_provider_envs

app = FastAPI(title="Mascarade Ops Agent", version="0.1.0")

HTTP_REQUESTS_TOTAL = Counter(
    "ops_agent_http_requests_total",
    "Total HTTP requests served by the ops-agent.",
    ["method", "path", "status"],
)
HTTP_REQUEST_DURATION_SECONDS = Histogram(
    "ops_agent_http_request_duration_seconds",
    "HTTP request latency for the ops-agent.",
    ["method", "path"],
)

DOCKER_SOCKET_PATH = "/var/run/docker.sock"
LOKI_URL = (os.getenv("LOKI_URL") or "http://loki:3100").rstrip("/")
AGENTSIGHT_URL = (os.getenv("AGENTSIGHT_URL") or "").rstrip("/")
KILL_LIFE_ROOT = Path(os.getenv("KILL_LIFE_ROOT") or "/home/clems/Kill_LIFE").resolve()
MASCARADE_ROOT = Path(os.getenv("MASCARADE_DIR") or "/home/clems/mascarade").resolve()
MASCARADE_ENV_FILE = Path(
    os.getenv("MASCARADE_ENV_FILE") or MASCARADE_ROOT / ".env"
).resolve()
MASCARADE_COMPOSE_FILE = Path(
    os.getenv("MASCARADE_COMPOSE_FILE") or MASCARADE_ROOT / "docker-compose.yml"
).resolve()
OPS_AGENT_API_KEY_COOKIE = "mascarade_key"
OPS_MCP_PROBE_CACHE_TTL_MS = max(
    1.0,
    (float(os.getenv("OPS_MCP_PROBE_CACHE_TTL_MS") or "15000") or 15000.0) / 1000.0,
)
DOCKER_COMPOSE_PLUGIN_CANDIDATES = [
    Path("/usr/libexec/docker/cli-plugins/docker-compose"),
    Path("/usr/local/libexec/docker/cli-plugins/docker-compose"),
    Path("/usr/lib/docker/cli-plugins/docker-compose"),
]
ENV_ASSIGN_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)=(.*)$")


@app.middleware("http")
async def instrument_http_requests(request: Request, call_next):
    path = request.url.path
    method = request.method
    start = time.perf_counter()
    status = 500
    try:
        response = await call_next(request)
        status = response.status_code
        return response
    finally:
        duration = max(0.0, time.perf_counter() - start)
        HTTP_REQUESTS_TOTAL.labels(method=method, path=path, status=str(status)).inc()
        HTTP_REQUEST_DURATION_SECONDS.labels(method=method, path=path).observe(duration)


RUNTIME_SECRET_GROUPS: dict[str, dict[str, Any]] = {
    "auth": {
        "label": "Mascarade auth",
        "description": "Controle le Bearer token de l'API, du core et de l'ops-agent.",
        "classification": "runtime-auth",
        "criticality": "required-security",
        "required_when": "Toujours requis pour un runtime protege.",
        "used_by": ["api", "core", "ops-agent"],
        "generate_supported": True,
        "fields": [
            {
                "env": "MASCARADE_API_KEY",
                "label": "Mascarade API key",
                "secret": True,
                "restart_services": ["core"],
            }
        ],
    },
    "notion": {
        "label": "Notion MCP",
        "description": "Auth Notion runtime et page de smoke test utilisee par les probes MCP.",
        "classification": "integration-credential",
        "criticality": "feature-required",
        "required_when": "Requis seulement si l'integration Notion est utilisee.",
        "used_by": ["core", "ops-agent"],
        "generate_supported": False,
        "auth_mode": {
            "env": "NOTION_AUTH_MODE",
            "default": "api_key",
            "options": ["api_key", "oauth_oidc"],
        },
        "fields": [
            {
                "env": "NOTION_API_KEY",
                "label": "Notion API key",
                "secret": True,
                "restart_services": ["core"],
                "auth_modes": ["api_key"],
                "classification": "integration-credential",
            },
            {
                "env": "NOTION_OAUTH_ACCESS_TOKEN",
                "label": "OAuth access token",
                "secret": True,
                "restart_services": ["core"],
                "auth_modes": ["oauth_oidc"],
                "classification": "integration-credential",
            },
            {
                "env": "NOTION_OAUTH_REFRESH_TOKEN",
                "label": "OAuth refresh token",
                "secret": True,
                "restart_services": ["core"],
                "auth_modes": ["oauth_oidc"],
                "classification": "integration-credential",
            },
            {
                "env": "NOTION_OAUTH_CLIENT_ID",
                "label": "OAuth client ID",
                "secret": False,
                "restart_services": [],
                "auth_modes": ["oauth_oidc"],
                "classification": "oauth-config",
            },
            {
                "env": "NOTION_OAUTH_CLIENT_SECRET",
                "label": "OAuth client secret",
                "secret": True,
                "restart_services": [],
                "auth_modes": ["oauth_oidc"],
                "classification": "integration-credential",
            },
            {
                "env": "NOTION_OAUTH_AUTHORIZATION_ENDPOINT",
                "label": "OAuth authorization endpoint",
                "secret": False,
                "restart_services": [],
                "auth_modes": ["oauth_oidc"],
                "classification": "oauth-config",
                "criticality": "local-operator-context",
            },
            {
                "env": "NOTION_OAUTH_TOKEN_ENDPOINT",
                "label": "OAuth token endpoint",
                "secret": False,
                "restart_services": [],
                "auth_modes": ["oauth_oidc"],
                "classification": "oauth-config",
                "criticality": "local-operator-context",
            },
            {
                "env": "NOTION_OAUTH_REDIRECT_URI",
                "label": "OAuth redirect URI override",
                "secret": False,
                "restart_services": [],
                "auth_modes": ["oauth_oidc"],
                "classification": "oauth-config",
                "criticality": "local-operator-context",
            },
            {
                "env": "NOTION_OAUTH_EXPIRES_AT",
                "label": "OAuth expires at",
                "secret": False,
                "restart_services": [],
                "auth_modes": ["oauth_oidc"],
                "classification": "oauth-config",
                "criticality": "local-operator-context",
            },
            {
                "env": "NOTION_OAUTH_WORKSPACE_NAME",
                "label": "OAuth workspace name",
                "secret": False,
                "restart_services": [],
                "auth_modes": ["oauth_oidc"],
                "classification": "operator-context",
                "criticality": "local-operator-context",
            },
            {
                "env": "NOTION_MCP_SMOKE_PAGE_ID",
                "label": "Smoke page ID",
                "secret": False,
                "restart_services": [],
                "classification": "live-validation-target",
                "criticality": "live-validation-optional",
            },
        ],
    },
    "github-dispatch": {
        "label": "GitHub dispatch MCP",
        "description": "Auth GitHub utilises pour les dispatch GitHub et leur smoke MCP.",
        "classification": "integration-credential",
        "criticality": "feature-required",
        "required_when": "Requis seulement si les dispatch GitHub sont utilises.",
        "used_by": ["core", "ops-agent", "crazy-lane"],
        "generate_supported": False,
        "auth_mode": {
            "env": "GITHUB_DISPATCH_AUTH_MODE",
            "default": "token",
            "options": ["token", "app"],
        },
        "fields": [
            {
                "env": "KILL_LIFE_GITHUB_TOKEN",
                "label": "Kill_LIFE GitHub token",
                "secret": True,
                "restart_services": [],
                "auth_modes": ["token"],
                "classification": "integration-credential",
            },
            {
                "env": "GITHUB_TOKEN",
                "label": "Fallback GitHub token",
                "secret": True,
                "restart_services": [],
                "auth_modes": ["token"],
                "classification": "integration-credential",
            },
            {
                "env": "GITHUB_APP_ID",
                "label": "GitHub App ID",
                "secret": False,
                "restart_services": [],
                "auth_modes": ["app"],
                "classification": "oauth-config",
            },
            {
                "env": "GITHUB_APP_PRIVATE_KEY",
                "label": "GitHub App private key",
                "secret": True,
                "restart_services": [],
                "auth_modes": ["app"],
                "classification": "integration-credential",
            },
            {
                "env": "GITHUB_APP_INSTALLATION_ID",
                "label": "GitHub App installation ID",
                "secret": False,
                "restart_services": [],
                "auth_modes": ["app"],
                "classification": "oauth-config",
            },
        ],
    },
    "huggingface": {
        "label": "HuggingFace MCP",
        "description": "Token READ pour le serveur MCP HuggingFace (https://huggingface.co/mcp). Utiliser OAuth login via https://huggingface.co/mcp?login si pas de token.",
        "classification": "integration-credential",
        "criticality": "feature-required",
        "required_when": "Requis seulement si le MCP HuggingFace distant est utilise.",
        "used_by": ["ops-agent"],
        "generate_supported": False,
        "fields": [
            {
                "env": "HUGGINGFACE_API_KEY",
                "label": "HuggingFace API key / READ token",
                "secret": True,
                "restart_services": [],
                "classification": "integration-credential",
            },
        ],
    },
}

SEVERITY_RE = [
    (re.compile(r"\b(critical|fatal|panic)\b", re.I), "critical"),
    (re.compile(r"\b(error|exception|traceback|failed)\b", re.I), "error"),
    (re.compile(r"\b(warn|warning)\b", re.I), "warning"),
    (re.compile(r"\b(debug|trace)\b", re.I), "debug"),
]

ROUTINE_HTTP_PROBE_RE = re.compile(
    r"\b(GET|HEAD)\s+\"?/"
    r"(health(?:/liveliness)?|healthz|ready|api/health|api/tags|collections|metrics|agent-traces/recent|cluster/identity|cluster/peers|api/ops/summary|logs/recent|events/recent)"
    r"(?:\?|\"|\s|$)",
    re.I,
)
ROUTINE_SERVICE_PATTERNS = [
    ROUTINE_HTTP_PROBE_RE,
    re.compile(r"No last resource version found, starting from scratch", re.I),
    re.compile(r"added Docker target", re.I),
    re.compile(r"finished transferring logs", re.I),
    re.compile(r"completed recalculate owned streams job", re.I),
    re.compile(r"starting recalculate owned streams job", re.I),
]
ROUTINE_MACHINE_PATTERNS = [
    re.compile(
        r"Activating via systemd: service name='org\.freedesktop\.login1'", re.I
    ),
    re.compile(
        r"Failed to activate service 'org\.freedesktop\.login1': timed out", re.I
    ),
    re.compile(r"Starting modprobe@drm\.service", re.I),
    re.compile(r"Finished modprobe@drm\.service", re.I),
    re.compile(r"modprobe@drm\.service: Deactivated successfully", re.I),
]
ROUTINE_MACHINE_SERVICE_PATTERNS: dict[str, list[re.Pattern[str]]] = {
    "avahi-daemon.service": [
        re.compile(r"Joining mDNS multicast group", re.I),
        re.compile(r"New relevant interface", re.I),
        re.compile(r"Registering new address record", re.I),
    ],
    "networkmanager.service": [
        re.compile(r"\bveth[a-z0-9]+\b", re.I),
        re.compile(r"\bbr-[a-f0-9]+\b", re.I),
    ],
    "docker.service": [
        re.compile(r"\bsbJoin\b", re.I),
        re.compile(r"\bNetworkDB stats\b", re.I),
    ],
    "kernel": [
        re.compile(r"\bveth[a-z0-9]+\b", re.I),
        re.compile(r"\bbr-[a-f0-9]+\b", re.I),
    ],
}

MCP_PROBE_CONFIGS: list[dict[str, Any]] = [
    {
        "key": "kicad",
        "command": [
            "python3",
            str(KILL_LIFE_ROOT / "tools" / "hw" / "mcp_smoke.py"),
            "--json",
            "--quick",
            "--timeout",
            "8.0",
        ],
        "cwd": KILL_LIFE_ROOT,
        "timeout_s": 8.0,
        "primary": True,
    },
    {
        "key": "freecad",
        "command": [
            "python3",
            str(KILL_LIFE_ROOT / "tools" / "freecad_mcp_smoke.py"),
            "--json",
            "--quick",
            "--timeout",
            "10.0",
        ],
        "cwd": KILL_LIFE_ROOT,
        "timeout_s": 10.0,
    },
    {
        "key": "openscad",
        "command": [
            "python3",
            str(KILL_LIFE_ROOT / "tools" / "openscad_mcp_smoke.py"),
            "--json",
            "--quick",
            "--timeout",
            "10.0",
        ],
        "cwd": KILL_LIFE_ROOT,
        "timeout_s": 10.0,
    },
    {
        "key": "validate-specs",
        "command": [
            "python3",
            str(KILL_LIFE_ROOT / "tools" / "validate_specs_mcp_smoke.py"),
            "--json",
            "--quick",
            "--timeout",
            "8.0",
        ],
        "cwd": KILL_LIFE_ROOT,
        "timeout_s": 8.0,
    },
    {
        "key": "notion",
        "command": [
            "python3",
            str(KILL_LIFE_ROOT / "tools" / "notion_mcp_smoke.py"),
            "--json",
            "--timeout",
            "12.0",
        ],
        "cwd": KILL_LIFE_ROOT,
        "timeout_s": 12.0,
    },
    {
        "key": "github-dispatch",
        "command": [
            "python3",
            str(KILL_LIFE_ROOT / "tools" / "github_dispatch_mcp_smoke.py"),
            "--json",
            "--timeout",
            "8.0",
        ],
        "cwd": KILL_LIFE_ROOT,
        "timeout_s": 8.0,
    },
    {
        "key": "huggingface",
        "type": "http",
        "url": "https://huggingface.co/mcp",
        "token_env": "HUGGINGFACE_API_KEY",
        "timeout_s": 10.0,
    },
]

_mcp_probe_cache: dict[str, Any] | None = None
_mcp_probe_cache_expires_at = 0.0
_mcp_probe_lock = asyncio.Lock()
_runtime_secret_lock = asyncio.Lock()


class RuntimeSecretUpdateRequest(BaseModel):
    values: dict[str, str] = Field(default_factory=dict)


class RuntimeSecretClearRequest(BaseModel):
    fields: list[str] | None = Field(default=None)


class ProviderUpdateRequest(BaseModel):
    keys: dict[str, str] = Field(default_factory=dict)


class ProviderClearRequest(BaseModel):
    fields: list[str] | None = Field(default=None)


def is_routine_service_message(service: str, severity: str, message: str) -> bool:
    if severity_rank(severity) >= severity_rank("warning"):
        return False
    normalized_service = service.strip().lower()
    for pattern in ROUTINE_SERVICE_PATTERNS:
        if pattern.search(message):
            return True
    if normalized_service == "ops-agent" and ROUTINE_HTTP_PROBE_RE.search(message):
        return True
    return False


def is_routine_machine_message(service: str, severity: str, message: str) -> bool:
    if severity_rank(severity) >= severity_rank("warning"):
        return False
    normalized_service = service.strip().lower()
    if any(pattern.search(message) for pattern in ROUTINE_MACHINE_PATTERNS):
        return True
    return any(
        pattern.search(message)
        for pattern in ROUTINE_MACHINE_SERVICE_PATTERNS.get(normalized_service, [])
    )


def is_routine_docker_event(action: str) -> bool:
    lowered = action.strip().lower()
    return (
        lowered == "exec_die"
        or lowered.startswith("exec_create:")
        or lowered.startswith("exec_start:")
    )


def iso_utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def to_iso(value: str | None) -> str:
    if not value:
        return iso_utc_now()
    try:
        return (
            datetime.fromisoformat(value.replace("Z", "+00:00"))
            .astimezone(UTC)
            .isoformat()
            .replace("+00:00", "Z")
        )
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


def make_default_mcp_status(**overrides: Any) -> dict[str, Any]:
    payload = {
        "ok": False,
        "status": "failed",
        "requested_runtime": "local",
        "runtime_mode": None,
        "protocol_version": None,
        "server_name": None,
        "tool_count": 0,
        "resource_count": 0,
        "prompt_count": 0,
        "latency_ms": 0,
        "checks": [],
    }
    payload.update(overrides)
    return payload


def invalidate_mcp_probe_cache() -> None:
    global _mcp_probe_cache, _mcp_probe_cache_expires_at
    _mcp_probe_cache = None
    _mcp_probe_cache_expires_at = 0.0


def configured_api_keys() -> list[str]:
    return [
        key.strip()
        for key in (os.getenv("MASCARADE_API_KEY") or "").split(",")
        if key.strip() and len(key.strip()) >= 16
    ]


def token_from_cookie(cookie_header: str | None) -> str | None:
    if not cookie_header:
        return None
    for part in cookie_header.split(";"):
        raw_name, _, raw_value = part.strip().partition("=")
        if raw_name != OPS_AGENT_API_KEY_COOKIE or not raw_value:
            continue
        try:
            return httpx.URL(f"http://cookie.local/?v={raw_value}").params.get("v")
        except Exception:
            return raw_value
    return None


async def require_admin_auth(request: Request) -> None:
    api_keys = configured_api_keys()
    if not api_keys:
        return

    auth_header = request.headers.get("Authorization") or ""
    header_token = auth_header[7:] if auth_header.startswith("Bearer ") else None
    cookie_token = token_from_cookie(request.headers.get("Cookie"))
    token = header_token or cookie_token
    if not token:
        raise HTTPException(status_code=401, detail="Token invalide ou manquant")

    if not any(hmac.compare_digest(token, key) for key in api_keys):
        raise HTTPException(status_code=401, detail="Token invalide ou manquant")


def resolve_runtime_secret_group(name: str) -> dict[str, Any]:
    group = RUNTIME_SECRET_GROUPS.get(name)
    if not group:
        raise HTTPException(
            status_code=404, detail=f"Unknown runtime secret group: {name}"
        )
    return group


def resolve_provider(name: str) -> dict[str, Any]:
    try:
        return resolve_provider_meta(name)
    except KeyError as exc:
        raise HTTPException(
            status_code=404, detail=f"Unknown provider: {name}"
        ) from exc


def _decode_env_value(raw_value: str) -> str:
    value = raw_value.strip()
    if not value:
        return ""
    if len(value) >= 2 and value[0] == value[-1] == '"':
        inner = value[1:-1]
        return inner.replace("\\n", "\n").replace('\\"', '"').replace("\\\\", "\\")
    if len(value) >= 2 and value[0] == value[-1] == "'":
        return value[1:-1]
    return value


def read_env_values() -> dict[str, str]:
    values: dict[str, str] = {}
    if not MASCARADE_ENV_FILE.exists():
        return values
    for raw_line in MASCARADE_ENV_FILE.read_text(encoding="utf-8").splitlines():
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        match = ENV_ASSIGN_RE.match(stripped)
        if not match:
            continue
        values[match.group(1)] = _decode_env_value(match.group(2))
    return values


def encode_env_value(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
    return f'"{escaped}"'


def write_env_updates(updates: dict[str, str]) -> None:
    if not MASCARADE_ENV_FILE.exists():
        raise FileNotFoundError(f"Runtime env file is missing: {MASCARADE_ENV_FILE}")

    original_text = MASCARADE_ENV_FILE.read_text(encoding="utf-8")
    original_mode = MASCARADE_ENV_FILE.stat().st_mode
    lines = original_text.splitlines()
    seen: set[str] = set()
    new_lines: list[str] = []

    for line in lines:
        stripped = line.lstrip()
        match = ENV_ASSIGN_RE.match(stripped)
        if match and match.group(1) in updates:
            key = match.group(1)
            indent = line[: len(line) - len(stripped)]
            new_lines.append(f"{indent}{key}={encode_env_value(updates[key])}")
            seen.add(key)
        else:
            new_lines.append(line)

    for key, value in updates.items():
        if key in seen:
            continue
        new_lines.append(f"{key}={encode_env_value(value)}")

    trailing_newline = "\n" if original_text.endswith("\n") or new_lines else ""
    with MASCARADE_ENV_FILE.open("w", encoding="utf-8") as handle:
        handle.write("\n".join(new_lines) + trailing_newline)
    os.chmod(MASCARADE_ENV_FILE, original_mode)


def apply_runtime_env_updates(updates: dict[str, str]) -> None:
    for key, value in updates.items():
        os.environ[key] = value


def masked_hint(value: str, *, secret: bool) -> str:
    if not value:
        return ""
    if secret:
        if len(value) <= 8:
            return "*" * len(value)
        return f"{value[:4]}...{value[-4:]}"
    if len(value) <= 18:
        return value
    return f"{value[:8]}...{value[-6:]}"


def runtime_group_auth_mode(
    group: dict[str, Any], env_values: dict[str, str]
) -> str | None:
    auth_mode_meta = group.get("auth_mode")
    if not auth_mode_meta:
        return None
    env_name = str(auth_mode_meta["env"])
    value = (env_values.get(env_name, os.getenv(env_name, "")) or "").strip().lower()
    options = [str(option) for option in auth_mode_meta.get("options", [])]
    default = str(auth_mode_meta.get("default", options[0] if options else ""))
    return value if value in options else default


def is_runtime_secret_group_configured(
    group_name: str,
    env_values: dict[str, str],
    auth_mode: str | None,
) -> bool:
    if group_name == "auth":
        return bool(
            env_values.get(
                "MASCARADE_API_KEY", os.getenv("MASCARADE_API_KEY", "")
            ).strip()
        )
    if group_name == "notion":
        if auth_mode == "oauth_oidc":
            return bool(
                env_values.get(
                    "NOTION_OAUTH_CLIENT_ID", os.getenv("NOTION_OAUTH_CLIENT_ID", "")
                ).strip()
                and (
                    env_values.get(
                        "NOTION_OAUTH_ACCESS_TOKEN",
                        os.getenv("NOTION_OAUTH_ACCESS_TOKEN", ""),
                    ).strip()
                    or env_values.get(
                        "NOTION_OAUTH_REFRESH_TOKEN",
                        os.getenv("NOTION_OAUTH_REFRESH_TOKEN", ""),
                    ).strip()
                )
                and env_values.get(
                    "NOTION_OAUTH_CLIENT_SECRET",
                    os.getenv("NOTION_OAUTH_CLIENT_SECRET", ""),
                ).strip()
            )
        return bool(
            env_values.get("NOTION_API_KEY", os.getenv("NOTION_API_KEY", "")).strip()
        )
    if group_name == "github-dispatch":
        if auth_mode == "app":
            return bool(
                env_values.get("GITHUB_APP_ID", os.getenv("GITHUB_APP_ID", "")).strip()
                and env_values.get(
                    "GITHUB_APP_PRIVATE_KEY",
                    os.getenv("GITHUB_APP_PRIVATE_KEY", ""),
                ).strip()
                and env_values.get(
                    "GITHUB_APP_INSTALLATION_ID",
                    os.getenv("GITHUB_APP_INSTALLATION_ID", ""),
                ).strip()
            )
        return bool(
            env_values.get(
                "KILL_LIFE_GITHUB_TOKEN",
                os.getenv("KILL_LIFE_GITHUB_TOKEN", ""),
            ).strip()
            or env_values.get("GITHUB_TOKEN", os.getenv("GITHUB_TOKEN", "")).strip()
        )
    return False


def build_runtime_secret_group_status(name: str) -> dict[str, Any]:
    group = resolve_runtime_secret_group(name)
    env_values = read_env_values()
    auth_mode_meta = group.get("auth_mode")
    auth_mode = runtime_group_auth_mode(group, env_values)
    fields: list[dict[str, Any]] = []
    restart_services: set[str] = set()
    configured_count = 0
    active_fields = [
        field
        for field in group["fields"]
        if not field.get("auth_modes")
        or auth_mode is None
        or auth_mode in field.get("auth_modes", [])
    ]

    for field in group["fields"]:
        env_name = str(field["env"])
        value = env_values.get(env_name, os.getenv(env_name, ""))
        configured = bool(value)
        auth_modes = [str(mode) for mode in field.get("auth_modes", [])]
        field_is_active = not auth_modes or auth_mode is None or auth_mode in auth_modes
        if configured:
            configured_count += 1
        restart_services.update(
            str(service) for service in field.get("restart_services", [])
        )
        fields.append(
            {
                "env": env_name,
                "label": str(field["label"]),
                "configured": configured,
                "hint": masked_hint(value, secret=bool(field.get("secret"))),
                "secret": bool(field.get("secret")),
                "classification": str(
                    field.get(
                        "classification",
                        group.get("classification", "integration-credential"),
                    )
                ),
                "criticality": str(
                    field.get(
                        "criticality", group.get("criticality", "feature-required")
                    )
                ),
                "restart_services": list(field.get("restart_services", [])),
                "auth_modes": auth_modes,
                "active": field_is_active,
            }
        )

    result = {
        "name": name,
        "label": str(group["label"]),
        "description": str(group["description"]),
        "classification": str(group.get("classification", "integration-credential")),
        "criticality": str(group.get("criticality", "feature-required")),
        "required_when": str(group.get("required_when", "")),
        "used_by": [str(item) for item in group.get("used_by", [])],
        "configured": is_runtime_secret_group_configured(name, env_values, auth_mode),
        "configured_count": sum(
            1 for field in fields if field["active"] and field["configured"]
        ),
        "field_count": len(active_fields),
        "generate_supported": bool(group.get("generate_supported")),
        "restart_services": sorted(restart_services),
        "fields": fields,
    }
    if auth_mode_meta:
        result["auth_mode"] = auth_mode
        result["auth_mode_env"] = str(auth_mode_meta["env"])
        result["auth_modes"] = [
            str(option) for option in auth_mode_meta.get("options", [])
        ]
    return result


def list_runtime_secret_groups() -> list[dict[str, Any]]:
    return [build_runtime_secret_group_status(name) for name in RUNTIME_SECRET_GROUPS]


def compose_plugin_path() -> Path:
    for candidate in DOCKER_COMPOSE_PLUGIN_CANDIDATES:
        if candidate.exists():
            return candidate
    raise FileNotFoundError("docker-compose plugin unavailable in ops-agent runtime")


async def recreate_compose_services(services: list[str]) -> None:
    if not services:
        return
    compose_plugin = compose_plugin_path()
    command = [
        str(compose_plugin),
        "--env-file",
        str(MASCARADE_ENV_FILE),
        "-f",
        str(MASCARADE_COMPOSE_FILE),
        "up",
        "-d",
        "--force-recreate",
        "--no-deps",
        *services,
    ]
    process = await asyncio.create_subprocess_exec(
        *command,
        cwd=str(MASCARADE_ROOT),
        env=os.environ.copy(),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await process.communicate()
    if process.returncode != 0:
        message = (
            stderr.decode("utf-8", errors="replace").strip()
            or stdout.decode("utf-8", errors="replace").strip()
        )
        raise RuntimeError(
            message or f"docker compose exited with code {process.returncode}"
        )


async def wait_for_core_ready(timeout_s: float = 45.0) -> None:
    deadline = asyncio.get_running_loop().time() + timeout_s
    last_error = "core did not become ready"
    async with httpx.AsyncClient(timeout=2.5) as client:
        while asyncio.get_running_loop().time() < deadline:
            try:
                response = await client.get("http://core:8100/health")
                if response.is_success:
                    return
                last_error = f"core health returned HTTP {response.status_code}"
            except Exception as exc:
                last_error = str(exc)
            await asyncio.sleep(1.0)
    raise RuntimeError(last_error)


def normalize_update_values(
    group: dict[str, Any], payload: dict[str, str]
) -> dict[str, str]:
    allowed_fields = {str(field["env"]): field for field in group["fields"]}
    auth_mode_meta = group.get("auth_mode")
    updates: dict[str, str] = {}
    for key, value in payload.items():
        if auth_mode_meta and key == str(auth_mode_meta["env"]):
            normalized = str(value).strip().lower()
            options = [str(option) for option in auth_mode_meta.get("options", [])]
            if normalized in options:
                updates[key] = normalized
            continue
        field = allowed_fields.get(key)
        if not field:
            continue
        updates[key] = str(value).strip()
    return updates


def restart_services_for_updates(
    group: dict[str, Any], updates: dict[str, str]
) -> list[str]:
    services: set[str] = set()
    field_map = {str(field["env"]): field for field in group["fields"]}
    for env_name in updates:
        services.update(
            str(service) for service in field_map[env_name].get("restart_services", [])
        )
    return sorted(services)


def normalize_provider_updates(
    meta: dict[str, Any], payload: dict[str, str]
) -> dict[str, str]:
    allowed_fields = valid_provider_envs(meta)
    auth_mode_meta = meta.get("auth_mode")
    toggle_meta = meta.get("toggle")
    normalized: dict[str, str] = {}

    for raw_key, raw_value in payload.items():
        key = str(raw_key)
        if key not in allowed_fields:
            raise HTTPException(status_code=400, detail=f"Unknown field: {key}")
        value = str(raw_value).strip()

        if auth_mode_meta and key == str(auth_mode_meta["env"]):
            options = [str(option) for option in auth_mode_meta.get("options", [])]
            if value not in options:
                raise HTTPException(
                    status_code=400, detail=f"Invalid auth mode: {value}"
                )
            normalized[key] = value
            continue

        if toggle_meta and key == str(toggle_meta["env"]):
            normalized[key] = (
                "true" if value.lower() in {"1", "true", "yes", "on"} else "false"
            )
            continue

        normalized[key] = value

    return normalized


def provider_clear_updates(
    meta: dict[str, Any], fields: list[str] | None = None
) -> dict[str, str]:
    allowed_fields = valid_provider_envs(meta)
    selected_fields = (
        allowed_fields if fields is None else {str(field) for field in fields}
    )
    unknown_fields = sorted(selected_fields - allowed_fields)
    if unknown_fields:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown field(s): {', '.join(unknown_fields)}",
        )

    updates: dict[str, str] = {}
    auth_mode_meta = meta.get("auth_mode")
    if auth_mode_meta and str(auth_mode_meta["env"]) in selected_fields:
        updates[str(auth_mode_meta["env"])] = str(
            auth_mode_meta.get("default", "")
        ).strip()
    toggle_meta = meta.get("toggle")
    if toggle_meta and str(toggle_meta["env"]) in selected_fields:
        updates[str(toggle_meta["env"])] = "false"
    for field in meta["fields"]:
        env_name = str(field["env"])
        if env_name in selected_fields:
            updates[env_name] = ""
    return updates


def client_token_for_auth(value: str | None) -> str | None:
    if not value:
        return None
    tokens = [token.strip() for token in value.split(",") if token.strip()]
    if len(tokens) == 1:
        return tokens[0]
    return None


async def persist_runtime_secret_updates(
    group_name: str, updates: dict[str, str]
) -> dict[str, Any]:
    group = resolve_runtime_secret_group(group_name)
    normalized_updates = normalize_update_values(group, updates)
    if not normalized_updates:
        raise HTTPException(
            status_code=400, detail="No valid runtime secret values supplied"
        )

    async with _runtime_secret_lock:
        write_env_updates(normalized_updates)
        apply_runtime_env_updates(normalized_updates)
        invalidate_mcp_probe_cache()
        restart_services = restart_services_for_updates(group, normalized_updates)
        if restart_services:
            await recreate_compose_services(restart_services)
            if "core" in restart_services:
                await wait_for_core_ready()

    result = {
        "status": "ok",
        "message": "Runtime secrets updated",
        "group": build_runtime_secret_group_status(group_name),
        "updated_env": sorted(normalized_updates),
        "restarted_services": restart_services,
    }
    if group_name == "auth":
        token = client_token_for_auth(normalized_updates.get("MASCARADE_API_KEY"))
        if token:
            result["client_token"] = token
    return result


async def clear_runtime_secret_group(
    group_name: str, fields: list[str] | None = None
) -> dict[str, Any]:
    group = resolve_runtime_secret_group(group_name)
    target_fields = {
        str(field["env"]): ""
        for field in group["fields"]
        if fields is None or str(field["env"]) in set(fields)
    }
    if not target_fields:
        raise HTTPException(
            status_code=400, detail="No runtime secret fields selected for clear"
        )

    async with _runtime_secret_lock:
        write_env_updates(target_fields)
        apply_runtime_env_updates(target_fields)
        invalidate_mcp_probe_cache()
        restart_services = restart_services_for_updates(group, target_fields)
        if restart_services:
            await recreate_compose_services(restart_services)
            if "core" in restart_services:
                await wait_for_core_ready()

    return {
        "status": "ok",
        "message": "Runtime secrets cleared",
        "group": build_runtime_secret_group_status(group_name),
        "cleared_env": sorted(target_fields),
        "restarted_services": restart_services,
    }


async def generate_auth_runtime_secret() -> dict[str, Any]:
    token = secrets.token_urlsafe(48)
    result = await persist_runtime_secret_updates("auth", {"MASCARADE_API_KEY": token})
    result["generated_value"] = token
    result["message"] = "Mascarade API key generated"
    return result


async def persist_provider_updates(
    provider_name: str, updates: dict[str, str]
) -> dict[str, Any]:
    meta = resolve_provider(provider_name)
    normalized_updates = normalize_provider_updates(meta, updates)
    if not normalized_updates:
        raise HTTPException(status_code=400, detail="No valid provider values supplied")

    async with _runtime_secret_lock:
        write_env_updates(normalized_updates)
        apply_runtime_env_updates(normalized_updates)
        await recreate_compose_services(["core"])
        await wait_for_core_ready()

    return {
        "status": "ok",
        "message": "Provider settings updated",
        "provider": provider_name,
        "updated_env": sorted(normalized_updates),
        "restarted_services": ["core"],
    }


async def clear_provider_settings(
    provider_name: str, fields: list[str] | None = None
) -> dict[str, Any]:
    meta = resolve_provider(provider_name)
    clear_updates = provider_clear_updates(meta, fields)
    if not clear_updates:
        raise HTTPException(
            status_code=400, detail="No provider fields selected for clear"
        )

    async with _runtime_secret_lock:
        write_env_updates(clear_updates)
        apply_runtime_env_updates(clear_updates)
        await recreate_compose_services(["core"])
        await wait_for_core_ready()

    return {
        "status": "ok",
        "message": "Provider settings cleared",
        "provider": provider_name,
        "cleared_env": sorted(clear_updates),
        "restarted_services": ["core"],
    }


async def run_mcp_http_probe(config: dict[str, Any]) -> dict[str, Any]:
    """Probe a remote HTTP MCP server (e.g. HuggingFace)."""
    started = asyncio.get_running_loop().time()
    key = str(config["key"])
    url = str(config["url"])
    timeout_s = float(config.get("timeout_s", 10.0) or 10.0)
    token_env = str(config.get("token_env", ""))
    token = os.getenv(token_env, "").strip() if token_env else ""
    headers: dict[str, str] = {
        "Accept": "application/json, text/event-stream",
        "Content-Type": "application/json",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    try:
        async with httpx.AsyncClient(timeout=timeout_s) as client:
            init_resp = await client.post(
                url,
                headers=headers,
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "initialize",
                    "params": {
                        "protocolVersion": "2025-03-26",
                        "capabilities": {},
                        "clientInfo": {
                            "name": "mascarade-ops-agent",
                            "version": "0.1.0",
                        },
                    },
                },
            )
    except Exception as exc:
        return make_default_mcp_status(
            status="failed",
            latency_ms=round((asyncio.get_running_loop().time() - started) * 1000),
            server_name=key,
            error=str(exc),
            secret_configured=bool(token),
        )

    latency_ms = round((asyncio.get_running_loop().time() - started) * 1000)

    if init_resp.status_code == 401:
        return make_default_mcp_status(
            status="degraded",
            latency_ms=latency_ms,
            server_name=key,
            error="Authentication required (401). Set token or use OAuth login.",
            secret_configured=bool(token),
        )

    if init_resp.status_code >= 400:
        return make_default_mcp_status(
            status="failed",
            latency_ms=latency_ms,
            server_name=key,
            error=f"HTTP {init_resp.status_code}: {init_resp.text[:200]}",
            secret_configured=bool(token),
        )

    protocol_version = None
    server_name = key
    tool_count = 0

    try:
        init_payload = init_resp.json()
    except Exception:
        init_payload = {}

    if isinstance(init_payload, dict):
        result = init_payload.get("result")
        if isinstance(result, dict):
            protocol_version = result.get("protocolVersion")
            server_info = result.get("serverInfo")
            if isinstance(server_info, dict) and isinstance(
                server_info.get("name"), str
            ):
                server_name = server_info["name"]

    session_id = init_resp.headers.get("mcp-session-id")
    if session_id:
        list_headers = dict(headers)
        list_headers["mcp-session-id"] = session_id
        try:
            async with httpx.AsyncClient(timeout=timeout_s) as client:
                list_resp = await client.post(
                    url,
                    headers=list_headers,
                    json={
                        "jsonrpc": "2.0",
                        "id": 2,
                        "method": "tools/list",
                        "params": {},
                    },
                )
            if list_resp.status_code < 400:
                list_payload = list_resp.json()
                if isinstance(list_payload, dict):
                    result = list_payload.get("result")
                    if isinstance(result, dict) and isinstance(
                        result.get("tools"), list
                    ):
                        tool_count = len(result["tools"])
        except Exception:
            pass

    return make_default_mcp_status(
        ok=True,
        status="ready",
        requested_runtime="remote-http",
        runtime_mode="streamable-http",
        protocol_version=str(protocol_version) if protocol_version else None,
        server_name=server_name,
        tool_count=tool_count,
        latency_ms=latency_ms,
        secret_configured=bool(token),
    )


async def run_mcp_probe(config: dict[str, Any]) -> dict[str, Any]:
    started = asyncio.get_running_loop().time()
    cwd = Path(config["cwd"])
    key = str(config["key"])
    command = [str(part) for part in config["command"]]
    timeout_s = float(config.get("timeout_s", 8.0) or 8.0)

    if not cwd.exists():
        return make_default_mcp_status(
            status="degraded",
            latency_ms=round((asyncio.get_running_loop().time() - started) * 1000),
            server_name=key,
            error=f"Probe workspace unavailable in ops-agent runtime: {cwd}",
        )

    script_candidate = Path(command[1]) if len(command) > 1 else None
    if (
        script_candidate
        and script_candidate.suffix in {".py", ".sh"}
        and not script_candidate.exists()
    ):
        return make_default_mcp_status(
            status="degraded",
            latency_ms=round((asyncio.get_running_loop().time() - started) * 1000),
            server_name=key,
            error=f"Probe script unavailable in ops-agent runtime: {script_candidate}",
        )

    try:
        process = await asyncio.create_subprocess_exec(
            *command,
            cwd=str(cwd),
            env=os.environ.copy(),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
    except FileNotFoundError as exc:
        return make_default_mcp_status(
            status="degraded",
            latency_ms=round((asyncio.get_running_loop().time() - started) * 1000),
            server_name=key,
            error=f"Probe dependency unavailable in ops-agent runtime: {exc}",
        )
    except Exception as exc:
        return make_default_mcp_status(
            status="failed",
            latency_ms=round((asyncio.get_running_loop().time() - started) * 1000),
            server_name=key,
            error=str(exc),
        )

    try:
        stdout, stderr = await asyncio.wait_for(
            process.communicate(), timeout=timeout_s
        )
    except asyncio.TimeoutError:
        process.kill()
        await process.communicate()
        return make_default_mcp_status(
            status="failed",
            latency_ms=round((asyncio.get_running_loop().time() - started) * 1000),
            server_name=key,
            error=f"Timed out after {timeout_s:.1f}s waiting for MCP probe",
        )

    stdout_text = stdout.decode("utf-8", errors="replace")
    stderr_text = stderr.decode("utf-8", errors="replace").strip()
    line = next(
        (
            entry.strip()
            for entry in reversed(stdout_text.splitlines())
            if entry.strip()
        ),
        "",
    )

    payload: dict[str, Any] | None = None
    if line:
        try:
            parsed = json.loads(line)
            if isinstance(parsed, dict):
                payload = parsed
        except json.JSONDecodeError:
            payload = None

    normalized_status = "failed"
    if payload and payload.get("status") in {"ready", "degraded", "failed"}:
        normalized_status = str(payload["status"])
    elif process.returncode == 0:
        normalized_status = "degraded"

    return make_default_mcp_status(
        ok=normalized_status == "ready",
        status=normalized_status,
        requested_runtime=(payload or {}).get("requested_runtime") or "local",
        runtime_mode=(payload or {}).get("runtime_mode"),
        protocol_version=(payload or {}).get("protocol_version"),
        server_name=(payload or {}).get("server_name") or key,
        tool_count=int((payload or {}).get("tool_count") or 0),
        resource_count=int((payload or {}).get("resource_count") or 0),
        prompt_count=int((payload or {}).get("prompt_count") or 0),
        latency_ms=round((asyncio.get_running_loop().time() - started) * 1000),
        checks=(
            (payload or {}).get("checks")
            if isinstance((payload or {}).get("checks"), list)
            else []
        ),
        secret_configured=(payload or {}).get("secret_configured"),
        token_configured=(payload or {}).get("token_configured"),
        live_requested=(payload or {}).get("live_requested"),
        live_validation=(payload or {}).get("live_validation"),
        error=(payload or {}).get("error")
        or stderr_text
        or (
            None
            if process.returncode == 0
            else f"Probe exited with code {process.returncode}"
        ),
    )


def aggregate_mcp_status(servers: dict[str, dict[str, Any]]) -> dict[str, Any]:
    entries = list(servers.items())
    primary_entry = next(
        (
            entry
            for entry in entries
            if entry[0] == "kicad"
            or next(
                (
                    cfg
                    for cfg in MCP_PROBE_CONFIGS
                    if cfg["key"] == entry[0] and cfg.get("primary")
                ),
                None,
            )
        ),
        entries[0] if entries else ("unknown", make_default_mcp_status()),
    )
    primary_server, primary = primary_entry
    if any(status.get("status") == "failed" for _, status in entries):
        aggregate_status = "failed"
    elif any(status.get("status") == "degraded" for _, status in entries):
        aggregate_status = "degraded"
    else:
        aggregate_status = "ready"

    payload = dict(primary)
    payload.update(
        {
            "ok": aggregate_status == "ready",
            "status": aggregate_status,
            "aggregate_status": aggregate_status,
            "primary_server": primary_server,
            "primary": primary,
            "server_count": len(entries),
            "servers_ok": sum(
                1 for _, status in entries if status.get("status") == "ready"
            ),
            "degraded_servers": [
                key for key, status in entries if status.get("status") != "ready"
            ],
            "servers": servers,
        }
    )
    return payload


async def probe_mcp_runtime(*, force: bool = False) -> dict[str, Any]:
    global _mcp_probe_cache, _mcp_probe_cache_expires_at

    now = asyncio.get_running_loop().time()
    if not force and _mcp_probe_cache and _mcp_probe_cache_expires_at > now:
        return _mcp_probe_cache

    async with _mcp_probe_lock:
        now = asyncio.get_running_loop().time()
        if not force and _mcp_probe_cache and _mcp_probe_cache_expires_at > now:
            return _mcp_probe_cache

        statuses = await asyncio.gather(
            *(
                (
                    run_mcp_http_probe(config)
                    if config.get("type") == "http"
                    else run_mcp_probe(config)
                )
                for config in MCP_PROBE_CONFIGS
            )
        )
        value = aggregate_mcp_status(
            {
                str(config["key"]): status
                for config, status in zip(MCP_PROBE_CONFIGS, statuses, strict=False)
            }
        )
        _mcp_probe_cache = value
        _mcp_probe_cache_expires_at = (
            asyncio.get_running_loop().time() + OPS_MCP_PROBE_CACHE_TTL_MS
        )
        return value


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


async def recent_docker_events(
    limit: int,
    since_seconds: int = 900,
    *,
    include_routine: bool = False,
) -> list[dict[str, Any]]:
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
            ts = (
                datetime.fromtimestamp(float(event_ts) / divisor, tz=UTC)
                .isoformat()
                .replace("+00:00", "Z")
            )
        else:
            ts = iso_utc_now()

        action = str(payload.get("Action") or payload.get("status") or "event")
        event_type = str(payload.get("Type") or "docker")
        if not include_routine and is_routine_docker_event(action):
            continue
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
                    "actor_id": str(
                        (payload.get("Actor") or {}).get("ID")
                        or payload.get("id")
                        or ""
                    )[:12],
                },
            }
        )

    return sorted(events, key=lambda event: event["ts"], reverse=True)[:limit]


def journal_dirs() -> list[str]:
    return [
        path for path in ("/var/log/journal", "/run/log/journal") if os.path.isdir(path)
    ]


def journalctl_available() -> bool:
    return shutil.which("journalctl") is not None and bool(journal_dirs())


async def recent_journal_logs(
    limit: int, *, include_routine: bool = False
) -> list[dict[str, Any]]:
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
            ts = (
                datetime.fromtimestamp(int(timestamp_us) / 1_000_000, tz=UTC)
                .isoformat()
                .replace("+00:00", "Z")
            )
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
        service = str(
            payload.get("_SYSTEMD_UNIT") or payload.get("SYSLOG_IDENTIFIER") or "system"
        )
        if not include_routine and is_routine_machine_message(
            service, severity, message
        ):
            continue
        entries.append(
            {
                "id": f"journal:{ts}:{len(entries)}",
                "ts": ts,
                "source": "machine",
                "service": service,
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


def gpu_probe() -> dict[str, Any]:
    """Run nvidia-smi and return structured GPU status."""
    nvidia_smi = shutil.which("nvidia-smi")
    if not nvidia_smi:
        return {
            "available": False,
            "kind": "nvidia-smi",
            "error": "nvidia-smi unavailable in ops-agent runtime",
            "runtime": {
                "visible_devices": os.getenv("NVIDIA_VISIBLE_DEVICES") or "",
                "driver_capabilities": os.getenv("NVIDIA_DRIVER_CAPABILITIES") or "",
            },
        }
    try:
        result = __import__("subprocess").run(
            [
                nvidia_smi,
                "--query-gpu=name,memory.total,memory.used,memory.free,utilization.gpu,temperature.gpu",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode != 0:
            return {
                "available": True,
                "kind": "nvidia-smi",
                "error": result.stderr.strip(),
            }
        gpus = []
        for line in result.stdout.strip().splitlines():
            parts = [p.strip() for p in line.split(",")]
            if len(parts) >= 6:
                gpus.append(
                    {
                        "name": parts[0],
                        "memory_total_mb": int(parts[1]),
                        "memory_used_mb": int(parts[2]),
                        "memory_free_mb": int(parts[3]),
                        "utilization_pct": int(parts[4]),
                        "temperature_c": int(parts[5]),
                    }
                )
        return {"available": True, "kind": "nvidia-smi", "gpus": gpus}
    except Exception as exc:
        return {"available": True, "kind": "nvidia-smi", "error": str(exc)}


@app.get("/runtime-secrets/status")
async def runtime_secrets_status(_auth: None = Depends(require_admin_auth)):
    return {
        "groups": list_runtime_secret_groups(),
        "timestamp": iso_utc_now(),
    }


@app.put("/runtime-secrets/{group_name}")
async def runtime_secrets_update(
    group_name: str,
    payload: RuntimeSecretUpdateRequest,
    _auth: None = Depends(require_admin_auth),
):
    return await persist_runtime_secret_updates(group_name, payload.values)


@app.post("/runtime-secrets/{group_name}/clear")
async def runtime_secrets_clear(
    group_name: str,
    payload: RuntimeSecretClearRequest,
    _auth: None = Depends(require_admin_auth),
):
    return await clear_runtime_secret_group(group_name, payload.fields)


@app.post("/runtime-secrets/{group_name}/generate")
async def runtime_secrets_generate(
    group_name: str, _auth: None = Depends(require_admin_auth)
):
    if group_name != "auth":
        raise HTTPException(
            status_code=400, detail=f"Generation not supported for {group_name}"
        )
    return await generate_auth_runtime_secret()


@app.put("/providers/{provider_name}")
async def provider_update(
    provider_name: str,
    payload: ProviderUpdateRequest,
    _auth: None = Depends(require_admin_auth),
):
    return await persist_provider_updates(provider_name, payload.keys)


@app.post("/providers/{provider_name}/clear")
async def provider_clear(
    provider_name: str,
    payload: ProviderClearRequest,
    _auth: None = Depends(require_admin_auth),
):
    return await clear_provider_settings(provider_name, payload.fields)


@app.get("/health")
async def health():
    docker_ok = await docker_available()
    return {
        "status": "ok",
        "docker": docker_ok,
        "journald": journalctl_available(),
        "gpu": gpu_probe(),
    }


@app.get("/metrics")
async def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.get("/sources")
async def sources():
    return {
        "docker_logs": {"available": await docker_available(), "kind": "docker-api"},
        "docker_events": {
            "available": await docker_available(),
            "kind": "docker-api-events",
        },
        "journald": {"available": journalctl_available(), "kind": "journalctl"},
        "gpu": gpu_probe(),
        "loki": {"available": await loki_available(), "kind": "loki"},
        "agentsight": {
            "available": await agentsight_available(),
            "kind": "optional-complement",
        },
    }


@app.get("/mcp/summary")
async def mcp_summary(force: bool = Query(default=False)):
    return await probe_mcp_runtime(force=force)


@app.get("/summary")
async def summary():
    docker_ok = await docker_available()
    containers = await list_containers() if docker_ok else []
    recent = await logs_recent(
        limit=40,
        services=None,
        include_services=True,
        include_machine=True,
        include_routine=False,
    )
    events = (
        await recent_docker_events(limit=20, include_routine=False) if docker_ok else []
    )
    return {
        "timestamp": iso_utc_now(),
        "container_count": len(containers),
        "services": sorted(service_name(container) for container in containers),
        "recent": recent,
        "events": events,
        "mcp": await probe_mcp_runtime(),
        "sources": await sources(),
    }


@app.get("/events/recent")
async def events_recent(
    limit: int = Query(default=40, ge=1, le=200),
    since_seconds: int = Query(default=900, ge=30, le=86400),
    include_routine: bool = Query(default=False),
):
    events = await recent_docker_events(
        limit=limit,
        since_seconds=since_seconds,
        include_routine=include_routine,
    )
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
    include_routine: bool = Query(default=False),
):
    service_filter = {
        token.strip() for token in (services or "").split(",") if token.strip()
    }
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
            for idx, line in enumerate(
                await fetch_container_logs(container["Id"], per_container_tail)
            ):
                ts, message = parse_timestamped_line(line)
                severity = infer_severity(message)
                if not include_routine and is_routine_service_message(
                    svc, severity, message
                ):
                    continue
                entries.append(
                    {
                        "id": f"service:{svc}:{ts}:{idx}",
                        "ts": ts,
                        "source": "service",
                        "service": svc,
                        "severity": severity,
                        "message": message,
                        "labels": {
                            "container_id": str(container.get("Id", ""))[:12],
                        },
                    }
                )

    if include_machine:
        entries.extend(
            await recent_journal_logs(min(limit, 120), include_routine=include_routine)
        )

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
    include_routine: bool = Query(default=False),
    severity: str = Query(default="info"),
    backfill: int = Query(default=20, ge=0, le=120),
    live_limit: int = Query(default=24, ge=5, le=120),
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
            include_routine=include_routine,
        )
        entries = list(payload.get("entries", []))
        if include_events:
            entries.extend(
                await recent_docker_events(
                    limit=max(10, min(limit, 80)),
                    since_seconds=since_seconds,
                    include_routine=include_routine,
                )
            )
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
            batch = await collect_entries(max(backfill, live_limit), window_seconds)
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
