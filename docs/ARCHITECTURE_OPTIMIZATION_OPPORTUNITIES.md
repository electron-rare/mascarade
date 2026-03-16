# Architecture Optimization Opportunities — Mascarade

> Synthesized from Phase 1 (State Analysis), Phase 2 (TODO Consolidation), Phase 3 (OSS Research), Phase 4 (Code Audit)
> Date: 2026-03-16

---

## 1. File Decomposition Candidates

### 1.1 core/mascarade/server.py → 15 route modules

| Attribute | Value |
|-----------|-------|
| **Current** | 2,751 lines, 93 route handlers, 37 inline Pydantic models |
| **Proposed** | Split into `routes/{chat,agents,orchestrator,finetune,p2p,health,metrics,knowledge,tools,mcp,config,cache,dispatch,rbac,legacy}.py` + `models/api.py` |
| **Effort** | 4–6 hours |
| **Impact** | **High** — reduces cognitive load, enables parallel development, eliminates duplicate imports |
| **Service** | core |
| **Dependencies** | None — pure refactor, no API changes |
| **Evidence** | 3 duplicate import sets, orphaned decorator at L419, duplicate /metrics route (L1349 vs L2722), hash_api_key defined locally AND imported |

### 1.2 api/src/routes/ops.ts → 6 domain modules

| Attribute | Value |
|-----------|-------|
| **Current** | 1,925 lines, mixed ops/monitoring/health/metrics/logs/providers |
| **Proposed** | Split into `routes/ops/{monitoring,health,metrics,logs,providers,system}.ts` |
| **Effort** | 3–4 hours |
| **Impact** | **High** — largest TypeScript file, blocks parallel API work |
| **Service** | api |
| **Dependencies** | None |

### 1.3 api/src/client/core.ts → typed client modules

| Attribute | Value |
|-----------|-------|
| **Current** | 1,082 lines, monolithic core proxy with malformed methods |
| **Proposed** | Split by domain: `client/{chat,agents,orchestrator,ops,finetune}.ts` + shared `client/base.ts` |
| **Effort** | 3–4 hours |
| **Impact** | **Medium** — reduces coupling, fixes malformed method signatures |
| **Service** | api |
| **Dependencies** | Should follow ops.ts split |

### 1.4 Web pages >1000 lines → component extraction (5 pages)

| Page | Lines | Proposed Extractions | Effort |
|------|-------|---------------------|--------|
| Logs.tsx | 1,468 | 6 components → main ~200 lines | 3h |
| Settings.tsx | 1,129 | 5 components/hooks, DRY ProviderCard/RuntimeSecretCard | 3h |
| OpsHub.tsx | 1,092 | 6 components → main ~200 lines | 3h |
| Orchestrate.tsx | 1,028 | 6 components, 15 useState → useReducer | 3h |
| KillLifeWorkflowEditor.tsx | 1,019 | 8 components, fix JSON cloning anti-pattern | 3h |

| Attribute | Value |
|-----------|-------|
| **Total effort** | 15 hours |
| **Impact** | **High** — 31 reusable components extracted, eliminates ~200 lines duplication |
| **Service** | web |
| **Dependencies** | Extract shared `lib/formatting.ts` first (formatLatency, mcpTone, sourceTone — 3 copies each) |

### 1.5 finetune/ large scripts → module packages (4 scripts)

| Script | Lines | Proposed Modules | Effort |
|--------|-------|-----------------|--------|
| model_selector.py | 1,746 | 5 modules (search, rank, download, watch, registry) | 4h |
| batch_local.py | 1,628 | 5 modules (jobs, distill, train, promote, manifest) | 4h |
| distill_dataset.py | 1,324 | 4 modules (teacher, student, pipeline, quality) | 3h |
| dataset_refresh.py | 1,207 | 4 modules (refresh, probes, briefs, sources) | 3h |

| Attribute | Value |
|-----------|-------|
| **Total effort** | 14 hours |
| **Impact** | **Medium** — improves maintainability, enables unit testing |
| **Service** | finetune |
| **Dependencies** | Should create shared `finetune/config.py` with single DOMAINS list first (currently duplicated in 6+ files) |

### 1.6 TopBar.tsx (789 lines)

| Attribute | Value |
|-----------|-------|
| **Effort** | 2 hours |
| **Impact** | **Low** — single component, but large for a nav bar |
| **Service** | web |
| **Dependencies** | None |

---

## 2. Module Extraction & DRY Violations

### 2.1 Shared DOMAINS constant (finetune/)

| Attribute | Value |
|-----------|-------|
| **Current** | DOMAINS list (11 items) duplicated in 6+ files: pipeline.py, batch_local.py, train_local.py, pipeline_automated.py, distill_and_train.py, dataset_refresh.py |
| **Proposed** | Single `finetune/domains.py` exporting DOMAINS, DOMAIN_CONFIGS |
| **Effort** | 1 hour |
| **Impact** | **Medium** — eliminates sync bugs, single source of truth |
| **Service** | finetune |
| **Dependencies** | None |

### 2.2 Web utility deduplication

| Attribute | Value |
|-----------|-------|
| **Current** | formatLatency (3 copies), formatMcpName/mcpTone/sourceTone (2 copies each), summarizeMcpServer (2 variants) |
| **Proposed** | Extract to `web/src/lib/formatting.ts` (~80 lines) |
| **Effort** | 1 hour |
| **Impact** | **Medium** — eliminates ~200 lines duplication |
| **Service** | web |
| **Dependencies** | Do before page decomposition (§1.4) |

### 2.3 Dual CircuitBreaker implementations (core/)

| Attribute | Value |
|-----------|-------|
| **Current** | `router/circuit_breaker.py` AND `resilience/circuit_breaker.py` — two separate implementations |
| **Proposed** | Consolidate into single `resilience/circuit_breaker.py`, update all imports |
| **Effort** | 2 hours |
| **Impact** | **Medium** — eliminates confusion, prepares for aiobreaker replacement |
| **Service** | core |
| **Dependencies** | Should coincide with aiobreaker replacement (§3.1) |

---

## 3. Dependency Modernization

### 3.1 Replace aiobreaker (abandoned since May 2021)

| Attribute | Value |
|-----------|-------|
| **Current** | aiobreaker 1.2.0 — last release May 2021, unmaintained |
| **Proposed** | Custom async circuit breaker (~150 lines) or adopt `purgatory` |
| **Effort** | 2–4 hours |
| **Impact** | **High** — eliminates unmaintained dependency, security/compatibility risk |
| **Service** | core |
| **Dependencies** | Consolidate dual implementations first (§2.3) |
| **OSS Research** | P0 priority per OSS_RESEARCH.md |

### 3.2 Consider LLaMA-Factory for finetune orchestration

| Attribute | Value |
|-----------|-------|
| **Current** | Custom 40+ scripts with duplicated pipeline logic |
| **Proposed** | Adopt LLaMA-Factory as orchestration layer, keep domain-specific builders |
| **Effort** | 1–2 weeks |
| **Impact** | **High** — standardizes training configs, reduces script count, adds eval integration |
| **Service** | finetune |
| **Dependencies** | DOMAINS extraction (§2.1) should come first |
| **OSS Research** | P1 priority per OSS_RESEARCH.md |

### 3.3 Redis → Valkey swap

| Attribute | Value |
|-----------|-------|
| **Current** | Redis in Docker Compose |
| **Proposed** | Drop-in replacement with Valkey (OSS fork, fully compatible) |
| **Effort** | 1 hour |
| **Impact** | **Low** — licensing improvement, no functional change |
| **Service** | infrastructure |
| **Dependencies** | None |

---

## 4. Pattern Improvements

### 4.1 API auth bypass bug (CRITICAL)

| Attribute | Value |
|-----------|-------|
| **Current** | auth.ts double `isValid` check bypasses DB auth; empty MASCARADE_API_KEY accepts all requests |
| **Proposed** | Fix auth middleware, enforce non-empty API key |
| **Effort** | 15 minutes |
| **Impact** | **Critical** — security vulnerability |
| **Service** | api |
| **Dependencies** | None — do immediately |

### 4.2 Missing v1 route imports (BUG)

| Attribute | Value |
|-----------|-------|
| **Current** | api/src/index.ts missing imports for p2p and finetune routes — runtime error on those endpoints |
| **Proposed** | Add missing route imports |
| **Effort** | 15 minutes |
| **Impact** | **High** — broken endpoints |
| **Service** | api |
| **Dependencies** | None |

### 4.3 Dynamic __import__() security (core/)

| Attribute | Value |
|-----------|-------|
| **Current** | router.py and provider_admin.py use unsafe `__import__()` for dynamic module loading |
| **Proposed** | Add allowlist validation before dynamic imports |
| **Effort** | 1 hour |
| **Impact** | **Medium** — security hardening |
| **Service** | core |
| **Dependencies** | None |

### 4.4 Web state management (useState → useReducer)

| Attribute | Value |
|-----------|-------|
| **Current** | 49+ useState hooks across 5 large pages, 0 useReducer |
| **Proposed** | Convert pages with >10 states (Orchestrate: 15, KillLife: 10) to useReducer |
| **Effort** | 4 hours |
| **Impact** | **Medium** — reduces re-renders, improves state predictability |
| **Service** | web |
| **Dependencies** | Do during page decomposition (§1.4) |

### 4.5 Web code splitting (React.lazy)

| Attribute | Value |
|-----------|-------|
| **Current** | All 18 pages eagerly imported in App.tsx — no lazy loading |
| **Proposed** | Wrap page imports with React.lazy + Suspense |
| **Effort** | 1 hour |
| **Impact** | **Medium** — reduces initial bundle size |
| **Service** | web |
| **Dependencies** | None |

---

## 5. Docker Compose Modularization

### 5.1 Split monolithic docker-compose.yml

| Attribute | Value |
|-----------|-------|
| **Current** | 955-line docker-compose.yml with 5 profiles and 33 services |
| **Proposed** | Keep profiles but extract service groups into override files: `docker-compose.observability.yml`, `docker-compose.personal.yml` |
| **Effort** | 3 hours |
| **Impact** | **Low** — profiles already handle separation; this is organizational |
| **Service** | infrastructure |
| **Dependencies** | None |

### 5.2 Edge proxy nginx config split

| Attribute | Value |
|-----------|-------|
| **Current** | 1,102-line nginx config template with 20+ server blocks |
| **Proposed** | Split into per-service includes under `deploy/edge-proxy/conf.d/` |
| **Effort** | 2 hours |
| **Impact** | **Low** — maintainability improvement |
| **Service** | infrastructure |
| **Dependencies** | None |

---

## 6. Test Infrastructure Gaps

### 6.1 Web frontend — zero tests (CRITICAL)

| Attribute | Value |
|-----------|-------|
| **Current** | 0 test files across 20 pages, 21 components, 8 API modules, 2 hooks |
| **Proposed** | Set up Vitest + React Testing Library, write tests for critical paths: AuthGate, useFetch, API client, Dashboard |
| **Effort** | 2 hours (setup) + 8 hours (critical path tests) |
| **Impact** | **High** — no regression safety net for 20K+ lines of UI code |
| **Service** | web |
| **Dependencies** | None |

### 6.2 Finetune — zero tests (CRITICAL)

| Attribute | Value |
|-----------|-------|
| **Current** | 0 test files, no conftest.py, no pytest.ini across 36 Python scripts |
| **Proposed** | Add pytest infrastructure, write tests for: sharegpt_utils, validators, domain config, VRAM heuristics |
| **Effort** | 2 hours (setup) + 6 hours (core tests) |
| **Impact** | **High** — 26K+ lines with no test safety net, broad exception catches hiding bugs |
| **Service** | finetune |
| **Dependencies** | DOMAINS extraction (§2.1) enables domain config tests |

### 6.3 API — weak coverage

| Attribute | Value |
|-----------|-------|
| **Current** | 12 test files for 31 route files — ~39% file coverage |
| **Proposed** | Add tests for: auth middleware, ops routes, killlife routes, error handling |
| **Effort** | 4 hours |
| **Impact** | **Medium** — auth bugs (§4.1) would have been caught with middleware tests |
| **Service** | api |
| **Dependencies** | Fix auth bug (§4.1) first |

---

## Summary: Effort vs Impact Matrix

| ID | Opportunity | Effort | Impact | Service | Priority |
|----|------------|--------|--------|---------|----------|
| 4.1 | Fix API auth bypass | 15 min | Critical | api | **P0** |
| 4.2 | Fix missing route imports | 15 min | High | api | **P0** |
| 3.1 | Replace aiobreaker | 2–4h | High | core | **P0** |
| 6.1 | Web test infrastructure | 2h setup | High | web | **P0** |
| 6.2 | Finetune test infrastructure | 2h setup | High | finetune | **P0** |
| 1.1 | Split server.py | 4–6h | High | core | **P1** |
| 1.2 | Split ops.ts | 3–4h | High | api | **P1** |
| 2.2 | Web utility dedup | 1h | Medium | web | **P1** |
| 2.1 | DOMAINS constant extraction | 1h | Medium | finetune | **P1** |
| 4.3 | __import__() allowlist | 1h | Medium | core | **P1** |
| 4.5 | React.lazy code splitting | 1h | Medium | web | **P1** |
| 1.4 | Web page decomposition (5 pages) | 15h | High | web | **P2** |
| 1.3 | Split core.ts client | 3–4h | Medium | api | **P2** |
| 2.3 | Consolidate circuit breakers | 2h | Medium | core | **P2** |
| 4.4 | useState → useReducer | 4h | Medium | web | **P2** |
| 6.3 | API test coverage | 4h | Medium | api | **P2** |
| 1.5 | Finetune script decomposition | 14h | Medium | finetune | **P2** |
| 3.2 | LLaMA-Factory adoption | 1–2w | High | finetune | **P3** |
| 5.1 | Docker Compose split | 3h | Low | infra | **P3** |
| 5.2 | Nginx config split | 2h | Low | infra | **P3** |
| 3.3 | Redis → Valkey | 1h | Low | infra | **P3** |
| 1.6 | TopBar.tsx decomposition | 2h | Low | web | **P3** |

### Dependency Graph (critical path)

```
§4.1 (auth fix, 15min) ─→ §6.3 (API tests, 4h)
§2.1 (DOMAINS, 1h) ─→ §1.5 (finetune decomp, 14h) ─→ §3.2 (LLaMA-Factory, 1-2w)
§2.2 (web utils, 1h) ─→ §1.4 (page decomp, 15h)
§2.3 (circuit breaker consolidation, 2h) ─→ §3.1 (aiobreaker replace, 2-4h)
§1.1 (server.py, 4-6h) — independent
§1.2 (ops.ts, 3-4h) ─→ §1.3 (core.ts, 3-4h)
```

### Total Estimated Effort

| Tier | Items | Hours |
|------|-------|-------|
| Quick wins (P0) | 5 | ~7h |
| Medium effort (P1) | 5 | ~10h |
| Significant (P2) | 6 | ~42h |
| Major investment (P3) | 4 | ~90h+ |
| **Total** | **22 opportunities** | **~150h** |
