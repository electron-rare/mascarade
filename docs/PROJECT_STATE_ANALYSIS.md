# Project State Analysis — 2026-03-16

Analyse automatisee de l'etat complet du projet mascarade, tous services confondus.

## Resume executif

Le projet mascarade est un systeme d'orchestration LLM multi-service compose de:
- Un moteur Python (`core/`) avec routage multi-provider, agents, P2P, observabilite
- Une facade API TypeScript (`api/`) sur Hono
- Un frontend React (`web/`) avec Vite et TailwindCSS
- Une infrastructure de deploiement Docker Compose (`deploy/`) avec stack d'observabilite complete
- Des pipelines de fine-tuning (`finetune/`) avec support GPU distribue
- Un outillage operateur (`scripts/`) de 100+ scripts

Niveau de maturite: **Avance** pour le core et l'infra, **Moyen** pour le frontend et les tests d'integration.

---

## Etat par service

### core/ — Moteur Python

| Metrique | Valeur |
|----------|--------|
| Langage | Python 3.11+ |
| Framework | FastAPI + Uvicorn |
| Modules principaux | 18 (agents, router, orchestrator, p2p, cache, etc.) |
| Fichiers test (test_*.py) | 240 |
| Providers LLM | 7 (Claude, OpenAI, Mistral, Google, HF, Ollama, llama_cpp) |
| Fichier serveur | `server.py` (91 KB) |
| Fichier cluster | `cluster.py` (41 KB) |
| Dependencies | 25+ (fastapi, pydantic, httpx, anthropic, openai, redis, etc.) |
| Linting | ruff + black (line-length=100) |
| Typing | mypy strict |

**Modules:**

| Module | Role | Status |
|--------|------|--------|
| `router/` | Routage multi-provider avec strategies (cheapest/fastest/best) | Actif |
| `agents/` | Factory et registry d'agents | Actif |
| `orchestrator/` | Orchestration seq/par/pipeline avec OrchestrationContext | Recemment refactorise |
| `p2p/` | Reseau pair-a-pair avec libp2p | Actif |
| `cache/` | Couche Redis | Actif |
| `load_balancer/` | Repartition de charge inter-providers | Actif |
| `resilience/` | Retry, fallback, circuit breaker (aiobreaker) | Actif |
| `observability/` | OpenTelemetry tracing | Actif |
| `metrics/` | Export Prometheus | Actif |
| `finetune/` | Integration pipeline fine-tuning (8 agents) | Cree, partiellement teste |
| `integrations/` | ComfyUI, CAD, knowledge-base, GitHub dispatch | Actif |
| `mcp/` | Model Context Protocol | Actif |
| `analytics/` | Analytique et metriques avancees | Actif |
| `conversation/` | Gestion des conversations | Actif |
| `db/` | Abstraction base de donnees | Actif |
| `dispatch/` | Dispatch de requetes | Actif |
| `benchmarks/` | Benchmarking performance | Actif |
| `tools/` | Framework d'integration d'outils | Actif |

**Risques:**
- `server.py` a 91 KB — candidat au decoupage
- `cluster.py` a 41 KB — idem
- Tests non executables sans `.venv` local (cf. audit F-006)
- Regressions P2P/cluster sur chemins reseau local

---

### api/ — Facade TypeScript

| Metrique | Valeur |
|----------|--------|
| Langage | TypeScript (ES modules) |
| Framework | Hono 4.x sur Node 20 |
| Fichiers route | 31 |
| Fichiers middleware | 10 |
| Fichiers test (*.test.ts) | 12 |
| Test runner | Vitest 4.x |

**Structure:**

| Repertoire | Role | Fichiers |
|------------|------|----------|
| `routes/` | Endpoints API (agents, cluster, p2p, cad, killlife, ops) | 31 |
| `middleware/` | Auth, rate-limit, security, logging | 10 |
| `lib/` | Utilitaires partages | 9 |
| `client/` | Client d'integration vers core:8100 | 4 |

**Risques:**
- `MASCARADE_API_KEY` vide en runtime = routes publiques (cf. audit F-003)
- Couverture de tests faible par rapport au nombre de routes

---

### web/ — Frontend React

| Metrique | Valeur |
|----------|--------|
| Langage | TypeScript/TSX |
| Framework | React 19, Vite 6, TailwindCSS 3 |
| Pages | 20 |
| Composants | 6 |
| Hooks | 4 |
| Tests | 0 |

**Pages principales:**
- Dashboard, metrics, logs, infra
- Agents, playground, orchestrate
- Knowledge browser, P2P mesh, Kill_LIFE workflows

**Risques:**
- **Aucun test frontend** — regressions UI non detectees
- Bridge historique vers `crazy_life` — responsabilites ambigues

---

### deploy/ — Infrastructure

| Metrique | Valeur |
|----------|--------|
| Dockerfiles | 5 (api, core, edge-proxy, ops-agent, generate-audio) |
| Sous-repertoires | 19 |
| Services docker-compose | 20+ |

**Stack d'observabilite:**

| Composant | Role | Status |
|-----------|------|--------|
| Prometheus | Collecte metriques | Deploye |
| Grafana | Dashboards | Deploye |
| Loki | Aggregation logs | Deploye |
| Tempo | Tracing distribue | Deploye |
| OpenTelemetry Collector | Instrumentation | Deploye |
| ClickHouse | Analytics OLAP | Deploye |

**Services specialises:**

| Service | Role |
|---------|------|
| edge-proxy | Proxy edge avec TLS |
| ops-agent | Agent operateur |
| ops-console | Console operations |
| apple_llm_api | Integration CoreML |
| audio_gen_api | Synthese vocale |
| cad/ | Sidecars CAD |

**Risques:**
- Build web salit le repo (artefacts suivis par Git, cf. audit F-007)
- Pression memoire/swap sur Tower (cf. audit F-001)
- Surface reseau publique elargie (cf. audit F-002)

---

### finetune/ — Pipelines d'entrainement

| Metrique | Valeur |
|----------|--------|
| Sous-repertoires | 58 |
| Agents pipeline | 8 (researcher, documentalist, teacher, archivist, student, analyst, reinforcer, validator) |
| Scripts principaux | pipeline.py, train_local.py, train_cpu.py, train_dpo.py |
| Projets KiCAD | 3 (mcp_server, fabrication_toolkit, kic_ai) |
| Datasets | 12 repertoires |
| Research probes | 12 repertoires |

**Risques:**
- Agents partiellement testes (seuls Researcher et Documentalist valides)
- Pipeline complet non encore execute end-to-end
- Dependance a trl/peft sur machine GPU (KXKM-AI)

---

### scripts/ — Outillage operateur

| Metrique | Valeur |
|----------|--------|
| Total scripts | 101 |
| Compose/deploy | ~15 |
| Fine-tuning | ~20 |
| Modele management | ~10 |
| Health/monitoring | ~10 |
| TUI operateur | 3 (mesh_tui, finetune_tui, run_research) |

---

## CI/CD Pipeline

| Job | Scope | Trigger |
|-----|-------|---------|
| API tests | `api/` build + vitest | Push main/dev, PR |
| Web build | `web/` vite build | Push main/dev, PR |
| Core tests | `core/` pytest | Push main/dev, PR |
| Lint | ruff + black | Push main/dev, PR |
| Compose | docker-compose config | Push main/dev, PR |
| Docker | Build & push GHCR | Push main (after tests) |
| Fine-tune | GPU self-hosted | Manual dispatch |
| Deploy | SSH production | After Docker |
| Notify | Commit status | Always |

---

## Metriques globales

| Metrique | Valeur |
|----------|--------|
| Fichiers Python (core/) | ~7000+ |
| Fichiers TypeScript (api/ + web/) | ~135 |
| Tests Python | 240 fichiers |
| Tests TypeScript | 12 fichiers |
| Tests Frontend | 0 |
| Scripts operateur | 101 |
| Documentation | 49 fichiers |
| Services Docker | 20+ |
| Providers LLM | 7 |
| Agents fine-tuning | 8 |
| Noeuds P2P | 5 |
| Jobs CI/CD | 9 |

---

## Evaluation des risques

| # | Risque | Severite | Service | Ref Audit |
|---|--------|----------|---------|-----------|
| R-001 | Routes API publiques sans auth effective | **Critique** | api/ | F-003 |
| R-002 | Saturation memoire/swap sur Tower | **Critique** | deploy/ | F-001 |
| R-003 | Zero tests frontend | **Haute** | web/ | — |
| R-004 | server.py monolithique (91 KB) | **Haute** | core/ | — |
| R-005 | Surface reseau publique elargie | **Haute** | deploy/ | F-002 |
| R-006 | Healthchecks verts malgre erreurs applicatives | **Haute** | core/ | F-004 |
| R-007 | Build web modifie fichiers suivis | **Moyenne-Haute** | web/ | F-007 |
| R-008 | Pipeline fine-tuning non valide e2e | **Moyenne-Haute** | finetune/ | — |
| R-009 | Observabilite GPU incomplete dans ops | **Moyenne-Haute** | deploy/ | F-005 |
| R-010 | Chain Python locale ambigue (venv-dependante) | **Moyenne** | core/ | F-006 |
| R-011 | Couplage fort au filesystem local | **Moyenne-Haute** | scripts/ | F-013 |

---

## Activite recente (Git)

| Commit | Description |
|--------|-------------|
| `3ce6220` | Merge auto-claude/029-create-missing-orchestrator-context-file |
| `f5e6b44` | Create OrchestrationContext dataclass |
| `77eaa17` | Merge PR #23 sync/main-convergence |
| `c0a5409` | Reconcile sync branch with latest main |
| `c272708` | Fix orchestrator retry and fallback compatibility |
| `4237445` | Fix cache import compatibility, relax aiobreaker pin |
| `defb976` | Merge feat/frontend-pr1-stability |
| `1f45ac9` | Merge feat/apple-coreml-runtime-pristine |

**Focus actuel:** Refactoring orchestrateur, convergence multi-branches, stabilite integration.

---

## Priorites recommandees

| # | Action | Effort | Impact |
|---|--------|--------|--------|
| 1 | Activer auth API (MASCARADE_API_KEY) | 15 min | Critique |
| 2 | Ajouter tests frontend minimaux | 2h | Haute |
| 3 | Decouper server.py en modules | 4h | Haute |
| 4 | Corriger build hermetique web/ | 1h | Moyenne-Haute |
| 5 | Valider pipeline fine-tuning e2e | 4h | Moyenne-Haute |
| 6 | Completer observabilite GPU dans ops | 1h | Moyenne |
| 7 | Documenter bootstrap test unifie | 30 min | Moyenne |
| 8 | Push mascarade + verifier CI | 15 min | Basse |
