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

## Architecture — Big Picture

```
                         ┌─────────────────────────────────┐
                         │        Web Frontend (web/)       │
                         │  React 19 + ReactFlow + Tailwind │
                         └──────────────┬──────────────────┘
                                        │ HTTP/WS
                         ┌──────────────▼──────────────────┐
                         │     TypeScript API (api/)        │
                         │  Hono — proxy + graph CRUD + WS  │
                         └──────────────┬──────────────────┘
                                        │ :8100
┌───────────────────────────────────────▼───────────────────────────────────┐
│                        Python Core (core/mascarade/)                      │
│                                                                           │
│  ┌─────────┐    ┌──────────────┐    ┌──────────────────────────────────┐ │
│  │ Agents  │───►│    Router    │───►│          Providers (30+)         │ │
│  │Registry │    │  (strategy)  │    │ Ollama│Claude│OpenAI│P2P│Prima.. │ │
│  └─────────┘    └──────┬───────┘    └──────────────────────────────────┘ │
│                        │                                                  │
│  ┌─────────────────────▼─────────────────────────────────────────────┐   │
│  │                    Node Engine (graph runtime)                     │   │
│  │  ┌─────┐  ┌─────┐  ┌────────────┐  ┌──────────┐  ┌───────────┐  │   │
│  │  │ AI  │  │ CAD │  │Electronics │  │ Hardware │  │Cross-Domain│  │   │
│  │  │Work.│  │Work.│  │  Worker    │  │  Worker  │  │ Adapters   │  │   │
│  │  └─────┘  └─────┘  └────────────┘  └──────────┘  └───────────┘  │   │
│  └───────────────────────────────────────────────────────────────────┘   │
│                                                                           │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐                │
│  │ Cluster  │  │   RAG    │  │   MCP    │  │Finetune  │                │
│  │P2P mesh  │  │ pipeline │  │ servers  │  │ pipeline │                │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘                │
└───────────────────────────────────────────────────────────────────────────┘
```

### Request Flow

1. Client → `api/` (Hono) → authenticates, routes
2. LLM requests → `core/mascarade/router/router.py` → selects provider by strategy
3. Router checks `model_sizes.py` for VRAM needs → `cluster.py` `select_route()` decides local vs remote
4. If remote → P2P mesh forwards to peer with sufficient VRAM
5. If distributed (70B+) → `PrimaCppProvider` → prima.cpp ring cluster

### Python Core (`core/mascarade/`)

The core is a FastAPI app (`server.py`) with routers mounted from `routers/`. All LLM calls flow through `router/router.py` which dispatches to providers based on strategy.

**Router → Providers**: Each provider implements `LLMProvider` (`router/providers/base.py`) with `send()`, `stream()`, `is_configured`, `available_models()`. Strategy: cheapest/fastest/best/specific. 30+ providers including Ollama, Claude, OpenAI, Mistral, Google, P2P, PrimaCpp, Bedrock, HuggingFace, MLX, vLLM, Exo.

**Node Engine** (`node_engine/`): Graph-based execution across 5 domain workers:
- `workers/ai/` — LLM inference, streaming, function calling, classify, summarize, agent dispatch
- `workers/cad/` — trace width (IPC-2221), BOM, DRC, stackup, thermal via, mesh ops, toolpath, FreeCAD/KiCad MCP
- `workers/electronics/` — SPICE simulation (ngspice), PCB DRC (kicad-cli), firmware compile (PlatformIO), 19 component nodes (JLCPCB, BOM, CPL, availability, datasheet, parametric search)
- `workers/hardware/` — ESP32 GPIO/sensors/OTA, DMX universe/fixture/scene, MIDI note/cc/pattern, serial I/O, safety interlocks
- `cross_domain/` — 5 adapters with 10 type mappings (AI↔CAD↔Electronics↔Hardware), `CrossDomainOrchestrator` (auto adapter insertion), `FederatedExecutor` (machine-capability planning)

Runtime (`runtime.py`): 3 execution modes — eager (parallel branches), lazy (demand-driven from targets), stepped (async generator, yields after each node). Graph validation, topological sort, persistence with versioned JSON. MVP Gate 7/7 passed: compilation 4.6ms/50-nodes, overhead 0.1ms/node, new node creation 77s.

**Cluster** (`cluster.py`): mDNS/Zeroconf `_mascarade._tcp.local.`, `PeerCapabilities` (gpu_vram_gb, chip_family, ram_gb), `select_route()` filters by VRAM, 3786 loc P2P module with discovery, transport, pubsub, relay, auth, metrics.

**Config**: `config.py` via `pydantic-settings`. All env vars. `.env` gitignored.

### TypeScript API (`api/`)

Hono on Node.js. Proxies to core :8100. Node engine graph CRUD stored as JSON on filesystem. WebSocket for streaming. 9 node-engine endpoints.

### Web Frontend (`web/`)

React 19 + Router 7 + Tailwind + @xyflow/react (ReactFlow). Code-split with React.lazy. Factory 4.0 pages: NodeEngineGraph, HardwareFleet, AgentControl, McpControl, ProductionPipeline.

## Infrastructure — 5-Machine P2P Mesh

```
         LAN 192.168.0.x              Tailscale 100.x.x.x
    ┌──────────────────────┐       ┌─────────────────────────┐
    │ Tower (.120)         │       │ KXKM-AI (100.87.54.119) │
    │ PRIMARY — 87 cont.   │       │ 28CPU/64GB/RTX 4090     │
    ├──────────────────────┤       ├─────────────────────────┤
    │ Mac CILS (.210)      │◄─────►│ GrosMac (100.80.178.42) │
    │ Dev — TS:100.126     │bridge │ M5/16GB/ANE             │
    ├──────────────────────┤       ├─────────────────────────┤
    │ Photon VM (.119)     │◄─────►│ kxkm-dev (100.76)       │
    │ Bridge — TS:100.112  │       │ kxkm-prod (100.97)      │
    └──────────────────────┘       └─────────────────────────┘
```

| Machine | Role | SSH | Specs | Ollama models |
|---------|------|-----|-------|---------------|
| Tower | Primary (87 containers) | `clems@tower` | 12 CPU, 32GB, P2000 | devstral, deepseek-r1:8b, qwen2.5-coder:7b, mascarade-* |
| KXKM-AI | GPU compute (15 containers) | via Photon: `ssh cils@192.168.0.119 "ssh kxkm@100.87.54.119 '...'"` | 28 CPU, 64GB, RTX 4090 | qwen3-coder:18G, codestral:12G, devstral:14G, 30+ models |
| GrosMac | Apple Silicon | via Photon: `ssh cils@192.168.0.119 "ssh electron@100.80.178.42 '...'"` | M5, 10 cores, 16GB | qwen2.5:1.5b |
| Photon | LAN↔Tailscale bridge | `cils@192.168.0.119` (root pw: DockerVM2026) | 4 vCPU, 6.8GB | — |
| Mac CILS | Development | local | i7, 16GB | mellum-4b, qwen2.5-coder:1.5b, llama3.2:1b |

**Deploy on Tower**: containers run from `/root/mascarade-deploy-main/` (NOT `/mascarade/`). Always pull both repos.

**Never stop Ollama** on any machine — fine-tuning and prima.cpp coexist with Ollama.

**Prima.cpp ring** (distributed 70B+ inference): built on all 4 machines, QwQ-32B downloaded on Tower+KXKM-AI, NAT relay via Photon. Ring script: `scripts/prima_ring.sh`.

**Factory 4.0**: `https://factory.saillant.cc` — Cloudflare tunnel via Tower edge proxy.

## Key Patterns

- **Async everywhere**: all providers, agents, node workers use `async def`. No sync I/O in the hot path.
- **Pydantic models**: data structures, config (`Settings(BaseSettings)`), API request/response schemas. Use `model_dump()` not `.dict()`.
- **Circuit breakers**: `aiobreaker` wraps all provider calls. Retry via `tenacity` with `make_retry()` factory.
- **Conditional imports**: heavy deps (libp2p, litellm, mlx, torch) use `try/except ImportError` so core starts without them.
- **Provider lifecycle**: `providers/__init__.py` registers each provider in a try/except block. `is_configured` property checks env vars. `Router._register_defaults()` skips unconfigured providers.
- **Node Engine dispatch**: each domain worker has `_NODE_CLASSES: dict[str, type]` mapping `node_type` strings to node classes. `execute(node_type, inputs, config, context)` looks up and instantiates the node.
- **Cross-domain adapters**: `supported_mappings()` → `list[AdapterMapping]`, `convert(source_data, mapping)` → transformed data. `CrossDomainOrchestrator` auto-inserts adapters at domain boundaries in a graph.
- **VRAM-aware routing**: `get_model_size_gb(model)` from `model_sizes.py` → `select_route()` in `cluster.py` compares to `peer.gpu_vram_gb` → dispatches to best peer.
- **Secret handling**: `pydantic.SecretStr` for API keys in config. Use `secret_value(settings.foo)` helper (not `.get_secret_value()` directly) — handles both `SecretStr` and plain strings.
- **Test mocking**: always patch where the name is **used** (e.g., `mascarade.routers.chat.settings`), not where it's **defined** (e.g., `mascarade.config.settings`). Empty `set()` is falsy in Python — use `if x is not None` not `x or default`.

## Pytest Notes

- Default addopts includes `--cov-report=html` which may fail without coverage plugin — use `--override-ini="addopts="` to skip
- Test venv at `/tmp/mascarade-test-venv/` has all deps installed
- `asyncio_mode = "auto"` in pyproject.toml — async tests run automatically
- Tests mock providers via `unittest.mock.patch` — always patch the import path where the name is used, not where it's defined
