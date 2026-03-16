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

    monkeypatch.setattr(router, "send", mock_send)
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
