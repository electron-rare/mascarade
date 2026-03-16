"""End-to-end test for simple inference graph execution.

Tests a complete workflow from graph construction through execution,
validating that the Universal Node Engine correctly orchestrates
AI Worker nodes in a simple inference scenario.
"""

import asyncio

import pytest

from mascarade.agents.registry import AgentRegistry
from mascarade.node_engine.graph import Edge, Graph, Node
from mascarade.node_engine.runtime import ExecutionStatus, GraphRuntime
from mascarade.node_engine.workers.ai.worker import AIWorker
from mascarade.router import Router
from mascarade.router.providers.base import LLMProvider, LLMResponse


class MockProvider(LLMProvider):
    """Mock LLM provider for end-to-end testing."""

    def __init__(self, name: str = "mock", model: str = "mock-model"):
        self.name = name
        self.default_model = model
        self.cost_per_million = (1.0, 2.0)
        self.speed_rank = 1
        self.quality_rank = 3

    async def send(self, messages, **kwargs):
        """Mock send that echoes the last user message."""
        # Extract the last user message
        user_messages = [m for m in messages if m.get("role") == "user"]
        content = user_messages[-1]["content"] if user_messages else "no input"

        return LLMResponse(
            content=f"Response to: {content}",
            model=self.default_model,
            provider=self.name,
            usage={"input_tokens": 10, "output_tokens": 20, "total_tokens": 30},
        )

    async def stream(self, messages, **kwargs):
        """Mock stream implementation."""
        for token in ["Mock", " streaming", " response"]:
            yield token

    def available_models(self):
        """Return available models."""
        return [self.default_model]


@pytest.fixture
def runtime():
    """Create a GraphRuntime with AI Worker registered."""
    # Create runtime
    rt = GraphRuntime()

    # Create router with mock provider
    router = Router()
    router._providers.clear()
    router.register(MockProvider())

    # Create registry
    registry = AgentRegistry()

    # Create and register AI worker
    ai_worker = AIWorker(router=router, registry=registry)
    rt.register_worker(ai_worker)

    return rt


def test_e2e_single_inference_node(runtime):
    """Test end-to-end execution of a single LLM inference node."""
    # Create a simple graph with one inference node
    graph = Graph(
        nodes=[
            Node(
                id="llm1",
                type="ai.llm-inference",
                inputs={"prompt": "What is 2+2?"},
                config={"strategy": "best", "temperature": 0.7},
            ),
        ],
        metadata={"id": "simple-inference", "name": "Simple Inference Test"},
    )

    # Execute the graph
    context = asyncio.run(runtime.execute(graph))

    # Verify execution succeeded
    assert context.status == ExecutionStatus.COMPLETED
    assert len(context.node_results) == 1

    # Verify node execution
    result = context.node_results["llm1"]
    assert result.status == ExecutionStatus.COMPLETED
    assert result.worker_name == "ai-worker"

    # Verify output structure
    assert "response" in result.outputs
    response = result.outputs["response"]
    assert response.content == "Response to: What is 2+2?"
    assert response.model == "mock-model"
    assert response.provider == "mock"

    # Verify usage tracking
    assert response.usage["input_tokens"] == 10
    assert response.usage["output_tokens"] == 20
    assert response.usage["total_tokens"] == 30


def test_e2e_template_to_inference(runtime):
    """Test end-to-end execution of template -> inference pipeline."""
    # Create a graph with prompt template feeding into LLM inference
    graph = Graph(
        nodes=[
            Node(
                id="template1",
                type="ai.prompt-template",
                inputs={
                    "template": "Explain {{topic}} in simple terms",
                    "variables": {"topic": "quantum computing"},
                },
            ),
            Node(
                id="llm1",
                type="ai.llm-inference",
                inputs={"prompt": "placeholder"},  # Will be overridden by edge
                config={"strategy": "best"},
            ),
        ],
        edges=[
            Edge(
                from_node="template1",
                from_port="prompt",
                to_node="llm1",
                to_port="prompt",
            ),
        ],
        metadata={"id": "template-to-inference", "name": "Template Pipeline Test"},
    )

    # Execute the graph
    context = asyncio.run(runtime.execute(graph))

    # Verify execution succeeded
    assert context.status == ExecutionStatus.COMPLETED
    assert len(context.node_results) == 2

    # Verify template node
    template_result = context.node_results["template1"]
    assert template_result.status == ExecutionStatus.COMPLETED
    assert template_result.outputs["prompt"] == "Explain quantum computing in simple terms"

    # Verify inference node received templated prompt
    llm_result = context.node_results["llm1"]
    assert llm_result.status == ExecutionStatus.COMPLETED
    assert "Response to: Explain quantum computing in simple terms" in llm_result.outputs["response"].content


def test_e2e_multi_step_inference(runtime):
    """Test end-to-end execution of multi-step inference pipeline."""
    # Create a graph with template -> inference -> template -> inference
    # This tests data flowing through multiple steps
    graph = Graph(
        nodes=[
            Node(
                id="template1",
                type="ai.prompt-template",
                inputs={
                    "template": "Step 1: {{topic}}",
                    "variables": {"topic": "computer architecture"},
                },
            ),
            Node(
                id="step1",
                type="ai.llm-inference",
                inputs={"prompt": "placeholder"},  # Will be overridden by edge
                config={"strategy": "best"},
            ),
            Node(
                id="template2",
                type="ai.prompt-template",
                inputs={
                    "template": "Step 2: Follow up on {{topic}}",
                    "variables": {"topic": "previous discussion"},
                },
            ),
            Node(
                id="step2",
                type="ai.llm-inference",
                inputs={"prompt": "placeholder"},  # Will be overridden by edge
                config={"strategy": "best"},
            ),
        ],
        edges=[
            Edge(
                from_node="template1",
                from_port="prompt",
                to_node="step1",
                to_port="prompt",
            ),
            Edge(
                from_node="template2",
                from_port="prompt",
                to_node="step2",
                to_port="prompt",
            ),
        ],
        metadata={"id": "multi-step-inference", "name": "Multi-Step Inference Test"},
    )

    # Execute the graph
    context = asyncio.run(runtime.execute(graph))

    # Verify execution succeeded
    assert context.status == ExecutionStatus.COMPLETED
    assert len(context.node_results) == 4

    # Verify all nodes executed successfully
    for node_id in ["template1", "step1", "template2", "step2"]:
        assert context.node_results[node_id].status == ExecutionStatus.COMPLETED

    # Verify data flow through the pipeline
    step1_response = context.node_results["step1"].outputs["response"]
    assert "Response to: Step 1: computer architecture" in step1_response.content

    # Verify second inference step
    step2_response = context.node_results["step2"].outputs["response"]
    assert step2_response.provider == "mock"
    assert "Step 2:" in step2_response.content


def test_e2e_parallel_inference(runtime):
    """Test end-to-end execution of parallel inference nodes."""
    # Create a graph with multiple independent inference nodes
    graph = Graph(
        nodes=[
            Node(
                id="question1",
                type="ai.llm-inference",
                inputs={"prompt": "What is Python?"},
                config={"strategy": "best"},
            ),
            Node(
                id="question2",
                type="ai.llm-inference",
                inputs={"prompt": "What is JavaScript?"},
                config={"strategy": "best"},
            ),
            Node(
                id="question3",
                type="ai.llm-inference",
                inputs={"prompt": "What is Rust?"},
                config={"strategy": "best"},
            ),
        ],
        # No edges - all nodes are independent
        metadata={"id": "parallel-inference", "name": "Parallel Inference Test"},
    )

    # Execute the graph
    context = asyncio.run(runtime.execute(graph))

    # Verify execution succeeded
    assert context.status == ExecutionStatus.COMPLETED
    assert len(context.node_results) == 3

    # Verify all nodes executed successfully
    for node_id in ["question1", "question2", "question3"]:
        result = context.node_results[node_id]
        assert result.status == ExecutionStatus.COMPLETED
        assert "response" in result.outputs
        assert result.outputs["response"].provider == "mock"

    # Verify each got a unique response based on their prompt
    assert "Python" in context.node_results["question1"].outputs["response"].content
    assert "JavaScript" in context.node_results["question2"].outputs["response"].content
    assert "Rust" in context.node_results["question3"].outputs["response"].content


def test_e2e_batch_inference(runtime):
    """Test end-to-end execution of batch inference node."""
    # Create a graph with a batch inference node
    graph = Graph(
        nodes=[
            Node(
                id="batch1",
                type="ai.batch-inference",
                inputs={
                    "prompts": [
                        "What is AI?",
                        "What is ML?",
                        "What is DL?",
                    ],
                },
                config={"strategy": "best"},
            ),
        ],
        metadata={"id": "batch-inference", "name": "Batch Inference Test"},
    )

    # Execute the graph
    context = asyncio.run(runtime.execute(graph))

    # Verify execution succeeded
    assert context.status == ExecutionStatus.COMPLETED
    assert len(context.node_results) == 1

    # Verify batch node execution
    result = context.node_results["batch1"]
    assert result.status == ExecutionStatus.COMPLETED

    # Verify all prompts were processed
    responses = result.outputs["responses"]
    assert len(responses) == 3

    # Verify each response
    assert "AI" in responses[0].content
    assert "ML" in responses[1].content
    assert "DL" in responses[2].content


def test_e2e_inference_with_system_message(runtime):
    """Test end-to-end execution with system message."""
    # Create a graph with system message
    graph = Graph(
        nodes=[
            Node(
                id="llm1",
                type="ai.llm-inference",
                inputs={
                    "prompt": "Hello!",
                    "system": "You are a helpful coding assistant.",
                },
                config={"strategy": "best"},
            ),
        ],
        metadata={"id": "system-message-inference", "name": "System Message Test"},
    )

    # Execute the graph
    context = asyncio.run(runtime.execute(graph))

    # Verify execution succeeded
    assert context.status == ExecutionStatus.COMPLETED
    result = context.node_results["llm1"]
    assert result.status == ExecutionStatus.COMPLETED
    assert "response" in result.outputs


def test_e2e_validation_failure(runtime):
    """Test that graph validation catches errors before execution."""
    # Create an invalid graph (missing required input)
    graph = Graph(
        nodes=[
            Node(
                id="llm1",
                type="ai.llm-inference",
                inputs={},  # Missing required 'prompt' input
                config={},
            ),
        ],
        metadata={"id": "invalid-graph", "name": "Invalid Graph Test"},
    )

    # Execution should fail validation
    with pytest.raises(ValueError, match="validation failed"):
        asyncio.run(runtime.execute(graph))


def test_e2e_graph_metadata(runtime):
    """Test that graph metadata is preserved through execution."""
    # Create a graph with rich metadata
    graph_metadata = {
        "id": "test-workflow-123",
        "name": "Test Workflow",
        "version": "1.0.0",
        "author": "test-suite",
        "description": "A test workflow for validation",
    }

    graph = Graph(
        nodes=[
            Node(
                id="llm1",
                type="ai.llm-inference",
                inputs={"prompt": "test"},
                config={},
            ),
        ],
        metadata=graph_metadata,
    )

    # Execute the graph with execution metadata
    execution_metadata = {"execution_time": "2026-03-16", "environment": "test"}
    context = asyncio.run(runtime.execute(graph, metadata=execution_metadata))

    # Verify graph ID is extracted from graph metadata
    assert context.graph_id == "test-workflow-123"
    # Verify execution metadata is stored in context
    assert context.metadata == execution_metadata


def test_e2e_execution_timing(runtime):
    """Test that execution timing is tracked."""
    # Create a simple graph
    graph = Graph(
        nodes=[
            Node(
                id="llm1",
                type="ai.llm-inference",
                inputs={"prompt": "test"},
                config={},
            ),
        ],
        metadata={"id": "timing-test"},
    )

    # Execute the graph
    context = asyncio.run(runtime.execute(graph))

    # Verify timing information is present
    result = context.node_results["llm1"]
    assert result.execution_time_ms is not None
    assert result.execution_time_ms > 0


def test_e2e_classify_node(runtime):
    """Test end-to-end execution of classify node."""
    # Create a graph with a classify node
    graph = Graph(
        nodes=[
            Node(
                id="classify1",
                type="ai.classify",
                inputs={
                    "text": "Python is a programming language",
                    "categories": ["technology", "science", "arts", "sports"],
                },
                config={},
            ),
        ],
        metadata={"id": "classify-test"},
    )

    # Execute the graph
    context = asyncio.run(runtime.execute(graph))

    # Verify execution succeeded
    assert context.status == ExecutionStatus.COMPLETED
    result = context.node_results["classify1"]
    assert result.status == ExecutionStatus.COMPLETED

    # Verify classification output
    assert "category" in result.outputs
    assert "confidence" in result.outputs


def test_e2e_summarize_node(runtime):
    """Test end-to-end execution of summarize node."""
    # Create a graph with a summarize node
    graph = Graph(
        nodes=[
            Node(
                id="summarize1",
                type="ai.summarize",
                inputs={
                    "text": "This is a long text that needs to be summarized. " * 10,
                    "max_length": 50,
                },
                config={},
            ),
        ],
        metadata={"id": "summarize-test"},
    )

    # Execute the graph
    context = asyncio.run(runtime.execute(graph))

    # Verify execution succeeded
    assert context.status == ExecutionStatus.COMPLETED
    result = context.node_results["summarize1"]
    assert result.status == ExecutionStatus.COMPLETED

    # Verify summary output
    assert "summary" in result.outputs
    assert isinstance(result.outputs["summary"], str)


def test_chain_of_thought_graph(runtime):
    """Test end-to-end execution of chain-of-thought reasoning node."""
    # Create a graph with a chain-of-thought node
    graph = Graph(
        nodes=[
            Node(
                id="cot1",
                type="ai.chain-of-thought",
                inputs={
                    "question": "How does photosynthesis work?",
                    "steps": 3,
                },
                config={"strategy": "best"},
            ),
        ],
        metadata={"id": "chain-of-thought-test", "name": "Chain of Thought Test"},
    )

    # Execute the graph
    context = asyncio.run(runtime.execute(graph))

    # Verify execution succeeded
    assert context.status == ExecutionStatus.COMPLETED
    assert len(context.node_results) == 1

    # Verify chain-of-thought node execution
    result = context.node_results["cot1"]
    assert result.status == ExecutionStatus.COMPLETED
    assert result.worker_name == "ai-worker"

    # Verify output structure
    assert "reasoning" in result.outputs
    assert "answer" in result.outputs
    assert "usage" in result.outputs

    # Verify reasoning steps
    reasoning = result.outputs["reasoning"]
    assert isinstance(reasoning, list)
    assert len(reasoning) == 3  # Should have 3 reasoning steps

    # Verify each reasoning step has content
    for i, step in enumerate(reasoning):
        assert isinstance(step, str)
        assert len(step) > 0
        # Mock provider should echo back the step number
        assert f"Step {i + 1}/3" in step

    # Verify final answer
    answer = result.outputs["answer"]
    assert isinstance(answer, str)
    assert len(answer) > 0
    # Final synthesis should reference the question
    assert "photosynthesis" in answer.lower()

    # Verify usage tracking
    assert isinstance(result.outputs["usage"], dict)


def test_agent_orchestration(runtime):
    """Test end-to-end agent dispatch and orchestration."""
    from mascarade.agents.base import Agent
    from mascarade.router.router import Strategy

    # Create and register a mock agent
    mock_agent = Agent(
        name="test-assistant",
        description="A test assistant agent",
        system_prompt="You are a helpful test assistant.",
        strategy=Strategy.BEST,
        temperature=0.5,
    )
    # Access the AI worker from the runtime and register the agent
    ai_worker = runtime.workers["ai"]
    ai_worker.registry.register(mock_agent)

    # Create a graph with agent-dispatch node
    graph = Graph(
        nodes=[
            Node(
                id="agent1",
                type="ai.agent-dispatch",
                inputs={
                    "agent_name": "test-assistant",
                    "message": "Hello, how are you?",
                },
                config={},
            ),
        ],
        metadata={"id": "agent-dispatch-test", "name": "Agent Dispatch Test"},
    )

    # Execute the graph
    context = asyncio.run(runtime.execute(graph))

    # Verify execution succeeded
    assert context.status == ExecutionStatus.COMPLETED
    assert len(context.node_results) == 1

    # Verify agent dispatch node execution
    result = context.node_results["agent1"]
    assert result.status == ExecutionStatus.COMPLETED
    assert result.worker_name == "ai-worker"

    # Verify output structure
    assert "response" in result.outputs
    response = result.outputs["response"]

    # Verify agent response - the mock provider will echo the message
    assert response.content == "Response to: Hello, how are you?"
    assert response.model == "mock-model"
    assert response.provider == "mock"

    # Verify usage tracking
    assert response.usage["input_tokens"] == 10
    assert response.usage["output_tokens"] == 20
    assert response.usage["total_tokens"] == 30
