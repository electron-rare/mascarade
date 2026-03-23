# Phase 0 — Foundations Specification

**Document:** SPEC-029-P0 — Universal Node Engine Phase 0 Foundations
**Date:** 2026-03-16
**Version:** 1.0
**Status:** Draft
**Parent:** SPEC-029 (Universal Node Engine Architecture)

---

## Table of Contents

1. [Overview](#1-overview)
2. [Universal Node Type System](#2-universal-node-type-system)
3. [Graph Execution Runtime](#3-graph-execution-runtime)
4. [Plugin API (NodeWorker Interface)](#4-plugin-api-nodeworker-interface)
5. [Node Registry](#5-node-registry)
6. [Persistence Layer](#6-persistence-layer)
7. [Acceptance Criteria](#7-acceptance-criteria)

---

## 1. Overview

Phase 0 establishes the foundational abstractions upon which all domain workers (AI, CAD, Electronics, Hardware) are built. No domain-specific code is introduced in this phase — only the core infrastructure that all domains share.

### 1.1 Goals

- Define a universal port type system with primitive, composite, and domain-extensible types
- Implement a graph execution runtime with topological sort, parallel branches, and cycle detection
- Define the `NodeWorker` plugin API as the contract for all domain workers
- Build the `NodeTypeRegistry` and `WorkerRegistry` for node/worker discovery and management
- Establish graph persistence with versioned serialization and migration support

### 1.2 Non-Goals

- Domain-specific workers (deferred to Phases 1–4)
- Cross-domain type adapters (deferred to Phase 5)
- ReactFlow UI integration (separate spec)
- Distributed/federated execution via Ray (Phase 5)

### 1.3 Dependencies

- Python 3.11+ with Pydantic (existing Mascarade core stack)
- TypeScript with Hono (existing API stack)
- Patterns from `LLMProvider` (`core/mascarade/router/providers/base.py`)
- Patterns from `AgentRegistry` (`core/mascarade/agents/registry.py`)
- Patterns from `Orchestrator` (`core/mascarade/orchestrator/engine.py`)

---

## 2. Universal Node Type System

The type system defines what data can flow through node connections. Every port has a type, and connections are only valid between compatible types.

### 2.1 Primitive Types

| Type | Description | Serialization |
|------|-------------|---------------|
| `string` | UTF-8 text | JSON string |
| `number` | IEEE 754 float64 | JSON number |
| `integer` | Signed 64-bit integer | JSON number |
| `boolean` | True/False | JSON boolean |
| `binary` | Raw byte buffer | Base64-encoded string |
| `json` | Arbitrary JSON value | JSON value |
| `void` | No data (trigger-only ports) | null |

### 2.2 Composite Types

| Type | Description | Example |
|------|-------------|---------|
| `array<T>` | Ordered collection of type T | `array<number>` |
| `map<K, V>` | Key-value mapping | `map<string, number>` |
| `optional<T>` | Nullable value of type T | `optional<string>` |
| `union<A, B, ...>` | One of several types | `union<string, number>` |
| `stream<T>` | Async iterable of type T | `stream<string>` |

### 2.3 Domain-Specific Type Extensions

Each domain extends the base type system with structured types registered at runtime. Domain types are declared as `DomainType` with a JSON Schema for validation:

| Domain | Key Types |
|--------|-----------|
| AI | `LLMResponse`, `EmbeddingVector`, `ChatMessage`, `PromptTemplate`, `TokenUsage` |
| CAD | `MeshData`, `Toolpath`, `BOM`, `GCode`, `CADDocument` |
| Electronics | `Netlist`, `Schematic`, `Waveform`, `FirmwareBinary`, `ComponentSpec` |
| Hardware | `MIDIMessage`, `DMXFrame`, `SerialData`, `GPIOState`, `SensorReading` |

Domain types are registered by workers during initialization and are not hard-coded into the core type system.

### 2.4 Type Coercion Rules

**Automatic (implicit) coercion:**

| From | To | Rule |
|------|----|------|
| `integer` | `number` | Widen to float64 |
| `T` | `optional<T>` | Wrap in optional |
| `T` | `array<T>` | Wrap in single-element array |
| `T` | `json` | Serialize to JSON |
| `string` | `binary` | UTF-8 encode |

**Prohibited without explicit adapter node:**

| From | To | Reason |
|------|----|--------|
| `number` | `string` | Formatting ambiguity (decimal places, locale) |
| `binary` | `string` | Encoding ambiguity (UTF-8, ASCII, Base64) |
| Any domain type | Another domain type | Cross-domain semantics require explicit mapping |

### 2.5 Subtype Hierarchy

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

### 2.6 Python Type Definitions

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

### 2.7 TypeScript Type Definitions

```typescript
/**
 * Base port type identifiers for the Universal Node Engine.
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
  domain: string;
  name: string;
  schema: Record<string, unknown>;
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

---

## 3. Graph Execution Runtime

The Graph Execution Runtime compiles, validates, schedules, and executes node graphs. It extends the `Orchestrator` engine pattern (`core/mascarade/orchestrator/engine.py`) from fixed sequential/parallel/pipeline modes to arbitrary DAG execution.

### 3.1 Graph Representation

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
    node_type: str
    label: str
    config: dict[str, Any] = field(default_factory=dict)
    position: tuple[float, float] = (0.0, 0.0)
    domain: str | None = None


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

### 3.2 Topological Sort and Parallel Scheduling

The runtime uses Kahn's algorithm for topological sort, producing execution levels where each level contains nodes that can run in parallel. This extends the Orchestrator's `PARALLEL` execution mode to arbitrary graph structures.

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
        """
        levels = self._topological_sort(graph)
        all_results: list[NodeResult] = []
        port_data: dict[str, dict[str, Any]] = {}

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
                    all_results.append(NodeResult(node_id="unknown", error=str(result)))
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

### 3.3 Cycle Detection

Cycle detection is integrated into the topological sort via Kahn's algorithm. If `processed < len(graph.nodes)`, a cycle exists and `CycleDetectedError` is raised. Graphs with cycles are rejected at validation time, before any execution begins.

### 3.4 Execution Context

The `ExecutionContext` carries runtime metadata to each node:

- **graph_id / run_id / node_id** — identifiers for tracing and logging
- **config** — node-specific configuration (model name, temperature, baud rate, etc.)
- **metadata** — graph-level metadata (user ID, project, environment)
- **cancel_event** — asyncio Event for cooperative cancellation

Workers check `ctx.is_cancelled()` before expensive operations for graceful shutdown.

### 3.5 Error Handling Strategy

Layered error handling modeled on the Orchestrator's circuit breaker and retry patterns:

1. **Node-Level:** Exceptions are caught and recorded in `NodeResult`. Engine decides to continue (optional branches) or abort (required data flow).
2. **Branch-Level:** If a required-path node fails, downstream nodes in that branch are skipped. Independent branches continue.
3. **Graph-Level:** Success if all required terminal nodes complete, even with optional branch failures.
4. **Retry:** Nodes can have retry policies (max attempts, backoff). Engine wraps execution with `RetryExecutor` from the Orchestrator's retry module.
5. **Dead Letter:** Failed executions are recorded in `DeadLetterStore` for post-mortem analysis.
6. **Circuit Breaker:** Workers with consistent failures have their circuit breaker opened, immediately rejecting dispatches to prevent cascading failures.

### 3.6 Execution Modes

| Mode | Description |
|------|-------------|
| **Eager** | Execute nodes as soon as inputs are available. Maximizes parallelism. |
| **Lazy** | Execute only when outputs are requested by downstream consumers. |
| **Stepped** | One node at a time with user confirmation between steps (debugging). |

---

## 4. Plugin API (NodeWorker Interface)

The `NodeWorker` is the central abstraction all domain workers implement. It is modeled directly on `LLMProvider` (`core/mascarade/router/providers/base.py`), sharing patterns for abstract methods, capability declarations, and resilience integration.

### 4.1 Python NodeWorker Abstract Base Class

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

    node_types: list[str]
    domain: str
    supports_streaming: bool = False
    supports_cancellation: bool = True
    max_concurrent: int = 10
    requires_gpu: bool = False
    requires_hardware: bool = False
    estimated_memory_mb: int = 256


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

        States: CLOSED (normal) -> OPEN (failures, reject) -> HALF_OPEN (test recovery)
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

### 4.2 TypeScript NodeWorker Interface

```typescript
/**
 * NodeWorker — TypeScript interface for domain workers.
 *
 * TypeScript counterpart to the Python NodeWorker ABC.
 * Used in the Hono API layer for type-safe worker integration
 * and in the frontend for capability-aware node rendering.
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

### 4.3 Lifecycle Hooks

| Hook | When Called | Use Case |
|------|-----------|----------|
| `on_init` / `onInit` | Graph execution starts | Initialize connections, load models, allocate resources |
| `on_destroy` / `onDestroy` | Graph execution ends | Release resources, close connections, flush buffers |

### 4.4 SPEC-025 Backward Compatibility

A `Spec025Adapter` wraps legacy `NodePlugin` implementations into the `NodeWorker` interface:

```typescript
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
    return [];
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
    Audio: "hardware",
    CAD: "cad",
    Workflow: "ai",
    Automation: "ai",
  };
  return mapping[category] ?? "ai";
}
```

---

## 5. Node Registry

The Node Registry manages node type definitions and worker instances. It follows the `AgentRegistry` pattern from `core/mascarade/agents/registry.py` — centralized registration with register/get/list/remove semantics, builtin vs. dynamic distinction, metrics tracking, and atomic JSON persistence.

### 5.1 NodeTypeRegistry

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
    inputs: list[dict[str, Any]] = field(default_factory=list)
    outputs: list[dict[str, Any]] = field(default_factory=list)
    config_schema: dict[str, Any] = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)
    deprecated: bool = False
    deprecated_by: str | None = None


DEFAULT_REGISTRY_PATH = Path("data/node_types.json")


class NodeTypeRegistry:
    """
    Centralized registry for node type definitions.

    Follows AgentRegistry patterns:
    - register/get/list/remove semantics
    - builtin vs. dynamic node type distinction
    - JSON persistence with atomic writes (temp + rename)
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

### 5.2 WorkerRegistry

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

### 5.3 Discovery and Versioning

- **Discovery:** Node types are discovered through registry queries filtered by domain, tags, or capability flags. The API layer exposes a `/nodes/catalog` endpoint for frontend node palette population.
- **Versioning:** Node types use semantic versioning (`1.0.0`). When a node type is deprecated, `deprecated=True` and `deprecated_by` points to its replacement. Graphs referencing deprecated types emit warnings during validation.
- **Dependency Resolution:** Node types declare their domain, and the engine resolves the appropriate worker at execution time. Cross-domain dependencies are explicit through graph edges, not implicit worker dependencies.

---

## 6. Persistence Layer

### 6.1 Graph Serialization Format

Graphs are serialized as versioned JSON documents designed for human readability, forward compatibility (unknown fields are ignored), and efficient diff-based versioning.

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
        "config": { "model": "mistral-large-latest", "temperature": 0.3 },
        "position": [100, 200]
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

### 6.2 Versioning Strategy

Graph versions use a simple incrementing integer (not semver — graphs are data, not APIs).

**Phase 0 Implementation:**
- **Current version:** Full graph JSON with atomic writes (temp + rename)
- **Schema versioning:** Via `MigrationRegistry` for schema evolution

**Phase 1+ Implementation (PostgreSQL):**
- **Version history:** Diffs between consecutive versions using JSON Patch (RFC 6902)
- **Version metadata:** Author, timestamp, description per version

The file-based persistence in Phase 0 focuses on reliable single-version storage. Version history tracking with JSON Patch diffs is better suited for the PostgreSQL backend (Phase 1+), which provides:
- Efficient storage of version chains
- ACID guarantees for version transitions
- Query capabilities for version history
- Concurrent multi-user version management

This follows the same pattern as `AgentRegistry.save()` which defers advanced persistence features to database backends.

### 6.3 Storage Backends

| Backend | Use Case | Phase |
|---------|----------|-------|
| **File-based JSON** | Initial implementation, consistent with `AgentRegistry`'s `data/agents.json` | Phase 0 |
| **PostgreSQL** | Multi-user concurrent access (already in Mascarade stack) | Phase 1+ |
| **Redis** | Short-lived execution state and caching (already available) | Phase 1+ |
| **Qdrant** | Graph similarity search and recommendation (already available) | Phase 5 |

### 6.4 Migration Strategy

When the graph schema evolves, migrations are applied automatically on load:

1. Read the `version` field from the serialized graph
2. Apply migration functions sequentially up to the current schema version
3. Save the migrated graph at the new version

Migration functions are registered in a migration registry and are idempotent. This follows standard database migration patterns.

```python
"""Graph schema migration framework."""

from __future__ import annotations

from typing import Any, Callable

MigrationFn = Callable[[dict[str, Any]], dict[str, Any]]


class MigrationRegistry:
    """Registry of schema migration functions."""

    def __init__(self) -> None:
        self._migrations: dict[str, MigrationFn] = {}

    def register(self, from_version: str, to_version: str, fn: MigrationFn) -> None:
        self._migrations[f"{from_version}->{to_version}"] = fn

    def migrate(self, data: dict[str, Any], target_version: str) -> dict[str, Any]:
        current = data.get("version", "1.0.0")
        while current != target_version:
            key = f"{current}->{target_version}"
            if key not in self._migrations:
                raise ValueError(f"No migration path from {current} to {target_version}")
            data = self._migrations[key](data)
            current = data["version"]
        return data
```

---

## 7. Acceptance Criteria

### 7.1 Type System

- [ ] All 7 primitive types defined with serialization rules
- [ ] All 5 composite types support recursive nesting
- [ ] Domain types are extensible at runtime without core changes
- [ ] Type coercion rules enforce safety at connection time

### 7.2 Graph Execution Runtime

- [ ] Topological sort produces correct execution levels for any DAG
- [ ] Parallel branches execute concurrently within levels
- [ ] Cycle detection rejects invalid graphs before execution
- [ ] ExecutionContext supports cooperative cancellation
- [ ] Error handling follows Orchestrator patterns (retry, circuit breaker, dead letter)

### 7.3 Plugin API

- [ ] `NodeWorker` ABC defines `execute`, `validate`, `capabilities` abstract methods
- [ ] Lifecycle hooks (`on_init`, `on_destroy`) are optional overrides
- [ ] Circuit breaker integration matches `LLMProvider` pattern
- [ ] `make_worker_retry` follows `make_retry` pattern from providers/base.py
- [ ] TypeScript `NodeWorker` interface mirrors Python ABC

### 7.4 Node Registry

- [ ] `NodeTypeRegistry` supports register/get/list/remove with builtin distinction
- [ ] Atomic JSON persistence follows `AgentRegistry.save()` pattern
- [ ] `WorkerRegistry` maps domains to `NodeWorker` instances
- [ ] Domain discovery and versioning supported

### 7.5 Persistence Layer

- [ ] Graph serialization format is versioned and forward-compatible
- [ ] Version history uses JSON Patch diffs (deferred to Phase 1+ PostgreSQL backend)
- [ ] Migration framework supports sequential schema upgrades
- [ ] File-based storage uses atomic writes (temp + rename)
