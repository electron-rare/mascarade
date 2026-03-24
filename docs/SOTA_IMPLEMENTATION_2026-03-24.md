# SOTA 2026 Implementation Plan — Mascarade

> Research completed 2026-03-24. Covers RAG, Agents, Fine-tuning.

## 1. RAG (Implemented)

### Done
- **Hybrid search**: dense + BM25 with RRF fusion (Qdrant native)
- **LLM reranking**: cross-encoder approximation via router
- **CRAG**: corrective RAG with SearXNG web fallback on low confidence
- **SearXNG MCP**: web search tool for agents
- **Ingestion**: 242 docs / 853 chunks via Ollama bge-m3 (1024 dims)

### TODO
- **Contextual chunking** (Anthropic): LLM prepends context to each chunk at indexing time. 49% less retrieval failures. Requires LLM call per chunk during ingestion.
- **Parent-child chunking**: small chunks for retrieval, return parent for generation context
- **HyDE**: generate hypothetical answer document before embedding query
- **Cross-encoder reranking**: replace LLM reranking with mxbai-rerank or Qwen3-reranker via Ollama (faster, more accurate)

## 2. Agents (Partially implemented)

### Done
- 26 agents with auto-routing
- Agent gates (pre/post execution, evidence tracking)
- A2A protocol v0.3
- MCP 10+ servers

### TODO — Priority order

#### P0: Plan-and-Execute orchestrator
Top-level orchestrator that:
1. Receives user request
2. Plans a DAG of subtasks (which agents, what order, what parallel)
3. Executes via scatter-gather for parallel branches
4. Re-plans on failure

Implementation: new `mascarade/orchestrator/planner.py`

#### P1: Agent delegation with capability registry
Each agent declares capabilities. When an agent can't handle a subtask, it delegates to a specialist.

Implementation: extend `AgentRegistry` with capability vectors, add `delegate()` method to Agent.

#### P2: Hierarchical domain clusters
Group 26 agents into clusters:
- **General**: agent-zero, summarizer, writer, brainstorm, classifier, translator, planner
- **Code**: coder, firmware-agent
- **Electronics**: kicad-designer, spice-expert, components-expert, pcb-routing-kicad, freecad-designer
- **Ops**: analyst, knowledge-scribe, doc-agent, qa-agent, pm-agent, architect-agent
- **Creative**: image-generator

Each cluster has a supervisor that routes within the cluster.

#### P3: AoT (Algorithm of Thoughts) prompting
Single-LLM-call structured reasoning. Replace Tree of Thoughts (109 calls) with AoT (1 call, same quality). Add as a prompt template in the skill system.

#### P4: Agent memory (Letta-style)
Per-agent working memory with paging. Context = RAM (current window), Storage = Qdrant (long-term). Agent manages what to page in/out.

## 3. Fine-tuning

### Current state
- 3-stage pipeline: CPT -> SFT -> RLVR
- LoRA/QLoRA, DPO, SimPO, KTO, GRPO
- 14 domain mini-models (mascarade-esp32, mascarade-pio, mascarade-spice, mascarade-iot, etc.)

### TODO — Priority order

#### P0: Switch default alignment to SimPO
Replace DPO with SimPO as default preference optimization. +6.4 pts AlpacaEval, length-normalized.

#### P1: QDoRA default
Use `use_dora=True` with QLoRA for all fine-tuning. Rank 16, target_modules="all-linear".

#### P2: GRPO for reasoning agents
Train KiCad/SPICE/components agents with GRPO + verifiable rewards:
- KiCad: DRC pass/fail as reward
- SPICE: simulation convergence as reward
- Code: unit test pass/fail as reward

Use Unsloth FP8 on KXKM-AI RTX 4090.

#### P3: Domain continued pre-training (ChipNeMo approach)
1. Collect domain corpus: datasheets, KiCad docs, SPICE manuals, embedded code
2. GaLore continued pre-training on Qwen2.5-7B (single 4090, 1-2 weeks)
3. Domain-specific tokenizer extension (component names, EDA commands)
4. Then SFT + SimPO + GRPO

#### P4: Distillation pipeline
Use Mistral Large / Claude as teacher to generate CoT responses.
Rejection sampling (16-64 candidates, keep top 1-2).
Distill into domain 3-8B student models.

## Hardware Budget (RTX 4090 24GB)

| Task | VRAM | Time |
|------|------|------|
| QDoRA SFT 7B | ~10 GB | 2-4 days |
| SimPO 7B | ~10 GB | 1-2 days |
| GRPO 7B (Unsloth FP8) | ~15 GB | 2-4 days |
| GaLore continued pretrain 7B | ~20 GB | 1-2 weeks |
| bge-m3 embeddings | ~2 GB | minutes |
| Ollama inference devstral/qwen | ~8 GB | realtime |

## Implementation Order

| Phase | What | Effort | Impact |
|-------|------|--------|--------|
| **Done** | RAG hybrid + reranking + CRAG | - | High |
| **Week 1** | SimPO default, QDoRA, Plan-and-Execute | Med | High |
| **Week 2** | Agent delegation, domain clusters | Med | High |
| **Week 3** | GRPO KiCad/SPICE, AoT prompting | Med | Med |
| **Week 4** | Contextual chunking, cross-encoder rerank | Med | Med |
| **Month 2** | ChipNeMo DAPT, distillation, agent memory | High | High |

## Sources

### RAG
- Anthropic Contextual Retrieval (49% less failures)
- Qdrant 1.15+ native BM25 + RRF
- mxbai-rerank-large-v2 (outperforms Cohere on BEIR)
- CRAG pattern (Correct/Ambiguous/Incorrect routing)

### Agents
- Plan-and-Execute (LangGraph)
- AoT - Algorithm of Thoughts (Microsoft Research, 25x fewer tokens than ToT)
- A-HMAD debate (30%+ factual error reduction)
- Letta/MemGPT memory architecture
- A2A + MCP (tool + agent interop)

### Fine-tuning
- SimPO (+6.4 AlpacaEval over DPO)
- GRPO/DAPO (DeepSeek-R1, online RL)
- ChipNeMo (5x model reduction, domain-adapted)
- Unsloth FP8 (GRPO on 7B in 15GB)
- GaLore (7B pretrain on single 24GB GPU)
