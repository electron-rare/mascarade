"""GitHub workflow_dispatch integration shared by API and MCP surfaces."""

from __future__ import annotations

import json
import os
import re
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import uuid4

import httpx

from mascarade.config import is_secret_configured

DEFAULT_KILL_LIFE_ROOT = Path(os.getenv("KILL_LIFE_ROOT", "/home/clems/Kill_LIFE")).resolve()
DEFAULT_GITHUB_REPO = os.getenv("KILL_LIFE_GITHUB_REPO", "electron-rare/Kill_LIFE")
DEFAULT_GITHUB_REF = os.getenv("KILL_LIFE_GITHUB_REF", "main")
DEFAULT_MASCARADE_API_BASE_URL = os.getenv(
    "MASCARADE_API_BASE_URL",
    f"http://127.0.0.1:{os.getenv('API_PORT', '3100')}",
).rstrip("/")
GITHUB_API_BASE_URL = "https://api.github.com"
SAFE_INPUT_KEY_RE = re.compile(r"^[a-zA-Z0-9_.-]{1,64}$")
ALLOWED_GITHUB_WORKFLOWS = (
    "badges.yml",
    "evidence_pack.yml",
    "release_signing.yml",
    "repo_state.yml",
    "static.yml",
)


class GitHubDispatchError(RuntimeError):
    """Base error for dispatch integration failures."""


class GitHubDispatchAuthError(GitHubDispatchError):
    """Raised when the GitHub token is missing or unusable."""


def _iso_now() -> str:
    return datetime.now(tz=UTC).isoformat().replace("+00:00", "Z")


def _parse_iso(value: str) -> datetime:
    normalized = value.strip()
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    return datetime.fromisoformat(normalized).astimezone(UTC)


def _trim_excerpt(value: str, limit: int = 400) -> str:
    trimmed = value.strip()
    if len(trimmed) <= limit:
        return trimmed
    return f"{trimmed[:limit]}..."


def normalized_github_dispatch_auth_mode() -> str:
    mode = os.getenv("GITHUB_DISPATCH_AUTH_MODE", "token").strip().lower()
    return mode if mode in {"token", "app"} else "token"


def github_dispatch_auth_configured() -> bool:
    if normalized_github_dispatch_auth_mode() == "app":
        return bool(
            os.getenv("GITHUB_APP_ID", "").strip()
            and is_secret_configured(os.getenv("GITHUB_APP_PRIVATE_KEY", ""))
            and os.getenv("GITHUB_APP_INSTALLATION_ID", "").strip()
        )
    return bool(
        is_secret_configured(os.getenv("KILL_LIFE_GITHUB_TOKEN", ""))
        or is_secret_configured(os.getenv("GITHUB_TOKEN", ""))
    )


def list_allowlisted_workflows() -> list[dict[str, str]]:
    """Return the workflows allowed for MCP and direct dispatch."""
    return [
        {
            "workflow_file": workflow_file,
            "repo": DEFAULT_GITHUB_REPO,
            "default_ref": DEFAULT_GITHUB_REF,
        }
        for workflow_file in ALLOWED_GITHUB_WORKFLOWS
    ]


def sanitize_github_inputs(inputs: dict[str, Any] | None) -> dict[str, str]:
    """Normalize workflow inputs and reject unsafe keys."""
    if not inputs:
        return {}

    cleaned: dict[str, str] = {}
    for key, value in inputs.items():
        if not SAFE_INPUT_KEY_RE.fullmatch(key):
            raise GitHubDispatchError(f"Invalid GitHub input key '{key}'")
        if value is None:
            continue
        cleaned[key] = str(value)
    return cleaned


def ensure_allowlisted_workflow(workflow_file: str) -> str:
    """Validate that a workflow file is part of the dispatch allowlist."""
    normalized = workflow_file.strip()
    if normalized not in ALLOWED_GITHUB_WORKFLOWS:
        raise GitHubDispatchError(f"Workflow '{workflow_file}' is not allowlisted")
    return normalized


class GitHubDispatchClient:
    """Thin async client around GitHub workflow_dispatch plus local status cache."""

    def __init__(
        self,
        *,
        api_token: str | None = None,
        repo: str = DEFAULT_GITHUB_REPO,
        default_ref: str = DEFAULT_GITHUB_REF,
        state_dir: Path | None = None,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self.auth_mode = normalized_github_dispatch_auth_mode()
        self.api_token = (
            api_token or os.getenv("KILL_LIFE_GITHUB_TOKEN") or os.getenv("GITHUB_TOKEN", "")
        ).strip()
        self.api_base_url = DEFAULT_MASCARADE_API_BASE_URL
        self.repo = repo
        self.default_ref = default_ref
        self.state_dir = state_dir or (
            DEFAULT_KILL_LIFE_ROOT / ".mascarade" / "mcp" / "github-dispatch"
        )
        self._http_client = http_client or httpx.AsyncClient(
            base_url=GITHUB_API_BASE_URL,
            timeout=20.0,
            headers={
                "Accept": "application/vnd.github+json",
                "User-Agent": "mascarade-github-dispatch-mcp",
                **(
                    {"Authorization": f"Bearer {self.api_token}"}
                    if is_secret_configured(self.api_token)
                    else {}
                ),
            },
        )
        self._owns_http_client = http_client is None

    async def close(self) -> None:
        if self._owns_http_client:
            await self._http_client.aclose()

    def _auth_configured(self) -> bool:
        if self.auth_mode == "app":
            return github_dispatch_auth_configured()
        return is_secret_configured(self.api_token)

    async def _resolve_api_token(self) -> str:
        if self.auth_mode == "app":
            payload = await self._request_installation_token()
            token = str(payload.get("token") or "").strip()
            if not is_secret_configured(token):
                raise GitHubDispatchAuthError(
                    "GitHub App configured but no installation token was returned"
                )
            self.api_token = token
            if hasattr(self._http_client, "headers"):
                self._http_client.headers["Authorization"] = f"Bearer {token}"
            return token

        token = self.api_token.strip()
        if not is_secret_configured(token):
            raise GitHubDispatchAuthError(
                "GitHub dispatch non configure (KILL_LIFE_GITHUB_TOKEN ou GITHUB_TOKEN manquant)"
            )
        return token

    async def _request_installation_token(self) -> dict[str, Any]:
        api_key = os.getenv("MASCARADE_API_KEY", "").strip()
        if not is_secret_configured(api_key):
            raise GitHubDispatchAuthError(
                "GitHub App mode requires MASCARADE_API_KEY for local token refresh"
            )

        url = f"{self.api_base_url}/api/settings/runtime-secrets/github-dispatch/app-token"
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.post(
                url,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Accept": "application/json",
                },
            )
        if response.status_code != 200:
            raise GitHubDispatchAuthError(
                "GitHub App token refresh failed "
                f"({response.status_code}): {_trim_excerpt(response.text)}"
            )
        payload = response.json()
        if not isinstance(payload, dict):
            raise GitHubDispatchAuthError("GitHub App token refresh returned invalid payload")
        return payload

    def _record_path(self, dispatch_id: str) -> Path:
        safe_id = dispatch_id.strip().lower()
        if not safe_id or not re.fullmatch(r"[a-z0-9-]{8,64}", safe_id):
            raise GitHubDispatchError("Invalid dispatch id")
        return self.state_dir / f"{safe_id}.json"

    def _write_record(self, payload: dict[str, Any]) -> None:
        self.state_dir.mkdir(parents=True, exist_ok=True)
        dispatch_id = str(payload["dispatch_id"])
        file_path = self._record_path(dispatch_id)
        file_path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    def _read_record(self, dispatch_id: str) -> dict[str, Any]:
        file_path = self._record_path(dispatch_id)
        if not file_path.exists():
            raise GitHubDispatchError(f"Unknown dispatch id '{dispatch_id}'")
        return json.loads(file_path.read_text(encoding="utf-8"))

    async def dispatch_workflow(
        self,
        workflow_file: str,
        *,
        ref: str | None = None,
        inputs: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        await self._resolve_api_token()
        safe_workflow = ensure_allowlisted_workflow(workflow_file)
        target_ref = ref.strip() if isinstance(ref, str) and ref.strip() else self.default_ref
        payload = {
            "ref": target_ref,
            "inputs": sanitize_github_inputs(inputs),
        }

        response = await self._http_client.post(
            f"/repos/{self.repo}/actions/workflows/{safe_workflow}/dispatches",
            json=payload,
        )
        if response.status_code != 204:
            raise GitHubDispatchError(
                "GitHub dispatch failed "
                f"({response.status_code}): {_trim_excerpt(response.text)}"
            )

        record = {
            "dispatch_id": str(uuid4()),
            "repo": self.repo,
            "workflow_file": safe_workflow,
            "ref": target_ref,
            "inputs": payload["inputs"],
            "dispatched_at": _iso_now(),
            "updated_at": _iso_now(),
            "status": "accepted",
            "workflow_run": None,
        }
        self._write_record(record)
        return record

    async def get_dispatch_status(self, dispatch_id: str) -> dict[str, Any]:
        record = self._read_record(dispatch_id)
        workflow_run = await self._refresh_workflow_run(record)
        if workflow_run is not None:
            record["workflow_run"] = workflow_run
            record["status"] = self._run_status(workflow_run)
        elif not self._auth_configured():
            record["status"] = record.get("status") or "accepted"
            record["note"] = "GitHub token absent; returning local dispatch state only"
        else:
            record["status"] = "accepted"

        record["updated_at"] = _iso_now()
        self._write_record(record)
        return record

    async def _refresh_workflow_run(self, record: dict[str, Any]) -> dict[str, Any] | None:
        if not self._auth_configured():
            return record.get("workflow_run")

        await self._resolve_api_token()

        existing = record.get("workflow_run")
        if isinstance(existing, dict) and isinstance(existing.get("run_id"), int):
            response = await self._http_client.get(
                f"/repos/{self.repo}/actions/runs/{existing['run_id']}"
            )
            if response.status_code == 200:
                return self._normalize_run(response.json())

        response = await self._http_client.get(
            f"/repos/{self.repo}/actions/workflows/{record['workflow_file']}/runs",
            params={
                "event": "workflow_dispatch",
                "branch": record["ref"],
                "per_page": 20,
            },
        )
        if response.status_code != 200:
            raise GitHubDispatchError(
                "GitHub run lookup failed "
                f"({response.status_code}): {_trim_excerpt(response.text)}"
            )

        payload = response.json()
        workflow_runs = payload.get("workflow_runs") or []
        dispatched_at = _parse_iso(str(record["dispatched_at"]))
        threshold = dispatched_at - timedelta(minutes=2)
        candidates = []
        for run in workflow_runs:
            created_at = run.get("created_at") or run.get("run_started_at")
            if not isinstance(created_at, str):
                continue
            if _parse_iso(created_at) < threshold:
                continue
            candidates.append(run)

        if not candidates:
            return None

        candidates.sort(
            key=lambda run: _parse_iso(str(run.get("created_at") or run.get("run_started_at"))),
            reverse=True,
        )
        return self._normalize_run(candidates[0])

    @staticmethod
    def _normalize_run(run: dict[str, Any]) -> dict[str, Any]:
        return {
            "run_id": int(run["id"]),
            "name": run.get("name") or "",
            "display_title": run.get("display_title") or "",
            "status": run.get("status") or "unknown",
            "conclusion": run.get("conclusion"),
            "html_url": run.get("html_url") or "",
            "created_at": run.get("created_at"),
            "updated_at": run.get("updated_at"),
            "run_number": run.get("run_number"),
        }

    @staticmethod
    def _run_status(workflow_run: dict[str, Any]) -> str:
        status = str(workflow_run.get("status") or "").lower()
        conclusion = str(workflow_run.get("conclusion") or "").lower()
        if status == "completed":
            if conclusion == "success":
                return "success"
            if conclusion:
                return conclusion
            return "completed"
        if status in {"queued", "waiting", "requested", "pending"}:
            return "queued"
        if status in {"in_progress", "running"}:
            return "running"
        return status or "accepted"


__all__ = [
    "ALLOWED_GITHUB_WORKFLOWS",
    "DEFAULT_GITHUB_REF",
    "DEFAULT_GITHUB_REPO",
    "DEFAULT_MASCARADE_API_BASE_URL",
    "GitHubDispatchAuthError",
    "GitHubDispatchClient",
    "GitHubDispatchError",
    "ensure_allowlisted_workflow",
    "github_dispatch_auth_configured",
    "list_allowlisted_workflows",
    "normalized_github_dispatch_auth_mode",
    "sanitize_github_inputs",
]
