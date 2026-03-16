# Phase 5 — Cross-Domain Integration Specification

**Document:** SPEC-029-P5 — Universal Node Engine Phase 5 Cross-Domain Integration
**Date:** 2026-03-16
**Version:** 1.0
**Status:** Draft
**Parent:** SPEC-029 (Universal Node Engine Architecture)

---

## Table of Contents

1. [Overview](#1-overview)
2. [Cross-Domain Type Adapters](#2-cross-domain-type-adapters)
3. [Unified Orchestration Pipeline](#3-unified-orchestration-pipeline)
4. [Federated Graph Execution](#4-federated-graph-execution)
5. [Data Serialization Between Domains](#5-data-serialization-between-domains)
6. [Error Propagation Across Domain Boundaries](#6-error-propagation-across-domain-boundaries)
7. [Cross-Domain Observability](#7-cross-domain-observability)
8. [Example End-to-End Workflows](#8-example-end-to-end-workflows)
9. [Acceptance Criteria](#9-acceptance-criteria)

---

## 1. Overview

Phase 5 is the capstone phase of the Universal Node Engine, introducing the cross-domain integration layer that enables workflows spanning multiple domain workers (AI, CAD, Electronics, Hardware). Where Phases 1–4 deliver isolated domain workers, Phase 5 bridges them — enabling an AI-generated design to flow into CAD modeling, through electronics validation, and onto physical hardware deployment within a single graph execution.

### 1.1 Goals

- Define cross-domain type adapters that convert between domain-specific port types (e.g., AI `LLMResponse` → CAD `DesignParameters`, Electronics `Netlist` → Hardware `FirmwareBinary` config)
- Implement a unified orchestration pipeline where nodes from different domains compose into a single workflow graph
- Enable federated graph execution across multiple services and machines via Ray and the existing P2P cluster infrastructure
- Provide example end-to-end workflows demonstrating multi-domain composition
- Establish data serialization contracts between domains
- Define error propagation semantics across domain boundaries
- Deliver cross-domain observability with distributed tracing

### 1.2 Non-Goals

- Modifying domain worker internals (Phases 1–4 workers are consumed as-is)
- Building a visual workflow designer (separate UI spec)
- Automatic adapter inference (adapters are explicit and user-configured)
- Real-time streaming across federated nodes (batch execution only in v1)

### 1.3 Dependencies

- Phase 0 Foundations (core type system, graph execution runtime, NodeWorker interface, registries)
- Phase 1 AI Worker (LLMResponse, EmbeddingVector, ChatMessage, PromptTemplate, TokenUsage)
- Phase 2 CAD Worker (MeshData, Toolpath, BOM, GCode, CADDocument, SchematicData, PCBLayout)
- Phase 3 Electronics Worker (Netlist, Schematic, Waveform, FirmwareBinary, ComponentSpec, DRCReport)
- Phase 4 Hardware Worker (MIDIMessage, DMXFrame, SerialData, GPIOState, SensorReading)
- Existing Mascarade Orchestrator (`core/mascarade/orchestrator/engine.py`) — execution modes, circuit breakers, retry, dead letter
- Existing ClusterManager (`core/mascarade/cluster/`) — P2P node discovery and task dispatch
- Ray (optional) — distributed task execution

---

## 2. Cross-Domain Type Adapters

Cross-domain type adapters are explicit conversion nodes that transform output from one domain into input for another. They are never implicit — every cross-domain boundary requires an adapter node in the graph, making data transformations visible and auditable.

### 2.1 Adapter Architecture

```
┌──────────┐     ┌─────────────────────┐     ┌──────────────┐
│ AI Node  │────▶│ Cross-Domain Adapter │────▶│  CAD Node    │
│ (output: │     │                     │     │ (input:      │
│ LLMResp) │     │ ai.LLMResponse →    │     │ CADDocument) │
└──────────┘     │ cad.DesignParams    │     └──────────────┘
                 └─────────────────────┘
```

Each adapter implements the `NodeWorker` interface from Phase 0 and is registered in the `NodeTypeRegistry` under the `cross_domain` domain prefix.

### 2.2 Adapter Interface

```python
"""Cross-domain type adapter base class.

Extends the Phase 0 NodeWorker interface with adapter-specific
validation and conversion semantics.
"""

from __future__ import annotations

from abc import abstractmethod
from dataclasses import dataclass, field
from typing import Any

from mascarade.node_engine.types import DomainType, PortType
from mascarade.node_engine.worker import NodeWorker, ExecutionContext, NodeResult


@dataclass
class AdapterMapping:
    """Declares a single type conversion supported by an adapter."""

    source_domain: str
    source_type: str
    target_domain: str
    target_type: str
    lossy: bool = False          # True if conversion discards information
    requires_config: bool = False  # True if user must provide mapping config


class CrossDomainAdapter(NodeWorker):
    """Base class for all cross-domain type adapters.

    Subclasses declare which domain type conversions they support
    and implement the conversion logic. The adapter validates that
    source data conforms to the source domain schema before conversion
    and validates the output against the target domain schema after.
    """

    @abstractmethod
    def supported_mappings(self) -> list[AdapterMapping]:
        """Return all type conversions this adapter supports."""
        ...

    @abstractmethod
    async def convert(
        self,
        source_data: Any,
        mapping: AdapterMapping,
        config: dict[str, Any] | None = None,
    ) -> Any:
        """Convert source domain data to target domain data."""
        ...

    async def execute(self, context: ExecutionContext) -> NodeResult:
        """Standard NodeWorker execute — delegates to convert()."""
        source = context.inputs["source"]
        mapping_id = context.config.get("mapping")
        config = context.config.get("adapter_config", {})

        mapping = self._resolve_mapping(mapping_id)
        self._validate_source(source, mapping)
        result = await self.convert(source, mapping, config)
        self._validate_target(result, mapping)

        return NodeResult(outputs={"result": result})

    def _resolve_mapping(self, mapping_id: str | None) -> AdapterMapping:
        mappings = self.supported_mappings()
        if mapping_id:
            for m in mappings:
                if f"{m.source_domain}.{m.source_type}->{m.target_domain}.{m.target_type}" == mapping_id:
                    return m
        if len(mappings) == 1:
            return mappings[0]
        raise ValueError(f"Adapter has {len(mappings)} mappings — specify 'mapping' in config")

    def _validate_source(self, data: Any, mapping: AdapterMapping) -> None:
        """Validate source data against the source domain type schema."""
        # Delegates to NodeTypeRegistry schema validation
        pass

    def _validate_target(self, data: Any, mapping: AdapterMapping) -> None:
        """Validate converted data against the target domain type schema."""
        pass
```

### 2.3 Built-in Adapter Catalog

#### 2.3.1 AI → CAD Adapter (`cross_domain.ai_to_cad`)

Converts AI-generated responses into CAD design parameters, FreeCAD scripts, or KiCad schematic instructions.

| Mapping | Source | Target | Lossy | Description |
|---------|--------|--------|-------|-------------|
| `ai.LLMResponse->cad.CADDocument` | `LLMResponse` | `CADDocument` parameters | Yes | Extracts structured design parameters from LLM output via JSON parsing or structured output |
| `ai.LLMResponse->cad.GCode` | `LLMResponse` | `GCode` | Yes | Extracts G-code program from LLM-generated machining instructions |

**Configuration:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `extraction_mode` | `string` | `"json"` | How to extract structured data: `"json"`, `"regex"`, `"structured_output"` |
| `schema_hint` | `json` | `null` | JSON Schema hint for the expected output structure |
| `fallback_on_parse_error` | `boolean` | `false` | If true, wrap raw LLM text as a string parameter instead of failing |

#### 2.3.2 AI → Electronics Adapter (`cross_domain.ai_to_electronics`)

Converts AI-generated circuit descriptions into SPICE netlists or component specifications.

| Mapping | Source | Target | Lossy | Description |
|---------|--------|--------|-------|-------------|
| `ai.LLMResponse->electronics.Netlist` | `LLMResponse` | `Netlist` | Yes | Parses SPICE netlist from LLM output, validates syntax |
| `ai.LLMResponse->electronics.ComponentSpec` | `LLMResponse` | `ComponentSpec` | Yes | Extracts component parameters from LLM-generated datasheets |

#### 2.3.3 CAD → Electronics Adapter (`cross_domain.cad_to_electronics`)

Bridges CAD schematic data to electronics simulation and validation.

| Mapping | Source | Target | Lossy | Description |
|---------|--------|--------|-------|-------------|
| `cad.SchematicData->electronics.Netlist` | `SchematicData` | `Netlist` | No | Generates SPICE netlist from KiCad schematic symbols and nets |
| `cad.PCBLayout->electronics.DRCReport` | `PCBLayout` | DRC input | No | Converts PCB layout to DRC-checkable format |
| `cad.BOM->electronics.ComponentSpec[]` | `BOM` | `array<ComponentSpec>` | Yes | Resolves BOM entries to component specifications via library lookup |

#### 2.3.4 Electronics → Hardware Adapter (`cross_domain.electronics_to_hardware`)

Converts electronics artifacts to hardware-deployable formats.

| Mapping | Source | Target | Lossy | Description |
|---------|--------|--------|-------|-------------|
| `electronics.FirmwareBinary->hardware.SerialData` | `FirmwareBinary` | `SerialData` | No | Wraps firmware binary for serial upload (ESP32 bootloader protocol) |
| `electronics.Netlist->hardware.GPIOState[]` | `Netlist` | `array<GPIOState>` | Yes | Extracts GPIO pin configuration from netlist pin assignments |
| `electronics.ComponentSpec->hardware.SensorReading` | `ComponentSpec` | `SensorReading` template | Yes | Creates sensor reading template from component parameters (units, ranges) |

#### 2.3.5 Hardware → AI Adapter (`cross_domain.hardware_to_ai`)

Feeds hardware telemetry back into AI analysis nodes, closing the feedback loop.

| Mapping | Source | Target | Lossy | Description |
|---------|--------|--------|-------|-------------|
| `hardware.SensorReading->ai.ChatMessage` | `SensorReading` | `ChatMessage` | Yes | Formats sensor data as a user message for LLM analysis |
| `hardware.GPIOState->ai.ChatMessage` | `GPIOState` | `ChatMessage` | Yes | Formats GPIO state as a user message for diagnostics |

---

## 3. Unified Orchestration Pipeline

The unified orchestration pipeline extends the Phase 0 graph execution runtime to support multi-domain graph execution — where nodes from different domains (AI, CAD, Electronics, Hardware) compose into a single workflow with cross-domain adapter nodes at the boundaries.

### 3.1 Multi-Domain Graph Composition

A cross-domain graph is a standard Phase 0 graph where:

1. Nodes belong to different domain workers (identified by their `domain` prefix)
2. Cross-domain connections pass through explicit adapter nodes
3. The graph execution runtime schedules nodes to the appropriate domain workers

```
┌────────────────────────────────────────────────────────────────────┐
│                   Unified Orchestration Pipeline                   │
│                                                                    │
│  ┌─────────┐   ┌───────────┐   ┌──────────┐   ┌───────────────┐  │
│  │ AI Node │──▶│ AI→CAD    │──▶│ CAD Node │──▶│ CAD→Elec      │  │
│  │ (Phase1)│   │ Adapter   │   │ (Phase 2)│   │ Adapter       │  │
│  └─────────┘   └───────────┘   └──────────┘   └───────┬───────┘  │
│                                                        │          │
│                                                 ┌──────▼───────┐  │
│                                                 │ Electronics  │  │
│                                                 │ Node (Ph. 3) │  │
│                                                 └──────┬───────┘  │
│                                                        │          │
│                                                 ┌──────▼───────┐  │
│                                                 │ Elec→HW      │  │
│                                                 │ Adapter       │  │
│                                                 └──────┬───────┘  │
│                                                        │          │
│                                                 ┌──────▼───────┐  │
│                                                 │ Hardware     │  │
│                                                 │ Node (Ph. 4) │  │
│                                                 └──────────────┘  │
└────────────────────────────────────────────────────────────────────┘
```

### 3.2 Domain-Aware Scheduling

The graph execution runtime extends Phase 0 scheduling with domain awareness:

```python
"""Cross-domain scheduler — extends the Phase 0 graph execution runtime.

Routes nodes to the correct domain worker based on node type prefix
and manages adapter node execution at domain boundaries.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from mascarade.node_engine.runtime import GraphExecutionRuntime, ExecutionPlan, NodeTask
from mascarade.node_engine.registry import WorkerRegistry


@dataclass
class DomainScheduler:
    """Schedules nodes to domain workers with cross-domain awareness.

    Extends the base topological scheduler to:
    1. Route each node to its domain worker
    2. Insert implicit serialization at domain boundaries
    3. Respect domain-specific resource constraints
    4. Support remote dispatch via Ray for heavy workloads
    """

    worker_registry: WorkerRegistry
    execution_plan: ExecutionPlan
    resource_limits: dict[str, dict[str, Any]] = field(default_factory=dict)

    def schedule(self) -> list[NodeTask]:
        """Produce an ordered task list respecting domain constraints."""
        tasks = self.execution_plan.topological_tasks()

        for task in tasks:
            domain = self._extract_domain(task.node_type)
            worker = self.worker_registry.get_worker(domain)

            task.worker = worker
            task.serialization_format = self._resolve_serialization(task)
            task.resource_allocation = self._allocate_resources(domain, task)

        return tasks

    def _extract_domain(self, node_type: str) -> str:
        """Extract domain from node type ID (e.g., 'ai.llm.inference' → 'ai')."""
        return node_type.split(".")[0]

    def _resolve_serialization(self, task: NodeTask) -> str:
        """Determine serialization format for cross-domain data transfer."""
        upstream_domains = {
            self._extract_domain(dep.node_type)
            for dep in task.dependencies
        }
        task_domain = self._extract_domain(task.node_type)

        if upstream_domains and upstream_domains != {task_domain}:
            return "cross_domain_envelope"
        return "passthrough"

    def _allocate_resources(
        self, domain: str, task: NodeTask,
    ) -> dict[str, Any]:
        """Allocate resources based on domain constraints."""
        limits = self.resource_limits.get(domain, {})
        return {
            "max_memory_mb": limits.get("max_memory_mb", 512),
            "max_cpu_cores": limits.get("max_cpu_cores", 1),
            "timeout_s": limits.get("timeout_s", 300),
            "gpu_required": limits.get("gpu_required", False),
        }
```

### 3.3 Execution Context Propagation

When a graph spans multiple domains, the execution context carries cross-domain metadata:

```python
@dataclass
class CrossDomainContext:
    """Extended execution context for cross-domain workflows."""

    graph_id: str
    run_id: str
    trace_id: str                           # Distributed trace ID (W3C Trace Context)
    domain_chain: list[str]                 # Ordered list of domains traversed
    adapter_history: list[AdapterExecution]  # Record of all adapter conversions
    accumulated_cost: float = 0.0           # Running cost across all domains
    accumulated_tokens: int = 0             # Running token count (AI domain)
    deadline_utc: float | None = None       # Optional deadline for the entire pipeline
```

---

## 4. Federated Graph Execution

Federated execution enables graph nodes to run across multiple services and machines, leveraging the existing Mascarade infrastructure: the `ClusterManager` for P2P node discovery and Ray for distributed task dispatch.

### 4.1 Architecture

```
┌─────────────────┐       ┌─────────────────┐       ┌──────────────────┐
│  Machine A      │       │  Machine B      │       │  Machine C       │
│  (192.168.0.119)│       │  (GPU Server)   │       │  (Hardware Host) │
│                 │       │                 │       │                  │
│  ┌───────────┐  │  Ray  │  ┌───────────┐  │  P2P  │  ┌────────────┐ │
│  │ AI Worker │◀─┼───────┼─▶│ CAD Worker│  │◀──────┼─▶│ HW Worker  │ │
│  │ Elec.Work.│  │       │  │ (FreeCAD) │  │       │  │ (ESP32s)   │ │
│  │ Scheduler │  │       │  └───────────┘  │       │  └────────────┘ │
│  └───────────┘  │       └─────────────────┘       └──────────────────┘
└─────────────────┘
```

### 4.2 Execution Dispatch Strategy

```python
"""Federated execution dispatcher.

Extends the Orchestrator's existing Ray integration
(see core/mascarade/orchestrator/engine.py _ensure_ray / _ray_router_send)
to support multi-domain graph execution across machines.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class DispatchStrategy(StrEnum):
    LOCAL = "local"           # Execute on the scheduler machine
    RAY_REMOTE = "ray_remote" # Dispatch to Ray cluster
    P2P_CLUSTER = "p2p"       # Dispatch via ClusterManager peer
    AFFINITY = "affinity"     # Route to machine where domain resources exist


@dataclass
class FederatedDispatcher:
    """Routes node execution to the appropriate machine.

    Selection logic:
    1. If the node's domain worker declares hardware affinity
       (e.g., Hardware Worker needs physical USB/serial), route to
       the machine that has the required devices.
    2. If the node requires GPU (e.g., AI inference, mesh operations),
       route to the GPU-equipped machine via Ray.
    3. If the node has no special requirements, execute locally.
    4. Fall back to local execution if remote dispatch fails
       (circuit breaker pattern from Orchestrator).
    """

    ray_client: Any = None
    cluster_manager: Any = None  # ClusterManager instance
    domain_affinity: dict[str, str] = field(default_factory=dict)
    circuit_breakers: dict[str, Any] = field(default_factory=dict)

    def select_strategy(self, task: "NodeTask") -> DispatchStrategy:
        domain = task.node_type.split(".")[0]

        # Hardware nodes must run where devices are attached
        if domain == "hardware" and self.cluster_manager:
            return DispatchStrategy.AFFINITY

        # GPU-requiring tasks go to Ray cluster
        if task.resource_allocation.get("gpu_required"):
            if self.ray_client:
                return DispatchStrategy.RAY_REMOTE
            return DispatchStrategy.LOCAL  # Fallback

        # Check domain affinity configuration
        if domain in self.domain_affinity and self.cluster_manager:
            return DispatchStrategy.P2P_CLUSTER

        return DispatchStrategy.LOCAL

    async def dispatch(self, task: "NodeTask", context: "CrossDomainContext") -> Any:
        strategy = self.select_strategy(task)
        breaker_key = f"{strategy}:{task.node_type}"

        breaker = self.circuit_breakers.get(breaker_key)
        if breaker and breaker.is_open:
            # Fallback to local execution
            return await self._execute_local(task, context)

        try:
            if strategy == DispatchStrategy.RAY_REMOTE:
                return await self._execute_ray(task, context)
            elif strategy == DispatchStrategy.P2P_CLUSTER:
                return await self._execute_p2p(task, context)
            elif strategy == DispatchStrategy.AFFINITY:
                return await self._execute_affinity(task, context)
            else:
                return await self._execute_local(task, context)
        except Exception as exc:
            if breaker:
                breaker.record_failure()
            # Fallback to local
            return await self._execute_local(task, context)

    async def _execute_local(self, task: "NodeTask", context: "CrossDomainContext") -> Any:
        """Execute node in the local process via its domain worker."""
        worker = task.worker
        return await worker.execute(task.to_execution_context(context))

    async def _execute_ray(self, task: "NodeTask", context: "CrossDomainContext") -> Any:
        """Dispatch to Ray cluster — mirrors Orchestrator._try_ray_send()."""
        import ray
        serialized = task.serialize_for_remote()
        result_ref = self.ray_client.remote(serialized)
        return await asyncio.wait_for(
            ray.get(result_ref),
            timeout=task.resource_allocation.get("timeout_s", 300),
        )

    async def _execute_p2p(self, task: "NodeTask", context: "CrossDomainContext") -> Any:
        """Dispatch to a peer via ClusterManager."""
        peer = self.cluster_manager.select_peer(
            domain=task.node_type.split(".")[0],
        )
        return await peer.execute_remote(task.serialize_for_remote())

    async def _execute_affinity(self, task: "NodeTask", context: "CrossDomainContext") -> Any:
        """Route to the machine with required hardware devices."""
        domain = task.node_type.split(".")[0]
        target = self.domain_affinity.get(domain)
        if target and self.cluster_manager:
            peer = self.cluster_manager.get_peer(target)
            if peer:
                return await peer.execute_remote(task.serialize_for_remote())
        return await self._execute_local(task, context)
```

### 4.3 Resource Constraints

Federated execution respects the Mascarade deployment constraints (4 vCPU, 6.8 GiB RAM on the primary VM):

| Resource | Local Limit | Remote (Ray) | Notes |
|----------|-------------|--------------|-------|
| Memory | 512 MB per node | Configurable | CAD/SPICE nodes may need more |
| CPU | 1 core per node | Up to 4 cores | AI inference is I/O-bound |
| GPU | Not available | If available | AI inference, mesh rendering |
| Timeout | 300s default | 600s max | Hardware nodes may need longer |
| Concurrent nodes | 4 max | Cluster-limited | Prevents OOM on primary VM |

---

## 5. Data Serialization Between Domains

Cross-domain data transfer requires a well-defined serialization contract. Data crossing domain boundaries is wrapped in a `CrossDomainEnvelope` that carries type metadata, provenance, and validation checksums.

### 5.1 Envelope Format

```python
"""Cross-domain data serialization envelope.

All data crossing domain boundaries is wrapped in this envelope
to ensure type safety, provenance tracking, and integrity validation.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any


@dataclass
class CrossDomainEnvelope:
    """Wraps data for cross-domain transfer.

    The envelope ensures:
    1. Source domain and type are preserved
    2. Target domain and type are declared
    3. Data integrity is verified via checksum
    4. Provenance chain tracks all transformations
    """

    source_domain: str
    source_type: str
    target_domain: str
    target_type: str
    payload: Any
    checksum: str = ""
    provenance: list[str] = field(default_factory=list)
    serialization_format: str = "json"  # "json", "msgpack", "arrow"

    def __post_init__(self) -> None:
        if not self.checksum:
            self.checksum = self._compute_checksum()

    def _compute_checksum(self) -> str:
        serialized = json.dumps(self.payload, sort_keys=True, default=str)
        return hashlib.sha256(serialized.encode()).hexdigest()[:16]

    def verify(self) -> bool:
        return self.checksum == self._compute_checksum()

    def serialize(self) -> bytes:
        """Serialize envelope for network transfer."""
        if self.serialization_format == "json":
            return json.dumps({
                "source_domain": self.source_domain,
                "source_type": self.source_type,
                "target_domain": self.target_domain,
                "target_type": self.target_type,
                "payload": self.payload,
                "checksum": self.checksum,
                "provenance": self.provenance,
            }, default=str).encode()
        # msgpack and arrow formats for high-throughput scenarios
        raise NotImplementedError(f"Format {self.serialization_format} not yet implemented")

    @classmethod
    def deserialize(cls, data: bytes) -> "CrossDomainEnvelope":
        parsed = json.loads(data)
        return cls(**parsed)
```

### 5.2 Serialization Format Selection

| Scenario | Format | Rationale |
|----------|--------|-----------|
| Default cross-domain transfer | JSON | Human-readable, debuggable, universal |
| Large numeric arrays (waveforms, meshes) | MessagePack | 2-5× smaller than JSON for numeric data |
| Streaming sensor data | Apache Arrow IPC | Zero-copy, columnar, efficient for time series |
| Binary payloads (firmware, images) | Base64 in JSON | Compatible with JSON envelope |

---

## 6. Error Propagation Across Domain Boundaries

Cross-domain workflows require careful error handling because failures in one domain can cascade unpredictably into others. Phase 5 defines a structured error propagation model.

### 6.1 Error Classification

| Error Class | Scope | Propagation | Example |
|-------------|-------|-------------|---------|
| `DomainError` | Within a single domain | Contained to domain worker | FreeCAD script syntax error |
| `AdapterError` | At a domain boundary | Blocks downstream domains | JSON parse failure in AI→CAD adapter |
| `FederatedError` | Remote execution | Triggers fallback to local | Ray worker timeout |
| `PipelineError` | Entire cross-domain flow | May halt or degrade pipeline | Deadline exceeded |
| `IntegrityError` | Data transfer | Blocks consumption | Checksum mismatch in envelope |

### 6.2 Error Propagation Rules

```python
"""Cross-domain error handling.

Extends the Orchestrator's circuit breaker and dead letter patterns
to cross-domain boundaries.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class ErrorSeverity(StrEnum):
    WARNING = "warning"     # Adapter produced partial result
    ERROR = "error"         # Node failed, downstream blocked
    FATAL = "fatal"         # Pipeline must abort


class ErrorStrategy(StrEnum):
    HALT = "halt"           # Stop entire pipeline
    SKIP = "skip"           # Skip failed node, continue with defaults
    RETRY = "retry"         # Retry with backoff (uses RetryExecutor)
    FALLBACK = "fallback"   # Use fallback adapter or local execution
    DEAD_LETTER = "dead_letter"  # Store failed data for later retry


@dataclass
class CrossDomainError:
    """Structured error that propagates across domain boundaries."""

    source_domain: str
    source_node: str
    error_class: str        # DomainError, AdapterError, etc.
    severity: ErrorSeverity
    message: str
    strategy: ErrorStrategy = ErrorStrategy.HALT
    original_exception: Exception | None = None
    context: dict[str, Any] | None = None

    def should_halt_pipeline(self) -> bool:
        return self.severity == ErrorSeverity.FATAL or (
            self.severity == ErrorSeverity.ERROR
            and self.strategy == ErrorStrategy.HALT
        )
```

### 6.3 Dead Letter Handling

Failed cross-domain transfers are stored in the existing `DeadLetterStore` (from `core/mascarade/orchestrator/dead_letter.py`) with extended metadata:

- Source and target domain identifiers
- The `CrossDomainEnvelope` that failed
- Failure reason and timestamp
- Retry count and next retry time

This enables operators to inspect, manually fix, and replay failed cross-domain transfers.

---

## 7. Cross-Domain Observability

Observability for cross-domain workflows extends the existing `AgentTraceBuffer` pattern with distributed tracing semantics (W3C Trace Context).

### 7.1 Distributed Trace Model

```
Trace: "AI-designed enclosure → CNC machining"
│
├── Span: ai.llm.inference (Machine A)
│   └── duration: 2.3s, tokens: 1420, cost: $0.004
│
├── Span: cross_domain.ai_to_cad (Machine A)
│   └── duration: 0.1s, adapter: "json extraction"
│
├── Span: cad.freecad.parametric_model (Machine B, Ray)
│   └── duration: 8.7s, memory: 380MB
│
├── Span: cad.toolpath.generate (Machine B, Ray)
│   └── duration: 3.2s, gcode_lines: 14200
│
├── Span: cross_domain.cad_to_electronics (Machine A)
│   └── duration: 0.05s, adapter: "BOM extraction"
│
├── Span: electronics.spice.simulate (Machine A)
│   └── duration: 1.8s, convergence: true
│
└── Span: cross_domain.electronics_to_hardware (Machine A)
    └── duration: 0.02s, adapter: "firmware config"
```

### 7.2 Metrics

| Metric | Type | Description |
|--------|------|-------------|
| `node_engine.cross_domain.adapter_duration_s` | Histogram | Time spent in adapter conversion |
| `node_engine.cross_domain.adapter_errors_total` | Counter | Adapter conversion failures by source/target domain |
| `node_engine.cross_domain.envelope_size_bytes` | Histogram | Size of cross-domain data envelopes |
| `node_engine.cross_domain.pipeline_duration_s` | Histogram | Total end-to-end pipeline duration |
| `node_engine.cross_domain.domain_transitions_total` | Counter | Number of domain boundary crossings per pipeline |
| `node_engine.federated.dispatch_strategy` | Counter | Dispatch strategy selection (local/ray/p2p/affinity) |
| `node_engine.federated.fallback_total` | Counter | Fallbacks from remote to local execution |

### 7.3 Logging Convention

Cross-domain log entries use structured logging with the following fields, consistent with the existing `mascarade.orchestrator` logger:

```python
logger.info(
    "cross_domain_transfer",
    extra={
        "trace_id": context.trace_id,
        "run_id": context.run_id,
        "source_domain": envelope.source_domain,
        "source_type": envelope.source_type,
        "target_domain": envelope.target_domain,
        "target_type": envelope.target_type,
        "envelope_size_bytes": len(envelope.serialize()),
        "checksum_valid": envelope.verify(),
    },
)
```

---

## 8. Example End-to-End Workflows

### 8.1 AI-Designed CAD Part → Electronics Validation → Hardware Deployment

**Scenario:** A user describes an enclosure for an ESP32 sensor board. The system generates a 3D model, validates the electronics fit, compiles firmware, and deploys to the device.

```yaml
graph:
  id: "ai-to-hardware-enclosure"
  name: "AI-Designed Enclosure Pipeline"
  nodes:
    - id: "describe"
      type: "ai.llm.inference"
      config:
        strategy: "best"
        system: "You are a mechanical engineer. Output JSON with dimensions, mounting holes, and ventilation parameters."
      inputs:
        prompt: "Design an enclosure for an ESP32-WROOM-32 with a DHT22 sensor, 80x50x30mm, wall thickness 2mm"

    - id: "ai_to_cad"
      type: "cross_domain.ai_to_cad"
      config:
        mapping: "ai.LLMResponse->cad.CADDocument"
        extraction_mode: "json"

    - id: "model"
      type: "cad.freecad.parametric_model"
      config:
        template: "enclosure_parametric"

    - id: "export_stl"
      type: "cad.freecad.export"
      config:
        format: "stl"

    - id: "cad_to_elec"
      type: "cross_domain.cad_to_electronics"
      config:
        mapping: "cad.BOM->electronics.ComponentSpec[]"

    - id: "validate_components"
      type: "electronics.components.lookup"
      config:
        supplier: "jlcpcb"
        check_stock: true

    - id: "compile_firmware"
      type: "electronics.firmware.compile"
      config:
        target: "esp32"
        framework: "esp-idf"

    - id: "elec_to_hw"
      type: "cross_domain.electronics_to_hardware"
      config:
        mapping: "electronics.FirmwareBinary->hardware.SerialData"

    - id: "deploy"
      type: "hardware.esp32.ota_update"
      config:
        device_id: "esp32-sensor-01"

  edges:
    - from: "describe.response"      to: "ai_to_cad.source"
    - from: "ai_to_cad.result"       to: "model.parameters"
    - from: "model.document"         to: "export_stl.document"
    - from: "model.document"         to: "cad_to_elec.source"
    - from: "cad_to_elec.result"     to: "validate_components.specs"
    - from: "validate_components.validated" to: "compile_firmware.components"
    - from: "compile_firmware.binary" to: "elec_to_hw.source"
    - from: "elec_to_hw.result"      to: "deploy.firmware"
```

### 8.2 AI Prompt → SPICE Simulation → Results Analysis

**Scenario:** A user describes a circuit in natural language. The system generates a SPICE netlist, runs simulation, and feeds results back to AI for analysis.

```yaml
graph:
  id: "ai-spice-analysis"
  name: "AI-Driven Circuit Analysis"
  nodes:
    - id: "circuit_prompt"
      type: "ai.llm.inference"
      config:
        strategy: "best"
        system: "You are an electronics engineer. Generate a SPICE netlist for the described circuit."
      inputs:
        prompt: "Design a common-emitter amplifier with 2N2222, Vcc=12V, gain ~20, input impedance >10kΩ"

    - id: "ai_to_spice"
      type: "cross_domain.ai_to_electronics"
      config:
        mapping: "ai.LLMResponse->electronics.Netlist"

    - id: "simulate"
      type: "electronics.spice.simulate"
      config:
        analysis: "ac"
        frequency_range: { start: 10, stop: 1000000, points: 100, scale: "dec" }

    - id: "hw_to_ai"
      type: "cross_domain.hardware_to_ai"
      config:
        mapping: "hardware.SensorReading->ai.ChatMessage"
        # In this case we're adapting waveform results, which are
        # formatted as a ChatMessage for LLM consumption

    - id: "analyze"
      type: "ai.llm.inference"
      config:
        strategy: "best"
        system: "Analyze these simulation results. Report gain, bandwidth, phase margin, and any design concerns."

  edges:
    - from: "circuit_prompt.response"  to: "ai_to_spice.source"
    - from: "ai_to_spice.result"       to: "simulate.netlist"
    - from: "simulate.waveform"        to: "hw_to_ai.source"
    - from: "hw_to_ai.result"          to: "analyze.messages"
```

### 8.3 Sensor Feedback Loop — Hardware → AI → Hardware

**Scenario:** An ESP32 reads sensor data, AI analyzes it and adjusts hardware parameters in a continuous feedback loop.

```yaml
graph:
  id: "sensor-feedback-loop"
  name: "AI-Controlled Sensor Feedback"
  execution_mode: "continuous"
  nodes:
    - id: "read_sensor"
      type: "hardware.esp32.sensor_read"
      config:
        device_id: "esp32-climate-01"
        sensor_type: "temperature"
        interval_ms: 5000

    - id: "sensor_to_ai"
      type: "cross_domain.hardware_to_ai"
      config:
        mapping: "hardware.SensorReading->ai.ChatMessage"

    - id: "decide"
      type: "ai.llm.inference"
      config:
        strategy: "cheapest"
        system: "You control a climate system. Given sensor data, output JSON: {fan_speed: 0-100, heater: bool}"

    - id: "ai_to_hw"
      type: "cross_domain.ai_to_cad"
      config:
        mapping: "ai.LLMResponse->hardware.GPIOState"
        extraction_mode: "json"

    - id: "actuate"
      type: "hardware.esp32.gpio_write"
      config:
        device_id: "esp32-climate-01"

  edges:
    - from: "read_sensor.reading"   to: "sensor_to_ai.source"
    - from: "sensor_to_ai.result"   to: "decide.messages"
    - from: "decide.response"       to: "ai_to_hw.source"
    - from: "ai_to_hw.result"       to: "actuate.state"
```

---

## 9. Acceptance Criteria

### 9.1 Cross-Domain Type Adapters

- [ ] `CrossDomainAdapter` base class implements `NodeWorker` interface from Phase 0
- [ ] At least 5 adapter types cover AI↔CAD, AI↔Electronics, CAD↔Electronics, Electronics↔Hardware, Hardware↔AI
- [ ] Each adapter validates source data against source domain schema before conversion
- [ ] Each adapter validates converted data against target domain schema after conversion
- [ ] Lossy conversions are explicitly marked and documented
- [ ] Adapters that require configuration fail with clear error if config is missing

### 9.2 Unified Orchestration Pipeline

- [ ] Multi-domain graphs execute correctly with nodes from ≥2 different domains
- [ ] `DomainScheduler` routes nodes to the correct domain worker
- [ ] `CrossDomainContext` propagates trace ID, cost, and deadline across domains
- [ ] Adapter nodes appear in the execution plan between domain boundaries

### 9.3 Federated Graph Execution

- [ ] `FederatedDispatcher` selects dispatch strategy based on domain affinity and resource needs
- [ ] Ray dispatch works for GPU-requiring nodes with circuit breaker fallback
- [ ] P2P cluster dispatch works for hardware-affinity nodes
- [ ] Fallback to local execution on remote failure

### 9.4 Data Serialization

- [ ] `CrossDomainEnvelope` wraps all cross-domain data transfers
- [ ] Checksum validation detects data corruption
- [ ] JSON serialization works for all domain types
- [ ] Provenance chain tracks all adapter transformations

### 9.5 Error Propagation

- [ ] `CrossDomainError` carries source domain, node, and severity
- [ ] Fatal errors halt the pipeline; warnings allow continuation
- [ ] Failed transfers stored in `DeadLetterStore` with extended metadata
- [ ] Circuit breakers prevent cascading failures across domains

### 9.6 Observability

- [ ] Distributed traces span all domains in a cross-domain pipeline
- [ ] Adapter duration, error count, and envelope size metrics are emitted
- [ ] Structured log entries include trace ID, source/target domain, and envelope metadata

### 9.7 End-to-End Workflows

- [ ] AI→CAD→Electronics→Hardware pipeline executes with correct adapter chaining
- [ ] AI→SPICE→AI analysis loop produces valid simulation results and analysis
- [ ] Sensor feedback loop demonstrates bidirectional cross-domain flow

## SPEC-025 Compatibility

Cross-domain orchestration supports mixed graphs containing both native `NodeWorker` implementations and legacy SPEC-025 nodes wrapped via the `Spec025Adapter`. Type adapters handle port compatibility across both interfaces.
