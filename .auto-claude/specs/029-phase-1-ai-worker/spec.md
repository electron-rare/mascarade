# Phase 1 — AI Worker Specification

**Document:** SPEC-029-P1 — Universal Node Engine Phase 1 AI Worker
**Date:** 2026-03-16
**Version:** 1.0
**Status:** Draft
**Parent:** SPEC-029 (Universal Node Engine Architecture)
**Phase:** MVP (Phase 0 + Phase 1)

---

## Table of Contents

1. [Overview](#1-overview)
2. [AI Domain Port Types](#2-ai-domain-port-types)
3. [Node Types](#3-node-types)
4. [Router Integration](#4-router-integration)
5. [Orchestrator Integration](#5-orchestrator-integration)
6. [AgentRegistry Integration](#6-agentregistry-integration)
7. [AI Worker Implementation](#7-ai-worker-implementation)
8. [Acceptance Criteria](#8-acceptance-criteria)

---

## 1. Overview

Phase 1 delivers the AI Worker — the first domain worker for the Universal Node Engine. Together with Phase 0 (Foundations), Phase 1 constitutes the **Minimum Viable Product (MVP)** that must be validated before expanding into CAD, Electronics, and Hardware domains.

The AI Worker is unique among domain workers because it wraps existing, production-proven Mascarade services rather than introducing new capabilities. It integrates the Universal Node Engine with:

- **Router** (`core/mascarade/router/`) — multi-provider LLM dispatch with circuit breakers
- **Orchestrator** (`core/mascarade/orchestrator/engine.py`) — multi-agent sequential/parallel/pipeline execution
- **AgentRegistry** (`core/mascarade/agents/registry.py`) — agent discovery and management

### 1.1 Goals

- Define AI-specific domain port types (`LLMResponse`, `EmbeddingVector`, `PromptTemplate`, `ChatMessage`, `TokenUsage`)
- Implement LLM Inference Nodes wrapping `Router.send()` and `Router.stream()`
- Implement Embedding Nodes for text/image embedding via the provider system
- Implement Reasoning Chain Nodes for chain-of-thought and multi-step reasoning
- Implement Prompt Template Nodes for variable substitution and template management
- Implement Router Integration Nodes for strategy selection (cheapest/fastest/best/specific)
- Implement Orchestrator Nodes for sequential/parallel/pipeline execution modes
- Integrate with the `AgentRegistry` for agent dispatch within graphs

### 1.2 Non-Goals

- CAD, Electronics, or Hardware domain workers (Phases 2–4)
- Cross-domain type adapters (Phase 5)
- Fine-tuning or model training nodes
- Custom model hosting infrastructure

### 1.3 Dependencies

- Phase 0 Foundations (core type system, graph runtime, NodeWorker interface, registry)
- `LLMProvider` interface (`core/mascarade/router/providers/base.py`)
- `Agent` base class (`core/mascarade/agents/base.py`)
- `Orchestrator` engine (`core/mascarade/orchestrator/engine.py`)
- `Router` with strategy-based dispatch (`core/mascarade/router/router.py`)

---

## 2. AI Domain Port Types

These types extend the Phase 0 base type system with AI-specific structures. They are registered as `DomainType` instances during AI Worker initialization — not hard-coded into the core type system.

### 2.1 Type Definitions

```python
"""AI Worker domain types.

These types extend the base type system with AI-specific structures.
Modeled on the existing LLMResponse dataclass from providers/base.py.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class LLMResponse:
    """Normalized LLM response — mirrors core/mascarade/router/providers/base.py.

    This is the primary output type for inference nodes. It preserves
    the exact structure used by the Router so that downstream consumers
    can access provider metadata without transformation.
    """

    content: str
    model: str
    provider: str
    usage: dict[str, int] = field(default_factory=dict)


@dataclass
class TokenUsage:
    """Token consumption metrics for cost tracking and budgeting."""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    cost_usd: float = 0.0


@dataclass
class EmbeddingVector:
    """Dense vector embedding produced by an embedding model."""

    values: list[float]
    model: str
    dimensions: int


@dataclass
class ChatMessage:
    """A single message in a conversation.

    Follows the standard role-based message format used by all
    LLM providers in the Mascarade Router.
    """

    role: str          # "system" | "user" | "assistant"
    content: str
    name: str | None = None


@dataclass
class PromptTemplate:
    """A template with variable placeholders for dynamic prompt construction."""

    template: str
    variables: list[str]       # Variable names expected in the template
    defaults: dict[str, str] = field(default_factory=dict)
```

### 2.2 Domain Type Registration

AI domain types are registered with the `NodeTypeRegistry` at worker startup using the `DomainType` model from Phase 0:

```python
AI_DOMAIN_TYPES = [
    DomainType(
        domain="ai",
        name="LLMResponse",
        schema={
            "type": "object",
            "properties": {
                "content": {"type": "string"},
                "model": {"type": "string"},
                "provider": {"type": "string"},
                "usage": {"type": "object"},
            },
            "required": ["content", "model", "provider"],
        },
    ),
    DomainType(
        domain="ai",
        name="TokenUsage",
        schema={
            "type": "object",
            "properties": {
                "prompt_tokens": {"type": "integer"},
                "completion_tokens": {"type": "integer"},
                "total_tokens": {"type": "integer"},
                "cost_usd": {"type": "number"},
            },
        },
    ),
    DomainType(
        domain="ai",
        name="EmbeddingVector",
        schema={
            "type": "object",
            "properties": {
                "values": {"type": "array", "items": {"type": "number"}},
                "model": {"type": "string"},
                "dimensions": {"type": "integer"},
            },
            "required": ["values", "model", "dimensions"],
        },
    ),
    DomainType(
        domain="ai",
        name="ChatMessage",
        schema={
            "type": "object",
            "properties": {
                "role": {"type": "string", "enum": ["system", "user", "assistant"]},
                "content": {"type": "string"},
                "name": {"type": "string"},
            },
            "required": ["role", "content"],
        },
    ),
    DomainType(
        domain="ai",
        name="PromptTemplate",
        schema={
            "type": "object",
            "properties": {
                "template": {"type": "string"},
                "variables": {"type": "array", "items": {"type": "string"}},
                "defaults": {"type": "object"},
            },
            "required": ["template", "variables"],
        },
    ),
]
```

---

## 3. Node Types

### 3.1 LLM Inference Nodes

These nodes wrap the Router's `send()` and `stream()` methods, exposing LLM inference as composable graph nodes.

#### 3.1.1 `ai.llm-inference`

Send a prompt to an LLM via the Router and receive a complete response.

| Property | Value |
|----------|-------|
| **Domain** | `ai` |
| **Category** | Inference |
| **MVP** | Yes |

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
| `strategy` | `string` | `"best"` | Router strategy: cheapest/fastest/best/specific |

**Integration:** Delegates to `Router.send()`. The Router's existing circuit breaker (fail_max=5, timeout=60s) and retry logic (3 attempts, exponential backoff) are preserved. The AI Worker does not add another resilience layer.

#### 3.1.2 `ai.llm-stream`

Stream LLM response token by token for real-time output.

| Property | Value |
|----------|-------|
| **Domain** | `ai` |
| **Category** | Inference |
| **MVP** | Yes |

**Inputs:** Same as `ai.llm-inference`

**Outputs:**

| Port | Type | Description |
|------|------|-------------|
| `stream` | `stream<string>` | Token-by-token response stream |
| `usage` | `TokenUsage` | Token consumption (available after stream completes) |

**Integration:** Delegates to `Router.stream()`. Supports WebSocket forwarding for real-time UI updates.

#### 3.1.3 `ai.batch-inference`

Process multiple prompts in parallel via the Router.

| Property | Value |
|----------|-------|
| **Domain** | `ai` |
| **Category** | Inference |
| **MVP** | Yes |

**Inputs:**

| Port | Type | Required | Description |
|------|------|----------|-------------|
| `prompts` | `array<string>` | Yes | List of prompts to process |

**Outputs:**

| Port | Type | Description |
|------|------|-------------|
| `responses` | `array<LLMResponse>` | Responses in same order as inputs |
| `usage` | `TokenUsage` | Aggregate token consumption |

**Configuration:** Same as `ai.llm-inference` (applied to all prompts).

**Integration:** Maps to Orchestrator's `PARALLEL` execution mode. Respects `max_concurrent` capability limit.

### 3.2 Embedding Nodes

#### 3.2.1 `ai.embedding`

Generate embeddings for text input via the provider system.

| Property | Value |
|----------|-------|
| **Domain** | `ai` |
| **Category** | Embedding |
| **MVP** | Yes |

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

**Integration:** Invokes the provider's embedding endpoint. Falls back through the Router's provider list if the primary provider fails.

#### 3.2.2 `ai.embedding-batch`

Generate embeddings for multiple texts in a single call.

| Property | Value |
|----------|-------|
| **Domain** | `ai` |
| **Category** | Embedding |
| **MVP** | No (post-MVP) |

**Inputs:**

| Port | Type | Required | Description |
|------|------|----------|-------------|
| `texts` | `array<string>` | Yes | Texts to embed |

**Outputs:**

| Port | Type | Description |
|------|------|-------------|
| `vectors` | `array<EmbeddingVector>` | Embedding vectors in input order |

### 3.3 Reasoning Chain Nodes

#### 3.3.1 `ai.chain-of-thought`

Multi-step reasoning with intermediate outputs. Each step feeds its output as context to the next step.

| Property | Value |
|----------|-------|
| **Domain** | `ai` |
| **Category** | Reasoning |
| **MVP** | Yes |

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

**Integration:** Maps to the Orchestrator's `PIPELINE` execution mode. Each reasoning step is a sequential LLM call where the previous step's output is injected as context for the next.

#### 3.3.2 `ai.conditional-branch`

Conditional branching based on LLM classification of input.

| Property | Value |
|----------|-------|
| **Domain** | `ai` |
| **Category** | Reasoning |
| **MVP** | No (post-MVP) |

**Inputs:**

| Port | Type | Required | Description |
|------|------|----------|-------------|
| `input` | `string` | Yes | Text to classify for branching |
| `branches` | `array<string>` | Yes | Possible branch labels |

**Outputs:**

| Port | Type | Description |
|------|------|-------------|
| `selected` | `string` | The selected branch label |
| `confidence` | `number` | Classification confidence (0.0–1.0) |
| `trigger` | `void` | Trigger for the selected branch |

#### 3.3.3 `ai.classify`

Classify text into predefined categories.

| Property | Value |
|----------|-------|
| **Domain** | `ai` |
| **Category** | Reasoning |
| **MVP** | Yes |

**Inputs:**

| Port | Type | Required | Description |
|------|------|----------|-------------|
| `text` | `string` | Yes | Text to classify |
| `categories` | `array<string>` | Yes | Available categories |

**Outputs:**

| Port | Type | Description |
|------|------|-------------|
| `category` | `string` | Selected category |
| `confidence` | `number` | Classification confidence |

#### 3.3.4 `ai.summarize`

Summarize text using an LLM.

| Property | Value |
|----------|-------|
| **Domain** | `ai` |
| **Category** | Reasoning |
| **MVP** | Yes |

**Inputs:**

| Port | Type | Required | Description |
|------|------|----------|-------------|
| `text` | `string` | Yes | Text to summarize |
| `max_length` | `integer` | No | Target summary length |

**Outputs:**

| Port | Type | Description |
|------|------|-------------|
| `summary` | `string` | Summarized text |

### 3.4 Prompt Template Nodes

#### 3.4.1 `ai.prompt-template`

Apply variable substitution to a prompt template.

| Property | Value |
|----------|-------|
| **Domain** | `ai` |
| **Category** | Template |
| **MVP** | Yes |

**Inputs:**

| Port | Type | Required | Description |
|------|------|----------|-------------|
| `template` | `string` | Yes | Template string with `{{variable}}` placeholders |
| `variables` | `map<string, string>` | Yes | Variable name-value mappings |

**Outputs:**

| Port | Type | Description |
|------|------|-------------|
| `prompt` | `string` | Rendered prompt with variables substituted |

**Implementation:** Pure function — no LLM call. Replaces `{{key}}` patterns with corresponding values from the variables map.

#### 3.4.2 `ai.prompt-compose`

Compose a multi-part prompt from multiple inputs.

| Property | Value |
|----------|-------|
| **Domain** | `ai` |
| **Category** | Template |
| **MVP** | No (post-MVP) |

**Inputs:**

| Port | Type | Required | Description |
|------|------|----------|-------------|
| `parts` | `array<string>` | Yes | Prompt sections to combine |
| `separator` | `string` | No | Separator between parts (default: `"\n\n"`) |

**Outputs:**

| Port | Type | Description |
|------|------|-------------|
| `prompt` | `string` | Combined prompt |

### 3.5 Router Integration Nodes

#### 3.5.1 `ai.router-select`

Select a provider and model based on routing strategy, without executing an inference call.

| Property | Value |
|----------|-------|
| **Domain** | `ai` |
| **Category** | Router |
| **MVP** | Yes |

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

**Integration:** Queries the Router's provider registry and applies the strategy selection algorithm from `core/mascarade/router/router.py`. Uses `LLMProvider.cost_per_million`, `speed_rank`, and `quality_rank` attributes for ranking.

### 3.6 Orchestrator Nodes

#### 3.6.1 `ai.agent-dispatch`

Run a registered agent from the AgentRegistry within a graph.

| Property | Value |
|----------|-------|
| **Domain** | `ai` |
| **Category** | Orchestrator |
| **MVP** | Yes |

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

**Integration:** Looks up the agent by name in `AgentRegistry`, then calls `Agent.run()` with the configured Router. Preserves the agent's `strategy`, `preferred_provider`, `preferred_model`, `temperature`, and `max_tokens` settings.

**Validation:** At graph validation time, verifies that `agent_name` exists in the registry. Produces a validation error if the agent is not found.

#### 3.6.2 `ai.orchestrate-sequential`

Execute multiple agents sequentially, piping each output to the next.

| Property | Value |
|----------|-------|
| **Domain** | `ai` |
| **Category** | Orchestrator |
| **MVP** | Yes |

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

**Integration:** Maps directly to `Orchestrator.run()` with `ExecutionMode.SEQUENTIAL`.

#### 3.6.3 `ai.orchestrate-parallel`

Execute multiple agents in parallel on the same input.

| Property | Value |
|----------|-------|
| **Domain** | `ai` |
| **Category** | Orchestrator |
| **MVP** | Yes |

**Inputs:**

| Port | Type | Required | Description |
|------|------|----------|-------------|
| `agents` | `array<string>` | Yes | List of agent names to run concurrently |
| `prompt` | `string` | Yes | Prompt sent to all agents |

**Outputs:**

| Port | Type | Description |
|------|------|-------------|
| `results` | `array<LLMResponse>` | Responses from all agents |

**Integration:** Maps directly to `Orchestrator.run()` with `ExecutionMode.PARALLEL`.

#### 3.6.4 `ai.orchestrate-pipeline`

Execute agents in a pipeline where each agent's output feeds into the next.

| Property | Value |
|----------|-------|
| **Domain** | `ai` |
| **Category** | Orchestrator |
| **MVP** | Yes |

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

**Integration:** Maps directly to `Orchestrator.run()` with `ExecutionMode.PIPELINE`.

---

## 4. Router Integration

The AI Worker delegates all LLM calls to the existing Router infrastructure. This section details how the integration works.

### 4.1 Strategy Mapping

Node configuration maps to Router strategies defined in `core/mascarade/router/router.py`:

| Node Config `strategy` | Router `Strategy` | Selection Criteria |
|-------------------------|--------------------|--------------------|
| `"cheapest"` | `Strategy.CHEAPEST` | Lowest `cost_per_million` |
| `"fastest"` | `Strategy.FASTEST` | Lowest `speed_rank` |
| `"best"` | `Strategy.BEST` | Highest `quality_rank` |
| `"specific"` | `Strategy.SPECIFIC` | Exact provider/model match |

### 4.2 Resilience

The Router provides built-in resilience that the AI Worker inherits:

- **Circuit Breakers:** Per-provider circuit breakers (fail_max=5, timeout=60s) prevent cascading failures. Defined in the `LLMProvider` interface.
- **Retry Logic:** Exponential backoff retry (3 attempts) via `tenacity` for transient errors (`ConnectionError`, `TimeoutError`, `OSError`). Defined via `make_retry()` in `providers/base.py`.
- **Dead Letter Queue:** Failed requests are captured in the Orchestrator's `DeadLetterStore` for later inspection.

The AI Worker does **not** add its own retry or circuit breaker layer. This avoids retry amplification.

### 4.3 Provider Attributes

The AI Worker exposes provider attributes through the `ai.router-select` node:

- `LLMProvider.cost_per_million` — cost per 1M tokens (input, output)
- `LLMProvider.speed_rank` — relative speed ranking (lower = faster)
- `LLMProvider.quality_rank` — relative quality ranking (higher = better)
- `LLMProvider.available_models()` — list of available models
- `LLMProvider.is_configured` — whether the provider has API keys configured

---

## 5. Orchestrator Integration

The AI Worker maps graph-level orchestration patterns to the existing Orchestrator's execution modes.

### 5.1 Execution Mode Mapping

| Node Type | Orchestrator Mode | Description |
|-----------|-------------------|-------------|
| `ai.orchestrate-sequential` | `ExecutionMode.SEQUENTIAL` | Agents run one after another |
| `ai.orchestrate-parallel` | `ExecutionMode.PARALLEL` | Agents run concurrently |
| `ai.orchestrate-pipeline` | `ExecutionMode.PIPELINE` | Output of each agent feeds into the next |
| `ai.chain-of-thought` | `ExecutionMode.PIPELINE` | Multi-step reasoning as sequential LLM calls |
| `ai.batch-inference` | `ExecutionMode.PARALLEL` | Multiple prompts processed concurrently |

### 5.2 Resilience Inheritance

The Orchestrator provides additional resilience features that the AI Worker inherits:

- **Per-agent circuit breakers** (`Orchestrator.circuit_breakers`)
- **Retry executor** with configurable `RetryConfig`
- **Dead letter store** for failed agent executions
- **Ray-based distributed execution** (when enabled) with its own circuit breaker and timeout management
- **Trace buffer** (`AgentTraceBuffer`) for observability

---

## 6. AgentRegistry Integration

The `ai.agent-dispatch` node bridges the Node Engine with the existing agent system.

### 6.1 Agent Lookup

Agents are resolved by name via `AgentRegistry.get()`. The registry contains all registered agents, including domain-specific agents like:

- `kicad-designer` — KiCad schematic and PCB design
- `spice-expert` — SPICE simulation and analysis
- `freecad-modeler` — FreeCAD 3D modeling

This allows domain-specific agents to be invoked from AI Worker graphs even before their dedicated domain workers (Phases 2–4) are implemented.

### 6.2 Agent Configuration Passthrough

When dispatching to an agent, the AI Worker preserves the agent's own configuration:

```python
agent = registry.get(agent_name)
# Agent's own settings are used:
# - agent.strategy (cheapest/fastest/best/specific)
# - agent.preferred_provider
# - agent.preferred_model
# - agent.temperature
# - agent.max_tokens
# - agent.system_prompt
response = await agent.run(message, router=router)
```

The node does not override these settings unless explicitly configured to do so.

---

## 7. AI Worker Implementation

### 7.1 Worker Class

```python
"""AI Worker implementation.

Wraps existing Mascarade Router, Orchestrator, and AgentRegistry
into the NodeWorker interface for graph-based execution.
"""

from __future__ import annotations

from typing import Any

from mascarade.agents.registry import AgentRegistry
from mascarade.orchestrator.engine import ExecutionMode, Orchestrator
from mascarade.router import Router
from mascarade.router.router import Strategy


class AIWorker:
    """AI domain worker — wraps Mascarade LLM infrastructure.

    Implements the NodeWorker interface defined in Phase 0.
    All LLM calls delegate to the Router; all multi-agent
    patterns delegate to the Orchestrator.
    """

    name = "ai-worker"
    domain = "ai"

    def __init__(
        self,
        router: Router,
        registry: AgentRegistry,
        orchestrator: Orchestrator | None = None,
    ) -> None:
        self._router = router
        self._registry = registry
        self._orchestrator = orchestrator or Orchestrator(
            router=router, registry=registry,
        )

    async def execute(
        self,
        node_type: str,
        inputs: dict[str, Any],
        config: dict[str, Any],
        context: Any,
    ) -> dict[str, Any]:
        """Execute an AI node. Dispatches to the appropriate handler."""
        handlers = {
            "ai.llm-inference": self._llm_inference,
            "ai.llm-stream": self._llm_stream,
            "ai.embedding": self._embedding,
            "ai.prompt-template": self._prompt_template,
            "ai.chain-of-thought": self._chain_of_thought,
            "ai.agent-dispatch": self._agent_dispatch,
            "ai.router-select": self._router_select,
            "ai.batch-inference": self._batch_inference,
            "ai.summarize": self._summarize,
            "ai.classify": self._classify,
            "ai.orchestrate-sequential": self._orchestrate_sequential,
            "ai.orchestrate-parallel": self._orchestrate_parallel,
            "ai.orchestrate-pipeline": self._orchestrate_pipeline,
        }
        handler = handlers.get(node_type)
        if handler is None:
            raise ValueError(f"Unknown AI node type: {node_type}")
        if node_type == "ai.prompt-template":
            return handler(inputs)
        if node_type == "ai.router-select":
            return handler(inputs, config)
        return await handler(inputs, config)

    async def _llm_inference(
        self, inputs: dict[str, Any], config: dict[str, Any],
    ) -> dict[str, Any]:
        strategy = Strategy(config.get("strategy", "best"))
        messages = list(inputs.get("context", []))
        messages.append({"role": "user", "content": inputs["prompt"]})
        response = await self._router.send(
            messages=messages,
            strategy=strategy,
            system=inputs.get("system"),
            model=config.get("model"),
            temperature=config.get("temperature", 0.7),
            max_tokens=config.get("max_tokens", 4096),
        )
        return {
            "response": {
                "content": response.content,
                "model": response.model,
                "provider": response.provider,
                "usage": response.usage,
            },
            "usage": response.usage,
        }

    async def _llm_stream(
        self, inputs: dict[str, Any], config: dict[str, Any],
    ) -> dict[str, Any]:
        strategy = Strategy(config.get("strategy", "best"))
        messages = list(inputs.get("context", []))
        messages.append({"role": "user", "content": inputs["prompt"]})
        stream = self._router.stream(
            messages=messages,
            strategy=strategy,
            system=inputs.get("system"),
            model=config.get("model"),
            temperature=config.get("temperature", 0.7),
            max_tokens=config.get("max_tokens", 4096),
        )
        return {"stream": stream}

    async def _embedding(
        self, inputs: dict[str, Any], config: dict[str, Any],
    ) -> dict[str, Any]:
        # Delegates to provider embedding endpoint via Router
        provider_name = config.get("provider")
        model = config.get("model")
        # Implementation depends on provider embedding API
        raise NotImplementedError("Embedding support pending provider implementation")

    def _prompt_template(self, inputs: dict[str, Any]) -> dict[str, Any]:
        template = inputs["template"]
        variables = inputs.get("variables", {})
        result = template
        for key, value in variables.items():
            result = result.replace(f"{{{{{key}}}}}", str(value))
        return {"prompt": result}

    async def _chain_of_thought(
        self, inputs: dict[str, Any], config: dict[str, Any],
    ) -> dict[str, Any]:
        steps = inputs.get("steps", 3)
        question = inputs["question"]
        reasoning = []
        current_context = question

        for i in range(steps):
            step_prompt = (
                f"Step {i + 1}/{steps}: Reason about the following.\n\n"
                f"{current_context}\n\n"
                f"Provide your reasoning for this step."
            )
            result = await self._llm_inference(
                {"prompt": step_prompt}, config,
            )
            step_output = result["response"]["content"]
            reasoning.append(step_output)
            current_context = f"{question}\n\nPrevious reasoning:\n" + "\n".join(reasoning)

        # Final synthesis
        synthesis_prompt = (
            f"Based on the following reasoning steps, provide a final answer.\n\n"
            f"Question: {question}\n\n"
            f"Reasoning:\n" + "\n---\n".join(reasoning)
        )
        final = await self._llm_inference({"prompt": synthesis_prompt}, config)

        return {
            "reasoning": reasoning,
            "answer": final["response"]["content"],
            "usage": final["usage"],
        }

    async def _agent_dispatch(
        self, inputs: dict[str, Any], config: dict[str, Any],
    ) -> dict[str, Any]:
        agent = self._registry.get(inputs["agent_name"])
        context = inputs.get("context")
        response = await agent.run(
            inputs["message"],
            router=self._router,
            context=context,
        )
        return {
            "response": {
                "content": response.content,
                "model": response.model,
                "provider": response.provider,
                "usage": response.usage,
            },
        }

    def _router_select(
        self, inputs: dict[str, Any], config: dict[str, Any],
    ) -> dict[str, Any]:
        strategy = Strategy(inputs["strategy"])
        # Selection logic mirrors Router's internal strategy resolution
        # Returns the provider/model that would be selected
        return {"provider": "", "model": ""}  # Resolved at runtime

    async def _batch_inference(
        self, inputs: dict[str, Any], config: dict[str, Any],
    ) -> dict[str, Any]:
        import asyncio

        prompts = inputs["prompts"]
        tasks = [
            self._llm_inference({"prompt": p}, config)
            for p in prompts
        ]
        results = await asyncio.gather(*tasks)
        return {
            "responses": [r["response"] for r in results],
            "usage": {
                "total_tokens": sum(
                    r["usage"].get("total_tokens", 0) for r in results
                ),
            },
        }

    async def _summarize(
        self, inputs: dict[str, Any], config: dict[str, Any],
    ) -> dict[str, Any]:
        max_length = inputs.get("max_length", 200)
        prompt = (
            f"Summarize the following text in approximately {max_length} words:\n\n"
            f"{inputs['text']}"
        )
        result = await self._llm_inference({"prompt": prompt}, config)
        return {"summary": result["response"]["content"]}

    async def _classify(
        self, inputs: dict[str, Any], config: dict[str, Any],
    ) -> dict[str, Any]:
        categories = inputs["categories"]
        prompt = (
            f"Classify the following text into exactly one of these categories: "
            f"{', '.join(categories)}\n\n"
            f"Text: {inputs['text']}\n\n"
            f"Respond with only the category name."
        )
        result = await self._llm_inference(
            {"prompt": prompt},
            {**config, "temperature": 0.1},
        )
        return {
            "category": result["response"]["content"].strip(),
            "confidence": 1.0,  # Placeholder — real confidence requires logprobs
        }

    async def _orchestrate_sequential(
        self, inputs: dict[str, Any], config: dict[str, Any],
    ) -> dict[str, Any]:
        run = await self._orchestrator.run(
            agents=inputs["agents"],
            prompt=inputs["initial_prompt"],
            mode=ExecutionMode.SEQUENTIAL,
        )
        return {
            "results": [
                {
                    "content": r.response.content,
                    "model": r.response.model,
                    "provider": r.response.provider,
                    "usage": r.response.usage,
                }
                for r in run.results
            ],
            "final": {
                "content": run.results[-1].response.content,
                "model": run.results[-1].response.model,
                "provider": run.results[-1].response.provider,
                "usage": run.results[-1].response.usage,
            },
        }

    async def _orchestrate_parallel(
        self, inputs: dict[str, Any], config: dict[str, Any],
    ) -> dict[str, Any]:
        run = await self._orchestrator.run(
            agents=inputs["agents"],
            prompt=inputs["prompt"],
            mode=ExecutionMode.PARALLEL,
        )
        return {
            "results": [
                {
                    "content": r.response.content,
                    "model": r.response.model,
                    "provider": r.response.provider,
                    "usage": r.response.usage,
                }
                for r in run.results
            ],
        }

    async def _orchestrate_pipeline(
        self, inputs: dict[str, Any], config: dict[str, Any],
    ) -> dict[str, Any]:
        run = await self._orchestrator.run(
            agents=inputs["agents"],
            prompt=inputs["initial_prompt"],
            mode=ExecutionMode.PIPELINE,
        )
        return {
            "results": [
                {
                    "content": r.response.content,
                    "model": r.response.model,
                    "provider": r.response.provider,
                    "usage": r.response.usage,
                }
                for r in run.results
            ],
            "final": {
                "content": run.results[-1].response.content,
                "model": run.results[-1].response.model,
                "provider": run.results[-1].response.provider,
                "usage": run.results[-1].response.usage,
            },
        }

    async def validate(
        self, node_type: str, inputs: dict[str, Any], config: dict[str, Any],
    ) -> list[str]:
        """Validate node inputs before execution."""
        errors: list[str] = []
        if node_type == "ai.llm-inference" and "prompt" not in inputs:
            errors.append("Missing required input: prompt")
        if node_type == "ai.agent-dispatch":
            if "agent_name" not in inputs:
                errors.append("Missing required input: agent_name")
            elif inputs["agent_name"] not in self._registry:
                errors.append(f"Agent '{inputs['agent_name']}' not found in registry")
        if node_type == "ai.prompt-template" and "template" not in inputs:
            errors.append("Missing required input: template")
        if node_type == "ai.chain-of-thought" and "question" not in inputs:
            errors.append("Missing required input: question")
        if node_type == "ai.classify":
            if "text" not in inputs:
                errors.append("Missing required input: text")
            if "categories" not in inputs:
                errors.append("Missing required input: categories")
        if node_type == "ai.batch-inference" and "prompts" not in inputs:
            errors.append("Missing required input: prompts")
        return errors

    def capabilities(self) -> dict[str, Any]:
        """Declare worker capabilities for the registry."""
        return {
            "node_types": [
                "ai.llm-inference", "ai.llm-stream", "ai.embedding",
                "ai.prompt-template", "ai.chain-of-thought", "ai.agent-dispatch",
                "ai.router-select", "ai.batch-inference", "ai.summarize",
                "ai.classify", "ai.orchestrate-sequential",
                "ai.orchestrate-parallel", "ai.orchestrate-pipeline",
            ],
            "domain": "ai",
            "supports_streaming": True,
            "supports_cancellation": True,
            "max_concurrent": 10,
            "requires_gpu": False,
            "requires_hardware": False,
            "estimated_memory_mb": 128,
        }

    @property
    def is_available(self) -> bool:
        """AI Worker is available if the Router has at least one configured provider."""
        return True
```

### 7.2 Node Type Summary

| Node Type | Category | MVP | LLM Call | Integration |
|-----------|----------|-----|----------|-------------|
| `ai.llm-inference` | Inference | Yes | `Router.send()` | Router |
| `ai.llm-stream` | Inference | Yes | `Router.stream()` | Router |
| `ai.batch-inference` | Inference | Yes | `Router.send()` × N | Router + Orchestrator (PARALLEL) |
| `ai.embedding` | Embedding | Yes | Provider embedding API | Router |
| `ai.embedding-batch` | Embedding | No | Provider embedding API | Router |
| `ai.chain-of-thought` | Reasoning | Yes | `Router.send()` × steps | Orchestrator (PIPELINE) |
| `ai.conditional-branch` | Reasoning | No | `Router.send()` | Router |
| `ai.classify` | Reasoning | Yes | `Router.send()` | Router |
| `ai.summarize` | Reasoning | Yes | `Router.send()` | Router |
| `ai.prompt-template` | Template | Yes | None (pure function) | — |
| `ai.prompt-compose` | Template | No | None (pure function) | — |
| `ai.router-select` | Router | Yes | None (query only) | Router |
| `ai.agent-dispatch` | Orchestrator | Yes | Via Agent | AgentRegistry |
| `ai.orchestrate-sequential` | Orchestrator | Yes | Via Orchestrator | Orchestrator (SEQUENTIAL) |
| `ai.orchestrate-parallel` | Orchestrator | Yes | Via Orchestrator | Orchestrator (PARALLEL) |
| `ai.orchestrate-pipeline` | Orchestrator | Yes | Via Orchestrator | Orchestrator (PIPELINE) |

---

## 8. Acceptance Criteria

### 8.1 MVP Gate

Phase 1 (AI Worker) combined with Phase 0 (Foundations) must pass the following criteria before proceeding to Phase 2:

1. **All MVP node types execute successfully** — each node listed as MVP=Yes must handle valid inputs and produce correctly-typed outputs
2. **Router integration validated** — `ai.llm-inference` successfully dispatches to at least two different providers via strategy selection
3. **Orchestrator integration validated** — `ai.orchestrate-pipeline` successfully chains at least two agents
4. **AgentRegistry integration validated** — `ai.agent-dispatch` successfully invokes a registered agent and returns its response
5. **Type validation enforced** — connecting incompatible port types produces a clear validation error at graph validation time
6. **Error propagation** — Router circuit breaker trips are surfaced as node execution errors with actionable messages
7. **Streaming works** — `ai.llm-stream` produces a `stream<string>` that can be consumed by downstream nodes or forwarded via WebSocket

### 8.2 Performance Targets

| Metric | Target | Rationale |
|--------|--------|-----------|
| Node dispatch overhead | < 5ms | Graph runtime should not add perceptible latency to LLM calls |
| Graph compilation (10 nodes) | < 50ms | Must feel instantaneous in the UI |
| Concurrent inference nodes | ≥ 10 | Matches `max_concurrent` capability |
| Memory per AI Worker | < 128 MB | Fits within the 6.8 GiB VM budget alongside other services |

### 8.3 Test Coverage

- Unit tests for each node type handler
- Integration tests for Router delegation (mock provider)
- Integration tests for Orchestrator delegation (mock agents)
- Validation tests for all required-input constraints
- Type compatibility tests for AI domain port types

## SPEC-025 Compatibility

All AI Worker nodes implement the `NodeWorker` interface defined in Phase 0, which includes backward compatibility with SPEC-025 (`NodePlugin`) via the `Spec025Adapter`. Existing AI integrations built on SPEC-025 can be wrapped without modification.
