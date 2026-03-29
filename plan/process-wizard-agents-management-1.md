---
goal: Wizard Agents Management Implementation Plan
version: 1.0
date_created: 2026-03-29
last_updated: 2026-03-29
owner: platform-ai
status: 'Planned'
tags: [process, feature, architecture, agents, orchestration]
---

# Introduction

![Status: Planned](https://img.shields.io/badge/status-Planned-blue)

Plan d'implementation pour industrialiser la gestion des agents du wizard (selection, orchestration, gouvernance, observabilite, tests) sur les stacks `core/` et `api/` avec compatibilite `web/`.

## 1. Requirements & Constraints

- **REQ-001**: Exposer une gestion unifiee des agents wizard (catalog, selection, execution, statut).
- **REQ-002**: Preserver la separation `api -> core` (pas d'appel direct `web -> core`).
- **REQ-003**: Maintenir les contrats API existants sans breaking change.
- **SEC-001**: Routes sensibles sous auth stricte, comportement fail-closed si token absent/invalide.
- **SEC-002**: Aucune fuite de secret dans logs/reponses de debug.
- **CON-001**: `core/` reste async-first pour tout I/O reseau/disque.
- **CON-002**: Pydantic v2 uniquement cote Python.
- **CON-003**: TypeScript strict cote `api/`.
- **GUD-001**: Patches minimaux par stack, validations ciblees.
- **PAT-001**: Providers geres via router + circuit breaker, jamais instancies directement en route.

## 2. Implementation Steps

### Implementation Phase 1

- **GOAL-001**: Formaliser le contrat Wizard Agents Management (domain model + API contract) sans implementation disruptive.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-001 | Creer `docs/agents/WIZARD_AGENTS_MANAGEMENT_SPEC.md` avec flux metier (catalog -> select -> run -> status) et statuts de cycle de vie. |  |  |
| TASK-002 | Definir les schemas Pydantic v2 `WizardAgentRunRequest`, `WizardAgentRunResult`, `WizardAgentStatus` dans `core/mascarade/agents/schemas.py`. |  |  |
| TASK-003 | Definir les schemas Zod homologues dans `api/src/validation/schemas.ts` pour stabiliser le contrat gateway. |  |  |
| TASK-004 | Ajouter matrice de capacites agents (domain, required_context, cost_class) dans `core/mascarade/agents/registry.py` (ou module dedie). |  |  |

### Implementation Phase 2

- **GOAL-002**: Implementer le service de gestion wizard cote core (selection + execution + suivi).

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-005 | Creer `core/mascarade/agents/wizard_management.py` avec classe `WizardAgentsManagementService`. |  |  |
| TASK-006 | Implementer `select_agents(task, domain, constraints)` avec regles deterministes et score de selection. |  |  |
| TASK-007 | Implementer `run_wizard_plan(mode=sequential|parallel)` en s'appuyant sur `orchestrator/engine.py`. |  |  |
| TASK-008 | Implementer `get_run_status(task_id)` + persistance courte duree (in-memory + option Redis). |  |  |
| TASK-009 | Integrer les garde-fous de resilience (retry/fallback/timeout) via patterns existants `router/fallback.py`. |  |  |

### Implementation Phase 3

- **GOAL-003**: Exposer les routes API de management sans casser les routes existantes.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-010 | Creer `core/mascarade/routers/wizard_management.py` avec routes: `GET /api/wizard/agents`, `POST /api/wizard/run`, `GET /api/wizard/status/{task_id}`. |  |  |
| TASK-011 | Brancher ces routes dans `core/mascarade/server.py` avec middlewares existants. |  |  |
| TASK-012 | Ajouter proxy Hono dans `api/src/routes/` pour relayer vers core (memes statuts HTTP). |  |  |
| TASK-013 | Verifier ordre middleware `auth -> rate-limit -> CORS` sur les nouvelles routes `api/`. |  |  |

### Implementation Phase 4

- **GOAL-004**: Ajouter observabilite, diagnostics et securite operationnelle.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-014 | Emettre metriques `wizard_runs_total`, `wizard_run_latency_ms`, `wizard_selection_fallback_total` dans `core/mascarade/metrics/`. |  |  |
| TASK-015 | Ajouter logs structures correles par `task_id` (sans donnees sensibles). |  |  |
| TASK-016 | Ajouter endpoint health cible wizard (`/health/wizard`) ou enrichir health existant. |  |  |
| TASK-017 | Ajouter garde auth/rbac explicite pour run/status cote API gateway. |  |  |

### Implementation Phase 5

- **GOAL-005**: Durcir les tests et la validation CI par impact.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-018 | Ajouter tests unitaires core `core/tests/test_wizard_agents_management.py` (selection, orchestration, erreurs). |  |  |
| TASK-019 | Ajouter tests routes core `core/tests/test_wizard_management_router.py`. |  |  |
| TASK-020 | Ajouter tests API gateway `api/src/routes/*wizard*.test.ts` (proxy + auth + erreurs). |  |  |
| TASK-021 | Ajouter tests E2E Playwright `e2e/tests/api/wizard-management.spec.ts` avec mock API adapte. |  |  |
| TASK-022 | Mettre a jour CI pour executer checks cibles selon changements wizard (core/api/e2e). |  |  |

## 3. Alternatives

- **ALT-001**: Implementer la logique wizard uniquement dans `api/` (rejete: violerait la frontiere d'architecture, logique metier doit rester dans `core/`).
- **ALT-002**: Executer en direct via providers sans agent registry (rejete: perte des capacites agentiques et de la gouvernance).
- **ALT-003**: Orchestration uniquement sequentielle (rejete: insuffisant pour taches parallelisables et latence globale).

## 4. Dependencies

- **DEP-001**: `core/mascarade/orchestrator/engine.py` pour execution de plans.
- **DEP-002**: `core/mascarade/agents/registry.py` pour inventaire/capacites agents.
- **DEP-003**: `core/mascarade/router/fallback.py` et resilience associee.
- **DEP-004**: `api/src/validation/schemas.ts` pour contrat gateway.
- **DEP-005**: `e2e/playwright.config.ts` + `e2e/mock-api/server.mjs` pour validation E2E.

## 5. Files

- **FILE-001**: `docs/agents/WIZARD_AGENTS_MANAGEMENT_SPEC.md` (nouveau)
- **FILE-002**: `core/mascarade/agents/wizard_management.py` (nouveau)
- **FILE-003**: `core/mascarade/agents/schemas.py` (update)
- **FILE-004**: `core/mascarade/routers/wizard_management.py` (nouveau)
- **FILE-005**: `core/mascarade/server.py` (update)
- **FILE-006**: `api/src/routes/wizard-management.ts` (nouveau)
- **FILE-007**: `api/src/validation/schemas.ts` (update)
- **FILE-008**: `core/tests/test_wizard_agents_management.py` (nouveau)
- **FILE-009**: `core/tests/test_wizard_management_router.py` (nouveau)
- **FILE-010**: `api/src/routes/wizard-management.test.ts` (nouveau)
- **FILE-011**: `e2e/tests/api/wizard-management.spec.ts` (nouveau)
- **FILE-012**: `e2e/mock-api/server.mjs` (update)

## 6. Testing

- **TEST-001**: `cd core && python -m pytest core/tests/test_wizard_agents_management.py -q`
- **TEST-002**: `cd core && python -m pytest core/tests/test_wizard_management_router.py -q`
- **TEST-003**: `cd core && ruff check mascarade/ tests/ && mypy mascarade/`
- **TEST-004**: `cd api && npm test && npm run build`
- **TEST-005**: `npm exec --prefix e2e playwright -- test --config e2e/playwright.config.ts tests/api/wizard-management.spec.ts --project api`
- **TEST-006**: test de non-regression auth/rate-limit sur nouvelles routes API

## 7. Risks & Assumptions

- **RISK-001**: Derive de contrat entre schemas core (Pydantic) et API (Zod).
- **RISK-002**: Latence excessive en mode parallele si provider distant instable.
- **RISK-003**: Regression auth si middleware/order modifie par inadvertance.
- **RISK-004**: Flakiness E2E si mock API incomplet sur les nouveaux flux.
- **ASSUMPTION-001**: L'agent registry actuel contient deja les metadonnees minimales pour le scoring.
- **ASSUMPTION-002**: L'orchestrateur existant supporte la granularite requise sans refactor majeur.

## 8. Related Specifications / Further Reading

- [CLAUDE.md](../CLAUDE.md)
- [docs/ARCHITECTURE.md](../docs/ARCHITECTURE.md)
- [docs/API.md](../docs/API.md)
- [.github/copilot-instructions.md](../.github/copilot-instructions.md)
- [plan/process-wizard-agents-coordination-1.md](./process-wizard-agents-coordination-1.md)