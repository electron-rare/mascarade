"""Tests for CLI coding agents (Vibe, Codex, Claude Code)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mascarade.agents.cli_agents import (
    ClaudeCodeAgent,
    CodexAgent,
    VibeAgent,
    _cli_available,
    register_cli_agents,
)

# --- Availability ---


def test_cli_available_true():
    with patch("shutil.which", return_value="/usr/local/bin/vibe"):
        assert _cli_available("vibe") is True


def test_cli_available_false():
    with patch("shutil.which", return_value=None):
        assert _cli_available("nope") is False


# --- VibeAgent ---


def test_vibe_agent_attributes():
    agent = VibeAgent()
    assert agent.name == "vibe"
    assert "Mistral" in agent.description
    assert agent.temperature == 0.2


def test_vibe_agent_availability():
    with patch("shutil.which", return_value="/usr/local/bin/vibe"):
        agent = VibeAgent()
        assert agent.is_available is True

    with patch("shutil.which", return_value=None):
        agent = VibeAgent()
        assert agent.is_available is False


@pytest.mark.asyncio
async def test_vibe_agent_run():
    agent = VibeAgent()
    mock_output = '{"result": {"text": "def hello(): pass"}, "model": "devstral-small-2505", "usage": {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15}}'

    with patch("shutil.which", return_value="/usr/local/bin/vibe"):
        with patch("mascarade.agents.cli_agents._run_cli", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = (mock_output, "", 0)
            response = await agent.run("Write hello function")

            assert response.content == "def hello(): pass"
            assert response.provider == "vibe"
            assert response.usage["total_tokens"] == 15


@pytest.mark.asyncio
async def test_vibe_agent_not_available():
    with patch("shutil.which", return_value=None):
        agent = VibeAgent()
        with pytest.raises(RuntimeError, match="vibe CLI not found"):
            await agent.run("test")


# --- CodexAgent ---


def test_codex_agent_attributes():
    agent = CodexAgent()
    assert agent.name == "codex"
    assert "OpenAI" in agent.description


@pytest.mark.asyncio
async def test_codex_agent_run():
    agent = CodexAgent()

    with patch("shutil.which", return_value="/usr/local/bin/codex"):
        with patch("mascarade.agents.cli_agents._run_cli", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = ("Fixed the bug in line 42", "", 0)
            response = await agent.run("Fix the bug")

            assert response.content == "Fixed the bug in line 42"
            assert response.provider == "codex-cli"


# --- ClaudeCodeAgent ---


def test_claude_code_agent_attributes():
    agent = ClaudeCodeAgent()
    assert agent.name == "claude-code"
    assert "Anthropic" in agent.description


@pytest.mark.asyncio
async def test_claude_code_agent_run():
    agent = ClaudeCodeAgent()
    mock_output = '{"result": "Refactored the module", "model": "claude-sonnet-4-6", "usage": {"input_tokens": 100, "output_tokens": 50, "total_tokens": 150}}'

    with patch("shutil.which", return_value="/usr/local/bin/claude"):
        with patch("mascarade.agents.cli_agents._run_cli", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = (mock_output, "", 0)
            response = await agent.run("Refactor the module")

            assert response.content == "Refactored the module"
            assert response.provider == "claude-code"
            assert response.usage["total_tokens"] == 150


@pytest.mark.asyncio
async def test_claude_code_with_tools():
    agent = ClaudeCodeAgent(allowed_tools=["Read", "Edit", "Bash"])

    with patch("shutil.which", return_value="/usr/local/bin/claude"):
        with patch("mascarade.agents.cli_agents._run_cli", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = ("done", "", 0)
            await agent.run("Fix it")

            cmd = mock_run.call_args[0][0]
            assert "--allowedTools" in cmd
            assert "Read,Edit,Bash" in cmd


# --- Registration ---


def test_register_cli_agents():
    registry = MagicMock()

    with patch(
        "shutil.which",
        side_effect=lambda b: (f"/usr/local/bin/{b}" if b in ("vibe", "codex", "claude") else None),
    ):
        register_cli_agents(registry)

    # All 3 should be registered
    assert registry.register.call_count == 3
    names = [call[0][0].name for call in registry.register.call_args_list]
    assert "vibe" in names
    assert "codex" in names
    assert "claude-code" in names


def test_register_cli_agents_none_available():
    registry = MagicMock()

    with patch("shutil.which", return_value=None):
        register_cli_agents(registry)

    assert registry.register.call_count == 0
