# Mascarade — Conventions

## Project
- Mascarade is a personal agentic orchestration system
- Python core (agents, router, orchestrator) + TypeScript API (Hono)
- Deployed on Tower (primary) and Photon VM (mesh secondary) via Docker Compose

## Python (core/)
- Python 3.11+, use Pydantic for models
- Async everywhere (httpx, async providers)
- Run tests: `cd core && python -m pytest`
- Format: ruff

## TypeScript (api/)
- Hono framework on Node
- Run: `cd api && npm run dev`
- Build: `cd api && npm run build`

## Infrastructure
- **Tower** (primary server): 12 CPU, 32GB RAM, Quadro P2000, 87 containers, mascarade-core healthy. SSH: `clems@tower`
- **Photon** (mesh secondary): 4 vCPU, 6.8GB RAM, minimal (core mesh + Pi-hole + CF tunnel). SSH: `cils@192.168.0.119`
- **Mac** (dev machine): 192.168.0.210
- mascarade-core runs on BOTH Tower and Photon for P2P mesh

## Docker
- `docker compose up` from project root
- Core service on port 8100 (both machines), API on port 3100

## Key patterns
- All LLM providers implement `LLMProvider` (core/mascarade/router/providers/base.py)
- Agents are registered in the `AgentRegistry`
- Router dispatches to providers based on strategy (cheapest/fastest/best/specific)
- Knowledge-base / CAD surfaces replace the old Notion-first operator path; remaining Notion code is legacy compatibility only

## RAG pipeline (implemented 2026-03-27)
- Entry points: `POST /v1/api/rag/query`, `/ingest`, `/search`, `/eval`
- `RAGPipeline` in `rag/pipeline.py` orchestrates: intent classify → embed → hybrid_search → rerank → generate
- **Embeddings**: `EmbeddingProvider` (`rag/embeddings.py`) — provider auto-fallback chain (OpenAI → Mistral → HuggingFace → Ollama → Qdrant fastembed). Override: `settings.rag_embedding_provider = "ollama"` + `rag_embedding_model = "bge-m3:latest"` for local 1024-dim BGE-M3.
- **Reranking**: `CrossEncoderReranker` (`rag/reranker.py`) — lazy-loads BAAI/bge-reranker-v2-m3 in a `ThreadPoolExecutor`; falls back to LLM comma-score ranking. Needs `pip install mascarade-core[reranker]`. Toggle: `settings.rag_reranker_enabled`.
- **Contextual Retrieval**: enable with `pipeline.ingest(contextual_retrieval=True)` or `settings.rag_contextual_retrieval_enabled = True`. LLM preamble per chunk using `settings.rag_contextual_retrieval_model` (default haiku). −49% failed retrievals.
- **Semantic cache**: `RAGQueryCache` (`rag/query_cache.py`) — Qdrant collection `rag-query-cache` (cosine threshold 0.92) + Redis (TTL 3600s). Enable with `settings.rag_cache_enabled = True`.
- **Eval**: `RAGEvaluator` (`rag/eval.py`) — 5 RAGAS-compatible metrics via LLM judges. Production thresholds in `THRESHOLDS` dict. Accepts golden datasets; `run_pipeline=True` fills missing answers/contexts.
- **Chunker**: `chunk_text()`/`chunk_document()` (`rag/chunker.py`) — paragraph→sentence split, merge to `rag_chunk_size` tokens, `rag_chunk_overlap` overlap. No external deps.
- **Ingest endpoints**: `POST /ingest` now accepts `chunk=true`; `POST /ingest/url` and `POST /ingest/upload` call Docling (requires `DOCLING_URL`), chunk and embed. Returns 503 with clear message if Docling is not configured.

## P2P hardware-aware mesh (implemented 2026-03-26)
- Each node advertises GPU VRAM, chip family and RAM via `PeerCapabilities` (p2p/capabilities.py)
- Hardware profile is detected at startup via `detect_machine_profile()` and injected into `NodeIdentity`
- `select_route()` in cluster.py filters remote candidates by VRAM when `model_size_gb > local_vram`
- `P2PProvider._resolve_peer()` in router/providers/p2p.py prefers VRAM-capable peers (sorted by gpu_vram_gb desc)
- VRAM size registry in `router/model_sizes.py`: `get_model_size_gb(model)` + param-count heuristic fallback
- OllamaProvider auto-pulls missing models via `_ensure_model()` / `_pull_model()` before first use
- Tower (Quadro P2000 5GB) handles small models ≤4.5GB; KXKM-AI (RTX 4090 24GB) receives large models

## Suite Numérique (deployed 2026-03-27)
- All services on Tower, routed via Traefik on Photon (VM)
- SSO: Keycloak `auth.saillant.cc` (realm `zacus`), forward-auth + OIDC natif
- SMTP: Brevo (`smtp-relay.brevo.com:587`, user `a556ee001@smtp-brevo.com`)
- DB: mascarade-postgres (shared), Redis mascarade (shared)

### Services
| Service | URL | Port | SSO | DB |
|---|---|---|---|---|
| Conversations | conversations.saillant.cc | 8082 | forward-auth | postgres/conversations |
| Docs/Impress | docs.saillant.cc | 8073 | forward-auth | postgres/impress |
| Meet | meet.saillant.cc | 8084 | forward-auth | postgres/meet |
| Drive | drive.saillant.cc | 8086 | forward-auth | postgres/drive |
| People | people.saillant.cc | 8087 | forward-auth | postgres/people |
| Messages | messages.saillant.cc | 8090 | forward-auth | postgres/messages |
| Calendars | calendars.saillant.cc | 8089 | forward-auth | postgres/calendars |
| Grist | grist.saillant.cc | 8484 | OIDC natif | postgres/grist |
| Dolibarr | erp.saillant.cc | 8488 | forward-auth | postgres/dolibarr |
| DocuSeal | signature.saillant.cc | 7070 | forward-auth | SQLite |
| Garage S3 | s3.saillant.cc | 3900 | — | LMDB |
| Matrix/Synapse | matrix.saillant.cc | 8008 | — | postgres/synapse |
| Element | chat.saillant.cc | 8080 | — | — |
| Transfert | transfert.saillant.cc | 3000 | forward-auth | — |

### Repos
- `electron-rare/suite-numerique` — conversations + docs/impress compose
- `electron-rare/suite-apps` — drive, people, messages, calendars compose
- `electron-rare/meet-saillant` — meet + LiveKit compose
- `electron-rare/oidc2fer` — fork proconnect-gouv, SAML→OIDC bridge Renater

## Open Buro alignment (planned)
- Standard EU d'interopérabilité pour suites collaboratives souveraines
- Spec: https://openburo.eu/
- Alignment doc: `docs/OPENBURO_ALIGNMENT.md`
- Target endpoints: `/openburo/apps`, `/openburo/events`, `/openburo/objects/{type}`, `/openburo/workspaces`, `/openburo/search`
- Phase 1: App registry + Event bus (Redis Streams/CloudEvents) + Business Objects schemas
