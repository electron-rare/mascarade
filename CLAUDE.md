# Mascarade — Conventions

## Project
- Mascarade is a personal agentic orchestration system
- Python core (agents, router, orchestrator) + TypeScript API (Hono)
- Deployed on VM 192.168.0.119 via Docker Compose

## Python (core/)
- Python 3.11+, use Pydantic for models
- Async everywhere (httpx, async providers)
- Run tests: `cd core && python -m pytest`
- Format: ruff

## TypeScript (api/)
- Hono framework on Node
- Run: `cd api && npm run dev`
- Build: `cd api && npm run build`

## Docker
- `docker compose up` from project root
- Core service on port 8100, API on port 3100

## Key patterns
- All LLM providers implement `LLMProvider` (core/mascarade/router/providers/base.py)
- Agents are registered in the `AgentRegistry`
- Router dispatches to providers based on strategy (cheapest/fastest/best/specific)
- Knowledge-base / CAD surfaces replace the old Notion-first operator path; remaining Notion code is legacy compatibility only

## P2P hardware-aware mesh (implemented 2026-03-26)
- Each node advertises GPU VRAM, chip family and RAM via `PeerCapabilities` (p2p/capabilities.py)
- Hardware profile is detected at startup via `detect_machine_profile()` and injected into `NodeIdentity`
- `select_route()` in cluster.py filters remote candidates by VRAM when `model_size_gb > local_vram`
- `P2PProvider._resolve_peer()` in router/providers/p2p.py prefers VRAM-capable peers (sorted by gpu_vram_gb desc)
- VRAM size registry in `router/model_sizes.py`: `get_model_size_gb(model)` + param-count heuristic fallback
- OllamaProvider auto-pulls missing models via `_ensure_model()` / `_pull_model()` before first use
- Tower (Quadro P2000 5GB) handles small models ≤4.5GB; KXKM-AI (RTX 4090 24GB) receives large models
