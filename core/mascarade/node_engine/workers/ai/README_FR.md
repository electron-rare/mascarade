# AI Worker

LLM inference, agent dispatch, and orchestration nodes for the Universal Node Engine.

## Table of Contents

1. [Overview](#overview)
2. [Quick Start](#quick-start)
3. [Node Types Reference](#node-types-reference)
4. [Domain Types](#domain-types)
5. [Integration](#integration)
6. [Usage Examples](#usage-examples)
7. [Configuration](#configuration)

---

## Overview

The AI Worker is the first domain worker for the Universal Node Engine, providing graph-executable nodes for LLM operations. It wraps Mascarade's existing, production-proven infrastructure:

- **Router** — Multi-provider LLM dispatch with circuit breakers and retry logic
- **AgentRegistry** — Agent discovery and management
- **Orchestrator** — Multi-agent sequential/parallel/pipeline execution

### Key Features

- **13 Node Types** — From simple LLM inference to complex multi-agent orchestration
- **Provider Agnostic** — Works with any provider registered in the Router (OpenAI, Anthropic, Mistral, etc.)
- **Strategy-Based Routing** — Select providers by cost, speed, quality, or specific model
- **Built-in Resilience** — Inherits Router's circuit breakers, retry logic, and dead letter queue
- **Agent Integration** — Dispatch to registered agents from within graphs
- **Orchestration Patterns** — Sequential, parallel, and pipeline execution modes

### Node Categories

| Category | Node Types | Description |
|----------|-----------|-------------|
| **Inference** | `llm-inference`, `llm-stream`, `batch-inference` | Direct LLM calls via Router |
| **Embedding** | `embedding` | Text embedding generation |
| **Reasoning** | `chain-of-thought`, `classify`, `summarize` | Multi-step reasoning and classification |
| **Template** | `prompt-template` | Dynamic prompt construction |
| **Router** | `router-select` | Provider and model selection |
| **Orchestrator** | `agent-dispatch`, `orchestrate-sequential`, `orchestrate-parallel`, `orchestrate-pipeline` | Agent execution and workflows |

---

## Quick Start

### 1. Register the AI Worker

```python
from mascarade.node_engine.runtime import GraphRuntime
from mascarade.node_engine.workers.ai.register import register_ai_worker

# Initialize runtime
runtime = GraphRuntime()

# Register AI worker (creates default Router and AgentRegistry)
ai_worker = register_ai_worker(runtime)
```

### 2. Execute a Single Node

```python
# Simple LLM inference
outputs = await runtime.execute_node(
    node_type="ai.llm-inference",
    inputs={"prompt": "Explain quantum computing in one sentence."},
    config={"temperature": 0.7, "strategy": "best"},
)

print(outputs["response"].content)
```

### 3. Build a Graph

```python
from mascarade.node_engine.graph import Graph, Node, Edge

graph = Graph(
    nodes=[
        Node(
            id="template",
            type="ai.prompt-template",
            inputs={
                "template": "Translate '{{text}}' to {{language}}",
                "variables": {"text": "Hello", "language": "French"},
            },
        ),
        Node(
            id="llm",
            type="ai.llm-inference",
            config={"temperature": 0.3},
        ),
    ],
    edges=[
        Edge(from_node="template", from_port="prompt", to_node="llm", to_port="prompt"),
    ],
)

context = await runtime.execute(graph)
print(context.node_results["llm"].outputs["response"].content)
```

---

## Node Types Reference

### Inference Nodes

#### `ai.llm-inference`

Send a prompt to an LLM via the Router and receive a complete response.

**Inputs:**

| Port | Type | Required | Description |
|------|------|----------|-------------|
| `prompt` | `string` | Yes | The user prompt to send |
| `system` | `string` | No | System message for context |
| `context` | `array<ChatMessage>` | No | Conversation history |

**Outputs:**

| Port | Type | Description |
|------|------|-------------|
| `response` | `LLMResponse` | Complete LLM response with metadata |
| `usage` | `TokenUsage` | Token consumption metrics |

**Configuration:**

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `model` | `string` | Provider default | Specific model to use |
| `temperature` | `number` | `0.7` | Generation temperature (0.0–1.0) |
| `max_tokens` | `integer` | `4096` | Maximum tokens to generate |
| `strategy` | `string` | `"best"` | Router strategy: `cheapest`, `fastest`, `best`, `specific` |

**Example:**

```python
Node(
    id="llm1",
    type="ai.llm-inference",
    inputs={"prompt": "What is the capital of France?"},
    config={"temperature": 0.3, "strategy": "cheapest"},
)
```

---

#### `ai.llm-stream`

Stream LLM response token by token for real-time output.

**Inputs:** Same as `ai.llm-inference`

**Outputs:**

| Port | Type | Description |
|------|------|-------------|
| `stream` | `stream<string>` | Token-by-token response stream |
| `usage` | `TokenUsage` | Token consumption (available after stream completes) |

**Configuration:** Same as `ai.llm-inference`

**Example:**

```python
Node(
    id="stream1",
    type="ai.llm-stream",
    inputs={"prompt": "Write a short story about a robot."},
    config={"temperature": 0.9},
)
```

---

#### `ai.batch-inference`

Process multiple prompts in parallel via the Router.

**Inputs:**

| Port | Type | Required | Description |
|------|------|----------|-------------|
| `prompts` | `array<string>` | Yes | List of prompts to process |

**Outputs:**

| Port | Type | Description |
|------|------|-------------|
| `responses` | `array<LLMResponse>` | Responses in same order as inputs |
| `usage` | `TokenUsage` | Aggregate token consumption |

**Configuration:** Same as `ai.llm-inference` (applied to all prompts)

**Example:**

```python
Node(
    id="batch1",
    type="ai.batch-inference",
    inputs={
        "prompts": [
            "What is 2+2?",
            "What is the speed of light?",
            "What is the meaning of life?",
        ],
    },
    config={"temperature": 0.1},
)
```

---

### Embedding Nodes

#### `ai.embedding`

Generate embeddings for text input via the provider system.

**Inputs:**

| Port | Type | Required | Description |
|------|------|----------|-------------|
| `text` | `string` | Yes | Text to embed |

**Outputs:**

| Port | Type | Description |
|------|------|-------------|
| `vector` | `EmbeddingVector` | Dense vector embedding |

**Configuration:**

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `model` | `string` | Provider default | Embedding model to use |
| `provider` | `string` | Auto-select | Specific provider for embeddings |

**Note:** Embedding support is currently pending provider implementation.

---

### Reasoning Nodes

#### `ai.chain-of-thought`

Multi-step reasoning with intermediate outputs. Each step feeds its output as context to the next step.

**Inputs:**

| Port | Type | Required | Description |
|------|------|----------|-------------|
| `question` | `string` | Yes | The question to reason about |
| `steps` | `integer` | No | Number of reasoning steps (default: 3) |

**Outputs:**

| Port | Type | Description |
|------|------|-------------|
| `reasoning` | `array<string>` | Intermediate reasoning steps |
| `answer` | `string` | Final synthesized answer |
| `usage` | `TokenUsage` | Aggregate token consumption across all steps |

**Configuration:** Same as `ai.llm-inference`

**Example:**

```python
Node(
    id="cot1",
    type="ai.chain-of-thought",
    inputs={
        "question": "If a train travels 120 miles in 2 hours, how far will it travel in 5 hours?",
        "steps": 3,
    },
    config={"temperature": 0.5},
)
```

---

#### `ai.classify`

Classify text into predefined categories.

**Inputs:**

| Port | Type | Required | Description |
|------|------|----------|-------------|
| `text` | `string` | Yes | Text to classify |
| `categories` | `array<string>` | Yes | Available categories |

**Outputs:**

| Port | Type | Description |
|------|------|-------------|
| `category` | `string` | Selected category |
| `confidence` | `number` | Classification confidence (0.0–1.0) |

**Configuration:** Same as `ai.llm-inference` (temperature defaults to 0.1 for deterministic results)

**Example:**

```python
Node(
    id="classify1",
    type="ai.classify",
    inputs={
        "text": "I love this product! It's amazing!",
        "categories": ["positive", "negative", "neutral"],
    },
)
```

---

#### `ai.summarize`

Summarize text using an LLM.

**Inputs:**

| Port | Type | Required | Description |
|------|------|----------|-------------|
| `text` | `string` | Yes | Text to summarize |
| `max_length` | `integer` | No | Target summary length in words (default: 200) |

**Outputs:**

| Port | Type | Description |
|------|------|-------------|
| `summary` | `string` | Summarized text |

**Configuration:** Same as `ai.llm-inference`

**Example:**

```python
Node(
    id="summarize1",
    type="ai.summarize",
    inputs={
        "text": "Long article text...",
        "max_length": 100,
    },
    config={"temperature": 0.5},
)
```

---

### Template Nodes

#### `ai.prompt-template`

Apply variable substitution to a prompt template.

**Inputs:**

| Port | Type | Required | Description |
|------|------|----------|-------------|
| `template` | `string` | Yes | Template string with `{{variable}}` placeholders |
| `variables` | `map<string, string>` | Yes | Variable name-value mappings |

**Outputs:**

| Port | Type | Description |
|------|------|-------------|
| `prompt` | `string` | Rendered prompt with variables substituted |

**Configuration:** None (pure function — no LLM call)

**Example:**

```python
Node(
    id="template1",
    type="ai.prompt-template",
    inputs={
        "template": "Hello {{name}}, welcome to {{place}}!",
        "variables": {"name": "Alice", "place": "Wonderland"},
    },
)
# Output: "Hello Alice, welcome to Wonderland!"
```

---

### Router Nodes

#### `ai.router-select`

Select a provider and model based on routing strategy, without executing an inference call.

**Inputs:**

| Port | Type | Required | Description |
|------|------|----------|-------------|
| `strategy` | `string` | Yes | Routing strategy: `cheapest`, `fastest`, `best`, `specific` |
| `constraints` | `json` | No | Additional constraints (e.g., max cost, required capabilities) |

**Outputs:**

| Port | Type | Description |
|------|------|-------------|
| `provider` | `string` | Selected provider name |
| `model` | `string` | Selected model identifier |

**Configuration:** None

**Example:**

```python
Node(
    id="select1",
    type="ai.router-select",
    inputs={"strategy": "cheapest"},
)
```

---

### Orchestrator Nodes

#### `ai.agent-dispatch`

Run a registered agent from the AgentRegistry within a graph.

**Inputs:**

| Port | Type | Required | Description |
|------|------|----------|-------------|
| `agent_name` | `string` | Yes | Name of agent in the AgentRegistry |
| `message` | `string` | Yes | Message to send to the agent |
| `context` | `array<ChatMessage>` | No | Conversation history |

**Outputs:**

| Port | Type | Description |
|------|------|-------------|
| `response` | `LLMResponse` | Agent's response |

**Configuration:** None (agent's own configuration is used)

**Validation:** At graph validation time, verifies that `agent_name` exists in the registry.

**Example:**

```python
Node(
    id="agent1",
    type="ai.agent-dispatch",
    inputs={
        "agent_name": "coder-agent",
        "message": "Write a Python function to check if a number is prime.",
    },
)
```

---

#### `ai.orchestrate-sequential`

Execute multiple agents sequentially, piping each output to the next.

**Inputs:**

| Port | Type | Required | Description |
|------|------|----------|-------------|
| `agents` | `array<string>` | Yes | Ordered list of agent names |
| `initial_prompt` | `string` | Yes | Starting prompt for the first agent |

**Outputs:**

| Port | Type | Description |
|------|------|-------------|
| `results` | `array<LLMResponse>` | Response from each agent in order |
| `final` | `LLMResponse` | Last agent's response |

**Configuration:** None

**Example:**

```python
Node(
    id="seq1",
    type="ai.orchestrate-sequential",
    inputs={
        "agents": ["researcher", "summarizer"],
        "initial_prompt": "Find the latest Python releases",
    },
)
```

---

#### `ai.orchestrate-parallel`

Execute multiple agents in parallel on the same input.

**Inputs:**

| Port | Type | Required | Description |
|------|------|----------|-------------|
| `agents` | `array<string>` | Yes | List of agent names to run concurrently |
| `prompt` | `string` | Yes | Prompt sent to all agents |

**Outputs:**

| Port | Type | Description |
|------|------|-------------|
| `results` | `array<LLMResponse>` | Responses from all agents |

**Configuration:** None

**Example:**

```python
Node(
    id="parallel1",
    type="ai.orchestrate-parallel",
    inputs={
        "agents": ["expert1", "expert2", "expert3"],
        "prompt": "What is the best approach to solve this problem?",
    },
)
```

---

#### `ai.orchestrate-pipeline`

Execute agents in a pipeline where each agent's output feeds into the next.

**Inputs:**

| Port | Type | Required | Description |
|------|------|----------|-------------|
| `agents` | `array<string>` | Yes | Ordered list of agent names |
| `initial_prompt` | `string` | Yes | Starting prompt |

**Outputs:**

| Port | Type | Description |
|------|------|-------------|
| `results` | `array<LLMResponse>` | All intermediate results |
| `final` | `LLMResponse` | Final pipeline output |

**Configuration:** None

**Example:**

```python
Node(
    id="pipeline1",
    type="ai.orchestrate-pipeline",
    inputs={
        "agents": ["analyzer", "enhancer", "validator"],
        "initial_prompt": "Design a user authentication system",
    },
)
```

---

## Domain Types

The AI Worker registers the following domain types with the Universal Node Engine:

### `LLMResponse`

Normalized LLM response with provider metadata.

**Fields:**
- `content: string` — Response text
- `model: string` — Model identifier
- `provider: string` — Provider name
- `usage: object` — Token usage statistics

### `TokenUsage`

Token consumption metrics for cost tracking and budgeting.

**Fields:**
- `prompt_tokens: integer` — Input tokens
- `completion_tokens: integer` — Output tokens
- `total_tokens: integer` — Total tokens
- `cost_usd: number` — Estimated cost in USD

### `EmbeddingVector`

Dense vector embedding produced by an embedding model.

**Fields:**
- `values: array<number>` — Vector values
- `model: string` — Model identifier
- `dimensions: integer` — Vector dimensions

### `ChatMessage`

A single message in a conversation.

**Fields:**
- `role: string` — Message role (`"system"`, `"user"`, or `"assistant"`)
- `content: string` — Message content
- `name: string | null` — Optional speaker name

### `PromptTemplate`

A template with variable placeholders for dynamic prompt construction.

**Fields:**
- `template: string` — Template string with `{{variable}}` placeholders
- `variables: array<string>` — Variable names expected in the template
- `defaults: object` — Default values for variables

---

## Integration

### Router Integration

The AI Worker delegates all LLM calls to the existing Router infrastructure.

**Strategy Mapping:**

| Node Config `strategy` | Router Strategy | Selection Criteria |
|------------------------|-----------------|-------------------|
| `"cheapest"` | `Strategy.CHEAPEST` | Lowest cost per million tokens |
| `"fastest"` | `Strategy.FASTEST` | Lowest speed rank |
| `"best"` | `Strategy.BEST` | Highest quality rank |
| `"specific"` | `Strategy.SPECIFIC` | Exact provider/model match |

**Resilience Features (inherited from Router):**
- Circuit breakers per provider (fail_max=5, timeout=60s)
- Exponential backoff retry (3 attempts)
- Dead letter queue for failed requests

### AgentRegistry Integration

The `ai.agent-dispatch` node bridges the Node Engine with the existing agent system.

**Agent Lookup:**
```python
agent = registry.get(agent_name)  # Resolved by name
response = await agent.run(message, router=router)
```

**Agent Configuration Passthrough:**
- Agent's own `strategy`, `preferred_provider`, `preferred_model`, `temperature`, `max_tokens`, and `system_prompt` are preserved
- Node configuration does not override agent settings

### Orchestrator Integration

Orchestration nodes map to the Orchestrator's execution modes.

**Execution Mode Mapping:**

| Node Type | Orchestrator Mode | Description |
|-----------|-------------------|-------------|
| `ai.orchestrate-sequential` | `ExecutionMode.SEQUENTIAL` | Agents run one after another |
| `ai.orchestrate-parallel` | `ExecutionMode.PARALLEL` | Agents run concurrently |
| `ai.orchestrate-pipeline` | `ExecutionMode.PIPELINE` | Output of each agent feeds into the next |

**Resilience Features (inherited from Orchestrator):**
- Per-agent circuit breakers
- Retry executor with configurable `RetryConfig`
- Dead letter store for failed agent executions
- Trace buffer for observability

---

## Usage Examples

### Example 1: Simple LLM Inference

```python
from mascarade.node_engine.runtime import GraphRuntime
from mascarade.node_engine.workers.ai.register import register_ai_worker

runtime = GraphRuntime()
ai_worker = register_ai_worker(runtime)

outputs = await runtime.execute_node(
    node_type="ai.llm-inference",
    inputs={"prompt": "What is the capital of France?"},
    config={"temperature": 0.3, "strategy": "cheapest"},
)

print(outputs["response"].content)
# Output: "The capital of France is Paris."
```

---

### Example 2: Template → LLM Pipeline

```python
from mascarade.node_engine.graph import Graph, Node, Edge

graph = Graph(
    nodes=[
        Node(
            id="template",
            type="ai.prompt-template",
            inputs={
                "template": "Explain {{concept}} in simple terms.",
                "variables": {"concept": "quantum entanglement"},
            },
        ),
        Node(
            id="llm",
            type="ai.llm-inference",
            config={"temperature": 0.7},
        ),
    ],
    edges=[
        Edge(from_node="template", from_port="prompt", to_node="llm", to_port="prompt"),
    ],
)

context = await runtime.execute(graph)
print(context.node_results["llm"].outputs["response"].content)
```

---

### Example 3: Chain-of-Thought Reasoning

```python
from mascarade.node_engine.graph import Graph, Node

graph = Graph(
    nodes=[
        Node(
            id="reasoning",
            type="ai.chain-of-thought",
            inputs={
                "question": "A farmer has 17 sheep, and all but 9 die. How many are left?",
                "steps": 3,
            },
            config={"temperature": 0.5},
        ),
    ],
)

context = await runtime.execute(graph)
result = context.node_results["reasoning"]

print("Reasoning steps:")
for i, step in enumerate(result.outputs["reasoning"], 1):
    print(f"Step {i}: {step}")

print(f"\nFinal answer: {result.outputs['answer']}")
```

---

### Example 4: Agent Dispatch

```python
from mascarade.node_engine.graph import Graph, Node

# Assuming an agent "coder-agent" is registered in AgentRegistry
graph = Graph(
    nodes=[
        Node(
            id="agent",
            type="ai.agent-dispatch",
            inputs={
                "agent_name": "coder-agent",
                "message": "Write a Python function to check if a number is prime.",
            },
        ),
    ],
)

context = await runtime.execute(graph)
print(context.node_results["agent"].outputs["response"].content)
```

---

### Example 5: Parallel Agent Execution

```python
from mascarade.node_engine.graph import Graph, Node

graph = Graph(
    nodes=[
        Node(
            id="parallel",
            type="ai.orchestrate-parallel",
            inputs={
                "agents": ["expert1", "expert2", "expert3"],
                "prompt": "What are the key principles of software architecture?",
            },
        ),
    ],
)

context = await runtime.execute(graph)
results = context.node_results["parallel"].outputs["results"]

for i, response in enumerate(results, 1):
    print(f"Expert {i}: {response.content}\n")
```

---

### Example 6: Classification Pipeline

```python
from mascarade.node_engine.graph import Graph, Node, Edge

graph = Graph(
    nodes=[
        Node(
            id="input",
            type="ai.prompt-template",
            inputs={
                "template": "{{review}}",
                "variables": {"review": "This product exceeded my expectations!"},
            },
        ),
        Node(
            id="classify",
            type="ai.classify",
            inputs={
                "categories": ["positive", "negative", "neutral"],
            },
        ),
    ],
    edges=[
        Edge(from_node="input", from_port="prompt", to_node="classify", to_port="text"),
    ],
)

context = await runtime.execute(graph)
result = context.node_results["classify"]
print(f"Category: {result.outputs['category']}")
print(f"Confidence: {result.outputs['confidence']}")
```

---

## Configuration

### Worker Registration

**Basic Registration (default Router and AgentRegistry):**

```python
from mascarade.node_engine.runtime import GraphRuntime
from mascarade.node_engine.workers.ai.register import register_ai_worker

runtime = GraphRuntime()
ai_worker = register_ai_worker(runtime)
```

**Advanced Registration (custom Router and AgentRegistry):**

```python
from mascarade.router import Router
from mascarade.agents.registry import AgentRegistry
from mascarade.orchestrator.engine import Orchestrator

# Create custom instances
router = Router()
registry = AgentRegistry()
orchestrator = Orchestrator(router=router, registry=registry)

# Register with custom configuration
ai_worker = register_ai_worker(
    runtime=runtime,
    router=router,
    registry=registry,
    orchestrator=orchestrator,
)
```

### Worker Capabilities

The AI Worker declares the following capabilities:

```python
{
    "node_types": [
        "ai.llm-inference",
        "ai.llm-stream",
        "ai.embedding",
        "ai.prompt-template",
        "ai.chain-of-thought",
        "ai.agent-dispatch",
        "ai.router-select",
        "ai.batch-inference",
        "ai.summarize",
        "ai.classify",
        "ai.orchestrate-sequential",
        "ai.orchestrate-parallel",
        "ai.orchestrate-pipeline",
    ],
    "domain": "ai",
    "supports_streaming": True,
    "supports_cancellation": True,
    "max_concurrent": 10,
    "requires_gpu": False,
    "requires_hardware": False,
    "estimated_memory_mb": 128,
}
```

### Performance Targets

| Metric | Target | Rationale |
|--------|--------|-----------|
| Node dispatch overhead | < 5ms | Graph runtime should not add perceptible latency to LLM calls |
| Graph compilation (10 nodes) | < 50ms | Must feel instantaneous in the UI |
| Concurrent inference nodes | ≥ 10 | Matches `max_concurrent` capability |
| Memory per AI Worker | < 128 MB | Fits within the 6.8 GiB VM budget alongside other services |

---

## Further Reading

- **Universal Node Engine:** `core/mascarade/node_engine/README.md`
- **Phase 1 AI Worker Specification:** `.auto-claude/specs/029-phase-1-ai-worker/spec.md`
- **Router Documentation:** `core/mascarade/router/README.md`
- **Agent System:** `core/mascarade/agents/README.md`
- **Orchestrator:** `core/mascarade/orchestrator/README.md`

<iframe src="https://github.com/sponsors/electron-rare/card" title="Sponsor electron-rare" height="225" width="600" style="border: 0;"></iframe>
