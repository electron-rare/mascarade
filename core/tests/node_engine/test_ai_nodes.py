"""Tests for AI node execution handlers."""

from __future__ import annotations

import pytest

from mascarade.agents.registry import AgentRegistry
from mascarade.node_engine.workers.ai.worker import AIWorker
from mascarade.router import Router
from mascarade.router.providers.base import LLMResponse


@pytest.fixture
def mock_router(monkeypatch):
    """Create a mock Router instance."""
    router = Router()

    # Mock the send method to return a test response
    async def mock_send(*args, **kwargs):
        return LLMResponse(
            content="Test response",
            model="test-model",
            provider="test-provider",
            usage={"input_tokens": 10, "output_tokens": 20},
        )

    # Mock the stream method to return an async iterator
    async def mock_stream(*args, **kwargs):
        tokens = ["Test", " ", "streaming", " ", "response"]
        for token in tokens:
            yield token

    monkeypatch.setattr(router, "send", mock_send)
    monkeypatch.setattr(router, "stream", mock_stream)
    return router


@pytest.fixture
def mock_registry():
    """Create an empty AgentRegistry."""
    return AgentRegistry()


@pytest.fixture
def ai_worker(mock_router, mock_registry):
    """Create an AIWorker instance with mock dependencies."""
    return AIWorker(router=mock_router, registry=mock_registry)


class TestLLMInference:
    """Test suite for ai.llm-inference execution."""

    @pytest.mark.asyncio
    async def test_llm_inference(self, ai_worker):
        """Test basic LLM inference with prompt."""
        result = await ai_worker.execute(
            node_type="ai.llm-inference",
            inputs={"prompt": "Hello, world!"},
            config={},
            context=None,
        )

        assert "response" in result
        response = result["response"]
        assert isinstance(response, LLMResponse)
        assert response.content == "Test response"
        assert response.model == "test-model"
        assert response.provider == "test-provider"

    @pytest.mark.asyncio
    async def test_llm_inference_with_config(self, ai_worker):
        """Test LLM inference with custom config parameters."""
        result = await ai_worker.execute(
            node_type="ai.llm-inference",
            inputs={"prompt": "Test prompt"},
            config={
                "model": "custom-model",
                "temperature": 0.5,
                "max_tokens": 2048,
            },
            context=None,
        )

        assert "response" in result
        response = result["response"]
        assert isinstance(response, LLMResponse)

    @pytest.mark.asyncio
    async def test_llm_inference_with_system(self, ai_worker):
        """Test LLM inference with system prompt."""
        result = await ai_worker.execute(
            node_type="ai.llm-inference",
            inputs={
                "prompt": "What is 2+2?",
                "system": "You are a helpful math tutor.",
            },
            config={},
            context=None,
        )

        assert "response" in result
        response = result["response"]
        assert isinstance(response, LLMResponse)


class TestLLMStream:
    """Test suite for ai.llm-stream execution."""

    @pytest.mark.asyncio
    async def test_llm_stream(self, ai_worker):
        """Test basic LLM streaming with prompt."""
        result = await ai_worker.execute(
            node_type="ai.llm-stream",
            inputs={"prompt": "Hello, world!"},
            config={},
            context=None,
        )

        assert "stream" in result
        stream = result["stream"]

        # Collect all tokens from the stream
        tokens = []
        async for token in stream:
            tokens.append(token)

        # Verify we received the expected tokens
        assert len(tokens) == 5
        assert "".join(tokens) == "Test streaming response"

    @pytest.mark.asyncio
    async def test_llm_stream_with_config(self, ai_worker):
        """Test LLM streaming with custom config parameters."""
        result = await ai_worker.execute(
            node_type="ai.llm-stream",
            inputs={"prompt": "Test prompt"},
            config={
                "model": "custom-model",
                "temperature": 0.5,
                "max_tokens": 2048,
            },
            context=None,
        )

        assert "stream" in result
        stream = result["stream"]

        # Verify stream is iterable
        tokens = []
        async for token in stream:
            tokens.append(token)

        assert len(tokens) > 0

    @pytest.mark.asyncio
    async def test_llm_stream_with_system(self, ai_worker):
        """Test LLM streaming with system prompt."""
        result = await ai_worker.execute(
            node_type="ai.llm-stream",
            inputs={
                "prompt": "What is 2+2?",
                "system": "You are a helpful math tutor.",
            },
            config={},
            context=None,
        )

        assert "stream" in result
        stream = result["stream"]

        # Verify stream is iterable
        tokens = []
        async for token in stream:
            tokens.append(token)

        assert len(tokens) > 0


class TestBatchInference:
    """Test suite for ai.batch-inference execution."""

    @pytest.mark.asyncio
    async def test_batch_inference(self, ai_worker):
        """Test batch inference with multiple prompts."""
        result = await ai_worker.execute(
            node_type="ai.batch-inference",
            inputs={"prompts": ["Hello", "World", "Test"]},
            config={},
            context=None,
        )

        assert "responses" in result
        responses = result["responses"]
        assert isinstance(responses, list)
        assert len(responses) == 3

        # Verify each response is an LLMResponse
        for response in responses:
            assert isinstance(response, LLMResponse)
            assert response.content == "Test response"
            assert response.model == "test-model"
            assert response.provider == "test-provider"

    @pytest.mark.asyncio
    async def test_batch_inference_with_config(self, ai_worker):
        """Test batch inference with custom config parameters."""
        result = await ai_worker.execute(
            node_type="ai.batch-inference",
            inputs={"prompts": ["Prompt 1", "Prompt 2"]},
            config={
                "model": "custom-model",
                "temperature": 0.5,
                "max_tokens": 2048,
            },
            context=None,
        )

        assert "responses" in result
        responses = result["responses"]
        assert isinstance(responses, list)
        assert len(responses) == 2

    @pytest.mark.asyncio
    async def test_batch_inference_empty_list(self, ai_worker):
        """Test batch inference with empty prompts list."""
        result = await ai_worker.execute(
            node_type="ai.batch-inference",
            inputs={"prompts": []},
            config={},
            context=None,
        )

        assert "responses" in result
        responses = result["responses"]
        assert isinstance(responses, list)
        assert len(responses) == 0


class TestPromptTemplate:
    """Test suite for ai.prompt-template execution."""

    @pytest.mark.asyncio
    async def test_prompt_template(self, ai_worker):
        """Test basic prompt template variable substitution."""
        result = await ai_worker.execute(
            node_type="ai.prompt-template",
            inputs={
                "template": "Hello {{name}}, your role is {{role}}!",
                "variables": {"name": "Alice", "role": "developer"},
            },
            config={},
            context=None,
        )

        assert "prompt" in result
        assert result["prompt"] == "Hello Alice, your role is developer!"

    @pytest.mark.asyncio
    async def test_prompt_template_empty_variables(self, ai_worker):
        """Test prompt template with no variables."""
        result = await ai_worker.execute(
            node_type="ai.prompt-template",
            inputs={
                "template": "This is a static template.",
                "variables": {},
            },
            config={},
            context=None,
        )

        assert "prompt" in result
        assert result["prompt"] == "This is a static template."

    @pytest.mark.asyncio
    async def test_prompt_template_partial_substitution(self, ai_worker):
        """Test prompt template with some variables missing."""
        result = await ai_worker.execute(
            node_type="ai.prompt-template",
            inputs={
                "template": "Hello {{name}}, {{greeting}} from {{place}}!",
                "variables": {"name": "Bob", "place": "Earth"},
            },
            config={},
            context=None,
        )

        assert "prompt" in result
        # Unmatched variables should remain as placeholders
        assert result["prompt"] == "Hello Bob, {{greeting}} from Earth!"

    @pytest.mark.asyncio
    async def test_prompt_template_type_coercion(self, ai_worker):
        """Test prompt template with non-string variable values."""
        result = await ai_worker.execute(
            node_type="ai.prompt-template",
            inputs={
                "template": "Count: {{count}}, Price: {{price}}",
                "variables": {"count": 42, "price": 19.99},
            },
            config={},
            context=None,
        )

        assert "prompt" in result
        assert result["prompt"] == "Count: 42, Price: 19.99"


class TestChainOfThought:
    """Test suite for ai.chain-of-thought execution."""

    @pytest.mark.asyncio
    async def test_chain_of_thought(self, ai_worker):
        """Test basic chain-of-thought multi-step reasoning."""
        result = await ai_worker.execute(
            node_type="ai.chain-of-thought",
            inputs={
                "question": "What is the capital of France?",
                "steps": 2,
            },
            config={},
            context=None,
        )

        assert "reasoning" in result
        assert "answer" in result
        assert "usage" in result

        # Verify reasoning is a list with correct number of steps
        reasoning = result["reasoning"]
        assert isinstance(reasoning, list)
        assert len(reasoning) == 2

        # Verify each reasoning step is a string
        for step in reasoning:
            assert isinstance(step, str)
            assert len(step) > 0

        # Verify answer is a string
        assert isinstance(result["answer"], str)
        assert len(result["answer"]) > 0

        # Verify usage is a dict
        assert isinstance(result["usage"], dict)

    @pytest.mark.asyncio
    async def test_chain_of_thought_default_steps(self, ai_worker):
        """Test chain-of-thought with default steps (3)."""
        result = await ai_worker.execute(
            node_type="ai.chain-of-thought",
            inputs={
                "question": "Why is the sky blue?",
            },
            config={},
            context=None,
        )

        assert "reasoning" in result
        reasoning = result["reasoning"]
        assert isinstance(reasoning, list)
        # Default steps should be 3
        assert len(reasoning) == 3

    @pytest.mark.asyncio
    async def test_chain_of_thought_with_config(self, ai_worker):
        """Test chain-of-thought with custom config parameters."""
        result = await ai_worker.execute(
            node_type="ai.chain-of-thought",
            inputs={
                "question": "Explain photosynthesis.",
                "steps": 1,
            },
            config={
                "model": "custom-model",
                "temperature": 0.5,
                "max_tokens": 2048,
            },
            context=None,
        )

        assert "reasoning" in result
        assert "answer" in result
        assert len(result["reasoning"]) == 1
