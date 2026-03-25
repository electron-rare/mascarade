# Deep Dive: High-Impact OSS for Mascarade Integration

_Research: 2026-03-25_
_Companion to: [OPEN_SOURCE_LANDSCAPE_2026-03.md](OPEN_SOURCE_LANDSCAPE_2026-03.md)_

---

## 1. LiteLLM — Unified Provider Layer

**Repo:** https://github.com/BerriAI/litellm
**Stars:** ~40K | **Version:** 1.77+ | **License:** MIT

### Proxy vs SDK Mode

| Aspect | AI Gateway (Proxy) | Python SDK |
|--------|-------------------|------------|
| Deployment | Standalone service (Docker/K8s) | `pip install litellm` in your app |
| Use case | Central gateway for multiple teams | Single app, direct integration |
| Features | Dashboard UI, virtual keys, multi-tenant spend tracking | Router with failover, in-app load balancing |
| Performance | **8ms P95 latency at 1k RPS** (v1.77) | Lower overhead, no network hop |
| Admin | Per-project logging, guardrails, caching | Programmatic config only |

**Recommendation for Mascarade:** Start with SDK mode to replace the 25+ custom provider implementations. The Proxy can come later when multi-tenant/cockpit needs arise.

### Custom Provider Migration Path

LiteLLM offers two mechanisms for providers not in its 100+ list:

1. **`CustomLLM` class** — extend `CustomLLM`, implement `completion()` and `acompletion()`, register in `custom_provider_map`. This maps directly to Mascarade's `LLMProvider` interface.
2. **OpenAI-compatible registration** — for providers that speak OpenAI format, register in config with `base_url`, `api_key_env`, constraints. Zero code needed.
3. **Entry-points (in progress)** — [Issue #7733](https://github.com/BerriAI/litellm/issues/7733) proposes pip-installable custom providers via Python entry-points.

**Migration strategy:**
- Map each Mascarade `LLMProvider` to LiteLLM's equivalent (most of the 28 providers are already supported)
- For proprietary/custom endpoints, wrap in `CustomLLM` — same `completion()`/`acompletion()` pattern
- Keep Mascarade's routing strategies (cheapest/fastest/best) as an orchestration layer above LiteLLM
- Use LiteLLM's `Router` for fallback/retry/load-balancing within a single strategy

### Cost Tracking

- `cost_per_token()` returns USD cost for input/output tokens per model
- `completion_cost()` aggregates per-call cost
- Tracks spend **per API key, per user, per team** with daily breakdowns
- Custom pricing via `input_cost_per_token` / `output_cost_per_token` in config
- `BudgetManager` class for hard limits + Slack alerts
- **Accuracy caveat:** Azure may return a different model name than configured, leading to wrong pricing. Fix: set `base_model` in config.

### Latest Features (2026)

- Google Chirp3 HD TTS provider
- Batch API spend tracking with custom metadata
- AWS IAM Secret Manager support
- RunwayML video generation integration
- Container API support
- **A2A endpoint** (`/a2a`) — direct relevance to Mascarade's A2A layer
- 2.9x faster median latency in v1.77.7 (550+ RPS)

### Mascarade Benefit

Replace ~6000 lines of provider implementation code. Keep Mascarade's routing intelligence (RouteLLM ML routing, strategy engine) as the decision layer, delegate provider communication to LiteLLM. Cost tracking comes free.

---

## 2. Langfuse — Self-Hosted LLM Observability

**Repo:** https://github.com/langfuse/langfuse
**Stars:** ~24K | **License:** MIT (core)

### Self-Hosted Docker Setup

**Architecture (v3):**
- `langfuse-web` — main app (port 3000)
- `langfuse-worker` — background processing (events, emails)
- ClickHouse — fast analytics
- PostgreSQL — metadata
- Redis — queued ingestion
- MinIO — blob storage

**Requirements:** 4 CPU cores, 16 GiB RAM, 100+ GiB storage

**Quick start:**
```bash
git clone https://github.com/langfuse/langfuse
cd langfuse
# Edit docker-compose.yml — change all CHANGEME secrets
docker compose up  # Ready in ~2-3 min
```

**Upgrade:** `docker compose up --pull always`

### FastAPI / Python Integration

The `@observe()` decorator is the primary integration mechanism:

```python
from langfuse.decorators import observe, langfuse_context

@observe()
async def route_request(message: str, strategy: str):
    provider = select_provider(strategy)
    result = await call_llm(provider, message)
    return result

@observe()
async def call_llm(provider: str, message: str):
    # This becomes a child span of route_request
    ...
```

- Outermost `@observe()` creates a **trace**, nested calls become **spans**
- Async-native — works with FastAPI's event loop
- Compatible with LangChain callbacks via `langfuse_context.get_current_langchain_handler()`
- Token/cost tracking per span
- **Caveat:** `contextvars` issues with `ThreadPoolExecutor` — stick to async

### Agent Trace Correlation

For Mascarade's multi-agent orchestrator:
- Tag traces with `agent_id`, `session_id`, `strategy`
- Use `langfuse_context.update_current_trace(metadata={...})` to attach routing decisions
- Nested spans show the full agent -> router -> provider -> response chain
- Pair with LiteLLM's native Langfuse callback for automatic cost attribution

### Mascarade Benefit

Full visibility into the 35-agent orchestration pipeline: which agent handled what, which provider was chosen, latency per hop, cost per request. Self-hosted on 192.168.0.119 alongside existing services.

---

## 3. OpenLLMetry / OpenLIT — OTel Auto-Instrumentation

### OpenLLMetry (`traceloop/openllmetry`)

**Stars:** ~7K | **License:** Apache-2.0

**Auto-instrumented providers:** OpenAI, Azure OpenAI, Anthropic, Cohere, Ollama, Mistral AI, HuggingFace, Bedrock, SageMaker, Replicate, Vertex AI, Gemini, Watsonx, Together AI, Aleph Alpha, Groq.

**What it captures:** Prompt details, token usage, model parameters, latency — all as OpenTelemetry spans.

**Export destinations:** Traceloop, Datadog, Honeycomb, Grafana, Splunk, Langfuse (via OTLP).

**Integration:** One-line init:
```python
from traceloop.sdk import Traceloop
Traceloop.init(app_name="mascarade")
```

### OpenLIT (`openlit/openlit`)

**Stars:** ~2K | **License:** Apache-2.0

**Differentiator: GPU monitoring + guardrails + prompt management**

- Auto-instruments **50+ LLM providers** + vector DBs + agent frameworks
- **GPU monitoring** via `openlit-instrument` CLI or Docker OTel GPU Collector
- Kubernetes Operator for zero-code pod injection
- Captures: prompts, completions, token usage, latency, **GPU utilization/memory/temperature**

**GPU setup:**
```bash
# CLI
openlit-instrument --collect-system-metrics python your_app.py

# Docker
docker run -e GPU_APPLICATION_NAME=mascarade \
  -e OTEL_EXPORTER_OTLP_ENDPOINT=http://collector:4318 \
  openlit/gpu-collector
```

### Recommended Stack for Mascarade

| Layer | Tool | Role |
|-------|------|------|
| Auto-instrumentation | OpenLLMetry | Capture all LLM calls without code changes |
| GPU metrics | OpenLIT | Monitor inference hardware |
| Trace storage + UI | Langfuse | Self-hosted dashboard, cost tracking, evals |
| Export bridge | OTLP | OpenLLMetry -> Langfuse via OTel protocol |

This stack is complementary, not competing. OpenLLMetry/OpenLIT generate telemetry; Langfuse stores and visualizes it.

---

## 4. CrewAI + LangGraph — Embedding in Custom Orchestrators

### Can They Run Inside Mascarade?

**Yes.** Both frameworks are designed as libraries, not monolithic platforms.

### LangGraph as Sub-Graph

LangGraph models agents as **stateful graphs** (nodes = functions, edges = control flow). To embed inside Mascarade:

```python
from langgraph.graph import StateGraph

# Define a complex reasoning sub-graph
graph = StateGraph(AgentState)
graph.add_node("analyze", analyze_fn)
graph.add_node("decide", decide_fn)
graph.add_edge("analyze", "decide")
compiled = graph.compile()

# Register as a Mascarade agent
class LangGraphAgent(MascaradeAgent):
    async def execute(self, input):
        return await compiled.ainvoke({"input": input})
```

**Best for:** Complex multi-step reasoning tasks, state machines, human-in-the-loop flows within a single agent.

### CrewAI as Task Executor

CrewAI emphasizes **role-based collaboration**. To embed:

```python
from crewai import Crew, Agent, Task

class CrewAIAgent(MascaradeAgent):
    async def execute(self, input):
        crew = Crew(agents=[...], tasks=[...])
        return crew.kickoff(inputs={"topic": input})
```

**Best for:** Tasks that benefit from multiple specialized roles (researcher + writer + reviewer).

### Hybrid Pattern (2026 Best Practice)

Use **CrewAI Flows** for high-level orchestration while embedding a **LangGraph sub-graph** for complex reasoning within a single agent's execution. This means:

- Mascarade's `AgentRegistry` remains the top-level orchestrator
- Individual agents can internally use LangGraph for stateful reasoning
- CrewAI crews can be registered as composite agents
- LangGraph can even call CrewAI crews as nodes

### Mascarade Benefit

Don't rebuild specialized agent patterns — use LangGraph for DAG-based reasoning (complement to Node Engine) and CrewAI for role-based task decomposition. Register both as standard agents.

---

## 5. MCP Ecosystem for Creative/Industrial Use

### Audio / Music Generation

| Server | Repo/URL | Capabilities | Relevance |
|--------|----------|-------------|-----------|
| **Reaper MCP** | [hamzabels85/reaper-mcp](https://mcp.so/server/reaper-mcp/hamzabels85) | AI-powered music production in REAPER DAW, MIDI + audio, fully mixed/mastered tracks | **HIGH** — direct DAW control for KXKM audio |
| **MiniMax Music** | [falahgs/mcp-minimax-music-server](https://github.com/falahgs/mcp-minimax-music-server) | Text-to-music via MiniMax API | Medium — quick generation |
| **Suno Generator** | [PulseMCP](https://www.pulsemcp.com/servers/suno-music-generator) | Custom compositions with lyrics, style tags, audio URLs | Medium — prototype/demo tracks |
| **Epidemic Sound** | [epidemicsound.com/blog/mcp-server](https://www.epidemicsound.com/blog/mcp-server/) | Context-aware music search from licensed catalog | Low — search, not generation |
| **MIDI MCP** | [LobeHub](https://lobehub.com/mcp/your-org-midi-mcp) | MIDI file manipulation | Medium — MIDI pipeline |
| **music21 MCP** | [brightlikethelight/music21-mcp-server](https://github.com/brightlikethelight/music21-mcp-server) | Music analysis + generation via music21 library, OAuth2, Docker | Medium — analysis workflows |
| **Audio MCP** | [gongrzhe/audio-mcp-server](https://lobehub.com/mcp/gongrzhe-audio-mcp-server) | Mic recording + speaker playback | Low — I/O utility |

### 3D Modeling / CAD

| Server | Repo/URL | Capabilities | Relevance |
|--------|----------|-------------|-----------|
| **FreeCAD MCP (neka-nat)** | [neka-nat/freecad-mcp](https://github.com/neka-nat/freecad-mcp) | JSON-RPC addon inside FreeCAD, Python API control, parametric modeling | **HIGH** — direct integration for enclosure/mechanical design |
| **FreeCAD MCP (contextform)** | [contextform/freecad-mcp](https://github.com/contextform/freecad-mcp) | Conversational 3D modeling, CAD workflow automation | HIGH |
| **FreeCAD MCP (lucygoodchild)** | [lucygoodchild/freecad-mcp-server](https://github.com/lucygoodchild/freecad-mcp-server) | AI assistant interaction with FreeCAD | Medium |
| **OpenSCAD** | Via code generation | LLMs generate OpenSCAD code directly (text-based modeling) | Medium — no MCP needed, just prompting |

### Electronics (KiCad / SPICE)

| Server | Repo/URL | Capabilities | Relevance |
|--------|----------|-------------|-----------|
| **Seeed KiCad MCP** | [Seeed-Studio/kicad-mcp-server](https://github.com/Seeed-Studio/kicad-mcp-server) | **39 tools**, 7 categories: analysis, validation, pin analysis, code generation. KiCad 9.0+ | **HIGH** — most complete |
| **kicad-mcp-python** | [Finerestaurant/kicad-mcp-python](https://github.com/Finerestaurant/kicad-mcp-python) | KiCad IPC API bridge | Medium — already in landscape |
| **kicad-mcp (lamaalrajih)** | [lamaalrajih/kicad-mcp](https://github.com/lamaalrajih/kicad-mcp) | Cross-platform KiCad MCP, Mac/Win/Linux | Medium |
| **circuit-synth/mcp-kicad-sch-api** | [circuit-synth/mcp-kicad-sch-api](https://github.com/circuit-synth/mcp-kicad-sch-api) | Schematic manipulation API for AI agents | Medium — schematic-focused |

**Note:** KiCad 10 (expected 2026) will have more robust APIs. The Seeed server with 39 tools is the current best bet for production use.

### Creative Writing / Novel Engines

| Server/Tool | Repo/URL | Capabilities | Relevance |
|-------------|----------|-------------|-----------|
| **UNO (Unified Narrative Operator)** | [MushroomFleet/UNO-MCP](https://github.com/mushroomfleet/uno-mcp) | Text enhancement (2x length), literary techniques, analyze/enhance tools | **HIGH** — MCP-native writing tool |
| **Book Series MCP** | [LobeHub](https://lobehub.com/mcp/rlryals-book-series-mcp) | Character management, plot tracking, world-building for series | HIGH |
| **Writer MCP** | [huangjien/writer-mcp](https://github.com/huangjien/writer-mcp) | Character knowledge, relationships, semantic search | Medium |
| **Speedgrapher** | [Medium](https://medium.com/google-cloud/introducing-speedgrapher-an-mcp-server-for-vibe-writing-53030256691d) | Writing toolkit as slash commands | Medium |
| **NovelGenerator** | [KazKozDev/NovelGenerator](https://github.com/KazKozDev/NovelGenerator) | Autonomous novel generation (premise -> EPUB), multi-threaded narratives, character psychology | HIGH (not MCP, standalone pipeline) |
| **AIStoryWriter** | [datacrystals/AIStoryWriter](https://github.com/datacrystals/AIStoryWriter) | Long-form fiction, Ollama support, novella/novel length | Medium |
| **StoryCraftr** | [raestrada/storycraftr](https://github.com/raestrada/storycraftr) | CLI for worldbuilding, outlines, chapters | Medium |

### DMX / Lighting Control

| Server | Repo/URL | Capabilities | Relevance |
|--------|----------|-------------|-----------|
| **LacyLights MCP** | [bbernstein/lacylights-mcp](https://github.com/bbernstein/lacylights-mcp) | **Multi-universe DMX**, fixture management, script analysis -> auto cue generation, natural language -> DMX values, GraphQL backend | **HIGH** — direct relevance to KXKM lighting |

LacyLights features:
- Intelligent fixture inventory with capability analysis (color mixing, positioning, effects)
- DMX channel usage mapping across universes
- Smart channel assignment for new fixtures
- AI-powered look generation from descriptions ("warm sunset on stage left")
- Script analysis to extract and sequence lighting cues
- Requires: Node.js, OpenAI API key, GraphQL backend (lacylights-go)
- Optional: ChromaDB for RAG-enhanced design suggestions

### Video / Streaming

| Server | Repo/URL | Capabilities | Relevance |
|--------|----------|-------------|-----------|
| **OBS MCP** | [royshil/obs-mcp](https://github.com/royshil/obs-mcp) | OBS WebSocket control: scene switching, recording, stream alerts | **HIGH** — streaming automation |
| **OBS MCP (sbroenne)** | [sbroenne/mcp-server-obs](https://github.com/sbroenne/mcp-server-obs) | Recording, streaming, scenes, window capture | HIGH |
| **FFmpeg MCP** | [PulseMCP](https://www.pulsemcp.com/servers/kush36agrawal-video-editor) | FFmpeg as MCP tools — encode, transcode, composite | HIGH — video pipeline |

**Emerging pattern:** Chain Blender render -> After Effects composite -> FFmpeg encode, all via MCP tool calls from a single agent conversation.

---

## 6. P2P / Distributed AI Inference

### Exo (`exo-explore/exo`)

**Repo:** https://github.com/exo-explore/exo
**Stars:** ~20K+

- **Architecture:** Pure P2P, no master-worker. Devices auto-discover and join.
- **Model splitting:** Ring memory-weighted partitioning — each device runs layers proportional to its memory.
- **Backend:** MLX + MLX distributed for communication.
- **Hardware:** Demonstrated 671B parameter models across Mac Mini clusters.
- **Constraint:** Total unified memory across devices; network bandwidth is the bottleneck.
- **Best for:** Apple hardware clusters (M-series Macs pooled together).

### llm-d (`llm-d/llm-d`)

**Repo:** https://github.com/llm-d/llm-d
**Backed by:** IBM Research, Red Hat, Google Cloud | **CNCF Sandbox project**

- **Architecture:** Kubernetes-native, disaggregated inference (prefill and decode on separate pods).
- **Key innovation:** Gateway routes requests based on KV-cache state, pod load, and hardware characteristics.
- **Cache:** Hierarchical offloading across GPU -> CPU -> storage tiers.
- **Hardware:** NVIDIA A100+, AMD MI250, Google TPU v5e+, Intel GPU Max.
- **Best for:** Production datacenter deployments with heterogeneous accelerators.

### Wavefy Network

**Repo:** https://github.com/wavefy/decentralized-llm-inference

- **Architecture:** P2P with custom routing algorithm for lowest-latency layer chains.
- **Model split:** 60 layers across ~4 devices (10-20 layers each).
- **Differentiator:** Blockchain-based incentivization (Aptos smart contracts).
- **Best for:** Community/edge inference networks.

### Petals

**URL:** https://petals.dev/

- **Architecture:** BitTorrent-style — each participant loads part of a model, joins a swarm.
- **Communication:** Distributed hash table (DHT) for peer coordination.
- **Best for:** Community inference of large open models.

### LocalAI (2026 Updates)

**Repo:** https://github.com/mudler/LocalAI

- **New in 2026:** Agent management, React UI, WebRTC support, MLX-distributed via P2P and RDMA, MCP Apps, MCP client-side features.
- **Best for:** Single-node or small-cluster local inference with MCP integration.

### Relevance to Mascarade

| Scenario | Tool | Fit |
|----------|------|-----|
| Dev cluster (Mac Minis) | **Exo** | Pool M-series Macs for large model inference |
| Production K8s | **llm-d** | Disaggregated inference with smart routing |
| Local single-node | **LocalAI** | MCP-native local inference |
| Edge/community | **Petals** or **Wavefy** | Distributed open model serving |

Mascarade's router could treat Exo/llm-d clusters as provider endpoints alongside cloud APIs, routing based on cost/latency/privacy strategy.

---

## 7. AI Creative Writing Pipelines

### Best Open Models for Fiction (2026)

| Model | Strength | Size |
|-------|----------|------|
| **Qwen3-235B-A22B** | Superior creative alignment across all metrics | 235B (MoE, 22B active) |
| **DeepSeek-V3** | Reasoning depth + role-playing | 671B (MoE) |
| **Qwen3-14B** | Cost-efficient creative performance | 14B |

### Pipeline Tools

**NovelGenerator** ([KazKozDev/NovelGenerator](https://github.com/KazKozDev/NovelGenerator))
- Input: story premise + chapter count
- Output: complete novel in EPUB
- Features: multi-threaded narratives, psychological arcs, timeline tracking
- Architecture: TypeScript, multi-agent pipeline (planner -> writer -> reviewer)
- Active development (v4.1, 105 stars)

**AIStoryWriter** ([datacrystals/AIStoryWriter](https://github.com/datacrystals/AIStoryWriter))
- Focus on long-form coherent output (novella/novel length)
- Supports local models via Ollama
- Privacy-first approach

**StoryCraftr** ([raestrada/storycraftr](https://github.com/raestrada/storycraftr))
- CLI-based: worldbuilding, outlines, chapter generation
- Good for structured workflows

### Integration with Mascarade

A creative writing pipeline as a Mascarade agent composition:

```
[Premise Agent] -> [Worldbuilding Agent] -> [Outline Agent] -> [Chapter Writer Agent] -> [Editor Agent] -> [EPUB Export]
```

Each agent uses Mascarade's router to select the best model for its task:
- Worldbuilding/Outline: Qwen3-14B (fast, cheap)
- Chapter writing: Qwen3-235B or DeepSeek-V3 (creative quality)
- Editing: Claude/GPT-4o (instruction following, consistency checks)

MCP servers (UNO, Book Series MCP) provide tools for character tracking and narrative enhancement within the pipeline.

---

## Summary: Integration Priority Matrix

| # | Integration | Impact | Effort | Dependencies |
|---|-------------|--------|--------|-------------|
| 1 | **LiteLLM SDK** — replace provider layer | Eliminate ~6K lines, get 100+ providers + cost tracking | HIGH | Refactor all provider calls |
| 2 | **Langfuse** — self-hosted observability | Full pipeline visibility, cost attribution | LOW | Docker Compose on 192.168.0.119 |
| 3 | **OpenLLMetry** — auto-instrumentation | Zero-code tracing for all LLM calls | LOW | `pip install traceloop-sdk` |
| 4 | **Seeed KiCad MCP** — electronics | 39-tool KiCad integration | LOW | KiCad 9.0+ |
| 5 | **FreeCAD MCP** — mechanical CAD | AI-driven 3D modeling | LOW | FreeCAD installed |
| 6 | **LacyLights MCP** — DMX lighting | Natural language -> DMX values | MEDIUM | Node.js, GraphQL backend |
| 7 | **OBS + FFmpeg MCP** — video pipeline | Streaming/recording automation | LOW | OBS WebSocket enabled |
| 8 | **Reaper MCP** — music production | AI-powered DAW control | MEDIUM | REAPER DAW |
| 9 | **LangGraph/CrewAI** — agent patterns | Complex reasoning + role-based tasks | MEDIUM | Register as Mascarade agents |
| 10 | **Exo** — distributed inference | Pool Mac hardware for large models | MEDIUM | MLX, network config |
| 11 | **UNO + Book Series MCP** — creative writing | Narrative tools for writing agents | LOW | MCP client |
| 12 | **llm-d** — K8s inference | Production disaggregated serving | HIGH | Kubernetes cluster |

---

## Sources

- [LiteLLM GitHub](https://github.com/BerriAI/litellm)
- [LiteLLM Spend Tracking](https://docs.litellm.ai/docs/proxy/cost_tracking)
- [LiteLLM Custom Providers](https://docs.litellm.ai/docs/providers/custom_llm_server)
- [LiteLLM Provider Registration](https://docs.litellm.ai/docs/provider_registration/)
- [LiteLLM Production Best Practices](https://docs.litellm.ai/docs/proxy/prod)
- [LiteLLM Review 2026](https://www.truefoundry.com/blog/a-detailed-litellm-review-features-pricing-pros-and-cons-2026)
- [Langfuse Self-Hosting](https://langfuse.com/self-hosting)
- [Langfuse Docker Compose](https://langfuse.com/self-hosting/deployment/docker-compose)
- [Langfuse Python Decorators](https://langfuse.com/docs/sdk/python/decorators)
- [Langfuse + OpenLLMetry Integration](https://langfuse.com/guides/cookbook/otel_integration_openllmetry)
- [OpenLLMetry GitHub](https://github.com/traceloop/openllmetry)
- [OpenLIT GitHub](https://github.com/openlit/openlit)
- [OpenLIT GPU Monitoring](https://docs.openlit.io/latest/openlit/quickstart-gpu)
- [CrewAI + LangGraph Combination](https://medium.com/@mayadakhatib/combining-langgraph-and-crewai-bf38c719ab27)
- [Agent Frameworks 2026 Guide](https://dev.to/pockit_tools/langgraph-vs-crewai-vs-autogen-the-complete-multi-agent-ai-orchestration-guide-for-2026-2d63)
- [Agentic Frameworks Definitive Guide 2026](https://softmaxdata.com/blog/definitive-guide-to-agentic-frameworks-in-2026-langgraph-crewai-ag2-openai-and-more/)
- [Epidemic Sound MCP](https://www.epidemicsound.com/blog/mcp-server/)
- [MiniMax Music MCP](https://github.com/falahgs/mcp-minimax-music-server)
- [music21 MCP Server](https://github.com/brightlikethelight/music21-mcp-server)
- [FreeCAD MCP (neka-nat)](https://github.com/neka-nat/freecad-mcp)
- [FreeCAD MCP (contextform)](https://github.com/contextform/freecad-mcp)
- [9 MCP Servers for CAD (Snyk)](https://snyk.io/articles/9-mcp-servers-for-computer-aided-drafting-cad-with-ai/)
- [Seeed KiCad MCP Server](https://github.com/Seeed-Studio/kicad-mcp-server)
- [circuit-synth KiCad MCP](https://github.com/circuit-synth/mcp-kicad-sch-api)
- [LacyLights MCP](https://github.com/bbernstein/lacylights-mcp)
- [OBS MCP](https://github.com/royshil/obs-mcp)
- [OBS MCP (sbroenne)](https://github.com/sbroenne/mcp-server-obs)
- [FFmpeg MCP (PulseMCP)](https://www.pulsemcp.com/servers/kush36agrawal-video-editor)
- [MCP Servers for Creative Tools (Shyft)](https://shyft.ai/blog/mcp-servers-creative-tools)
- [Exo GitHub](https://github.com/exo-explore/exo)
- [llm-d GitHub](https://github.com/llm-d/llm-d)
- [llm-d CNCF Announcement](https://thenewstack.io/llm-d-cncf-kubernetes-inference/)
- [Wavefy Decentralized Inference](https://github.com/wavefy/decentralized-llm-inference)
- [Petals](https://petals.dev/)
- [LocalAI GitHub](https://github.com/mudler/LocalAI)
- [NovelGenerator](https://github.com/KazKozDev/NovelGenerator)
- [AIStoryWriter](https://github.com/datacrystals/AIStoryWriter)
- [StoryCraftr](https://github.com/raestrada/storycraftr)
- [UNO MCP](https://github.com/mushroomfleet/uno-mcp)
- [Book Series MCP](https://lobehub.com/mcp/rlryals-book-series-mcp)
- [Writer MCP](https://github.com/huangjien/writer-mcp)
- [Best Open Source LLM for Creative Writing 2026](https://www.siliconflow.com/articles/en/best-open-source-llm-for-creative-writing-ideation)
