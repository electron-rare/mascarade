"""Tests for the skills management system — registry, API, and agent integration."""

from __future__ import annotations

import tempfile
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI

from mascarade.agents.base import Agent
from mascarade.agents.registry import AgentRegistry
from mascarade.agents.skill import Skill
from mascarade.agents.skill_registry import SkillRegistry
from mascarade.agents.skills import register_default_skills_v2

# --- Standalone test app ---

# The skills router is not mounted on the main ``server.app``, so we build a
# lightweight FastAPI app for the API tests.  The router has prefix ``/v1/api``,
# so routes are at ``/v1/api/skills/...``.  The tests use ``/v1/skills/...``, so
# we create a copy of the router with prefix ``/v1``.
def _build_test_app(skill_reg: SkillRegistry, agent_reg: AgentRegistry) -> FastAPI:
    """Build a minimal FastAPI app with the skills router for testing."""
    from fastapi import APIRouter

    # Create a fresh router with the same endpoints but at /v1 prefix
    test_router = APIRouter(prefix="/v1", tags=["skills-test"])

    # Re-register each endpoint from the skills router onto our test router
    from mascarade.routers.skills import (
        assign_skill,
        create_skill,
        delete_skill,
        get_skill,
        list_agent_skills,
        list_skills,
        unassign_skill,
        update_skill,
    )

    test_router.add_api_route("/skills", create_skill, methods=["POST"])
    test_router.add_api_route("/skills", list_skills, methods=["GET"])
    test_router.add_api_route("/skills/{name}", get_skill, methods=["GET"])
    test_router.add_api_route("/skills/{name}", update_skill, methods=["PUT"])
    test_router.add_api_route("/skills/{name}", delete_skill, methods=["DELETE"])
    test_router.add_api_route(
        "/skills/{name}/assign/{agent_name}", assign_skill, methods=["POST"]
    )
    test_router.add_api_route(
        "/skills/{name}/assign/{agent_name}", unassign_skill, methods=["DELETE"]
    )
    test_router.add_api_route(
        "/agents/{agent_name}/skills", list_agent_skills, methods=["GET"]
    )

    test_app = FastAPI()
    test_app.include_router(test_router)
    test_app.state.skill_registry = skill_reg
    test_app.state.registry = agent_reg
    return test_app


@asynccontextmanager
async def _client():
    """Create test client with a standalone skills app and temp storage."""
    with tempfile.TemporaryDirectory() as tmpdir:
        skill_reg = SkillRegistry(storage_path=Path(tmpdir) / "skills.json")
        register_default_skills_v2(skill_reg)
        agent_reg = AgentRegistry(storage_path=Path(tmpdir) / "agents.json")
        # Register test agents so assign/unassign tests have targets
        agent_reg.register(
            Agent(name="summarizer", description="Summarizer", system_prompt="Summarize."),
            builtin=True,
        )
        agent_reg.register(
            Agent(name="coder", description="Coder", system_prompt="Code."),
            builtin=True,
        )

        test_app = _build_test_app(skill_reg, agent_reg)
        transport = httpx.ASGITransport(app=test_app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            yield client


# --- SkillRegistry unit tests ---


def test_skill_registry_register_and_get():
    reg = SkillRegistry(storage_path=None)
    skill = Skill(
        name="test-skill",
        description="A test skill",
        category="text",
        instruction="Do something useful.",
    )
    reg.register(skill)
    assert reg.get("test-skill") is skill
    assert len(reg) == 1


def test_skill_registry_list():
    reg = SkillRegistry(storage_path=None)
    reg.register(Skill(name="a", description="A", category="text", instruction="A"))
    reg.register(Skill(name="b", description="B", category="code", instruction="B"))
    assert len(reg.list()) == 2


def test_skill_registry_contains():
    reg = SkillRegistry(storage_path=None)
    reg.register(Skill(name="x", description="X", category="text", instruction="X"))
    assert "x" in reg
    assert "y" not in reg


def test_skill_registry_remove():
    reg = SkillRegistry(storage_path=None)
    reg.register(
        Skill(name="rm", description="Remove me", category="text", instruction="RM")
    )
    reg.remove("rm")
    assert "rm" not in reg


def test_skill_registry_get_missing():
    reg = SkillRegistry(storage_path=None)
    with pytest.raises(KeyError):
        reg.get("missing")


def test_skill_registry_is_builtin():
    reg = SkillRegistry(storage_path=None)
    reg.register(
        Skill(name="builtin", description="B", category="text", instruction="B"),
        builtin=True,
    )
    reg.register(
        Skill(name="dynamic", description="D", category="text", instruction="D")
    )
    assert reg.is_builtin("builtin") is True
    assert reg.is_builtin("dynamic") is False


def test_skill_registry_save_and_load(tmp_path):
    """Dynamic skills are persisted and reloaded; builtins are not."""
    storage = tmp_path / "skills.json"

    reg = SkillRegistry(storage_path=storage)
    reg.register(
        Skill(name="builtin", description="B", category="text", instruction="B"),
        builtin=True,
    )
    reg.register(
        Skill(
            name="dynamic",
            description="D",
            category="code",
            instruction="D instruction",
            tools=["tool1"],
        )
    )
    reg.save()

    reg2 = SkillRegistry(storage_path=storage)
    reg2.load()
    assert "dynamic" in reg2
    assert "builtin" not in reg2  # builtin not persisted
    loaded = reg2.get("dynamic")
    assert loaded.category == "code"
    assert loaded.tools == ["tool1"]


def test_skill_registry_save_noop_when_disabled():
    reg = SkillRegistry(storage_path=None)
    reg.register(Skill(name="x", description="X", category="text", instruction="X"))
    reg.save()  # should not raise


def test_skill_registry_load_noop_when_no_file(tmp_path):
    storage = tmp_path / "nonexistent.json"
    reg = SkillRegistry(storage_path=storage)
    reg.load()
    assert len(reg) == 0


# --- register_default_skills_v2 ---


def test_register_default_skills_v2():
    reg = SkillRegistry(storage_path=None)
    register_default_skills_v2(reg)
    assert len(reg) > 0
    # Test the actual skills that are registered in register_default_skills_v2
    assert "structured-output" in reg
    assert "chain-of-thought" in reg
    skill = reg.get("structured-output")
    assert skill.category == "output"
    assert reg.is_builtin("structured-output") is True


# --- Agent.get_enhanced_system_prompt ---


def test_agent_enhanced_system_prompt():
    skill_reg = SkillRegistry(storage_path=None)
    skill_reg.register(
        Skill(
            name="code-review",
            description="Code review",
            category="code",
            instruction="Always review code for security issues.",
        )
    )
    skill_reg.register(
        Skill(
            name="disabled-skill",
            description="Disabled",
            category="text",
            instruction="This should not appear.",
            enabled=False,
        )
    )

    agent = Agent(
        name="test-agent",
        description="Test",
        system_prompt="You are a helpful assistant.",
        skills=["code-review", "disabled-skill", "nonexistent"],
    )

    enhanced = agent.get_enhanced_system_prompt(skill_reg)
    assert "You are a helpful assistant." in enhanced
    assert "Always review code for security issues." in enhanced
    assert "This should not appear." not in enhanced  # disabled skill excluded


def test_agent_enhanced_prompt_no_skills():
    skill_reg = SkillRegistry(storage_path=None)
    agent = Agent(name="bare", description="Bare", system_prompt="Base prompt.")
    assert agent.get_enhanced_system_prompt(skill_reg) == "Base prompt."


# --- API tests ---


@pytest.mark.asyncio
async def test_create_skill():
    async with _client() as client:
        resp = await client.post(
            "/v1/skills",
            json={
                "name": "my-skill",
                "description": "A custom skill",
                "category": "text",
                "instruction": "Be concise.",
            },
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "my-skill"
    assert data["category"] == "text"
    assert data["builtin"] is False


@pytest.mark.asyncio
async def test_create_duplicate_skill():
    async with _client() as client:
        await client.post(
            "/v1/skills",
            json={
                "name": "dup-skill",
                "description": "First",
                "category": "text",
                "instruction": "First instruction.",
            },
        )
        resp = await client.post(
            "/v1/skills",
            json={
                "name": "dup-skill",
                "description": "Second",
                "category": "text",
                "instruction": "Second instruction.",
            },
        )
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_list_skills():
    async with _client() as client:
        resp = await client.get("/v1/skills")
    assert resp.status_code == 200
    data = resp.json()
    assert "skills" in data
    assert isinstance(data["skills"], list)
    # Should include builtin skills at minimum
    assert len(data["skills"]) > 0


@pytest.mark.asyncio
async def test_get_skill():
    async with _client() as client:
        # builtin "structured-output" should exist
        resp = await client.get("/v1/skills/structured-output")
    assert resp.status_code == 200
    assert resp.json()["name"] == "structured-output"
    assert resp.json()["builtin"] is True


@pytest.mark.asyncio
async def test_get_skill_not_found():
    async with _client() as client:
        resp = await client.get("/v1/skills/nonexistent-skill")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_update_skill():
    async with _client() as client:
        # Create a dynamic skill first
        await client.post(
            "/v1/skills",
            json={
                "name": "updatable",
                "description": "Original",
                "category": "text",
                "instruction": "Original instruction.",
            },
        )
        resp = await client.put(
            "/v1/skills/updatable",
            json={
                "description": "Updated",
                "category": "code",
                "instruction": "Updated instruction.",
            },
        )
    assert resp.status_code == 200
    assert resp.json()["description"] == "Updated"
    assert resp.json()["category"] == "code"


@pytest.mark.asyncio
async def test_update_builtin_skill_forbidden():
    async with _client() as client:
        resp = await client.put(
            "/v1/skills/structured-output",
            json={
                "description": "Hacked",
                "category": "text",
                "instruction": "Hacked instruction.",
            },
        )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_delete_skill():
    async with _client() as client:
        await client.post(
            "/v1/skills",
            json={
                "name": "deletable",
                "description": "Delete me",
                "category": "text",
                "instruction": "Delete instruction.",
            },
        )
        resp = await client.delete("/v1/skills/deletable")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_delete_builtin_skill_forbidden():
    async with _client() as client:
        resp = await client.delete("/v1/skills/structured-output")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_assign_and_unassign_skill():
    async with _client() as client:
        # Create a dynamic skill
        await client.post(
            "/v1/skills",
            json={
                "name": "assignable",
                "description": "Assignable skill",
                "category": "text",
                "instruction": "Be assignable.",
            },
        )

        # Assign to builtin agent "summarizer"
        resp = await client.post("/v1/skills/assignable/assign/summarizer")
        assert resp.status_code == 200

        # List agent skills
        resp = await client.get("/v1/agents/summarizer/skills")
        assert resp.status_code == 200
        skill_names = [s["name"] for s in resp.json()["skills"]]
        assert "assignable" in skill_names

        # Unassign
        resp = await client.delete("/v1/skills/assignable/assign/summarizer")
        assert resp.status_code == 200

        # Verify removed
        resp = await client.get("/v1/agents/summarizer/skills")
        skill_names = [s["name"] for s in resp.json()["skills"]]
        assert "assignable" not in skill_names


@pytest.mark.asyncio
async def test_assign_duplicate_skill():
    async with _client() as client:
        await client.post(
            "/v1/skills",
            json={
                "name": "dup-assign",
                "description": "Dup",
                "category": "text",
                "instruction": "Dup.",
            },
        )
        await client.post("/v1/skills/dup-assign/assign/summarizer")
        resp = await client.post("/v1/skills/dup-assign/assign/summarizer")
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_assign_nonexistent_skill():
    async with _client() as client:
        resp = await client.post("/v1/skills/nonexistent/assign/summarizer")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_assign_skill_to_nonexistent_agent():
    async with _client() as client:
        await client.post(
            "/v1/skills",
            json={
                "name": "orphan-skill",
                "description": "Orphan",
                "category": "text",
                "instruction": "Orphan.",
            },
        )
        resp = await client.post("/v1/skills/orphan-skill/assign/nonexistent-agent")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_unassign_not_assigned():
    async with _client() as client:
        resp = await client.delete("/v1/skills/summarizer/assign/summarizer")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_list_agent_skills_empty():
    async with _client() as client:
        # Use "coder" agent which shouldn't have skills assigned by other tests
        resp = await client.get("/v1/agents/coder/skills")
    assert resp.status_code == 200
    assert resp.json()["skills"] == []


@pytest.mark.asyncio
async def test_list_agent_skills_nonexistent_agent():
    async with _client() as client:
        resp = await client.get("/v1/agents/nonexistent-agent/skills")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_skill_unassigns_from_agents():
    """Deleting a skill should remove it from all agents that have it assigned."""
    async with _client() as client:
        await client.post(
            "/v1/skills",
            json={
                "name": "cascade-delete",
                "description": "Will be deleted",
                "category": "text",
                "instruction": "Cascade.",
            },
        )
        await client.post("/v1/skills/cascade-delete/assign/summarizer")

        # Verify assigned
        resp = await client.get("/v1/agents/summarizer/skills")
        assert any(s["name"] == "cascade-delete" for s in resp.json()["skills"])

        # Delete the skill
        await client.delete("/v1/skills/cascade-delete")

        # Verify unassigned
        resp = await client.get("/v1/agents/summarizer/skills")
        assert all(s["name"] != "cascade-delete" for s in resp.json()["skills"])
