# Consolidated Tasks — 16 mars 2026 (v1)

Consolidation de tous les TODO files et plans d'exécution en une liste unique, dédupliquée et priorisée.

## Mise à jour opératoire — 24/03/2026

- Lot actif de référence: `docs/plan/2026-03-24-sota-mascarade/active_execution_plan.md`
- Objectif immédiat: exécuter des lots courts, vérifiables, avec propriétaire explicite par module/spec et journalisation TUI.
- Décision: privilégier les correctifs structurels à faible risque et forte valeur (`router`, `auth gateway`, `docs/runbooks`, `tests de garde`) avant toute extension ambitieuse.
- Correctif démarré dans ce lot: durcissement du `CircuitBreaker` en `HALF_OPEN` avec budget de probes effectivement consommé.
- Backlog critiques identifiés par analyse croisée: secrets versionnés, auth fail-open Hono, fallback RBAC admin, surface réseau Docker trop large.

Sources: `docs/EXECUTION_PLAN_2026-03-10.md`, `docs/TODO_2026-03-10.md`, `TODO_IMPLEMENTE.md`, `TODO_VM.md`, `TODO_COCKPIT_OPS.md`, `TODO_CAD_KICAD.md`, `TODO_TUNNING_PARTY.md`, `TODO_AI_NOVEL_ENGINE.md`, `plan.md`

---

## État actuel (snapshot 16/03)

| Repo | Tests | Providers | Infra | Fine-tune |
|------|-------|-----------|-------|-----------|
| **mascarade** | 247/247 | 10 (7 actifs) | P2P mesh 5 nœuds, Docker UP | Pipeline complet, 2 runs OK |
| **Kill_LIFE** | 20/20 | — | PlatformIO à installer | — |
| **crazy_life** | 34/34 | — | — | — |

---

## Axe 1 — Mascarade Core: stabilisation & refactoring

### P0 — Push & CI
| # | Task | Effort | Blocker | Service | Deps |
|---|------|--------|---------|---------|------|
| 1.1 | - [ ] Push mascarade (all pending commits incl. finetune + webui + P2P) | 5 min | Non | core | — |
| 1.2 | - [ ] Vérifier CI GitHub Actions post-push | 10 min | Push 1.1 | core | 1.1 |

### P1 — server.py Decomposition (top refactoring candidate)
| # | Task | Effort | Blocker | Service | Deps |
|---|------|--------|---------|---------|------|
| 1.3 | - [ ] Split server.py (2700+ lines) en modules: routes/, middleware/, startup.py | 4h | Non | core | — |
| 1.4 | - [ ] Extraire route groups: /send, /v1/*, /agents/*, /p2p/*, /finetune/* | 2h | Non | core | 1.3 |
| 1.5 | - [ ] Vérifier 247 tests post-refactor | 30 min | Non | core | 1.4 |

### P2 — Provider Audit & Consistency
| # | Task | Effort | Blocker | Service | Deps |
|---|------|--------|---------|---------|------|
| 1.6 | - [ ] Audit 10 provider files pour pattern consistency (base.py interface) | 1h | Non | core | — |
| 1.7 | - [ ] Évaluer remplacement aiobreaker (unmaintained since 2021) par purgatory ou aiomisc | 1h | Non | core | — |
| 1.8 | - [ ] Quantifier et documenter legacy Notion code surface | 30 min | Non | core | — |
| 1.9 | - [ ] Fixer Ollama macOS Tahoe (Metal bfloat16 bug) ou confirmer llama.cpp comme remplacement permanent | 30 min | macOS update | core | — |

### P3 — Sécurisation
| # | Task | Effort | Blocker | Service | Deps |
|---|------|--------|---------|---------|------|
| 1.10 | - [ ] P2P auth reject_unsigned=true sur tous les nœuds | 15 min | Non | core | — |
| 1.11 | - [ ] Knowledge Base URL configurée | 15 min | Non | core | — |
| 1.12 | - [ ] Sécuriser API keys (Anthropic/OpenAI) — audit .env exposure | 15 min | Non | infra | — |

### P4 — Services locaux
| # | Task | Effort | Blocker | Service | Deps |
|---|------|--------|---------|---------|------|
| 1.13 | - [ ] Apple CoreML provider: vérifier et activer | 1h | Non | core | — |

---

## Axe 2 — API Gateway: nettoyage & alignment

### P1 — Route Consolidation
| # | Task | Effort | Blocker | Service | Deps |
|---|------|--------|---------|---------|------|
| 2.1 | - [ ] Résoudre port discrepancy: API_PORT=3100 vs Vite proxy target :3000 | 15 min | Non | api, web | — |
| 2.2 | - [ ] Auditer legacy `/api/*` routes vs `/v1/api/*` — plan de dépréciation | 1h | Non | api | — |
| 2.3 | - [ ] Réduire core.ts (29KB) — décomposer client proxy | 2h | Non | api | — |

### P2 — Testing
| # | Task | Effort | Blocker | Service | Deps |
|---|------|--------|---------|---------|------|
| 2.4 | - [ ] Augmenter couverture Vitest API (coverage baseline à mesurer) | 2h | Non | api | — |

---

## Axe 3 — Web Frontend: testing & quality

### P1 — Test Infrastructure
| # | Task | Effort | Blocker | Service | Deps |
|---|------|--------|---------|---------|------|
| 3.1 | - [ ] Ajouter Vitest + testing-library/react au frontend (0 tests actuellement) | 2h | Non | web | — |
| 3.2 | - [ ] Tests critiques: Dashboard, OpsHub, Settings (top 3 pages par taille) | 3h | Non | web | 3.1 |

### P2 — Large Page Decomposition
| # | Task | Effort | Blocker | Service | Deps |
|---|------|--------|---------|---------|------|
| 3.3 | - [ ] Décomposer Logs.tsx (59KB), OpsHub.tsx (53KB), Orchestrate.tsx (44KB) | 4h | Non | web | — |

---

## Axe 4 — Fine-tuning: pipeline completion

### P0 — Pipeline Live (en cours)
| # | Task | Effort | Blocker | Service | Deps |
|---|------|--------|---------|---------|------|
| 4.1 | - [ ] Tester distribute_task ft-research → GrosMac → résultats HF | 30 min | mesh connectivity | core | — |
| 4.2 | - [ ] Pipeline fine-tune via P2P distribute_task (pas SSH manuel) | 1h | 4.1 | core | 4.1 |
| 4.3 | - [ ] Analyste: benchmarks perplexité + vitesse (HumanEval) | 2h | llama-cli | core | — |
| 4.4 | - [ ] Archiviste: push résultat sur HuggingFace clemsail/ | 30 min | HF token | core | — |

### P1 — Alignment & Reinforcement
| # | Task | Effort | Blocker | Service | Deps |
|---|------|--------|---------|---------|------|
| 4.5 | - [ ] Ajouter GRPO dans ReinforcerAgent (reasoning, 5GB VRAM min) | 3h | Non | core | — |
| 4.6 | - [ ] DPO/SimPO cycle: Renforceur collecte erreurs → Teacher corrige → Student re-train | 4h | Training complete | core | 4.3 |
| 4.7 | - [ ] Validation: red-team + regression sur CILS | 2h | 4.6 | core | 4.6 |
| 4.8 | - [ ] Publication: Archiviste push modèle final validé sur HuggingFace | 30 min | 4.7 | core | 4.7 |
| 4.9 | - [ ] Auto-registration: modèle fine-tuné → provider mascarade | 1h | 4.8 | core | 4.8 |

### P2 — Batch Fine-tuning (finetune/ standalone)
| # | Task | Effort | Blocker | Service | Deps |
|---|------|--------|---------|---------|------|
| 4.10 | - [ ] Phase A SFT completion (~22h restantes, 13 domaines) | 22h | GPU time | finetune | — |
| 4.11 | - [ ] Phase B rejection sampling post-SFT | 4h | 4.10 | finetune | 4.10 |
| 4.12 | - [ ] Phase C DPO alignment | 4h | 4.11 | finetune | 4.11 |
| 4.13 | - [ ] Components dataset review + staging | 1h | Non | finetune | — |
| 4.14 | - [ ] Ajouter pytest au module finetune/ (0 tests standalone) | 2h | Non | finetune | — |

### P3 — Automatisation
| # | Task | Effort | Blocker | Service | Deps |
|---|------|--------|---------|---------|------|
| 4.15 | - [ ] Cycle continu: recherche hebdo nouvelles bases/datasets | 2h | Non | core | 4.9 |
| 4.16 | - [ ] Dataset mascarade-kicad sur HuggingFace | 2h | Non | finetune | — |
| 4.17 | - [ ] Surveiller Qwen3-Coder-Next (annonce mars 2026) | — | Externe | — | — |

---

## Axe 5 — Infrastructure & Observability

### P0 — Monitoring
| # | Task | Effort | Blocker | Service | Deps |
|---|------|--------|---------|---------|------|
| 5.1 | - [ ] Grafana dashboard P2P import | 15 min | Non | infra | — |
| 5.2 | - [ ] Prometheus alerting: peer_count < expected | 30 min | Non | infra | 5.1 |
| 5.3 | - [ ] Grafana consolidé: LLM + P2P + finetune metrics | 1h | Non | infra | 5.1 |
| 5.4 | - [ ] Langfuse traces agents e2e | 1h | Non | core, infra | — |

### P1 — VM Finalization
| # | Task | Effort | Blocker | Service | Deps |
|---|------|--------|---------|---------|------|
| 5.5 | - [ ] Graphiti MCP Server sur VM (knowledge graph) | 1h | Non | infra | — |
| 5.6 | - [ ] Network validation: TLS/DNS rules | 30 min | Non | infra | — |
| 5.7 | - [ ] Personal light stack healthchecks scaffolding | 30 min | Non | infra | — |

### P2 — MCP Registry
| # | Task | Effort | Blocker | Service | Deps |
|---|------|--------|---------|---------|------|
| 5.8 | - [ ] Registry-first MCP: décider firecrawl ajout config locale | 15 min | Non | infra | — |
| 5.9 | - [ ] Registry-first MCP: décider mem0 ajout config locale | 15 min | Non | infra | — |
| 5.10 | - [ ] Registry-first MCP: appliquer shadow config sur ~/.codex/config.toml | 15 min | Hors sandbox | infra | — |

---

## Axe 6 — AI Novel Engine

### P1 — Runtime Stabilisation
| # | Task | Effort | Blocker | Service | Deps |
|---|------|--------|---------|---------|------|
| 6.1 | - [ ] Compléter baseline validation (all runtime models) | 1h | Non | core | — |
| 6.2 | - [ ] Stabiliser secondary models (ollama:qwen2.5:1.5b Metal crash) | 1h | Metal bug | core | — |
| 6.3 | - [ ] Exposer single-model constraint clairement dans API | 30 min | Non | core, api | — |

---

## Axe 7 — Écosystème: boucle complète

### P0 — Cross-repo Integration
| # | Task | Effort | Blocker | Service | Deps |
|---|------|--------|---------|---------|------|
| 7.1 | - [ ] crazy_life UI → mascarade API → LLM → résultat (e2e) | 2h | crazy_life runtime | externe | — |
| 7.2 | - [ ] mascarade API → Kill_LIFE MCP → résultat (e2e) | 2h | Kill_LIFE MCP | externe | — |
| 7.3 | - [ ] KILL_LIFE_ROOT dans .envrc + npm run dev:all test | 15 min | Non | externe | — |

### P1 — Kill_LIFE Firmware
| # | Task | Effort | Blocker | Service | Deps |
|---|------|--------|---------|---------|------|
| 7.4 | - [ ] pip install platformio | 5 min | Non | externe | — |
| 7.5 | - [ ] pio run -e native && pio test -e native | 15 min | 7.4 | externe | 7.4 |
| 7.6 | - [ ] Premier firmware WiFi scanner (spec → impl → test → gate S0→S1) | 8h | 7.5 | externe | 7.5 |

### P2 — Advanced Integration
| # | Task | Effort | Blocker | Service | Deps |
|---|------|--------|---------|---------|------|
| 7.7 | - [ ] ZeroClaw + n8n integration | 4h | Non | infra | — |
| 7.8 | - [ ] KiCad Docker Compose integration | 2h | Non | infra | — |
| 7.9 | - [ ] Cockpit CAD UI page | 4h | Non | web | 7.8 |

---

## Priorités ordonnées (top 20)

| # | Action | Effort | Blocker? | Axe | Service |
|---|--------|--------|----------|-----|---------|
| 1 | Push mascarade (all pending) | 5 min | Non | 1 | core |
| 2 | Vérifier CI post-push | 10 min | Push | 1 | core |
| 3 | P2P auth reject_unsigned | 15 min | Non | 1 | core |
| 4 | Résoudre port discrepancy API | 15 min | Non | 2 | api/web |
| 5 | Grafana dashboard P2P import | 15 min | Non | 5 | infra |
| 6 | Tester distribute_task ft-research | 30 min | Mesh | 4 | core |
| 7 | Knowledge Base URL config | 15 min | Non | 1 | core |
| 8 | MCP shadow config apply | 15 min | Sandbox | 5 | infra |
| 9 | Analyste: benchmarks HumanEval | 2h | llama-cli | 4 | core |
| 10 | Archiviste: push HF clemsail/ | 30 min | HF token | 4 | core |
| 11 | Split server.py en modules | 4h | Non | 1 | core |
| 12 | Provider audit (10 providers) | 1h | Non | 1 | core |
| 13 | Évaluer remplacement aiobreaker | 1h | Non | 1 | core |
| 14 | Ajouter tests frontend (Vitest) | 2h | Non | 3 | web |
| 15 | Ajouter pytest finetune/ | 2h | Non | 4 | finetune |
| 16 | DPO/SimPO cycle complet | 4h | Training | 4 | core |
| 17 | GRPO dans ReinforcerAgent | 3h | Non | 4 | core |
| 18 | Langfuse traces e2e | 1h | Non | 5 | core |
| 19 | Décomposer large pages web | 4h | Non | 3 | web |
| 20 | Phase A SFT completion | 22h | GPU time | 4 | finetune |

---

## Dependency Graph (critical path)

```raw
1.1 (push) → 1.2 (CI)
4.1 (distribute_task) → 4.2 (P2P pipeline)
4.3 (benchmarks) → 4.6 (DPO) → 4.7 (validation) → 4.8 (publish) → 4.9 (auto-register) → 4.15 (continuous)
4.10 (SFT) → 4.11 (rejection) → 4.12 (DPO standalone)
1.3 (split server) → 1.4 (route groups) → 1.5 (verify tests)
3.1 (vitest setup) → 3.2 (critical tests)
5.1 (grafana) → 5.2 (alerting) + 5.3 (consolidated)
7.4 (platformio) → 7.5 (build) → 7.6 (firmware)
```

---

## Notes

- **Conflicting priorities resolved**: TODO_2026-03-10.md (v10) used as authoritative source; EXECUTION_PLAN items reconciled against it
- **External deps flagged**: Tasks requiring crazy_life/Kill_LIFE repos marked as `externe`
- **Completed items excluded**: ~80 completed items from all TODO files omitted (see individual files for history)
- **Effort estimates**: Combined from execution plan ordered priorities + per-task estimates from TODO files
- **Stale items removed**: Execution plan P1 "Installer trl + peft sur KXKM-AI" already done per TODO v10; "Installer huggingface_hub" already done per TODO v10
