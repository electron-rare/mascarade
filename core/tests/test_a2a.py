"""Comprehensive tests for the A2A (Agent-to-Agent) protocol router."""

from __future__ import annotations

from dataclasses import dataclass, field
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from mascarade.routers.a2a import (
    A2ATask,
    _tasks,
    authed_router,
    public_router,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


@dataclass
class FakeAgent:
    name: str
    description: str = "A test agent"
    tools: list[str] = field(default_factory=list)


class FakeRegistry:
    def __init__(self, agents: list[FakeAgent] | None = None):
        self._agents = {a.name: a for a in (agents or [])}

    def list(self):
        return list(self._agents.values())

    def __contains__(self, name: str) -> bool:
        return name in self._agents


@dataclass
class FakeSkill:
    name: str
    description: str = "A test skill"
    category: str = "general"


class FakeSkillRegistry:
    def __init__(self, skills: list[FakeSkill] | None = None):
        self._skills = {s.name: s for s in (skills or [])}

    def list(self):
        return list(self._skills.values())

    def __contains__(self, name: str) -> bool:
        return name in self._skills


def _make_app(
    *,
    a2a_enabled: bool = True,
    registry: FakeRegistry | None = None,
    skill_registry: FakeSkillRegistry | None = None,
    orchestrator: MagicMock | None = None,
    p2p_enabled: bool = False,
    cluster_enabled: bool = False,
) -> FastAPI:
    """Create a test FastAPI app with A2A routes."""
    app = FastAPI()
    app.include_router(public_router)
    app.include_router(authed_router)

    app.state.registry = registry
    app.state.skill_registry = skill_registry
    app.state.orchestrator = orchestrator

    # Patch settings for tests
    settings_patch = {
        "a2a_enabled": a2a_enabled,
        "a2a_agent_name": "test-mascarade",
        "a2a_agent_url": "http://localhost:8000",
        "p2p_enabled": p2p_enabled,
        "cluster_enabled": cluster_enabled,
    }

    # We patch settings used by the endpoints
    app._settings_patch = settings_patch
    return app


@pytest.fixture(autouse=True)
def _clear_tasks():
    """Clear the global task store before each test."""
    _tasks.clear()
    yield
    _tasks.clear()


# ---------------------------------------------------------------------------
# Agent Card (/.well-known/agent.json)
# ---------------------------------------------------------------------------


class TestAgentCard:
    def test_agent_card_basic(self):
        registry = FakeRegistry([FakeAgent(name="coder", tools=["python", "bash"])])
        app = _make_app(registry=registry)

        with patch("mascarade.routers.a2a.settings") as mock_settings:
            mock_settings.a2a_agent_name = "test-mascarade"
            mock_settings.a2a_agent_url = "http://localhost:8000"
            mock_settings.p2p_enabled = False
            mock_settings.cluster_enabled = False

            client = TestClient(app)
            resp = client.get("/.well-known/agent.json")

        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "test-mascarade"
        assert data["url"] == "http://localhost:8000"
        assert "skills" in data
        assert len(data["skills"]) == 1
        assert data["skills"][0]["id"] == "coder"

    def test_agent_card_includes_skills(self):
        skill_registry = FakeSkillRegistry(
            [
                FakeSkill(name="translate", category="language"),
            ]
        )
        app = _make_app(skill_registry=skill_registry)

        with patch("mascarade.routers.a2a.settings") as mock_settings:
            mock_settings.a2a_agent_name = "mascarade"
            mock_settings.a2a_agent_url = ""
            mock_settings.p2p_enabled = False
            mock_settings.cluster_enabled = False

            client = TestClient(app)
            resp = client.get("/.well-known/agent.json")

        data = resp.json()
        skill_ids = [s["id"] for s in data["skills"]]
        assert "translate" in skill_ids

    def test_agent_card_capabilities_p2p(self):
        app = _make_app(p2p_enabled=True)

        with patch("mascarade.routers.a2a.settings") as mock_settings:
            mock_settings.a2a_agent_name = "mascarade"
            mock_settings.a2a_agent_url = ""
            mock_settings.p2p_enabled = True
            mock_settings.cluster_enabled = False

            client = TestClient(app)
            resp = client.get("/.well-known/agent.json")

        data = resp.json()
        assert data["capabilities"]["p2p"] is True

    def test_agent_card_empty_registries(self):
        app = _make_app()

        with patch("mascarade.routers.a2a.settings") as mock_settings:
            mock_settings.a2a_agent_name = "mascarade"
            mock_settings.a2a_agent_url = ""
            mock_settings.p2p_enabled = False
            mock_settings.cluster_enabled = False

            client = TestClient(app)
            resp = client.get("/.well-known/agent.json")

        data = resp.json()
        assert data["skills"] == []


# ---------------------------------------------------------------------------
# Task submission (POST /a2a/tasks)
# ---------------------------------------------------------------------------


class TestTaskSubmission:
    def test_submit_task_success(self):
        registry = FakeRegistry([FakeAgent(name="coder")])
        app = _make_app(registry=registry, orchestrator=MagicMock())

        with patch("mascarade.routers.a2a.settings") as mock_settings, patch(
            "mascarade.routers.a2a.require_auth", return_value=None
        ):
            mock_settings.a2a_enabled = True

            # Override auth dependency
            from mascarade.auth import require_auth

            app.dependency_overrides[require_auth] = lambda: None

            client = TestClient(app)
            resp = client.post(
                "/a2a/tasks",
                json={
                    "skill_id": "coder",
                    "input": {"text": "Write a hello world function"},
                },
            )

        assert resp.status_code == 201
        data = resp.json()
        assert data["skill_id"] == "coder"
        assert data["status"] == "submitted"
        assert data["input_text"] == "Write a hello world function"
        assert "id" in data

    def test_submit_task_unknown_skill(self):
        registry = FakeRegistry([FakeAgent(name="coder")])
        app = _make_app(registry=registry)

        with patch("mascarade.routers.a2a.settings") as mock_settings:
            mock_settings.a2a_enabled = True

            from mascarade.auth import require_auth

            app.dependency_overrides[require_auth] = lambda: None

            client = TestClient(app)
            resp = client.post(
                "/a2a/tasks",
                json={
                    "skill_id": "nonexistent",
                    "input": {"text": "test"},
                },
            )

        assert resp.status_code == 404
        assert "nonexistent" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# Task status (GET /a2a/tasks/{task_id})
# ---------------------------------------------------------------------------


class TestTaskStatus:
    def test_get_task_status(self):
        app = _make_app()

        # Pre-insert a task
        task = A2ATask(
            id="test-123",
            skill_id="coder",
            status="completed",
            input_text="hello",
            output_text="world",
            created_at="2025-01-01T00:00:00Z",
            updated_at="2025-01-01T00:00:01Z",
        )
        _tasks["test-123"] = task

        with patch("mascarade.routers.a2a.settings") as mock_settings:
            mock_settings.a2a_enabled = True

            from mascarade.auth import require_auth

            app.dependency_overrides[require_auth] = lambda: None

            client = TestClient(app)
            resp = client.get("/a2a/tasks/test-123")

        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "test-123"
        assert data["status"] == "completed"
        assert data["output_text"] == "world"

    def test_get_unknown_task_404(self):
        app = _make_app()

        with patch("mascarade.routers.a2a.settings") as mock_settings:
            mock_settings.a2a_enabled = True

            from mascarade.auth import require_auth

            app.dependency_overrides[require_auth] = lambda: None

            client = TestClient(app)
            resp = client.get("/a2a/tasks/does-not-exist")

        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# A2A disabled
# ---------------------------------------------------------------------------


class TestA2ADisabled:
    def test_submit_task_returns_503_when_disabled(self):
        registry = FakeRegistry([FakeAgent(name="coder")])
        app = _make_app(a2a_enabled=False, registry=registry)

        with patch("mascarade.routers.a2a.settings") as mock_settings:
            mock_settings.a2a_enabled = False

            from mascarade.auth import require_auth

            app.dependency_overrides[require_auth] = lambda: None

            client = TestClient(app)
            resp = client.post(
                "/a2a/tasks",
                json={
                    "skill_id": "coder",
                    "input": {"text": "test"},
                },
            )

        assert resp.status_code == 503
        assert "disabled" in resp.json()["detail"]

    def test_get_task_returns_503_when_disabled(self):
        app = _make_app(a2a_enabled=False)

        with patch("mascarade.routers.a2a.settings") as mock_settings:
            mock_settings.a2a_enabled = False

            from mascarade.auth import require_auth

            app.dependency_overrides[require_auth] = lambda: None

            client = TestClient(app)
            resp = client.get("/a2a/tasks/some-id")

        assert resp.status_code == 503
        assert "disabled" in resp.json()["detail"]
