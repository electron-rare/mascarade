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


def test_version_pruning():
    """Test automatic pruning of old versions when max_versions is set."""
    # Create history with max_versions=5
    history = PromptHistory(storage_path=None, max_versions=5)

    # Add 10 versions
    for i in range(1, 11):
        history.add_version(
            content=f"Prompt version {i}",
            author_hash="test-author",
            note=f"Version {i}",
        )

    # Should only keep last 5 versions
    assert len(history._versions) == 5

    # Version numbers should be renumbered to 1-5
    version_numbers = [v.version_number for v in history._versions]
    assert version_numbers == [1, 2, 3, 4, 5]

    # Content should be from versions 6-10
    contents = [v.content for v in history._versions]
    assert contents == [
        "Prompt version 6",
        "Prompt version 7",
        "Prompt version 8",
        "Prompt version 9",
        "Prompt version 10",
    ]

    # Add one more version
    history.add_version(
        content="Prompt version 11",
        author_hash="test-author",
        note="Version 11",
    )

    # Should still keep only 5 versions
    assert len(history._versions) == 5

    # Latest version should be version 11
    assert history._versions[-1].content == "Prompt version 11"
    assert history._versions[0].content == "Prompt version 7"


def test_version_pruning_disabled_by_default():
    """Test that pruning is disabled when max_versions is not set."""
    history = PromptHistory(storage_path=None)

    # Add many versions
    for i in range(1, 101):
        history.add_version(
            content=f"Prompt version {i}",
            author_hash="test-author",
        )

    # Should keep all 100 versions
    assert len(history._versions) == 100
