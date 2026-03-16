# Core Python Deep Code Audit

## 1. server.py Decomposition Analysis (2,751 lines)

### Logical Boundaries Identified — Propose Split into 15 Modules

| # | Module | Routes | Lines (est.) | Description |
|---|--------|--------|-------------|-------------|
| 1 | `routers/health.py` | 3 | ~50 | `/health`, `/v1/version`, `/health/providers` |
| 2 | `routers/llm.py` | 2 | ~200 | `/v1/send`, `/v1/chat/completions` |
| 3 | `routers/auth.py` | 4 | ~60 | API key CRUD, `/v1/auth/me` |
| 4 | `routers/users.py` | 9 | ~350 | User CRUD, rate limits, user API keys |
| 5 | `routers/providers.py` | 5 | ~80 | Provider listing, status, Bedrock models |
| 6 | `routers/agents.py` | 7 | ~200 | Agent CRUD, run, metrics |
| 7 | `routers/orchestration.py` | 4 | ~150 | Orchestrate, templates |
| 8 | `routers/cluster.py` | 5 | ~100 | P2P cluster operations |
| 9 | `routers/analytics.py` | 4 | ~150 | Cost analytics, usage stats, router metrics |
| 10 | `routers/traces.py` | 3 | ~100 | Agent traces, SSE stream |
| 11 | `routers/knowledge_base.py` | 5 | ~150 | KB search, pages, scribe |
| 12 | `routers/mcp.py` | 16 | ~400 | GitHub dispatch, FreeCAD, OpenSCAD, Industrial MCP |
| 13 | `routers/comfyui.py` | 8 | ~150 | ComfyUI image generation |
| 14 | `routers/benchmarks.py` | 3 | ~200 | Benchmark runs, webhooks |
| 15 | `models.py` | — | ~250 | All 37 Pydantic request/response models |

**Residual `server.py`**: ~200 lines (FastAPI app, lifespan, app.state setup)

**Total: 93 route handlers → 15 router modules + models.py**

### Critical Issues in server.py

| Severity | Issue | Location |
|----------|-------|----------|
| 🔴 HIGH | Duplicate import: `asynccontextmanager` imported twice | Lines 10 & 13 |
| 🔴 HIGH | Duplicate import: `StreamingResponse` imported twice | Lines 18 & 20 |
| 🔴 HIGH | Duplicate import: `BaseModel, Field` imported twice | Lines 19 & 21 |
| 🔴 HIGH | Orphaned `@app.post("/v1/chat/completions")` decorator with no function body | Line 419 |
| 🔴 HIGH | Duplicate `/metrics` route (collision, second overwrites first) | Lines 1349 & 2722 |
| 🔴 HIGH | Incomplete `metrics()` function (missing return) | Line 2722 |
| 🟡 MED | `ConfigDict` imported but never used | Line 19 |
| 🟡 MED | `hash_api_key` defined locally AND imported from `mascarade.auth` | Line 30 vs import |
| 🟡 MED | `ChatCompletionRequest`, `ChatCompletionChunk*` classes used but not defined/imported in file | Lines 449-627 |

---

## 2. router.py Complexity Assessment (1,021 lines)

### Missing Imports (Runtime Errors)

| Severity | Symbol | Used At | Defined In | Status |
|----------|--------|---------|------------|--------|
| 🔴 CRITICAL | `CircuitBreaker` | Line 102 | `mascarade.router.circuit_breaker` | **NOT IMPORTED** |
| 🔴 CRITICAL | `get_cost_logger()` | Line 107 | `mascarade.analytics.clickhouse_logger` | **NOT IMPORTED** |
| 🔴 CRITICAL | `get_cost_calculator()` | Line 108 | `mascarade.analytics.cost_calculator` | **NOT IMPORTED** |

> **Note**: These may be resolved at runtime via star imports or module-level injection not visible in the file header. If not, Router.__init__() will raise NameError.

### Complexity Hotspots

| Method | Lines | Concern |
|--------|-------|---------|
| `send()` | ~285 lines | Deeply nested: cache check → strategy → fallback → metrics → langfuse. Extract into 4-5 smaller methods |
| `_select_candidates()` | ~97 lines | Multiple filter passes, acceptable but could clarify |
| `_resolve_routellm_target()` | ~72 lines | Inner functions + ternary logic |

---

## 3. Provider Audit (10 files)

### Interface Compliance Matrix

| Provider | send | stream | available_models | is_configured | make_retry | cost_per_million | speed_rank | quality_rank |
|----------|------|--------|-------------------|---------------|------------|-----------------|------------|-------------|
| claude | ✅ | ✅ | ✅ | ✅ | ✅ | (3.0, 15.0) | 2 | 3 |
| openai | ✅ | ✅ | ✅ | ✅ | ✅ | (2.5, 10.0) | 1 | 2 |
| mistral | ✅ | ✅ | ✅ | ✅ | ✅ | (2.0, 6.0) | 1 | 1 |
| bedrock | ✅ | ✅ | ✅ | ✅ | ✅ | (3.0, 15.0) | 2 | 3 |
| google | ✅ | ✅ | ✅ | ✅ | ✅ | (1.25, 5.0) | 1 | 2 |
| huggingface | ✅ | ✅ | ✅ | ✅ | ✅ | (0.0, 0.0) | 2 | 2 |
| ollama | ✅ | ✅ | ✅ | ✅ | ✅ | (0.0, 0.0) | 1 | 1 |
| llama_cpp | ✅ | ✅ | ✅ | ✅ | ✅ | (0.0, 0.0) | 1 | 1 |
| apple_coreml | ✅ | ✅* | ✅ | ✅ | ✅ | (0.0, 0.0) | 1 | 2 |
| kicad_router | ✅ | ✅ | ✅ | ✅ | ❌ | (0.0, 0.0) | 5 | 7 |

*apple_coreml.stream() delegates to send() (non-streaming fallback)*

### Provider Issues

| Severity | Provider | Issue |
|----------|----------|-------|
| 🟡 MED | kicad_router | No `make_retry` decorator — inconsistent with all other providers |
| 🟡 MED | mistral | `send()` accepts `response_format` but `stream()` does not — signature inconsistency |
| 🟢 LOW | bedrock | Uses `asyncio.to_thread()` for sync boto3 — acceptable but non-ideal |
| 🟢 LOW | apple_coreml | stream() is non-streaming fallback — acceptable for local model |

### API Model Currency

| Provider | Models | Status |
|----------|--------|--------|
| claude | claude-sonnet-4-6, claude-haiku-4-5, claude-opus-4-6 | ✅ Current |
| openai | gpt-4o, gpt-4o-mini, o1, o3-mini | ✅ Current |
| mistral | mistral-large-latest, mistral-small-latest, codestral-latest | ✅ Current |
| bedrock | Dynamic via AWS discovery | ✅ Current |
| google | Dynamic from settings | ✅ Current |
| ollama | Dynamic via API | ✅ Current |

---

## 4. cluster.py Analysis

| Severity | Issue |
|----------|-------|
| 🟢 LOW | Duplicate socket import: `from socket import ...` AND `import socket` |
| ✅ OK | Well-structured, clear helper functions, no deep nesting |

---

## 5. aiobreaker Usage Patterns

- **Dependency**: `aiobreaker>=1.2.0,<2` in pyproject.toml
- **TYPE_CHECKING import**: `base.py` line 20 — `from aiobreaker import CircuitBreaker` (type hint only)
- **Runtime usage**: `mascarade/resilience/circuit_breaker.py` — `CircuitBreakerManager` wraps aiobreaker
- **Router integration**: `mascarade/router/circuit_breaker.py` has its own `CircuitBreaker` class (separate from resilience module — potential confusion)
- **Provider level**: No provider directly uses aiobreaker; circuit breaking is applied at Router level ✅

**Issue**: Two separate CircuitBreaker implementations exist:
1. `mascarade.router.circuit_breaker.CircuitBreaker` — simple implementation
2. `mascarade.resilience.circuit_breaker.CircuitBreakerManager` — aiobreaker-backed, full-featured

---

## 6. Notion Legacy Code Quantification

**Result: ZERO Notion code in core/**

- No imports, no references, no API calls to Notion
- Only references: `pyproject.toml` and `uv.lock` (dependency metadata, not code)
- Knowledge base has fully replaced Notion ✅

---

## 7. Dead Code Detection Summary

| Location | Dead Code | Severity |
|----------|-----------|----------|
| server.py L419 | Orphaned decorator (no function body) | 🔴 HIGH |
| server.py L2722 | Incomplete duplicate `/metrics` handler | 🔴 HIGH |
| server.py L19 | Unused `ConfigDict` import | 🟢 LOW |
| server.py L10/13/18/20/19/21 | Duplicate imports (3 sets) | 🟡 MED |

---

## 8. Severity Summary

| Severity | Count | Key Items |
|----------|-------|-----------|
| 🔴 CRITICAL | 3 | router.py missing imports (CircuitBreaker, cost_logger, cost_calculator) |
| 🔴 HIGH | 5 | server.py duplicate imports, orphaned decorator, route collision, incomplete function |
| 🟡 MEDIUM | 4 | kicad_router missing retry, mistral signature inconsistency, duplicate CircuitBreaker implementations, unused ConfigDict |
| 🟢 LOW | 3 | cluster.py duplicate socket import, bedrock sync wrapper, apple_coreml non-streaming |

**Overall Assessment**: Core code is functionally mature but server.py is a monolith that urgently needs decomposition. Router.py has potential runtime errors from missing imports. Provider implementations are consistent (9/10 use make_retry). No Notion legacy debt remains.
