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
