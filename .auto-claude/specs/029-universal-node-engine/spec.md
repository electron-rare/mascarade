# Specification: Universal Node Engine Architecture (SPEC-029)

## Overview

SPEC-029 defines a multi-domain, graph-based execution architecture — the Universal Node Engine — that enables composable, visual workflows spanning four primary technical domains: **AI**, **CAD**, **Electronics**, and **Hardware Runtime**. This initiative evolves the existing Kill_LIFE-focused node engine (SPEC-025) into a universal, extensible platform that serves as the computational backbone of the Mascarade ecosystem. The engine replaces ad-hoc agent orchestration with a formal, type-safe, graph-structured execution model featuring domain-aware scheduling, cross-domain type adaptation, and federated execution across multiple services and machines.

## Workflow Type

**Type**: feature

**Rationale**: This is a greenfield architecture initiative that introduces a new execution engine subsystem spanning Python core and TypeScript API layers. While it evolves patterns from SPEC-025 and leverages existing Mascarade infrastructure (Router, Orchestrator, AgentRegistry), the Universal Node Engine is a net-new system with its own type system, execution runtime, worker model, and persistence layer. The 6-phase rollout ensures incremental delivery with an explicit MVP gate at Phase 0-1.

## Task Scope

### Services Involved
- **core** (primary) - Python backend hosts the Graph Execution Runtime, NodeWorker base class, domain workers, type system, and node registry
- **api** (primary) - TypeScript/Hono service exposes graph CRUD, execution triggers, real-time status streaming, and node catalog REST/WebSocket endpoints
- **crazy_life** (secondary) - Web surface hosts the ReactFlow-based graph editor UI
- **mascarade-cockpit** (secondary) - SvelteKit monitoring UI for Node Engine execution observability
- **docs** (output) - Architectural specification and roadmap documentation

### This Task Will:
- [ ] Define the Universal Node Type System with primitive, composite, and domain-specific port types
- [ ] Define the Graph Execution Runtime with topological sorting, parallel branch scheduling, and execution modes (eager, lazy, stepped)
- [ ] Define the NodeWorker plugin interface with lifecycle hooks, validation, and capability declarations
- [ ] Define the Node Registry with registration, discovery, versioning, and dependency resolution
- [ ] Define 4 domain workers (AI, CAD, Electronics, Hardware Runtime) with domain-specific node types and port types
- [ ] Define cross-domain integration layer with type adapters, unified orchestration, and federated execution
- [ ] Define 6-phase rollout strategy with dependency graph and MVP gate at Phase 0-1

### Out of Scope:
- Code implementation (specifications only — implementation follows in subsequent phase tasks)
- Modification of existing Python or TypeScript source code
- Changes to Docker Compose, CI/CD, or deployment configurations
- UI/UX design for the ReactFlow graph editor (covered in crazy_life specs)

## Service Context

### core (Python/FastAPI) - Primary Host

**Tech Stack:** Python 3.11+, FastAPI, Pydantic, async everywhere, uv package manager

**Key Patterns to Extend:**
- `LLMProvider` abstract base class (`core/mascarade/router/providers/base.py`) — template for `NodeWorker` base interface
- `AgentRegistry` (`core/mascarade/agents/registry.py`) — template for `NodeTypeRegistry` and `WorkerRegistry`
- `Orchestrator` engine (`core/mascarade/orchestrator/engine.py`) — template for `GraphExecutionEngine` with circuit breakers, retry, dead letter queues, Ray distribution

**Existing Domain Agents to Integrate:**
- `kicad_agent.py` — wraps into CAD Worker nodes
- `freecad_agent.py` — wraps into CAD Worker nodes
- `spice_agent.py` — wraps into Electronics Worker nodes

### api (TypeScript/Hono) - API Layer

**Tech Stack:** TypeScript, Hono v4.12.4, Node.js

**Key Patterns to Extend:**
- Route organization (`api/src/routes/`) — new routes for graph CRUD, execution, node catalog
- Kill_LIFE integration (`api/src/lib/killlife.ts`) — workflow execution patterns
- Middleware stack — auth, CORS, rate-limit, error handling

## Files to Create

### Phase 0 — Foundations (Core Abstractions)
| File | Purpose |
|------|---------|
| `core/mascarade/node_engine/__init__.py` | Node engine package |
| `core/mascarade/node_engine/types.py` | Universal type system (primitive, composite, domain types) |
| `core/mascarade/node_engine/worker.py` | `NodeWorker` abstract base class |
| `core/mascarade/node_engine/registry.py` | `NodeTypeRegistry` and `WorkerRegistry` |
| `core/mascarade/node_engine/runtime.py` | `GraphExecutionEngine` (topological sort, scheduling, execution) |
| `core/mascarade/node_engine/graph.py` | Graph, Node, Connection, Port models (Pydantic) |
| `core/mascarade/node_engine/persistence.py` | Graph serialization/deserialization (JSON) |
| `core/mascarade/node_engine/context.py` | `ExecutionContext` with tracing, metrics, cancellation |
| `api/src/routes/node-engine.ts` | REST/WS endpoints for graph operations |

### Phase 1 — AI Worker
| File | Purpose |
|------|---------|
| `core/mascarade/node_engine/workers/ai/__init__.py` | AI worker package |
| `core/mascarade/node_engine/workers/ai/worker.py` | AI domain worker (LLM, embeddings, chains) |
| `core/mascarade/node_engine/workers/ai/types.py` | AI domain port types (`LLMResponse`, `EmbeddingVector`, etc.) |
| `core/mascarade/node_engine/workers/ai/nodes/` | Individual AI node implementations |

### Phase 2 — CAD Worker
| File | Purpose |
|------|---------|
| `core/mascarade/node_engine/workers/cad/worker.py` | CAD domain worker (FreeCAD, KiCad, toolpath) |
| `core/mascarade/node_engine/workers/cad/types.py` | CAD domain port types (`MeshData`, `Toolpath`, `BOM`, etc.) |

### Phase 3 — Electronics Worker
| File | Purpose |
|------|---------|
| `core/mascarade/node_engine/workers/electronics/worker.py` | Electronics domain worker (SPICE, PCB, firmware) |
| `core/mascarade/node_engine/workers/electronics/types.py` | Electronics domain port types (`Netlist`, `Waveform`, etc.) |

### Phase 4 — Hardware Runtime Worker
| File | Purpose |
|------|---------|
| `core/mascarade/node_engine/workers/hardware/worker.py` | Hardware Runtime worker (ESP32, MIDI, DMX, serial) |
| `core/mascarade/node_engine/workers/hardware/types.py` | Hardware domain port types (`MIDIMessage`, `DMXFrame`, etc.) |

### Phase 5 — Cross-Domain Integration
| File | Purpose |
|------|---------|
| `core/mascarade/node_engine/adapters/` | Cross-domain type adapters |
| `core/mascarade/node_engine/federation.py` | Federated graph execution (multi-service, Ray) |

## Files to Reference

| File | Pattern to Reference |
|------|---------------------|
| `core/mascarade/router/providers/base.py` | `LLMProvider` abstract base — template for `NodeWorker` |
| `core/mascarade/agents/registry.py` | `AgentRegistry` — template for `NodeTypeRegistry` |
| `core/mascarade/orchestrator/engine.py` | `Orchestrator` — template for `GraphExecutionEngine` |
| `core/mascarade/agents/kicad_agent.py` | KiCad agent — CAD Worker integration reference |
| `core/mascarade/agents/freecad_agent.py` | FreeCAD agent — CAD Worker integration reference |
| `core/mascarade/agents/spice_agent.py` | SPICE agent — Electronics Worker integration reference |
| `.auto-claude/specs/025-unified-node-engine-architecture/spec.md` | SPEC-025 predecessor — what to evolve vs. supersede |
| `docs/UNIVERSAL_NODE_ENGINE_SPECIFICATION_2026-03-15.md` | Detailed architectural specification document |

## Patterns to Follow

### 1. NodeWorker Base Interface (from LLMProvider pattern)

```python
from abc import ABC, abstractmethod
from pydantic import BaseModel

class NodeWorker(ABC):
    """Base interface for all domain workers in the Universal Node Engine."""
    domain: str           # "ai", "cad", "electronics", "hardware"
    name: str
    version: str
    circuit_breaker: CircuitBreaker | None = None

    @abstractmethod
    async def execute(self, inputs: dict[str, Any], context: ExecutionContext) -> dict[str, Any]: ...

    @abstractmethod
    async def validate(self, inputs: dict[str, Any]) -> ValidationResult: ...

    @abstractmethod
    def capabilities(self) -> WorkerCapabilities: ...

    def on_init(self, context: ExecutionContext) -> None: ...
    def on_destroy(self, context: ExecutionContext) -> None: ...
```

### 2. Registry Pattern (from AgentRegistry)

```python
class NodeTypeRegistry:
    def __init__(self, storage_path: Path = DEFAULT_STORAGE_PATH):
        self._nodes: dict[str, NodeDefinition] = {}
        self._workers: dict[str, NodeWorker] = {}
        self.metrics = MetricsTracker()

    def register(self, node_def: NodeDefinition, worker: NodeWorker, *, builtin: bool = False) -> None: ...
    def get(self, node_type_id: str) -> tuple[NodeDefinition, NodeWorker]: ...
    def list(self, domain: str | None = None) -> list[NodeDefinition]: ...
    def remove(self, node_type_id: str) -> None: ...
```

### 3. Graph Execution (from Orchestrator pattern)

```python
class GraphExecutionEngine:
    registry: NodeTypeRegistry
    retry_executor: RetryExecutor
    dead_letter_store: DeadLetterStore
    circuit_breakers: dict[str, CircuitBreaker]

    async def execute_graph(self, graph: Graph, mode: ExecutionMode, context: ExecutionContext) -> GraphResult: ...
```

## Relationship to SPEC-025

SPEC-025 ("Unified Node Engine Architecture — Kill_LIFE") defined a node-based execution engine focused on Kill_LIFE project workflows with six fixed categories (AI, Hardware, Audio, CAD, Workflow, Automation) and a ReactFlow-based UI.

### What SPEC-029 Supersedes from SPEC-025

- The fixed `NodeCategory` enum — replaced by an extensible domain registry
- The simple `execute()` function signature — replaced by full `NodeWorker` interface with lifecycle hooks, validation, and capability declarations
- Client-side-only execution — replaced by server-side graph execution runtime with optional client-side preview
- The flat port type system — replaced by hierarchical, domain-aware port types with coercion rules
- Single-graph execution model — replaced by multi-graph, distributed execution

### What SPEC-029 Preserves from SPEC-025

- The `NodePlugin` interface concept (evolved into `NodeWorker`)
- The ReactFlow UI paradigm for graph composition
- The port-based connection model (inputs/outputs)
- Backward compatibility with SPEC-025 node definitions through adapter wrappers

### Domain Decomposition: 6 Categories to 4 Domains

| SPEC-025 Category | SPEC-029 Domain | Rationale |
|-------------------|-----------------|-----------|
| AI | AI Worker | Direct evolution with Mascarade Router/Orchestrator integration |
| CAD | CAD Worker | Extended with FreeCAD/KiCad agent integration from core |
| Hardware | Hardware Runtime Worker | Consolidated with Audio category |
| Audio | Hardware Runtime Worker | MIDI, DMX, Tone.js merged into hardware runtime |
| Workflow | Phase 0 Foundations | Becomes cross-cutting graph execution concern |
| Automation | Phase 0 Foundations | Becomes cross-cutting scheduling/trigger concern |

## 6-Phase Rollout Strategy

### Phase Dependency Graph

```
Phase 0 (Foundations)
    |
    v
Phase 1 (AI Worker)
    |
    +--- MVP GATE: validate before proceeding ---+
    |                                              |
    v                                              v
Phase 2 (CAD Worker)                    Phase 3 (Electronics Worker)
    |                                              |
    +-------> Phase 4 (Hardware Runtime) <---------+
                       |
                       v
              Phase 5 (Cross-Domain Integration)
```

### Phase Definitions

| Phase | Name | Duration | Dependencies | Deliverables |
|-------|------|----------|--------------|-------------|
| 0 | Foundations | 3-4 weeks | None | Type system, graph runtime, plugin API, registry, persistence |
| 1 | AI Worker | 2-3 weeks | Phase 0 | LLM nodes, embedding nodes, chain nodes, Router integration |
| **MVP Gate** | **Validation** | **1 week** | **Phase 0 + 1** | **End-to-end AI workflow execution validated** |
| 2 | CAD Worker | 3-4 weeks | Phase 0 | FreeCAD nodes, KiCad nodes, toolpath generation, mesh ops |
| 3 | Electronics Worker | 3-4 weeks | Phase 0 | SPICE simulation, PCB DRC, firmware nodes, component library |
| 4 | Hardware Runtime Worker | 4-5 weeks | Phase 0 (+ Phase 2/3 recommended) | ESP32, MIDI, DMX, serial, real-time control loops |
| 5 | Cross-Domain Integration | 3-4 weeks | Phase 1-4 | Type adapters, unified orchestration, federated execution |

**Note:** Phases 2, 3, and 4 can be developed in parallel after the MVP gate, but Phase 5 requires all domain workers to be complete.

### MVP Gate: Phase 0-1 Validation Criteria

The MVP gate is a hard checkpoint after Phase 0 and Phase 1 completion. The following criteria must be met before proceeding to Phase 2+:

1. **Type System Validated:** All primitive and composite types serialize/deserialize correctly; domain type extension mechanism proven with AI types
2. **Graph Execution Proven:** A multi-node AI workflow executes end-to-end with topological ordering, parallel branch execution, and error handling
3. **Plugin API Stable:** At least 5 AI node types implemented and registered via NodeWorker interface; interface is stable enough for other domains
4. **Registry Operational:** Node discovery, versioning, and dependency resolution work for AI domain nodes
5. **Persistence Round-Trip:** A graph can be saved, loaded, and re-executed with identical results
6. **API Surface Functional:** REST endpoints for graph CRUD and execution work; WebSocket streaming for execution status proven
7. **Resilience Tested:** Circuit breakers, retry logic, and dead letter handling work for failed AI node executions
8. **Performance Baseline:** Single AI workflow (5-10 nodes) executes within acceptable latency on target VM (4 vCPU, 6.8 GiB RAM)

### M-009 Dependency

The AI Novel Engine (M-009) may influence Phase 1 AI Worker design. Two options:

- **Sequential:** Wait for M-009 completion, incorporate learnings into Phase 1 design
- **Parallel (recommended):** Start Phase 0 immediately (no M-009 dependency), begin Phase 1 with current AI patterns, adapt as M-009 matures

## Requirements

### Functional Requirements

1. **Universal Type System** — Primitive, composite, and domain-specific port types with static and runtime validation, automatic coercion for safe conversions, explicit adapters for cross-domain conversions
2. **Graph Execution Runtime** — Topological sort, parallel branch scheduling, three execution modes (eager/lazy/stepped), local/distributed/hybrid deployment, execution context with tracing and cancellation
3. **NodeWorker Plugin Interface** — Abstract base with `execute()`, `validate()`, `capabilities()`, lifecycle hooks (`on_init`, `on_destroy`), circuit breaker integration, async-first design
4. **Node Registry** — Centralized registration with domain filtering, versioning, dependency resolution, JSON persistence with atomic writes
5. **Graph Persistence** — JSON serialization format with schema versioning, migration support, backward compatibility
6. **4 Domain Workers** — AI (LLM, embeddings, chains), CAD (FreeCAD, KiCad, toolpath), Electronics (SPICE, PCB, firmware), Hardware Runtime (ESP32, MIDI, DMX, serial)
7. **Cross-Domain Integration** — Explicit type adapters between domains, unified orchestration pipeline, federated execution via Ray
8. **SPEC-025 Backward Compatibility** — Adapter wrappers allow SPEC-025 `NodePlugin` definitions to run in the new engine

### Non-Functional Requirements

1. **Performance** — Single-domain workflow (10 nodes) executes in <5s on target VM; cross-domain workflow (20 nodes) in <30s
2. **Resilience** — Circuit breakers per worker, retry with exponential backoff, dead letter queue for failed executions
3. **Observability** — Execution tracing (OpenTelemetry compatible), per-node metrics, graph-level dashboards in mascarade-cockpit
4. **Resource Awareness** — Graceful degradation on resource-constrained VM (4 vCPU, 6.8 GiB RAM, 74% disk usage)
5. **Extensibility** — New domains can be added without modifying core engine; new node types register via plugin API

## Success Criteria

### Per-Phase Success Criteria

**Phase 0 — Foundations:**
- [ ] Type system supports all primitive and composite types with validation and coercion
- [ ] Graph execution runtime handles topological sort, parallel branches, and all 3 execution modes
- [ ] NodeWorker interface is implemented and testable with mock workers
- [ ] Node registry supports register/get/list/remove with JSON persistence
- [ ] Graph persistence round-trips correctly (save/load/execute)
- [ ] 90%+ test coverage on core abstractions

**Phase 1 — AI Worker:**
- [ ] LLM inference node executes via Mascarade Router with all supported providers
- [ ] Embedding node generates vectors via configured embedding provider
- [ ] Chain-of-thought node composes multi-step reasoning workflows
- [ ] Prompt template node supports variable substitution and conditional logic
- [ ] AI workflow (5+ nodes) executes end-to-end through graph runtime
- [ ] Integration with existing AgentRegistry for AI agent discovery

**Phase 2 — CAD Worker:**
- [ ] FreeCAD node generates 3D models from parametric descriptions
- [ ] KiCad node generates PCB layouts from schematics
- [ ] Toolpath node generates G-code from mesh data
- [ ] CAD-specific port types (`MeshData`, `Toolpath`, `BOM`) validated

**Phase 3 — Electronics Worker:**
- [ ] SPICE simulation node runs circuit analysis via ngspice
- [ ] PCB DRC node validates design rules
- [ ] Firmware compilation node produces binaries for target MCUs
- [ ] Electronics-specific port types (`Netlist`, `Waveform`, `DRCReport`) validated

**Phase 4 — Hardware Runtime Worker:**
- [ ] ESP32 control node communicates via HTTP/MQTT
- [ ] MIDI I/O node sends/receives MIDI messages
- [ ] DMX node controls lighting fixtures
- [ ] Serial node communicates with arbitrary serial devices
- [ ] Real-time control loop executes within timing constraints
- [ ] Graceful degradation when hardware devices are absent

**Phase 5 — Cross-Domain Integration:**
- [ ] Type adapters bridge AI output to CAD input (e.g., `LLMResponse` -> `DesignParameters`)
- [ ] End-to-end workflow: AI design -> CAD model -> Electronics validation -> Hardware deployment
- [ ] Federated execution distributes workers across multiple machines via Ray
- [ ] Unified orchestration pipeline coordinates cross-domain graphs

### Overall Initiative Success Criteria

- [ ] All 4 domain workers operational with domain-specific node types and port types
- [ ] Cross-domain workflows execute end-to-end
- [ ] SPEC-025 backward compatibility maintained via adapter wrappers
- [ ] Performance targets met on target VM infrastructure
- [ ] Observability integrated with mascarade-cockpit dashboards
- [ ] Documentation complete: architectural spec, phase specs, API reference

## QA Acceptance Criteria

### Architecture Tests
| Test | What to Verify |
|------|----------------|
| Type system completeness | All primitive, composite, and domain types defined with validation rules |
| Execution mode coverage | Eager, lazy, and stepped modes tested with multi-node graphs |
| Plugin interface stability | NodeWorker interface supports all 4 domains without modification |
| Registry functionality | Register/get/list/remove/persist operations work correctly |
| SPEC-025 compatibility | Adapter wraps SPEC-025 NodePlugin and executes in new runtime |

### Integration Tests
| Test | What to Verify |
|------|----------------|
| Router integration | AI Worker nodes dispatch to Mascarade Router for LLM inference |
| Agent integration | Existing KiCad/FreeCAD/SPICE agents wrap into domain worker nodes |
| API surface | REST endpoints serve graph CRUD, execution, and node catalog |
| WebSocket streaming | Execution status streams in real-time to connected clients |
| Persistence | Graphs save/load with full fidelity across engine versions |

### Performance Tests
| Test | What to Verify |
|------|----------------|
| Single-domain latency | 10-node AI workflow completes in <5s |
| Cross-domain latency | 20-node multi-domain workflow completes in <30s |
| Resource usage | Engine operates within VM resource constraints (4 vCPU, 6.8 GiB RAM) |
| Concurrent graphs | Multiple graph executions run without resource starvation |

---

**END OF SPECIFICATION**
