# API Service State Analysis

## 1. Route Inventory

**Total: ~95 handlers across 21 route files**

### Route Files Summary

| File | Lines | GET | POST | PUT | DELETE | Total |
|------|-------|-----|------|-----|--------|-------|
| agents.ts | - | 8 | 14 | 2 | 1 | 25 |
| ops.ts | 1925 | 10 | 0 | 0 | 0 | 10 |
| settings.ts | - | 6 | 5 | 1 | 0 | 12 |
| qdrantKnowledge.ts | - | 3 | 6 | 1 | 1 | 11 |
| comfyui.ts | - | 4 | 4 | 0 | 0 | 8 |
| killlife.ts (route) | 120 | 4 | 2 | 1 | 0 | 7 |
| users.ts | - | 2 | 2 | 1 | 1 | 6 |
| cad.ts | - | 2 | 4 | 0 | 0 | 6 |
| industrial.ts | - | 4 | 1 | 0 | 0 | 5 |
| mcpIndustrial.ts | - | ~3 | ~2 | 0 | 0 | ~5 |
| knowledgeBase.ts | - | 2 | 2 | 0 | 0 | 4 |
| cluster.ts | - | 2 | 1 | 0 | 0 | 3 |
| finetune.ts | - | 1 | 1 | 0 | 1 | 3 |
| pipeline.ts | - | 2 | 1 | 0 | 0 | 3 |
| orchestrateTemplates.ts | - | 2 | 1 | 0 | 0 | 3 |
| auth.ts (route) | - | 0 | 1 | 0 | 1 | 2 |
| p2p.ts | - | 2 | 0 | 0 | 0 | 2 |
| chat.ts | - | 0 | 1 | 0 | 0 | 1 |
| health.ts | - | 1 | 0 | 0 | 0 | 1 |
| version.ts | - | 1 | 0 | 0 | 0 | 1 |
| analytics.ts | - | 1 | 0 | 0 | 0 | 1 |

---

## 2. Middleware Audit

**8 files in `api/src/middleware/`:**

| File | Purpose |
|------|---------|
| **auth.ts** (220 lines) | Bearer token auth, dual-mode (DB-backed + legacy env-var), RBAC with viewer/operator/admin roles |
| **cors.ts** (48 lines) | Fail-closed CORS, configurable via `CORS_ORIGINS` env var |
| **rate-limit.ts** (247 lines) | Multi-window rate limiting (per-minute/hour/day), in-memory store, per-user limits |
| **security.ts** (19 lines) | Standard HTTP security headers (nosniff, DENY frames, CSP) |
| **deprecation.ts** | Deprecation tracking middleware |
| **error.ts** | Error handling utilities (handleCoreError) |
| **auth.test.ts** | Auth middleware tests |
| **error.test.ts** | Error middleware tests |

### Middleware Chain (from index.ts)
1. `corsMiddleware` — applied to all routes (`*`)
2. `securityHeaders` — applied to all routes (`*`)
3. `logger()` — Hono built-in logger, all routes
4. `authMiddleware` — applied to `/v1/api/*` and `/api/*` (not /health, /v1/version, /api/auth)
5. `rateLimitMiddleware` — applied after auth on `/v1/api/*` and `/api/*`, also on `/api/auth/*` without auth

---

## 3. Core Client Coupling Analysis (`api/src/client/core.ts` — 1082 lines)

### Summary
- **65+ methods** on `coreClient` object
- **Pure proxy pattern**: Node API is essentially a gateway to Python core
- Every method calls `request<T>(path, options)` which hits `CORE_URL` (default `http://localhost:8100`)

### Method Categories
| Category | Count | Endpoints |
|----------|-------|-----------|
| Health/Status | 1 | /health |
| LLM Operations | 3 | /send, /orchestrate, /agents/{name}/run |
| Agent CRUD | 5 | /agents, /agents/{name} |
| Agent Traces | 2 | /agent-traces/* |
| Metrics | 4 | /metrics, /metrics/{provider}, /agents/{name}/metrics |
| Cache | 2 | /cache/* |
| Load Balancer | 2 | /load-balancer/* |
| Fallback | 2 | /fallback/* |
| Providers | 4 | /providers, /providers/status, /health/providers |
| Knowledge Base | 4 | /knowledge-base/* |
| ComfyUI | 8 | /comfyui/* |
| Cluster | 3 | /cluster/* |
| CAD (FreeCAD/OpenSCAD) | 8 | /mcp/freecad/*, /mcp/openscad/* |
| Industrial MCP | 5 | /mcp/industrial/* |
| Auth | 1 | /auth/me |
| User Management | 5 | /users* |
| API Keys | 3 | /users/{id}/api-keys* |
| Qdrant | 11 | /qdrant/* |
| Fine-tuning | 3 | /finetune/* |
| GitHub Dispatch | 3 | /mcp/github-dispatch/* |
| Templates | 3 | /orchestrate/templates* |

### Coupling Assessment
- **HIGH coupling** — the API is a thin HTTP proxy over core
- Timeout: 30s configurable via `CORE_TIMEOUT_MS`
- Auth: forwards `MASCARADE_API_KEY` as Bearer token to core
- Errors: translates core HTTP errors into `CoreApiError`

---

## 4. ops.ts Complexity Analysis (1925 lines)

### Route Handlers (10)
1. `GET /monitor` — Full system health snapshot
2. `GET /sources` — Observability source listing
3. `GET /summary` — Aggregated operational summary
4. `POST /mcp/probe/:serverKey` — MCP server health probe
5. `GET /agent-traces/recent` — Recent agent traces
6. `GET /agent-traces/stream` — SSE trace stream
7. `GET /agent-traces/:runId` — Traces by run ID
8. `GET /logs/recent` — Recent operational logs
9. `GET /logs/stream` — SSE log stream
10. `GET /logs/query` — Structured log query

### Logical Groups
- Monitoring/Health (3): monitor, sources, summary
- MCP Probing (1): mcp/probe/:serverKey
- Agent Traces (3): agent-traces/*
- Logs (3): logs/*

### Complexity Issues
- **~30+ type definitions** at the top of the file
- **Multiple integration points**: Loki, Tempo, Prometheus, Grafana, Langfuse
- **Health probing logic** for services, surfaces, industrial UI
- **SSE stream handling** for real-time logs and traces
- **MCP server introspection** via child process spawning
- **Docker event integration**
- **Strong decomposition candidate**: Types → separate file, MCP probing → separate module, stream handlers → separate module

---

## 5. killlife.ts Coupling Analysis

### Route file (`api/src/routes/killlife.ts` — 120 lines)
- 7 route handlers, clean delegation pattern
- Imports 7 functions from `../lib/killlife.js`

### Library file (`api/src/lib/killlife.ts` — 924 lines)
- **No direct core client calls** — standalone file-system-based module
- Uses `KILL_LIFE_ROOT` env var for root directory
- Workflow management: CRUD, validation, execution
- Evidence collection and listing
- Supports local and GitHub execution modes
- Self-contained coupling — only depends on Node.js fs/path/child_process

---

## 6. Two-Tier Versioning Analysis

### Mount Structure
```
/health                    → health       (NO auth, NO rate-limit)
/v1/version                → version      (NO auth, NO rate-limit)

/v1/api/* (auth + rate-limit):
  agents, cluster, knowledge-base, qdrant-knowledge, cad,
  comfyui, ops, industrial, mcp/industrial, killlife, settings

/api/auth/*                → auth         (rate-limit ONLY, no auth)

/api/* (auth + rate-limit):
  agents, cluster, knowledge-base, qdrant-knowledge, cad,
  comfyui, ops, industrial, mcp/industrial, killlife, settings,
  v1/chat, pipeline, analytics, users, p2p, finetune
```

### Inconsistencies
1. **Missing imports**: `p2p` and `finetune` are routed in index.ts but NOT imported — **runtime error**
2. **11 routes duplicated** across both `/v1/api/` and `/api/` tiers
3. **6 routes only on `/api/`** tier: chat, pipeline, analytics, users, p2p, finetune — no v1 equivalent
4. **Chat path anomaly**: mounted at `/api/v1/chat` (v1 inside /api/) instead of `/v1/api/chat` or `/api/chat`
5. **No migration strategy** between tiers — both serve identical handlers

---

## 7. Auth Coverage Summary

### Unprotected Routes
| Path | Rate Limited? |
|------|--------------|
| `/health` | No |
| `/v1/version` | No |
| `/api/auth/*` | Yes |

### Protected Routes (auth + rate-limit)
All routes under `/v1/api/*` and `/api/*` require authentication.

### RBAC Restrictions (when enabled)
| Access Level | Paths |
|-------------|-------|
| **Admin only** | settings/runtime-secrets, settings/providers, settings/oauth, mcp/industrial, ops, cluster/forward |
| **Operator+** | cluster (POST/PUT/DELETE), p2p (mutating), killlife (mutating) |
| **Viewer+** | All GET requests |

---

## Key Findings & Risks

1. **ops.ts (1925 lines)** — strongest decomposition candidate; types, MCP probing, SSE streams, and monitoring could each be separate modules
2. **core.ts (1082 lines)** — 65+ methods in a single object; could be split by domain (agents, qdrant, comfyui, etc.)
3. **Missing imports** for p2p and finetune in index.ts — will cause runtime crash
4. **Dual-tier routing** creates maintenance burden with no clear deprecation path
5. **killlife library (924 lines)** — self-contained, moderate complexity, reasonable coupling
