# Changelog

All notable changes to the Mascarade API will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased] - 2026-03-27

### Added
- **RAG P0 — Cross-encoder reranking** (`rag/reranker.py`): `CrossEncoderReranker` wraps BAAI/bge-reranker-v2-m3 via sentence-transformers; lazy-loaded, runs in `ThreadPoolExecutor` (non-blocking). Falls back silently to LLM comma-score ranking if sentence-transformers is not installed. Optional dep: `pip install mascarade-core[reranker]`.
- **RAG P0 — Contextual Retrieval** (Anthropic pattern, −49% failed retrievals): `pipeline.ingest(contextual_retrieval=True)` generates a 1-2 sentence LLM preamble per chunk before embedding. Uses `rag_contextual_retrieval_model` (default: claude-haiku-4-5-20251001). Added `_add_contextual_preambles()` to `RAGPipeline`.
- **RAG P1 — Semantic query cache** (`rag/query_cache.py`): `RAGQueryCache` stores query embeddings in a dedicated Qdrant collection (`rag-query-cache`) and results in Redis with configurable TTL. Cache hits skip embed+retrieve+generate, returning in < 5ms.
- **RAG P1 — BGE-M3 Ollama embedding**: `EmbeddingProvider` now supports `settings.rag_embedding_provider = "ollama"` with `rag_embedding_model = "bge-m3:latest"` (1024-dim, MTEB 63.0). Added `_embed_ollama()` backend with 60s timeout for cold model load.
- **RAG P1 — RAGAS evaluation pipeline** (`rag/eval.py`, `POST /v1/api/rag/eval`): `RAGEvaluator` computes 5 LLM-judge metrics (Faithfulness ≥0.85, Answer Relevance ≥0.75, Context Precision ≥0.70, Context Recall ≥0.75, Hallucination Rate <5%). Supports golden datasets with optional pipeline fill for missing answers/contexts.
- **Fine-tuning Phase B script** (`finetune/batch_phase_b.sh`): rejection sampling across 10 domains (stm32, embedded, spice, kicad, platformio, iot, dsp, emc, power, freecad), 8 candidates per prompt, outputs `dpo_pairs/{domain}/dpo_{domain}_{stamp}.jsonl`.
- **Fine-tuning Phase C script** (`finetune/batch_phase_c.sh`): ORPO training (no reference model, −3GB VRAM on Qwen2.5-Coder-3B), auto-detects latest Phase A SFT adapter and latest DPO pairs file per domain.
- **Fine-tuning Phase D script** (`finetune/batch_phase_d.sh`): merge → GGUF → Ollama deploy + HF upload to `clemsail/mascarade-{domain}-lora` with auto-generated model card.
- **Fine-tuning Phase B→C→D chain** (`finetune/batch_phases_bcd.sh`): sequential chaining with `--skip-phase-d` option.
- **Agentic CLI loop** (`server_protected.py`): `POST /agents/{name}/run-agentic` — ReAct loop (max 6 iterations), parses ` ```tool_call``` ` blocks, dispatches to Kill_LIFE CLI tools via `_run_cli_agent_core` (shared with `/cli-agents/run`).
- **P2P VRAM Prometheus metrics** (`p2p/metrics.py`): gauges `mascarade_p2p_peer_vram_gb` (labels: peer_id, chip_family), `mascarade_p2p_local_vram_gb` (label: chip_family), counter `mascarade_p2p_routing_vram_skips_total`. Heartbeat re-announce now includes `gpu_vram_gb`, `chip_family`, `ram_gb`.
- **Prometheus P2P alert rules** (`deploy/prometheus/alerts/p2p.yml`): `MascaradeP2PPeerDown`, `MascaradeP2PMeshTooSmall` (<3 peers), `MascaradeGPUNodeDown` (kxkm-ai, critical), `MascaradeCoreDown`, `MascaradeCoreHighMemory` (>2GB RSS).
- **Lazy MCP env resolution** (`mcp/servers_registry.py`): `"env:VAR_NAME|default"` pattern resolved at call time via `get_server_config()`.
- **Healthchecks self-hosted** (`deploy/healthchecks.yml`): linuxserver/healthchecks on mascarade-postgres, exposed at `hc.saillant.cc`.
- **Edge proxy vhosts** (`deploy/edge-proxy/default.conf.template`): Frappe LMS, Moodle, and oidc2fer SATOSA gateway with HTTP+HTTPS blocks and WebSocket support.
- **RAG config settings** (`config.py`): `rag_reranker_enabled`, `rag_reranker_model`, `rag_contextual_retrieval_enabled`, `rag_contextual_retrieval_model`, `rag_cache_enabled`, `rag_cache_similarity_threshold`, `rag_cache_ttl`, `rag_embedding_provider`, `rag_embedding_model`.
- **Whisper config** (`config.py`): `whisper_model_size`, `whisper_device`, `whisper_compute_type`.

### Fixed
- ruff B904: all `raise HTTPException` inside `except` clauses in `server_protected.py` now use `from exc`.
- `docker-compose.graphiti.yml`: bind `${GRAPHITI_BIND_HOST:-127.0.0.1}` (was `0.0.0.0`); NEO4J_AUTH/NEO4J_PASSWORD now use required env vars.
- Loki retention reduced to 7d (was 30d).

---

## API Version 1.0.0 - Initial Release

### Overview
This release establishes the baseline API contract for Mascarade. All endpoints are now versioned under `/v1/` prefix to ensure backward compatibility and stability guarantees.

### Added - Non-Breaking
- **Versioning Infrastructure**
  - All API endpoints now use `/v1/` prefix for versioning
  - New `GET /v1/version` endpoint returns API version, supported features, and provider list
  - Python API version module (`mascarade.api_version`) with programmatic access to version metadata
  - Deprecation middleware infrastructure (RFC 8594-compliant) for future endpoint deprecations
    - Supports `Deprecation`, `Warning`, `Sunset`, `Link`, and `X-Deprecated-Since` headers
    - Pattern-based and endpoint-specific deprecation rules
  - Comprehensive regression test suite (45+ tests) to ensure API stability across releases

- **Core Python API (port 8100)**
  - `GET /v1/version` - API version metadata and supported features
  - `POST /v1/chat/completions` - OpenAI-compatible endpoint (frozen contract)
  - `POST /v1/agents/send` - Primary agent dispatch endpoint
  - `POST /v1/agents/orchestrate` - Multi-agent orchestration
  - `GET /v1/agents/providers` - List active LLM providers
  - `GET /v1/agents/metrics` - Global metrics and statistics
  - `GET /v1/cache/stats` - Cache performance metrics
  - `/v1/cluster/*` - Multi-node coordination endpoints
  - `/v1/knowledge-base/*` - Knowledge base operations
  - `/v1/api-keys/*` - API key management endpoints

- **TypeScript API (port 3100)**
  - `GET /v1/version` - API version metadata aggregated from core service
  - `/v1/api/agents/*` - Agent management and execution
  - `/v1/api/cluster/*` - Cluster coordination proxy
  - `/v1/api/cad/*` - CAD/EDA integration endpoints
  - `/v1/api/comfyui/*` - ComfyUI workflow integration
  - `/v1/api/knowledge-base/*` - Knowledge base operations
  - `/v1/api/ops/*` - Operations and monitoring
  - `/v1/api/industrial/*` - Industrial automation endpoints
  - `/v1/api/mcp/industrial/*` - MCP industrial integration
  - `/health` - Health check (no version prefix, always stable)

### Stability Guarantees

#### Frozen Contracts
The following endpoints have frozen contracts and will not change in v1.x:
- `POST /v1/chat/completions` - OpenAI-compatible interface
  - Request/response schema matches OpenAI API v1
  - Supports: messages, model, temperature, max_tokens, stream
  - Response includes: id, object, created, choices, usage

#### Backward Compatibility Promise
- No breaking changes will be introduced in v1.x releases
- New fields may be added to responses (clients should ignore unknown fields)
- Optional request parameters may be added
- Deprecated features will be supported for minimum 6 months with warnings
- Migration guide will be provided before any v2.0 breaking changes

### Breaking Changes
- **[BREAKING]** None - this is the initial versioned release establishing the baseline API contract
  - Note: This release establishes `/v1/` as the canonical API prefix. Non-versioned paths are no longer supported.
  - Clients must update to use `/v1/` prefixed endpoints (Python core) and `/v1/api/` prefixed endpoints (TypeScript API).
  - Migration path: Replace `/agents/*` with `/v1/agents/*` and `/api/*` with `/v1/api/*`

### Deprecated
- None

### Security
- **[SECURITY]** All protected endpoints require `Authorization: Bearer <token>` header
- `/health` endpoint remains public for monitoring purposes
- API key management available via `/v1/api-keys/*` endpoints

---

## Version History

### [Unreleased] - 2026-03-26

#### Added
- **LiteLLM migration (Google, HuggingFace, Codestral)** — Chat completion paths for 3 providers now use `litellm.acompletion()` instead of direct SDK/httpx calls. All auth logic (Google 3-mode: API key / OAuth OIDC / ADC; HuggingFace OAuth token refresh; Codestral API key) is preserved. LiteLLM is an optional import (`try/except`). Codestral FIM endpoint stays on direct httpx since litellm has no FIM support.
- **OpenAPI spec export** — `scripts/export_openapi.py` generates `docs/api/openapi.json` (140KB, OpenAPI 3.1.0) from the FastAPI app
- **Auth & security hardening** — Token validation improvements, RBAC key support, E2E tests for payload limits and auth security
- **Agents UX research** — SOTA research findings for agents auth UX (`docs/plan/2026-03-24-sota-mascarade/`)

#### Changed
- **Provider consolidation** — Google provider no longer imports `google.genai` for chat (litellm handles it); removed `openai` dependency from Google provider; HuggingFace provider no longer creates its own `openai.AsyncOpenAI` client for chat; Codestral provider no longer parses SSE manually for chat streaming
- **Web cockpit** — Updated API client, AuthContext improvements, Agents page updates

#### Fixed
- Health route updates in API layer

---

### [Unreleased] - 2026-03-24

#### Added
- **Agent Gates** — Pre/post execution gate system with 4 built-in checks (`has_system_prompt`, `has_skills`, `has_tools`, `is_configured`). Required and optional gates, `EvidenceRecord` for audit trails. (`core/mascarade/agents/base.py`)
- **MCP n8n Client** — `N8nMcpClient` with 4 tools: `list_workflows`, `execute_workflow`, `get_execution`, `list_executions`. Auto-registered via `N8N_BASE_URL` env var. (`core/mascarade/mcp/n8n.py`)
- **MCP ERPNext Client** — `ERPNextMcpClient` with 6 tools: `list_leads`, `get_lead`, `create_lead`, `list_quotations`, `create_quotation`, `list_invoices`. Auto-registered via `FRAPPE_URL` env var. (`core/mascarade/mcp/erpnext.py`)
- **A2A SDK migration (Phase 1)** — Router aligned to A2A spec v0.3 with 6 task states (`submitted`, `working`, `input-required`, `completed`, `failed`, `canceled`), `AgentCardResponse` model, conditional `a2a-sdk` import. (`core/mascarade/routers/a2a.py`)
- **Zod validation** — 6 new schemas (`UserCreate`, `UserUpdate`, `ApiKeyCreate`, `WorkflowRun`, `FinetuneRun`, `ClusterForwardSend`) wired into 5 API routes via `validate()` middleware. (`api/src/validation/schemas.ts`)
- **Tests** — +107 new tests: 4 providers (Claude, OpenAI, LiteLLM, Bedrock), 4 routers (Admin, WebSocket, Analytics, Voice), agent gates (17 tests), MCP clients (21 tests)
- **CI** — Added TypeScript type-check step (`tsc --noEmit`) and pytest coverage threshold (`--cov-fail-under=50`)
- **MCP SearXNG** — Web search tool for agents, auto-registered via `SEARXNG_URL` env var. (`core/mascarade/mcp/searxng.py`)
- **RAG SOTA 2026** — Hybrid search (dense+BM25+RRF fusion), LLM reranking, CRAG pattern with SearXNG web fallback. (`core/mascarade/rag/pipeline.py`, `core/mascarade/rag/vectorstore.py`)
- **RAG Ingestion** — Script to chunk + embed 242 docs / 853 chunks via Ollama bge-m3 into Qdrant. (`scripts/ingest-docs.py`)

#### Fixed
- Syntax error in `gpt53_codex.py` where `import json` was placed before the docstring
- **SecretStr bug** in 5 providers (claude, openai, google, huggingface, bedrock) — all now use `secret_value()` to unwrap keys
- **API proxy** routing `/api/ai` to correct `/prompts` endpoint on mascarade-core
- **Frappe CRM** — removed orphan `lms` and `payments` modules from installed apps

---

## Change Classification

Changes are labeled as:
- **[BREAKING]** - Requires client code changes
- **[DEPRECATED]** - Will be removed in future version
- **[ADDED]** - New feature or endpoint
- **[CHANGED]** - Modification to existing feature
- **[FIXED]** - Bug fix
- **[SECURITY]** - Security-related change

## Migration Guides

### Future v1.x → v2.0
Migration documentation will be provided when v2.0 planning begins.
