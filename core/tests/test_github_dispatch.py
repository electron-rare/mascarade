"""Tests for the GitHub workflow_dispatch integration."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from mascarade.integrations.github_dispatch import (
    GitHubDispatchAuthError,
    GitHubDispatchClient,
    GitHubDispatchError,
    list_allowlisted_workflows,
)


class _FakeResponse:
    def __init__(self, status_code: int, payload: dict | None = None, text: str = ""):
        self.status_code = status_code
        self._payload = payload or {}
        self.text = text

    def json(self) -> dict:
        return self._payload


class _FakeAsyncClient:
    def __init__(self, responses: list[_FakeResponse]):
        self._responses = responses
        self.calls: list[tuple[str, str, dict | None]] = []

    async def post(self, url: str, json: dict | None = None):
        self.calls.append(("POST", url, json))
        return self._responses.pop(0)

    async def get(self, url: str, params: dict | None = None):
        self.calls.append(("GET", url, params))
        return self._responses.pop(0)

    async def aclose(self) -> None:
        return None


def test_list_allowlisted_workflows_returns_curated_surface():
    workflows = list_allowlisted_workflows()
    names = {entry["workflow_file"] for entry in workflows}
    assert "badges.yml" in names
    assert "static.yml" in names


@pytest.mark.asyncio
async def test_dispatch_workflow_requires_token(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setenv("GITHUB_DISPATCH_AUTH_MODE", "token")
    monkeypatch.setenv("KILL_LIFE_GITHUB_TOKEN", "")
    monkeypatch.setenv("GITHUB_TOKEN", "")
    client = GitHubDispatchClient(
        api_token="",
        state_dir=tmp_path,
        http_client=_FakeAsyncClient([]),
    )

    with pytest.raises(GitHubDispatchAuthError):
        await client.dispatch_workflow("badges.yml")


@pytest.mark.asyncio
async def test_dispatch_and_status_persist_structured_record(tmp_path: Path):
    now_iso = datetime.now(tz=UTC).isoformat().replace("+00:00", "Z")
    fake_http = _FakeAsyncClient(
        [
            _FakeResponse(204),
            _FakeResponse(
                200,
                {
                    "workflow_runs": [
                        {
                            "id": 4242,
                            "name": "repo state",
                            "display_title": "repo state",
                            "status": "completed",
                            "conclusion": "success",
                            "html_url": "https://github.com/example/run/4242",
                            "created_at": now_iso,
                            "updated_at": now_iso,
                            "run_number": 7,
                        }
                    ]
                },
            ),
        ]
    )
    client = GitHubDispatchClient(
        api_token="ghp_test_token_123456789",  # noqa: S106
        state_dir=tmp_path,
        http_client=fake_http,
    )

    dispatch = await client.dispatch_workflow(
        "badges.yml",
        ref="main",
        inputs={"target": "linux"},
    )
    assert dispatch["status"] == "accepted"
    assert (tmp_path / f"{dispatch['dispatch_id']}.json").exists()

    status = await client.get_dispatch_status(dispatch["dispatch_id"])
    assert status["status"] == "success"
    assert status["workflow_run"]["run_id"] == 4242
    assert status["workflow_run"]["html_url"].endswith("/4242")


@pytest.mark.asyncio
async def test_dispatch_rejects_non_allowlisted_workflow(tmp_path: Path):
    client = GitHubDispatchClient(
        api_token="ghp_test_token_123456789",  # noqa: S106
        state_dir=tmp_path,
        http_client=_FakeAsyncClient([]),
    )

    with pytest.raises(GitHubDispatchError):
        await client.dispatch_workflow("dangerous.yml")


@pytest.mark.asyncio
async def test_dispatch_supports_github_app_mode(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    fake_http = _FakeAsyncClient([_FakeResponse(204)])
    client = GitHubDispatchClient(
        api_token="",
        state_dir=tmp_path,
        http_client=fake_http,
    )
    monkeypatch.setenv("GITHUB_DISPATCH_AUTH_MODE", "app")

    async def _fake_installation_token() -> dict:
        return {
            "token": "ghs_installation_token_123456789",
            "expires_at": "2026-03-08T12:00:00Z",
        }

    client.auth_mode = "app"
    client._request_installation_token = _fake_installation_token  # type: ignore[method-assign]

    dispatch = await client.dispatch_workflow("badges.yml")

    assert dispatch["status"] == "accepted"
    assert fake_http.calls[0][0] == "POST"
    assert client.api_token == "ghs_installation_token_123456789"  # noqa: S105
