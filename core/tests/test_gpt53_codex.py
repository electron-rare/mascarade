"""Tests for GPT-5.3 Codex Provider."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mascarade.router.providers.gpt53_codex import GPT53_CODEX_AVAILABLE

# Skip entire module if openai is not installed
pytestmark = pytest.mark.skipif(
    not GPT53_CODEX_AVAILABLE,
    reason="openai not installed",
)


@pytest.fixture
def mock_openai():
    """Patch openai.AsyncOpenAI for all tests."""
    with patch("mascarade.router.providers.gpt53_codex.openai") as mock_mod:
        mock_client = AsyncMock()
        mock_mod.AsyncOpenAI.return_value = mock_client
        yield mock_client


@pytest.fixture
def mock_response():
    """Standard mock LLM response."""
    resp = MagicMock()
    resp.choices = [MagicMock()]
    resp.choices[0].message.content = "test response"
    resp.choices[0].message.tool_calls = None
    resp.model = "gpt-5.3-codex"
    resp.usage.prompt_tokens = 10
    resp.usage.completion_tokens = 20
    resp.usage.total_tokens = 30
    return resp


@pytest.mark.asyncio
async def test_gpt53_codex_initialization(mock_openai):
    from mascarade.router.providers.gpt53_codex import GPT53CodexProvider

    provider = GPT53CodexProvider(api_key="test-key")
    assert provider.name == "gpt-5.3-codex"
    assert provider.cost_per_million == (1.75, 14.0)


@pytest.mark.asyncio
async def test_gpt53_codex_send(mock_openai, mock_response):
    from mascarade.router.providers.gpt53_codex import GPT53CodexProvider

    mock_openai.chat.completions.create = AsyncMock(return_value=mock_response)
    provider = GPT53CodexProvider(api_key="test-key")

    messages = [{"role": "user", "content": "test"}]
    response = await provider.send(messages)

    assert response.content == "test response"
    assert response.model == "gpt-5.3-codex"


@pytest.mark.asyncio
async def test_gpt53_codex_stream(mock_openai):
    from mascarade.router.providers.gpt53_codex import GPT53CodexProvider

    chunk1 = MagicMock()
    chunk1.choices = [MagicMock()]
    chunk1.choices[0].delta.content = "chunk1"
    chunk2 = MagicMock()
    chunk2.choices = [MagicMock()]
    chunk2.choices[0].delta.content = "chunk2"

    async def mock_stream():
        yield chunk1
        yield chunk2

    mock_openai.chat.completions.create = AsyncMock(return_value=mock_stream())
    provider = GPT53CodexProvider(api_key="test-key")

    chunks = []
    async for chunk in provider.stream([{"role": "user", "content": "test"}]):
        chunks.append(chunk)

    assert chunks == ["chunk1", "chunk2"]


@pytest.mark.asyncio
async def test_gpt53_codex_function_calling(mock_openai, mock_response):
    from mascarade.router.providers.gpt53_codex import (
        GPT53CodexFunctionCalling,
        GPT53CodexProvider,
    )

    mock_response.choices[0].message.content = "Function called"
    mock_openai.chat.completions.create = AsyncMock(return_value=mock_response)

    provider = GPT53CodexProvider(api_key="test-key")
    fc = GPT53CodexFunctionCalling(provider)

    functions = [{"name": "get_weather", "description": "Get weather", "parameters": {}}]
    response = await fc.call_with_functions([{"role": "user", "content": "weather?"}], functions)
    assert response.content == "Function called"


def test_gpt53_codex_without_openai():
    """Test when OpenAI library is not available."""
    with patch("mascarade.router.providers.gpt53_codex.GPT53_CODEX_AVAILABLE", False):
        from mascarade.router.providers.gpt53_codex import GPT53CodexProvider

        with pytest.raises(RuntimeError, match="OpenAI Python library not available"):
            GPT53CodexProvider(api_key="test-key")
