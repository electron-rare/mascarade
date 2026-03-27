# Mascarade Project Roadmap — Universal Node Engine Initiative

**Document:** Updated Project Roadmap
**Date:** 2026-03-27
**Version:** 1.0
**Reference:** SPEC-029 (Universal Node Engine Architecture)
**Predecessor:** SPEC-025 (Unified Node Engine Architecture — Kill_LIFE)

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Current Status (2026-03-27 Audit)](#2-current-status-2026-03-27-audit)
3. [Ecosystem Repositories](#3-ecosystem-repositories)
4. [Phase Overview](#4-phase-overview)
5. [Phase Dependency Graph](#5-phase-dependency-graph)
6. [Phase Details](#6-phase-details)
7. [MVP Gate: Phase 0-1](#7-mvp-gate-phase-0-1)
8. [M-009 AI Novel Engine Dependency](#8-m-009-ai-novel-engine-dependency)
9. [Infrastructure Constraints](#9-infrastructure-constraints)
10. [Parallelism Opportunities](#10-parallelism-opportunities)
11. [Risk Register](#11-risk-register)

---

## 1. Executive Summary

This roadmap incorporates the SPEC-029 Universal Node Engine initiative into the broader Mascarade project plan. The Node Engine introduces a multi-domain, graph-based execution architecture spanning AI, CAD, Electronics, and Hardware Runtime domains. It is delivered across six phases (Phase 0–5) with an explicit MVP gate after Phase 1.

The initiative evolves SPEC-025's Kill_LIFE-focused node engine into a universal platform, replacing ad-hoc agent orchestration with a formal, type-safe, graph-structured execution model. All durations are expressed as relative estimates in weeks to accommodate schedule flexibility.

---

## 2. Current Status (2026-03-27 Audit)

Implementation audit conducted on 2026-03-27. Completion percentages reflect code that exists and is functional, not just declared or scaffolded.

| Phase | Name | Completion | Summary |
|-------|------|------------|---------|
| Phase 0 | Foundations | **~85%** | Core abstractions largely in place. Type system, registry, persistence, and NodeWorker are near-complete. Execution modes and streaming support missing. API layer not yet implemented. |
| Phase 1 | AI Worker | **~60%** | AIWorker class, types, and Router integration done. Streaming nodes, function calling, agent dispatch execution, and error handling nodes missing. |
| Phase 2 | CAD Worker | **~40%** | CADWorker base with IPC-2221 calculations done. FreeCAD/KiCad workers declared with MCP pattern. Actual tool execution unverified. Mesh ops and toolpath are placeholders. |
| Phase 3 | Electronics Worker | **~10%** | Only config dataclasses and capability declarations exist. No actual SPICE simulation, DRC, firmware compilation, or component execution. |
| Phase 4 | Hardware Runtime Worker | **~20%** | ESP32 client and DMX controller exist as infrastructure. No HardwareWorker class or worker nodes. MIDI worker declared but no execution. |
| Phase 5 | Cross-Domain Integration | **~10%** | Base adapter class exists. No actual cross-domain adapters implemented. |

### MVP Readiness (Phase 0 + Phase 1)

The MVP gate (Phase 0-1) is approximately **~75%** complete by code presence, but key gaps remain:

- **Execution modes** (eager/lazy/stepped) not implemented — blocks Go/No-Go criterion #2
- **REST/WebSocket API** not implemented — blocks Go/No-Go criterion #5
- **Streaming support** missing — affects LLM latency management in graph execution
- **Agent dispatch and error handling nodes** missing from AI Worker

---

## 3. Ecosystem Repositories

Five repositories participate in the Universal Node Engine initiative:

| Repository | Role in Node Engine Initiative |
|------------|-------------------------------|
| **mascarade** (core/) | Primary host — Python backend containing the Graph Execution Runtime, NodeWorker base class, domain workers (AI, CAD, Electronics, Hardware), type system, node registry, persistence layer, and cross-domain adapters |
| **mascarade** (api/) | API layer — TypeScript/Hono service exposing graph CRUD, execution triggers, real-time status streaming via REST/WebSocket, and node catalog endpoints |
| **crazy_life** | Web surface — ReactFlow-based graph editor UI for visual workflow composition, node palette, connection drawing, and execution monitoring |
| **mascarade-cockpit** | Observability — SvelteKit monitoring dashboard for Node Engine execution traces, worker health, graph run history, and cross-domain flow visualization |
| **docker-studio-ai** | Infrastructure — Docker Compose orchestration, Dockerfiles for worker containers, service discovery configuration, and deployment tooling for the VM environment |

---

## 4. Phase Overview

| Phase | Name | Duration (weeks) | Depends On | MVP? | Status |
|-------|------|-------------------|------------|------|--------|
| Phase 0 | Foundations | 4–6 | — | ✅ MVP | ⚠️ ~85% |
| Phase 1 | AI Worker | 3–4 | Phase 0 | ✅ MVP | ⚠️ ~60% |
| Phase 2 | CAD Worker | 3–5 | Phase 0 | | ⚠️ ~40% |
| Phase 3 | Electronics Worker | 3–5 | Phase 0 | | ❌ ~10% |
| Phase 4 | Hardware Runtime Worker | 4–6 | Phase 0 | | ❌ ~20% |
| Phase 5 | Cross-Domain Integration | 4–6 | Phases 1–4 | | ❌ ~10% |

**Total estimated duration:** 14–21 weeks (with parallelism), 21–32 weeks (fully sequential).

---

## 5. Phase Dependency Graph

```
                    ┌───────────┐
                    │  Phase 0  │
                    │Foundations│
                    └─────┬─────┘
                          │
            ┌─────────────┼─────────────┬─────────────┐
            │             │             │             │
      ┌─────▼─────┐ ┌────▼─────┐ ┌────▼──────┐ ┌────▼───────┐
      │  Phase 1  │ │ Phase 2  │ │  Phase 3  │ │  Phase 4   │
      │ AI Worker │ │CAD Worker│ │Electronics│ │  Hardware   │
      │   (MVP)   │ │          │ │  Worker   │ │Runtime Work.│
      └─────┬─────┘ └────┬─────┘ └────┬──────┘ └────┬───────┘
            │             │             │             │
            └─────────────┼─────────────┼─────────────┘
                          │             │
                    ┌─────▼─────────────▼─┐
                    │      Phase 5        │
                    │ Cross-Domain Integ. │
                    └─────────────────────┘
```

**Key constraint:** Phase 0 is the universal dependency. All domain workers (Phase 1–4) require stable Phase 0 abstractions. Phase 5 requires all domain workers to be complete.

---

## 6. Phase Details

### Phase 0 — Foundations (4–6 weeks) — ~85% Complete

**Objective:** Establish the core abstractions — type system, graph execution runtime, NodeWorker plugin API, node registry, and persistence layer.

**Milestones:**
- ✅ M-0.1: Universal type system with primitive, composite, and domain-extension points (95%)
- ⚠️ M-0.2: Graph execution runtime with topological sort, parallel branch scheduling, and 3 execution modes (eager, lazy, stepped) — *runtime 85%, execution modes (eager/lazy/stepped) missing*
- ✅ M-0.3: NodeWorker abstract base class with lifecycle hooks, validation, and capability declarations (90%)
- ✅ M-0.4: Node registry with registration, discovery, and versioning (95%)
- ✅ M-0.5: Persistence layer with JSON serialization and graph versioning (90%)
- ❌ M-0.6: REST/WebSocket API endpoints for graph operations (api/) — *not implemented*

**Deliverables:**
- `core/mascarade/node_engine/` package (types, worker, registry, runtime, graph, persistence, context)
- `api/src/routes/node-engine.ts`

**Risk Factors:**
- **Type system design lock-in** (medium): Poor type system decisions in Phase 0 cascade to all subsequent phases. Mitigation: review against all 4 domain worker specs before finalizing.
- **Execution runtime complexity** (medium): Graph scheduling with parallel branches, circuit breakers, and retry logic is non-trivial. Mitigation: model on proven Orchestrator patterns.

---

### Phase 1 — AI Worker (3–4 weeks) — ~60% Complete

**Objective:** Implement the AI domain worker, integrating with the existing Mascarade Router, Orchestrator, and AgentRegistry.

**Milestones:**
- ⚠️ M-1.1: LLM inference nodes (prompt → response via LLMProvider) — *AIWorker class and types done, streaming nodes missing*
- ❌ M-1.2: Embedding nodes (text/image embedding via provider system) — *not implemented*
- ❌ M-1.3: Reasoning chain nodes (multi-step, conditional branching) — *function calling and error handling nodes missing*
- ✅ M-1.4: Router integration nodes (strategy selection: cheapest/fastest/best/specific)
- ❌ M-1.5: Orchestrator nodes (sequential/parallel/pipeline execution modes) — *agent dispatch execution missing*

**Deliverables:**
- `core/mascarade/node_engine/workers/ai/` package
- AI-specific port types: `LLMResponse`, `EmbeddingVector`, `ChatMessage`, `PromptTemplate`, `TokenUsage`

**Risk Factors:**
- **Router/Orchestrator coupling** (low): AI Worker depends on existing infrastructure that is already stable.
- **LLM latency in graph execution** (medium): Long-running LLM calls can block graph progress. Mitigation: streaming support and timeout management built into Phase 0 runtime.

---

### Phase 2 — CAD Worker (3–5 weeks) — ~40% Complete

**Objective:** Wrap existing FreeCAD and KiCad agent capabilities into composable graph nodes.

**Milestones:**
- ⚠️ M-2.1: FreeCAD nodes (document creation, parametric modeling, script execution, export) — *declared with MCP pattern, actual tool execution unverified*
- ⚠️ M-2.2: KiCad nodes (schematic generation, PCB layout, DRC, manufacturing export) — *declared with MCP pattern, actual tool execution unverified*
- ❌ M-2.3: Toolpath generation nodes (G-code, CNC optimization) — *placeholder only*
- ❌ M-2.4: Mesh operation nodes (STL import/export, boolean operations) — *placeholder only*

**Deliverables:**
- `core/mascarade/node_engine/workers/cad/` package — *CADWorker base with IPC-2221 calculations implemented*
- CAD-specific port types: `MeshData`, `Toolpath`, `BOM`, `GCode`, `SchematicData`, `PCBLayout`, `CADDocument`

**Risk Factors:**
- **FreeCAD/KiCad process isolation** (medium): Both tools run as external processes with their own memory footprint. On a 6.8 GiB VM, concurrent runs risk OOM. Mitigation: worker-level resource limits and sequential scheduling for heavy operations.
- **Binary data handling** (low): Mesh and manufacturing files are large binary blobs. Mitigation: binary port type with streaming support from Phase 0.

---

### Phase 3 — Electronics Worker (3–5 weeks) — ~10% Complete

**Objective:** Implement electronics simulation, PCB validation, firmware compilation, and component management nodes.

**Milestones:**
- ❌ M-3.1: SPICE simulation nodes (ngspice-based netlist generation, transient/AC/DC analysis) — *config dataclasses only, no execution*
- ❌ M-3.2: PCB design rule checking nodes (KiCad CLI integration) — *capability declarations only*
- ❌ M-3.3: Firmware compilation nodes (ESP-IDF/PlatformIO build targets) — *not implemented*
- ❌ M-3.4: Component library nodes (part lookup, BOM management) — *not implemented*

**Deliverables:**
- `core/mascarade/node_engine/workers/electronics/` package
- Electronics-specific port types: `Netlist`, `Schematic`, `Waveform`, `FirmwareBinary`, `ComponentSpec`, `DRCReport`

**Risk Factors:**
- **ngspice convergence failures** (medium): SPICE simulations can diverge on complex circuits. Mitigation: convergence debugging nodes and sensible timeout defaults.
- **Toolchain dependencies** (medium): ESP-IDF and PlatformIO require significant disk space and build-time resources. Mitigation: Docker-based build containers with cached toolchains.

---

### Phase 4 — Hardware Runtime Worker (4–6 weeks) — ~20% Complete

**Objective:** Implement real-time hardware control nodes for ESP32, MIDI, DMX, and serial communication.

**Milestones:**
- ⚠️ M-4.1: ESP32 control nodes (device discovery, GPIO, sensor reading, OTA updates) — *ESP32 client exists as infrastructure, no worker nodes*
- ❌ M-4.2: MIDI I/O nodes (input/output, CC mapping, clock sync) — *MIDI worker declared, no execution*
- ⚠️ M-4.3: DMX lighting nodes (universe management, fixture control, scene programming) — *DMX controller exists as infrastructure, no worker nodes*
- ❌ M-4.4: Serial communication nodes (protocol adapters, data parsing) — *not implemented*
- ❌ M-4.5: Real-time control loop nodes (PID controllers, safety interlocks) — *not implemented*

**Deliverables:**
- `core/mascarade/node_engine/workers/hardware/` package
- Hardware-specific port types: `MIDIMessage`, `DMXFrame`, `SerialData`, `GPIOState`, `SensorReading`, `DeviceDescriptor`

**Risk Factors:**
- **Real-time constraints on VM** (high): The VM environment (4 vCPU, 6.8 GiB RAM, VMware virtualization) introduces jitter incompatible with strict real-time requirements. Mitigation: offload timing-critical loops to ESP32 firmware; use VM only for supervision and configuration.
- **Hardware absence during development** (medium): Hardware may not be physically connected during CI/testing. Mitigation: mock device layer with simulated responses.
- **Safety** (medium): Incorrect GPIO or DMX commands can damage hardware. Mitigation: safety interlock nodes with configurable limits and confirmation gates.

---

### Phase 5 — Cross-Domain Integration (4–6 weeks) — ~10% Complete

**Objective:** Enable workflows that span multiple domains through type adapters, unified orchestration, and federated execution.

**Milestones:**
- ❌ M-5.1: Cross-domain type adapters (AI↔CAD, AI↔Electronics, CAD↔Electronics, Electronics↔Hardware, Hardware↔AI) — *base adapter class exists, no actual adapters*
- ❌ M-5.2: Unified orchestration pipeline with domain-aware scheduling — *not implemented*
- ❌ M-5.3: Federated graph execution via Ray and P2P cluster — *not implemented*
- ❌ M-5.4: End-to-end workflow examples (AI-designed part → electronics validation → hardware deployment) — *not implemented*
- ❌ M-5.5: Cross-domain observability in mascarade-cockpit — *not implemented*

**Deliverables:**
- `core/mascarade/node_engine/adapters/` package
- `core/mascarade/node_engine/federation.py`
- Cross-domain workflow templates

**Risk Factors:**
- **Type adapter correctness** (high): Incorrect cross-domain type conversions produce silent data corruption. Mitigation: explicit adapter validation with round-trip testing.
- **Distributed execution complexity** (high): Federated graphs across multiple machines add network partitioning, serialization, and ordering challenges. Mitigation: start with single-machine multi-process, graduate to Ray distribution.
- **Integration surface area** (medium): Phase 5 touches all prior phases. Mitigation: stable Phase 0 interfaces and versioned adapter contracts.

---

## 7. MVP Gate: Phase 0-1

Phases 0 and 1 together constitute the **Minimum Viable Product (MVP)**. The MVP must be validated before committing resources to Phases 2–5.

### Go/No-Go Criteria

The MVP is considered successful if **all** of the following are met:

| # | Criterion | Measurement |
|---|-----------|-------------|
| 1 | **Core type system is stable** | No breaking changes to `PortType` definitions for 2+ weeks after Phase 0 completion |
| 2 | **Graph execution runtime handles real workloads** | Successfully executes a 10+ node AI workflow graph with parallel branches, retries, and error handling |
| 3 | **AI Worker integrates with existing infrastructure** | LLM inference nodes route through existing Router/Provider system; Orchestrator nodes compose with existing agent patterns |
| 4 | **Performance is acceptable** | Graph compilation < 100ms for 50-node graphs; node execution overhead < 10ms per node (excluding worker time) |
| 5 | **API layer is functional** | Graph CRUD, execution trigger, and real-time status streaming work end-to-end through Hono API |
| 6 | **Persistence round-trips cleanly** | Graphs can be saved, loaded, and re-executed with identical results |
| 7 | **Developer experience is viable** | A new AI node can be implemented and registered in < 30 minutes by a developer familiar with the codebase |

### Decision Points

- **GO:** All 7 criteria met → proceed to Phase 2–4 (domain workers) in parallel
- **CONDITIONAL GO:** 5–6 criteria met → proceed with scope reduction, address gaps in parallel
- **NO-GO:** < 5 criteria met → re-evaluate architecture, revisit Phase 0 design decisions

---

## 8. M-009 AI Novel Engine Dependency

M-009 (AI Novel Engine) is an independent project milestone that shares infrastructure with the Node Engine initiative. Specifically, M-009 depends on:

- LLM inference capabilities (existing Router/Provider infrastructure)
- Agent orchestration (existing Orchestrator engine)
- Potentially, the AI Worker nodes from Phase 1

### Option A: Sequential Start (M-009 First)

```
M-009 AI Novel Engine ──────────────► Phase 0 ──► Phase 1 ──► ...
      (8–12 weeks)                   (4–6 wk)   (3–4 wk)
```

**Pros:**
- M-009 validates AI infrastructure patterns before Phase 0 codifies them
- Lessons learned from M-009 inform NodeWorker API design
- No resource contention between initiatives

**Cons:**
- Delays Node Engine initiative by 8–12 weeks
- M-009 may evolve patterns that diverge from Node Engine needs

### Option B: Parallel Start

```
M-009 AI Novel Engine ──────────────────────────────────►
      (8–12 weeks)
Phase 0 ──► Phase 1 ──► Phase 2/3/4 ──► Phase 5
(4–6 wk)   (3–4 wk)    (parallel)      (4–6 wk)
```

**Pros:**
- No delay to either initiative
- Phase 0 type system and runtime are M-009-independent
- Phase 1 AI Worker can incorporate M-009 learnings mid-flight

**Cons:**
- Resource contention on the VM (both initiatives are compute-heavy)
- Risk of duplicate effort if M-009 patterns conflict with Phase 1 decisions
- Requires coordination overhead to keep designs aligned

### Recommendation

**Option B (Parallel Start)** is recommended with the following conditions:

1. Phase 0 starts immediately — it has no dependency on M-009
2. Phase 1 (AI Worker) starts after Phase 0, incorporating any M-009 learnings available at that time
3. Weekly sync between M-009 and Node Engine teams to detect pattern divergence early
4. If M-009 reveals fundamental issues with the Router/Provider architecture, Phase 1 pauses to absorb changes

---

## 9. Infrastructure Constraints

The Mascarade ecosystem runs on a single VM with limited resources. The Node Engine must be designed within these constraints.

### Current Infrastructure (from machine state report 2026-03-05)

| Resource | Capacity | Current Usage | Available |
|----------|----------|---------------|-----------|
| **CPU** | 4 vCPU | High (load avg peaks at 71.13) | Limited — contention with 27 active containers |
| **RAM** | 6.8 GiB | 4.2 GiB used + 3.6/4.0 GiB swap | Critical — swap at ~90% |
| **Disk** | 246 GiB | 175 GiB used (74%) | ~70 GiB free |
| **Docker images** | — | 92.76 GiB (60 GiB reclaimable) | Pruning needed |
| **Network** | 192.168.0.119 | Ports 22, 80 exposed | LAN-only, no public ingress |

### Docker Deployment Model

- All services deploy via Docker Compose from the project root
- Core service on port 8100, API on port 3000
- Node Engine workers run as part of the core container (in-process) or as separate containers (for isolation)
- Resource-heavy workers (FreeCAD, KiCad, ngspice) should use `deploy.resources` limits to prevent OOM

### Infrastructure Implications per Phase

| Phase | Resource Impact | Mitigation |
|-------|----------------|------------|
| Phase 0 | Low — runtime and type system are lightweight | None needed |
| Phase 1 | Medium — LLM inference uses existing LiteLLM/Ollama infrastructure | Share existing LLM containers |
| Phase 2 | High — FreeCAD/KiCad processes are memory-intensive | Container resource limits; sequential scheduling |
| Phase 3 | Medium — ngspice is CPU-intensive but low memory | CPU affinity; timeout enforcement |
| Phase 4 | Low — hardware I/O is lightweight; USB passthrough needed | Docker device mapping for serial/USB |
| Phase 5 | Variable — depends on which domains are combined | Dynamic resource allocation; deferred execution for heavy cross-domain graphs |

### Recommended Infrastructure Actions

1. **Before Phase 0:** Prune unused Docker images to reclaim ~60 GiB disk space
2. **Before Phase 2:** Increase VM RAM to 12–16 GiB if multi-stack operation continues
3. **Before Phase 4:** Configure USB passthrough for hardware devices in VMware settings
4. **Before Phase 5:** Evaluate Ray cluster deployment for federated execution (may require additional VMs)

---

## 10. Parallelism Opportunities

### Phase-Level Parallelism

After Phase 0 completes, Phases 1–4 can run in parallel:

```
Week  1  2  3  4  5  6  7  8  9 10 11 12 13 14 15 16 17 18 19 20
      ├──Phase 0──────────┤
                           ├──Phase 1 (MVP)──┤
                           ├──Phase 2 (CAD)────────┤
                           ├──Phase 3 (Elec.)──────┤
                           ├──Phase 4 (Hardware)─────────┤
                                                          ├──Phase 5──────────┤
```

**Maximum parallelism:** 4 domain workers developed simultaneously after Phase 0.

**Practical parallelism:** 2 workers in parallel is recommended given:
- Single VM with 4 vCPU limits concurrent development/testing
- Developer bandwidth constraints
- Phase 1 (MVP) should receive priority focus

### Recommended Parallel Groups

| Group | Phases | Rationale |
|-------|--------|-----------|
| Group A (priority) | Phase 1 + Phase 2 | AI Worker is MVP; CAD Worker leverages existing agents |
| Group B | Phase 3 + Phase 4 | Electronics and Hardware are independent domains |

### Within-Phase Parallelism

- **Phase 0:** Type system and runtime can be developed in parallel by different contributors
- **Phase 1:** LLM nodes and embedding nodes are independent; reasoning chains depend on both
- **Phase 2:** FreeCAD and KiCad nodes are fully independent
- **Phase 5:** Type adapters for different domain pairs are independent

---

## 11. Risk Register

| Risk | Phase | Severity | Likelihood | Mitigation |
|------|-------|----------|------------|------------|
| Type system design requires breaking changes after Phase 0 | Phase 0 | High | Medium | Pre-validate type system against all domain worker requirements before freezing |
| VM resource exhaustion during multi-worker testing | Phase 2–4 | High | High | Container resource limits; sequential testing; consider RAM upgrade |
| M-009 and Node Engine architectural divergence | Phase 1 | Medium | Medium | Weekly sync meetings; shared design review |
| FreeCAD/KiCad process crashes in Docker | Phase 2 | Medium | Medium | Circuit breakers; process isolation; crash recovery in worker |
| Real-time hardware control unreliable on VM | Phase 4 | High | High | Offload timing-critical work to ESP32; VM handles supervision only |
| Cross-domain type adapters introduce data corruption | Phase 5 | High | Low | Round-trip testing; explicit validation at every adapter boundary |
| Scope creep from domain-specific feature requests | All | Medium | High | Strict phase boundaries; defer non-essential features to post-Phase 5 |
| Single-developer bottleneck | All | Medium | Medium | Prioritize Phase 0-1 MVP; defer Phase 2-4 based on capacity |

---

*This roadmap is a living document. It will be updated as phases complete and new information emerges from implementation.*

*Last audit: 2026-03-27 — implementation status verified against codebase.*
