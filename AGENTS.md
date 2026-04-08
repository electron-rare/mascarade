<!-- Generated: 2026-04-07 -->

# AGENTS.md — Mascarade Agentic Orchestration Platform

## Purpose

Mascarade is a personal agentic orchestration system with three integrated stacks:
- **Core** (Python/FastAPI :8100): 34 LLM providers, 35+ autonomous agents, 50+ node types, RAG pipeline, P2P mesh
- **API** (TypeScript/Hono :3100): 31 routes, WebSocket-driven execution, real-time node editor
- **Web** (React/Vite :5173): 22 feature pages, operations cockpit UI

**Key Stats**: 55K+ LOC, 2500+ core tests, 458 API tests, 65 web tests

---

## Key Files & Subdirectories

| Path | Purpose | Key Content |
|------|---------|-------------|
| `core/mascarade/router/` | Multi-provider LLM routing | 34 providers (OpenAI, Anthropic, Mistral, Google, etc.), fallback logic |
| `core/mascarade/agents/` | Autonomous agents | 35+ domain-specific agents (KiCad, FreeCAD, Firmware, SPICE) |
| `core/mascarade/node_engine/` | Cross-domain DAG orchestration | 50+ node types (AI, CAD, Electronics, Hardware, MIDI) |
| `core/mascarade/rag/` | RAG pipeline | Intent, embedding, hybrid search, reranking, generation |
| `core/mascarade/orchestrator/` | Workflow coordination | Sequential, parallel, pipeline, plan-and-execute strategies |
| `core/mascarade/p2p/` | Distributed mesh | Hardware detection, topology-aware routing, load balancing |
| `api/src/routes/` | API handlers | 31 routes (chat, agents, CAD, finetune, node-engine, OpenBuro) |
| `web/src/pages/` | UI pages | 22 pages (Dashboard, Agents, Playground, CAD, Infrastructure, etc.) |

---

## For AI Agents: Working Instructions

### Setup
```bash
cd /home/kxkm/mascarade-main
docker-compose up  # Spins up core :8100, api :3100, web :5173
```

### Testing
```bash
cd core && python -m pytest -v           # 2500+ tests
cd api && npm test                       # 458 tests
cd web && npm test -- --run              # 65 tests
```

### Development
```bash
cd core
ruff check mascarade/ && black mascarade/ && mypy mascarade/

cd api
npx tsc --noEmit && npm test

cd web
npm run build && npm test
```

### Common Patterns

**Add a Provider** → `core/mascarade/router/providers/my_provider.py`, implement `LLMProvider` interface, auto-discovered.

**Add an Agent** → `core/mascarade/agents/my_agent.py`, implement `Agent` interface, register via `AgentRegistry`.

**Add a Node Type** → `core/mascarade/node_engine/workers/mydomain/my_node.py`, implement `Worker` interface, register in registry.

**Add API Route** → `api/src/routes/myroute.ts`, export handler, register in router.

**Add Web Page** → `web/src/pages/MyPage.tsx`, add route in navigation, write tests in `__tests__/`.

### Debugging
```bash
docker-compose logs -f mascarade-core    # Core logs
curl http://localhost:8100/health        # Health check
scripts/mascarade-health.sh              # Full stack health
```

### Key Resources
- Main entry: `CLAUDE.md`
- Deployment: `core/DEPLOYMENT_GUIDE.md`
- P2P mesh: `P2P_NETWORK_README.md`
- Fine-tuning: `FINE_TUNING_GUIDE.md`
- E2E tests: `E2E_VERIFICATION.md`

---

**Git**: Commit to `dev`, open PR with clear description. CI runs pytest + npm test + tsc.
