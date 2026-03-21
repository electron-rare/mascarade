"""Tests for GPT-5.3 Codex Provider."""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from mascarade.router.providers.gpt53_codex import (
    GPT53CodexProvider,
    GPT53CodexFunctionCalling,
)
from mascarade.router.providers.base import LLMResponse


@pytest.mark.asyncio
async def test_gpt53_codex_initialization():
    """Test GPT-5.3 Codex provider initialization."""
    with patch('mascarade.router.providers.gpt53_codex.openai.AsyncOpenAI') as mock_client:
        provider = GPT53CodexProvider(api_key="test-key")
        mock_client.assert_called_once()
        assert provider.name == "gpt-5.3-codex"
        assert provider.cost_per_million == (1.75, 14.0)


@pytest.mark.asyncio
async def test_gpt53_codex_send():
    """Test GPT-5.3 Codex send method."""
    with patch('mascarade.router.providers.gpt53_codex.openai.AsyncOpenAI') as mock_client:
        # Setup mock response
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message = MagicMock()
        mock_response.choices[0].message.content = "test response"
        mock_response.model = "gpt-5.3-codex"
        mock_response.usage = MagicMock()
        mock_response.usage.prompt_tokens = 10
        mock_response.usage.completion_tokens = 20
        mock_response.usage.total_tokens = 30
        
        mock_completion = AsyncMock()
        mock_completion.return_value = mock_response
        mock_client.return_value.chat.completions.create = mock_completion
        
        provider = GPT53CodexProvider(api_key="test-key")
        
        # Test send
        messages = [{"role": "user", "content": "test"}]
        response = await provider.send(messages)
        
        # Verify
        assert isinstance(response, LLMResponse)
        assert response.content == "test response"
        assert response.model == "gpt-5.3-codex"
        assert response.usage["total_tokens"] == 30


@pytest.mark.asyncio
async def test_gpt53_codex_stream():
    """Test GPT-5.3 Codex stream method."""
    with patch('mascarade.router.providers.gpt53_codex.openai.AsyncOpenAI') as mock_client:
        # Setup mock stream
        mock_chunk1 = MagicMock()
        mock_chunk1.choices = [MagicMock()]
        mock_chunk1.choices[0].delta = MagicMock()
        mock_chunk1.choices[0].delta.content = "chunk1"
        
        mock_chunk2 = MagicMock()
        mock_chunk2.choices = [MagicMock()]
        mock_chunk2.choices[0].delta = MagicMock()
        mock_chunk2.choices[0].delta.content = "chunk2"
        
        async def mock_stream():
            yield mock_chunk1
            yield mock_chunk2
        
        mock_completion = AsyncMock()
        mock_completion.return_value = mock_stream()
        mock_client.return_value.chat.completions.create = mock_completion
        
        provider = GPT53CodexProvider(api_key="test-key")
        
        # Test stream
        messages = [{"role": "user", "content": "test"}]
        chunks = []
        async for chunk in provider.stream(messages):
            chunks.append(chunk)
        
        # Verify
        assert chunks == ["chunk1", "chunk2"]


@pytest.mark.asyncio
async def test_gpt53_codex_function_calling():
    """Test GPT-5.3 Codex function calling."""
    with patch('mascarade.router.providers.gpt53_codex.openai.AsyncOpenAI') as mock_client:
        # Setup mock response with tool calls
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message = MagicMock()
        mock_response.choices[0].message.content = "Function called"
        mock_response.choices[0].message.tool_calls = [
            MagicMock(
                id="call-1",
                type="function",
                function=MagicMock(
                    name="get_weather",
                    arguments=json.dumps({"location": "Paris"})
                )
            )
        ]
        mock_response.model = "gpt-5.3-codex"
        mock_response.usage = MagicMock()
        mock_response.usage.prompt_tokens = 15
        mock_response.usage.completion_tokens = 25
        mock_response.usage.total_tokens = 40
        
        mock_completion = AsyncMock()
        mock_completion.return_value = mock_response
        mock_client.return_value.chat.completions.create = mock_completion
        
        provider = GPT53CodexProvider(api_key="test-key")
        function_calling = GPT53CodexFunctionCalling(provider)
        
        # Define test function
        functions = [
            {
                "name": "get_weather",
                "description": "Get weather for a location",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "location": {"type": "string"}
                    }
                },
                "implementation": lambda location: {"weather": "sunny", "temp": 22}
            }
        ]
        
        # Test function calling
        messages = [{"role": "user", "content": "What's the weather?"}]
        response = await function_calling.call_with_functions(messages, functions)
        
        # Verify
        assert isinstance(response, LLMResponse)
        assert response.content == "Function called"
        assert hasattr(response, 'tool_calls')


@pytest.mark.asyncio
async def test_gpt53_codex_interactive_workflow():
    """Test GPT-5.3 Codex interactive multi-turn workflow."""
    with patch('mascarade.router.providers.gpt53_codex.openai.AsyncOpenAI') as mock_client:
        # Setup mock responses for multi-turn
        mock_response1 = MagicMock()
        mock_response1.choices = [MagicMock()]
        mock_response1.choices[0].message = MagicMock()
        mock_response1.choices[0].message.content = "Calling function"
        mock_response1.choices[0].message.tool_calls = [
            MagicMock(
                id="call-1",
                type="function",
                function=MagicMock(
                    name="get_data",
                    arguments=json.dumps({"source": "api"})
                )
            )
        ]
        
        mock_response2 = MagicMock()
        mock_response2.choices = [MagicMock()]
        mock_response2.choices[0].message = MagicMock()
        mock_response2.choices[0].message.content = "Final answer"
        mock_response2.choices[0].message.tool_calls = None
        
        mock_completion = AsyncMock()
        mock_completion.side_effect = [mock_response1, mock_response2]
        mock_client.return_value.chat.completions.create = mock_completion
        
        provider = GPT53CodexProvider(api_key="test-key")
        function_calling = GPT53CodexFunctionCalling(provider)
        
        # Define test function
        functions = [
            {
                "name": "get_data",
                "description": "Get data from source",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "source": {"type": "string"}
                    }
                },
                "implementation": lambda source: {"data": "sample data"}
            }
        ]
        
        # Test interactive workflow
        messages = [{"role": "user", "content": "Get data and process"}]
        responses = await function_calling.call_with_interactive_workflow(
            messages, functions, max_turns=2
        )
        
        # Verify
        assert len(responses) == 2
        assert responses[0].content == "Calling function"
        assert responses[1].content == "Final answer"


def test_gpt53_codex_without_openai():
    """Test when OpenAI library is not available."""
    with patch('mascarade.router.providers.gpt53_codex.GPT53_CODEX_AVAILABLE', False):
        with pytest.raises(RuntimeError, match="OpenAI Python library not available"):
            GPT53CodexProvider(api_key="test-key")
