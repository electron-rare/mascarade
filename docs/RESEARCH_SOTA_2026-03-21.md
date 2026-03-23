# State-of-the-Art Research Report — March 2026

> Date: 2026-03-21 | Project: Mascarade | Author: Claude Opus 4.6 + Clems

---

## 1. Agentic Frameworks

The agentic AI framework landscape has consolidated around several major players, each with distinct architectural philosophies.

### Top Frameworks

| Framework | Maintainer | Architecture | Key Differentiator |
|-----------|-----------|-------------|-------------------|
| **LangGraph** | LangChain | Stateful DAG with cycles | Persistence, human-in-the-loop, streaming |
| **CrewAI** | CrewAI Inc | Role-based multi-agent | Simple API, delegated tasks, crew memory |
| **Microsoft Agent Framework** | Microsoft | Multi-agent orchestration | Successor to AutoGen, enterprise-grade |
| **Agno** | Agno.com | Lightweight agent toolkit | Fast, model-agnostic, structured outputs |
| **OpenAI Agents SDK** | OpenAI | Tool-use + handoffs | Guardrails, tracing, built-in tool calling |
| **Claude Agent SDK** | Anthropic | Tool-use + extended thinking | Claude Code integration, MCP-native |
| **Google ADK** | Google | Agent-to-agent native | A2A protocol, Vertex AI integration |

### Key Patterns

- **DAG Execution**: Most frameworks converge on directed graph execution (nodes = LLM calls or tools, edges = conditional routing). LangGraph pioneered this; Node Engine in mascarade follows the same pattern.
- **Tool Use**: Universal adoption of function calling / tool use as the primary agent capability.
- **Memory**: Short-term (conversation), long-term (vector store), and episodic (Mem0-style) memory tiers are becoming standard.
- **Planning**: ReAct, Plan-and-Execute, and tree-of-thought planning are the dominant strategies. LangGraph's `create_react_agent` is the most widely adopted.

### Mascarade Positioning

Mascarade occupies a unique niche: **P2P mesh + domain-specialized agents**. No major framework combines peer-to-peer distributed inference with domain-specific agent specialization (electronics, mechanical, acoustics). The closest comparison is Exo for distributed inference, but Exo lacks the agent orchestration layer.

**References:**
- LangGraph: https://github.com/langchain-ai/langgraph
- CrewAI: https://github.com/crewai-inc/crewAI
- Microsoft Agent Framework: https://github.com/microsoft/agents
- Agno: https://github.com/agno-agi/agno
- OpenAI Agents SDK: https://github.com/openai/openai-agents-python
- Claude Agent SDK: https://docs.anthropic.com/en/docs/agents-and-tools/claude-code/sdk
- Google ADK: https://github.com/google/adk-python

---

## 2. MCP Protocol (Model Context Protocol)

### Current Spec

- **Version**: 2025-06-18 (latest stable)
- **Transport**: Streamable HTTP replaced the previous SSE transport. Single endpoint (`POST /mcp`) handles all communication via JSON-RPC 2.0.
- **Session management**: Optional `Mcp-Session-Id` header for stateful interactions.
- **Capabilities**: Tools, Resources, Prompts, Sampling, Roots, Elicitation.

### Ecosystem

- **Thousands of MCP servers** available across the ecosystem (file systems, databases, APIs, SaaS tools).
- **Major adopters**: Claude Code, Cursor, Windsurf, VS Code (GitHub Copilot), JetBrains, Zed.
- **Governance**: Transferred to Linux Foundation's **AI & AI Foundation (AAIF)** for vendor-neutral stewardship.

### Mascarade Status

- **MCP Client**: Implemented and connected to 7+ industrial servers (FreeCAD, KiCad, filesystem, Git, etc.).
- **MCP Server**: Scaffold created to expose mascarade agents as MCP tools. Target file: `core/mascarade/mcp/server.py`. Tools: `list_agents`, `run_agent`, `search_knowledge_base`, `orchestrate`, `list_providers`.

**References:**
- MCP Spec: https://spec.modelcontextprotocol.io/specification/2025-06-18/
- MCP Python SDK: https://pypi.org/project/mcp/
- MCP Server Registry: https://github.com/modelcontextprotocol/servers
- AAIF Announcement: https://www.linuxfoundation.org/press/linux-foundation-launches-ai-and-ai-foundation

---

## 3. A2A Protocol (Agent-to-Agent)

### Specification

Google's A2A protocol defines how AI agents discover and communicate with each other, complementary to MCP (which is agent-to-tool).

- **Agent Card**: Published at `/.well-known/agent.json`, describes agent capabilities, skills, authentication, and supported modes.
- **Task Lifecycle**: `submitted` → `working` → `input-required` → `completed` | `failed` | `canceled`
- **Message Format**: Parts-based (text, file, data), supports streaming via SSE.
- **Authentication**: OAuth 2.0, API key, or custom schemes declared in the Agent Card.

### SDK

- **Python SDK**: `a2a-sdk` on PyPI, provides both client and server implementations.
- **Interoperability**: Designed to work alongside MCP; agents use A2A for agent-agent delegation and MCP for tool access.

### Mascarade Status

- Basic A2A implementation created: Agent Card generation from the agent registry, task lifecycle management, and delegation between mascarade agents.
- Target: Enable external agents (Google ADK, OpenAI Agents) to discover and delegate tasks to mascarade's domain-specialized agents.

**References:**
- A2A Spec: https://google.github.io/A2A/
- A2A GitHub: https://github.com/google/A2A
- A2A Python SDK: https://pypi.org/project/a2a-sdk/

---

## 4. LLM Routing

### Architecture Patterns

Two complementary layers have emerged:

| Layer | Purpose | Tools |
|-------|---------|-------|
| **Gateway / Proxy** | Unified API, cost tracking, rate limiting, caching, fallback | LiteLLM, Helicone, Portkey, Martian |
| **Router / Classifier** | Intelligent model selection based on query complexity | RouteLLM, Not Diamond, Unify.ai |

### Best Practice

Deploy **both layers together**: a router selects the optimal model, and the gateway handles the actual API call with observability and fallback.

```
User Query → Router (classify complexity) → Gateway (LiteLLM) → Provider API
                                                ↓
                                          Cost tracking + caching
```

### Mascarade Status

- **Custom Router**: 11 providers with strategy-based selection (cost, speed, quality).
- **LiteLLM Provider**: Added as a provider, enabling access to 100+ models through a single integration.
- **Planned**: ML-based routing (RouteLLM integration) for automatic complexity classification.

**References:**
- LiteLLM: https://github.com/BerriAI/litellm
- RouteLLM: https://github.com/lm-sys/RouteLLM
- Helicone: https://github.com/Helicone/helicone
- Not Diamond: https://github.com/Not-Diamond/notdiamond-python

---

## 5. Distributed AI Inference

### Key Projects

| Project | Architecture | Discovery | Model Partitioning |
|---------|-------------|-----------|-------------------|
| **Exo** | Ring topology | mDNS auto-discovery | Dynamic tensor partitioning |
| **Petals** | BitTorrent-style | Relay servers | Layer-by-layer collaborative |
| **LocalAI** | libp2p mesh | DHT + PubSub | Full model per node |
| **vLLM** | Centralized | Manual config | Tensor parallel + pipeline parallel |

### Exo Deep Dive

Most relevant to mascarade's architecture:
- **Dynamic tensor partitioning**: Splits models across heterogeneous devices (mix Apple Silicon + NVIDIA GPUs).
- **Auto-discovery**: mDNS-based peer discovery, similar to mascarade's cluster manager.
- **Supported models**: LLaMA, Mistral, Qwen, Gemma, DeepSeek up to 405B parameters.
- **No master node**: Fully decentralized coordination.

### Mascarade Status

- **P2P Mesh**: 13 modules (DHT, PubSub, Relay, Tasks, Stream Forwarding, etc.) providing the networking layer.
- **Exo Provider**: Added to the router, enabling distributed inference of 70B+ models across the heterogeneous cluster (photon, KXKM-AI, grosmac).
- **Cluster Manager**: mDNS + heartbeat-based discovery with resource-aware scheduling (VRAM, CPU, latency).

**References:**
- Exo: https://github.com/exo-explore/exo
- Petals: https://github.com/bigscience-workshop/petals
- LocalAI: https://github.com/mudler/LocalAI
- vLLM: https://github.com/vllm-project/vllm

---

## 6. Fine-Tuning & Alignment

### Training Frameworks

| Framework | Specialty | Key Feature |
|-----------|----------|------------|
| **Unsloth** | Memory-efficient fine-tuning | 2x faster, 60% less VRAM via custom CUDA kernels |
| **LLaMA-Factory** | Unified fine-tuning UI | 100+ models, web UI, all methods in one place |
| **Axolotl** | Config-driven training | YAML-based, extensive preset library |
| **TRL** | HuggingFace official | SFT, DPO, KTO, SimPO, GRPO, PPO |

### Post-Training Alignment Evolution

The field has moved rapidly beyond RLHF:

```
RLHF (2022) → DPO (2023) → SimPO / KTO (2024) → GRPO / DAPO (2025) → RLVR (2025-26)
```

| Method | Data Required | Key Advantage |
|--------|--------------|---------------|
| **DPO** | Preference pairs (chosen/rejected) | No reward model needed |
| **SimPO** | Preference pairs | Simpler than DPO, uses average log-prob as reward |
| **KTO** | Binary feedback (good/bad) | Works with unpaired data, easier to collect |
| **GRPO** | Group of completions | DeepSeek's method, self-generated rewards |
| **DAPO** | Group of completions | Dynamic sampling, clip-higher, no overlong penalty |
| **RLVR** | Verifiable rewards | Uses external verifiers (code exec, math, DRC) |

### RLVR (Reinforcement Learning with Verifiable Rewards)

The most promising frontier for domain-specialized models: use automated verification (KiCad DRC checks, SPICE simulation, FEM analysis) as reward signals. This enables training without human preference data.

### Mascarade Status

- **8-phase pipeline**: research → prepare → train → evaluate → DPO → publish → monitor → iterate.
- **DPO/SimPO/KTO**: Implemented in the reinforcer module using TRL.
- **RLVR scaffold**: Created for domain-specific verification (KiCad DRC as verifiable reward for electronics design).
- **Unsloth integration**: Used for memory-efficient training on RTX 4090.

**References:**
- Unsloth: https://github.com/unslothai/unsloth
- LLaMA-Factory: https://github.com/hiyouga/LLaMA-Factory
- TRL: https://github.com/huggingface/trl
- Axolotl: https://github.com/axolotl-ai-cloud/axolotl
- DPO Paper: https://arxiv.org/abs/2305.18290
- SimPO Paper: https://arxiv.org/abs/2405.14734
- KTO Paper: https://arxiv.org/abs/2402.01306
- GRPO (DeepSeek): https://arxiv.org/abs/2402.03300
- DAPO Paper: https://arxiv.org/abs/2503.14476

---

## 7. Observability

### LLM Observability Landscape

| Tool | Focus | OpenTelemetry | Self-hosted |
|------|-------|--------------|-------------|
| **Langfuse** | LLM traces, prompt management | Export via OTEL | Yes (Docker) |
| **OpenLLMetry** | Auto-instrumentation for LLM SDKs | Native OTEL | N/A (library) |
| **Arize Phoenix** | Evaluation + tracing | Export | Yes |
| **Helicone** | Gateway + observability | Partial | Yes |
| **Lunary** | Agent tracing | Partial | Yes |

### Industry Convergence

The industry is converging on **OpenTelemetry (OTEL)** as the standard for LLM observability:
- **Semantic conventions** for GenAI are now part of the OTEL spec (gen_ai.* attributes).
- **OpenLLMetry** provides zero-config auto-instrumentation: a single `init()` call instruments all major LLM SDKs (anthropic, openai, mistral, cohere, etc.) and exports traces/metrics to any OTEL-compatible backend.
- The **LGTM stack** (Loki + Grafana + Tempo + Mimir/Prometheus) provides a complete open-source observability backend.

### Mascarade Status

- **OpenLLMetry**: Integrated with single-line init, auto-instrumenting all LLM provider calls.
- **Full LGTM stack**: Grafana (8 dashboards) + Prometheus + Loki + Tempo + OTEL Collector.
- **Langfuse**: Connected via ClickHouse backend for prompt management and cost tracking.
- **30+ services** instrumented with health checks and metrics export.

**References:**
- Langfuse: https://github.com/langfuse/langfuse
- OpenLLMetry: https://github.com/traceloop/openllmetry
- Arize Phoenix: https://github.com/Arize-AI/phoenix
- OTEL GenAI Semantic Conventions: https://opentelemetry.io/docs/specs/semconv/gen-ai/
- Grafana LGTM: https://grafana.com/oss/

---

## Summary — Mascarade's Position in the Landscape

Mascarade sits at the intersection of several cutting-edge trends, with a unique combination that no single competing framework offers:

| Capability | Mascarade | Closest Competitor |
|-----------|-----------|-------------------|
| P2P distributed inference | Native mesh (13 modules) | Exo (inference only) |
| Domain-specialized agents | 4 domain agents (electronics, mech, acoustics, optics) | None |
| Multi-provider routing | 11+ providers with strategy selection | LiteLLM (proxy only, no strategy) |
| Fine-tuning pipeline | 8 phases including DPO/SimPO/KTO/RLVR | LLaMA-Factory (training only) |
| MCP + A2A interop | Client + server + A2A | Google ADK (A2A only) |
| Full observability stack | OTEL + Langfuse + LGTM | Langfuse (standalone) |

The key differentiator remains the **P2P mesh combined with domain expertise** — enabling a heterogeneous cluster of machines to collaboratively run specialized AI agents for technical domains.
