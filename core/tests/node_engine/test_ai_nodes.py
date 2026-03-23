"""Tests for AI node execution handlers."""

from __future__ import annotations

import pytest

from mascarade.agents.base import Agent
from mascarade.agents.registry import AgentRegistry
from mascarade.node_engine.workers.ai.worker import AIWorker
from mascarade.router import Router
from mascarade.router.providers.base import LLMResponse
from mascarade.router.router import Strategy


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


class TestClassify:
    """Test suite for ai.classify execution."""

    @pytest.mark.asyncio
    async def test_classify(self, ai_worker):
        """Test basic text classification."""
        result = await ai_worker.execute(
            node_type="ai.classify",
            inputs={
                "text": "This is a great product! I love it!",
                "categories": ["positive", "negative", "neutral"],
            },
            config={},
            context=None,
        )

        assert "category" in result
        assert "confidence" in result

        # Verify category is a string
        assert isinstance(result["category"], str)
        assert len(result["category"]) > 0

        # Verify confidence is a number
        assert isinstance(result["confidence"], (int, float))
        assert 0.0 <= result["confidence"] <= 1.0

    @pytest.mark.asyncio
    async def test_classify_with_config(self, ai_worker):
        """Test classification with custom config parameters."""
        result = await ai_worker.execute(
            node_type="ai.classify",
            inputs={
                "text": "The weather is okay.",
                "categories": ["good", "bad", "average"],
            },
            config={
                "model": "custom-model",
                "max_tokens": 10,
            },
            context=None,
        )

        assert "category" in result
        assert "confidence" in result
        assert isinstance(result["category"], str)

    @pytest.mark.asyncio
    async def test_classify_binary(self, ai_worker):
        """Test binary classification."""
        result = await ai_worker.execute(
            node_type="ai.classify",
            inputs={
                "text": "The system failed to start.",
                "categories": ["success", "failure"],
            },
            config={},
            context=None,
        )

        assert "category" in result
        assert "confidence" in result
        assert isinstance(result["category"], str)


class TestSummarize:
    """Test suite for ai.summarize execution."""

    @pytest.mark.asyncio
    async def test_summarize(self, ai_worker):
        """Test basic text summarization."""
        long_text = (
            "The quick brown fox jumps over the lazy dog. "
            "This is a common pangram used for testing. "
            "It contains all letters of the alphabet. "
            "Many typographers and designers use this phrase. "
            "It has been around for over a century."
        )

        result = await ai_worker.execute(
            node_type="ai.summarize",
            inputs={
                "text": long_text,
            },
            config={},
            context=None,
        )

        assert "summary" in result
        assert isinstance(result["summary"], str)
        assert len(result["summary"]) > 0

    @pytest.mark.asyncio
    async def test_summarize_with_max_length(self, ai_worker):
        """Test summarization with custom max_length."""
        long_text = (
            "Artificial intelligence is transforming the world. "
            "Machine learning models are becoming more capable. "
            "Natural language processing enables better communication. "
            "Computer vision helps us understand images and videos."
        )

        result = await ai_worker.execute(
            node_type="ai.summarize",
            inputs={
                "text": long_text,
                "max_length": 50,
            },
            config={},
            context=None,
        )

        assert "summary" in result
        assert isinstance(result["summary"], str)
        assert len(result["summary"]) > 0

    @pytest.mark.asyncio
    async def test_summarize_with_config(self, ai_worker):
        """Test summarization with custom config parameters."""
        result = await ai_worker.execute(
            node_type="ai.summarize",
            inputs={
                "text": "This is a test text that needs to be summarized.",
                "max_length": 100,
            },
            config={
                "model": "custom-model",
                "temperature": 0.3,
                "max_tokens": 512,
            },
            context=None,
        )

        assert "summary" in result
        assert isinstance(result["summary"], str)
        assert len(result["summary"]) > 0


class TestAgentDispatch:
    """Test suite for ai.agent-dispatch execution."""

    @pytest.mark.asyncio
    async def test_agent_dispatch(self, ai_worker):
        """Test agent dispatch with registered agent."""
        # Create and register a test agent
        test_agent = Agent(
            name="test-agent",
            description="A test agent for validation",
            system_prompt="You are a helpful test assistant.",
            strategy=Strategy.BEST,
        )
        ai_worker.registry.register(test_agent)

        # Execute agent dispatch
        result = await ai_worker.execute(
            node_type="ai.agent-dispatch",
            inputs={
                "agent_name": "test-agent",
                "message": "Hello, agent!",
            },
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
    async def test_agent_dispatch_with_context(self, ai_worker):
        """Test agent dispatch with conversation context."""
        # Create and register a test agent
        test_agent = Agent(
            name="context-agent",
            description="An agent that handles context",
            system_prompt="You are a context-aware assistant.",
            strategy=Strategy.BEST,
        )
        ai_worker.registry.register(test_agent)

        # Execute agent dispatch with context
        result = await ai_worker.execute(
            node_type="ai.agent-dispatch",
            inputs={
                "agent_name": "context-agent",
                "message": "Continue the conversation",
                "context": [
                    {"role": "user", "content": "Hello"},
                    {"role": "assistant", "content": "Hi there!"},
                ],
            },
            config={},
            context=None,
        )

        assert "response" in result
        response = result["response"]
        assert isinstance(response, LLMResponse)

    @pytest.mark.asyncio
    async def test_agent_dispatch_unknown_agent(self, ai_worker):
        """Test agent dispatch with unknown agent name."""
        # Attempt to dispatch to non-existent agent
        # This should raise a KeyError from the registry
        with pytest.raises(KeyError):
            await ai_worker.execute(
                node_type="ai.agent-dispatch",
                inputs={
                    "agent_name": "non-existent-agent",
                    "message": "Hello",
                },
                config={},
                context=None,
            )


class TestOrchestrate:
    """Test suite for ai.orchestrate execution."""

    @pytest.mark.asyncio
    async def test_orchestrate_sequential(self, mock_router, mock_registry):
        """Test sequential orchestration of multiple agents."""
        # Mock ClusterManager to avoid FastAPI dependency issues
        import sys
        from unittest.mock import MagicMock

        mock_cluster = MagicMock()
        mock_cluster.ClusterManager = MagicMock
        sys.modules["mascarade.cluster"] = mock_cluster

        from mascarade.orchestrator.engine import Orchestrator

        # Create and register test agents
        agent1 = Agent(
            name="agent-1",
            description="First agent",
            system_prompt="You are agent 1.",
            strategy=Strategy.BEST,
        )
        agent2 = Agent(
            name="agent-2",
            description="Second agent",
            system_prompt="You are agent 2.",
            strategy=Strategy.BEST,
        )
        mock_registry.register(agent1)
        mock_registry.register(agent2)

        # Create orchestrator and AI worker
        orchestrator = Orchestrator(router=mock_router, registry=mock_registry)
        ai_worker = AIWorker(
            router=mock_router, registry=mock_registry, orchestrator=orchestrator
        )

        # Execute sequential orchestration
        result = await ai_worker.execute(
            node_type="ai.orchestrate",
            inputs={
                "agent_names": ["agent-1", "agent-2"],
                "prompt": "Test prompt",
                "mode": "sequential",
            },
            config={},
            context=None,
        )

        # Verify result structure
        assert "run_id" in result
        assert "mode" in result
        assert "results" in result
        assert "errors" in result

        # Verify mode
        assert result["mode"] == "sequential"

        # Verify results
        results = result["results"]
        assert isinstance(results, list)
        assert len(results) == 2

        # Verify each result
        for i, task_result in enumerate(results):
            assert task_result["agent_name"] == f"agent-{i + 1}"
            assert "response" in task_result
            assert task_result["response"]["content"] == "Test response"
            assert task_result["step"] == i

        # Verify no errors
        assert result["errors"] == []

    @pytest.mark.asyncio
    async def test_orchestrate_parallel(self, mock_router, mock_registry):
        """Test parallel orchestration of multiple agents."""
        # Mock ClusterManager to avoid FastAPI dependency issues
        import sys
        from unittest.mock import MagicMock

        mock_cluster = MagicMock()
        mock_cluster.ClusterManager = MagicMock
        sys.modules["mascarade.cluster"] = mock_cluster

        from mascarade.orchestrator.engine import Orchestrator

        # Create and register test agents
        agent1 = Agent(
            name="parallel-agent-1",
            description="First parallel agent",
            system_prompt="You are agent 1.",
            strategy=Strategy.BEST,
        )
        agent2 = Agent(
            name="parallel-agent-2",
            description="Second parallel agent",
            system_prompt="You are agent 2.",
            strategy=Strategy.BEST,
        )
        mock_registry.register(agent1)
        mock_registry.register(agent2)

        # Create orchestrator and AI worker
        orchestrator = Orchestrator(router=mock_router, registry=mock_registry)
        ai_worker = AIWorker(
            router=mock_router, registry=mock_registry, orchestrator=orchestrator
        )

        # Execute parallel orchestration
        result = await ai_worker.execute(
            node_type="ai.orchestrate",
            inputs={
                "agent_names": ["parallel-agent-1", "parallel-agent-2"],
                "prompt": "Test prompt",
                "mode": "parallel",
            },
            config={},
            context=None,
        )

        # Verify result structure
        assert "run_id" in result
        assert "mode" in result
        assert "results" in result
        assert "errors" in result

        # Verify mode
        assert result["mode"] == "parallel"

        # Verify results
        results = result["results"]
        assert isinstance(results, list)
        assert len(results) == 2

        # Verify no errors
        assert result["errors"] == []

    @pytest.mark.asyncio
    async def test_orchestrate_pipeline(self, mock_router, mock_registry):
        """Test pipeline orchestration where output feeds into next agent."""
        # Mock ClusterManager to avoid FastAPI dependency issues
        import sys
        from unittest.mock import MagicMock

        mock_cluster = MagicMock()
        mock_cluster.ClusterManager = MagicMock
        sys.modules["mascarade.cluster"] = mock_cluster

        from mascarade.orchestrator.engine import Orchestrator

        # Create and register test agents
        agent1 = Agent(
            name="pipeline-agent-1",
            description="First pipeline agent",
            system_prompt="You are agent 1.",
            strategy=Strategy.BEST,
        )
        agent2 = Agent(
            name="pipeline-agent-2",
            description="Second pipeline agent",
            system_prompt="You are agent 2.",
            strategy=Strategy.BEST,
        )
        mock_registry.register(agent1)
        mock_registry.register(agent2)

        # Create orchestrator and AI worker
        orchestrator = Orchestrator(router=mock_router, registry=mock_registry)
        ai_worker = AIWorker(
            router=mock_router, registry=mock_registry, orchestrator=orchestrator
        )

        # Execute pipeline orchestration
        result = await ai_worker.execute(
            node_type="ai.orchestrate",
            inputs={
                "agent_names": ["pipeline-agent-1", "pipeline-agent-2"],
                "prompt": "Initial prompt",
                "mode": "pipeline",
            },
            config={},
            context=None,
        )

        # Verify result structure
        assert "run_id" in result
        assert "mode" in result
        assert "results" in result
        assert "errors" in result

        # Verify mode
        assert result["mode"] == "pipeline"

        # Verify results
        results = result["results"]
        assert isinstance(results, list)
        assert len(results) == 2

        # Verify no errors
        assert result["errors"] == []

    @pytest.mark.asyncio
    async def test_orchestrate_default_mode(self, mock_router, mock_registry):
        """Test orchestration with default mode (sequential)."""
        # Mock ClusterManager to avoid FastAPI dependency issues
        import sys
        from unittest.mock import MagicMock

        mock_cluster = MagicMock()
        mock_cluster.ClusterManager = MagicMock
        sys.modules["mascarade.cluster"] = mock_cluster

        from mascarade.orchestrator.engine import Orchestrator

        # Create and register test agents
        agent1 = Agent(
            name="default-agent-1",
            description="First agent",
            system_prompt="You are agent 1.",
            strategy=Strategy.BEST,
        )
        mock_registry.register(agent1)

        # Create orchestrator and AI worker
        orchestrator = Orchestrator(router=mock_router, registry=mock_registry)
        ai_worker = AIWorker(
            router=mock_router, registry=mock_registry, orchestrator=orchestrator
        )

        # Execute orchestration without specifying mode
        result = await ai_worker.execute(
            node_type="ai.orchestrate",
            inputs={
                "agent_names": ["default-agent-1"],
                "prompt": "Test prompt",
            },
            config={},
            context=None,
        )

        # Verify mode defaults to sequential
        assert result["mode"] == "sequential"

    @pytest.mark.asyncio
    async def test_orchestrate_without_orchestrator(self, ai_worker):
        """Test that orchestration fails when orchestrator is not available."""
        # ai_worker fixture doesn't have an orchestrator
        with pytest.raises(RuntimeError, match="Orchestrator not available"):
            await ai_worker.execute(
                node_type="ai.orchestrate",
                inputs={
                    "agent_names": ["agent-1"],
                    "prompt": "Test prompt",
                },
                config={},
                context=None,
            )


@pytest.mark.asyncio
async def test_orchestrate(mock_router, mock_registry, monkeypatch):
    """Main test for orchestration functionality (required by verification)."""
    # Mock ClusterManager to avoid FastAPI dependency issues
    import sys
    from unittest.mock import MagicMock

    # Create mock module for cluster
    mock_cluster = MagicMock()
    mock_cluster.ClusterManager = MagicMock
    sys.modules["mascarade.cluster"] = mock_cluster

    from mascarade.orchestrator.engine import Orchestrator

    # Create and register test agents
    agent1 = Agent(
        name="test-agent-1",
        description="First test agent",
        system_prompt="You are a helpful assistant.",
        strategy=Strategy.BEST,
    )
    agent2 = Agent(
        name="test-agent-2",
        description="Second test agent",
        system_prompt="You are another helpful assistant.",
        strategy=Strategy.BEST,
    )
    mock_registry.register(agent1)
    mock_registry.register(agent2)

    # Create orchestrator and AI worker
    orchestrator = Orchestrator(router=mock_router, registry=mock_registry)
    ai_worker = AIWorker(
        router=mock_router, registry=mock_registry, orchestrator=orchestrator
    )

    # Test sequential mode
    result = await ai_worker.execute(
        node_type="ai.orchestrate",
        inputs={
            "agent_names": ["test-agent-1", "test-agent-2"],
            "prompt": "Hello, world!",
            "mode": "sequential",
        },
        config={},
        context=None,
    )

    assert "run_id" in result
    assert "mode" in result
    assert result["mode"] == "sequential"
    assert "results" in result
    assert len(result["results"]) == 2
    assert result["errors"] == []


@pytest.mark.asyncio
async def test_router_select(mock_router, mock_registry):
    """Main test for router-select functionality (required by verification)."""
    from mascarade.router.providers.base import LLMProvider

    # Create a mock provider
    class MockProvider(LLMProvider):
        name = "test-provider"
        cost_per_million = (1.0, 2.0)
        speed_rank = 5
        quality_rank = 8
        is_configured = True

        def available_models(self):
            return ["test-model-1", "test-model-2"]

        async def send(self, *args, **kwargs):
            pass

        def stream(self, *args, **kwargs):
            pass

    # Create AI worker
    ai_worker = AIWorker(router=mock_router, registry=mock_registry)

    # Mock the router's _select_provider method
    mock_provider = MockProvider()
    mock_router._select_provider = (
        lambda strategy, provider_name=None, domain=None: mock_provider
    )

    # Test basic provider selection
    result = await ai_worker.execute(
        node_type="ai.router-select",
        inputs={"strategy": "best"},
        config={},
        context=None,
    )

    # Verify result structure and content
    assert "provider" in result
    assert "model" in result
    assert result["provider"] == "test-provider"
    assert result["model"] == "test-model-1"

    # Test validation
    errors = await ai_worker.validate(
        node_type="ai.router-select",
        inputs={"strategy": "best"},
        config={},
    )
    assert len(errors) == 0

    # Test validation failure
    errors = await ai_worker.validate(
        node_type="ai.router-select",
        inputs={},
        config={},
    )
    assert len(errors) > 0


class TestRouterSelect:
    """Test suite for ai.router-select execution."""

    @pytest.mark.asyncio
    async def test_router_select(self, ai_worker, monkeypatch):
        """Test basic router provider selection."""
        from mascarade.router.providers.base import LLMProvider

        # Create a mock provider
        class MockProvider(LLMProvider):
            name = "mock-provider"
            cost_per_million = (1.0, 2.0)
            speed_rank = 5
            quality_rank = 8
            is_configured = True

            def available_models(self):
                return ["mock-model-1", "mock-model-2"]

            async def send(self, *args, **kwargs):
                pass

            def stream(self, *args, **kwargs):
                pass

        # Mock the router's _select_provider method
        mock_provider = MockProvider()
        monkeypatch.setattr(
            ai_worker.router,
            "_select_provider",
            lambda strategy, provider_name=None, domain=None: mock_provider,
        )

        # Execute router-select node
        result = await ai_worker.execute(
            node_type="ai.router-select",
            inputs={"strategy": "best"},
            config={},
            context=None,
        )

        # Verify result structure
        assert "provider" in result
        assert "model" in result

        # Verify selected provider and model
        assert result["provider"] == "mock-provider"
        assert result["model"] == "mock-model-1"

    @pytest.mark.asyncio
    async def test_router_select_specific_strategy(self, ai_worker, monkeypatch):
        """Test router selection with specific provider strategy."""
        from mascarade.router.providers.base import LLMProvider

        # Create a mock provider
        class MockProvider(LLMProvider):
            name = "specific-provider"
            cost_per_million = (1.0, 2.0)
            speed_rank = 5
            quality_rank = 8
            is_configured = True

            def available_models(self):
                return ["specific-model"]

            async def send(self, *args, **kwargs):
                pass

            def stream(self, *args, **kwargs):
                pass

        # Mock the router's _select_provider method
        mock_provider = MockProvider()
        monkeypatch.setattr(
            ai_worker.router,
            "_select_provider",
            lambda strategy, provider_name=None, domain=None: mock_provider,
        )

        # Execute router-select with specific strategy
        result = await ai_worker.execute(
            node_type="ai.router-select",
            inputs={
                "strategy": "specific",
                "provider_name": "specific-provider",
            },
            config={},
            context=None,
        )

        # Verify result
        assert result["provider"] == "specific-provider"
        assert result["model"] == "specific-model"

    @pytest.mark.asyncio
    async def test_router_select_validation(self, ai_worker):
        """Test validation for router-select node."""
        # Test missing strategy
        errors = await ai_worker.validate(
            node_type="ai.router-select",
            inputs={},
            config={},
        )
        assert len(errors) > 0
        assert any("strategy" in err.lower() for err in errors)

        # Test invalid strategy
        errors = await ai_worker.validate(
            node_type="ai.router-select",
            inputs={"strategy": "invalid-strategy"},
            config={},
        )
        assert len(errors) > 0
        assert any("strategy" in err.lower() for err in errors)

        # Test valid strategy
        errors = await ai_worker.validate(
            node_type="ai.router-select",
            inputs={"strategy": "best"},
            config={},
        )
        assert len(errors) == 0

        # Test specific strategy without provider_name
        errors = await ai_worker.validate(
            node_type="ai.router-select",
            inputs={"strategy": "specific"},
            config={},
        )
        assert len(errors) > 0
        assert any("provider_name" in err.lower() for err in errors)

    @pytest.mark.asyncio
    async def test_router_select_with_domain(self, ai_worker, monkeypatch):
        """Test router selection with domain hint."""
        from mascarade.router.providers.base import LLMProvider

        # Create a mock provider
        class MockProvider(LLMProvider):
            name = "domain-provider"
            cost_per_million = (1.0, 2.0)
            speed_rank = 5
            quality_rank = 8
            is_configured = True

            def available_models(self):
                return ["domain-model"]

            async def send(self, *args, **kwargs):
                pass

            def stream(self, *args, **kwargs):
                pass

        # Mock the router's _select_provider method
        mock_provider = MockProvider()
        monkeypatch.setattr(
            ai_worker.router,
            "_select_provider",
            lambda strategy, provider_name=None, domain=None: mock_provider,
        )

        # Execute router-select with domain
        result = await ai_worker.execute(
            node_type="ai.router-select",
            inputs={
                "strategy": "best",
                "domain": "code",
            },
            config={},
            context=None,
        )

        # Verify result
        assert result["provider"] == "domain-provider"
        assert result["model"] == "domain-model"
