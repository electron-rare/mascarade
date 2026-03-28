# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Mascarade is a personal agentic orchestration system: multi-provider LLM router, agent registry, DAG orchestrator, RAG pipeline, P2P mesh. Three stacks: Python core (FastAPI), TypeScript API (Hono), React cockpit (Vite).

## Commands

### Python core (core/)
```bash
cd core
python -m pytest                        # all tests (~2500 collected)
python -m pytest tests/test_router.py   # single file
python -m pytest -k test_cheapest       # single test by name
ruff check mascarade/ tests/            # lint
black mascarade/ tests/                 # format
mypy mascarade/                         # type check
```

### TypeScript API (api/)
```bash
cd api
npm run dev                             # dev server (tsx watch)
npm run build                           # tsc compile
npm test                                # vitest (~458 tests)
```

### React cockpit (web/)
```bash
cd web
npm run dev                             # vite dev server
npm run build                           # production build
npm test -- --run                       # vitest (~65 tests)
```

### Docker
```bash
docker compose up                       # full stack from project root
# Core :8100, API :3100
```

## Architecture

```
┌─────────────────────────────────────────────────────┐
│  web/ (React + Vite)                                │
│  Cockpit UI → calls API                             │
├─────────────────────────────────────────────────────┤
│  api/ (Hono + Node)                                 │
│  Auth, WebSocket, proxies to core                   │
├─────────────────────────────────────────────────────┤
│  core/mascarade/ (FastAPI)                           │
│  ┌──────────┐ ┌──────────┐ ┌────────────┐          │
│  │  Router   │ │ Orchestr.│ │ RAG Pipeline│          │
│  │ 34 provid.│ │ DAG/Plan │ │ embed→rank │          │
│  └────┬─────┘ └────┬─────┘ └────┬───────┘          │
│       │             │             │                   │
│  ┌────┴─────────────┴─────────────┴───────┐         │
│  │  Agents (35) · MCP · A2A · P2P Mesh    │         │
│  └────────────────────────────────────────┘         │
└─────────────────────────────────────────────────────┘
```

### Key modules in core/mascarade/
- **router/** — `LLMProvider` base class (`providers/base.py`), 34 provider implementations, routing strategies (cheapest/fastest/best/specific), circuit breaker
- **routers/** — FastAPI route files (34 modules): `/v1/api/chat`, `/v1/api/rag/*`, `/v1/graph/*`, `/openburo/*`, etc.
- **orchestrator/** — `engine.py` (sequential/parallel/pipeline), `planner.py` (Plan-and-Execute), `state_graph.py` (LangGraph-inspired StateGraph)
- **agents/** — `AgentRegistry`, agent definitions, skills, ANE prompt profiles
- **rag/** — `pipeline.py` orchestrates: intent → embed → hybrid_search → rerank → generate. Embeddings with auto-fallback chain, cross-encoder reranker, semantic cache (Qdrant + Redis)
- **p2p/** — Hardware-aware mesh: `capabilities.py` (VRAM/GPU detection), `cluster.py` (route selection by VRAM)
- **node_engine/** — DAG execution engine with typed workers
- **observability/** — OTel, OpenLLMetry, Langfuse integrations

### Key patterns
- All LLM providers implement `LLMProvider` base class
- Agents registered via `AgentRegistry`
- Router dispatches based on strategy; `model_sizes.py` maps models to VRAM requirements
- Config via Pydantic Settings (`config.py`), env vars override everything
- Async everywhere: httpx, async providers, `asyncio_mode = "auto"` in pytest

## Infrastructure

| Machine | Role | Specs | SSH |
|---------|------|-------|-----|
| Tower | Primary server | 12 CPU, 32GB, Quadro P2000 | `clems@tower` |
| Photon VM | Mesh secondary | 4 vCPU, 6.8GB | `cils@192.168.0.119` |
| KXKM-AI | GPU node | RTX 4090 24GB | `kxkm@kxkm-ai` |
| Mac | Dev machine | 192.168.0.210 | — |

- mascarade-core on port 8100, API on 3100
- Deploy repo on VM: `/root/mascarade-deploy-main/`
- P2P mesh: Tower handles ≤4.5GB models, KXKM-AI receives large models

## Code style
- Python: ruff + black, line-length 100, target py311
- TypeScript: tsc strict
- Pydantic v2 for all models
- No local model loading during dev (use remote providers)

## Suite Numérique
All services on Tower, routed via Traefik on Photon. SSO: Keycloak `auth.saillant.cc` (realm `zacus`). Shared DB: mascarade-postgres + Redis.

Key services: Conversations (:8082), Docs (:8073), Meet (:8084), Drive (:8086), Grist (:8484), Dolibarr/ERP (:8488), Matrix (:8008).

Repos: `electron-rare/suite-numerique`, `electron-rare/suite-apps`, `electron-rare/meet-saillant`, `electron-rare/oidc2fer`.

## Open Buro
EU interoperability standard alignment. Endpoints: `/openburo/apps`, `/openburo/events`, `/openburo/objects/{type}`. Phase 1 done: App registry + Event bus (Redis Streams/CloudEvents) + Business Objects schemas.
