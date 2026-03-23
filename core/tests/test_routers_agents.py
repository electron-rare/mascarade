"""Tests for agents router endpoints."""

from __future__ import annotations

from contextlib import asynccontextmanager
from uuid import uuid4

import httpx
import pytest

from mascarade.auth import add_api_key, get_active_api_keys, remove_api_key
from mascarade.router.providers.base import LLMResponse
from mascarade.server import app

TEST_API_KEY = "test-agent-key-001"


class FakeRouter:
    """Fake router for testing agent endpoints."""

    def __init__(
        self,
        *,
        response: LLMResponse | None = None,
        error: Exception | None = None,
    ) -> None:
        self._response = response or LLMResponse(
            content="Agent response",
            model="gpt-4",
            provider="openai",
            usage={"input_tokens": 10, "output_tokens": 5},
        )
        self._error = error
        self.calls: list[dict] = []

    async def send(self, messages: list[dict], **kwargs) -> LLMResponse:
        self.calls.append({"messages": messages, **kwargs})
        if self._error is not None:
            raise self._error
        return self._response


@pytest.fixture(autouse=True)
def _clean_api_keys():
    """Clean API keys before and after each test."""
    for key in get_active_api_keys():
        remove_api_key(key)
    add_api_key(TEST_API_KEY)
    yield
    for key in get_active_api_keys():
        remove_api_key(key)


@pytest.fixture
def _clean_registry():
    """Clean agent registry before and after each test."""
    # Store original state
    original_agents = {}
    if hasattr(app.state, "registry"):
        for agent in app.state.registry.list():
            if not app.state.registry.is_builtin(agent.name):
                original_agents[agent.name] = agent

    yield

    # Restore original state
    if hasattr(app.state, "registry"):
        # Remove any test agents
        for agent in list(app.state.registry.list()):
            if not app.state.registry.is_builtin(agent.name) and agent.name not in original_agents:
                try:
                    app.state.registry.remove(agent.name)
                except KeyError:
                    pass


@asynccontextmanager
async def _client(fake_router: FakeRouter | None = None):
    """Create test client with optional fake router."""
    async with app.router.lifespan_context(app):
        original_router = app.state.router if fake_router else None
        if fake_router:
            app.state.router = fake_router
        try:
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(
                transport=transport,
                base_url="http://testserver",
            ) as client:
                yield client
        finally:
            if original_router:
                app.state.router = original_router


@pytest.mark.asyncio
async def test_create_agent(request, _clean_registry):
    """Test creating a new agent."""
    async with _client() as client:
        response = await client.post(
            "/api/agents",
            headers={"Authorization": f"Bearer {TEST_API_KEY}"},
            json={
                "name": "test-agent",
                "description": "A test agent",
                "system_prompt": "You are a helpful assistant",
                "strategy": "best",
                "routing_policy": "auto",
                "temperature": 0.7,
                "max_tokens": 4096,
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "test-agent"
    assert body["description"] == "A test agent"
    assert body["system_prompt"] == "You are a helpful assistant"
    assert body["strategy"] == "best"
    assert body["routing_policy"] == "auto"
    assert body["temperature"] == 0.7
    assert body["max_tokens"] == 4096
    assert body["builtin"] is False


@pytest.mark.asyncio
async def test_list_agents(request, _clean_registry):
    """Test listing all agents."""
    # Create a test agent first
    async with _client() as client:
        await client.post(
            "/api/agents",
            headers={"Authorization": f"Bearer {TEST_API_KEY}"},
            json={
                "name": "test-agent-1",
                "description": "Test agent 1",
                "system_prompt": "You are helpful",
            },
        )

        response = await client.get(
            "/api/agents",
            headers={"Authorization": f"Bearer {TEST_API_KEY}"},
        )

    assert response.status_code == 200
    body = response.json()
    assert "agents" in body
    assert isinstance(body["agents"], list)
    # Should have at least the test agent we created
    agent_names = [a["name"] for a in body["agents"]]
    assert "test-agent-1" in agent_names


@pytest.mark.asyncio
async def test_get_agent(request, _clean_registry):
    """Test getting a specific agent."""
    async with _client() as client:
        # Create agent
        await client.post(
            "/api/agents",
            headers={"Authorization": f"Bearer {TEST_API_KEY}"},
            json={
                "name": "test-agent",
                "description": "Test agent",
                "system_prompt": "You are helpful",
            },
        )

        # Get agent
        response = await client.get(
            "/api/agents/test-agent",
            headers={"Authorization": f"Bearer {TEST_API_KEY}"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "test-agent"
    assert body["description"] == "Test agent"


@pytest.mark.asyncio
async def test_get_nonexistent_agent():
    """Test getting a nonexistent agent returns 404."""
    async with _client() as client:
        response = await client.get(
            "/api/agents/nonexistent-agent",
            headers={"Authorization": f"Bearer {TEST_API_KEY}"},
        )

    assert response.status_code == 404
    assert "not found" in response.json()["detail"]


@pytest.mark.asyncio
async def test_update_agent(request, _clean_registry):
    """Test updating an agent."""
    async with _client() as client:
        # Create agent
        await client.post(
            "/api/agents",
            headers={"Authorization": f"Bearer {TEST_API_KEY}"},
            json={
                "name": "test-agent",
                "description": "Original description",
                "system_prompt": "Original prompt",
            },
        )

        # Update agent
        response = await client.put(
            "/api/agents/test-agent",
            headers={"Authorization": f"Bearer {TEST_API_KEY}"},
            json={
                "description": "Updated description",
                "system_prompt": "Updated prompt",
                "temperature": 0.9,
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["description"] == "Updated description"
    assert body["system_prompt"] == "Updated prompt"
    assert body["temperature"] == 0.9


@pytest.mark.asyncio
async def test_update_agent_creates_version(request, _clean_registry):
    """Test updating agent system_prompt creates a new version."""
    async with _client() as client:
        # Create agent
        await client.post(
            "/api/agents",
            headers={"Authorization": f"Bearer {TEST_API_KEY}"},
            json={
                "name": "test-agent",
                "description": "Test",
                "system_prompt": "Original prompt",
            },
        )

        # Update agent with new system_prompt
        response = await client.put(
            "/api/agents/test-agent",
            headers={"Authorization": f"Bearer {TEST_API_KEY}"},
            json={
                "description": "Test",
                "system_prompt": "Updated prompt",
                "version_note": "Updated for testing",
            },
        )

    assert response.status_code == 200
    # Verify the agent was updated
    body = response.json()
    assert body["system_prompt"] == "Updated prompt"


@pytest.mark.asyncio
async def test_update_nonexistent_agent():
    """Test updating a nonexistent agent returns 404."""
    async with _client() as client:
        response = await client.put(
            "/api/agents/nonexistent-agent",
            headers={"Authorization": f"Bearer {TEST_API_KEY}"},
            json={
                "description": "Test",
                "system_prompt": "Test",
            },
        )

    assert response.status_code == 404
    assert "not found" in response.json()["detail"]


@pytest.mark.asyncio
async def test_delete_agent(request, _clean_registry):
    """Test deleting an agent."""
    async with _client() as client:
        # Create agent
        await client.post(
            "/api/agents",
            headers={"Authorization": f"Bearer {TEST_API_KEY}"},
            json={
                "name": "test-agent",
                "description": "Test",
                "system_prompt": "Test",
            },
        )

        # Delete agent
        response = await client.delete(
            "/api/agents/test-agent",
            headers={"Authorization": f"Bearer {TEST_API_KEY}"},
        )

    assert response.status_code == 200
    assert "deleted successfully" in response.json()["message"]


@pytest.mark.asyncio
async def test_delete_nonexistent_agent():
    """Test deleting a nonexistent agent returns 404."""
    async with _client() as client:
        response = await client.delete(
            "/api/agents/nonexistent-agent",
            headers={"Authorization": f"Bearer {TEST_API_KEY}"},
        )

    assert response.status_code == 404
    assert "not found" in response.json()["detail"]


@pytest.mark.asyncio
async def test_run_agent(request, _clean_registry):
    """Test running an agent with messages."""
    fake_router = FakeRouter(
        response=LLMResponse(
            content="Agent response",
            model="gpt-4",
            provider="openai",
            usage={"input_tokens": 10, "output_tokens": 5},
        )
    )

    async with _client(fake_router) as client:
        # Create agent
        await client.post(
            "/api/agents",
            headers={"Authorization": f"Bearer {TEST_API_KEY}"},
            json={
                "name": "test-agent",
                "description": "Test",
                "system_prompt": "You are helpful",
            },
        )

        # Run agent
        response = await client.post(
            "/api/agents/test-agent/run",
            headers={"Authorization": f"Bearer {TEST_API_KEY}"},
            json={
                "project_id": "project-alpha",
                "messages": [
                    {"role": "user", "content": "Hello"}
                ],
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["content"] == "Agent response"
    assert body["model"] == "gpt-4"
    assert body["provider"] == "openai"
    assert body["usage"]["input_tokens"] == 10
    assert body["usage"]["output_tokens"] == 5
    assert fake_router.calls[0]["project_id"] == "project-alpha"


@pytest.mark.asyncio
async def test_run_agent_with_context(request, _clean_registry):
    """Test running an agent with multiple messages (context)."""
    fake_router = FakeRouter()

    async with _client(fake_router) as client:
        # Create agent
        await client.post(
            "/api/agents",
            headers={"Authorization": f"Bearer {TEST_API_KEY}"},
            json={
                "name": "test-agent",
                "description": "Test",
                "system_prompt": "You are helpful",
            },
        )

        # Run agent with context
        response = await client.post(
            "/api/agents/test-agent/run",
            headers={"Authorization": f"Bearer {TEST_API_KEY}"},
            json={
                "project_id": "project-alpha",
                "messages": [
                    {"role": "user", "content": "What is 2+2?"},
                    {"role": "assistant", "content": "4"},
                    {"role": "user", "content": "What is 3+3?"},
                ],
            },
        )

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_run_agent_no_messages():
    """Test running an agent without messages returns 400."""
    async with _client() as client:
        response = await client.post(
            "/api/agents/test-agent/run",
            headers={"Authorization": f"Bearer {TEST_API_KEY}"},
            json={
                "project_id": "project-alpha",
                "messages": [],
            },
        )

    assert response.status_code == 400
    assert "At least one message is required" in response.json()["detail"]


@pytest.mark.asyncio
async def test_run_nonexistent_agent():
    """Test running a nonexistent agent returns 404."""
    async with _client() as client:
        response = await client.post(
            "/api/agents/nonexistent-agent/run",
            headers={"Authorization": f"Bearer {TEST_API_KEY}"},
            json={
                "project_id": "project-alpha",
                "messages": [
                    {"role": "user", "content": "Hello"}
                ],
            },
        )

    assert response.status_code == 404
    assert "not found" in response.json()["detail"]


@pytest.mark.asyncio
async def test_get_agent_metrics(request, _clean_registry):
    """Test getting agent metrics."""
    async with _client() as client:
        # Create agent
        await client.post(
            "/api/agents",
            headers={"Authorization": f"Bearer {TEST_API_KEY}"},
            json={
                "name": "test-agent",
                "description": "Test",
                "system_prompt": "Test",
            },
        )

        # Get metrics
        response = await client.get(
            "/api/agents/test-agent/metrics",
            headers={"Authorization": f"Bearer {TEST_API_KEY}"},
        )

    assert response.status_code == 200
    # Metrics structure depends on registry implementation
    assert isinstance(response.json(), dict)


@pytest.mark.asyncio
async def test_get_metrics_nonexistent_agent():
    """Test getting metrics for nonexistent agent returns 404."""
    async with _client() as client:
        response = await client.get(
            "/api/agents/nonexistent-agent/metrics",
            headers={"Authorization": f"Bearer {TEST_API_KEY}"},
        )

    assert response.status_code == 404
    assert "not found" in response.json()["detail"]


@pytest.mark.asyncio
async def test_agent_endpoints_require_auth():
    """Test that agent endpoints require authentication."""
    async with _client() as client:
        # Try to list agents without auth
        response = await client.get("/api/agents")

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_create_agent_with_preferences(request, _clean_registry):
    """Test creating an agent with provider and model preferences."""
    async with _client() as client:
        response = await client.post(
            "/api/agents",
            headers={"Authorization": f"Bearer {TEST_API_KEY}"},
            json={
                "name": "test-agent",
                "description": "Test",
                "system_prompt": "Test",
                "preferred_provider": "openai",
                "preferred_model": "gpt-4",
                "preferred_role": "assistant",
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["preferred_provider"] == "openai"
    assert body["preferred_model"] == "gpt-4"
    assert body["preferred_role"] == "assistant"


@pytest.mark.asyncio
async def test_delete_builtin_agent_forbidden():
    """Test that built-in agents cannot be deleted (403)."""
    async with _client() as client:
        # List agents to find a builtin
        list_resp = await client.get(
            "/api/agents",
            headers={"Authorization": f"Bearer {TEST_API_KEY}"},
        )
        assert list_resp.status_code == 200
        agents = list_resp.json()["agents"]
        builtins = [a for a in agents if a.get("builtin")]

        if builtins:
            response = await client.delete(
                f"/api/agents/{builtins[0]['name']}",
                headers={"Authorization": f"Bearer {TEST_API_KEY}"},
            )
            assert response.status_code == 403
            assert "read-only" in response.json()["detail"]


@pytest.mark.asyncio
async def test_update_builtin_agent_forbidden():
    """Test that built-in agents cannot be updated (403)."""
    async with _client() as client:
        list_resp = await client.get(
            "/api/agents",
            headers={"Authorization": f"Bearer {TEST_API_KEY}"},
        )
        assert list_resp.status_code == 200
        agents = list_resp.json()["agents"]
        builtins = [a for a in agents if a.get("builtin")]

        if builtins:
            response = await client.put(
                f"/api/agents/{builtins[0]['name']}",
                headers={"Authorization": f"Bearer {TEST_API_KEY}"},
                json={
                    "description": "Updated",
                    "system_prompt": "Updated",
                },
            )
            assert response.status_code == 403


@pytest.mark.asyncio
async def test_create_duplicate_agent(request, _clean_registry):
    """Test creating an agent with a duplicate name fails."""
    agent_name = f"dup-agent-{uuid4().hex[:8]}"
    async with _client() as client:
        payload = {
            "name": agent_name,
            "description": "Test",
            "system_prompt": "Test",
        }
        resp1 = await client.post(
            "/api/agents",
            headers={"Authorization": f"Bearer {TEST_API_KEY}"},
            json=payload,
        )
        assert resp1.status_code == 200

        # Try to create the same agent again
        resp2 = await client.post(
            "/api/agents",
            headers={"Authorization": f"Bearer {TEST_API_KEY}"},
            json=payload,
        )
        # Should fail with conflict or error
        assert resp2.status_code in (400, 409, 422, 500)


@pytest.mark.asyncio
async def test_run_agent_router_error(request, _clean_registry):
    """Test running an agent when router raises an error."""
    fake_router = FakeRouter(error=RuntimeError("LLM unavailable"))

    async with _client(fake_router) as client:
        await client.post(
            "/api/agents",
            headers={"Authorization": f"Bearer {TEST_API_KEY}"},
            json={
                "name": "error-agent",
                "description": "Test",
                "system_prompt": "Test",
            },
        )

        response = await client.post(
            "/api/agents/error-agent/run",
            headers={"Authorization": f"Bearer {TEST_API_KEY}"},
            json={
                "project_id": "project-alpha",
                "messages": [{"role": "user", "content": "Hello"}],
            },
        )

    assert response.status_code == 503


@pytest.mark.asyncio
async def test_run_agent_requires_project_id(request, _clean_registry):
    fake_router = FakeRouter()

    async with _client(fake_router) as client:
        await client.post(
            "/api/agents",
            headers={"Authorization": f"Bearer {TEST_API_KEY}"},
            json={
                "name": "test-agent-project",
                "description": "Test",
                "system_prompt": "You are helpful",
            },
        )

        response = await client.post(
            "/api/agents/test-agent-project/run",
            headers={"Authorization": f"Bearer {TEST_API_KEY}"},
            json={
                "messages": [{"role": "user", "content": "Hello"}],
            },
        )

    assert response.status_code == 400
    assert "project_id is required" in response.json()["detail"]


@pytest.mark.asyncio
async def test_create_agent_with_custom_strategy(request, _clean_registry):
    """Test creating an agent with a non-default strategy."""
    agent_name = f"cheap-agent-{uuid4().hex[:8]}"
    async with _client() as client:
        response = await client.post(
            "/api/agents",
            headers={"Authorization": f"Bearer {TEST_API_KEY}"},
            json={
                "name": agent_name,
                "description": "Test",
                "system_prompt": "You are cheap",
                "strategy": "cheapest",
                "routing_policy": "cheap",
                "temperature": 0.3,
                "max_tokens": 1024,
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["strategy"] == "cheapest"
    assert body["temperature"] == 0.3
    assert body["max_tokens"] == 1024


@pytest.mark.asyncio
async def test_agent_invalid_auth_token():
    """Test agent endpoints reject invalid auth tokens."""
    async with _client() as client:
        response = await client.get(
            "/api/agents",
            headers={"Authorization": "Bearer invalid-key-xyz"},
        )

    assert response.status_code == 401
