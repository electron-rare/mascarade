# Mascarade Workspace Instructions

## Scope

Monorepo à trois stacks. Ne pas mélanger les contextes ni les validations par défaut.

- `core/` : runtime Python FastAPI, routeur LLM, agents, RAG, P2P, Node Engine
- `api/` : gateway TypeScript Hono, auth, rate-limit, proxy vers core
- `web/` : bridge React Vite local ; le cockpit principal vit dans le repo externe `crazy_life`
- `finetune/` et `core/mascarade/finetune/` : pipeline de fine-tuning, à traiter comme un scope à part

Repos compagnons hors worktree : `crazy_life` pour le cockpit React complet, `Kill_LIFE` pour les serveurs MCP CAD.

## Stack Routing

- `core/**/*.py` : appliquer [.github/instructions/core-python.instructions.md](.github/instructions/core-python.instructions.md)
- `api/src/**/*.ts` : appliquer [.github/instructions/api-hono.instructions.md](.github/instructions/api-hono.instructions.md)
- `web/src/**/*.{ts,tsx}` : appliquer [.github/instructions/web-react.instructions.md](.github/instructions/web-react.instructions.md)
- `finetune/**` ou `core/mascarade/finetune/**` : appliquer [.github/instructions/finetune-pipeline.instructions.md](.github/instructions/finetune-pipeline.instructions.md)
- setup local, ports, dépendances, bootstrap : appliquer [.github/instructions/dev-environment.instructions.md](.github/instructions/dev-environment.instructions.md)

## Build And Test

Validation rapide, limitée au scope touché :

```bash
cd core && python -m pytest tests/test_router.py -q
cd api && npm test
cd web && npm test -- --run
cd e2e && npm exec playwright -- test tests/api/health.spec.ts
```

Validation complète avant livraison :

```bash
cd core && python -m pytest && ruff check mascarade/ tests/ && mypy mascarade/
cd api && npm run build && npm test
cd web && npm run build && npm test -- --run
```

Boucles de dev utiles :

```bash
cd api && npm run dev
cd web && npm run dev
cd core && python -m pytest --lf --tb=short
```

Stratégie de validation par impact :

- modif `core/` : pytest ciblé, puis `tests/test_router.py` pour tout changement provider/router
- modif `api/` : `npm test`, puis `npm run build` si contrat, middleware ou types changent
- modif `web/` : `npm test -- --run`, puis Playwright si flux UI impacté
- modif cross-stack ou auth/RAG/OpenBuro : voir [INTEGRATION_TESTING.md](INTEGRATION_TESTING.md) et [E2E_VERIFICATION.md](E2E_VERIFICATION.md)

## Architecture Boundaries

- `api/` orchestre et protège ; la logique provider, agent, RAG et orchestration vit dans `core/`
- Les providers sont gérés par le router et son circuit breaker ; ne pas instancier un provider directement depuis une route
- `core/` est async-first pour tout I/O réseau/disque
- Configuration via settings/env vars ; éviter les constantes d'environnement codées en dur
- `web/` consomme `api/` ; ne pas brancher `web/` directement sur `core/`
- Les routes OpenBuro restent séparées des routes internes classiques ; implémentation centrale dans `api/src/routes/openburo.ts`
- Les tests `node_engine` sont isolés du flux standard ; vérifier explicitement si ce périmètre change

## Working Conventions

- Garder les patches minimaux, déterministes et confinés à la stack concernée
- Préserver les contrats publics et l'ordre middleware `auth -> rate-limit -> CORS`
- `core/` : Pydantic v2 uniquement, validation aux frontières, pas de `@pytest.mark.asyncio` manuel si `asyncio_mode = "auto"`
- `api/` et `web/` : `tsc strict`, suivre les patterns déjà présents avant d'introduire une nouvelle abstraction
- Ne pas charger de modèles locaux pendant le dev si le flux prévu passe par les providers distants ou le routage multi-machine

## Setup Gotchas

- Python : activer le venv de `core/` avant les tests ou les imports échoueront
- Node : relancer `npm install` dans `api/` ou `web/` si build/tests cassent sans raison fonctionnelle
- Ports à garder libres pour le dev local : `8100`, `3100`, `5173`
- `web/` est un bridge local, pas la source canonique de l'UI opérateur complète
- Le routage Ollama peut fallback vers le mesh P2P ; un `MetalGPUError` côté provider n'est pas forcément bloquant
- Redis sert au cache/session, ClickHouse à l'analytics ; ne pas leur attribuer des rôles interchangeables

## Key References

- [CLAUDE.md](CLAUDE.md) : commandes détaillées, architecture, infra, providers, services
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) : diagrammes et frontières système
- [docs/API.md](docs/API.md) : endpoints, auth, conventions d'API
- [docs/PROJECT_STATE_ANALYSIS.md](docs/PROJECT_STATE_ANALYSIS.md) : état des modules et zones actives du repo
- [docs/testing/coverage-baseline.md](docs/testing/coverage-baseline.md) : état de couverture et priorités de tests
- [docs/e2e/README.md](docs/e2e/README.md) : conventions E2E
- [.github/instructions/core-python.instructions.md](.github/instructions/core-python.instructions.md)
- [.github/instructions/api-hono.instructions.md](.github/instructions/api-hono.instructions.md)
- [.github/instructions/web-react.instructions.md](.github/instructions/web-react.instructions.md)
- [.github/instructions/frontend-testing.instructions.md](.github/instructions/frontend-testing.instructions.md)
- [.github/instructions/dev-environment.instructions.md](.github/instructions/dev-environment.instructions.md)

## Next Customizations

Exemples pour voir ces instructions en action :

- `/fix core router fallback test regression`
- `/tests ajoute des tests ciblés pour api/src/routes/openburo.ts`
- `/create-prompt boucle test audit correctif pour la stack web`

Customisations utiles à créer ensuite :

1. `/create-instruction` pour un fichier dédié `e2e/**` avec conventions Playwright + mock API
2. `/create-agent` pour un reviewer cross-stack orienté contrats `api` ↔ `core`
3. `/create-prompt` pour une boucle de validation rapide par stack avant commit