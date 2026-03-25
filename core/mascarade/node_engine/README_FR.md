# Universal Node Engine

Graph-based execution system for composable domain workflows across AI, CAD, Electronics, and Hardware domains.

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Core Concepts](#core-concepts)
4. [Quick Start](#quick-start)
5. [Usage Examples](#usage-examples)
6. [API Reference](#api-reference)
7. [Worker Development](#worker-development)
8. [Testing](#testing)

---

## Overview

The Universal Node Engine provides a type-safe, graph-based execution runtime for composing domain-specific operations into workflows. Unlike monolithic orchestration systems, the Node Engine follows a **domain worker** pattern where each domain (AI, CAD, Electronics, Hardware) implements the `NodeWorker` interface independently.

### Key Features

- **Type-Safe Graphs** — Pydantic-based graph models with DAG validation and port type checking
- **Domain Workers** — Pluggable workers that execute nodes within their domain
- **Async Execution** — Native async/await support for concurrent node execution
- **Topological Ordering** — Automatic dependency resolution and execution ordering
- **Extensible Type System** — Domain-specific types registered at runtime via `DomainType`
- **Graph Validation** — Pre-execution validation catches errors before execution begins

### Architecture Principles

1. **Domain Isolation** — Each domain worker is self-contained and owns its node types
2. **Type Registration** — Domain types are registered at worker startup, not hard-coded
3. **Worker Interface** — All workers implement `NodeWorker` (execute, validate, capabilities)
4. **Graph-First** — Graphs are first-class citizens; single-node execution is a convenience method

---

## Architecture

### Component Overview

```
┌─────────────────────────────────────────────────────────────┐
│                     GraphRuntime                            │
│  • Validates graphs (DAG, types, worker availability)       │
│  • Computes topological execution order                     │
│  • Resolves edge-connected inputs                           │
│  • Dispatches nodes to domain workers                       │
│  • Tracks execution state and results                       │
└────────────┬────────────────────────────────────────────────┘
             │
             │ registers workers
             │
   ┌─────────┴──────────┐
   │                    │
   v                    v
┌──────────────┐  ┌──────────────┐
│  AIWorker    │  │  CADWorker   │  ... (future domains)
│  domain: ai  │  │  domain: cad │
└──────────────┘  └──────────────┘
   │                    │
   │ executes           │ executes
   │                    │
   v                    v
┌──────────────┐  ┌──────────────┐
│ ai.llm-      │  │ cad.sketch   │
│ inference    │  │              │
│              │  │ cad.extrude  │
│ ai.agent-    │  │              │
│ dispatch     │  │ cad.fillet   │
└──────────────┘  └──────────────┘
```

### Core Modules

| Module | Purpose |
|--------|---------|
| `types.py` | `DomainType` and `PortType` definitions — foundation for domain-specific types |
| `registry.py` | `NodeTypeRegistry` for registering and discovering domain types |
| `graph.py` | `Graph`, `Node`, `Edge` models with DAG validation |
| `runtime.py` | `GraphRuntime` for executing graphs and dispatching to workers |
| `worker.py` | `NodeWorker` abstract interface for domain workers |
| `workers/ai/` | AI domain worker implementation (Phase 1) |

---

## Core Concepts

### Domain Types

Domain types extend the base type system with domain-specific structures. They are defined as JSON Schema and registered at worker startup:

```python
from mascarade.node_engine.types import DomainType

# Register an AI domain type
llm_response_type = DomainType(
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
)
```

**Primitive Types:** `string`, `number`, `integer`, `boolean`, `json`, `void`, `array<T>`, `map<K,V>`, `stream<T>`

**Domain Types:** Qualified as `domain.TypeName` (e.g., `ai.LLMResponse`, `cad.Sketch`)

### Graphs

Graphs are directed acyclic graphs (DAGs) composed of **nodes** (computation units) and **edges** (data flow connections):

```python
from mascarade.node_engine.graph import Graph, Node, Edge

graph = Graph(
    nodes=[
        Node(
            id="template1",
            type="ai.prompt-template",
            inputs={"template": "Hello {{name}}!"},
        ),
        Node(
            id="llm1",
            type="ai.llm-inference",
            config={"temperature": 0.7, "model": "gpt-4"},
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
)
```

**Graph Validation:**
- All node IDs must be unique
- All edges must reference existing nodes
- No cycles (DAG constraint enforced via topological sort)
- All referenced node types must have registered workers

### Nodes

Nodes represent computation units with typed inputs, outputs, and configuration:

**Anatomy of a Node:**
```python
Node(
    id="llm1",                      # Unique identifier within the graph
    type="ai.llm-inference",        # Fully qualified node type (domain.typename)
    inputs={"prompt": "Hello!"},    # Input port values (literal or edge-connected)
    config={"temperature": 0.7},    # Node configuration parameters
)
```

**Node Execution:**
1. Runtime resolves inputs from edges (upstream node outputs)
2. Runtime validates inputs against worker's validation logic
3. Runtime dispatches to the appropriate worker based on domain
4. Worker executes and returns output port values

### Workers

Workers implement the `NodeWorker` interface to provide domain-specific node types:

```python
from mascarade.node_engine.worker import NodeWorker

class MyWorker(NodeWorker):
    name = "my-worker"
    domain = "my-domain"

    async def execute(self, node_type, inputs, config, context):
        # Execute the node and return outputs
        return {"result": "..."}

    async def validate(self, node_type, inputs, config):
        # Validate inputs and return error messages
        errors = []
        if "required_input" not in inputs:
            errors.append("Missing required input: required_input")
        return errors

    def capabilities(self):
        return {
            "node_types": ["my-domain.node-a", "my-domain.node-b"],
            "domain": "my-domain",
            "supports_streaming": False,
            "max_concurrent": 5,
        }
```

**Worker Registration:**
```python
runtime = GraphRuntime()
runtime.register_worker(MyWorker())
```

---

## Quick Start

### 1. Create a Graph

```python
from mascarade.node_engine.graph import Graph, Node, Edge

graph = Graph(
    nodes=[
        Node(id="n1", type="ai.llm-inference", inputs={"prompt": "Hello!"}),
    ],
)
```

### 2. Initialize Runtime and Register Workers

```python
from mascarade.node_engine.runtime import GraphRuntime
from mascarade.node_engine.workers.ai.worker import AIWorker
from mascarade.router import Router
from mascarade.agents.registry import AgentRegistry

runtime = GraphRuntime()

# Register AI worker
ai_worker = AIWorker(
    router=Router(),
    registry=AgentRegistry(),
)
runtime.register_worker(ai_worker)
```

### 3. Execute the Graph

```python
context = await runtime.execute(graph)

# Check execution status
if context.status == "completed":
    for node_id, result in context.node_results.items():
        print(f"{node_id}: {result.outputs}")
```

---

## Usage Examples

### Example 1: Single-Node LLM Inference

```python
from mascarade.node_engine.runtime import GraphRuntime
from mascarade.node_engine.workers.ai.worker import AIWorker
from mascarade.router import Router
from mascarade.agents.registry import AgentRegistry

# Initialize runtime
runtime = GraphRuntime()
ai_worker = AIWorker(router=Router(), registry=AgentRegistry())
runtime.register_worker(ai_worker)

# Execute a single node (convenience method)
outputs = await runtime.execute_node(
    node_type="ai.llm-inference",
    inputs={"prompt": "Explain quantum computing in one sentence."},
    config={"temperature": 0.7, "model": "gpt-4"},
)

print(outputs["response"])  # LLMResponse object
```

### Example 2: Multi-Node Template → LLM Pipeline

```python
from mascarade.node_engine.graph import Graph, Node, Edge

graph = Graph(
    nodes=[
        Node(
            id="template1",
            type="ai.prompt-template",
            inputs={
                "template": "Translate '{{text}}' to {{language}}",
                "variables": {"text": "Hello", "language": "French"},
            },
        ),
        Node(
            id="llm1",
            type="ai.llm-inference",
            config={"temperature": 0.3, "model": "gpt-4"},
        ),
    ],
    edges=[
        Edge(from_node="template1", from_port="prompt", to_node="llm1", to_port="prompt"),
    ],
)

context = await runtime.execute(graph)
result = context.node_results["llm1"]
print(result.outputs["response"].content)
```

### Example 3: Agent Dispatch

```python
from mascarade.node_engine.graph import Graph, Node

# Assuming an agent "coder-agent" is registered in AgentRegistry
graph = Graph(
    nodes=[
        Node(
            id="agent1",
            type="ai.agent-dispatch",
            inputs={
                "agent_name": "coder-agent",
                "task": "Write a Python function to check if a number is prime.",
            },
            config={"temperature": 0.7},
        ),
    ],
)

context = await runtime.execute(graph)
agent_result = context.node_results["agent1"]
print(agent_result.outputs["response"].content)
```

### Example 4: Orchestrator Sequential Execution

```python
graph = Graph(
    nodes=[
        Node(
            id="orchestrate1",
            type="ai.orchestrate-sequential",
            inputs={
                "steps": [
                    {"agent": "researcher", "task": "Find latest Python releases"},
                    {"agent": "summarizer", "task": "Summarize findings in 3 bullet points"},
                ],
            },
        ),
    ],
)

context = await runtime.execute(graph)
result = context.node_results["orchestrate1"]
print(result.outputs["results"])  # List of LLMResponse objects
```

### Example 5: Graph Validation Before Execution

```python
graph = Graph(
    nodes=[
        Node(id="n1", type="ai.llm-inference", inputs={}),  # Missing required "prompt" input
    ],
)

validation_errors = await runtime.validate_graph(graph)

if validation_errors:
    print("Graph validation failed:")
    for error in validation_errors:
        print(f"  - {error}")
else:
    context = await runtime.execute(graph)
```

---

## API Reference

### Core Classes

#### `DomainType`

**Location:** `mascarade.node_engine.types`

Domain-specific type definition with JSON schema validation.

**Fields:**
- `domain: str` — Domain identifier (e.g., `"ai"`, `"cad"`)
- `name: str` — Type name within the domain (e.g., `"LLMResponse"`)
- `schema: dict[str, Any]` — JSON Schema definition

**Properties:**
- `qualified_name: str` — Fully qualified type name (`domain.name`)

**Example:**
```python
domain_type = DomainType(
    domain="ai",
    name="LLMResponse",
    schema={"type": "object", "properties": {...}},
)
print(domain_type.qualified_name)  # "ai.LLMResponse"
```

---

#### `PortType`

**Location:** `mascarade.node_engine.types`

Port type definition for node inputs and outputs.

**Fields:**
- `name: str` — Port name (unique within the node)
- `type: str` — Port data type (primitive or domain-specific)
- `required: bool` — Whether the port must be connected (default: `True`)
- `description: str | None` — Human-readable description

**Properties:**
- `is_primitive: bool` — Check if type is primitive (not domain-specific)
- `is_stream: bool` — Check if type is a stream (`stream<T>`)
- `is_array: bool` — Check if type is an array (`array<T>`)
- `is_map: bool` — Check if type is a map (`map<K,V>`)

**Example:**
```python
port = PortType(
    name="prompt",
    type="string",
    required=True,
    description="User prompt for the LLM",
)
```

---

#### `Node`

**Location:** `mascarade.node_engine.graph`

A node in the execution graph.

**Fields:**
- `id: str` — Unique identifier within the graph
- `type: str` — Fully qualified node type (`domain.typename`)
- `inputs: dict[str, Any]` — Input port values (literal or edge-connected)
- `config: dict[str, Any]` — Node configuration parameters

**Properties:**
- `domain: str` — Extract domain from node type

**Example:**
```python
node = Node(
    id="llm1",
    type="ai.llm-inference",
    inputs={"prompt": "Hello!"},
    config={"temperature": 0.7},
)
```

---

#### `Edge`

**Location:** `mascarade.node_engine.graph`

A directed edge connecting two nodes.

**Fields:**
- `from_node: str` — Source node ID
- `from_port: str` — Source output port name
- `to_node: str` — Destination node ID
- `to_port: str` — Destination input port name

**Properties:**
- `source: tuple[str, str]` — `(node_id, port_name)` for source
- `destination: tuple[str, str]` — `(node_id, port_name)` for destination

**Validation:**
- Ensures no self-loops (node cannot connect to itself)

**Example:**
```python
edge = Edge(
    from_node="template1",
    from_port="prompt",
    to_node="llm1",
    to_port="prompt",
)
```

---

#### `Graph`

**Location:** `mascarade.node_engine.graph`

Directed acyclic graph (DAG) of nodes and edges.

**Fields:**
- `nodes: list[Node]` — List of nodes in the graph
- `edges: list[Edge]` — List of edges connecting nodes
- `metadata: dict[str, Any]` — Optional metadata (name, description, version)

**Methods:**
- `get_node(node_id: str) -> Node | None` — Get a node by ID
- `get_incoming_edges(node_id: str) -> list[Edge]` — Get edges connecting to a node
- `get_outgoing_edges(node_id: str) -> list[Edge]` — Get edges from a node
- `topological_sort() -> list[Node]` — Return nodes in execution order

**Properties:**
- `node_count: int` — Number of nodes
- `edge_count: int` — Number of edges

**Validation:**
- All node IDs must be unique
- All edges must reference existing nodes
- No cycles (DAG constraint)

**Example:**
```python
graph = Graph(
    nodes=[...],
    edges=[...],
    metadata={"name": "my-workflow", "version": "1.0"},
)
execution_order = graph.topological_sort()
```

---

#### `GraphRuntime`

**Location:** `mascarade.node_engine.runtime`

Runtime for executing node graphs.

**Fields:**
- `workers: dict[str, NodeWorker]` — Registered workers by domain
- `max_concurrent: int` — Maximum concurrent node executions (default: 10)
- `execution_timeout_s: float` — Execution timeout in seconds (default: 300)

**Methods:**

##### `register_worker(worker: NodeWorker) -> None`
Register a domain worker with the runtime.

```python
runtime.register_worker(ai_worker)
```

##### `get_worker(domain: str) -> NodeWorker | None`
Get the worker for a specific domain.

```python
worker = runtime.get_worker("ai")
```

##### `async validate_graph(graph: Graph) -> list[str]`
Validate graph before execution. Returns list of error messages (empty if valid).

```python
errors = await runtime.validate_graph(graph)
if errors:
    print("Validation failed:", errors)
```

##### `async execute(graph: Graph, *, initial_inputs: dict | None = None, metadata: dict | None = None) -> GraphExecutionContext`
Execute a graph. Returns execution context with results.

```python
context = await runtime.execute(graph)
if context.status == "completed":
    print("Graph executed successfully")
```

##### `async execute_node(node_type: str, inputs: dict, config: dict | None = None) -> dict[str, Any]`
Execute a single node without a graph (convenience method).

```python
outputs = await runtime.execute_node(
    node_type="ai.llm-inference",
    inputs={"prompt": "Hello!"},
    config={"temperature": 0.7},
)
```

##### `list_workers() -> list[dict[str, Any]]`
List all registered workers with their capabilities.

```python
workers = runtime.list_workers()
for worker in workers:
    print(f"{worker['name']} ({worker['domain']}): {worker['capabilities']}")
```

---

#### `NodeWorker` (Abstract Interface)

**Location:** `mascarade.node_engine.worker`

Abstract interface for domain-specific node workers.

**Attributes:**
- `name: str` — Unique identifier for this worker
- `domain: str` — Domain this worker handles

**Abstract Methods:**

##### `async execute(node_type: str, inputs: dict, config: dict, context: Any) -> dict[str, Any]`
Execute a node and return output port values.

**Raises:**
- `ValueError` if node_type is not supported
- `RuntimeError` if execution fails

##### `async validate(node_type: str, inputs: dict, config: dict) -> list[str]`
Validate node inputs and configuration. Returns list of error messages.

##### `capabilities() -> dict[str, Any]`
Declare worker capabilities for the registry.

**Required keys:**
- `node_types: list[str]` — All node types this worker can execute
- `domain: str` — Domain identifier

**Optional keys:**
- `supports_streaming: bool`
- `supports_cancellation: bool`
- `max_concurrent: int`
- `requires_gpu: bool`
- `requires_hardware: bool`
- `estimated_memory_mb: int`

**Properties:**
- `is_available: bool` — Check if worker is ready for execution

---

#### `GraphExecutionContext`

**Location:** `mascarade.node_engine.runtime`

Execution context for a graph run.

**Fields:**
- `graph_id: str` — Graph identifier
- `status: ExecutionStatus` — Execution status (`pending`, `running`, `completed`, `failed`, `cancelled`)
- `node_results: dict[str, NodeResult]` — Results for each node (keyed by node ID)
- `metadata: dict[str, Any]` — Optional metadata

---

#### `NodeResult`

**Location:** `mascarade.node_engine.runtime`

Result of a single node execution.

**Fields:**
- `node_id: str` — Node identifier
- `status: ExecutionStatus` — Execution status
- `outputs: dict[str, Any]` — Output port values
- `error: str | None` — Error message (if failed)
- `worker_name: str | None` — Worker that executed the node
- `execution_time_ms: float | None` — Execution time in milliseconds

---

## Worker Development

### Creating a New Domain Worker

To add a new domain (e.g., `cad`), implement the `NodeWorker` interface:

```python
from mascarade.node_engine.worker import NodeWorker

class CADWorker(NodeWorker):
    name = "cad-worker"
    domain = "cad"

    async def execute(self, node_type, inputs, config, context):
        if node_type == "cad.sketch":
            return await self._execute_sketch(inputs, config)
        elif node_type == "cad.extrude":
            return await self._execute_extrude(inputs, config)
        else:
            raise ValueError(f"Unknown node type: {node_type}")

    async def validate(self, node_type, inputs, config):
        errors = []
        if node_type == "cad.sketch" and "points" not in inputs:
            errors.append("Missing required input: points")
        return errors

    def capabilities(self):
        return {
            "node_types": ["cad.sketch", "cad.extrude", "cad.fillet"],
            "domain": "cad",
            "supports_streaming": False,
            "max_concurrent": 5,
        }

    async def _execute_sketch(self, inputs, config):
        # Implement sketch logic
        return {"sketch_id": "sketch-123"}

    async def _execute_extrude(self, inputs, config):
        # Implement extrude logic
        return {"model_id": "model-456"}
```

### Registering Domain Types

Workers should register their domain types during initialization:

```python
from mascarade.node_engine.types import DomainType
from mascarade.node_engine.registry import NodeTypeRegistry

registry = NodeTypeRegistry()

sketch_type = DomainType(
    domain="cad",
    name="Sketch",
    schema={
        "type": "object",
        "properties": {
            "points": {"type": "array", "items": {"type": "array"}},
            "closed": {"type": "boolean"},
        },
        "required": ["points"],
    },
)

registry.register(sketch_type, builtin=True)
```

---

## Testing

### Unit Tests

Test individual components in isolation:

```python
import pytest
from mascarade.node_engine.graph import Graph, Node, Edge

def test_node_validation():
    """Test that invalid node IDs are rejected."""
    with pytest.raises(ValueError, match="Node ID cannot be empty"):
        Node(id="", type="ai.llm-inference")

def test_graph_cycle_detection():
    """Test that graphs with cycles are rejected."""
    graph = Graph(
        nodes=[
            Node(id="n1", type="ai.test"),
            Node(id="n2", type="ai.test"),
        ],
        edges=[
            Edge(from_node="n1", from_port="out", to_node="n2", to_port="in"),
            Edge(from_node="n2", from_port="out", to_node="n1", to_port="in"),
        ],
    )
    # Should raise ValueError due to cycle
    with pytest.raises(ValueError, match="cycle"):
        pass
```

### Integration Tests

Test graph execution with real workers:

```python
import pytest
from mascarade.node_engine.runtime import GraphRuntime
from mascarade.node_engine.graph import Graph, Node
from mascarade.node_engine.workers.ai.worker import AIWorker
from mascarade.router import Router
from mascarade.agents.registry import AgentRegistry

@pytest.mark.asyncio
async def test_single_node_execution():
    """Test executing a single LLM inference node."""
    runtime = GraphRuntime()
    ai_worker = AIWorker(router=Router(), registry=AgentRegistry())
    runtime.register_worker(ai_worker)

    graph = Graph(
        nodes=[
            Node(
                id="llm1",
                type="ai.llm-inference",
                inputs={"prompt": "Say hello"},
                config={"temperature": 0.7},
            ),
        ],
    )

    context = await runtime.execute(graph)
    assert context.status == "completed"
    assert "llm1" in context.node_results
    assert context.node_results["llm1"].outputs["response"].content
```

### Running Tests

```bash
cd core
python -m pytest mascarade/node_engine/tests/ -v
```

---

## Further Reading

- **Phase 0 Foundations:** `docs/node-engine/phase-0-foundations.md`
- **Phase 1 AI Worker:** `.auto-claude/specs/029-phase-1-ai-worker/spec.md`
- **Router Documentation:** `core/mascarade/router/README.md`
- **Agent System:** `core/mascarade/agents/README.md`
- **Orchestrator:** `core/mascarade/orchestrator/README.md`

<iframe src="https://github.com/sponsors/electron-rare/card" title="Sponsor electron-rare" height="225" width="600" style="border: 0;"></iframe>
