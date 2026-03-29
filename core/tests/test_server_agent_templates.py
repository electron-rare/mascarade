from __future__ import annotations

from contextlib import asynccontextmanager
from uuid import uuid4

import httpx
import pytest
from unittest.mock import patch

from mascarade.auth import add_api_key, get_active_api_keys, remove_api_key
from mascarade.server import app

TEST_API_KEY = "test-agent-template-key-001"


@pytest.fixture(autouse=True)
def _clean_api_keys():
    for key in get_active_api_keys():
        remove_api_key(key)
    add_api_key(TEST_API_KEY)
    yield
    for key in get_active_api_keys():
        remove_api_key(key)


@asynccontextmanager
async def _client():
    with (
        patch("mascarade.auth.is_valid_api_key", return_value=True),
        patch("mascarade.auth._resolve_role", return_value="admin"),
    ):
        async with app.router.lifespan_context(app):
            original_agents = {
                agent.name
                for agent in app.state.registry.list()
                if not app.state.registry.is_builtin(agent.name)
            }
            original_templates = {
                template.id
                for template in app.state.template_registry.list()
                if not app.state.template_registry.is_builtin(template.id)
            }
            try:
                transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
                async with httpx.AsyncClient(
                    transport=transport,
                    base_url="http://testserver",
                ) as client:
                    yield client
            finally:
                for agent in list(app.state.registry.list()):
                    if (
                        not app.state.registry.is_builtin(agent.name)
                        and agent.name not in original_agents
                    ):
                        app.state.registry.remove(agent.name)
                app.state.registry.save()

                for template in list(app.state.template_registry.list()):
                    if (
                        not app.state.template_registry.is_builtin(template.id)
                        and template.id not in original_templates
                    ):
                        app.state.template_registry.remove(template.id)
                app.state.template_registry.save()


@pytest.mark.asyncio
async def test_agent_advanced_metadata_roundtrip():
    agent_name = f"advanced-{uuid4().hex[:8]}"
    async with _client() as client:
        create_response = await client.post(
            "/v1/agents",
            headers={"Authorization": f"Bearer {TEST_API_KEY}"},
            json={
                "name": agent_name,
                "description": "Advanced metadata agent",
                "system_prompt": "You are advanced.",
                "preferred_role": "gpu",
                "tools": ["python", "kicad-mcp"],
                "skills": ["json-output"],
                "category": "code",
                "cluster": "runtime",
                "capabilities": ["code", "review"],
                "evidence_refs": ["kb://runbook"],
                "retry_config": {"max_attempts": 2, "backoff_seconds": 1},
                "gates": [
                    {
                        "name": "has-tools",
                        "phase": "pre",
                        "required": True,
                        "check": "has_tools",
                    }
                ],
            },
        )
        assert create_response.status_code == 200
        created = create_response.json()
        assert created["tools"] == ["python", "kicad-mcp"]
        assert created["skills"] == ["json-output"]
        assert created["category"] == "code"
        assert created["cluster"] == "runtime"
        assert created["capabilities"] == ["code", "review"]
        assert created["evidence_refs"] == ["kb://runbook"]
        assert created["retry_config"] == {"max_attempts": 2, "backoff_seconds": 1}
        assert created["gates"][0]["check"] == "has_tools"

        get_response = await client.get(
            f"/v1/agents/{agent_name}",
            headers={"Authorization": f"Bearer {TEST_API_KEY}"},
        )
        assert get_response.status_code == 200
        fetched = get_response.json()
        assert fetched["tools"] == ["python", "kicad-mcp"]
        assert fetched["gates"][0]["name"] == "has-tools"


@pytest.mark.asyncio
async def test_prompt_history_endpoint_tracks_updates():
    agent_name = f"prompt-history-{uuid4().hex[:8]}"
    async with _client() as client:
        await client.post(
            "/v1/agents",
            headers={"Authorization": f"Bearer {TEST_API_KEY}"},
            json={
                "name": agent_name,
                "description": "Prompt history agent",
                "system_prompt": "Original prompt",
            },
        )

        update_response = await client.put(
            f"/v1/agents/{agent_name}",
            headers={"Authorization": f"Bearer {TEST_API_KEY}"},
            json={
                "system_prompt": "Updated prompt",
                "version_note": "Refined prompt",
            },
        )
        assert update_response.status_code == 200

        history_response = await client.get(
            f"/v1/agents/{agent_name}/prompts/history",
            headers={"Authorization": f"Bearer {TEST_API_KEY}"},
        )
        assert history_response.status_code == 200
        versions = history_response.json()["versions"]
        assert len(versions) >= 1
        assert versions[-1]["content"] == "Updated prompt"
        assert versions[-1]["note"] == "Refined prompt"


@pytest.mark.asyncio
async def test_template_crud_roundtrip():
    agent_a = f"template-agent-a-{uuid4().hex[:6]}"
    agent_b = f"template-agent-b-{uuid4().hex[:6]}"
    template_id = f"template-{uuid4().hex[:8]}"

    async with _client() as client:
        for agent_name in (agent_a, agent_b):
            response = await client.post(
                "/v1/agents",
                headers={"Authorization": f"Bearer {TEST_API_KEY}"},
                json={
                    "name": agent_name,
                    "description": f"Agent {agent_name}",
                    "system_prompt": "You are template-capable.",
                },
            )
            assert response.status_code == 200

        create_response = await client.post(
            "/v1/orchestrate/templates",
            headers={"Authorization": f"Bearer {TEST_API_KEY}"},
            json={
                "id": template_id,
                "name": "Template CRUD",
                "description": "CRUD coverage",
                "agent_names": [agent_a, agent_b],
                "mode": "pipeline",
                "routing_overrides": {
                    agent_a: {"preferred_role": "gpu"},
                    agent_b: {"peer_id": "node-gpu"},
                },
                "documentation": "Template created during API tests.",
            },
        )
        assert create_response.status_code == 200
        created = create_response.json()
        assert created["id"] == template_id
        assert created["routing_overrides"][agent_b]["peer_id"] == "node-gpu"

        list_response = await client.get(
            "/v1/orchestrate/templates",
            headers={"Authorization": f"Bearer {TEST_API_KEY}"},
        )
        assert list_response.status_code == 200
        assert any(
            template["id"] == template_id
            for template in list_response.json()["templates"]
        )

        update_response = await client.put(
            f"/v1/orchestrate/templates/{template_id}",
            headers={"Authorization": f"Bearer {TEST_API_KEY}"},
            json={
                "description": "Updated CRUD coverage",
                "mode": "sequential",
            },
        )
        assert update_response.status_code == 200
        updated = update_response.json()
        assert updated["description"] == "Updated CRUD coverage"
        assert updated["mode"] == "sequential"

        delete_response = await client.delete(
            f"/v1/orchestrate/templates/{template_id}",
            headers={"Authorization": f"Bearer {TEST_API_KEY}"},
        )
        assert delete_response.status_code == 200
        assert "deleted successfully" in delete_response.json()["message"]
