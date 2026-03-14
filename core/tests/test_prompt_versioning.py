"""Tests pour le versionnage des prompts."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from mascarade.agents.base import Agent
from mascarade.agents.prompt_versioning import (
    PromptHistory,
    PromptVersion,
    iso_utc_now,
)
from mascarade.agents.registry import AgentRegistry
from mascarade.router.router import Strategy


# =============================================================================
# Unit tests for PromptVersion and PromptHistory classes
# =============================================================================


def test_iso_utc_now_returns_utc_timestamp():
    """iso_utc_now retourne un timestamp ISO8601 UTC avec suffixe Z."""
    timestamp = iso_utc_now()
    assert timestamp.endswith("Z")
    assert "T" in timestamp


def test_prompt_version_creation():
    """Création d'une PromptVersion avec tous les champs."""
    version = PromptVersion(
        version_number=1,
        timestamp="2026-03-14T10:00:00Z",
        content="You are a helpful assistant.",
        author_hash="abc123",
        diff=None,
        note="Initial version",
    )
    assert version.version_number == 1
    assert version.timestamp == "2026-03-14T10:00:00Z"
    assert version.content == "You are a helpful assistant."
    assert version.author_hash == "abc123"
    assert version.diff is None
    assert version.note == "Initial version"


def test_prompt_version_minimal_creation():
    """Création d'une PromptVersion avec champs minimaux."""
    version = PromptVersion(
        version_number=1,
        timestamp="2026-03-14T10:00:00Z",
        content="Test prompt",
        author_hash="xyz789",
    )
    assert version.version_number == 1
    assert version.diff is None
    assert version.note is None


def test_prompt_history_init():
    """Initialisation de PromptHistory."""
    history = PromptHistory(storage_path=None)
    assert history.get_history() == []


def test_add_version_first():
    """Ajouter la première version d'un prompt."""
    history = PromptHistory(storage_path=None)
    version = history.add_version(
        content="You are a helpful assistant.",
        author_hash="user123",
        note="Initial version",
    )
    assert version.version_number == 1
    assert version.content == "You are a helpful assistant."
    assert version.author_hash == "user123"
    assert version.note == "Initial version"
    assert version.diff is None  # Pas de diff pour la première version
    assert version.timestamp.endswith("Z")


def test_add_version_second_with_diff():
    """Ajouter une deuxième version génère un diff."""
    history = PromptHistory(storage_path=None)
    history.add_version(
        content="You are a helpful assistant.",
        author_hash="user123",
    )
    version2 = history.add_version(
        content="You are a very helpful assistant.",
        author_hash="user123",
    )
    assert version2.version_number == 2
    assert version2.diff is not None
    assert len(version2.diff) > 0


def test_get_history():
    """Récupérer l'historique complet."""
    history = PromptHistory(storage_path=None)
    history.add_version(content="v1", author_hash="a")
    history.add_version(content="v2", author_hash="a")
    history.add_version(content="v3", author_hash="a")

    versions = history.get_history()
    assert len(versions) == 3
    assert versions[0].version_number == 1
    assert versions[1].version_number == 2
    assert versions[2].version_number == 3


def test_get_history_with_limit():
    """Récupérer l'historique avec une limite."""
    history = PromptHistory(storage_path=None)
    history.add_version(content="v1", author_hash="a")
    history.add_version(content="v2", author_hash="a")
    history.add_version(content="v3", author_hash="a")

    versions = history.get_history(limit=2)
    assert len(versions) == 2
    assert versions[0].version_number == 2
    assert versions[1].version_number == 3


def test_get_history_with_since():
    """Récupérer l'historique depuis un timestamp."""
    history = PromptHistory(storage_path=None)
    v1 = history.add_version(content="v1", author_hash="a")
    v2 = history.add_version(content="v2", author_hash="a")
    v3 = history.add_version(content="v3", author_hash="a")

    versions = history.get_history(since=v2.timestamp)
    assert len(versions) == 2
    assert versions[0].version_number == 2
    assert versions[1].version_number == 3


def test_get_history_empty():
    """Récupérer l'historique d'un PromptHistory vide."""
    history = PromptHistory(storage_path=None)
    assert history.get_history() == []


def test_get_diff():
    """Calculer le diff entre deux versions."""
    history = PromptHistory(storage_path=None)
    history.add_version(content="Line 1\nLine 2", author_hash="a")
    history.add_version(content="Line 1\nLine 2 modified", author_hash="a")

    diff = history.get_diff(1, 2)
    assert "Line 2" in diff
    assert "Line 2 modified" in diff


def test_get_diff_invalid_from_version():
    """get_diff lève ValueError si from_version est invalide."""
    history = PromptHistory(storage_path=None)
    history.add_version(content="v1", author_hash="a")

    try:
        history.get_diff(0, 1)
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "introuvable" in str(e)


def test_get_diff_invalid_to_version():
    """get_diff lève ValueError si to_version est invalide."""
    history = PromptHistory(storage_path=None)
    history.add_version(content="v1", author_hash="a")

    try:
        history.get_diff(1, 99)
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "introuvable" in str(e)


def test_rollback():
    """Rollback vers une version précédente."""
    history = PromptHistory(storage_path=None)
    v1 = history.add_version(content="Original content", author_hash="a")
    history.add_version(content="Modified content", author_hash="a")

    rollback_version = history.rollback(1)
    assert rollback_version.version_number == 3
    assert rollback_version.content == "Original content"
    assert "Rollback to version 1" in rollback_version.note


def test_rollback_invalid_version():
    """rollback lève ValueError si la version est invalide."""
    history = PromptHistory(storage_path=None)
    history.add_version(content="v1", author_hash="a")

    try:
        history.rollback(99)
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "introuvable" in str(e)


def test_prune():
    """Supprimer les anciennes versions."""
    history = PromptHistory(storage_path=None)
    history.add_version(content="v1", author_hash="a")
    history.add_version(content="v2", author_hash="a")
    history.add_version(content="v3", author_hash="a")
    history.add_version(content="v4", author_hash="a")

    removed = history.prune(keep_count=2)
    assert removed == 2

    versions = history.get_history()
    assert len(versions) == 2
    assert versions[0].version_number == 1  # Renuméroté
    assert versions[1].version_number == 2  # Renuméroté
    assert versions[0].content == "v3"
    assert versions[1].content == "v4"


def test_prune_noop_when_below_threshold():
    """prune ne fait rien si déjà en dessous du seuil."""
    history = PromptHistory(storage_path=None)
    history.add_version(content="v1", author_hash="a")
    history.add_version(content="v2", author_hash="a")

    removed = history.prune(keep_count=5)
    assert removed == 0
    assert len(history.get_history()) == 2


def test_prune_invalid_keep_count():
    """prune lève ValueError si keep_count < 1."""
    history = PromptHistory(storage_path=None)
    history.add_version(content="v1", author_hash="a")

    try:
        history.prune(keep_count=0)
        assert False, "Should have raised ValueError"
    except ValueError:
        pass


def test_max_versions_auto_prune():
    """Auto-prune quand max_versions est défini."""
    history = PromptHistory(storage_path=None, max_versions=2)
    history.add_version(content="v1", author_hash="a")
    history.add_version(content="v2", author_hash="a")
    history.add_version(content="v3", author_hash="a")

    versions = history.get_history()
    assert len(versions) == 2
    assert versions[0].content == "v2"
    assert versions[1].content == "v3"


def test_save_and_load(tmp_path):
    """Sauvegarder et charger l'historique."""
    storage = tmp_path / "history.json"

    history1 = PromptHistory(storage_path=storage)
    history1.add_version(content="v1", author_hash="a", note="First")
    history1.add_version(content="v2", author_hash="b", note="Second")
    history1.save()

    history2 = PromptHistory(storage_path=storage)
    history2.load()
    versions = history2.get_history()

    assert len(versions) == 2
    assert versions[0].content == "v1"
    assert versions[0].author_hash == "a"
    assert versions[0].note == "First"
    assert versions[1].content == "v2"
    assert versions[1].author_hash == "b"
    assert versions[1].note == "Second"


def test_save_noop_when_disabled():
    """Pas d'erreur si storage_path=None."""
    history = PromptHistory(storage_path=None)
    history.add_version(content="v1", author_hash="a")
    history.save()  # Ne doit pas lever d'erreur


def test_load_noop_when_no_file(tmp_path):
    """Pas d'erreur si le fichier n'existe pas."""
    storage = tmp_path / "nonexistent.json"
    history = PromptHistory(storage_path=storage)
    history.load()  # Ne doit pas lever d'erreur
    assert len(history.get_history()) == 0


def test_load_with_invalid_json(tmp_path):
    """Charger un fichier JSON invalide ne lève pas d'erreur."""
    storage = tmp_path / "invalid.json"
    storage.write_text("{ invalid json", encoding="utf-8")

    history = PromptHistory(storage_path=storage)
    history.load()  # Ne doit pas lever d'erreur
    assert len(history.get_history()) == 0


def test_load_skips_invalid_entries(tmp_path):
    """Charger un fichier avec des entrées invalides les ignore."""
    storage = tmp_path / "partial.json"
    storage.write_text(
        '[{"version_number": 1, "timestamp": "2026-01-01T00:00:00Z", '
        '"content": "valid", "author_hash": "a"}, '
        '{"invalid": "entry"}]',
        encoding="utf-8",
    )

    history = PromptHistory(storage_path=storage)
    history.load()
    versions = history.get_history()

    assert len(versions) == 1
    assert versions[0].content == "valid"


# =============================================================================
# Integration tests with Agent and AgentRegistry
# =============================================================================


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
