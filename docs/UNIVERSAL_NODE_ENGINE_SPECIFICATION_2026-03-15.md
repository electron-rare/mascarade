# Universal Node Engine — Master Architectural Specification

**Document ID:** SPEC-029
**Version:** 1.0.0
**Date:** 2026-03-15
**Status:** Draft — Foundation Architecture
**Authors:** Mascarade Architecture Team

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [System Context](#2-system-context)
3. [High-Level Design](#3-high-level-design)
4. [Domain Decomposition](#4-domain-decomposition)
5. [Cross-Domain Integration Strategy](#5-cross-domain-integration-strategy)
6. [Core Abstractions](#6-core-abstractions)
7. [Execution Model](#7-execution-model)
8. [Type System Architecture](#8-type-system-architecture)
9. [Resilience & Reliability](#9-resilience--reliability)
10. [Performance & Scalability](#10-performance--scalability)
11. [Observability & Monitoring](#11-observability--monitoring)
12. [Security Architecture](#12-security-architecture)
13. [Rollout Strategy](#13-rollout-strategy)
14. [Success Criteria](#14-success-criteria)
15. [Appendices](#15-appendices)

---

## 1. Executive Summary

### 1.1 Purpose

The **Universal Node Engine** is a multi-domain, graph-based execution architecture that enables composable, visual workflows spanning four primary technical domains: **AI**, **CAD**, **Electronics**, and **Hardware Runtime**. This engine serves as the computational backbone of the Mascarade ecosystem, replacing ad-hoc agent orchestration with a formal, type-safe, graph-structured execution model.

### 1.2 Strategic Goals

1. **Unification** — Consolidate disparate workflow execution patterns (AI chains, CAD pipelines, hardware control) into a single, coherent execution runtime
2. **Extensibility** — Enable rapid domain expansion without core engine modification through a plugin-based architecture
3. **Composability** — Allow visual composition of complex cross-domain workflows via ReactFlow-based graph editor
4. **Performance** — Achieve sub-5s execution for single-domain workflows, sub-30s for cross-domain workflows on target VM infrastructure
5. **Reliability** — Implement circuit breakers, retry logic, and graceful degradation for production-grade resilience

### 1.3 Evolution from SPEC-025

This specification supersedes **SPEC-025** ("Unified Node Engine Architecture — Kill_LIFE") by:

- Expanding from 6 fixed categories to 4 extensible domain workers
- Migrating from client-side execution to server-side runtime with distributed execution support
- Introducing a hierarchical, domain-aware type system with cross-domain adapters
- Implementing production-grade resilience (circuit breakers, dead letter queues, retry policies)
- Integrating with existing Mascarade infrastructure (Router, Orchestrator, AgentRegistry)

**Backward Compatibility:** SPEC-025 node definitions are supported via adapter wrappers, ensuring zero migration effort for existing Kill_LIFE workflows.

### 1.4 Key Architectural Innovations

1. **Universal Type System** — Primitive, composite, and domain-specific port types with compile-time validation and runtime coercion
2. **Graph Execution Runtime** — Topological sort, parallel branch scheduling, and three execution modes (eager/lazy/stepped)
3. **NodeWorker Plugin Interface** — Abstract base class with lifecycle hooks, capability declarations, and circuit breaker integration
4. **Federated Execution** — Distribute graph execution across multiple machines via Ray, with automatic worker placement
5. **Cross-Domain Type Adapters** — Explicit type conversions between domains (e.g., `LLMResponse` → `DesignParameters`)

---

## 2. System Context

### 2.1 Architectural Position

```
┌─────────────────────────────────────────────────────────────────┐
│                     Mascarade Ecosystem                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌─────────────────┐       ┌─────────────────┐                 │
│  │   crazy_life    │       │ mascarade-cockpit│                 │
│  │ (ReactFlow UI)  │◄──────┤ (Observability)  │                 │
│  └────────┬────────┘       └─────────────────┘                 │
│           │ WebSocket/REST                                       │
│           ▼                                                       │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │              TypeScript API (Hono)                       │   │
│  │  ┌─────────────────────────────────────────────────┐    │   │
│  │  │   Graph CRUD   │ Execution Control │ Node Catalog│    │   │
│  │  └─────────────────────────────────────────────────┘    │   │
│  └──────────────────────────┬──────────────────────────────┘   │
│                              │ HTTP/JSON                         │
│                              ▼                                   │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │           Python Core (FastAPI)                          │   │
│  │  ┌─────────────────────────────────────────────────┐    │   │
│  │  │        Universal Node Engine                     │    │   │
│  │  │  ┌──────────────────────────────────────────┐   │    │   │
│  │  │  │  Graph Execution Runtime                  │   │    │   │
│  │  │  │  ┌────────┬────────┬────────┬────────┐  │   │    │   │
│  │  │  │  │   AI   │  CAD   │Electron│Hardware│  │   │    │   │
│  │  │  │  │ Worker │ Worker │ Worker │ Worker │  │   │    │   │
│  │  │  │  └────────┴────────┴────────┴────────┘  │   │    │   │
│  │  │  └──────────────────────────────────────────┘   │    │   │
│  │  └─────────────────────────────────────────────────┘    │   │
│  │  ┌─────────────────────────────────────────────────┐    │   │
│  │  │   Router │ Orchestrator │ AgentRegistry         │    │   │
│  │  └─────────────────────────────────────────────────┘    │   │
│  └─────────────────────────────────────────────────────────┘   │
│           │                                                      │
│           ▼                                                      │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  External Services (KiCad, FreeCAD, ngspice, ESP32)     │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 Integration Points

| Component | Integration Type | Purpose |
|-----------|-----------------|---------|
| **Mascarade Router** | Internal API | LLM provider abstraction for AI Worker nodes |
| **Mascarade Orchestrator** | Pattern Template | Execution engine patterns (circuit breakers, retry, Ray distribution) |
| **AgentRegistry** | Internal API | Discovery of existing agents (KiCad, FreeCAD, SPICE) for domain worker integration |
| **crazy_life UI** | REST/WebSocket | Graph composition, real-time execution status |
| **mascarade-cockpit** | Metrics/Traces | Execution observability, node-level metrics, graph dashboards |
| **Ray Cluster** | Distributed Execution | Federated graph execution across multiple machines |
| **KiCad/FreeCAD** | External Process | CAD worker subprocess invocation |
| **ngspice** | External Process | Electronics worker circuit simulation |
| **ESP32/MIDI/DMX** | Hardware I/O | Hardware Runtime worker device communication |

### 2.3 Technology Stack

| Layer | Technology | Version | Rationale |
|-------|-----------|---------|-----------|
| **Core Runtime** | Python | 3.11+ | Async-first, Pydantic validation, type safety |
| **API Layer** | TypeScript, Hono | v4.12.4 | Type-safe REST/WebSocket, minimal overhead |
| **UI Layer** | React, ReactFlow | Latest | Industry-standard graph editor |
| **Validation** | Pydantic | v2.x | Schema-first validation, serialization |
| **Distributed Execution** | Ray | Latest | Proven multi-machine orchestration |
| **Metrics** | OpenTelemetry | Latest | Vendor-neutral observability |
| **Persistence** | JSON + PostgreSQL | — | JSON for graphs, PostgreSQL for execution history |

### 2.4 Deployment Context

**Target Environment:** Single VM (192.168.0.119)
**Resources:** 4 vCPU, 6.8 GiB RAM, 74% disk usage
**Deployment:** Docker Compose with core service (port 8100) and API service (port 3000)

**Resource Constraints:**
- Limited memory requires careful graph size management (max 100 nodes per graph)
- High disk usage requires pruning of execution history (retention: 30 days)
- CPU contention requires priority-based scheduling for time-critical hardware nodes

---

## 3. High-Level Design

### 3.1 Core Architecture Layers

```
┌─────────────────────────────────────────────────────────────────┐
│                     Presentation Layer                           │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  ReactFlow Graph Editor │ Node Catalog UI │ Metrics UI  │   │
│  └─────────────────────────────────────────────────────────┘   │
└──────────────────────────┬──────────────────────────────────────┘
                            │
┌──────────────────────────┼──────────────────────────────────────┐
│                     API Layer (TypeScript)                       │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  Graph CRUD Routes │ Execution Routes │ Catalog Routes   │   │
│  └─────────────────────────────────────────────────────────┘   │
└──────────────────────────┬──────────────────────────────────────┘
                            │
┌──────────────────────────┼──────────────────────────────────────┐
│                   Execution Layer (Python)                       │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │              Graph Execution Runtime                     │   │
│  │  ┌─────────────────────────────────────────────────┐    │   │
│  │  │  Scheduler │ Validator │ Context Manager        │    │   │
│  │  └─────────────────────────────────────────────────┘    │   │
│  └─────────────────────────────────────────────────────────┘   │
└──────────────────────────┬──────────────────────────────────────┘
                            │
┌──────────────────────────┼──────────────────────────────────────┐
│                   Worker Layer (Python)                          │
│  ┌───────────┬───────────┬─────────────┬─────────────────┐     │
│  │ AI Worker │CAD Worker │Elec. Worker │Hardware Worker  │     │
│  │           │           │             │                 │     │
│  │ • LLM     │• FreeCAD  │• SPICE      │• ESP32 Control  │     │
│  │ • Embed   │• KiCad    │• PCB DRC    │• MIDI I/O       │     │
│  │ • Chains  │• Toolpath │• Firmware   │• DMX Control    │     │
│  └───────────┴───────────┴─────────────┴─────────────────┘     │
└──────────────────────────┬──────────────────────────────────────┘
                            │
┌──────────────────────────┼──────────────────────────────────────┐
│                 Infrastructure Layer                             │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ Type System │ Registry │ Persistence │ Resilience       │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

### 3.2 Data Flow

**Graph Composition Flow:**
1. User composes graph in ReactFlow UI (crazy_life)
2. Graph definition sent to API layer via REST
3. API validates schema, persists to storage
4. Node type validation via Core registry
5. Success/error response to UI

**Execution Flow:**
1. User triggers execution via API (POST /graphs/{id}/execute)
2. API forwards to Core execution runtime
3. Runtime performs topological sort, builds execution DAG
4. Scheduler dispatches nodes to appropriate workers
5. Workers execute nodes, update execution context
6. Real-time status streamed via WebSocket
7. Final result persisted, metrics recorded

**Cross-Domain Flow:**
1. AI Worker generates design parameters (`LLMResponse`)
2. Type adapter converts to `DesignParameters` (CAD domain type)
3. CAD Worker generates 3D model (`MeshData`)
4. Type adapter converts to `ComponentGeometry` (Electronics domain type)
5. Electronics Worker validates manufacturability
6. Hardware Worker deploys firmware to physical device

### 3.3 Key Design Principles

1. **Separation of Concerns** — Clear boundaries between graph composition (UI), execution control (API), and computation (Core workers)
2. **Type Safety** — Pydantic models for all data structures, static type checking via mypy
3. **Async-First** — All I/O operations async, non-blocking execution
4. **Fail-Safe** — Circuit breakers prevent cascade failures, dead letter queues capture failed executions
5. **Observable** — Every execution step traced, metrics collected, dashboards available
6. **Domain-Driven** — Each domain worker encapsulates domain-specific knowledge, tools, and types
7. **Extensible** — New domains and node types via plugin registration, no core modification required

---

## 4. Domain Decomposition

### 4.1 Overview

The Universal Node Engine is decomposed into **4 primary domains**, each with a dedicated worker subsystem:

| Domain | Purpose | Node Count (MVP) | External Dependencies |
|--------|---------|------------------|----------------------|
| **AI** | LLM inference, embeddings, reasoning chains | 8-10 | Mascarade Router, OpenAI/Mistral/Anthropic APIs |
| **CAD** | 3D modeling, PCB design, toolpath generation | 12-15 | FreeCAD, KiCad, FreeCAD Python API |
| **Electronics** | Circuit simulation, PCB validation, firmware | 10-12 | ngspice, KiCad DRC, PlatformIO |
| **Hardware Runtime** | Device control, MIDI/DMX, real-time I/O | 8-10 | ESP32 HTTP API, MIDI devices, DMX controllers |

### 4.2 Domain: AI

**Scope:** Natural language processing, reasoning, embeddings, and AI-driven workflows.

**Core Capabilities:**
- **LLM Inference** — Single-turn and multi-turn conversations via Mascarade Router
- **Embeddings** — Generate vector embeddings for semantic search
- **Chains** — Chain-of-thought, ReAct, and custom reasoning patterns
- **Prompt Engineering** — Template-based prompt construction with variable substitution

**Node Types (Phase 1):**
1. **LLM Inference Node** — Send prompt, receive response
2. **Embedding Node** — Generate embeddings from text
3. **Chain-of-Thought Node** — Multi-step reasoning workflow
4. **Prompt Template Node** — Parameterized prompt generation
5. **Text Transform Node** — String manipulation, regex, formatting
6. **Conditional Logic Node** — Branch based on LLM output
7. **Memory Node** — Conversation history management
8. **Agent Invocation Node** — Call existing Mascarade agents

**Port Types:**
- `String` (input/output) — Text data
- `LLMResponse` (output) — Structured LLM response with metadata
- `EmbeddingVector` (output) — Float array embedding
- `ConversationHistory` (input/output) — List of message dicts

**Integration:**
- **Mascarade Router** — All LLM calls route through existing Router for provider abstraction
- **AgentRegistry** — Existing agents (e.g., `kicad_agent`, `freecad_agent`) callable as nodes

**Example Workflow:**
```
[Prompt Template] → [LLM Inference] → [Conditional Logic] → [Chain-of-Thought]
                                             ↓
                                       [Text Transform]
```

### 4.3 Domain: CAD

**Scope:** Computer-aided design for mechanical parts, PCB layouts, and manufacturing.

**Core Capabilities:**
- **3D Modeling** — Parametric CAD via FreeCAD Python API
- **PCB Design** — Schematic and layout via KiCad Python API
- **Toolpath Generation** — CNC G-code from 3D models
- **Manufacturing Export** — STL, Gerber, drill files

**Node Types (Phase 2):**
1. **FreeCAD Model Node** — Generate 3D model from parameters
2. **KiCad Schematic Node** — Generate schematic from netlist
3. **KiCad Layout Node** — Generate PCB layout
4. **Toolpath Node** — Generate G-code from mesh
5. **Mesh Transform Node** — Scale, rotate, translate mesh
6. **BOM Generator Node** — Extract bill of materials
7. **STL Export Node** — Export mesh to STL
8. **Gerber Export Node** — Export PCB to Gerber

**Port Types:**
- `MeshData` — 3D mesh (vertices, faces)
- `Toolpath` — G-code string
- `Schematic` — KiCad schematic JSON
- `PCBLayout` — KiCad layout JSON
- `BOM` — Bill of materials (CSV/JSON)
- `DesignParameters` — Parametric CAD input (dict)

**Integration:**
- **FreeCAD Agent** — Wraps existing `freecad_agent.py` for model generation
- **KiCad Agent** — Wraps existing `kicad_agent.py` for PCB design

**Example Workflow:**
```
[Design Parameters] → [FreeCAD Model] → [Toolpath Generator] → [G-code Export]
                                             ↓
                                       [Mesh Transform] → [STL Export]
```

### 4.4 Domain: Electronics

**Scope:** Circuit simulation, PCB validation, firmware compilation, and component management.

**Core Capabilities:**
- **SPICE Simulation** — Circuit analysis via ngspice
- **PCB DRC** — Design rule checking via KiCad
- **Firmware Compilation** — PlatformIO/Arduino build
- **Component Library** — Retrieve footprints, symbols, datasheets

**Node Types (Phase 3):**
1. **SPICE Simulation Node** — Run circuit simulation, output waveforms
2. **PCB DRC Node** — Validate design rules, output report
3. **Netlist Generator Node** — Extract netlist from schematic
4. **Firmware Build Node** — Compile firmware for target MCU
5. **Component Lookup Node** — Search component library
6. **Waveform Analysis Node** — Analyze SPICE output
7. **Schematic Validator Node** — Validate electrical rules
8. **Flash Firmware Node** — Upload firmware to device

**Port Types:**
- `Netlist` — SPICE netlist string
- `Waveform` — Time-series voltage/current data
- `DRCReport` — Design rule violations (JSON)
- `FirmwareBinary` — Compiled firmware (bytes)
- `ComponentSpec` — Component metadata (JSON)

**Integration:**
- **SPICE Agent** — Wraps existing `spice_agent.py` for simulation

**Example Workflow:**
```
[Schematic] → [Netlist Generator] → [SPICE Simulation] → [Waveform Analysis]
                   ↓
           [Schematic Validator] → [PCB DRC]
```

### 4.5 Domain: Hardware Runtime

**Scope:** Real-time device control, MIDI/DMX/serial I/O, and embedded system interaction.

**Core Capabilities:**
- **ESP32 Control** — HTTP/MQTT communication with ESP32 devices
- **MIDI I/O** — Send/receive MIDI messages
- **DMX Control** — Lighting fixture control
- **Serial Communication** — Arbitrary serial device I/O
- **Real-Time Loops** — Time-critical control sequences

**Node Types (Phase 4):**
1. **ESP32 HTTP Node** — Send HTTP request to ESP32
2. **MIDI Send Node** — Send MIDI message
3. **MIDI Receive Node** — Receive MIDI message
4. **DMX Output Node** — Set DMX channel values
5. **Serial Send Node** — Write to serial port
6. **Serial Receive Node** — Read from serial port
7. **Delay Node** — Wait for specified duration
8. **Loop Control Node** — Real-time loop with timing constraints

**Port Types:**
- `MIDIMessage` — MIDI event (note on/off, CC, etc.)
- `DMXFrame` — 512-byte DMX universe
- `SerialData` — Byte array
- `HTTPResponse` — HTTP response from ESP32
- `TimingConstraint` — Max execution time (ms)

**Integration:**
- **ESP32 Fleet** — Existing Mascarade ESP32 devices
- **MIDI Devices** — Hardware MIDI controllers/synths
- **DMX Fixtures** — Lighting equipment

**Example Workflow:**
```
[MIDI Receive] → [Conditional Logic] → [DMX Output] → [Delay] → [Loop Control]
                         ↓
                 [ESP32 HTTP Node] → [Serial Send]
```

### 4.6 Domain Comparison Matrix

| Feature | AI | CAD | Electronics | Hardware Runtime |
|---------|----|----|-------------|-----------------|
| **Execution Model** | Async I/O | Blocking (subprocess) | Blocking (subprocess) | Async I/O + Real-time |
| **Parallelism** | High | Low (resource-bound) | Medium | Low (device contention) |
| **Latency** | 1-10s per node | 5-60s per node | 5-30s per node | 10-500ms per node |
| **Error Handling** | Retry + fallback | Fail-fast + manual recovery | Retry + simulation validation | Circuit breaker + graceful degradation |
| **Resource Usage** | Network-bound | CPU + Memory-bound | CPU-bound | I/O-bound |
| **External Dependencies** | LLM APIs | FreeCAD, KiCad | ngspice, PlatformIO | Hardware devices |

---

## 5. Cross-Domain Integration Strategy

### 5.1 Motivation

Cross-domain workflows are the primary value proposition of the Universal Node Engine. Examples:

1. **AI → CAD:** LLM generates design parameters → FreeCAD creates 3D model
2. **CAD → Electronics:** PCB layout → DRC validation → SPICE simulation
3. **Electronics → Hardware:** Firmware compilation → ESP32 flash → MIDI control loop
4. **AI → Electronics → Hardware:** LLM designs circuit → SPICE validates → ESP32 deploys

**Challenge:** Each domain has domain-specific types (`LLMResponse`, `MeshData`, `Netlist`, `MIDIMessage`) that are incompatible by default.

### 5.2 Type Adapter Architecture

**Concept:** Explicit, bidirectional type adapters between domain-specific port types.

**Example:**
```python
class LLMResponseToDesignParametersAdapter(TypeAdapter):
    source_type = LLMResponse
    target_type = DesignParameters

    async def convert(self, source: LLMResponse, context: ExecutionContext) -> DesignParameters:
        # Parse LLM response (JSON/YAML), extract parameters
        parsed = json.loads(source.content)
        return DesignParameters(
            width=parsed["width"],
            height=parsed["height"],
            depth=parsed["depth"],
            # ...
        )
```

**Adapter Registry:**
```python
class TypeAdapterRegistry:
    def register(self, adapter: TypeAdapter) -> None: ...
    def get_adapter(self, source_type: Type, target_type: Type) -> TypeAdapter: ...
    def find_path(self, source_type: Type, target_type: Type) -> list[TypeAdapter]: ...
```

**Automatic Path Finding:**
If no direct adapter exists from `LLMResponse` → `Netlist`, the registry searches for a multi-hop path:
```
LLMResponse → DesignParameters → Schematic → Netlist
```

### 5.3 Unified Orchestration

**Strategy:** Cross-domain graphs execute as a single orchestration pipeline, with domain-specific workers invoked transparently.

**Orchestration Flow:**
1. Graph validated (all connections have valid adapters)
2. Topological sort across all domains
3. Per-node scheduling:
   - Identify domain worker
   - Apply circuit breaker
   - Execute node
   - Apply type adapter if cross-domain edge
   - Update execution context
4. Aggregate results, record metrics

**Hybrid Execution:**
- **Local Execution:** All workers on single machine (MVP)
- **Federated Execution:** Workers distributed via Ray (Phase 5)

### 5.4 Federated Execution (Phase 5)

**Motivation:** CAD and Electronics workers are resource-intensive and benefit from dedicated machines.

**Architecture:**
```
┌────────────────────────────────────────────────────────────┐
│                    Ray Cluster                              │
│  ┌───────────────┐  ┌───────────────┐  ┌───────────────┐  │
│  │   VM #1       │  │   VM #2       │  │   VM #3       │  │
│  │ (Coordinator) │  │ (CAD Worker)  │  │ (Elec Worker) │  │
│  │               │  │               │  │               │  │
│  │ • AI Worker   │  │ • FreeCAD     │  │ • ngspice     │  │
│  │ • Scheduler   │  │ • KiCad       │  │ • PlatformIO  │  │
│  │ • Registry    │  │               │  │               │  │
│  └───────────────┘  └───────────────┘  └───────────────┘  │
└────────────────────────────────────────────────────────────┘
```

**Worker Placement:**
- **AI Worker:** Always local (low latency, high throughput)
- **CAD Worker:** Remote if available (resource-intensive)
- **Electronics Worker:** Remote if available (SPICE simulations CPU-bound)
- **Hardware Runtime Worker:** Always local (physical device access)

**Execution Strategy:**
1. Scheduler analyzes graph, identifies worker requirements
2. Ray places tasks on appropriate machines
3. Cross-machine edges serialize/deserialize via Arrow
4. Execution context propagated across machines
5. Final result aggregated on coordinator

### 5.5 SPEC-025 Backward Compatibility

**Strategy:** Adapter wrappers convert SPEC-025 `NodePlugin` definitions to Universal Node Engine `NodeWorker` format.

**Wrapper Implementation:**
```python
class SPEC025NodeWrapper(NodeWorker):
    def __init__(self, legacy_plugin: SPEC025NodePlugin):
        self.legacy_plugin = legacy_plugin
        self.domain = "legacy"

    async def execute(self, inputs: dict[str, Any], context: ExecutionContext) -> dict[str, Any]:
        # Convert inputs to SPEC-025 format
        legacy_inputs = self._convert_inputs(inputs)

        # Execute legacy plugin
        legacy_output = await self.legacy_plugin.execute(legacy_inputs)

        # Convert output to Universal format
        return self._convert_output(legacy_output)
```

**Migration Path:**
1. **Phase 0-1:** Wrapper available, SPEC-025 nodes run unchanged
2. **Phase 2-4:** Gradual migration to native Universal nodes
3. **Phase 5:** Wrapper deprecated, all nodes native

---

## 6. Core Abstractions

### 6.1 NodeWorker Interface

**Purpose:** Abstract base class for all domain workers.

**Pattern Source:** `core/mascarade/router/providers/base.py` (`LLMProvider`)

**Interface Definition:**
```python
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from mascarade.node_engine.context import ExecutionContext
from mascarade.orchestrator.circuit_breaker import CircuitBreaker


@dataclass
class WorkerCapabilities:
    """Declarative worker capabilities for scheduling decisions."""
    can_parallelize: bool = False
    requires_gpu: bool = False
    max_concurrent: int = 1
    estimated_latency_ms: int = 1000
    resource_cost: dict[str, float] = field(default_factory=dict)  # {"cpu": 0.5, "memory": 100}


@dataclass
class ValidationResult:
    """Result of input validation."""
    valid: bool
    errors: list[str] = field(default_factory=list)


class NodeWorker(ABC):
    """
    Abstract base class for all domain workers in the Universal Node Engine.

    Inspired by LLMProvider pattern, adapted for node execution.
    """

    domain: str           # "ai", "cad", "electronics", "hardware"
    name: str
    version: str
    circuit_breaker: CircuitBreaker | None = None

    @abstractmethod
    async def execute(
        self,
        inputs: dict[str, Any],
        context: ExecutionContext,
    ) -> dict[str, Any]:
        """
        Execute the node with given inputs.

        Args:
            inputs: Port name → value mapping
            context: Execution context with tracing, metrics, cancellation

        Returns:
            Port name → value mapping for outputs

        Raises:
            ValidationError: Invalid inputs
            ExecutionError: Node execution failed
            CircuitBreakerError: Circuit breaker open
        """
        ...

    @abstractmethod
    async def validate(self, inputs: dict[str, Any]) -> ValidationResult:
        """
        Validate inputs before execution.

        Args:
            inputs: Port name → value mapping

        Returns:
            ValidationResult with success/error status
        """
        ...

    @abstractmethod
    def capabilities(self) -> WorkerCapabilities:
        """
        Return worker capabilities for scheduling.

        Returns:
            WorkerCapabilities with resource requirements and constraints
        """
        ...

    def on_init(self, context: ExecutionContext) -> None:
        """Lifecycle hook: called before first execution."""
        pass

    def on_destroy(self, context: ExecutionContext) -> None:
        """Lifecycle hook: called after all executions complete."""
        pass
```

**Example Implementation (AI Worker):**
```python
class LLMInferenceWorker(NodeWorker):
    domain = "ai"
    name = "llm-inference"
    version = "1.0.0"

    def __init__(self, router: Router):
        self.router = router

    async def execute(
        self,
        inputs: dict[str, Any],
        context: ExecutionContext,
    ) -> dict[str, Any]:
        prompt = inputs["prompt"]
        system = inputs.get("system", "")

        response = await self.router.send(
            [{"role": "user", "content": prompt}],
            system=system,
            strategy=Strategy.BEST,
        )

        return {
            "response": response.content,
            "model": response.model,
            "provider": response.provider,
        }

    async def validate(self, inputs: dict[str, Any]) -> ValidationResult:
        if "prompt" not in inputs:
            return ValidationResult(valid=False, errors=["Missing 'prompt' input"])
        if not isinstance(inputs["prompt"], str):
            return ValidationResult(valid=False, errors=["'prompt' must be a string"])
        return ValidationResult(valid=True)

    def capabilities(self) -> WorkerCapabilities:
        return WorkerCapabilities(
            can_parallelize=True,
            max_concurrent=5,
            estimated_latency_ms=3000,
            resource_cost={"network": 1.0},
        )
```

### 6.2 NodeTypeRegistry

**Purpose:** Centralized registration, discovery, and versioning of node types.

**Pattern Source:** `core/mascarade/agents/registry.py` (`AgentRegistry`)

**Interface Definition:**
```python
@dataclass
class NodeDefinition:
    """Metadata for a node type."""
    node_type_id: str          # "ai.llm-inference"
    display_name: str          # "LLM Inference"
    description: str
    domain: str
    version: str
    inputs: list[PortDefinition]
    outputs: list[PortDefinition]
    tags: list[str] = field(default_factory=list)
    icon: str | None = None
    documentation_url: str | None = None


class NodeTypeRegistry:
    """
    Centralized registry for node type definitions and workers.

    Inspired by AgentRegistry pattern.
    """

    def __init__(self, storage_path: Path = DEFAULT_STORAGE_PATH):
        self._nodes: dict[str, NodeDefinition] = {}
        self._workers: dict[str, NodeWorker] = {}
        self._builtin_nodes: set[str] = set()
        self.metrics = MetricsTracker()

    def register(
        self,
        node_def: NodeDefinition,
        worker: NodeWorker,
        *,
        builtin: bool = False,
    ) -> None:
        """Register a node type and its worker."""
        self._nodes[node_def.node_type_id] = node_def
        self._workers[node_def.node_type_id] = worker
        if builtin:
            self._builtin_nodes.add(node_def.node_type_id)

    def get(self, node_type_id: str) -> tuple[NodeDefinition, NodeWorker]:
        """Get node definition and worker by ID."""
        if node_type_id not in self._nodes:
            raise KeyError(f"Node type '{node_type_id}' not found")
        return self._nodes[node_type_id], self._workers[node_type_id]

    def list(self, domain: str | None = None) -> list[NodeDefinition]:
        """List all node types, optionally filtered by domain."""
        nodes = list(self._nodes.values())
        if domain:
            nodes = [n for n in nodes if n.domain == domain]
        return nodes

    def remove(self, node_type_id: str) -> None:
        """Remove a node type (only if not builtin)."""
        if node_type_id in self._builtin_nodes:
            raise ValueError(f"Cannot remove builtin node '{node_type_id}'")
        self._nodes.pop(node_type_id, None)
        self._workers.pop(node_type_id, None)

    # Persistence (mirrors AgentRegistry)
    def save(self) -> None: ...
    def load(self) -> None: ...
```

### 6.3 Graph Execution Runtime

**Purpose:** Topological sort, scheduling, and execution of node graphs.

**Pattern Source:** `core/mascarade/orchestrator/engine.py` (`Orchestrator`)

**Interface Definition:**
```python
class ExecutionMode(StrEnum):
    EAGER = "eager"        # Execute immediately when inputs available
    LAZY = "lazy"          # Execute only when outputs requested
    STEPPED = "stepped"    # Execute one node at a time (debugging)


@dataclass
class GraphResult:
    """Result of graph execution."""
    run_id: str
    success: bool
    outputs: dict[str, Any]
    execution_time_ms: float
    node_results: list[NodeResult]
    error: str | None = None


class GraphExecutionEngine:
    """
    Graph execution runtime with topological sort, parallel scheduling, and resilience.

    Inspired by Orchestrator pattern.
    """

    def __init__(
        self,
        registry: NodeTypeRegistry,
        retry_executor: RetryExecutor,
        dead_letter_store: DeadLetterStore,
    ):
        self.registry = registry
        self.retry_executor = retry_executor
        self.dead_letter_store = dead_letter_store
        self.circuit_breakers: dict[str, CircuitBreaker] = {}

    async def execute_graph(
        self,
        graph: Graph,
        mode: ExecutionMode,
        context: ExecutionContext,
    ) -> GraphResult:
        """
        Execute a graph with the specified execution mode.

        Steps:
        1. Validate graph (all nodes registered, all connections valid)
        2. Topological sort
        3. Build execution DAG
        4. Schedule and execute nodes (mode-dependent)
        5. Aggregate results
        """
        # Validation
        validation_errors = await self._validate_graph(graph)
        if validation_errors:
            return GraphResult(
                run_id=context.run_id,
                success=False,
                outputs={},
                execution_time_ms=0,
                node_results=[],
                error=f"Validation failed: {validation_errors}",
            )

        # Topological sort
        sorted_nodes = self._topological_sort(graph)

        # Execute based on mode
        if mode == ExecutionMode.EAGER:
            return await self._execute_eager(sorted_nodes, graph, context)
        elif mode == ExecutionMode.LAZY:
            return await self._execute_lazy(sorted_nodes, graph, context)
        elif mode == ExecutionMode.STEPPED:
            return await self._execute_stepped(sorted_nodes, graph, context)

    async def _execute_eager(
        self,
        sorted_nodes: list[Node],
        graph: Graph,
        context: ExecutionContext,
    ) -> GraphResult:
        """
        Eager execution: execute nodes immediately when inputs available.

        Uses asyncio.gather for parallel branch execution.
        """
        ...

    def _topological_sort(self, graph: Graph) -> list[Node]:
        """
        Topological sort using Kahn's algorithm.

        Raises:
            CycleDetectedError: Graph contains cycles
        """
        ...
```

---

## 7. Execution Model

### 7.1 Execution Modes

| Mode | Behavior | Use Case |
|------|----------|----------|
| **Eager** | Execute nodes immediately when inputs available | Production workflows, maximum throughput |
| **Lazy** | Execute only when outputs requested | Cost optimization, conditional workflows |
| **Stepped** | Execute one node at a time, pause for inspection | Debugging, interactive development |

### 7.2 Execution Context

**Purpose:** Propagate tracing, metrics, cancellation, and user context across node executions.

**Definition:**
```python
@dataclass
class ExecutionContext:
    """Execution context for graph and node execution."""
    run_id: str
    user_id: str | None
    trace_id: str
    parent_span_id: str | None
    started_at: datetime
    timeout: timedelta | None
    cancellation_token: CancellationToken
    metadata: dict[str, Any] = field(default_factory=dict)

    def create_child_span(self, operation_name: str) -> ExecutionContext:
        """Create a child context for nested operation."""
        ...
```

### 7.3 Scheduling Strategies

**1. Sequential Scheduling:**
- Execute nodes one at a time in topological order
- Simplest, predictable, but slowest
- Use case: Resource-constrained environments, debugging

**2. Parallel Branch Scheduling:**
- Execute independent branches in parallel via `asyncio.gather`
- Optimal for workflows with parallel paths
- Use case: AI chains with independent tool calls

**3. Priority-Based Scheduling:**
- Assign priorities to nodes based on:
  - Downstream dependencies (more dependents = higher priority)
  - Estimated latency (faster nodes first for early feedback)
  - User-defined priority
- Use case: Mixed-latency workflows (e.g., fast AI + slow CAD)

**4. Resource-Aware Scheduling:**
- Track available CPU, memory, GPU slots
- Schedule nodes only when resources available
- Use case: CAD/Electronics workers on resource-constrained VM

### 7.4 Execution DAG Example

**Workflow:** AI generates design → FreeCAD creates model → SPICE validates circuit

```
┌─────────────┐
│ Prompt      │
│ Template    │
└──────┬──────┘
       │
       ▼
┌─────────────┐
│ LLM         │
│ Inference   │
└──┬────┬─────┘
   │    │
   │    └──────────────┐
   │                   │
   ▼                   ▼
┌──────────────┐  ┌──────────────┐
│ Parse        │  │ Schematic    │
│ Design       │  │ Generator    │
│ Params       │  │              │
└──────┬───────┘  └──────┬───────┘
       │                 │
       │                 │
       ▼                 ▼
┌──────────────┐  ┌──────────────┐
│ FreeCAD      │  │ Netlist      │
│ Model        │  │ Generator    │
└──────┬───────┘  └──────┬───────┘
       │                 │
       │                 │
       │                 ▼
       │          ┌──────────────┐
       │          │ SPICE        │
       │          │ Simulation   │
       │          └──────┬───────┘
       │                 │
       └────────┬────────┘
                │
                ▼
         ┌──────────────┐
         │ Validation   │
         │ Report       │
         └──────────────┘
```

**Execution Order (Topological):**
1. Prompt Template
2. LLM Inference
3. Parse Design Params ∥ Schematic Generator (parallel)
4. FreeCAD Model ∥ Netlist Generator (parallel)
5. SPICE Simulation
6. Validation Report

---

## 8. Type System Architecture

### 8.1 Type Hierarchy

```
PortType (abstract)
├── PrimitiveType
│   ├── String
│   ├── Integer
│   ├── Float
│   ├── Boolean
│   ├── Bytes
│   └── JSON
├── CompositeType
│   ├── List[T]
│   ├── Dict[K, V]
│   └── Optional[T]
└── DomainType
    ├── AI Domain
    │   ├── LLMResponse
    │   ├── EmbeddingVector
    │   └── ConversationHistory
    ├── CAD Domain
    │   ├── MeshData
    │   ├── Toolpath
    │   ├── Schematic
    │   ├── PCBLayout
    │   └── BOM
    ├── Electronics Domain
    │   ├── Netlist
    │   ├── Waveform
    │   ├── DRCReport
    │   └── FirmwareBinary
    └── Hardware Domain
        ├── MIDIMessage
        ├── DMXFrame
        ├── SerialData
        └── HTTPResponse
```

### 8.2 Type Validation

**Compile-Time Validation:**
- Pydantic models for all port types
- Static type checking via mypy
- Graph validation before execution

**Runtime Validation:**
- Pydantic validation on node inputs/outputs
- Type coercion for safe conversions (e.g., `int` → `float`)
- Explicit adapters for cross-domain conversions

### 8.3 Type Coercion Rules

**Automatic Coercion (Primitive Types):**
```python
int → float          # 42 → 42.0
int → str            # 42 → "42"
str → int            # "42" → 42 (if parseable)
bool → int           # True → 1
list[T] → Optional[list[T]]
```

**Manual Adaptation (Domain Types):**
```python
LLMResponse → DesignParameters    # Via LLMResponseToDesignParametersAdapter
MeshData → ComponentGeometry      # Via MeshToGeometryAdapter
Netlist → Waveform                # Via NetlistToSimulationAdapter
```

### 8.4 Port Definition

```python
@dataclass
class PortDefinition:
    """Definition of a node port (input or output)."""
    name: str
    type: PortType
    required: bool = True
    default_value: Any | None = None
    description: str = ""

    def validate(self, value: Any) -> ValidationResult:
        """Validate a value against this port's type."""
        return self.type.validate(value)
```

---

## 9. Resilience & Reliability

### 9.1 Circuit Breaker Integration

**Pattern Source:** `core/mascarade/orchestrator/engine.py`

**Strategy:** Per-worker circuit breakers prevent cascade failures.

**Configuration:**
```python
@dataclass
class CircuitBreakerConfig:
    failure_threshold: int = 5       # Open after 5 consecutive failures
    timeout_s: float = 60.0          # Open for 60s before half-open
    success_threshold: int = 2       # Close after 2 successes in half-open
```

**States:**
- **CLOSED:** Normal operation
- **OPEN:** Failures exceeded threshold, reject all calls
- **HALF_OPEN:** Test recovery, allow limited calls

**Per-Domain Configuration:**
- **AI Worker:** `failure_threshold=3` (LLM APIs flaky)
- **CAD Worker:** `failure_threshold=1, timeout_s=300` (crashes require long recovery)
- **Electronics Worker:** `failure_threshold=2`
- **Hardware Runtime Worker:** `failure_threshold=5, timeout_s=10` (device I/O transient)

### 9.2 Retry Logic

**Pattern Source:** `core/mascarade/orchestrator/retry.py`

**Strategy:** Exponential backoff with jitter for transient failures.

**Configuration:**
```python
@dataclass
class RetryConfig:
    max_attempts: int = 3
    initial_delay_s: float = 1.0
    max_delay_s: float = 10.0
    exponential_base: float = 2.0
    jitter: bool = True
```

**Retryable Errors:**
- Network errors (connection refused, timeout)
- LLM API rate limits (429)
- Temporary resource exhaustion (503)

**Non-Retryable Errors:**
- Validation errors (invalid inputs)
- Authentication errors (401, 403)
- User cancellation

### 9.3 Dead Letter Queue

**Pattern Source:** `core/mascarade/orchestrator/dead_letter.py`

**Strategy:** Capture failed executions for manual inspection and replay.

**Schema:**
```python
@dataclass
class DeadLetterEntry:
    run_id: str
    graph_id: str
    node_id: str
    inputs: dict[str, Any]
    error: str
    timestamp: datetime
    retry_count: int
    metadata: dict[str, Any]
```

**Operations:**
- `store(entry)` — Add failed execution
- `list(filters)` — Query dead letter queue
- `replay(entry_id)` — Re-execute with original inputs
- `delete(entry_id)` — Remove entry

### 9.4 Graceful Degradation

**Strategy:** Fallback to lower-quality but available alternatives.

**Examples:**
1. **AI Worker:** If Mistral API fails, fallback to OpenAI
2. **CAD Worker:** If FreeCAD crashes, return error with partial results
3. **Hardware Runtime Worker:** If ESP32 offline, log error, continue graph execution

**Configuration:**
```python
@dataclass
class FallbackConfig:
    enabled: bool = True
    fallback_worker: str | None = None
    degraded_quality_acceptable: bool = True
```

---

## 10. Performance & Scalability

### 10.1 Performance Targets

| Metric | Target | Measured On |
|--------|--------|-------------|
| Single AI workflow (5-10 nodes) | <5s | Target VM (4 vCPU, 6.8 GiB RAM) |
| Cross-domain workflow (20 nodes) | <30s | Target VM |
| Graph validation latency | <100ms | Target VM |
| Node catalog query latency | <50ms | Target VM |
| WebSocket status update latency | <200ms | Target VM |
| Concurrent graph executions | 5+ | Target VM |

### 10.2 Optimization Strategies

**1. Parallel Branch Execution:**
- Use `asyncio.gather` for independent branches
- Example: AI workflow with 3 parallel LLM calls → 3x speedup

**2. Lazy Evaluation:**
- Skip unused branches in conditional workflows
- Example: If condition false, skip downstream 10 nodes → 50% speedup

**3. Result Caching:**
- Cache node outputs keyed by (node_type_id, inputs_hash)
- TTL: 1 hour for deterministic nodes, disabled for non-deterministic
- Storage: Redis (if available), in-memory LRU cache (fallback)

**4. Ray Distributed Execution:**
- Offload CAD/Electronics workers to dedicated machines
- Reduce local resource contention

**5. Streaming Outputs:**
- Stream LLM responses token-by-token for early downstream processing
- Stream SPICE waveforms incrementally

### 10.3 Resource Management

**Memory:**
- Limit graph size: 100 nodes max per graph
- Limit execution history: 30 days retention
- Prune old metrics: 7 days retention

**CPU:**
- Priority-based scheduling: Hardware Runtime nodes (priority 1) > AI nodes (priority 2) > CAD/Electronics (priority 3)
- CAD/Electronics workers: max 1 concurrent execution (subprocess bottleneck)

**Disk:**
- Lazy load graph definitions (load on execution request)
- Compress execution history (gzip JSON)

### 10.4 Scalability Limits

| Dimension | Current Limit | Mitigation |
|-----------|--------------|------------|
| Graph size | 100 nodes | Split into subgraphs |
| Concurrent executions | 5 | Queue additional requests |
| Total graphs in system | 1000 | Archive/delete old graphs |
| Node type registry size | 500 node types | No limit expected |

---

## 11. Observability & Monitoring

### 11.1 Metrics

**Graph-Level Metrics:**
- Execution count (success/failure)
- Execution time (p50, p95, p99)
- Node count distribution
- Domain distribution

**Node-Level Metrics:**
- Execution count per node type
- Execution time per node type
- Error rate per node type
- Resource usage per node type

**Worker-Level Metrics:**
- Worker utilization (% time executing)
- Circuit breaker state transitions
- Retry attempts per worker

**System-Level Metrics:**
- Active graphs
- Queue depth
- CPU/memory/disk usage
- WebSocket connection count

### 11.2 Tracing

**OpenTelemetry Integration:**
- Each graph execution → trace
- Each node execution → span
- Distributed tracing across Ray workers

**Trace Attributes:**
```python
{
    "graph.id": "graph-123",
    "graph.execution.run_id": "run-456",
    "node.type_id": "ai.llm-inference",
    "node.id": "node-789",
    "worker.domain": "ai",
    "execution.mode": "eager",
}
```

### 11.3 Logging

**Structured Logging (JSON):**
```python
{
    "timestamp": "2026-03-15T10:30:00Z",
    "level": "INFO",
    "logger": "mascarade.node_engine",
    "message": "Node executed successfully",
    "run_id": "run-456",
    "node_id": "node-789",
    "duration_ms": 1234,
}
```

**Log Levels:**
- **DEBUG:** Input/output values, detailed execution steps
- **INFO:** Node start/completion, graph start/completion
- **WARNING:** Retry attempts, fallback activations
- **ERROR:** Node failures, validation errors
- **CRITICAL:** Circuit breaker opens, system failures

### 11.4 Dashboards (mascarade-cockpit)

**Graph Dashboard:**
- Active executions (real-time)
- Recent executions (last 24h)
- Execution time trend
- Error rate trend

**Node Dashboard:**
- Node type execution count (bar chart)
- Node type latency (heatmap)
- Error rate by node type (table)

**Worker Dashboard:**
- Worker utilization (gauge)
- Circuit breaker states (status indicators)
- Resource usage (time series)

---

## 12. Security Architecture

### 12.1 Threat Model

| Threat | Impact | Mitigation |
|--------|--------|------------|
| **Malicious graph injection** | Arbitrary code execution | Graph schema validation, node type whitelist |
| **Prompt injection (AI Worker)** | Unintended LLM behavior | Input sanitization, system prompt isolation |
| **Resource exhaustion** | DoS via large graphs | Graph size limits, execution timeouts |
| **Credential leakage** | Exposed API keys in logs | Redact sensitive fields, credential management |
| **Unauthorized execution** | Execution by non-authenticated users | API authentication, per-graph ACLs |

### 12.2 Authentication & Authorization

**API Layer (TypeScript):**
- JWT-based authentication for all endpoints
- Per-user graph ownership
- Role-based access control (RBAC):
  - **Admin:** Full access
  - **User:** CRUD own graphs, execute own graphs
  - **Viewer:** Read-only access

**Graph ACLs:**
```python
@dataclass
class GraphACL:
    owner_id: str
    readers: list[str]       # User IDs with read access
    executors: list[str]     # User IDs with execute access
    public: bool = False     # Public graphs visible to all
```

### 12.3 Input Validation

**Graph Validation:**
- Schema validation via Pydantic
- Node type existence check
- Connection type compatibility check
- Cycle detection
- Size limits (max 100 nodes)

**Node Input Validation:**
- Per-node validation via `NodeWorker.validate()`
- Type validation via Pydantic
- Range checks for numeric inputs
- String length limits

### 12.4 Secrets Management

**API Keys:**
- Store in environment variables (not committed to code)
- Rotate every 90 days
- Redact from logs (replace with `***`)

**User Credentials:**
- Never stored in graph definitions
- Passed via execution context
- Encrypted in transit (HTTPS/WSS)

---

## 13. Rollout Strategy

### 13.1 Phase Dependency Graph

```
Phase 0 (Foundations) — 3-4 weeks
    ├── Type system
    ├── Graph runtime
    ├── NodeWorker interface
    ├── Registry
    └── Persistence
    │
    ▼
Phase 1 (AI Worker) — 2-3 weeks
    ├── LLM nodes
    ├── Embedding nodes
    ├── Chain nodes
    └── Router integration
    │
    ▼
═══════════════════════════════════════════
    MVP GATE (1 week validation)
═══════════════════════════════════════════
    │
    ├─────────────────┬─────────────────┐
    ▼                 ▼                 ▼
Phase 2           Phase 3          Phase 4
(CAD Worker)      (Elec Worker)    (Hardware Worker)
3-4 weeks         3-4 weeks        4-5 weeks
    │                 │                 │
    └─────────────────┴─────────────────┘
                      │
                      ▼
            Phase 5 (Cross-Domain Integration)
                  3-4 weeks
                      │
                      ▼
                 PRODUCTION
```

### 13.2 Phase 0: Foundations (3-4 weeks)

**Goals:**
- Core abstractions implemented and tested
- Graph execution proven with mock nodes
- Persistence round-trip validated

**Deliverables:**
1. `core/mascarade/node_engine/types.py` — Type system
2. `core/mascarade/node_engine/worker.py` — NodeWorker base class
3. `core/mascarade/node_engine/registry.py` — Registry
4. `core/mascarade/node_engine/runtime.py` — Execution engine
5. `core/mascarade/node_engine/graph.py` — Graph models
6. `core/mascarade/node_engine/persistence.py` — Serialization
7. `core/mascarade/node_engine/context.py` — Execution context
8. `api/src/routes/node-engine.ts` — REST/WS endpoints

**Success Criteria:**
- [ ] All primitive and composite types validate correctly
- [ ] Mock graph (10 nodes) executes in all 3 modes
- [ ] Graph save/load round-trip preserves full fidelity
- [ ] 90%+ test coverage on core abstractions

**Risks:**
- Type system complexity underestimated → Simplify to MVP types
- Ray integration issues → Fallback to local-only for Phase 0

### 13.3 Phase 1: AI Worker (2-3 weeks)

**Goals:**
- AI domain nodes operational
- Router integration validated
- End-to-end AI workflow executes

**Deliverables:**
1. `core/mascarade/node_engine/workers/ai/worker.py`
2. `core/mascarade/node_engine/workers/ai/types.py`
3. 8 AI node types (LLM, embedding, chain, template, transform, conditional, memory, agent)
4. Integration tests with Mascarade Router

**Success Criteria:**
- [ ] LLM inference node calls all supported providers via Router
- [ ] Chain-of-thought workflow (5 nodes) executes end-to-end
- [ ] Execution time <5s for typical AI workflow
- [ ] Circuit breaker, retry logic validated with failing LLM API

**Risks:**
- Router API changes → Coordinate with Router team
- LLM latency exceeds targets → Add caching, parallel calls

### 13.4 MVP Gate (1 week)

**Purpose:** Validate core architecture before expanding to other domains.

**Criteria:**
1. Type system validated with AI domain types
2. Graph execution proven with 5+ AI workflows
3. Plugin API stable (no breaking changes anticipated)
4. Registry operational (register, get, list, persist)
5. Persistence round-trip validated
6. API surface functional (REST + WebSocket)
7. Resilience tested (circuit breakers, retry, dead letter)
8. Performance baseline met (<5s for AI workflow)

**Decision:**
- **Pass:** Proceed to Phases 2-4 in parallel
- **Fail:** Iterate on Phase 0/1, delay other phases

### 13.5 Phase 2: CAD Worker (3-4 weeks)

**Deliverables:**
- CAD domain worker with FreeCAD, KiCad integration
- 12-15 CAD node types
- Integration with existing `freecad_agent.py`, `kicad_agent.py`

**Success Criteria:**
- [ ] FreeCAD node generates 3D model from parameters
- [ ] KiCad node generates PCB layout from schematic
- [ ] CAD-specific port types validated

### 13.6 Phase 3: Electronics Worker (3-4 weeks)

**Deliverables:**
- Electronics domain worker with SPICE, PCB DRC
- 10-12 Electronics node types
- Integration with existing `spice_agent.py`

**Success Criteria:**
- [ ] SPICE simulation node runs circuit analysis
- [ ] PCB DRC node validates design rules
- [ ] Waveform analysis validated

### 13.7 Phase 4: Hardware Runtime Worker (4-5 weeks)

**Deliverables:**
- Hardware Runtime domain worker with ESP32, MIDI, DMX, serial
- 8-10 Hardware node types
- Real-time control loop support

**Success Criteria:**
- [ ] ESP32 control node communicates with hardware
- [ ] MIDI I/O node sends/receives MIDI messages
- [ ] Real-time loop executes within timing constraints

### 13.8 Phase 5: Cross-Domain Integration (3-4 weeks)

**Deliverables:**
- Type adapters between all domains
- Federated execution via Ray
- End-to-end cross-domain workflows

**Success Criteria:**
- [ ] AI → CAD → Electronics → Hardware workflow executes end-to-end
- [ ] Federated execution distributes workers across multiple machines
- [ ] Cross-domain workflow <30s execution time

---

## 14. Success Criteria

### 14.1 Overall Initiative Success

- [ ] All 4 domain workers operational with domain-specific node types and port types
- [ ] Cross-domain workflows execute end-to-end
- [ ] SPEC-025 backward compatibility maintained via adapter wrappers
- [ ] Performance targets met on target VM infrastructure
- [ ] Observability integrated with mascarade-cockpit dashboards
- [ ] Documentation complete: architectural spec, phase specs, API reference
- [ ] Zero security incidents during rollout
- [ ] User adoption: 10+ active users, 50+ graphs created, 500+ executions

### 14.2 Per-Phase Success Criteria

**Phase 0:**
- [ ] Type system completeness (primitives, composites, domain types)
- [ ] Graph execution runtime (topological sort, 3 modes, parallel branches)
- [ ] NodeWorker interface stable
- [ ] Registry functional (register, get, list, persist)
- [ ] 90%+ test coverage

**Phase 1:**
- [ ] LLM inference via Router
- [ ] Embedding generation
- [ ] Chain-of-thought workflow
- [ ] <5s execution for AI workflow
- [ ] Circuit breaker, retry validated

**MVP Gate:**
- [ ] All Phase 0 + Phase 1 criteria met
- [ ] No blocking issues identified
- [ ] Stakeholder approval

**Phase 2-4:**
- [ ] Domain-specific nodes operational
- [ ] Domain-specific port types validated
- [ ] Integration with existing agents

**Phase 5:**
- [ ] Cross-domain type adapters
- [ ] End-to-end cross-domain workflow
- [ ] Federated execution via Ray
- [ ] <30s execution for cross-domain workflow

### 14.3 Non-Functional Success Criteria

- [ ] **Reliability:** 99% uptime (24/7 monitoring)
- [ ] **Performance:** 95% of executions meet latency targets
- [ ] **Scalability:** Support 1000 graphs, 500 node types, 5 concurrent executions
- [ ] **Security:** Zero credential leaks, zero unauthorized executions
- [ ] **Maintainability:** 90%+ test coverage, comprehensive documentation
- [ ] **Extensibility:** New domain added in <2 weeks

---

## 15. Appendices

### 15.1 Glossary

| Term | Definition |
|------|------------|
| **Domain** | High-level category of functionality (AI, CAD, Electronics, Hardware Runtime) |
| **Worker** | Python class implementing domain-specific node execution |
| **Node Type** | Template for a node (e.g., "LLM Inference") with defined inputs/outputs |
| **Node Instance** | Concrete instance of a node type in a graph |
| **Port** | Input or output connection point on a node |
| **Edge** | Connection between two ports |
| **Graph** | Directed acyclic graph (DAG) of node instances and edges |
| **Execution Context** | Runtime context (tracing, metrics, cancellation) for graph execution |
| **Type Adapter** | Converter between incompatible port types |
| **Circuit Breaker** | Fault tolerance pattern preventing cascade failures |

### 15.2 References

| Document | Location |
|----------|----------|
| **SPEC-025** | `.auto-claude/specs/025-unified-node-engine-architecture/spec.md` |
| **Router Pattern** | `core/mascarade/router/providers/base.py` |
| **Registry Pattern** | `core/mascarade/agents/registry.py` |
| **Orchestrator Pattern** | `core/mascarade/orchestrator/engine.py` |
| **KiCad Agent** | `core/mascarade/agents/kicad_agent.py` |
| **FreeCAD Agent** | `core/mascarade/agents/freecad_agent.py` |
| **SPICE Agent** | `core/mascarade/agents/spice_agent.py` |

### 15.3 Revision History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0.0 | 2026-03-15 | Mascarade Architecture Team | Initial draft |

### 15.4 Contact

For questions or clarifications, contact the Mascarade Architecture Team.

---

**END OF SPECIFICATION**
