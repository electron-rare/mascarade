# OSS Research — Mascarade (2026-03-16)

Consolidated open-source landscape analysis covering all major Mascarade subsystems. Categorized findings with comparison tables, maintenance status, and actionable recommendations.

---

## Table of Contents

1. [LLM Routing & Provider Management](#1-llm-routing--provider-management)
2. [Agent Orchestration](#2-agent-orchestration)
3. [P2P Mesh Networking](#3-p2p-mesh-networking)
4. [Caching Layer](#4-caching-layer)
5. [Circuit Breaker / Resilience](#5-circuit-breaker--resilience)
6. [Fine-Tuning Pipeline](#6-fine-tuning-pipeline)
7. [Evaluation & Benchmarking](#7-evaluation--benchmarking)
8. [Observability & Tracing](#8-observability--tracing)
9. [Documentation & Diagramming](#9-documentation--diagramming)
10. [Summary: Action Matrix](#10-summary-action-matrix)

---

## 1. LLM Routing & Provider Management

**Mascarade status:** Custom router with 10 providers, 6 strategies (cheapest/fastest/best/specific/domain/routellm), circuit breakers, health monitoring, fallback chains.

### Comparison Table

| Project | Stars | Last Release | Providers | Routing Strategies | Async | License |
|---------|-------|-------------|-----------|-------------------|-------|---------|
| **Mascarade Router** | — | Active | 10 | 6 (strategy-based) | ✅ | Proprietary |
| **LiteLLM** | 38k | Mar 2026 | 100+ | Load balancing, fallback | ✅ | MIT |
| **Dify** | 100k+ | Mar 2026 | 20+ | None (manual selection) | ✅ | Apache 2.0 |

### Key Findings

- **LiteLLM** is the only direct competitor. It supports ~100 providers vs Mascarade's 10 but lacks strategy-based routing (cheapest/fastest/best), domain detection, and integrated circuit breakers.
- **Mascarade's router is differentiated** — no OSS project combines strategy-based routing, domain detection, and circuit breakers in one layer.
- LiteLLM's value is as a **provider abstraction library** (not proxy) — using `litellm.completion()` could replace the maintenance burden of 10 individual provider implementations.

### Recommendation

| Action | Project | What to Do | Priority | Effort |
|--------|---------|------------|----------|--------|
| **Consider** | LiteLLM | Use as provider backend library; keep Mascarade's strategy router intact | P2 | Medium |
| **Reject** | Dify | Architectural mismatch — platform vs personal system | — | — |

---

## 2. Agent Orchestration

**Mascarade status:** Agent registry, multi-agent dispatch (sequential/parallel/pipeline), P2P mesh networking for distributed agents.

### Comparison Table

| Project | Stars | Last Release | Agent Model | Multi-Agent | State Mgmt | P2P | License |
|---------|-------|-------------|-------------|-------------|------------|-----|---------|
| **Mascarade** | — | Active | Registry-based | ✅ | Basic | ✅ | Proprietary |
| **CrewAI** | 46k | Mar 2026 | Role/Goal/Backstory | ✅ | Memory (S/L/Entity) | ❌ | MIT |
| **LangGraph** | 26k | Mar 2026 | Graph nodes | ✅ | Checkpointing | ❌ | MIT |
| **AutoGen** | 50k | Maintenance mode | Conversational | ✅ | Conversation | ❌ | MIT |
| **Semantic Kernel** | 27k | Mar 2026 | Plugin-based | ✅ | Planner state | ❌ | MIT |
| **OpenHands** | N/A | Active | Code-first loop | Limited | Workspace | ❌ | MIT |

### Key Findings

- **CrewAI** has the most structured agent mental model (role/goal/backstory) — worth adopting for agent definitions.
- **LangGraph** excels at graph-based workflow patterns and state checkpointing — useful for complex multi-step orchestrations.
- **AutoGen** is in maintenance mode; being merged into Microsoft Agent Framework (GA Q1 2026). Skip.
- **Semantic Kernel** is C#-first, Azure-centric. Wrong ecosystem for Python-native Mascarade.
- **Mascarade's P2P mesh is unique** — no evaluated framework offers distributed agent communication.

### Recommendation

| Action | Project | What to Do | Priority | Effort |
|--------|---------|------------|----------|--------|
| **Inspire** | CrewAI | Adopt role/goal/backstory pattern for agent definitions; study memory abstractions | P3 | Low |
| **Inspire** | LangGraph | Adopt graph-based workflow patterns; study state checkpointing for resilience | P3 | Low |
| **Reject** | AutoGen | Maintenance mode, C#-focused successor | — | — |
| **Reject** | Semantic Kernel | Wrong ecosystem (C#/Azure) | — | — |
| **Reference** | OpenHands | Benchmark for agentic code-first autonomy comparisons | — | — |

---

## 3. P2P Mesh Networking

**Mascarade status:** Dual-backend — custom asyncio TCP transport (primary) + py-libp2p with trio↔asyncio bridge (secondary). 17 modules, 4 live nodes (VM, GrosMac, CILS, Tower).

### Comparison Table

| Library | Stars | Last Release | Language | Async | Discovery | Maintenance |
|---------|-------|-------------|----------|-------|-----------|-------------|
| **Custom TCP** (current) | — | Active | Python | ✅ | Custom | ✅ Self-owned |
| **py-libp2p** (current) | 400 | Jan 2026 | Python/trio | ✅ | DHT/gossipsub | ⚠️ Sporadic |
| **ZeroMQ (pyzmq)** | 3.8k | Mar 2026 | Python | ✅ | ❌ External | ✅ Active |
| **NATS (nats-py)** | 900 | Mar 2026 | Python | ✅ | ✅ Built-in | ✅ Active |
| **gRPC** | 43k | Mar 2026 | Python | ✅ | ❌ External | ✅ Active |
| **Ray** | 35k | Mar 2026 | Python | ✅ | ✅ Built-in | ✅ Active |

### Key Findings

- Custom TCP transport is production-proven with bounded timeouts for the current 4-node mesh.
- **NATS** is the best migration target if the mesh grows beyond 10 nodes (native clustering, queue groups, JetStream persistence).
- ZeroMQ lacks discovery — would need external mechanism.
- Ray/gRPC/Dask are overkill for a 4-node personal mesh.

### Recommendation

| Action | Project | What to Do | Priority | Effort |
|--------|---------|------------|----------|--------|
| **Keep** | Custom TCP + libp2p | No change needed for 4 nodes | — | — |
| **Plan** | NATS | Migration target if mesh grows >10 nodes | Future | High |

---

## 4. Caching Layer

**Mascarade status:** 3-tier cache — L1 (in-memory LRU) → L2 (Redis async) → L3 (GPTCache semantic). Clean `CacheBackend` ABC with `MultiTierCache` orchestrator and backfill on hits.

### Comparison Table

| Component | Current | Alternative | Stars | Migration | Benefit |
|-----------|---------|------------|-------|-----------|---------|
| L2 store | Redis 7 | **Valkey** | 18k | Drop-in (Docker swap) | License clarity (BSD) |
| L2 store | Redis 7 | **DragonflyDB** | 30k | Drop-in (Docker swap) | 25x perf on benchmarks |
| L1 cache | Custom LRU | **cachetools** | 2.3k | Low | Marginal — current works fine |
| Full stack | Custom | **cashews** | 500 | High | Overkill — architecture is solid |

### Key Findings

- The multi-tier cache architecture is **well-designed** — no framework replacement needed.
- **Valkey** is a free win: Linux Foundation fork of Redis, wire-compatible, BSD licensed. Just swap the Docker image.
- **DragonflyDB** if performance becomes a bottleneck (25x faster, same wire protocol).

### Recommendation

| Action | Project | What to Do | Priority | Effort |
|--------|---------|------------|----------|--------|
| **Adopt** | Valkey | Swap Docker image `redis:7` → `valkey/valkey:8` | P2 | 1h |
| **Monitor** | DragonflyDB | Upgrade path if Valkey perf insufficient | Future | 1h |
| **Reject** | cashews/cachetools | Current architecture is solid | — | — |

---

## 5. Circuit Breaker / Resilience

**Mascarade status:** Uses `aiobreaker>=1.2.0,<2` — **last release May 2021, abandoned**. Wrapped in `CircuitBreakerManager` in `core/mascarade/resilience/circuit_breaker.py`.

### Comparison Table

| Library | Stars | Last Release | Async | Maintenance | Migration Effort |
|---------|-------|-------------|-------|-------------|-----------------|
| **aiobreaker** (current) | 150 | May 2021 | ✅ | ❌ Abandoned | — |
| **Custom implementation** | — | — | ✅ | ✅ Self-owned | Low (~120 lines) |
| **aiomisc** (circuit_breaker) | 400 | Mar 2026 | ✅ | ✅ Active | Low |
| **purgatory** | 40 | Oct 2024 | ✅ | ⚠️ Low activity | Medium |
| **pybreaker** | 600 | Jun 2025 | ❌ sync | ✅ Active | High (async wrap) |
| **tenacity** + state machine | 6.5k | Mar 2026 | ✅ | ✅ Active | Medium |

### Key Findings

- **aiobreaker is a security/maintenance risk** — no Python 3.12/3.13 testing, no patches since 2021.
- Mascarade's `CircuitBreakerManager` already abstracts away aiobreaker — only internals need to change.
- A custom ~120 line implementation would: eliminate the abandoned dep, add missing `success_count` tracking, add per-breaker timeout config, keep the same `CircuitBreakerManager` API.
- **pybreaker** is sync-only — incompatible with Mascarade's async-first architecture.

### Recommendation

| Action | Project | What to Do | Priority | Effort |
|--------|---------|------------|----------|--------|
| **Adopt** | Custom implementation | Replace aiobreaker internals, keep `CircuitBreakerManager` API | **P0** | 2-4h |
| **Monitor** | aiomisc / purgatory | Fallback options if custom impl proves insufficient | — | — |
| **Reject** | pybreaker | Sync-only, incompatible | — | — |

---

## 6. Fine-Tuning Pipeline

**Mascarade status:** 36 Python scripts, 13 domains, ~143K training examples. Unsloth + TRL backend. Key hotspots: `batch_local.py` (1628 lines), `model_selector.py` (1746 lines). Zero tests.

### Comparison Table

| Framework | Stars | Last Release | GPU Req | GRPO/DPO | Multi-GPU | Config Style | Unsloth Backend |
|-----------|-------|-------------|---------|----------|-----------|-------------|-----------------|
| **Unsloth** (current) | 25k | Mar 2026 | Single | ✅ | ❌ | Python API | — |
| **LLaMA-Factory** | 67k | Mar 2026 | Single+ | ✅ | ✅ | YAML + Web UI | ✅ |
| **Axolotl** | 8k | Feb 2026 | Single+ | ✅ | ✅ | YAML | ❌ |
| **TRL** (current dep) | 12k | Mar 2026 | Any | ✅ | ✅ | Python API | ❌ |
| **OpenRLHF** | 7k | Mar 2026 | Multi | ✅ | ✅ Ray | Python | ❌ |
| **torchtune** | 5k | Mar 2026 | Any | ✅ | ✅ | Config files | ❌ |

### Evaluation Tools

| Tool | Stars | Purpose | Fit |
|------|-------|---------|-----|
| **lm-evaluation-harness** | 8k+ | 60+ benchmarks, YAML custom tasks | Direct adoption for model eval |
| **DeepEval** | 5k+ | LLM-as-judge, hallucination detection | Output quality eval |
| **RLHFlow** | 1.4k | Domain-specific reward model training | Alignment refinement |

### Key Findings

- **Unsloth** remains the best single-GPU training backend (12x faster, lowest VRAM).
- **LLaMA-Factory** uses Unsloth as backend and adds YAML-driven orchestration — would reduce `batch_local.py` (1628 lines) to YAML configs.
- **Axolotl** is a viable alternative but smaller community (8k vs 67k stars).
- **OpenRLHF** is for multi-node RLHF at scale — future consideration when P2P mesh supports distributed training.
- **SimPO** (NeurIPS 2024): +6.4 AlpacaEval 2 over DPO, no reference model needed, recommended alignment starting point.

### Recommendation

| Action | Project | What to Do | Priority | Effort |
|--------|---------|------------|----------|--------|
| **Keep** | Unsloth | Continue as core training backend | — | — |
| **Adopt** | LLaMA-Factory | Layer on top for YAML-driven orchestration; replace hardcoded scripts | **P1** | 1-2 weeks |
| **Adopt** | lm-evaluation-harness | Standardize model evaluation with 60+ benchmarks | P2 | 3-5 days |
| **Adopt** | DeepEval | Add LLM-as-judge output quality evaluation | P2 | 2-3 days |
| **Reject** | Axolotl | Redundant with LLaMA-Factory (smaller community) | — | — |
| **Reject** | torchtune | Too low-level, less mature | — | — |
| **Plan** | OpenRLHF | Multi-node RLHF when hardware scales | Future | High |

---

## 7. Evaluation & Benchmarking

**Mascarade status:** No standardized evaluation framework. Ad-hoc benchmarking via custom scripts.

### Comparison Table

| Tool | Stars | Focus | Integration | License |
|------|-------|-------|-------------|---------|
| **lm-evaluation-harness** | 8k+ | 60+ standard benchmarks, YAML custom tasks | CLI + Python API | MIT |
| **DeepEval** | 5k+ | LLM-as-judge, hallucination, faithfulness | Python API | Apache 2.0 |
| **RLHFlow** | 1.4k | Domain-specific reward models | Python | MIT |

### Recommendation

Adopt **lm-evaluation-harness** for standardized benchmarks and **DeepEval** for output quality metrics. Together they cover both capability measurement and generation quality.

---

## 8. Observability & Tracing

**Mascarade status:** Langfuse + OpenTelemetry integration in `core/mascarade/observability/`. 3+ modules.

### Comparison Table

| Tool | Stars | Focus | Already Integrated | Recommendation |
|------|-------|-------|-------------------|----------------|
| **Langfuse** | 8k+ | LLM tracing, evaluation, prompt management | ✅ Yes | Keep — high-value, already compatible |
| **OpenTelemetry** | 5k+ | General distributed tracing | ✅ Yes | Keep — industry standard |
| **LangSmith** | N/A | LangChain-specific tracing | ❌ | Skip — ecosystem lock-in |

### Recommendation

**No changes needed.** Langfuse + OpenTelemetry is the right combination. Langfuse provides LLM-specific tracing; OpenTelemetry provides general observability. Both are actively maintained and already integrated.

---

## 9. Documentation & Diagramming

**Mascarade status:** Markdown-based docs, no standardized diagramming. Ad-hoc architecture diagrams.

### Comparison Table

| Tool | Stars | Purpose | Fit | License |
|------|-------|---------|-----|---------|
| **Mermaid** | 75k+ | Versioned diagrams in Markdown, zero infra | All repos | MIT |
| **D2** | 18k | Diagrams-as-code, more readable than draw.io | Architecture maps | MPL 2.0 |
| **Structurizr** | 3k | C4 model as code, architecture + dependency maps | Architecture | Apache 2.0 |
| **React Flow** | 25k | Interactive graph/workflow editor UI | crazy_life, Kill_LIFE | MIT |

### Recommendation

| Action | Project | What to Do | Priority | Effort |
|--------|---------|------------|----------|--------|
| **Adopt** | Mermaid | Standard for all sequence diagrams and feature maps in Markdown | P3 | Low |
| **Prototype** | D2 or Structurizr | Evaluate for architecture cartography if Mermaid is too compact | Future | Low |
| **Adopt** | React Flow | Standard UI for workflow visualization/editing (crazy_life) | P3 | Medium |

---

## 10. Summary: Action Matrix

### Immediate Actions (P0-P1)

| # | Action | Subsystem | Project | Effort | Impact |
|---|--------|-----------|---------|--------|--------|
| 1 | Replace aiobreaker with custom async circuit breaker | Resilience | Custom | 2-4h | Eliminates abandoned dependency |
| 2 | Add LLaMA-Factory as fine-tuning orchestration layer | Fine-Tuning | LLaMA-Factory | 1-2 weeks | Major complexity reduction (replaces 1600+ line scripts) |

### Short-Term (P2)

| # | Action | Subsystem | Project | Effort | Impact |
|---|--------|-----------|---------|--------|--------|
| 3 | Swap Redis → Valkey Docker image | Caching | Valkey | 1h | License clarity (BSD) |
| 4 | Adopt lm-evaluation-harness for model benchmarks | Evaluation | lm-eval-harness | 3-5 days | Standardized evaluation |
| 5 | Adopt DeepEval for output quality metrics | Evaluation | DeepEval | 2-3 days | Hallucination detection, LLM-as-judge |
| 6 | Evaluate LiteLLM as provider abstraction library | Routing | LiteLLM | Medium | Reduce provider maintenance (10 classes → 1 library) |

### Medium-Term (P3)

| # | Action | Subsystem | Project | Effort | Impact |
|---|--------|-----------|---------|--------|--------|
| 7 | Adopt CrewAI role/goal/backstory agent pattern | Orchestration | CrewAI | Low | Better agent mental model |
| 8 | Study LangGraph graph-based workflows + checkpointing | Orchestration | LangGraph | Low | Resilient complex orchestrations |
| 9 | Adopt Mermaid for all documentation diagrams | Documentation | Mermaid | Low | Versioned, zero-infra diagrams |
| 10 | Adopt React Flow for workflow UI | Frontend | React Flow | Medium | Interactive workflow editing |

### Future / Monitor

| # | Action | Subsystem | Trigger |
|---|--------|-----------|---------|
| 11 | NATS for P2P mesh | P2P | Mesh grows >10 nodes |
| 12 | DragonflyDB for caching | Caching | Redis/Valkey perf insufficient |
| 13 | OpenRLHF for multi-node RLHF | Fine-Tuning | Multi-GPU cluster available |
| 14 | Microsoft Agent Framework | Orchestration | GA release, evaluate Python SDK maturity |

### Rejected (with rationale)

| Project | Category | Reason |
|---------|----------|--------|
| Dify | Orchestration | Platform vs personal system — architectural mismatch |
| AutoGen | Orchestration | Maintenance mode, C#-focused successor |
| Semantic Kernel | Orchestration | C#-first, Azure-centric, wrong ecosystem |
| Axolotl | Fine-Tuning | Redundant with LLaMA-Factory (smaller community) |
| torchtune | Fine-Tuning | Too low-level, less mature multi-node |
| NeMo | Fine-Tuning | Overkill for current hardware (single RTX 4090) |
| LitGPT | Fine-Tuning | Redundant with Unsloth |
| MLRun/ZenML | Orchestration | Conflicts with existing orchestration patterns |
| pybreaker | Resilience | Sync-only, incompatible with async-first architecture |
| cashews | Caching | Overkill — current multi-tier architecture is solid |

---

*Sources: docs/research/OSS_PROJECTS_2026-03-11.md, docs/research/SOTA_FINETUNING_RESEARCH_2026-03-11.md, docs/research/LLM_ROUTING_ORCHESTRATION_2026-03-16.md, docs/research/P2P_CACHE_FINETUNE_CIRCUITBREAKER_2026-03-16.md, docs/audit/MULTI_REPO_OPEN_SOURCE_SURVEY_2026-03-11.md*
