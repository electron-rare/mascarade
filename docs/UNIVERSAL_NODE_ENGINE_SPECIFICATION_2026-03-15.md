# Universal Node Engine — Architectural Specification

**Document:** SPEC-029 — Universal Node Engine Architecture
**Date:** 2026-03-15
**Version:** 1.0
**Author:** Architecture Team
**Status:** Draft
**Predecessor:** SPEC-025 (Unified Node Engine Architecture — Kill_LIFE)

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Architecture Overview](#2-architecture-overview)
3. [Core Abstractions (Phase 0)](#3-core-abstractions-phase-0)
4. [Domain Workers](#4-domain-workers)
5. [Cross-Domain Integration (Phase 5)](#5-cross-domain-integration-phase-5)
6. [Phasing Strategy](#6-phasing-strategy)
7. [Integration with Mascarade Ecosystem](#7-integration-with-mascarade-ecosystem)
8. [Security Considerations](#8-security-considerations)
9. [Performance Considerations](#9-performance-considerations)
10. [Appendices](#10-appendices)

---

## 1. Executive Summary

### 1.1 Vision

The Universal Node Engine is a multi-domain, graph-based execution architecture that enables composable, visual workflows spanning four primary technical domains: **AI**, **CAD**, **Electronics**, and **Hardware Runtime**. It provides a unified abstraction layer where specialized workers — each operating within their domain expertise — can be connected through typed ports, orchestrated through a graph execution runtime, and composed into cross-domain pipelines that bridge the gap between software intelligence and physical hardware.

The Node Engine is designed to be the computational backbone of the Mascarade ecosystem, replacing ad-hoc agent orchestration patterns with a formal, type-safe, graph-structured execution model. Where the existing Mascarade Orchestrator coordinates agents in sequential, parallel, or pipeline modes, the Universal Node Engine extends this to arbitrary directed acyclic graphs (DAGs) with domain-aware scheduling, cross-domain type adaptation, and federated execution across multiple services and machines.

### 1.2 Scope

This specification defines the complete architecture of the Universal Node Engine across six implementation phases:

- **Phase 0 — Foundations:** Core type system, graph execution runtime, plugin API, node registry, persistence layer
- **Phase 1 — AI Worker:** LLM inference, embeddings, reasoning chains, router/orchestrator integration
- **Phase 2 — CAD Worker:** FreeCAD, KiCad, toolpath generation, mesh operations
- **Phase 3 — Electronics Worker:** SPICE simulation, PCB design rules, firmware, component libraries
- **Phase 4 — Hardware Runtime Worker:** ESP32, MIDI, DMX, serial communication, real-time control
- **Phase 5 — Cross-Domain Integration:** Type adapters, unified orchestration, federated execution

Phases 0 and 1 together constitute the **Minimum Viable Product (MVP)**, which must be validated before expanding into the remaining domains.

### 1.3 Relationship to SPEC-025

SPEC-025 ("Unified Node Engine Architecture — Kill_LIFE") defined a node-based execution engine focused specifically on Kill_LIFE project workflows. It introduced six fixed categories (AI, Hardware, Audio, CAD, Workflow, Automation) and a ReactFlow-based UI for visual graph composition.

SPEC-029 evolves SPEC-025 in the following ways:

| Aspect | SPEC-025 | SPEC-029 (This Document) |
|--------|----------|--------------------------|
| **Scope** | Kill_LIFE workflows only | Universal, multi-domain |
| **Categories** | 6 fixed (AI, Hardware, Audio, CAD, Workflow, Automation) | 4 extensible domains + cross-domain layer |
| **Type System** | Basic primitives (string, number, boolean, array, object) | Rich domain-specific types with coercion rules |
| **Execution** | Client-side, single-graph | Server-side, distributed, multi-graph |
| **Backend** | TypeScript-primary | Python core + TypeScript API (dual-stack) |
| **Resilience** | None | Circuit breakers, retry, dead letter queues |
| **Distribution** | Single machine | Federated via Ray and P2P cluster |
| **Phasing** | Single-phase delivery | 6-phase rollout with MVP gate |

**What SPEC-029 supersedes from SPEC-025:**

- The fixed `NodeCategory` enum is replaced by an extensible domain registry
- The simple `execute()` function signature is replaced by a full `NodeWorker` interface with lifecycle hooks, validation, and capability declarations
- Client-side-only execution is replaced by a server-side graph execution runtime with optional client-side preview
- The flat port type system is replaced by hierarchical, domain-aware port types

**What SPEC-029 preserves from SPEC-025:**

- The `NodePlugin` interface concept (evolved into `NodeWorker`)
- The ReactFlow UI paradigm for graph composition
- The port-based connection model (inputs/outputs)
- Backward compatibility with SPEC-025 node definitions through adapter wrappers

### 1.4 Design Principles

1. **Domain Isolation:** Each worker domain operates independently with its own type system extensions, execution constraints, and failure modes. Domains communicate only through well-defined typed ports.

2. **Progressive Complexity:** Simple workflows (single-domain, linear graphs) require minimal configuration. Complex workflows (cross-domain, branching, federated) are possible but never forced.

3. **Resilience First:** Every execution path includes circuit breakers, retry logic, timeout management, and dead letter handling — patterns already proven in the Mascarade Orchestrator.

4. **Type Safety at Boundaries:** Data flowing between nodes is validated at connection time (static) and execution time (dynamic). Cross-domain type adapters are explicit and auditable.

5. **Infrastructure Awareness:** The engine is designed for deployment on resource-constrained infrastructure (4 vCPU, 6.8 GiB RAM) with graceful degradation when resources are scarce.

---

## 2. Architecture Overview

### 2.1 System Architecture

The Universal Node Engine is composed of five major subsystems:

```
┌─────────────────────────────────────────────────────────────────┐
│                    Universal Node Engine                         │
│                                                                 │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐  │
│  │  Graph Editor │  │  REST/WS API │  │  Headless Executor   │  │
│  │  (ReactFlow)  │  │  (Hono)      │  │  (CLI / Scheduler)   │  │
│  └──────┬───────┘  └──────┬───────┘  └──────────┬───────────┘  │
│         │                 │                      │              │
│         └─────────────────┼──────────────────────┘              │
│                           │                                     │
│                    ┌──────▼───────┐                              │
│                    │   Graph      │                              │
│                    │   Execution  │                              │
│                    │   Runtime    │                              │
│                    └──────┬───────┘                              │
│                           │                                     │
│         ┌─────────┬───────┼───────┬──────────┐                  │
│         │         │       │       │          │                  │
│    ┌────▼───┐ ┌───▼──┐ ┌─▼────┐ ┌▼───────┐ ┌▼──────────┐     │
│    │   AI   │ │ CAD  │ │Elec. │ │Hardware│ │Cross-Domain│     │
│    │ Worker │ │Worker│ │Worker│ │ Worker │ │  Adapters  │     │
│    └────────┘ └──────┘ └──────┘ └────────┘ └────────────┘     │
│                                                                 │
│    ┌────────────────────────────────────────────────────────┐   │
│    │              Shared Infrastructure                      │   │
│    │  Node Registry │ Type System │ Persistence │ Metrics   │   │
│    └────────────────────────────────────────────────────────┘   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 Component Relationships

**Graph Editor (Frontend):** A ReactFlow-based visual editor where users compose workflows by connecting nodes. Runs in the browser as part of the `crazy_life` web surface. Communicates with the backend via REST and WebSocket APIs.

**REST/WS API (Hono):** The TypeScript API layer (`api/`) exposes graph CRUD operations, execution triggers, real-time status streaming, and node catalog endpoints. Proxies execution requests to the Python core.

**Headless Executor:** A CLI and scheduler interface for running graphs without the visual editor. Supports cron-based scheduling, CI/CD integration, and batch processing.

**Graph Execution Runtime:** The core Python engine that manages graph execution. Performs topological sorting, schedules parallel branches, manages execution context, handles errors, and coordinates worker dispatch. Modeled on the existing `Orchestrator` engine with extensions for graph-aware scheduling.

**Domain Workers:** Specialized execution environments for each domain. Each worker implements the `NodeWorker` interface and registers its node types with the Node Registry. Workers may run in-process, in separate containers, or on remote machines via Ray.

**Cross-Domain Adapters:** Type conversion modules that bridge domain-specific port types. An adapter transforms output from one domain into input for another (e.g., AI `LLMResponse` → CAD `DesignParameters`).

**Shared Infrastructure:** The foundational services shared across all domains: the Node Registry (node type discovery and versioning), Type System (port type definitions and coercion rules), Persistence Layer (graph serialization and storage), and Metrics (execution tracing and performance monitoring).

### 2.3 Data Flow Model

Data flows through the Node Engine in a well-defined pipeline:

1. **Graph Definition:** A user (or automated system) creates a graph consisting of nodes and typed connections
2. **Validation:** The graph is statically validated — type compatibility of connections, cycle detection, required inputs satisfied
3. **Compilation:** The graph is compiled into an execution plan — topological sort, parallel branch identification, resource estimation
4. **Scheduling:** The execution plan is dispatched to the appropriate workers, respecting domain constraints and resource availability
5. **Execution:** Workers execute their nodes, producing outputs that flow to downstream nodes through typed ports
6. **Collection:** Results are aggregated, persisted, and surfaced to the user or downstream systems

### 2.4 Execution Modes

The Graph Execution Runtime supports three primary execution modes, extending the Orchestrator's existing patterns:

- **Eager:** Execute nodes as soon as all inputs are available. Maximizes parallelism but requires careful resource management.
- **Lazy:** Execute nodes only when their outputs are requested by a downstream consumer. Minimizes unnecessary computation.
- **Stepped:** Execute one node at a time with user confirmation between steps. Used for debugging and educational workflows.

Additionally, execution can be:

- **Local:** All workers run in the same process or on the same machine
- **Distributed:** Workers are dispatched to remote nodes via Ray or the P2P cluster
- **Hybrid:** Some workers run locally, others remotely, based on resource requirements and domain constraints

---

## 3. Core Abstractions (Phase 0)

Phase 0 establishes the foundational abstractions upon which all domain workers are built. These abstractions must be stable, well-tested, and extensible before any domain-specific work begins.

### 3.1 Universal Node Type System

#### 3.1.1 Base Port Types

The type system defines what data can flow through node connections. Every port has a type, and connections are only valid between compatible types.

**Primitive Types:**

| Type | Description | Serialization |
|------|-------------|---------------|
| `string` | UTF-8 text | JSON string |
| `number` | IEEE 754 float64 | JSON number |
| `integer` | Signed 64-bit integer | JSON number |
| `boolean` | True/False | JSON boolean |
| `binary` | Raw byte buffer | Base64-encoded string |
| `json` | Arbitrary JSON value | JSON value |
| `void` | No data (trigger-only ports) | null |

**Composite Types:**

| Type | Description | Example |
|------|-------------|---------|
| `array<T>` | Ordered collection of type T | `array<number>` |
| `map<K, V>` | Key-value mapping | `map<string, number>` |
| `optional<T>` | Nullable value of type T | `optional<string>` |
| `union<A, B, ...>` | One of several types | `union<string, number>` |
| `stream<T>` | Async iterable of type T | `stream<string>` (for token streaming) |

**Domain-Specific Types:**

Each domain extends the base type system with rich, structured types. These are defined in detail in the respective domain worker sections (Sections 4.1–4.4) but summarized here for reference:

| Domain | Key Types |
|--------|-----------|
| AI | `LLMResponse`, `EmbeddingVector`, `ChatMessage`, `PromptTemplate`, `TokenUsage` |
| CAD | `MeshData`, `Toolpath`, `BOM`, `GCode`, `SchematicData`, `PCBLayout`, `CADDocument` |
| Electronics | `Netlist`, `Schematic`, `Waveform`, `FirmwareBinary`, `ComponentSpec`, `DRCReport` |
| Hardware | `MIDIMessage`, `DMXFrame`, `SerialData`, `GPIOState`, `SensorReading`, `DeviceDescriptor` |

#### 3.1.2 Type Compatibility and Coercion

Connections between ports follow strict type compatibility rules:

**Exact Match:** A port of type `T` connects to a port of type `T`. Always valid.

**Subtype Compatibility:** A port of type `integer` can connect to a port of type `number` (integer is a subtype of number). Defined by the subtype hierarchy:

```
json
├── string
├── number
│   └── integer
├── boolean
├── array<T>
├── map<K, V>
└── binary
```

**Explicit Coercion:** Some type conversions require explicit adapter nodes. For example, `number` → `string` requires a "Format Number" node. Cross-domain types always require explicit adapters.

**Type Coercion Rules (Automatic):**

| From | To | Rule |
|------|----|------|
| `integer` | `number` | Widen to float64 |
| `T` | `optional<T>` | Wrap in optional |
| `T` | `array<T>` | Wrap in single-element array |
| `T` | `json` | Serialize to JSON |
| `string` | `binary` | UTF-8 encode |

**Type Coercion Rules (Prohibited without adapter):**

| From | To | Reason |
|------|----|--------|
| `number` | `string` | Formatting ambiguity (decimal places, locale) |
| `binary` | `string` | Encoding ambiguity (UTF-8, ASCII, Base64) |
| Any domain type | Another domain type | Cross-domain semantics require explicit mapping |

#### 3.1.3 TypeScript Type Definitions

```typescript
/**
 * Base port type identifiers for the Universal Node Engine.
 * Modeled on the port type system from SPEC-025 with extensions
 * for domain-specific types and composite structures.
 */
export type PrimitiveType =
  | "string"
  | "number"
  | "integer"
  | "boolean"
  | "binary"
  | "json"
  | "void";

export type CompositeType =
  | { kind: "array"; element: PortType }
  | { kind: "map"; key: PrimitiveType; value: PortType }
  | { kind: "optional"; inner: PortType }
  | { kind: "union"; variants: PortType[] }
  | { kind: "stream"; element: PortType };

export type DomainType = {
  kind: "domain";
  domain: string; // "ai" | "cad" | "electronics" | "hardware" | string
  name: string;   // e.g., "LLMResponse", "MeshData", "Netlist"
  schema: Record<string, unknown>; // JSON Schema for validation
};

export type PortType = PrimitiveType | CompositeType | DomainType;

export interface NodePort {
  id: string;
  label: string;
  type: PortType;
  required: boolean;
  default?: unknown;
  description?: string;
}

export interface NodeConnection {
  id: string;
  sourceNodeId: string;
  sourcePortId: string;
  targetNodeId: string;
  targetPortId: string;
}
```

#### 3.1.4 Python Type Definitions

```python
"""Universal Node Engine — Core type system.

Defines the port type hierarchy used across all domain workers.
Modeled on the Pydantic validation patterns used throughout Mascarade core.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal, Union

from pydantic import BaseModel, Field


class PrimitiveType(StrEnum):
    STRING = "string"
    NUMBER = "number"
    INTEGER = "integer"
    BOOLEAN = "boolean"
    BINARY = "binary"
    JSON = "json"
    VOID = "void"


class ArrayType(BaseModel):
    kind: Literal["array"] = "array"
    element: "PortType"


class MapType(BaseModel):
    kind: Literal["map"] = "map"
    key: PrimitiveType
    value: "PortType"


class OptionalType(BaseModel):
    kind: Literal["optional"] = "optional"
    inner: "PortType"


class UnionType(BaseModel):
    kind: Literal["union"] = "union"
    variants: list["PortType"]


class StreamType(BaseModel):
    kind: Literal["stream"] = "stream"
    element: "PortType"


class DomainType(BaseModel):
    kind: Literal["domain"] = "domain"
    domain: str
    name: str
    schema_def: dict[str, Any] = Field(default_factory=dict, alias="schema")


PortType = Union[
    PrimitiveType, ArrayType, MapType, OptionalType,
    UnionType, StreamType, DomainType,
]

# Required for Pydantic forward reference resolution
ArrayType.model_rebuild()
MapType.model_rebuild()
OptionalType.model_rebuild()
UnionType.model_rebuild()
StreamType.model_rebuild()


class NodePortDefinition(BaseModel):
    """Definition of a single input or output port on a node."""

    id: str
    label: str
    type: PortType
    required: bool = True
    default: Any = None
    description: str = ""
```

### 3.2 Graph Execution Runtime

The Graph Execution Runtime is the central engine responsible for compiling, validating, scheduling, and executing node graphs. It is modeled on the existing `Orchestrator` engine (`core/mascarade/orchestrator/engine.py`) but extended to handle arbitrary DAGs rather than the fixed sequential/parallel/pipeline modes.

#### 3.2.1 Graph Representation

A graph is a directed acyclic graph (DAG) consisting of nodes and edges. Each node represents a computation unit (backed by a `NodeWorker`), and each edge represents a data flow between an output port and an input port.

```python
"""Graph representation for the Universal Node Engine.

Modeled on the Orchestrator's TaskResult/OrchestrationRun pattern
but extended for arbitrary DAG execution.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class GraphStatus(StrEnum):
    DRAFT = "draft"
    VALIDATED = "validated"
    COMPILED = "compiled"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class GraphNode:
    """A node instance within a graph."""

    id: str
    node_type: str           # References a registered NodeType
    label: str
    config: dict[str, Any] = field(default_factory=dict)
    position: tuple[float, float] = (0.0, 0.0)  # UI position
    domain: str | None = None  # Resolved from NodeType registration


@dataclass
class GraphEdge:
    """A typed connection between two node ports."""

    id: str
    source_node: str
    source_port: str
    target_node: str
    target_port: str


@dataclass
class Graph:
    """A complete node graph ready for execution."""

    id: str
    name: str
    version: int = 1
    status: GraphStatus = GraphStatus.DRAFT
    nodes: list[GraphNode] = field(default_factory=list)
    edges: list[GraphEdge] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
```

#### 3.2.2 Topological Execution

The runtime executes nodes in topological order — a node is eligible for execution only when all its required input ports have received data from upstream nodes. The topological sort algorithm also identifies opportunities for parallelism: independent branches of the graph can execute concurrently.

```python
"""Graph execution engine — topological sort and parallel scheduling.

Extends the Orchestrator's sequential/parallel/pipeline model
to arbitrary DAG execution with domain-aware scheduling.
"""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger("mascarade.node_engine")


class CycleDetectedError(Exception):
    """Raised when the graph contains a cycle."""


class ValidationError(Exception):
    """Raised when the graph fails static validation."""


@dataclass
class ExecutionContext:
    """Runtime context passed to each node during execution."""

    graph_id: str
    run_id: str
    node_id: str
    config: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    cancel_event: asyncio.Event = field(default_factory=asyncio.Event)

    def is_cancelled(self) -> bool:
        return self.cancel_event.is_set()


@dataclass
class NodeResult:
    """Result from a single node execution."""

    node_id: str
    outputs: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    duration_ms: float = 0.0
    worker_name: str = ""


class GraphExecutionEngine:
    """
    Executes a node graph respecting topological ordering and parallel branches.

    Modeled on Orchestrator (core/mascarade/orchestrator/engine.py) with
    extensions for DAG-aware scheduling, domain-specific worker dispatch,
    and cross-domain type adaptation.
    """

    def __init__(self, worker_registry: "WorkerRegistry", node_registry: "NodeTypeRegistry"):
        self._worker_registry = worker_registry
        self._node_registry = node_registry

    def _topological_sort(self, graph: "Graph") -> list[list[str]]:
        """
        Compute execution levels via Kahn's algorithm.

        Returns a list of levels, where each level contains node IDs
        that can execute in parallel. Raises CycleDetectedError if
        the graph contains cycles.
        """
        in_degree: dict[str, int] = defaultdict(int)
        adjacency: dict[str, list[str]] = defaultdict(list)

        for node in graph.nodes:
            in_degree.setdefault(node.id, 0)

        for edge in graph.edges:
            adjacency[edge.source_node].append(edge.target_node)
            in_degree[edge.target_node] += 1

        queue = [nid for nid, deg in in_degree.items() if deg == 0]
        levels: list[list[str]] = []
        processed = 0

        while queue:
            levels.append(list(queue))
            next_queue: list[str] = []
            for nid in queue:
                processed += 1
                for neighbor in adjacency[nid]:
                    in_degree[neighbor] -= 1
                    if in_degree[neighbor] == 0:
                        next_queue.append(neighbor)
            queue = next_queue

        if processed != len(graph.nodes):
            raise CycleDetectedError(
                f"Graph contains a cycle: processed {processed}/{len(graph.nodes)} nodes"
            )

        return levels

    async def execute(self, graph: "Graph", run_id: str) -> list[NodeResult]:
        """
        Execute a graph by processing levels in order, parallelizing within levels.

        This follows the Orchestrator's pattern of supporting parallel execution
        while maintaining proper ordering constraints.
        """
        levels = self._topological_sort(graph)
        all_results: list[NodeResult] = []
        port_data: dict[str, dict[str, Any]] = {}  # node_id -> {port_id: value}

        for level in levels:
            tasks = []
            for node_id in level:
                node = next(n for n in graph.nodes if n.id == node_id)
                inputs = self._collect_inputs(graph, node_id, port_data)
                ctx = ExecutionContext(
                    graph_id=graph.id,
                    run_id=run_id,
                    node_id=node_id,
                    config=node.config,
                )
                tasks.append(self._execute_node(node, inputs, ctx))

            results = await asyncio.gather(*tasks, return_exceptions=True)

            for result in results:
                if isinstance(result, Exception):
                    logger.error("Node execution failed: %s", result)
                    all_results.append(NodeResult(
                        node_id="unknown",
                        error=str(result),
                    ))
                else:
                    all_results.append(result)
                    port_data[result.node_id] = result.outputs

        return all_results

    def _collect_inputs(
        self, graph: "Graph", node_id: str, port_data: dict[str, dict[str, Any]]
    ) -> dict[str, Any]:
        """Gather input values from upstream node outputs."""
        inputs: dict[str, Any] = {}
        for edge in graph.edges:
            if edge.target_node == node_id:
                source_outputs = port_data.get(edge.source_node, {})
                if edge.source_port in source_outputs:
                    inputs[edge.target_port] = source_outputs[edge.source_port]
        return inputs

    async def _execute_node(
        self, node: "GraphNode", inputs: dict[str, Any], ctx: ExecutionContext
    ) -> NodeResult:
        """Execute a single node using its registered worker."""
        import time

        start = time.monotonic()
        node_type = self._node_registry.get(node.node_type)
        worker = self._worker_registry.get(node_type.domain)

        try:
            outputs = await worker.execute(
                node_type=node.node_type,
                inputs=inputs,
                config=node.config,
                context=ctx,
            )
            duration = (time.monotonic() - start) * 1000
            return NodeResult(
                node_id=node.id,
                outputs=outputs,
                duration_ms=duration,
                worker_name=worker.name,
            )
        except Exception as exc:
            duration = (time.monotonic() - start) * 1000
            logger.error("Node %s failed: %s", node.id, exc)
            return NodeResult(
                node_id=node.id,
                error=str(exc),
                duration_ms=duration,
                worker_name=worker.name,
            )
```

#### 3.2.3 Cycle Detection

Cycle detection is performed during the topological sort phase (Kahn's algorithm). If the number of processed nodes is less than the total number of nodes in the graph, a cycle exists. The engine rejects graphs with cycles at validation time, before any execution begins.

In future phases, controlled cycles (feedback loops) may be supported through special "loop" meta-nodes that explicitly bound the iteration count, but this is out of scope for the initial architecture.

#### 3.2.4 Execution Context

The `ExecutionContext` carries runtime information to each node during execution:

- **graph_id / run_id / node_id:** Identifiers for tracing and logging
- **config:** Node-specific configuration (e.g., model name for an LLM node, baud rate for a serial node)
- **metadata:** Graph-level metadata (e.g., user ID, project ID, environment)
- **cancel_event:** An asyncio Event for cooperative cancellation

Workers check `ctx.is_cancelled()` before starting expensive operations, enabling graceful shutdown of long-running graphs.

#### 3.2.5 Error Handling Strategy

The execution engine follows a layered error handling strategy modeled on the Orchestrator's circuit breaker and retry patterns:

1. **Node-Level:** Individual nodes can raise exceptions. The engine catches these, records them in the `NodeResult`, and decides whether to continue (for optional branches) or abort (for required data flow).

2. **Branch-Level:** If a node in a required data path fails, all downstream nodes in that branch are skipped. Independent branches continue executing.

3. **Graph-Level:** If all required terminal nodes have completed successfully (even if some optional branches failed), the graph execution is considered successful.

4. **Retry:** Nodes can be annotated with retry policies (max attempts, backoff strategy). The engine wraps node execution with `RetryExecutor` from the Orchestrator's retry module.

5. **Dead Letter:** Failed node executions are recorded in a dead letter store for post-mortem analysis, following the `DeadLetterStore` pattern from the Orchestrator.

6. **Circuit Breaker:** If a worker consistently fails (e.g., an external API is down), its circuit breaker opens, and all nodes dispatched to that worker are immediately rejected with a clear error. This prevents cascade failures across the graph.

### 3.3 Plugin API (NodeWorker Interface)

The `NodeWorker` is the central abstraction that all domain workers implement. It is modeled directly on the `LLMProvider` abstract base class from `core/mascarade/router/providers/base.py`, sharing the same patterns for abstract methods, capability declarations, and resilience integration.

#### 3.3.1 Python NodeWorker Interface

```python
"""NodeWorker — abstract base class for all domain workers.

Modeled on LLMProvider (core/mascarade/router/providers/base.py)
with the same patterns: abstract methods, capability declarations,
circuit breaker integration, and retry support.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

if TYPE_CHECKING:
    from aiobreaker import CircuitBreaker

logger = logging.getLogger("mascarade.node_engine.workers")

RETRYABLE_EXCEPTIONS = (ConnectionError, TimeoutError, OSError)


def make_worker_retry(*extra_exceptions: type[BaseException]):
    """Create a retry decorator for worker execution, following LLMProvider's make_retry pattern."""
    return retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type(RETRYABLE_EXCEPTIONS + tuple(extra_exceptions)),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )


@dataclass
class NodeCapability:
    """Declares what a worker can do — used for routing and scheduling."""

    node_types: list[str]                   # Node types this worker handles
    domain: str                             # Domain identifier (ai, cad, electronics, hardware)
    supports_streaming: bool = False        # Can produce streaming outputs
    supports_cancellation: bool = True      # Supports cooperative cancellation
    max_concurrent: int = 10               # Maximum concurrent executions
    requires_gpu: bool = False             # Needs GPU resources
    requires_hardware: bool = False        # Needs physical hardware access
    estimated_memory_mb: int = 256         # Estimated memory per execution


class NodeWorker(ABC):
    """
    Abstract base class for all domain workers.

    Follows the LLMProvider pattern:
    - Abstract methods define the contract (execute, validate, capabilities)
    - Circuit breaker integration for resilience
    - Retry support via make_worker_retry decorator
    - Capability declarations for routing decisions

    Circuit Breaker Support:
        The execute() method should be protected by a circuit breaker
        to prevent cascade failures. The circuit breaker is managed by
        the GraphExecutionEngine during dispatch.

        States: CLOSED (normal) → OPEN (failures, reject) → HALF_OPEN (test recovery)
        Default: fail_max=5, timeout=60s
    """

    name: str
    domain: str

    # Circuit breaker instance (set by GraphExecutionEngine)
    circuit_breaker: "CircuitBreaker | None" = None

    @abstractmethod
    async def execute(
        self,
        node_type: str,
        inputs: dict[str, Any],
        config: dict[str, Any],
        context: "ExecutionContext",
    ) -> dict[str, Any]:
        """
        Execute a node of the given type with the provided inputs.

        This is the core method that domain workers must implement.
        Analogous to LLMProvider.send() — the primary execution path.

        Args:
            node_type: The registered node type identifier
            inputs: Input port values (keyed by port ID)
            config: Node-specific configuration
            context: Execution context with run metadata and cancellation

        Returns:
            Output port values (keyed by port ID)

        Raises:
            CircuitBreakerError: If the circuit breaker is open
            ValidationError: If inputs fail validation
            ExecutionError: If the node execution fails
        """
        ...

    @abstractmethod
    async def validate(
        self,
        node_type: str,
        inputs: dict[str, Any],
        config: dict[str, Any],
    ) -> list[str]:
        """
        Validate inputs and configuration before execution.

        Returns a list of validation error messages (empty if valid).
        Called during graph validation and before each node execution.

        Args:
            node_type: The registered node type identifier
            inputs: Input port values to validate
            config: Node-specific configuration to validate

        Returns:
            List of validation error messages (empty = valid)
        """
        ...

    @abstractmethod
    def capabilities(self) -> NodeCapability:
        """
        Declare this worker's capabilities.

        Used by the GraphExecutionEngine for routing and scheduling decisions.
        Analogous to LLMProvider's cost_per_million, speed_rank, quality_rank.
        """
        ...

    def on_init(self, context: "ExecutionContext") -> None:
        """Lifecycle hook: called when a graph execution starts. Optional override."""
        pass

    def on_destroy(self, context: "ExecutionContext") -> None:
        """Lifecycle hook: called when a graph execution completes. Optional override."""
        pass

    @property
    def is_available(self) -> bool:
        """Check if the worker is available (hardware present, service running, etc.)."""
        return True
```

#### 3.3.2 TypeScript NodeWorker Interface

```typescript
/**
 * NodeWorker — TypeScript interface for domain workers.
 *
 * This is the TypeScript counterpart to the Python NodeWorker ABC.
 * Used in the Hono API layer for type-safe worker integration
 * and in the frontend for capability-aware node rendering.
 *
 * Evolves SPEC-025's NodePlugin interface with:
 * - Explicit validation method
 * - Capability declarations
 * - Lifecycle hooks
 * - Circuit breaker awareness
 */

export interface ExecutionContext {
  graphId: string;
  runId: string;
  nodeId: string;
  config: Record<string, unknown>;
  metadata: Record<string, unknown>;
  isCancelled: () => boolean;
}

export interface NodeCapability {
  nodeTypes: string[];
  domain: string;
  supportsStreaming: boolean;
  supportsCancellation: boolean;
  maxConcurrent: number;
  requiresGpu: boolean;
  requiresHardware: boolean;
  estimatedMemoryMb: number;
}

export interface NodeWorker {
  readonly name: string;
  readonly domain: string;

  execute(
    nodeType: string,
    inputs: Record<string, unknown>,
    config: Record<string, unknown>,
    context: ExecutionContext,
  ): Promise<Record<string, unknown>>;

  validate(
    nodeType: string,
    inputs: Record<string, unknown>,
    config: Record<string, unknown>,
  ): Promise<string[]>;

  capabilities(): NodeCapability;

  onInit?(context: ExecutionContext): void | Promise<void>;
  onDestroy?(context: ExecutionContext): void | Promise<void>;

  readonly isAvailable: boolean;
}
```

#### 3.3.3 SPEC-025 Backward Compatibility

To support existing SPEC-025 node definitions, a compatibility adapter wraps old-style `NodePlugin` implementations into the new `NodeWorker` interface:

```typescript
/**
 * Adapter to wrap SPEC-025 NodePlugin into SPEC-029 NodeWorker.
 * Provides backward compatibility during migration.
 */
import type { NodePlugin } from "./spec025-compat";
import type { NodeWorker, ExecutionContext, NodeCapability } from "./node-worker";

export class Spec025Adapter implements NodeWorker {
  readonly name: string;
  readonly domain: string;
  readonly isAvailable = true;

  constructor(private plugin: NodePlugin) {
    this.name = `legacy-${plugin.id}`;
    this.domain = mapCategoryToDomain(plugin.category);
  }

  async execute(
    nodeType: string,
    inputs: Record<string, unknown>,
    config: Record<string, unknown>,
    context: ExecutionContext,
  ): Promise<Record<string, unknown>> {
    return await Promise.resolve(this.plugin.execute(inputs, context));
  }

  async validate(): Promise<string[]> {
    return []; // SPEC-025 plugins have no validation method
  }

  capabilities(): NodeCapability {
    return {
      nodeTypes: [this.plugin.id],
      domain: this.domain,
      supportsStreaming: false,
      supportsCancellation: false,
      maxConcurrent: 5,
      requiresGpu: false,
      requiresHardware: this.domain === "hardware",
      estimatedMemoryMb: 128,
    };
  }
}

function mapCategoryToDomain(category: string): string {
  const mapping: Record<string, string> = {
    AI: "ai",
    Hardware: "hardware",
    Audio: "hardware",     // Audio merged into hardware domain
    CAD: "cad",
    Workflow: "ai",        // Workflow becomes cross-cutting in Phase 0
    Automation: "ai",      // Automation becomes cross-cutting in Phase 0
  };
  return mapping[category] ?? "ai";
}
```

### 3.4 Node Registry

The Node Registry manages the catalog of available node types and their associated workers. It follows the `AgentRegistry` pattern from `core/mascarade/agents/registry.py` — centralized registration with register/get/list/remove semantics, metrics tracking, and JSON persistence.

#### 3.4.1 NodeType Definition

```python
"""Node type definition and registry.

Modeled on AgentRegistry (core/mascarade/agents/registry.py)
with the same patterns: centralized register/get/list/remove,
builtin vs. dynamic distinction, metrics tracking, atomic JSON persistence.
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger("mascarade.node_engine.registry")


@dataclass
class NodeType:
    """Definition of a node type in the registry."""

    id: str                               # Unique identifier (e.g., "ai.llm-inference")
    domain: str                           # Domain this node belongs to
    label: str                            # Human-readable label
    description: str                      # What this node does
    version: str = "1.0.0"               # Semantic version
    inputs: list[dict[str, Any]] = field(default_factory=list)   # Input port definitions
    outputs: list[dict[str, Any]] = field(default_factory=list)  # Output port definitions
    config_schema: dict[str, Any] = field(default_factory=dict)  # JSON Schema for config
    tags: list[str] = field(default_factory=list)
    deprecated: bool = False
    deprecated_by: str | None = None      # ID of replacement node type


DEFAULT_REGISTRY_PATH = Path("data/node_types.json")


class NodeTypeRegistry:
    """
    Centralized registry for node type definitions.

    Follows AgentRegistry patterns:
    - register/get/list/remove semantics
    - builtin vs. dynamic node type distinction
    - JSON persistence with atomic writes (temp + rename)
    - Metrics tracking for node type usage
    """

    def __init__(self, storage_path: Path | None = DEFAULT_REGISTRY_PATH) -> None:
        self._types: dict[str, NodeType] = {}
        self._builtin_ids: set[str] = set()
        self._storage_path = storage_path

    def register(self, node_type: NodeType, *, builtin: bool = False) -> None:
        """Register a node type. Raises ValueError if ID already exists."""
        if node_type.id in self._types and not node_type.deprecated:
            raise ValueError(f"Node type '{node_type.id}' already registered")
        self._types[node_type.id] = node_type
        if builtin:
            self._builtin_ids.add(node_type.id)

    def get(self, type_id: str) -> NodeType:
        """Get a node type by ID. Raises KeyError if not found."""
        if type_id not in self._types:
            raise KeyError(
                f"Node type '{type_id}' not found. Available: {list(self._types.keys())}"
            )
        return self._types[type_id]

    def list(self, domain: str | None = None) -> list[NodeType]:
        """List all node types, optionally filtered by domain."""
        types = list(self._types.values())
        if domain:
            types = [t for t in types if t.domain == domain]
        return types

    def remove(self, type_id: str) -> None:
        """Remove a node type from the registry."""
        self._types.pop(type_id, None)
        self._builtin_ids.discard(type_id)

    def domains(self) -> list[str]:
        """List all registered domains."""
        return sorted(set(t.domain for t in self._types.values()))

    def __contains__(self, type_id: str) -> bool:
        return type_id in self._types

    def __len__(self) -> int:
        return len(self._types)

    def is_builtin(self, type_id: str) -> bool:
        return type_id in self._builtin_ids

    # --- Persistence (follows AgentRegistry.save/load pattern) ---

    def save(self) -> None:
        """Save dynamic node types to JSON with atomic write."""
        if self._storage_path is None:
            return

        self._storage_path.parent.mkdir(parents=True, exist_ok=True)
        types_data = []
        for nt in self._types.values():
            if nt.id in self._builtin_ids:
                continue
            types_data.append({
                "id": nt.id,
                "domain": nt.domain,
                "label": nt.label,
                "description": nt.description,
                "version": nt.version,
                "inputs": nt.inputs,
                "outputs": nt.outputs,
                "config_schema": nt.config_schema,
                "tags": nt.tags,
                "deprecated": nt.deprecated,
                "deprecated_by": nt.deprecated_by,
            })

        # Atomic write: temp file + rename (same pattern as AgentRegistry)
        fd, tmp_path = tempfile.mkstemp(
            dir=str(self._storage_path.parent), suffix=".tmp"
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(types_data, f, indent=2, ensure_ascii=False)
            os.replace(tmp_path, str(self._storage_path))
        except BaseException:
            os.unlink(tmp_path)
            raise

    def load(self) -> None:
        """Load dynamic node types from JSON."""
        if self._storage_path is None or not self._storage_path.exists():
            return
        try:
            raw = json.loads(self._storage_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            logger.error("Failed to load node types from %s: %s", self._storage_path, exc)
            return
        for data in raw:
            try:
                nt = NodeType(**data)
                self.register(nt)
            except (KeyError, TypeError, ValueError) as exc:
                logger.warning("Skipping invalid node type entry: %s", exc)
```

#### 3.4.2 Worker Registry

The `WorkerRegistry` manages the mapping from domains to their `NodeWorker` implementations. It is a simpler registry that maps domain identifiers to worker instances.

```python
"""Worker registry — maps domains to NodeWorker instances.

Simpler than NodeTypeRegistry: one worker per domain.
"""

from __future__ import annotations

import logging

logger = logging.getLogger("mascarade.node_engine.workers")


class WorkerRegistry:
    """Registry of domain workers. One worker per domain."""

    def __init__(self) -> None:
        self._workers: dict[str, "NodeWorker"] = {}

    def register(self, worker: "NodeWorker") -> None:
        """Register a worker for its domain."""
        self._workers[worker.domain] = worker

    def get(self, domain: str) -> "NodeWorker":
        """Get the worker for a domain. Raises KeyError if not found."""
        if domain not in self._workers:
            raise KeyError(
                f"No worker registered for domain '{domain}'. "
                f"Available: {list(self._workers.keys())}"
            )
        return self._workers[domain]

    def list(self) -> list["NodeWorker"]:
        return list(self._workers.values())

    def available_domains(self) -> list[str]:
        return [d for d, w in self._workers.items() if w.is_available]

    def __contains__(self, domain: str) -> bool:
        return domain in self._workers

    def __len__(self) -> int:
        return len(self._workers)
```

### 3.5 Persistence Layer

The persistence layer handles serialization, storage, and versioning of graphs. It follows the atomic write pattern established in `AgentRegistry.save()`.

#### 3.5.1 Graph Serialization Format

Graphs are serialized as JSON documents following a versioned schema. The format is designed for human readability (for debugging), forward compatibility (new fields are ignored by older versions), and efficient diff-based versioning.

```json
{
  "version": "1.0.0",
  "schema": "universal-node-engine-graph-v1",
  "graph": {
    "id": "graph-001",
    "name": "AI-Driven PCB Design",
    "version": 3,
    "status": "validated",
    "metadata": {
      "author": "user-123",
      "created_at": "2026-03-15T10:00:00Z",
      "updated_at": "2026-03-15T14:30:00Z",
      "description": "Generate PCB layout from natural language requirements",
      "tags": ["ai", "cad", "electronics"]
    },
    "nodes": [
      {
        "id": "node-1",
        "node_type": "ai.llm-inference",
        "label": "Generate Requirements",
        "config": {
          "model": "mistral-large-latest",
          "temperature": 0.3,
          "max_tokens": 2048
        },
        "position": [100, 200]
      },
      {
        "id": "node-2",
        "node_type": "cad.kicad-schematic",
        "label": "Create Schematic",
        "config": {},
        "position": [400, 200]
      }
    ],
    "edges": [
      {
        "id": "edge-1",
        "source_node": "node-1",
        "source_port": "response",
        "target_node": "node-2",
        "target_port": "requirements"
      }
    ]
  }
}
```

#### 3.5.2 Versioning Strategy

Graph versions follow a simple incrementing integer model (not semantic versioning, since graphs are data, not APIs). Each save creates a new version. The persistence layer stores:

- The current version (full graph JSON)
- A history of diffs between consecutive versions (using JSON Patch RFC 6902)
- Metadata for each version (author, timestamp, description)

This mirrors the prompt versioning pattern in `AgentRegistry.save()` where prompt changes are tracked with diffs.

#### 3.5.3 Storage Backends

The initial implementation uses file-based JSON storage (consistent with `AgentRegistry`'s `data/agents.json` pattern). Future backends include:

- **PostgreSQL:** For multi-user concurrent access (already available in the Mascarade stack)
- **Redis:** For short-lived execution state and caching (already available)
- **Qdrant:** For graph similarity search and recommendation (already available)

#### 3.5.4 Migration Strategy

When the graph schema evolves, migrations are applied automatically on load:

1. Read the `version` field from the serialized graph
2. Apply migration functions sequentially up to the current schema version
3. Save the migrated graph at the new version

Migration functions are registered in a migration registry (similar to database migration frameworks) and are idempotent.

---

## 4. Domain Workers

### 4.1 AI Worker (Phase 1 — MVP)

The AI Worker integrates the Universal Node Engine with Mascarade's existing LLM infrastructure: the Router (multi-provider dispatch), the Orchestrator (multi-agent orchestration), and the AgentRegistry (agent discovery and management).

#### 4.1.1 Node Types

| Node Type | Description | Inputs | Outputs |
|-----------|-------------|--------|---------|
| `ai.llm-inference` | Send a prompt to an LLM via the Router | `prompt: string`, `system?: string`, `model?: string`, `temperature?: number` | `response: LLMResponse`, `usage: TokenUsage` |
| `ai.llm-stream` | Stream LLM response token by token | Same as `ai.llm-inference` | `stream: stream<string>`, `usage: TokenUsage` |
| `ai.embedding` | Generate embeddings via provider | `text: string`, `model?: string` | `vector: EmbeddingVector` |
| `ai.prompt-template` | Apply variable substitution to a template | `template: string`, `variables: map<string, string>` | `prompt: string` |
| `ai.chain-of-thought` | Multi-step reasoning with intermediate outputs | `question: string`, `steps?: integer` | `reasoning: array<string>`, `answer: string` |
| `ai.agent-dispatch` | Run a registered agent from the AgentRegistry | `agent_name: string`, `message: string` | `response: LLMResponse` |
| `ai.router-select` | Select a provider based on strategy | `strategy: string`, `constraints?: json` | `provider: string`, `model: string` |
| `ai.batch-inference` | Process multiple prompts in parallel | `prompts: array<string>`, `model?: string` | `responses: array<LLMResponse>` |
| `ai.summarize` | Summarize text using an LLM | `text: string`, `max_length?: integer` | `summary: string` |
| `ai.classify` | Classify text into categories | `text: string`, `categories: array<string>` | `category: string`, `confidence: number` |

#### 4.1.2 Domain-Specific Port Types

```python
"""AI Worker domain types.

These types extend the base type system with AI-specific structures.
Modeled on the existing LLMResponse dataclass from providers/base.py.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class LLMResponse:
    """Normalized LLM response — mirrors core/mascarade/router/providers/base.py."""

    content: str
    model: str
    provider: str
    usage: dict[str, int] = field(default_factory=dict)


@dataclass
class TokenUsage:
    """Token consumption metrics."""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    cost_usd: float = 0.0


@dataclass
class EmbeddingVector:
    """Dense vector embedding."""

    values: list[float]
    model: str
    dimensions: int


@dataclass
class ChatMessage:
    """A single message in a conversation."""

    role: str          # "system" | "user" | "assistant"
    content: str
    name: str | None = None


@dataclass
class PromptTemplate:
    """A template with variable placeholders."""

    template: str
    variables: list[str]       # Variable names
    defaults: dict[str, str] = field(default_factory=dict)
```

#### 4.1.3 Integration with Existing Infrastructure

The AI Worker is unique among domain workers because it wraps existing, production-proven Mascarade services rather than introducing new capabilities:

**Router Integration:** The `ai.llm-inference` and `ai.llm-stream` nodes delegate directly to `Router.send()` and `Router.stream()`, respectively. The routing strategy (cheapest, fastest, best, specific) is configurable per node. The Router's existing circuit breaker and retry logic is preserved — the AI Worker does not add another layer of resilience on top.

**Orchestrator Integration:** The `ai.chain-of-thought` node maps to the Orchestrator's `PIPELINE` execution mode, where each reasoning step is a sequential agent call. The `ai.batch-inference` node maps to the `PARALLEL` execution mode.

**AgentRegistry Integration:** The `ai.agent-dispatch` node looks up agents by name in the AgentRegistry and delegates execution. This allows existing agents (including domain-specific agents like `kicad-designer` and `spice-expert`) to be invoked from within node graphs.

```python
"""AI Worker implementation.

Wraps existing Mascarade Router, Orchestrator, and AgentRegistry
into the NodeWorker interface for graph-based execution.
"""

from __future__ import annotations

from typing import Any

from mascarade.agents.registry import AgentRegistry
from mascarade.router import Router
from mascarade.router.router import Strategy


class AIWorker:
    """AI domain worker — wraps Mascarade LLM infrastructure."""

    name = "ai-worker"
    domain = "ai"

    def __init__(self, router: Router, registry: AgentRegistry) -> None:
        self._router = router
        self._registry = registry

    async def execute(
        self,
        node_type: str,
        inputs: dict[str, Any],
        config: dict[str, Any],
        context: Any,
    ) -> dict[str, Any]:
        if node_type == "ai.llm-inference":
            return await self._llm_inference(inputs, config)
        elif node_type == "ai.agent-dispatch":
            return await self._agent_dispatch(inputs, config)
        elif node_type == "ai.prompt-template":
            return self._prompt_template(inputs)
        raise ValueError(f"Unknown AI node type: {node_type}")

    async def _llm_inference(
        self, inputs: dict[str, Any], config: dict[str, Any]
    ) -> dict[str, Any]:
        strategy = Strategy(config.get("strategy", "best"))
        response = await self._router.send(
            messages=[{"role": "user", "content": inputs["prompt"]}],
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

    async def _agent_dispatch(
        self, inputs: dict[str, Any], config: dict[str, Any]
    ) -> dict[str, Any]:
        agent = self._registry.get(inputs["agent_name"])
        response = await agent.run(inputs["message"], router=self._router)
        return {"response": {
            "content": response.content,
            "model": response.model,
            "provider": response.provider,
            "usage": response.usage,
        }}

    def _prompt_template(self, inputs: dict[str, Any]) -> dict[str, Any]:
        template = inputs["template"]
        variables = inputs.get("variables", {})
        result = template
        for key, value in variables.items():
            result = result.replace(f"{{{{{key}}}}}", str(value))
        return {"prompt": result}

    async def validate(self, node_type: str, inputs: dict[str, Any], config: dict[str, Any]) -> list[str]:
        errors = []
        if node_type == "ai.llm-inference" and "prompt" not in inputs:
            errors.append("Missing required input: prompt")
        if node_type == "ai.agent-dispatch":
            if "agent_name" not in inputs:
                errors.append("Missing required input: agent_name")
            elif inputs["agent_name"] not in self._registry:
                errors.append(f"Agent '{inputs['agent_name']}' not found in registry")
        return errors

    def capabilities(self):
        return {
            "node_types": [
                "ai.llm-inference", "ai.llm-stream", "ai.embedding",
                "ai.prompt-template", "ai.chain-of-thought", "ai.agent-dispatch",
                "ai.router-select", "ai.batch-inference", "ai.summarize", "ai.classify",
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
        return True
```

### 4.2 CAD Worker (Phase 2)

The CAD Worker provides graph nodes for 3D modeling (FreeCAD), PCB design (KiCad), toolpath generation, and mesh operations. It wraps the existing `freecad_agent` and `kicad_agent` patterns into composable graph nodes.

#### 4.2.1 Node Types

| Node Type | Description | Key Inputs | Key Outputs |
|-----------|-------------|------------|-------------|
| `cad.freecad-script` | Execute a FreeCAD Python script | `script: string`, `parameters?: json` | `document: CADDocument`, `export?: binary` |
| `cad.freecad-parametric` | Create parametric geometry | `dimensions: json`, `template?: string` | `document: CADDocument`, `mesh: MeshData` |
| `cad.freecad-export` | Export document to various formats | `document: CADDocument`, `format: string` | `file: binary`, `metadata: json` |
| `cad.kicad-schematic` | Generate KiCad schematic | `requirements: string`, `components?: array<string>` | `schematic: SchematicData` |
| `cad.kicad-layout` | Optimize PCB layout | `schematic: SchematicData`, `constraints?: json` | `layout: PCBLayout` |
| `cad.kicad-footprint` | Generate component footprint | `component: string`, `dimensions?: json` | `footprint: json` |
| `cad.kicad-drc` | Run Design Rule Check | `layout: PCBLayout`, `rules?: json` | `report: DRCReport` |
| `cad.kicad-manufacturing` | Generate manufacturing files | `layout: PCBLayout` | `gerber: binary`, `drill: binary`, `bom: BOM` |
| `cad.toolpath-generate` | Generate CNC toolpath | `mesh: MeshData`, `tool_config: json` | `toolpath: Toolpath`, `gcode: GCode` |
| `cad.mesh-simplify` | Simplify a mesh (reduce polygon count) | `mesh: MeshData`, `target_ratio: number` | `mesh: MeshData` |
| `cad.mesh-boolean` | Boolean operations on meshes | `mesh_a: MeshData`, `mesh_b: MeshData`, `operation: string` | `result: MeshData` |
| `cad.stl-import` | Import STL file | `file: binary` | `mesh: MeshData` |
| `cad.stl-export` | Export mesh to STL | `mesh: MeshData` | `file: binary` |

#### 4.2.2 Domain-Specific Port Types

```python
"""CAD Worker domain types.

Domain-specific types for FreeCAD, KiCad, toolpath, and mesh operations.
Modeled on the agent interface patterns from kicad_agent.py and freecad_agent.py.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class MeshData:
    """3D mesh representation."""

    vertices: list[list[float]]     # [[x, y, z], ...]
    faces: list[list[int]]          # [[v0, v1, v2], ...]
    normals: list[list[float]] | None = None
    vertex_count: int = 0
    face_count: int = 0
    format: str = "triangulated"     # triangulated | quad | mixed


@dataclass
class CADDocument:
    """Reference to a CAD document (FreeCAD .FCStd or similar)."""

    document_id: str
    format: str                      # "fcstd" | "step" | "iges"
    path: str | None = None          # File path if persisted
    parameters: dict[str, Any] = field(default_factory=dict)


@dataclass
class Toolpath:
    """CNC toolpath definition."""

    operations: list[dict[str, Any]]
    tool: dict[str, Any]             # Tool definition (diameter, type, etc.)
    feedrate: float
    spindle_speed: float
    total_length_mm: float = 0.0
    estimated_time_s: float = 0.0


@dataclass
class GCode:
    """G-code program."""

    code: str
    line_count: int
    format: str = "grbl"             # grbl | marlin | fanuc


@dataclass
class BOM:
    """Bill of Materials."""

    items: list[dict[str, Any]]      # [{reference, value, footprint, quantity}, ...]
    total_components: int = 0
    total_unique: int = 0


@dataclass
class SchematicData:
    """KiCad schematic representation."""

    schematic_id: str
    components: list[dict[str, Any]]
    nets: list[dict[str, Any]]
    format: str = "kicad_sch"


@dataclass
class PCBLayout:
    """KiCad PCB layout representation."""

    layout_id: str
    layers: list[str]
    components: list[dict[str, Any]]
    traces: list[dict[str, Any]]
    board_dimensions: dict[str, float] = field(default_factory=dict)


@dataclass
class DRCReport:
    """Design Rule Check report."""

    passed: bool
    violations: list[dict[str, Any]]
    warnings: list[dict[str, Any]]
    total_checks: int = 0
```

#### 4.2.3 Integration with Existing Agents

The CAD Worker delegates complex operations to the existing FreeCAD and KiCad agents:

- `cad.freecad-script` invokes `FreeCADAgent.generate_freecad_script()` through the AgentRegistry
- `cad.kicad-schematic` invokes `KiCadAgent.generate_schematic()` through the AgentRegistry
- `cad.kicad-layout` invokes `KiCadAgent.optimize_layout()` through the AgentRegistry
- `cad.kicad-drc` invokes `KiCadAgent.perform_drc()` through the AgentRegistry

This pattern means the CAD Worker acts as a thin node adapter over existing agent capabilities, rather than reimplementing CAD logic. The agents handle the LLM interaction (via the Router), and the worker handles the graph integration (port typing, validation, context propagation).

#### 4.2.4 File I/O Patterns

CAD operations frequently involve large binary files (STL, STEP, Gerber). The Node Engine handles these through:

1. **Binary Port Type:** Large files are passed as `binary` port values (base64-encoded for JSON serialization, raw bytes in-memory)
2. **File Reference Pattern:** For very large files (>10MB), ports carry file references (paths or object store URLs) rather than inline data
3. **Temp Directory Management:** Each graph execution gets a temporary directory for intermediate files, cleaned up after completion

### 4.3 Electronics Worker (Phase 3)

The Electronics Worker provides graph nodes for circuit simulation, PCB design rule checking, firmware compilation, and component library access. It wraps the existing `spice_agent` patterns and introduces new capabilities for firmware and component management.

#### 4.3.1 Node Types

| Node Type | Description | Key Inputs | Key Outputs |
|-----------|-------------|------------|-------------|
| `electronics.spice-netlist` | Generate SPICE netlist from description | `description: string` | `netlist: Netlist` |
| `electronics.spice-simulate` | Run SPICE simulation | `netlist: Netlist`, `analysis: string` | `waveform: Waveform`, `measurements: json` |
| `electronics.spice-debug` | Debug convergence issues | `netlist: Netlist`, `error: string` | `fixed_netlist: Netlist`, `diagnosis: string` |
| `electronics.spice-analyze` | Analyze simulation results | `waveform: Waveform` | `analysis: json`, `summary: string` |
| `electronics.pcb-drc` | Run PCB design rule check | `layout: PCBLayout`, `rules: json` | `report: DRCReport` |
| `electronics.firmware-compile` | Compile firmware for target | `source: string`, `target: string` | `binary: FirmwareBinary` |
| `electronics.firmware-flash-prep` | Prepare firmware for flashing | `binary: FirmwareBinary`, `device: string` | `flash_config: json` |
| `electronics.component-lookup` | Look up component specifications | `query: string` | `components: array<ComponentSpec>` |
| `electronics.component-bom` | Generate BOM from schematic | `schematic: SchematicData` | `bom: BOM` |
| `electronics.netlist-analyze` | Analyze netlist topology | `netlist: Netlist` | `analysis: json` |

#### 4.3.2 Domain-Specific Port Types

```python
"""Electronics Worker domain types.

Domain-specific types for SPICE simulation, firmware, and component management.
Modeled on the spice_agent.py patterns (temperature 0.1 for deterministic output).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Netlist:
    """SPICE netlist representation."""

    content: str                     # Raw SPICE netlist text
    format: str = "ngspice"          # ngspice | ltspice | generic
    components: list[str] = field(default_factory=list)
    analysis_directives: list[str] = field(default_factory=list)


@dataclass
class Waveform:
    """Simulation waveform data."""

    time: list[float]
    signals: dict[str, list[float]]  # signal_name -> values
    unit: str = "V"                  # V | A | W | dB
    analysis_type: str = "transient" # transient | ac | dc


@dataclass
class FirmwareBinary:
    """Compiled firmware binary."""

    data: bytes
    target: str                      # "esp32" | "esp32s3" | "stm32" | ...
    format: str = "elf"              # elf | bin | hex
    size_bytes: int = 0
    build_info: dict[str, Any] = field(default_factory=dict)


@dataclass
class ComponentSpec:
    """Electronic component specification."""

    manufacturer_part: str
    description: str
    package: str
    parameters: dict[str, Any] = field(default_factory=dict)
    datasheet_url: str | None = None
    availability: str = "unknown"
```

#### 4.3.3 SPICE Simulation Execution

The Electronics Worker targets **ngspice** as the primary SPICE simulator, consistent with the existing `spice_agent` configuration. The simulation execution model:

1. **Netlist Generation:** The `spice-netlist` node uses the SPICE agent to generate a complete netlist from a natural language description (temperature=0.1 for deterministic output, matching the agent's configuration)
2. **Simulation Execution:** The `spice-simulate` node invokes ngspice as a subprocess, parses the output, and produces structured `Waveform` data
3. **Result Analysis:** The `spice-analyze` node uses the SPICE agent to interpret simulation results in natural language

The simulation subprocess is sandboxed (no network access, limited file system access, CPU/memory limits) to prevent malicious or runaway netlists from affecting the host system.

#### 4.3.4 Firmware Build Integration

Firmware compilation nodes integrate with ESP-IDF and PlatformIO build systems:

- **ESP-IDF:** For ESP32 targets, uses the `idf.py` build system in a Docker container
- **PlatformIO:** For broader target support, uses PlatformIO CLI in a container

Build artifacts are captured and returned as `FirmwareBinary` port values. The build environment is isolated in a container to prevent toolchain conflicts with the host system.

### 4.4 Hardware Runtime Worker (Phase 4)

The Hardware Runtime Worker manages physical devices: ESP32 microcontrollers, MIDI controllers, DMX lighting fixtures, and serial devices. This domain has unique constraints around real-time scheduling, hardware availability, and safety.

#### 4.4.1 Node Types

| Node Type | Description | Key Inputs | Key Outputs |
|-----------|-------------|------------|-------------|
| `hardware.esp32-discover` | Discover ESP32 devices on network | `network?: string` | `devices: array<DeviceDescriptor>` |
| `hardware.esp32-gpio-write` | Set GPIO pin state | `device: DeviceDescriptor`, `pin: integer`, `state: boolean` | `success: boolean` |
| `hardware.esp32-gpio-read` | Read GPIO pin state | `device: DeviceDescriptor`, `pin: integer` | `state: GPIOState` |
| `hardware.esp32-sensor-read` | Read sensor value | `device: DeviceDescriptor`, `sensor: string` | `reading: SensorReading` |
| `hardware.esp32-ota-update` | Push OTA firmware update | `device: DeviceDescriptor`, `firmware: FirmwareBinary` | `success: boolean`, `status: string` |
| `hardware.midi-input` | Receive MIDI messages | `device?: string`, `channel?: integer` | `message: MIDIMessage` |
| `hardware.midi-output` | Send MIDI message | `message: MIDIMessage`, `device?: string` | `success: boolean` |
| `hardware.midi-cc` | Send MIDI CC message | `channel: integer`, `cc: integer`, `value: integer` | `success: boolean` |
| `hardware.midi-clock` | MIDI clock sync | `bpm: number` | `tick: stream<void>` |
| `hardware.dmx-universe` | Manage DMX universe | `universe: integer` | `frame: DMXFrame` |
| `hardware.dmx-fixture` | Control DMX fixture | `universe: integer`, `address: integer`, `channels: json` | `success: boolean` |
| `hardware.dmx-scene` | Set DMX scene | `scene: json` | `success: boolean` |
| `hardware.serial-open` | Open serial port | `port: string`, `baud_rate: integer` | `connection: json` |
| `hardware.serial-write` | Write to serial port | `connection: json`, `data: SerialData` | `bytes_written: integer` |
| `hardware.serial-read` | Read from serial port | `connection: json`, `timeout?: number` | `data: SerialData` |
| `hardware.pid-controller` | PID control loop | `setpoint: number`, `measurement: number`, `kp: number`, `ki: number`, `kd: number` | `output: number` |

#### 4.4.2 Domain-Specific Port Types

```python
"""Hardware Runtime Worker domain types.

Domain-specific types for ESP32, MIDI, DMX, serial, and real-time control.
Consolidates SPEC-025's Hardware and Audio categories.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class DeviceDescriptor:
    """Description of a discovered hardware device."""

    device_id: str
    device_type: str              # "esp32" | "midi" | "dmx" | "serial"
    name: str
    address: str                  # IP address, serial port, etc.
    protocol: str                 # "http" | "websocket" | "mqtt" | "serial" | "usb"
    capabilities: list[str] = field(default_factory=list)
    firmware_version: str | None = None
    online: bool = True


@dataclass
class GPIOState:
    """GPIO pin state reading."""

    pin: int
    value: bool
    analog_value: float | None = None  # ADC reading if applicable
    timestamp: float = 0.0


@dataclass
class SensorReading:
    """Sensor reading from a hardware device."""

    sensor_type: str              # "temperature" | "humidity" | "pressure" | "light" | ...
    value: float
    unit: str
    timestamp: float = 0.0
    device_id: str = ""


@dataclass
class MIDIMessage:
    """MIDI message."""

    type: str                     # "note_on" | "note_off" | "cc" | "program_change" | "clock"
    channel: int = 0
    note: int | None = None
    velocity: int | None = None
    cc_number: int | None = None
    cc_value: int | None = None
    program: int | None = None
    timestamp: float = 0.0


@dataclass
class DMXFrame:
    """DMX universe frame (512 channels)."""

    universe: int
    channels: list[int]           # 512 channel values (0-255)
    timestamp: float = 0.0


@dataclass
class SerialData:
    """Serial communication data."""

    data: bytes
    encoding: str = "utf-8"
    timestamp: float = 0.0
```

#### 4.4.3 Device Discovery

The Hardware Worker implements a multi-protocol device discovery system:

1. **mDNS/DNS-SD:** For ESP32 devices advertising via mDNS on the local network
2. **USB Enumeration:** For serial and MIDI devices connected via USB
3. **Art-Net Discovery:** For DMX devices on the network
4. **Manual Registration:** For devices that cannot be auto-discovered

Discovery results are cached with a configurable TTL (default: 60 seconds) and refreshed on demand. Devices that go offline are marked as unavailable, and nodes targeting offline devices fail gracefully with descriptive errors.

#### 4.4.4 Protocol Adapters

Each hardware protocol has a dedicated adapter that translates between the Node Engine's typed port system and the hardware protocol:

| Protocol | Adapter | Transport | Latency Target |
|----------|---------|-----------|---------------|
| HTTP REST | `HttpDeviceAdapter` | TCP/IP | < 100ms |
| WebSocket | `WebSocketDeviceAdapter` | TCP/IP | < 50ms |
| MQTT | `MqttDeviceAdapter` | TCP/IP | < 50ms |
| Serial | `SerialDeviceAdapter` | UART/USB | < 10ms |
| USB MIDI | `MidiDeviceAdapter` | USB | < 5ms |
| Art-Net | `ArtNetDeviceAdapter` | UDP | < 10ms |

#### 4.4.5 Real-Time Scheduling Constraints

The Hardware Worker operates under real-time constraints that differ from other domain workers:

**Timing Requirements:**
- MIDI clock: 24 ticks per quarter note at tempo → at 120 BPM, one tick every ~20.8ms
- DMX refresh: 44Hz recommended (22.7ms per frame)
- PID control loops: Typically 10-100Hz (10-100ms per iteration)
- GPIO polling: Configurable, typically 10-1000Hz

**Infrastructure Constraints:**
Given the deployment target (VMware Photon OS, 4 vCPU, 6.8 GiB RAM, swap at 90%), the Hardware Worker must:

1. **Dedicate a CPU core** for real-time tasks when active (configurable via `HARDWARE_WORKER_RT_CORES=1`)
2. **Avoid swap** for real-time buffers (pin critical buffers in RAM)
3. **Limit concurrent real-time nodes** to prevent timing violations (default: 4 real-time nodes per graph)
4. **Implement jitter monitoring** to detect and report timing violations

**Graceful Degradation:**
When hardware is absent (e.g., no MIDI devices connected, no ESP32 on network), the Hardware Worker provides:

1. **Mock Mode:** Simulated hardware responses for testing and development
2. **Record/Replay Mode:** Replay previously recorded hardware interactions
3. **Partial Execution:** Execute non-hardware nodes in the graph, skip hardware nodes with descriptive warnings

#### 4.4.6 Safety Constraints

Hardware control introduces physical safety concerns not present in software-only domains:

1. **Rate Limiting:** GPIO writes are rate-limited to prevent damage from rapid switching
2. **Voltage/Current Guards:** Configuration limits for analog outputs are validated before execution
3. **Emergency Stop:** A graph-level emergency stop mechanism that immediately ceases all hardware output
4. **Watchdog Timer:** If the Node Engine process crashes, hardware devices must return to a safe state (all outputs low/off)
5. **Confirmation Gates:** For potentially dangerous operations (high-power output, firmware flash), the engine supports manual confirmation gates that pause execution until user approval

---

## 5. Cross-Domain Integration (Phase 5)

Phase 5 enables the most powerful capability of the Universal Node Engine: workflows that span multiple domains. An AI model designs a circuit, the Electronics Worker simulates it, the CAD Worker produces the PCB layout, and the Hardware Worker programs the resulting firmware onto a device — all in a single graph.

### 5.1 Cross-Domain Type Adapters

When data flows between domains, type conversion is required. Cross-domain adapters are explicit, auditable conversion functions registered in the Node Registry.

#### 5.1.1 Adapter Registry

```python
"""Cross-domain type adapter registry.

Manages explicit conversions between domain-specific port types.
Adapters are registered as special node types with source and target domains.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Awaitable


@dataclass
class TypeAdapter:
    """A registered cross-domain type conversion."""

    id: str
    source_domain: str
    source_type: str
    target_domain: str
    target_type: str
    description: str
    convert: Callable[[Any], Awaitable[Any] | Any]
    lossy: bool = False          # True if conversion loses information
    requires_context: bool = False  # True if conversion needs ExecutionContext


class AdapterRegistry:
    """Registry of cross-domain type adapters."""

    def __init__(self) -> None:
        self._adapters: dict[tuple[str, str], TypeAdapter] = {}

    def register(self, adapter: TypeAdapter) -> None:
        key = (f"{adapter.source_domain}.{adapter.source_type}",
               f"{adapter.target_domain}.{adapter.target_type}")
        self._adapters[key] = adapter

    def find(self, source_domain: str, source_type: str,
             target_domain: str, target_type: str) -> TypeAdapter | None:
        key = (f"{source_domain}.{source_type}",
               f"{target_domain}.{target_type}")
        return self._adapters.get(key)

    def list_adapters(self, source_domain: str | None = None) -> list[TypeAdapter]:
        adapters = list(self._adapters.values())
        if source_domain:
            adapters = [a for a in adapters if a.source_domain == source_domain]
        return adapters
```

#### 5.1.2 Standard Adapters

| Adapter | From | To | Description |
|---------|------|----|-------------|
| `ai-to-cad-design` | `ai.LLMResponse` | `cad.json` (design parameters) | Extract structured design parameters from AI-generated text |
| `ai-to-electronics-netlist` | `ai.LLMResponse` | `electronics.Netlist` | Parse SPICE netlist from AI-generated text |
| `cad-to-electronics-schematic` | `cad.SchematicData` | `electronics.SchematicData` | Convert KiCad schematic to electronics analysis format |
| `electronics-to-hardware-firmware` | `electronics.FirmwareBinary` | `hardware.FirmwareBinary` | Pass firmware binary to hardware worker for flashing |
| `electronics-to-cad-bom` | `electronics.ComponentSpec` | `cad.BOM` | Convert component specs to BOM entries |
| `hardware-to-ai-sensor` | `hardware.SensorReading` | `ai.string` | Format sensor reading as text for AI analysis |
| `cad-to-ai-mesh-description` | `cad.MeshData` | `ai.string` | Describe mesh geometry in natural language for AI processing |

#### 5.1.3 Adapter Node Pattern

In the graph editor, cross-domain connections automatically insert adapter nodes. When a user connects an AI output to a CAD input, the editor:

1. Looks up the adapter registry for a compatible conversion
2. Inserts an adapter node between the two connected nodes
3. Displays the adapter node with a distinctive visual style (e.g., bridge icon)
4. If no adapter exists, shows an error and prevents the connection

This keeps cross-domain conversions explicit and visible in the graph, avoiding hidden type coercion.

### 5.2 Unified Orchestration Pipeline

Cross-domain graphs are executed by the same `GraphExecutionEngine` as single-domain graphs. The engine's topological sort naturally handles cross-domain dependencies — nodes from different domains can appear in the same execution level if they have no data dependencies.

**Scheduling Considerations:**

1. **Domain Affinity:** Nodes from the same domain are preferentially scheduled on the same worker instance to minimize context switching
2. **Hardware Priority:** Hardware Runtime nodes with real-time constraints are scheduled first within their execution level
3. **Resource Balancing:** The engine tracks resource usage per domain and throttles graph execution if resources are scarce

### 5.3 Federated Graph Execution

For graphs that exceed the capacity of a single machine, the Node Engine supports federated execution across multiple services:

1. **Ray Integration:** Extends the Orchestrator's existing Ray support to dispatch individual nodes or sub-graphs to remote workers
2. **P2P Cluster:** Leverages Mascarade's P2P cluster infrastructure for peer-to-peer node dispatch
3. **Sub-Graph Partitioning:** The engine can automatically partition a graph into sub-graphs based on domain, each executed on the most suitable node in the cluster

The federation model follows the Orchestrator's existing pattern:

```python
# Existing Orchestrator Ray pattern (simplified from engine.py)
async def _try_ray_execution(self, agent_name: str, payload: dict) -> dict:
    """Dispatch to Ray remote worker with circuit breaker."""
    ref = self._ray_send_remote.remote(payload)
    return await asyncio.wait_for(
        asyncio.wrap_future(ref.future()),
        timeout=_RAY_EXEC_TIMEOUT_S,
    )
```

The Node Engine extends this to dispatch individual graph nodes:

```python
# Node Engine federated dispatch (extends Orchestrator pattern)
async def _execute_node_remote(
    self, node: GraphNode, inputs: dict, ctx: ExecutionContext
) -> NodeResult:
    """Dispatch a single node to a remote worker via Ray."""
    payload = {
        "node_type": node.node_type,
        "inputs": inputs,
        "config": node.config,
        "context": {"graph_id": ctx.graph_id, "run_id": ctx.run_id},
    }
    result = await self._try_ray_execution(node.domain, payload)
    return NodeResult(
        node_id=node.id,
        outputs=result["outputs"],
        worker_name=result.get("worker_name", "remote"),
    )
```

### 5.4 Example End-to-End Workflows

#### 5.4.1 AI-Designed PCB

```
[ai.prompt-template] → [ai.llm-inference] → [ai-to-cad-design] →
[cad.kicad-schematic] → [cad.kicad-layout] → [cad.kicad-drc] →
[cad.kicad-manufacturing]
```

**Description:** A natural language description of circuit requirements is processed by an AI model, which generates structured design parameters. These parameters are adapted from the AI domain to the CAD domain, where they drive schematic generation, PCB layout optimization, design rule checking, and manufacturing file generation.

#### 5.4.2 Firmware Development Pipeline

```
[ai.llm-inference] → [ai-to-electronics-netlist] →
[electronics.spice-simulate] → [electronics.spice-analyze] →
[electronics.firmware-compile] → [electronics-to-hardware-firmware] →
[hardware.esp32-ota-update]
```

**Description:** An AI model generates a circuit design as a SPICE netlist. The Electronics Worker simulates the circuit and analyzes the results. If the simulation passes, firmware is compiled for the target ESP32. The firmware binary is adapted to the hardware domain and pushed to the device via OTA update.

#### 5.4.3 Sensor-Driven AI Analysis

```
[hardware.esp32-sensor-read] → [hardware-to-ai-sensor] →
[ai.llm-inference] → [ai.classify] → [hardware.dmx-scene]
```

**Description:** A sensor reading from an ESP32 device is converted to text and analyzed by an AI model. The AI classifies the reading (e.g., "normal", "warning", "critical"), and the classification drives a DMX lighting scene change (e.g., green for normal, red for critical).

---

## 6. Phasing Strategy

### 6.1 Phase Dependency Graph

```
Phase 0: Foundations
    │
    ├──→ Phase 1: AI Worker ─────┐
    │                             │
    │    [MVP GATE] ←────────────┘
    │
    ├──→ Phase 2: CAD Worker ────┐
    │                             │
    ├──→ Phase 3: Electronics ───┼──→ Phase 5: Cross-Domain
    │                             │
    └──→ Phase 4: Hardware ──────┘
```

**Phase 0** is a prerequisite for all other phases. **Phase 1** must be completed alongside Phase 0 to form the MVP. After the MVP gate (Phase 0+1), **Phases 2, 3, and 4** can proceed in parallel. **Phase 5** requires all domain workers to be complete.

### 6.2 Phase Descriptions and Durations

| Phase | Name | Duration | Prerequisites | Key Deliverables |
|-------|------|----------|---------------|-----------------|
| 0 | Foundations | 3-4 weeks | None | Type system, graph runtime, plugin API, registry, persistence |
| 1 | AI Worker | 2-3 weeks | Phase 0 | LLM/embedding/chain nodes, Router/Orchestrator integration |
| **MVP Gate** | Validation | 1 week | Phases 0+1 | End-to-end AI graph execution, performance benchmarks, user feedback |
| 2 | CAD Worker | 3-4 weeks | Phase 0, MVP gate passed | FreeCAD/KiCad nodes, mesh/toolpath operations |
| 3 | Electronics | 2-3 weeks | Phase 0, MVP gate passed | SPICE simulation, firmware compilation, component library |
| 4 | Hardware Runtime | 3-4 weeks | Phase 0, MVP gate passed | ESP32/MIDI/DMX/serial nodes, real-time scheduling |
| 5 | Cross-Domain | 2-3 weeks | Phases 2, 3, 4 | Type adapters, federated execution, end-to-end workflows |

**Total estimated duration:** 16-22 weeks (with Phases 2-4 running in parallel after MVP gate)

### 6.3 MVP Validation Criteria (Phase 0+1)

The MVP gate is the critical decision point. Before investing in domain-specific workers (Phases 2-4), the following criteria must be met:

1. **Graph Execution Works:** A graph with 10+ AI nodes executes successfully with correct data flow
2. **Type System Validates:** Static type checking catches incompatible connections at design time
3. **Performance Baseline:** Single-node execution adds < 5ms overhead compared to direct API calls
4. **Persistence Round-Trip:** Graphs can be saved, loaded, and executed identically
5. **Error Recovery:** Circuit breakers, retries, and dead letter handling work for AI worker nodes
6. **API Surface:** REST endpoints for graph CRUD and execution are functional
7. **User Feedback:** At least one real workflow (e.g., multi-step AI reasoning chain) is validated by a user

### 6.4 Risk Mitigation per Phase

| Phase | Key Risk | Mitigation |
|-------|----------|------------|
| 0 | Type system too rigid/too flexible | Start with primitives only, add domain types incrementally |
| 1 | Router/Orchestrator integration complexity | Wrap existing APIs directly, don't refactor |
| 2 | FreeCAD/KiCad subprocess management | Containerize CAD tools, use timeout-based cleanup |
| 3 | SPICE convergence failures | Leverage existing spice_agent debugging capability |
| 4 | Real-time timing on constrained VM | Mock mode for development, defer real hardware to staging |
| 5 | Cross-domain type explosion | Limit initial adapters to 5-7 most common conversions |

### 6.5 M-009 Dependency

The AI Novel Engine (M-009) is a potentially blocking dependency for Phase 0, as it may define patterns that the Node Engine should follow.

**Option A — Sequential:** Wait for M-009 completion, then start Phase 0. This ensures full alignment but delays the project.

**Option B — Parallel (Recommended):** Start Phase 0 immediately. The Node Engine's core abstractions (type system, graph runtime, plugin API) are independent of M-009's AI-specific patterns. If M-009 introduces patterns that conflict with Phase 0 decisions, they can be reconciled during Phase 1 (AI Worker), which is the natural integration point.

**Recommendation:** Pursue Option B. Phase 0's abstractions are domain-agnostic by design. M-009 will primarily influence Phase 1 (AI Worker node types and integration patterns), not the foundational architecture.

---

## 7. Integration with Mascarade Ecosystem

### 7.1 Service Integration Map

The Universal Node Engine integrates with the existing Mascarade service architecture:

```
┌─────────────────────────────────────────────────────────┐
│                  Mascarade Stack                         │
│                                                         │
│  ┌─────────┐    ┌──────────┐    ┌──────────────────┐   │
│  │  Router  │◄──│   Node   │──►│   Orchestrator   │   │
│  │ (LLM    │    │  Engine   │    │ (Multi-agent)    │   │
│  │ dispatch)│    │ (Graph   │    │                  │   │
│  └────┬────┘    │ execution)│    └────────┬─────────┘   │
│       │         └─────┬────┘             │              │
│       │               │                  │              │
│  ┌────▼────┐    ┌─────▼────┐    ┌────────▼─────────┐   │
│  │Providers│    │  Agent   │    │   Ray / P2P      │   │
│  │(Mistral,│    │ Registry │    │   Cluster        │   │
│  │ OpenAI, │    │          │    │                  │   │
│  │  etc.)  │    │          │    │                  │   │
│  └─────────┘    └──────────┘    └──────────────────┘   │
│                                                         │
│  ┌─────────┐    ┌──────────┐    ┌──────────────────┐   │
│  │  Redis  │    │ Postgres │    │     Qdrant       │   │
│  │ (cache) │    │ (persist)│    │  (embeddings)    │   │
│  └─────────┘    └──────────┘    └──────────────────┘   │
│                                                         │
│  ┌─────────┐    ┌──────────┐    ┌──────────────────┐   │
│  │ Grafana │    │Prometheus│    │    Langfuse      │   │
│  │(dashbrd)│    │(metrics) │    │  (LLM tracing)  │   │
│  └─────────┘    └──────────┘    └──────────────────┘   │
└─────────────────────────────────────────────────────────┘
```

### 7.2 Router Integration

The Node Engine's AI Worker is the primary consumer of the Router. Key integration points:

- **Strategy Selection:** Each AI node can specify a routing strategy (cheapest, fastest, best, specific provider)
- **Provider Cost Tracking:** Token usage from AI nodes is tracked through the Router's cost accounting
- **Circuit Breaker Propagation:** The Router's per-provider circuit breakers are respected by AI Worker nodes. If a provider is circuit-broken, all AI nodes targeting that provider fail fast

### 7.3 Orchestrator Integration

The Node Engine coexists with the Orchestrator — they serve different purposes:

| Aspect | Orchestrator | Node Engine |
|--------|-------------|-------------|
| **Structure** | Linear (sequential/parallel/pipeline) | Arbitrary DAG |
| **Unit of Work** | Agent | Node (finer-grained) |
| **Domain** | LLM agents only | Multi-domain (AI, CAD, Electronics, Hardware) |
| **UI** | API-driven | Visual graph editor |

The Orchestrator can be invoked from within a Node Engine graph (via `ai.agent-dispatch` and chain nodes), and the Node Engine can be triggered from Orchestrator pipelines. They are complementary, not competing.

### 7.4 API Surface

The Node Engine exposes its capabilities through the existing Hono API (`api/`):

**Graph Management:**
- `POST /api/graphs` — Create a new graph
- `GET /api/graphs` — List graphs
- `GET /api/graphs/:id` — Get graph by ID
- `PUT /api/graphs/:id` — Update graph
- `DELETE /api/graphs/:id` — Delete graph
- `POST /api/graphs/:id/validate` — Validate graph (type checking, cycle detection)

**Execution:**
- `POST /api/graphs/:id/execute` — Execute a graph
- `GET /api/graphs/:id/runs` — List execution runs
- `GET /api/graphs/:id/runs/:runId` — Get run status and results
- `DELETE /api/graphs/:id/runs/:runId` — Cancel a running execution
- `WS /api/graphs/:id/runs/:runId/stream` — WebSocket for real-time execution updates

**Node Catalog:**
- `GET /api/node-types` — List available node types
- `GET /api/node-types/:domain` — List node types by domain
- `GET /api/node-types/:id` — Get node type definition
- `GET /api/workers` — List registered workers and their status

### 7.5 Observability

The Node Engine integrates with Mascarade's existing observability stack:

**Tracing:** Each graph execution generates a trace (modeled on the Orchestrator's `AgentTraceBuffer`). Trace events include:
- Graph execution start/complete/fail
- Node execution start/complete/fail (with duration, worker, domain)
- Cross-domain adapter invocations
- Circuit breaker state changes
- Retry attempts

**Metrics (Prometheus):**
- `node_engine_executions_total` — Total graph executions (by status, domain)
- `node_engine_node_duration_seconds` — Node execution duration histogram
- `node_engine_active_runs` — Currently running graph executions
- `node_engine_type_adapter_invocations_total` — Cross-domain adapter usage

**Logging (Structured):**
- All log entries include `run_id`, `graph_id`, `node_id`, and `domain` fields
- Error logs include full context for debugging (inputs, config, stack trace)

**Dashboards (Grafana):**
- Graph execution overview (success rate, average duration, error distribution)
- Per-domain worker health (availability, latency, error rate)
- Resource usage (memory, CPU, active connections per domain)

### 7.6 Ecosystem Repository Roles

The Universal Node Engine spans the 5-repository Mascarade ecosystem:

| Repository | Role in Node Engine |
|------------|---------------------|
| **mascarade** | Host for Node Engine core runtime, worker registration, graph execution engine, Python workers |
| **mascarade-datasets** | Training data for AI Worker fine-tuning; graph template datasets |
| **mascarade-cockpit** | SvelteKit monitoring UI for Node Engine execution observability, worker health dashboards |
| **crazy_life** | Web surface hosting the ReactFlow graph editor UI for visual graph composition |
| **Kill_LIFE** | Embedded AI project template consuming Node Engine workflows; primary use case for cross-domain pipelines |

---

## 8. Security Considerations

### 8.1 Plugin Sandboxing

Third-party or user-defined node types execute in a sandboxed environment:

1. **Process Isolation:** External tool invocations (FreeCAD, ngspice, PlatformIO) run in dedicated Docker containers with restricted capabilities
2. **Resource Limits:** Each container has CPU, memory, and disk quotas (`deploy.resources` in Docker Compose)
3. **Network Isolation:** Sandboxed containers have no network access by default. Network access is granted per node type (e.g., AI nodes need outbound HTTPS for provider APIs)
4. **File System Isolation:** Sandboxed containers mount only a temporary directory. Outputs must be explicitly returned through port values

### 8.2 Hardware Access Control

Hardware Runtime nodes interact with physical devices, which requires careful access control:

1. **Device Allowlist:** Only explicitly allowed devices can be controlled. New devices must be approved before use
2. **Operation Permissions:** Hardware operations are categorized by risk level:
   - **Read-only** (sensor reads, GPIO reads): No approval needed
   - **State-changing** (GPIO writes, MIDI output): Requires graph-level permission
   - **Destructive** (firmware flash, factory reset): Requires explicit user confirmation
3. **Rate Limiting:** Hardware write operations are rate-limited per device to prevent damage
4. **Audit Trail:** All hardware interactions are logged with timestamps, user context, and device identifiers

### 8.3 Graph Validation and Sanitization

Before execution, every graph undergoes validation:

1. **Type Safety:** All port connections are type-checked
2. **Cycle Detection:** Graphs must be acyclic (DAGs)
3. **Resource Estimation:** The engine estimates total resource consumption and rejects graphs that exceed available capacity
4. **Input Sanitization:** Node configurations are validated against their JSON Schema definitions
5. **Privilege Escalation Prevention:** A graph cannot escalate its permissions beyond what the user has been granted
6. **Depth Limiting:** Maximum graph depth (longest path from source to sink) is configurable (default: 50 nodes)
7. **Node Count Limiting:** Maximum number of nodes per graph is configurable (default: 500)

### 8.4 Secret Management

Nodes that require credentials (API keys for LLM providers, device passwords) do not store secrets in the graph definition. Instead:

1. Secrets are referenced by name (e.g., `$SECRET:openai_api_key`)
2. Secret values are resolved at execution time from environment variables or a secret store
3. Secrets are never logged, serialized, or included in graph exports

---

## 9. Performance Considerations

### 9.1 Execution Engine Optimization

The graph execution engine is optimized for throughput and latency:

1. **Parallel Branch Execution:** Independent branches execute concurrently using `asyncio.gather`. The topological sort identifies parallelism opportunities automatically
2. **Node Pooling:** Frequently used node types maintain a pool of pre-initialized workers to avoid setup overhead
3. **Lazy Evaluation:** In lazy execution mode, nodes are only executed when their outputs are consumed, avoiding unnecessary computation
4. **Batch Scheduling:** When multiple graphs are queued, the engine batches nodes of the same type for efficient worker utilization

### 9.2 Caching Strategies

The Node Engine employs multi-level caching:

1. **Node-Level Cache:** Deterministic nodes (same inputs → same outputs) cache their results. Cache keys are derived from input values and configuration hash. Uses Redis for shared cache across workers
2. **Graph-Level Cache:** Complete graph execution results are cached for repeated invocations with identical inputs
3. **Type Adapter Cache:** Cross-domain type conversion results are cached when the conversion is deterministic
4. **Negative Cache:** Failed validations and type checks are cached to avoid re-computation

Cache invalidation follows a TTL-based strategy with manual invalidation support. Default TTLs:
- Node results: 5 minutes
- Graph results: 15 minutes
- Type adapter results: 30 minutes

### 9.3 Resource Management for Hardware Nodes

Hardware Runtime nodes have unique resource management requirements:

1. **Connection Pooling:** Hardware connections (serial ports, MIDI devices, WebSocket connections) are pooled and reused across graph executions
2. **Priority Scheduling:** Real-time hardware nodes get scheduling priority over batch operations
3. **Memory Pinning:** Audio buffers and real-time control data are pinned in RAM (not swappable) to prevent latency spikes
4. **Dedicated Thread Pool:** Hardware I/O operations use a dedicated thread pool separate from the asyncio event loop to avoid blocking

### 9.4 Infrastructure-Aware Scaling

Given the deployment target (4 vCPU, 6.8 GiB RAM, 90% swap usage), the engine implements infrastructure-aware scaling:

1. **Admission Control:** Before executing a graph, the engine checks available resources (CPU, memory, active connections). If resources are insufficient, the graph is queued rather than executed
2. **Memory Pressure Response:** When system memory is low (< 500MB free), the engine:
   - Pauses queued graph executions
   - Evicts cached results (oldest first)
   - Reduces worker pool sizes
3. **CPU Throttling:** If load average exceeds 3.0 (75% of 4 vCPU), the engine limits parallel branch execution to 2 concurrent branches
4. **Swap Avoidance:** The engine monitors swap usage and reduces concurrent activity when swap exceeds 80% to prevent performance degradation

### 9.5 Benchmarking Targets

| Metric | Target | Measurement Method |
|--------|--------|--------------------|
| Node overhead | < 5ms per node | Time(execute_via_engine) - Time(direct_call) |
| Graph compilation | < 50ms for 100 nodes | Time(topological_sort + validation) |
| Type checking | < 1ms per connection | Time(validate_port_compatibility) |
| Graph serialization | < 10ms for 100 nodes | Time(serialize_to_json) |
| Cache hit latency | < 1ms | Time(redis_get) |
| API response (graph CRUD) | < 50ms | Time(full_http_request) |
| WebSocket update latency | < 20ms | Time(event_to_client) |

---

## 10. Appendices

### 10.1 Glossary

| Term | Definition |
|------|------------|
| **Node** | A single computation unit in a graph, backed by a NodeWorker |
| **Port** | A typed input or output on a node |
| **Edge** | A connection between an output port and an input port |
| **Graph** | A directed acyclic graph (DAG) of nodes and edges |
| **Worker** | A domain-specific executor (implements NodeWorker) |
| **Domain** | A technical area (AI, CAD, Electronics, Hardware) |
| **Adapter** | A cross-domain type conversion function |
| **Registry** | A centralized catalog (NodeTypeRegistry, WorkerRegistry) |
| **MVP Gate** | The Phase 0+1 validation checkpoint |

### 10.2 Node Type Naming Convention

Node types follow a hierarchical naming convention:

```
<domain>.<category>-<action>
```

Examples:
- `ai.llm-inference` — AI domain, LLM category, inference action
- `cad.kicad-schematic` — CAD domain, KiCad category, schematic action
- `electronics.spice-simulate` — Electronics domain, SPICE category, simulate action
- `hardware.esp32-gpio-write` — Hardware domain, ESP32 category, GPIO write action

### 10.3 Configuration Reference

Environment variables for the Node Engine:

| Variable | Default | Description |
|----------|---------|-------------|
| `NODE_ENGINE_MAX_GRAPH_DEPTH` | 50 | Maximum graph depth (longest path) |
| `NODE_ENGINE_MAX_NODES` | 500 | Maximum nodes per graph |
| `NODE_ENGINE_PARALLEL_LIMIT` | 10 | Maximum concurrent branch executions |
| `NODE_ENGINE_CACHE_TTL_S` | 300 | Default cache TTL in seconds |
| `NODE_ENGINE_ADMISSION_MIN_MEMORY_MB` | 500 | Minimum free memory for admission control |
| `NODE_ENGINE_ADMISSION_MAX_LOAD` | 3.0 | Maximum load average for admission |
| `HARDWARE_WORKER_RT_CORES` | 1 | CPU cores reserved for real-time tasks |
| `HARDWARE_WORKER_MOCK_MODE` | false | Enable hardware mock mode |
| `NODE_ENGINE_RAY_ENABLED` | false | Enable federated execution via Ray |
| `NODE_ENGINE_STORAGE_PATH` | data/graphs/ | Graph storage directory |
| `NODE_ENGINE_REGISTRY_PATH` | data/node_types.json | Node type registry path |

### 10.4 SPEC-025 Migration Guide

For existing SPEC-025 node definitions:

1. **Category → Domain Mapping:**
   - AI → `ai`
   - Hardware → `hardware`
   - Audio → `hardware` (consolidated)
   - CAD → `cad`
   - Workflow → Cross-cutting (handled by graph structure)
   - Automation → Cross-cutting (handled by graph structure)

2. **NodePlugin → NodeWorker Migration:**
   - Use `Spec025Adapter` wrapper for immediate compatibility
   - Gradually migrate to native `NodeWorker` implementations
   - Add `validate()` and `capabilities()` methods during migration

3. **Port Type Migration:**
   - `"string"`, `"number"`, `"boolean"` → Same (primitive types preserved)
   - `"array"`, `"object"` → `array<json>`, `json` (more explicit)
   - Custom types → Domain-specific types (e.g., `"midi"` → `hardware.MIDIMessage`)

### 10.5 Related Documents

| Document | Relationship |
|----------|-------------|
| SPEC-025 (Unified Node Engine Architecture — Kill_LIFE) | Predecessor specification; SPEC-029 evolves and supersedes |
| M-009 (AI Novel Engine) | Potential dependency for Phase 1 AI Worker patterns |
| `docs/ARCHITECTURE_ETAT_MACHINE_PROJET_2026-03-05.md` | Infrastructure context informing performance constraints |
| `docs/ROADMAP_UPDATED_2026-03-15.md` | Project roadmap incorporating SPEC-029 timeline |

### 10.6 Open Questions

1. **ai-agentic-embedded-base Location:** Is this repository a subdirectory of Mascarade or a separate project? The Node Engine architecture is designed to be portable regardless.

2. **M-009 Timeline:** The exact completion date of M-009 affects Phase 1 planning. The parallel start option (Option B) mitigates this dependency.

3. **Hardware Device Inventory:** The specific ESP32 boards, MIDI controllers, and DMX interfaces available for Phase 4 development need to be inventoried.

4. **FreeCAD/KiCad Versions:** Target versions for the CAD Worker should be confirmed (recommended: FreeCAD 0.21+, KiCad 8.0+).

5. **SPICE Simulator:** ngspice is recommended as the primary target based on the existing `spice_agent` configuration. LTspice support can be added as a secondary target.

---

**END OF SPECIFICATION**

*This document defines the architectural vision for the Universal Node Engine. Implementation proceeds through the phased approach described in Section 6, with Phases 0 and 1 forming the MVP for validation. Detailed implementation specifications for each phase are provided in the companion spec documents (`.auto-claude/specs/029-phase-*/spec.md`).*
