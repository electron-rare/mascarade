"""Tests for AI Worker execute() dispatcher and validate() method."""

from __future__ import annotations

import pytest

from mascarade.agents.base import Agent
from mascarade.agents.registry import AgentRegistry
from mascarade.node_engine.workers.ai.worker import AIWorker
from mascarade.router import Router


@pytest.fixture
def mock_router():
    """Create a mock Router instance."""
    return Router()


@pytest.fixture
def mock_registry():
    """Create a mock AgentRegistry with a test agent."""
    registry = AgentRegistry()

    # Create a minimal test agent using proper instantiation
    test_agent = Agent(
        name="test-agent",
        description="A test agent",
        system_prompt="You are a test agent.",
    )

    # Register the test agent
    registry.register(test_agent)

    return registry


@pytest.fixture
def ai_worker(mock_router, mock_registry):
    """Create an AIWorker instance with mock dependencies."""
    return AIWorker(router=mock_router, registry=mock_registry)


class TestDispatch:
    """Test suite for execute() dispatcher."""

    @pytest.mark.asyncio
    async def test_dispatch_llm_inference_no_providers(self, ai_worker):
        """Test that ai.llm-inference fails when no providers are configured."""
        with pytest.raises(RuntimeError):
            await ai_worker.execute(
                node_type="ai.llm-inference",
                inputs={"prompt": "Test prompt"},
                config={},
                context=None,
            )

    @pytest.mark.asyncio
    async def test_dispatch_agent_dispatch_missing_agent(self, ai_worker):
        """Test that ai.agent-dispatch fails when agent doesn't exist."""
        with pytest.raises(KeyError):
            await ai_worker.execute(
                node_type="ai.agent-dispatch",
                inputs={"agent_name": "nonexistent-agent", "prompt": "Test message"},
                config={},
                context=None,
            )

    @pytest.mark.asyncio
    async def test_dispatch_llm_stream(self, ai_worker):
        """Test that ai.llm-stream dispatches correctly."""
        # Note: Comprehensive llm-stream tests are in test_ai_nodes.py with proper mocking
        # This test just verifies the dispatcher routes to the correct handler
        result = await ai_worker.execute(
            node_type="ai.llm-stream",
            inputs={"prompt": "Test prompt"},
            config={},
            context=None,
        )

        # Should return a dict with stream key
        assert "stream" in result
        # Stream is an async generator - comprehensive testing in test_ai_nodes.py

    @pytest.mark.asyncio
    async def test_dispatch_unsupported_node_type(self, ai_worker):
        """Test that unsupported node types raise ValueError."""
        with pytest.raises(ValueError, match="Unsupported node type: ai.unknown-node"):
            await ai_worker.execute(
                node_type="ai.unknown-node",
                inputs={},
                config={},
                context=None,
            )


class TestValidation:
    """Test suite for validate() method."""

    @pytest.mark.asyncio
    async def test_validate_llm_inference_missing_prompt(self, ai_worker):
        """Test that ai.llm-inference validation catches missing prompt."""
        errors = await ai_worker.validate(
            node_type="ai.llm-inference",
            inputs={},
            config={},
        )
        assert len(errors) == 1
        assert "Missing required input: prompt" in errors

    @pytest.mark.asyncio
    async def test_validate_llm_inference_valid(self, ai_worker):
        """Test that ai.llm-inference validation passes with valid inputs."""
        errors = await ai_worker.validate(
            node_type="ai.llm-inference",
            inputs={"prompt": "Test prompt"},
            config={},
        )
        assert len(errors) == 0

    @pytest.mark.asyncio
    async def test_validate_agent_dispatch_missing_agent_name(self, ai_worker):
        """Test that ai.agent-dispatch validation catches missing agent_name."""
        errors = await ai_worker.validate(
            node_type="ai.agent-dispatch",
            inputs={"message": "Test message"},
            config={},
        )
        assert len(errors) == 1
        assert "Missing required input: agent_name" in errors

    @pytest.mark.asyncio
    async def test_validate_agent_dispatch_missing_message(self, ai_worker):
        """Test that ai.agent-dispatch validation catches missing message."""
        errors = await ai_worker.validate(
            node_type="ai.agent-dispatch",
            inputs={"agent_name": "test-agent"},
            config={},
        )
        assert len(errors) == 1
        assert "Missing required input: message" in errors

    @pytest.mark.asyncio
    async def test_validate_agent_dispatch_missing_both(self, ai_worker):
        """Test that ai.agent-dispatch validation catches both missing inputs."""
        errors = await ai_worker.validate(
            node_type="ai.agent-dispatch",
            inputs={},
            config={},
        )
        assert len(errors) == 2
        assert any("agent_name" in e for e in errors)
        assert any("message" in e for e in errors)

    @pytest.mark.asyncio
    async def test_validate_agent_dispatch_nonexistent_agent(self, ai_worker):
        """Test that ai.agent-dispatch validation catches nonexistent agents."""
        errors = await ai_worker.validate(
            node_type="ai.agent-dispatch",
            inputs={"agent_name": "nonexistent-agent", "message": "Test message"},
            config={},
        )
        assert len(errors) == 1
        assert "Agent 'nonexistent-agent' not found in registry" in errors[0]

    @pytest.mark.asyncio
    async def test_validate_agent_dispatch_valid(self, ai_worker):
        """Test that ai.agent-dispatch validation passes with valid inputs."""
        errors = await ai_worker.validate(
            node_type="ai.agent-dispatch",
            inputs={"agent_name": "test-agent", "message": "Test message"},
            config={},
        )
        assert len(errors) == 0

    @pytest.mark.asyncio
    async def test_validate_llm_stream_missing_prompt(self, ai_worker):
        """Test that ai.llm-stream validation catches missing prompt."""
        errors = await ai_worker.validate(
            node_type="ai.llm-stream",
            inputs={},
            config={},
        )
        assert len(errors) == 1
        assert "Missing required input: prompt" in errors

    @pytest.mark.asyncio
    async def test_validate_llm_stream_valid(self, ai_worker):
        """Test that ai.llm-stream validation passes with valid inputs."""
        errors = await ai_worker.validate(
            node_type="ai.llm-stream",
            inputs={"prompt": "Test prompt"},
            config={},
        )
        assert len(errors) == 0

    @pytest.mark.asyncio
    async def test_validate_unsupported_node_type(self, ai_worker):
        """Test that unsupported node types produce validation error."""
        errors = await ai_worker.validate(
            node_type="ai.unknown-node",
            inputs={},
            config={},
        )
        assert len(errors) == 1
        assert "Unsupported node type: ai.unknown-node" in errors[0]
