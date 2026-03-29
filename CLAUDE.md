# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Mascarade is a personal agentic orchestration system: multi-provider LLM router, agent registry (242 agents, 9 production), DAG orchestrator, RAG pipeline (bge-m3 -> Qdrant -> SearXNG fallback), multi-machine Ollama routing, P2P mesh (5 nodes). Three stacks: Python core (FastAPI :8100), TypeScript API (Hono :3100), React cockpit (Vite). 42 services monitored via er-ops dashboard.

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

```raw
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
│  │  Agents (242) · MCP · A2A · P2P Mesh   │         │
│  └────────────────────────────────────────┘         │
└─────────────────────────────────────────────────────┘
```

### Key modules in core/mascarade/
- **router/** — `LLMProvider` base class (`providers/base.py`), 34 provider implementations, routing strategies (cheapest/fastest/best/specific), circuit breaker
- **routers/** — FastAPI route files (34 modules): `/chat/completions`, `/v1/api/rag/*`, `/v1/graph/*`, `/api/agents`, `/api/providers`, etc.
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
| photon | Traefik reverse proxy, CF tunnel, NAT relay | 4 vCPU, 6.8GB | `root@192.168.0.119` |
| Tower | Primary server (La Suite 8 services + API + Ollama CPU) | 12 CPU, 32GB, Quadro P2000 | `clems@192.168.0.120` |
| KXKM-AI | GPU inference (Ollama via SSH tunnel), fine-tuning | RTX 4090 24GB | `kxkm@100.87.54.119` |
| Cils | Web research (SearXNG, Browser-Use) | macOS Intel | `cils@100.126.225.111` |
| GrosMac | Dev machine (Apple M5) | `electron@100.80.178.42` | — |

- mascarade-core on port 8100, API on 3100
- Deploy repo on VM: `/root/mascarade-deploy-main/`
- Multi-machine Ollama routing: Tower CPU (qwen3:4b), KXKM-AI GPU (albert, mistral:7b, devstral, qwen3:8b, bge-m3)
- 42 services monitored via er-ops dashboard
- 9 production agents: ops-monitor, ops-deployer, ops-incident, ops-healthcheck, ops-security, web-researcher, lead-scorer, dolibarr-assistant, grist-data

## Code style
- Python: ruff + black, line-length 100, target py311
- TypeScript: tsc strict
- Pydantic v2 for all models
- No local model loading during dev (use remote providers)

## Suite Numerique (8 services)
All services on Tower, routed via Traefik on photon. SSO: Keycloak `auth.saillant.cc` (realm `zacus`). Shared DB: mascarade-postgres + Redis.

Key services: Conversations (:8082), Docs/Impress (:8073), Meet (:8084), Drive (:8086), Grist (:8484), Dolibarr/ERP (:8488), Matrix (:8008), Keycloak (:8085).

Repos: `electron-rare/suite-numerique`, `electron-rare/suite-apps`, `electron-rare/meet-saillant`, `electron-rare/oidc2fer`.

## Open Buro
EU interoperability standard alignment. Endpoints on API gateway (:3100): `/openburo/apps`, `/openburo/health`, `/openburo/ai/chat`, `/openburo/objects/*`, `/openburo/workspaces`, `/openburo/search`, `/openburo/events`, `/openburo/connectors/*`, `/openburo/notifications`. Connectors: Grist, Dolibarr, n8n webhooks. Phase 1 done: App registry + Event bus (Redis Streams/CloudEvents) + Business Objects schemas + AI chat + Search + Workspaces.
