# API TypeScript Deep Code Audit

**Date:** 2026-03-16
**Scope:** ops.ts, core.ts, killlife.ts, route handlers, middleware, auth, error handling

---

## 1. ops.ts Decomposition Analysis (1925 lines)

### Current Structure
The file contains 5 distinct domains mixed together:

| Domain | Lines (approx) | Description |
|--------|---------|-------------|
| **Types** | 1–199 | 14 type definitions (ProbeResult, MonitorSnapshot, McpSuiteStatus, etc.) |
| **Utility functions** | 200–470 | timedJson, timedProbe, proxyAuthHeaders, env constants |
| **Loki/Log processing** | 471–1138 | decodeLokiLine, lokiValueToOpsLogEntry, queryLoki, severity helpers |
| **MCP probe system** | 740–1030 | runMcpProbe, aggregateMcpStatus, probeMcpRuntime, cache logic |
| **Monitor snapshot** | 1140–1545 | collectMonitorSnapshot — the massive 400-line function probing 30+ services |
| **Route handlers** | 1553–1925 | 9 endpoints: /monitor, /sources, /summary, /mcp/probe/:serverKey, /agent-traces/*, /logs/* |

### Recommended Split Points

1. **`ops/types.ts`** — Extract all 14 type definitions (lines 1–199)
2. **`ops/probes.ts`** — timedJson, timedProbe, proxyAuthHeaders, env constants (lines 200–470)
3. **`ops/loki.ts`** — All Loki/log processing: decodeLokiLine, lokiValueToOpsLogEntry, queryLoki, severity/log helpers (lines 471–1138). Already has exported functions.
4. **`ops/mcp-probe.ts`** — MCP probe system: runMcpProbe, aggregateMcpStatus, probeMcpRuntime, cache (lines 740–1030)
5. **`ops/monitor.ts`** — collectMonitorSnapshot + surface assembly (lines 1140–1545)
6. **`ops/index.ts`** (or `ops.ts`) — Just the Hono route handlers importing from the above modules

### Key Concerns
- **collectMonitorSnapshot** fires 30+ concurrent HTTP probes — a single timeout chain failure can stall the entire endpoint
- **MCP probe cache** is module-level mutable state (`cachedMcpProbe`, `inflightMcpProbe`) — fragile singleton pattern
- **~40 env variables** read at module top-level — should be consolidated into a config object
- **Duplicated `isRecord` helper** — exists in both ops.ts and killlife.ts

---

## 2. core.ts Coupling Assessment (1082 lines)

### Structure
- Lines 1–155: Type/interface definitions (11 interfaces)
- Lines 156–189: Generic `request<T>` function + error handling
- Lines 191–1082: `coreClient` object literal with ~50 methods

### Coupling Degree: **HIGH but acceptable**
- `coreClient` is a pure HTTP client — every method calls the internal `request<T>` helper
- Used by: `ops.ts`, `killlife.ts`, `agents.ts`, `settings.ts`, `chat.ts`, `pipeline.ts`, `comfyui.ts`, `industrial.ts`, `mcpIndustrial.ts`, `qdrantKnowledge.ts`
- It's the **single gateway** to the Python core — appropriate coupling

### Issues Found
- **Lines 848–851: Malformed code** — `updateUser` method body is truncated, immediately followed by Qdrant section comment. The closing `});` for the method body is missing, with the Qdrant methods spliced in before `deleteUser` and API key methods appear later (lines 929+). The `revokeApiKey` at line 948 is similarly cut short. **This appears to be a merge conflict artifact or bad splice.**
- **Duplicated error handling** in `verifyToken` (lines 788–829) — manually reimplements the same error extraction as `request<T>`. Should reuse the shared function.
- **No retry logic** — single-shot requests with AbortSignal.timeout. Not a bug but worth noting.
- **Missing response type validation** — `request<T>` casts `res.json()` to `T` without runtime validation

### Recommended Splits
1. **`client/core-types.ts`** — All interface/type exports
2. **`client/core.ts`** — Keep the client, import types

---

## 3. killlife.ts Analysis (924 lines)

### Structure
- Well-organized: types → helpers → validation → CRUD → execution → evidence
- Good separation of concerns within the file
- Thorough input validation (regex-based IDs, allowlisted actions/workflows)

### Assessment: **Good quality, no urgent split needed**
- The file is cohesive — all functions serve the KillLife workflow domain
- Security: command execution is properly sandboxed via allowlists (`ALLOWED_LOCAL_ACTIONS`, `ALLOWED_GITHUB_WORKFLOWS`)
- `validateWorkflowDocument` (lines 283–514) is thorough with DAG cycle detection

### Minor Issues
- `executeCommand` doesn't cap stdout/stderr buffer size — a runaway process could OOM
- No timeout on the overall `runWorkflow` orchestration — individual steps time out but the aggregate doesn't

---

## 4. Route Handler Consistency Audit

### Error Handling Patterns

| Route | Pattern | Consistent? |
|-------|---------|------------|
| ops.ts | `try/catch → handleCoreError(error)` | ✅ Yes (all 9 handlers) |
| agents.ts | `try/catch → handleCoreError(error)` | ✅ Yes |
| settings.ts | Mixed — some use handleCoreError, some inline | ⚠️ Partially |
| killlife.ts (route) | `try/catch → c.json({ error }, status)` | ⚠️ Inconsistent with ops |
| pipeline.ts | `try/catch → handleCoreError(error)` | ✅ Yes |
| chat.ts | `try/catch → handleCoreError(error)` | ✅ Yes |
| p2p.ts | `try/catch → c.json({ error }, 500)` | ⚠️ Different pattern |
| finetune.ts | `try/catch → handleCoreError(error)` | ✅ Yes |
| comfyui.ts | `try/catch → handleCoreError(error)` | ✅ Yes |

### Finding: 3 routes (killlife, p2p, settings partially) use ad-hoc error handling instead of `handleCoreError`.

---

## 5. Auth Middleware & Coverage Analysis

### Critical Bug: Double `isValid` Declaration (auth.ts lines 179 & 204)

```typescript
let isValid = false;                    // line 179
if (useDatabaseAuth) { ... }            // lines 181-202
const isValid = isValidConfiguredApiKey(token);  // line 204 — REDECLARES!
```

Line 204 **shadows** the database auth result with a legacy env-key check. If `useDatabaseAuth` is true and the token is a valid DB token but NOT in MASCARADE_API_KEY, auth will **incorrectly reject**. This is a **critical auth bug** — database auth is effectively bypassed by the legacy check.

### Auth Coverage Gaps

| Route Path | Auth? | Rate Limited? | Notes |
|-----------|-------|--------------|-------|
| `/health` | ❌ No | ❌ No | Correct — health check |
| `/v1/version` | ❌ No | ❌ No | Intentional — public version info |
| `/v1/api/*` | ✅ Yes | ✅ Yes | Correct |
| `/api/auth/*` | ❌ No | ✅ Yes | Correct — login endpoints |
| `/api/*` | ✅ Yes | ✅ Yes | Correct |
| `/api/p2p` | ✅ Yes (via /api/* wildcard) | ✅ Yes | OK |
| `/api/finetune` | ✅ Yes (via /api/* wildcard) | ✅ Yes | OK |

**Missing from v1 namespace:**
- `/v1/api/chat` — NOT registered (only `/api/v1/chat` exists, which is an odd path)
- `/v1/api/pipeline` — NOT registered
- `/v1/api/analytics` — NOT registered
- `/v1/api/users` — NOT registered
- `/v1/api/p2p` — NOT registered
- `/v1/api/finetune` — NOT registered

**Missing imports in index.ts:**
- `p2p` and `finetune` are used on lines 76–77 but **never imported**. This will cause a **runtime crash** (ReferenceError).

### RBAC Role Assignments

The `requiredRoleForRequest` function in auth.ts assigns:
- **admin**: `/api/settings/runtime-secrets*`, `/api/settings/providers*`, `/api/settings/oauth*`, `/api/mcp/industrial*`, `/api/ops*`, `/api/cluster/forward*`
- **operator** (write) / **viewer** (read): `/api/cluster*`, `/api/p2p*`, `/api/killlife*`
- **operator** (write) / **viewer** (read): everything else

⚠️ `/api/users*` only requires **operator** for writes — should arguably require **admin** for user management.

---

## 6. Dead Routes / Unused Code

1. **`/api/v1/chat`** — unusual path nesting (`/api/v1/` inside `/api/`); likely should be `/v1/api/chat`
2. **Missing p2p/finetune imports** — these routes reference variables that don't exist in scope

---

## 7. Summary of Findings

### Critical (fix immediately)
1. **auth.ts double `isValid` declaration** — database auth bypassed by legacy check (line 204)
2. **index.ts missing imports** for `p2p` and `finetune` — runtime crash

### High Priority
3. **core.ts malformed updateUser/revokeApiKey methods** — missing closing braces, methods interleaved incorrectly
4. **ops.ts size** — 1925 lines with 5+ concerns; recommend splitting into 5–6 modules

### Medium Priority
5. **Inconsistent error handling** in killlife routes, p2p, parts of settings
6. **6 routes missing from v1 namespace** — chat, pipeline, analytics, users, p2p, finetune
7. **`/api/v1/chat` path** is oddly nested — should be `/v1/api/chat`
8. **`/api/users` RBAC** — user management only requires operator, should require admin

### Low Priority
9. **Duplicated `isRecord` helper** in ops.ts and killlife.ts
10. **40+ env vars** in ops.ts should be a config object
11. **No stdout buffer cap** in killlife.ts `executeCommand`
12. **core.ts `verifyToken`** duplicates error handling logic from `request<T>`
