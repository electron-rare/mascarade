"""Tests pour le versionnage des prompts."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from mascarade.agents.base import Agent
from mascarade.agents.prompt_versioning import PromptHistory, PromptVersion
from mascarade.agents.registry import AgentRegistry
from mascarade.router.router import Strategy


def test_auto_version_on_prompt_change():
    """Test automatic version creation when prompt changes on save."""
    with tempfile.TemporaryDirectory() as tmpdir:
        storage_path = Path(tmpdir) / "agents.json"
        registry = AgentRegistry(storage_path=storage_path)

        # Create an agent with initial prompt
        agent = Agent(
            name="test-agent",
            description="Test agent",
            system_prompt="Initial prompt",
            strategy=Strategy.BEST,
        )
        registry.register(agent)
        registry.save()

        # Verify no versions yet (initial save doesn't create version)
        assert len(agent.prompt_versions) == 0

        # Update the prompt
        agent.system_prompt = "Updated prompt"
        registry.save()

        # Verify a version was created
        assert len(agent.prompt_versions) == 1
        version = agent.prompt_versions[0]
        assert version["version_number"] == 1
        assert version["content"] == "Initial prompt"  # Version stores the OLD prompt
        assert "timestamp" in version
        assert "author_hash" in version

        # Update the prompt again
        agent.system_prompt = "Second update"
        registry.save()

        # Verify second version was created
        assert len(agent.prompt_versions) == 2
        version2 = agent.prompt_versions[1]
        assert version2["version_number"] == 2
        assert version2["content"] == "Updated prompt"  # Version stores the previous prompt
        assert version2["diff"] is not None  # Should have diff from previous

        # Save again without changing prompt - no new version
        registry.save()
        assert len(agent.prompt_versions) == 2
