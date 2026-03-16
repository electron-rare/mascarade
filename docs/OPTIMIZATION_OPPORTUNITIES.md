# Optimization Opportunities — Mascarade Ecosystem

Generated 2026-03-16. Covers core, API, web, deploy, CI/CD, and P2P mesh.

---

## Effort-vs-Impact Matrix

| # | Opportunity | Impact | Effort | Priority |
|---|------------|--------|--------|----------|
| 1 | Pytest parallelization (pytest-xdist) | High — 50-60% CI time reduction | Low | **P0** |
| 2 | Docker layer caching (generate-audio) | High — 30-40% build time | Medium | **P0** |
| 3 | Vite code-splitting + lazy Monaco | Medium — 20-30% bundle size | Low | **P1** |
| 4 | Metrics cardinality guards | Medium — Prometheus stability | Low | **P1** |
| 5 | P2P peer lock → RWLock | Medium — reduced contention | Low | **P1** |
| 6 | Redis connection pool tuning | Medium — 10-15% cache latency | Low | **P1** |
| 7 | Domain detection optimization (router) | Low-Medium — O(n) → O(1) lookup | Low | **P2** |
| 8 | Python dependency slimming | Medium — 200-300MB image size | High | **P2** |
| 9 | Distributed tracing (OpenTelemetry) | High — end-to-end visibility | High | **P2** |
| 10 | Docker Compose resource limits | Medium — stability under load | Medium | **P2** |
| 11 | server.py decomposition (2751 lines) | High — maintainability | High | **P3** |
| 12 | ops.ts decomposition (1925 lines) | High — maintainability | High | **P3** |

---

## 1. CI/CD Pipeline Speed

### Pytest parallelization
- **Current:** `python -m pytest -q` — sequential across 65 test files (745 tests)
- **Fix:** Add `pytest-xdist` to dev dependencies, run `pytest -n auto -q`
- **Expected gain:** 50-60% wall-clock reduction on multi-core CI runners
- **Effort:** 15 min

### CI Node.js version mismatch
- **Current:** CI uses Node 20, `api/package.json` engine specifies Node 22
- **Fix:** Align `.github/workflows/ci.yml` to Node 22
- **Effort:** 5 min

### Test markers for slow tests
- **Current:** No `@pytest.mark.slow` markers; all tests run every CI pass
- **Fix:** Mark integration/GPU tests as slow, add `--ignore-glob` for finetune tests in fast CI
- **Effort:** 30 min

---

## 2. Docker Image Sizes

### generate-audio Dockerfile
- **Current:** Single-stage build, torch installed without `--no-cache-dir`, no wheel caching layer
- **Fix:** Multi-stage build — builder layer for pip install, runtime layer copies only site-packages
- **Expected gain:** 30-40% smaller final image, faster rebuilds

### Core Dockerfile
- **Current:** `python:3.11-slim` with `--no-cache-dir` (good), but dependencies and source in same layer
- **Fix:** Split `COPY pyproject.toml` + `pip install` from `COPY . .` for better layer caching
- **Effort:** 15 min

### Docker Compose resource limits
- **Current:** No CPU/memory limits on any service in `docker-compose.yml` (31KB, 100+ services)
- **Fix:** Add `deploy.resources.limits` for memory-heavy services (core, generate-audio)
- **Effort:** 30 min

---

## 3. Caching Improvements

### Multi-tier cache tuning
- **Current:** L1 in-memory LRU + L2 Redis + L3 semantic — well-architected
- **Opportunities:**
  - Redis pool: `min_size=2, max_size=10` — increase to `min_size=5, max_size=25` for high concurrency
  - Add batch TTL cleanup instead of per-access expiry checks
  - L3 semantic cache utilization unknown — add hit/miss metrics

### Cache key cross-provider sharing
- **Current:** Cache keys exclude provider/strategy (good — allows cross-provider hits)
- **Opportunity:** Add cache warming for popular prompts during off-peak

---

## 4. Provider Routing Efficiency

### Domain detection
- **Current:** Linear keyword scan in `router.py` (dict iteration over domain_keywords)
- **Fix:** Pre-compile keyword → domain mapping into a trie or frozen set lookup
- **Expected gain:** O(n·k) → O(k) where k = prompt token count
- **Effort:** 1-2 hours

### Load balancer response tracking
- **Current:** `deque(maxlen=100)` per provider — efficient rolling window
- **Opportunity:** Add exponential moving average for faster response to provider degradation

---

## 5. P2P Mesh Latency

### Thread model
- **Current:** Dedicated `threading.Thread` per P2P node with trio↔asyncio bridge
- **Fix:** Use `asyncio.to_thread` with a shared ThreadPoolExecutor (reduces thread churn)
- **Effort:** 2-3 hours

### Peer lock contention
- **Current:** `threading.Lock()` for peer registry — all operations serialize
- **Fix:** Replace with `threading.RLock` or `asyncio.Lock` + read-write pattern
- **Expected gain:** 10-15% throughput under high peer discovery rates
- **Effort:** 1 hour

### GossipSub topic optimization
- **Current:** String-based topic names for heartbeat and capabilities
- **Fix:** Use content-addressed topic hashes to reduce message overhead
- **Effort:** Low but low impact

---

## 6. Bundle Size Optimization (Web)

### Monaco Editor lazy loading
- **Current:** `@monaco-editor/react` imported eagerly — ~2MB parsed JS
- **Fix:** `React.lazy()` + `Suspense` for editor routes only
- **Expected gain:** 20-30% reduction in initial bundle
- **Effort:** 30 min

### Vite config
- **Current:** Minimal `vite.config.ts` — no explicit code-splitting or chunk strategy
- **Fix:** Add `build.rollupOptions.output.manualChunks` to split vendor chunks
- **Effort:** 15 min

### API package.json cleanup
- **Current:** Server package includes `react`, `react-dom` as dependencies
- **Fix:** Move client deps to `devDependencies` or separate workspace package
- **Effort:** 30 min

---

## 7. Observability Gaps

### Missing distributed tracing
- **Current:** Langfuse optional tracing only — no cross-service correlation
- **Fix:** Add OpenTelemetry SDK with trace propagation (core → API → P2P)
- **Effort:** 1-2 days
- **Impact:** Critical for debugging multi-node P2P + LLM chains

### Metrics cardinality
- **Current:** No guards on Prometheus label values (model names, provider combos)
- **Risk:** Series explosion with new models/providers
- **Fix:** Allowlist known label values, bucket unknowns into "other"
- **Effort:** 1 hour

### Missing metrics
| Metric | Type | Why |
|--------|------|-----|
| Cache hit/miss ratio per tier | Counter | Validate multi-tier cache ROI |
| P2P message latency histogram | Histogram | SLA per node pair |
| Provider token throughput | Counter | Cost optimization signal |
| Queue depth per agent | Gauge | Backpressure visibility |

### Database observability
- **Current:** asyncpg pool with `min_size=2, max_size=10`, no leak detection
- **Fix:** Add pool exhaustion metric + connection lifetime tracking
- **Effort:** 30 min

---

## 8. Database & Connection Pooling

| Setting | Current | Recommended | Rationale |
|---------|---------|-------------|-----------|
| `max_size` | 10 | 20-25 | Support concurrent LLM + P2P + API |
| `command_timeout` | 60s | 30s | Fail fast on stuck queries |
| Prepared statements | Off | On | asyncpg native support, 10-20% query perf |
| Leak detection | None | Log connections held >30s | Prevent pool exhaustion |

---

## Priority Recommendations

### This week (P0 — high impact, low effort)
1. Add `pytest-xdist` to `core/pyproject.toml` dev deps → `pytest -n auto`
2. Split Docker layer: dependencies before source code in `Dockerfile.core`
3. Fix CI Node.js version mismatch (20 → 22)

### Next sprint (P1 — medium effort, solid returns)
4. Lazy-load Monaco editor in web frontend
5. Add Prometheus cardinality guards
6. Tune Redis pool settings (`max_size=25`)
7. Replace P2P peer `Lock` with read-write pattern

### Backlog (P2-P3 — high effort or lower urgency)
8. OpenTelemetry distributed tracing across core → API → P2P
9. Multi-stage Docker build for generate-audio
10. `server.py` decomposition (2751 → 5-6 focused modules)
11. `ops.ts` decomposition (1925 → route-group modules)
12. Python optional dependency groups to slim core image
