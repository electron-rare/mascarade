# Universal Node Engine

Graph-based execution system for composable domain workflows across AI, CAD, Electronics, MIDI, and Hardware domains.

*Last updated: 2026-03-27*

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Implementation Status](#implementation-status)
4. [Quick Start](#quick-start)
5. [Usage Examples](#usage-examples)
6. [API Reference](#api-reference)
7. [Worker Development](#worker-development)
8. [Testing](#testing)

---

## Overview

The Universal Node Engine provides a type-safe, graph-based execution runtime for composing domain-specific operations into workflows. Unlike monolithic orchestration systems, the Node Engine follows a **domain worker** pattern where each domain (AI, CAD, Electronics, MIDI) implements the `NodeWorker` interface independently.

### Key Features

- **Type-Safe Graphs** — Pydantic-based graph models with DAG validation and port type checking
- **Domain Workers** — Pluggable workers that execute nodes within their domain
- **Async Execution** — Native async/await support for concurrent node execution
- **Topological Ordering** — Automatic dependency resolution and execution ordering
- **Extensible Type System** — Primitive types, domain-specific types, composites (`array<T>`, `map<K,V>`, `stream<T>`)
- **Graph Validation** — Pre-execution validation catches errors before execution begins
- **Versioned Persistence** — JSON serialization with schema versioning and migrations
- **Circuit Breaker / Retry** — Workers support tenacity-based retries and aiobreaker integration
- **Cross-Domain Adapters** — Base framework for type conversion between domains

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
             │ dispatches via
             │
   ┌─────────┴──────────────────────────────┐
   │         GraphExecutionEngine            │
   │  • Topological sort + parallel sched.   │
   │  • Cycle detection                      │
   └─────────┬──────────────────────────────┘
             │
             │ delegates to
             │
   ┌─────────┴──────────────────────────────┐
   │         GraphExecutor                   │
   │  • Worker dispatch per node             │
   │  • Execution records + timing           │
   │  • Status tracking (pending→completed)  │
   └─────────┬──────────────────────────────┘
             │
             │ registers workers
             │
   ┌─────────┼──────────┬────────────┬───────────────┐
   │         │          │            │               │
   v         v          v            v               v
┌────────┐ ┌────────┐ ┌──────────┐ ┌─────────────┐ ┌──────────┐
│AIWorker│ │CADWork.│ │Electron. │ │ MIDIWorker  │ │CrossDom. │
│domain: │ │domain: │ │Worker    │ │ domain:midi │ │ Adapter  │
│  ai    │ │  cad   │ │domain:   │ │             │ │ (base)   │
│        │ │        │ │electron. │ │             │ │          │
└────────┘ └────────┘ └──────────┘ └─────────────┘ └──────────┘
```

### Core Modules

| Module | Status | Purpose |
|--------|--------|---------|
| `types.py` | Done | `PrimitiveType`, `DomainType`, `PortType`, composites (`array`, `map`, `stream`), `PortDirection`, `PortKind` |
| `graph.py` | Done | `Graph`, `GraphNode`, `GraphEdge` with validation, topological sort, dual construction |
| `worker.py` | Done | `NodeWorker` abstract base with lifecycle, `NodeCapability`, `WorkerCapabilities`, circuit breaker, tenacity retry |
| `registry.py` | Done | `NodeTypeRegistry` + `WorkerRegistry`, thread-safe, persistent storage |
| `engine.py` | Done | `GraphExecutionEngine` — topological sort, parallel scheduling, cycle detection |
| `executor.py` | Done | `GraphExecutor` — worker dispatch, execution records, status tracking |
| `runtime.py` | Done | `GraphRuntime` — full execution pipeline, validation, status tracking |
| `persistence.py` | Done | `GraphSerializer` — versioned JSON format (`v1.0.0`), migration support |
| `base.py` | Done | Base abstractions shared across the engine |
| `esp32_client.py` | Done | ESP32 HTTP/WebSocket client for hardware node communication |
| `dmx_controller.py` | Done | DMX bridge controller for lighting/hardware |
| `midi_controller.py` | Done | MIDI controller integration |
| `midi_bridge.js` | Done | Node.js MIDI bridge (JS sidecar) |
| `cross_domain/` | Partial | `CrossDomainAdapter` base class + `AdapterMapping` + `Envelope`. No concrete adapters yet. |
| `domains/electronics/types.py` | Done | Electronics domain types (Netlist, Schematic, Waveform, etc.) |

### Worker Modules

| Worker | Status | Details |
|--------|--------|---------|
| `workers/ai/` | **Production** | `AIWorker` with full Router/Orchestrator integration. Node types: `ai.llm-inference`, `ai.prompt-template`, `ai.agent-dispatch`, `ai.orchestrate-sequential`. Registered types + worker. |
| `workers/cad/worker.py` | **Working** | `CADWorker` with 6 pure-calculation node types (BOM, DRC, footprint lookup, stackup, trace width, thermal via). All have real implementations. |
| `workers/cad/freecad_worker.py` | Partial | `FreeCADWorker` — 4 node types delegating to MCP. Requires FreeCAD runtime. |
| `workers/cad/kicad_worker.py` | Partial | `KiCadWorker` — KiCad integration via MCP. Requires KiCad runtime. |
| `workers/cad/mesh_worker.py` | Partial | `MeshWorker` — mesh operations (STL/OBJ). MCP-dependent. |
| `workers/cad/toolpath_worker.py` | Partial | `ToolpathWorker` — CNC toolpath generation. MCP-dependent. |
| `workers/electronics/worker.py` | **Scaffold** | `ElectronicsWorker` registers domain types and checks external tools (ngspice, kicad-cli, idf.py, pio). Has `capabilities()`, `initialize()`, `shutdown()` but **no `execute()` dispatch** — node classes exist but are not wired to the runtime. |
| `workers/electronics/spice_nodes.py` | Implemented | 4 node classes (NetlistGenerator, Simulate, Analyze, DebugConvergence) with full execute logic. ~1300 lines. Requires ngspice. |
| `workers/electronics/component_nodes.py` | Implemented | 9 node classes (lookup, JLCPCB optimization, BOM/CPL generation, availability check, etc.). ~1600 lines. |
| `workers/electronics/pcb_nodes.py` | Implemented | 4 node classes (DRC, gerber export, etc.). ~640 lines. Requires kicad-cli. |
| `workers/electronics/firmware_nodes.py` | Implemented | 4 node classes (ESP-IDF compile, PlatformIO compile, etc.). ~960 lines. Requires idf.py/pio. |
| `workers/midi/` | **Working** | `MIDIWorker` with 4 node types (note-sequence, cc-map, pattern-generate, transform). All have real execute/validate implementations. |

### Examples

| Example | Status |
|---------|--------|
| `examples/simple_inference.py` | Working |
| `examples/chain_of_thought.py` | Working |
| `examples/agent_orchestration.py` | Working |

---

## Implementation Status

### What Works End-to-End

- **Core engine**: Graph construction, validation, topological sort, execution dispatch
- **AI domain**: Full pipeline — prompt templates, LLM inference, agent dispatch, sequential orchestration
- **CAD calculations**: Pure-math PCB design nodes (trace width, stackup, thermal vias, BOM, DRC, footprint lookup)
- **MIDI domain**: Note sequences, CC mapping, pattern generation, transformations
- **Persistence**: Save/load graphs as versioned JSON
- **Hardware bridges**: ESP32 client, DMX controller, MIDI bridge

### What Exists But Is Not Wired

- **Electronics nodes**: 21 node classes with real execute implementations across SPICE, PCB, firmware, and component domains (~4500 lines of logic). However, `ElectronicsWorker` lacks an `execute()` method, so these nodes cannot be dispatched through `GraphRuntime`. The node logic is real; the glue is missing.
- **CAD sub-workers** (FreeCAD, KiCad, Mesh, Toolpath): Implemented as MCP-delegating workers with their own `execute_node()` methods, but depend on external runtimes (FreeCAD, KiCad) being available. Not integrated into the main `CADWorker` dispatch.

### What Is Scaffolded Only

- **Cross-domain adapters**: Base `CrossDomainAdapter` class and `AdapterMapping` dataclass exist. No concrete adapters (e.g., AI-to-CAD, CAD-to-Electronics) are implemented.

### Phase Completion

| Phase | Status | Notes |
|-------|--------|-------|
| Phase 0 — Foundations | **Complete** | Type system, graph model, registry, engine, executor, runtime, persistence |
| Phase 1 — AI Worker | **Complete** | AIWorker with Router/Orchestrator integration, 4 node types, examples |
| Phase 2 — CAD Worker | **Partial** | Pure-calculation CADWorker complete. FreeCAD/KiCad/Mesh/Toolpath sub-workers exist but require MCP runtimes. |
| Phase 3 — Electronics | **Partial** | Domain types registered. 21 node classes implemented. Worker dispatch not wired. External tool dependencies (ngspice, kicad-cli, idf.py, pio). |
| Phase 4 — MIDI/Hardware | **Partial** | MIDIWorker functional. ESP32 client and DMX controller exist. Hardware integration untested in graph context. |
| Phase 5 — Cross-Domain | **Scaffolded** | Base adapter class only. No concrete adapters. |

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

### Example 2: Multi-Node Template -> LLM Pipeline

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

### Example 4: CAD Trace Width Calculation

```python
from mascarade.node_engine.workers.cad.worker import CADWorker

cad = CADWorker()
result = await cad.execute(
    node_type="cad.trace-width",
    inputs={"current": 2.0, "copper_thickness": 1.0, "temp_rise": 10.0, "layer": "external"},
    config={},
)
print(f"Trace width: {result['width_mm']}mm ({result['width_mil']}mil)")
```

### Example 5: MIDI Pattern Generation

```python
from mascarade.node_engine.workers.midi.worker import MIDIWorker

midi = MIDIWorker()
result = await midi.execute(
    node_type="midi.pattern-generate",
    inputs={"scale": "pentatonic", "root": 60, "steps": 8, "pattern": "ascending"},
    config={},
)
print(f"Generated {result['sequence']['note_count']} notes")
```

### Example 6: Graph Validation Before Execution

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

**Built-in resilience:**
- `make_worker_retry()` — tenacity decorator for retryable exceptions (ConnectionError, TimeoutError, OSError)
- Circuit breaker support via `aiobreaker`

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

#### `GraphSerializer`

**Location:** `mascarade.node_engine.persistence`

Versioned JSON serialization for graphs.

- Schema version: `1.0.0`
- Format: `universal-node-engine-graph-v1`
- Supports migration callbacks for version upgrades
- Atomic file writes via temp-file-then-rename

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

## File Structure

```
node_engine/
├── types.py              # Full type system — PrimitiveType, DomainType, PortType, composites
├── worker.py             # NodeWorker abstract base with lifecycle, capabilities, circuit breaker
├── graph.py              # Graph/GraphNode/GraphEdge, validation, dual construction
├── registry.py           # NodeTypeRegistry + WorkerRegistry, thread-safe, persistent
├── engine.py             # GraphExecutionEngine with topological sort + parallel scheduling
├── executor.py           # GraphExecutor with worker dispatch + execution records
├── runtime.py            # GraphRuntime — full execution pipeline
├── persistence.py        # GraphSerializer — versioned JSON, migrations
├── base.py               # Base abstractions
├── esp32_client.py       # ESP32 HTTP/WebSocket client
├── dmx_controller.py     # DMX bridge controller
├── midi_controller.py    # MIDI controller integration
├── midi_bridge.js        # Node.js MIDI bridge (JS sidecar)
├── cross_domain/
│   ├── adapter.py        # CrossDomainAdapter base class + AdapterMapping
│   └── envelope.py       # Cross-domain message envelope
├── domains/
│   └── electronics/
│       └── types.py      # Electronics domain types (Netlist, Schematic, Waveform, etc.)
├── workers/
│   ├── ai/
│   │   ├── worker.py     # AIWorker — full Router/Orchestrator integration
│   │   ├── types.py      # AI domain types (LLMResponse, etc.)
│   │   └── register.py   # AI type registration
│   ├── cad/
│   │   ├── worker.py     # CADWorker — 6 pure-calculation PCB nodes (working)
│   │   ├── freecad_worker.py  # FreeCAD MCP integration (partial)
│   │   ├── kicad_worker.py    # KiCad MCP integration (partial)
│   │   ├── mesh_worker.py     # Mesh operations (partial)
│   │   ├── toolpath_worker.py # CNC toolpath (partial)
│   │   ├── types.py      # CAD domain types
│   │   └── register.py   # CAD type registration
│   ├── electronics/
│   │   ├── worker.py     # ElectronicsWorker — init/capabilities only, no execute dispatch
│   │   ├── spice_nodes.py     # 4 SPICE nodes with real logic (~1300 lines)
│   │   ├── component_nodes.py # 9 component nodes with real logic (~1600 lines)
│   │   ├── pcb_nodes.py       # 4 PCB nodes with real logic (~640 lines)
│   │   ├── firmware_nodes.py  # 4 firmware nodes with real logic (~960 lines)
│   │   └── register.py   # Electronics type registration
│   └── midi/
│       ├── worker.py     # MIDIWorker — 4 node types, fully working
│       ├── types.py      # MIDI types (MIDINote, MIDISequence, MIDICCMap)
│       └── register.py   # MIDI type registration
└── examples/
    ├── simple_inference.py      # Single LLM inference
    ├── chain_of_thought.py      # Multi-step reasoning
    └── agent_orchestration.py   # Multi-agent workflow
```

---

## Further Reading

- **Phase 0 Foundations:** `docs/node-engine/phase-0-foundations.md`
- **Phase 1 AI Worker:** `.auto-claude/specs/029-phase-1-ai-worker/spec.md`
- **Router Documentation:** `core/mascarade/router/README.md`
- **Agent System:** `core/mascarade/agents/README.md`
- **Orchestrator:** `core/mascarade/orchestrator/README.md`

<iframe src="https://github.com/sponsors/electron-rare/card" title="Sponsor electron-rare" height="225" width="600" style="border: 0;"></iframe>
