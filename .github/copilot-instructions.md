# Mascarade Workspace Instructions

## Scope

Monorepo avec trois stacks distinctes : ne pas mélanger les contextes.
- `core/` : Python FastAPI runtime (port 8100)
- `api/` : TypeScript Hono API (port 3100)
- `web/` : React Vite bridge UI (l'UI cockpit principale est dans le repo externe `crazy_life`)

Repos compagnons hors worktree :
- `crazy_life` : cockpit React 19
- `Kill_LIFE` : MCP servers CAD + runtime canonique

Instructions de stack via `applyTo` dans `.github/instructions/`.

## Quick Stack Selection

- Si la demande touche `core/**/*.py` : appliquer `.github/instructions/core-python.instructions.md`.
- Si la demande touche `api/src/**/*.ts` : appliquer `.github/instructions/api-hono.instructions.md`.
- Si la demande touche `web/src/**/*.{ts,tsx}` : appliquer `.github/instructions/web-react.instructions.md`.

## Build And Test

Core (Python) :
```bash
cd core && python -m pytest
cd core && python -m pytest -k <pattern>
cd core && python -m pytest tests/test_router.py
cd core && ruff check mascarade/ tests/
cd core && black mascarade/ tests/
cd core && mypy mascarade/
```

API (TypeScript) :
```bash
cd api && npm run build
cd api && npm test
```

Web (React) :
```bash
cd web && npm run build
cd web && npm test
```

## Architecture Highlights

Détails complets : [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

Composants critiques :
- Router LLM : `core/mascarade/router/` (stratégies cheapest/fastest/best/specific, providers multiples)
- Agents : `core/mascarade/agents/` (9 agents en prod)
- Orchestrateur : `core/mascarade/orchestrator/` (sequential/parallel/pipeline + DAG)
- RAG : `core/mascarade/rag/` (BGE-M3 -> Qdrant -> fallback web, rerank)
- Node Engine : `core/mascarade/node_engine/`
- MCP : `core/mascarade/mcp/`
- P2P mesh : `core/mascarade/p2p/`
- OpenBuro : `api/src/routes/openburo.ts`

## Conventions

- Scope strict : limiter les changements à la stack concernée.
- Typage : Pydantic v2 côté core, `tsc strict` côté api/web.
- Async-first dans `core/` pour I/O.
- Validation aux frontières système (inputs user, API externes, config).
- Configuration par env vars via settings (pas de valeurs codées en dur quand évitable).
- Patches minimaux : lancer les checks de la stack touchée après édition.
- Ne pas charger de modèles locaux pendant le dev ; utiliser les providers distants.
- Config qualité : `core/pyproject.toml`, `core/.mypy.ini`, `ruff.toml`.

## Gotchas & Failsafes

- `core/mascarade/router/providers/ollama.py` : `MetalGPUError` peut basculer vers P2P sans être une panne bloquante.
- Tests core : `asyncio_mode = "auto"` dans `core/pyproject.toml` ; ne pas ajouter `@pytest.mark.asyncio` manuellement.
- Avant toute modif provider, relancer `cd core && python -m pytest tests/test_router.py`.
- Middleware API : ordre `auth -> rate-limit -> CORS` à conserver.
- `web/` est un bridge local ; l'UI cockpit complète vit dans `crazy_life` (externe).
- `core/conftest.py` ignore par défaut `tests/node_engine/*` et `tests/test_node_*` pendant la collecte standard.

## References

- [CLAUDE.md](CLAUDE.md) : commandes, architecture, infra
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) : architecture système
- [docs/API.md](docs/API.md) : endpoints et conventions API globales
- [docs/api/README.md](docs/api/README.md) : contrat API core
- [docs/audit/README.md](docs/audit/README.md) : audit packs
- [INTEGRATION_TESTING.md](INTEGRATION_TESTING.md) : tests d'intégration
- [E2E_VERIFICATION.md](E2E_VERIFICATION.md) : vérifications E2E
- [.github/instructions/core-python.instructions.md](.github/instructions/core-python.instructions.md) : règles Python core
- [.github/instructions/api-hono.instructions.md](.github/instructions/api-hono.instructions.md) : règles Hono API
- [.github/instructions/web-react.instructions.md](.github/instructions/web-react.instructions.md) : règles React web
