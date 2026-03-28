# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Build & Test Commands

```bash
# Python core
cd core && python -m pytest                          # full suite (2056+ tests)
cd core && python -m pytest tests/test_node_engine.py --override-ini="addopts=" -q  # node engine only (125 tests)
cd core && python -m pytest tests/test_foo.py -k "test_bar" --override-ini="addopts=" -v  # single test
cd core && ruff check .                              # lint
cd core && ruff format .                             # format

# TypeScript API
cd api && npm run dev                                # dev server (tsx watch)
cd api && npm run build                              # compile (tsc)
cd api && npm run test                               # vitest

# Web frontend
cd web && npm run dev                                # vite dev server
cd web && npm run build                              # tsc + vite build
cd web && npm run test                               # vitest

# Docker
docker compose --profile core up -d core             # start core container
docker compose --profile core build core             # rebuild core image
```

## Architecture

**Monorepo**: Python core (`core/`) + TypeScript API gateway (`api/`) + React frontend (`web/`).

### Python Core (`core/mascarade/`)

The core is a FastAPI app (`server.py`) that provides LLM orchestration, agent execution, and a universal node engine.

**Router → Providers**: All LLM calls go through `router/router.py` which dispatches to providers based on strategy (cheapest/fastest/best/specific). Each provider implements `LLMProvider` from `router/providers/base.py`. There are 30+ providers (Ollama, Claude, OpenAI, Mistral, Google, P2P, PrimaCpp, etc.).

**Node Engine** (`node_engine/`): Graph-based execution system spanning 5 domain workers:
- `workers/ai/` — LLM inference, streaming, function calling, agent dispatch
- `workers/cad/` — IPC-2221 trace width, BOM, DRC, mesh ops, toolpath, FreeCAD/KiCad MCP
- `workers/electronics/` — SPICE simulation (ngspice), PCB DRC (kicad-cli), firmware compilation (PlatformIO), 19 component nodes
- `workers/hardware/` — ESP32 GPIO/sensors, DMX lighting, MIDI, serial I/O, safety interlocks
- `cross_domain/` — 5 adapters (AI↔CAD↔Electronics↔Hardware), orchestrator, federated executor

The runtime (`runtime.py`) supports 3 execution modes: eager (parallel), lazy (demand-driven), stepped (debug). The type system (`types.py`) uses Pydantic-frozen models with JSON Schema validation.

**Cluster** (`cluster.py`): mDNS/Zeroconf discovery (`_mascarade._tcp.local.`), hardware-aware VRAM routing via `select_route()`, P2P mesh across machines.

**Config**: All settings in `config.py` via `pydantic-settings` (env vars). `.env` is gitignored — must be configured per-machine.

### TypeScript API (`api/`)

Hono framework on Node.js. Proxies to the Python core on port 8100. Graph CRUD for node engine is handled locally with filesystem JSON storage. WebSocket support for live streaming.

### Web Frontend (`web/`)

React 19 + React Router 7 + Tailwind + @xyflow/react (ReactFlow) for graph editing. Code-split with React.lazy on all routes.

## Infrastructure — 5-Machine Mesh

| Machine | Role | SSH | Specs |
|---------|------|-----|-------|
| Tower | Primary server (87 containers) | `clems@tower` | 12 CPU, 32GB, P2000 |
| KXKM-AI | GPU compute | `kxkm@100.87.54.119` via Photon | 28 CPU, 64GB, RTX 4090 |
| GrosMac | Apple Silicon | `electron@100.80.178.42` via Photon | M5, 10 cores, 16GB |
| Photon | LAN↔Tailscale bridge | `cils@192.168.0.119` | 4 vCPU, 6.8GB |
| Mac CILS | Development | local | i7, 16GB |

Core runs on Tower (primary) + Photon (mesh). Deploy repo on Tower: `/root/mascarade-deploy-main/` (not `/mascarade/`).

**Never stop Ollama on any machine** — fine-tuning and prima.cpp must coexist with Ollama.

## Key Patterns

- **Async everywhere**: all providers, agents, node workers are async
- **Pydantic models**: all data structures, config, API schemas
- **Circuit breakers**: `aiobreaker` on all provider calls
- **Conditional imports**: heavy deps (libp2p, litellm, mlx) use try/except so core starts without them
- **Provider registration**: `providers/__init__.py` uses try/except blocks for each provider
- **Node Engine dispatch**: each worker has a `_NODE_CLASSES` dict mapping `node_type` strings to node classes
- **Cross-domain adapters**: `supported_mappings()` returns `AdapterMapping` list, `convert(source_data, mapping)` does the conversion

## Pytest Notes

- Default addopts includes `--cov-report=html` which may fail without coverage plugin — use `--override-ini="addopts="` to skip
- Test venv at `/tmp/mascarade-test-venv/` has all deps installed
- `asyncio_mode = "auto"` in pyproject.toml — async tests run automatically
- Tests mock providers via `unittest.mock.patch` — always patch the import path where the name is used, not where it's defined
