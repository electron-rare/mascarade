# Mascarade Feature Map

> Last updated: 2026-03-27

## Legend

| Status | Meaning |
|--------|---------|
| done | Shipped and tested |
| in-progress | Active development |
| planned | Scheduled, not started |

| Priority | Meaning |
|----------|---------|
| P0 | Critical path |
| P1 | High value |
| P2 | Medium value |
| P3 | Nice to have |

---

## 1. LLM Router

| Feature | Status | Priority | Dependencies | Notes |
|---------|--------|----------|--------------|-------|
| Multi-provider routing | done | P0 | — | 25+ providers |
| Strategy engine (cheapest/fastest/best/specific) | done | P0 | — | |
| Automatic fallback chain | done | P0 | — | Provider failure → next |
| Load balancer | done | P1 | — | |
| Response cache (prompt hash) | done | P1 | Redis | |
| OpenAI-compatible API (`/v1/chat/completions`) | done | P0 | — | Frozen contract |
| Streaming support | done | P0 | — | SSE |
| Cost tracking per request | done | P1 | — | |
| Token usage analytics | done | P1 | ClickHouse | |
| Provider health monitoring | done | P1 | Prometheus | |

### Providers

| Provider | Status | Priority | Notes |
|----------|--------|----------|-------|
| Claude (Anthropic) | done | P0 | Direct API |
| OpenAI (GPT) | done | P0 | |
| Mistral | done | P0 | |
| AWS Bedrock | done | P0 | TOCTOU race fixed |
| Google Gemini | done | P1 | |
| Hugging Face | done | P1 | Inference API |
| Ollama | done | P0 | Local runtime |
| llama.cpp | done | P1 | GGUF models |
| Apple CoreML | done | P2 | M-series Macs |
| KiCad Router | done | P2 | Domain-specific |
| MLX-LM | done | P1 | Apple Silicon native |
| Exo (distributed) | done | P1 | Multi-Mac cluster |
| Apple Foundation Models | done | P2 | 3B on-device |
| GitHub Copilot | done | P1 | Copilot provider |
| Codestral | done | P1 | Mistral code model |
| Mistral Agents | done | P1 | Mistral agent API |
| Mistral Studio | done | P1 | Mistral Studio integration |
| Cody Gateway | done | P1 | Sourcegraph Cody |

## 2. Agents

| Feature | Status | Priority | Dependencies | Notes |
|---------|--------|----------|--------------|-------|
| Agent registry | done | P0 | — | |
| KiCad agent | done | P1 | Kill_LIFE MCP | PCB design |
| FreeCAD agent | done | P1 | Kill_LIFE MCP | 3D CAD |
| SPICE agent | done | P1 | — | Circuit simulation |
| Components agent | done | P1 | — | Electronics BOM |
| Agent skills system | done | P1 | — | |
| Prompt versioning | done | P2 | — | |
| Agent factory (DCS) | done | P2 | Agent Factory Cockpit | |

## 3. Orchestrator

| Feature | Status | Priority | Dependencies | Notes |
|---------|--------|----------|--------------|-------|
| Sequential execution | done | P0 | — | |
| Parallel execution | done | P0 | — | |
| Pipeline execution | done | P0 | — | |
| Orchestration templates | done | P1 | — | |
| Circuit breaker | done | P1 | — | |
| Retry with backoff | done | P1 | — | |
| Dead letter queue | done | P2 | — | Failed tasks |
| Execution context | done | P1 | — | State passing |
| Plan-and-Execute orchestrator | done | P1 | — | Execution plan + task management |

## 4. Node Engine

| Feature | Status | Priority | Dependencies | Notes |
|---------|--------|----------|--------------|-------|
| Graph runtime | done | P0 | — | DAG execution |
| Node executor | done | P0 | — | |
| Persistence layer | done | P1 | — | Save/load graphs |
| AI domain workers | done | P1 | Router | LLM nodes |
| CAD domain workers | done | P1 | Kill_LIFE MCP | |
| Electronics domain workers | done | P1 | — | |
| Cross-domain bridge | done | P2 | — | |
| DMX controller node | done | P2 | — | Lighting |
| MIDI controller node | done | P2 | — | Audio/music |
| ESP32 client node | done | P2 | — | IoT |
| XYFlow graph editor (web) | done | P1 | React 19 | Visual editor |
| CrazyLane workflow editor | in-progress | P1 | crazy_life | Vue 3 migration |

## 5. P2P Mesh

| Feature | Status | Priority | Dependencies | Notes |
|---------|--------|----------|--------------|-------|
| libp2p node | done | P0 | — | |
| DHT peer discovery | done | P0 | — | Poisoning fix applied |
| Gossip protocol (PubSub) | done | P0 | — | Inbound fix applied |
| mDNS local discovery | done | P1 | — | LAN nodes |
| Relay (Tailscale bridge) | done | P1 | — | Remote nodes |
| Stream forwarding | done | P1 | — | Request relay |
| Task distribution (claim-based) | done | P0 | — | Race fix applied |
| P2P authentication | done | P0 | — | Cluster token |
| Identity management | done | P1 | — | |
| Capabilities advertisement | done | P1 | — | GPU, storage |
| Memory pruning | done | P2 | — | |
| P2P metrics | done | P2 | Prometheus | |
| Finetune task handler | done | P1 | — | Distribute training |

### Mesh Nodes

| Node | Status | Role | Hardware |
|------|--------|------|----------|
| VM (192.168.0.119) | done | Bootstrap :4002 | 6.8GB RAM, 4 CPU, no GPU |
| GrosMac (local) | done | Bridge :4001 | Apple Silicon, LAN ↔ Tailscale |
| CILS (192.168.0.210) | done | Worker :4001 | MacBook, compute |
| Tower (192.168.0.120) | done | Worker :4001 | Compute + storage |
| KXKM-AI (kxkm-ai) | done | Worker :4001 (relay) | RTX 4090 24GB, 62GB RAM, 28 CPU |

## 6. Fine-Tuning Pipeline

| Feature | Status | Priority | Dependencies | Notes |
|---------|--------|----------|--------------|-------|
| Dataset bootstrap (13 domains) | done | P0 | mascarade-datasets | ~74k examples |
| Dataset quality filters | done | P1 | — | |
| Dataset refresh from sources | done | P1 | — | |
| HuggingFace dataset upload | done | P1 | — | |
| Teacher distillation | done | P1 | — | |
| Unsloth + LoRA training | done | P0 | RTX 4090 | |
| DPO/SimPO alignment | done | P1 | — | |
| Model promotion (quality gate) | done | P1 | — | |
| GGUF conversion (F16 → Q4_K_M) | done | P0 | — | 3.09G → 941MB |
| Ollama deployment | done | P0 | Ollama | Modelfile + push |
| P2P task distribution | done | P1 | P2P mesh | |
| Batch pipeline automation | done | P1 | — | |
| Model selector / benchmark | done | P2 | — | |
| Rejection sampling | done | P2 | — | |
| HuggingFace model upload | in-progress | P2 | — | clemsail/ |
| HumanEval benchmarks | planned | P2 | — | mascarade-coder eval |

### Fine-Tune Agents

| Agent | Status | Priority | Role |
|-------|--------|----------|------|
| Student | done | P0 | Learns from data |
| Teacher | done | P0 | Generates distillation data |
| Reinforcer | done | P1 | DPO/SimPO alignment |
| Analyst | done | P1 | Benchmarks and evaluation |
| Validator | done | P1 | Quality gates |
| Documentalist | done | P2 | Reports and docs |
| Archivist | done | P2 | HuggingFace upload |

## 7. MCP Integration

| Feature | Status | Priority | Dependencies | Notes |
|---------|--------|----------|--------------|-------|
| MCP client (HTTP transport) | done | P0 | — | `call_tool_http()` |
| Graphiti MCP server | done | P1 | Neo4j | Knowledge graph |
| Kill_LIFE: kicad MCP | done | P1 | Kill_LIFE repo | |
| Kill_LIFE: freecad MCP | done | P1 | Kill_LIFE repo | |
| Kill_LIFE: openscad MCP | done | P2 | Kill_LIFE repo | |
| Kill_LIFE: validate-specs MCP | done | P1 | Kill_LIFE repo | |
| Kill_LIFE: knowledge-base MCP | done | P1 | Kill_LIFE repo | |
| Kill_LIFE: github-dispatch MCP | done | P2 | Kill_LIFE repo | |
| Kill_LIFE: huggingface MCP | done | P2 | Kill_LIFE repo | |

## 8. API Gateway (TypeScript)

| Feature | Status | Priority | Dependencies | Notes |
|---------|--------|----------|--------------|-------|
| Hono framework | done | P0 | — | Port 3100 |
| JWT + API key auth | done | P0 | — | |
| Rate limiting | done | P1 | — | |
| Core proxy (→ :8100) | done | P0 | — | |
| Agent routes | done | P0 | — | |
| Cluster routes | done | P1 | — | |
| P2P routes | done | P1 | — | |
| CAD routes | done | P1 | — | |
| Industrial routes | done | P1 | — | |
| Kill_LIFE routes | done | P1 | — | |
| Node engine routes | done | P1 | — | |
| Ops routes | done | P1 | — | |
| Analytics routes | done | P2 | — | |
| Settings routes | done | P2 | — | |
| Pipeline routes | done | P1 | — | |
| Health check | done | P0 | — | |
| Version endpoint | done | P0 | — | Frozen contract |

## 9. Frontend (React 19)

| Feature | Status | Priority | Dependencies | Notes |
|---------|--------|----------|--------------|-------|
| XYFlow graph editor | done | P1 | React 19 | Node engine UI |
| Agent dashboard | done | P1 | — | |
| Metrics dashboard | done | P2 | — | |
| Playground (chat) | done | P1 | — | |
| Orchestration viewer | done | P2 | — | |
| Knowledge browser | done | P2 | — | |
| P2P mesh viewer | done | P2 | — | |
| Kill_LIFE workflows | in-progress | P2 | — | |

## 10. Infrastructure / DevOps

| Feature | Status | Priority | Dependencies | Notes |
|---------|--------|----------|--------------|-------|
| Docker Compose (30+ services) | done | P0 | — | |
| Prometheus metrics | done | P1 | — | |
| Grafana dashboards | done | P1 | — | |
| Loki log aggregation | done | P1 | — | |
| Tempo distributed tracing | done | P2 | — | |
| OTEL collector | done | P1 | — | |
| Langfuse LLM observability | done | P1 | — | |
| Edge proxy (TLS) | done | P1 | — | |
| Ops agent | done | P2 | — | |
| Blackbox exporter | done | P2 | — | |
| Neo4j + Graphiti | done | P1 | — | Knowledge graph |
| Mem0 memory layer | done | P2 | — | |
| Firecrawl web scraping | done | P2 | — | |
| n8n workflow automation | done | P2 | — | |
| Dify (API + Web + Worker) | done | P2 | — | |
| LiteLLM proxy | done | P2 | — | |
| MinIO object storage | done | P2 | — | |

## 11. Auth / Security

| Feature | Status | Priority | Dependencies | Notes |
|---------|--------|----------|--------------|-------|
| API key authentication | done | P0 | — | |
| JWT tokens | done | P0 | — | |
| RBAC | done | P1 | — | |
| Cluster token auth | done | P0 | — | P2P mesh |
| Rate limiting | done | P1 | — | |
| API hardening | done | P1 | — | Tower merge |
| Secrets manager (P2P) | done | P2 | — | `p2p_secrets_manager.sh` |

## 12. Apple Intelligence

| Feature | Status | Priority | Dependencies | Notes |
|---------|--------|----------|--------------|-------|
| MLX-LM provider | done | P1 | MLX framework | OpenAI-compatible server |
| MLX model quantization | done | P1 | MLX | 4-bit / 8-bit |
| Exo distributed inference | done | P1 | Exo | Mac cluster sharding |
| Apple Foundation Models (3B) | done | P2 | macOS 26+ | Swift bridge |
| Core AI framework integration | planned | P2 | WWDC 2026 | |
| App Intents (Siri) | planned | P3 | macOS 26+ | Voice → Mascarade |
| CoreML → Core AI migration | planned | P2 | Core AI SDK | |

## 13. Agentic RAG

| Feature | Status | Priority | Dependencies | Notes |
|---------|--------|----------|--------------|-------|
| Agentic RAG engine | done | P1 | Qdrant | Retrieval-augmented generation |
| Document retriever | done | P1 | — | Multi-source retrieval |
| Hybrid search (dense + BM25 + RRF) | done | P1 | Qdrant | |
| Cross-encoder reranking | done | P0 | sentence-transformers | BAAI/bge-reranker-v2-m3, +10-30% precision |
| LLM reranker fallback | done | P1 | — | When sentence-transformers absent |
| Contextual Retrieval | done | P0 | LLM (haiku) | −49% failed retrievals (Anthropic pattern) |
| Semantic query cache | done | P1 | Qdrant + Redis | Cosine sim threshold 0.92, TTL-based |
| BGE-M3 Ollama embedding | done | P1 | Ollama | 1024-dim, MTEB 63.0 |
| Multi-provider embedding | done | P1 | — | OpenAI / Mistral / HuggingFace / Ollama / fastembed |
| CRAG web fallback | done | P1 | SearXNG | Low-confidence → web search |
| Intent classification | done | P1 | LLM | rag / web / general routing |
| RAGAS eval pipeline | done | P1 | LLM judges | 5 metrics, POST /v1/api/rag/eval |
| RAG ingest API | done | P1 | — | POST /v1/api/rag/ingest (chunk=true support) |
| RAG search API | done | P1 | — | POST /v1/api/rag/search |
| RAG query API | done | P1 | — | POST /v1/api/rag/query |
| Text chunker | done | P1 | — | rag/chunker.py — token-aware, paragraph→sentence split + overlap |
| URL ingestion (Docling) | done | P1 | Docling | POST /v1/api/rag/ingest/url — PDF/DOCX/HTML fetch + chunk |
| File upload ingestion | done | P1 | Docling | POST /v1/api/rag/ingest/upload — 50MB limit, any Docling format |
| P2P VRAM Grafana dashboard | done | P2 | Prometheus | mascarade-p2p-mesh.json |
| data.gouv.fr MCP | done | P1 | — | 74k+ datasets publics français, SSE transport |
| LightRAG (large corpus) | planned | P2 | — | >1k docs |
| ColPali (visual PDFs) | planned | P2 | — | Datasheets / schematics |
| KiCad ingestion pipeline | planned | P2 | Kill_LIFE | PCB docs → RAG |

## 14. Cowork OTel

| Feature                  | Status | Priority | Dependencies   | Notes                        |
|--------------------------|--------|----------|----------------|------------------------------|
| Cowork OTel integration  | done   | P1       | OTEL Collector | Collaborative observability  |

## 15. Ecosystem Integration

| Feature | Status | Priority | Dependencies | Notes |
|---------|--------|----------|--------------|-------|
| crazy_life cockpit | in-progress | P1 | crazy_life repo | Vue 3 + Pinia migration |
| Kill_LIFE MCP servers | done | P1 | Kill_LIFE repo | 7 servers |
| mascarade-datasets | done | P1 | — | 13 domains |
| mascarade-cockpit (SvelteKit) | done | P2 | — | Ops monitoring |
| CrazyLane workflow editor | in-progress | P1 | Rete.js | |
| Graphiti knowledge graph | done | P1 | Neo4j | |

---

## Summary

| Domain | Done | In Progress | Planned | Total |
|--------|------|-------------|---------|-------|
| LLM Router | 10 | 0 | 0 | 10 |
| Providers | 18 | 0 | 0 | 18 |
| Agents | 8 | 0 | 0 | 8 |
| Orchestrator | 9 | 0 | 0 | 9 |
| Node Engine | 11 | 1 | 0 | 12 |
| P2P Mesh | 13 | 0 | 0 | 13 |
| Fine-Tuning | 13 | 1 | 1 | 15 |
| MCP Integration | 9 | 0 | 0 | 9 |
| API Gateway | 16 | 0 | 0 | 16 |
| Frontend | 7 | 1 | 0 | 8 |
| Infrastructure | 17 | 0 | 0 | 17 |
| Auth / Security | 7 | 0 | 0 | 7 |
| Apple Intelligence | 4 | 0 | 3 | 7 |
| Agentic RAG | 20 | 0 | 3 | 23 |
| Cowork OTel | 1 | 0 | 0 | 1 |
| Ecosystem | 4 | 2 | 0 | 6 |
| **Total** | **167** | **5** | **7** | **179** |
