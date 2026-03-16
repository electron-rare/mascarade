# P2P Mesh, Caching, Fine-Tuning & Circuit Breaker — OSS Alternatives (2026-03-16)

## Context

This research covers four Mascarade subsystems where OSS alternatives should be evaluated:

1. **P2P Mesh** — Custom TCP transport + libp2p dual-backend (17 modules)
2. **Caching** — Multi-tier L1/L2/L3 (in-memory → Redis → semantic)
3. **Fine-Tuning Pipeline** — 36 scripts, 11 domains, Unsloth/TRL-based
4. **Circuit Breaker** — `aiobreaker` dependency (abandoned since May 2021)

---

## 1. Circuit Breaker Alternatives (CRITICAL — aiobreaker abandoned)

### Current State

Mascarade uses `aiobreaker>=1.2.0,<2` (last release: May 2021, no commits since). It wraps `CircuitBreaker`, `CircuitBreakerListener`, and `CircuitBreakerState` in `core/mascarade/resilience/circuit_breaker.py`. Also imported in `core/mascarade/router/providers/base.py`.

**Risk:** Unmaintained dependency on Python 3.11+ async codebase. No Python 3.12/3.13 testing, no security patches, no bug fixes.

### Alternatives Evaluated

| Library | Stars | Last Release | Async | Maintenance | License |
|---------|-------|-------------|-------|-------------|---------|
| **aiobreaker** (current) | 150 | May 2021 | ✅ | ❌ Abandoned | MIT |
| **purgatory** | 40 | Oct 2024 | ✅ | ⚠️ Low activity | MIT |
| **aiomisc** (circuit_breaker) | 400 | Mar 2026 | ✅ | ✅ Active | MIT |
| **pybreaker** | 600 | Jun 2025 | ❌ sync | ✅ Active | BSD |
| **tenacity** + custom | 6.5k | Mar 2026 | ✅ | ✅ Active | Apache 2.0 |
| **Custom implementation** | N/A | N/A | ✅ | ✅ Self-owned | N/A |

### Detailed Analysis

#### purgatory
- Pure async circuit breaker for Python
- API: `purgatory = Purgatory()` → `async with purgatory.get("service"):` context manager
- Supports Redis-backed state sharing (multi-instance)
- Low star count but clean codebase, typed
- **Migration effort:** Medium — different API (context manager vs decorator), but similar concepts

#### aiomisc.circuit_breaker
- Part of the larger `aiomisc` toolkit (async utilities)
- Circuit breaker is one module among many — importing pulls in extras
- Well-maintained, tested on Python 3.11+
- **Migration effort:** Low — similar decorator pattern to aiobreaker
- **Concern:** Pulls in a larger dependency for one feature

#### pybreaker
- Most popular Python circuit breaker (600 stars)
- Fork of the original `pybreaker` project
- **Sync only** — would need wrapping for async code
- Not suitable for Mascarade's async-first architecture
- **Migration effort:** High — async wrapping needed everywhere

#### tenacity + custom state machine
- `tenacity` handles retry/backoff (already a common pattern in Python)
- Combine with a simple state machine (CLOSED/OPEN/HALF_OPEN) in ~80 lines
- Full control, no abandoned dependencies
- **Migration effort:** Medium — write ~80 lines, replace aiobreaker calls

#### Custom implementation (RECOMMENDED)
- Mascarade's `CircuitBreakerManager` already wraps aiobreaker with its own abstractions
- The actual aiobreaker surface used is minimal: `CircuitBreaker`, `CircuitBreakerListener`, `CircuitBreakerState`
- A custom implementation (~120 lines) would:
  - Remove the abandoned dependency entirely
  - Add `success_count` tracking (currently missing: "aiobreaker ne track pas success_count")
  - Add per-breaker timeout configuration
  - Keep the exact same `CircuitBreakerManager` API
- **Migration effort:** Low — replace internals, keep `CircuitBreakerManager` API unchanged

### Recommendation

**→ Custom implementation (P0)**

Replace aiobreaker with a self-contained ~120 line async circuit breaker. The current `CircuitBreakerManager` in `resilience/circuit_breaker.py` already abstracts away aiobreaker — only the internal implementation changes. This:
- Eliminates the abandoned dependency
- Adds missing `success_count` tracking
- Requires zero changes to callers (`get_breaker()`, `get_metrics()`, `reset()`)
- Estimated effort: **2-4 hours**

---

## 2. P2P Mesh Alternatives

### Current State

Mascarade runs a dual-backend P2P system:
- **Primary:** Custom asyncio TCP transport (`transport.py`, `protocol.py`) with bounded timeouts, peer discovery, task distribution
- **Secondary:** libp2p node (`libp2p_node.py`) using py-libp2p with trio↔asyncio bridge, mplex muxer, gossipsub pubsub

17 modules total in `core/mascarade/p2p/`. Live mesh has 4 nodes (VM, GrosMac, CILS, Tower).

### Alternatives Evaluated

| Library | Stars | Last Release | Language | Maintenance | Fit |
|---------|-------|-------------|----------|-------------|-----|
| **py-libp2p** (current secondary) | 400 | Jan 2026 | Python (trio) | ⚠️ Sporadic | Already integrated |
| **ZeroMQ (pyzmq)** | 3.8k | Mar 2026 | Python | ✅ Active | Good — transport |
| **NATS (nats-py)** | 900 | Mar 2026 | Python | ✅ Active | Good — messaging |
| **gRPC (grpcio)** | 43k | Mar 2026 | Python | ✅ Active | Overkill |
| **Dask Distributed** | 12k | Mar 2026 | Python | ✅ Active | Wrong abstraction |
| **Ray** | 35k | Mar 2026 | Python | ✅ Active | Overkill for 4 nodes |

### Detailed Analysis

#### py-libp2p (keep as-is)
- Already integrated as the secondary backend
- Trio↔asyncio bridge adds complexity but works
- Pubsub (gossipsub) and DHT capabilities
- Sporadic maintenance — Python bindings lag behind Go/Rust implementations
- **Verdict:** Keep for pubsub/DHT features, but the custom TCP transport is the production path

#### ZeroMQ (pyzmq)
- Battle-tested messaging library, excellent for small cluster topologies
- Patterns: PUB/SUB, REQ/REP, PUSH/PULL — all useful for task distribution
- No discovery protocol (needs external mechanism or static config)
- **Would replace:** Custom TCP transport layer only
- **Migration effort:** High — rewrite transport + protocol layers
- **Benefit:** More robust connection handling, built-in message framing

#### NATS (nats-py)
- Lightweight messaging system with built-in clustering
- JetStream for persistent messaging, KV store, object store
- Native async Python client
- Would simplify: peer discovery (NATS subjects), task distribution (queue groups), pub/sub
- **Migration effort:** High — requires NATS server deployment, rewrite P2P layer
- **Benefit:** Eliminates custom discovery, adds message persistence

#### gRPC / Ray / Dask
- All overkill for a 4-node personal mesh
- gRPC adds protobuf compilation step
- Ray/Dask are compute frameworks, not communication layers

### Recommendation

**→ Keep current dual-backend (no change)**

The custom TCP transport is production-proven with bounded timeouts (per P2P_MESH_RESEARCH_2026-03-14). The 4-node mesh doesn't justify migrating to ZeroMQ or NATS. If the mesh grows beyond 10 nodes, **NATS** would be the right migration target (native clustering, queue groups for task distribution, JetStream for persistence).

**Future consideration:** If libp2p maintenance stalls completely, extract only the pubsub/DHT capabilities needed and drop the dependency.

---

## 3. Caching Layer Alternatives

### Current State

Mascarade implements a 3-tier cache:
- **L1:** `InMemoryCache` — LRU, sync, always available
- **L2:** `RedisCache` — async via `redis.asyncio`, optional
- **L3:** `SemanticCache` — GPTCache-based similarity search, optional

Architecture is clean: `CacheBackend` ABC, `MultiTierCache` orchestrator with backfill on L2/L3 hits.

### Alternatives Evaluated

| Component | Current | Alternative | Stars | Maintenance | Migration |
|-----------|---------|------------|-------|-------------|-----------|
| L2 store | Redis (redis-py) | **Valkey** (valkey-py) | 18k | ✅ Active | Drop-in |
| L2 store | Redis | **DragonflyDB** | 30k | ✅ Active | Drop-in |
| L1 cache | Custom LRU | **cachetools** | 2.3k | ✅ Active | Low |
| L3 semantic | GPTCache | **LangChain Cache** | N/A | ✅ Active | Medium |
| Full stack | Custom | **cashews** | 500 | ✅ Active | High |

### Detailed Analysis

#### Valkey (Redis fork)
- Linux Foundation fork of Redis after license change (2024)
- Wire-compatible with Redis — `valkey-py` is a fork of `redis-py`
- Drop-in replacement: change `import redis.asyncio` → `import valkey.asyncio`
- Same commands, same performance, truly open source (BSD)
- **Migration effort:** Trivial — 1-line import change + Docker image swap
- **Benefit:** License clarity (BSD vs Redis's SSPL/RSALv2)

#### DragonflyDB
- Redis/Memcached compatible, but 25x faster on benchmarks
- Same wire protocol — works with existing `redis-py` client
- Better multi-threaded performance on modern hardware
- **Migration effort:** Zero code changes — just swap Docker image
- **Benefit:** Performance on multi-core (relevant for VM deployment)

#### cachetools for L1
- Mature Python caching library with LRU, TTL, LFU strategies
- Thread-safe variants available
- Would replace the custom `InMemoryCache`
- **Migration effort:** Low — swap implementation, keep `CacheBackend` interface
- **Marginal benefit** — current L1 works fine

#### cashews (full async cache framework)
- Async cache framework with decorator support, multiple backends
- Overkill — Mascarade's `MultiTierCache` is already well-structured
- Would add unnecessary abstraction

### Recommendation

**→ Valkey migration (P2, low effort)**

Swap Redis for Valkey for license clarity. Zero code changes (wire-compatible), just:
1. `pip install valkey` (or keep `redis-py` which works with Valkey server)
2. Swap Docker image `redis:7` → `valkey/valkey:8`

The multi-tier cache architecture is solid — no framework replacement needed. Consider DragonflyDB if Redis/Valkey performance becomes a bottleneck.

---

## 4. Fine-Tuning Pipeline Alternatives

### Current State

Mascarade's fine-tuning pipeline:
- 36 Python scripts, 11 domains, ~143K training examples
- Uses: `transformers`, `trl`, `peft`, `bitsandbytes`, `datasets`, `unsloth`
- Key scripts: `pipeline.py`, `batch_local.py` (1628 lines), `model_selector.py` (1746 lines)
- Hardware: RTX 4090 (24GB VRAM)
- Zero tests

### Frameworks Compared

| Framework | Stars | Last Release | GPU Req | GRPO/DPO | Multi-GPU | Config |
|-----------|-------|-------------|---------|----------|-----------|--------|
| **Unsloth** (current) | 25k | Mar 2026 | Single | ✅ | ❌ | Python API |
| **LLaMA-Factory** | 67k | Mar 2026 | Single+ | ✅ | ✅ | YAML + Web UI |
| **Axolotl** | 8k | Feb 2026 | Single+ | ✅ GRPO | ✅ | YAML |
| **TRL** (current dep) | 12k | Mar 2026 | Any | ✅ | ✅ | Python API |
| **torchtune** | 5k | Mar 2026 | Any | ✅ | ✅ | Config files |
| **OpenRLHF** | 7k | Mar 2026 | Multi | ✅ | ✅ Ray | Python |

### Detailed Analysis

#### Unsloth (keep as primary)
- 12x faster than base HF training, lowest VRAM usage
- Perfect for single RTX 4090 workflow
- Dynamic 4-bit quantization, GGUF export
- Active development, new MoE support
- **Current role in Mascarade:** Core training backend
- **Verdict:** Keep — best single-GPU performance

#### LLaMA-Factory (RECOMMENDED addition)
- Config-driven training orchestration — YAML defines the full pipeline
- Uses Unsloth as backend (best of both worlds)
- Web UI for monitoring (optional)
- 67k stars, very active community
- Already in `docs/research/OSS_PROJECTS_2026-03-11.md` as priority #3
- **Migration effort:** Medium — define YAML configs per domain, replace batch_local.py invocations
- **Benefit:** Reduces batch_local.py (1628 lines) to YAML configs + orchestration calls
- Could replace ~50% of custom pipeline scripts

#### Axolotl (alternative to LLaMA-Factory)
- YAML-driven fine-tuning, similar philosophy to LLaMA-Factory
- Stronger multi-GPU support
- GRPO and QAT (Quantization-Aware Training) support
- Smaller community (8k vs 67k stars)
- **Migration effort:** Medium — similar to LLaMA-Factory
- **Verdict:** LLaMA-Factory is preferred (larger community, Unsloth integration)

#### OpenRLHF (alignment layer)
- Ray + vLLM + DeepSpeed for RLHF/GRPO at scale
- Already in `docs/research/OSS_PROJECTS_2026-03-11.md` as priority #1
- Overkill for single-GPU but relevant for multi-node training via P2P mesh
- **Migration effort:** High — requires Ray cluster setup
- **Verdict:** Future consideration when multi-node training is needed

#### torchtune (Meta)
- Bare PyTorch, minimal abstractions
- Good for learning, bad for productivity
- Less mature multi-node than Axolotl/LLaMA-Factory
- **Verdict:** Skip — too low-level

### Recommendation

**→ Add LLaMA-Factory as orchestration layer (P1)**

Keep Unsloth as the training backend. Layer LLaMA-Factory on top for:
- YAML-driven domain configs (replace hardcoded parameters in 36 scripts)
- Built-in Unsloth integration (no performance loss)
- Monitoring dashboard
- Estimated effort: **1-2 weeks** to convert existing domains to YAML configs

This directly addresses the complexity hotspots: `batch_local.py` (1628 lines) and `model_selector.py` (1746 lines) can be significantly simplified.

---

## Summary Table

| Subsystem | Current | Recommendation | Priority | Effort | Impact |
|-----------|---------|---------------|----------|--------|--------|
| Circuit Breaker | aiobreaker (abandoned) | Custom implementation | **P0** | 2-4h | Eliminates security risk |
| P2P Mesh | Custom TCP + libp2p | Keep as-is | — | — | No change needed |
| Caching L2 | Redis | Valkey (Docker swap) | **P2** | 1h | License clarity |
| Fine-Tuning | Raw scripts + Unsloth | + LLaMA-Factory orchestration | **P1** | 1-2 weeks | Major complexity reduction |
| Circuit Breaker alt | — | Monitor purgatory/aiomisc | — | — | Fallback options |
| P2P future | — | NATS if >10 nodes | — | — | Future scalability |

### Key Takeaways

1. **aiobreaker replacement is urgent (P0)** — abandoned dependency on async codepath, easy custom replacement
2. **LLaMA-Factory adoption reduces pipeline complexity significantly (P1)** — YAML configs replace thousands of lines of hardcoded training scripts
3. **Valkey is a free win (P2)** — Docker image swap, zero code changes, license clarity
4. **P2P mesh is fine as-is** — custom transport with bounded timeouts is production-proven for 4 nodes
5. **The caching architecture is solid** — multi-tier with backfill is a good pattern, no framework needed
