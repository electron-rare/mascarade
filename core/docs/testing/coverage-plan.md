# Test Coverage Plan — Mascarade v1.1.0

## Executive Summary

This document outlines the test coverage strategy to achieve **80%+ overall coverage** with **95%+ coverage on critical paths** (auth, routing, orchestration) as part of the P2 Testing phase.

**Current Baseline**: 49% coverage (5795/11833 lines covered)
**Target**: 80% overall, 95% critical paths
**Gap**: +31 percentage points overall

---

## Critical Paths Requiring Coverage

### 1. Authentication & Authorization (`core/mascarade/auth.py`)

**Current State**: Mixed coverage - rate limiting present, DB auth partially tested
**Target Coverage**: 95%+
**Priority**: P0 (Security-critical)

#### Critical Functions to Test

##### 1.1 API Key Validation
- ✅ **COVERED**: Basic `is_valid_api_key()` tests exist
- ❌ **GAP**: Timing-safe comparison edge cases
- ❌ **GAP**: Key rotation during active requests
- ❌ **GAP**: Minimum key length validation (16 chars)
- ❌ **GAP**: Thread-safety under concurrent access

**Test Cases Needed:**
```python
# test_auth.py additions
async def test_timing_safe_compare_constant_time()
async def test_key_rotation_during_request()
async def test_api_key_minimum_length_rejection()
async def test_concurrent_key_validation()
async def test_key_rotation_interval_enforcement()
```

##### 1.2 Rate Limiting
- ✅ **COVERED**: Basic rate limiter initialization
- ❌ **GAP**: Per-user limit enforcement (100 req/min default)
- ❌ **GAP**: Per-IP limit enforcement (200 req/min default)
- ❌ **GAP**: Sliding window cleanup mechanism
- ❌ **GAP**: Rate limit metrics collection
- ❌ **GAP**: Rate limit reset functionality
- ❌ **GAP**: Concurrent request handling

**Test Cases Needed:**
```python
# test_rate_limiting.py (new file)
async def test_per_user_rate_limit_enforcement()
async def test_per_ip_rate_limit_enforcement()
async def test_rate_limit_sliding_window()
async def test_rate_limit_cleanup_expired_timestamps()
async def test_rate_limit_metrics_accuracy()
async def test_rate_limit_reset_user()
async def test_rate_limit_reset_ip()
async def test_rate_limit_concurrent_requests()
async def test_rate_limit_429_response_format()
```

##### 1.3 RBAC (Role-Based Access Control)
- ❌ **GAP**: Role resolution (admin/operator/viewer)
- ❌ **GAP**: Permission enforcement per endpoint
- ❌ **GAP**: Path-based permission requirements
- ❌ **GAP**: Method-based permission requirements (GET vs POST)

**Test Cases Needed:**
```python
# test_rbac_integration.py (new file)
async def test_admin_role_resolution()
async def test_operator_role_resolution()
async def test_viewer_role_resolution()
async def test_admin_only_endpoints()
async def test_viewer_read_only_enforcement()
async def test_operator_write_permissions()
async def test_rbac_disabled_fallback_to_admin()
```

##### 1.4 Database-Backed Authentication
- ✅ **COVERED**: Basic `authenticate_user()` flow
- ❌ **GAP**: API key expiration handling
- ❌ **GAP**: Inactive user rejection
- ❌ **GAP**: Inactive API key rejection
- ❌ **GAP**: Last-used timestamp update
- ❌ **GAP**: Database connection failure fallback

**Test Cases Needed:**
```python
# test_db_auth.py (new file)
async def test_expired_api_key_rejection()
async def test_inactive_user_rejection()
async def test_inactive_api_key_rejection()
async def test_last_used_timestamp_update()
async def test_auth_database_unavailable()
async def test_role_rate_limits_inheritance()
```

##### 1.5 Legacy Key Migration
- ❌ **GAP**: Migration of MASCARADE_API_KEY to database
- ❌ **GAP**: Duplicate key detection
- ❌ **GAP**: Migration tracking
- ❌ **GAP**: Admin user creation for legacy keys

**Test Cases Needed:**
```python
# test_legacy_migration.py (new file)
async def test_migrate_legacy_keys_success()
async def test_migrate_legacy_keys_duplicate_skip()
async def test_migrate_legacy_keys_tracking()
async def test_migrate_legacy_keys_admin_creation()
```

---

### 2. Router & Provider Selection (`core/mascarade/router/router.py`)

**Current State**: Partial coverage - basic routing tested, advanced features untested
**Target Coverage**: 95%+
**Priority**: P0 (Core business logic)

#### Critical Functions to Test

##### 2.1 Provider Selection Strategies
- ✅ **COVERED**: Basic BEST strategy
- ❌ **GAP**: CHEAPEST strategy with cost calculation
- ❌ **GAP**: FASTEST strategy with speed ranking
- ❌ **GAP**: DOMAIN strategy with domain detection
- ❌ **GAP**: SPECIFIC strategy with provider name
- ❌ **GAP**: ROUTELLM strategy with complexity scoring

**Test Cases Needed:**
```python
# test_router_strategies.py (new file)
async def test_cheapest_strategy_measured_cost()
async def test_cheapest_strategy_static_cost_fallback()
async def test_fastest_strategy_speed_rank()
async def test_domain_strategy_ollama_preference()
async def test_domain_strategy_fallback_to_best()
async def test_specific_strategy_provider_selection()
async def test_specific_strategy_invalid_provider()
async def test_routellm_auto_policy()
async def test_routellm_strong_policy()
async def test_routellm_cheap_policy()
async def test_routellm_fast_policy()
```

##### 2.2 Domain Detection & Routing
- ❌ **GAP**: Domain detection from message content
- ❌ **GAP**: Keyword-based domain matching (spice, kicad, stm32, electronics, code)
- ❌ **GAP**: Domain-specific provider filtering
- ❌ **GAP**: Benchmark-based provider selection for domains

**Test Cases Needed:**
```python
# test_domain_detection.py (enhance existing)
async def test_detect_domain_spice()
async def test_detect_domain_kicad()
async def test_detect_domain_stm32()
async def test_detect_domain_electronics()
async def test_detect_domain_code()
async def test_detect_domain_no_match()
async def test_domain_routing_filters_providers()
async def test_domain_routing_fallback_to_all()
```

##### 2.3 Fallback & Circuit Breaker
- ✅ **COVERED**: Basic fallback sequence
- ❌ **GAP**: Circuit breaker OPEN state blocking
- ❌ **GAP**: Circuit breaker HALF_OPEN recovery
- ❌ **GAP**: Circuit breaker success/failure recording
- ❌ **GAP**: Provider fallback after circuit breaker trip
- ❌ **GAP**: All providers unavailable scenario

**Test Cases Needed:**
```python
# test_router_circuit_breaker.py (new file)
async def test_circuit_breaker_open_blocks_provider()
async def test_circuit_breaker_half_open_allows_retry()
async def test_circuit_breaker_success_closes()
async def test_circuit_breaker_failure_increments()
async def test_fallback_after_circuit_breaker()
async def test_all_providers_circuit_open()
```

##### 2.4 Caching Integration
- ❌ **GAP**: Cache hit on exact match
- ❌ **GAP**: Cache miss triggers provider call
- ❌ **GAP**: Cache storage after successful response
- ❌ **GAP**: Cache key generation (messages + strategy + provider + model)
- ❌ **GAP**: Strict provider cache bypass

**Test Cases Needed:**
```python
# test_router_caching.py (new file)
async def test_cache_hit_returns_cached_response()
async def test_cache_miss_calls_provider()
async def test_cache_stores_successful_response()
async def test_cache_key_includes_all_params()
async def test_strict_provider_bypasses_cache()
```

##### 2.5 Cost Tracking & Metrics
- ❌ **GAP**: Token usage calculation
- ❌ **GAP**: Cost calculation (input + output tokens)
- ❌ **GAP**: Metrics tracking per provider
- ❌ **GAP**: Load balancer integration
- ❌ **GAP**: Cost logger integration

**Test Cases Needed:**
```python
# test_router_metrics.py (new file)
async def test_token_usage_calculation()
async def test_cost_calculation_per_provider()
async def test_metrics_track_success()
async def test_metrics_track_failure()
async def test_load_balancer_updates()
async def test_cost_logger_events()
```

##### 2.6 Streaming Support
- ❌ **GAP**: Stream fallback on pre-token failure
- ❌ **GAP**: Stream failure mid-stream handling
- ❌ **GAP**: Stream circuit breaker integration
- ❌ **GAP**: Stream metrics tracking

**Test Cases Needed:**
```python
# test_router_streaming.py (new file)
async def test_stream_fallback_before_first_token()
async def test_stream_fails_mid_stream_no_fallback()
async def test_stream_circuit_breaker_integration()
async def test_stream_metrics_tracking()
```

---

### 3. Orchestration (`core/mascarade/orchestrator/engine.py`)

**Current State**: Basic coverage - sequential mode tested, advanced modes untested
**Target Coverage**: 95%+
**Priority**: P0 (Core orchestration logic)

#### Critical Functions to Test

##### 3.1 Sequential Execution
- ✅ **COVERED**: Basic sequential agent execution
- ❌ **GAP**: Sequential with skip_on_error=True
- ❌ **GAP**: Sequential with skip_on_error=False (stops on error)
- ❌ **GAP**: Sequential routing overrides
- ❌ **GAP**: Sequential trace recording

**Test Cases Needed:**
```python
# test_orchestrator_sequential.py (enhance existing)
async def test_sequential_skip_on_error_continues()
async def test_sequential_stops_on_error()
async def test_sequential_routing_overrides_per_agent()
async def test_sequential_trace_recording()
```

##### 3.2 Parallel Execution
- ❌ **GAP**: Parallel execution of multiple agents
- ❌ **GAP**: Parallel timeout enforcement
- ❌ **GAP**: Parallel error handling (return_exceptions=True)
- ❌ **GAP**: Parallel routing overrides
- ❌ **GAP**: Parallel trace recording

**Test Cases Needed:**
```python
# test_orchestrator_parallel.py (new file)
async def test_parallel_all_agents_succeed()
async def test_parallel_partial_failure()
async def test_parallel_timeout_enforcement()
async def test_parallel_routing_overrides()
async def test_parallel_trace_recording()
```

##### 3.3 Pipeline Execution
- ❌ **GAP**: Pipeline output chaining (agent1 → agent2 → agent3)
- ❌ **GAP**: Pipeline with skip_on_error=True
- ❌ **GAP**: Pipeline with skip_on_error=False
- ❌ **GAP**: Pipeline fallback_map usage
- ❌ **GAP**: Pipeline handoff tracing

**Test Cases Needed:**
```python
# test_orchestrator_pipeline.py (new file)
async def test_pipeline_output_chaining()
async def test_pipeline_skip_on_error_continues()
async def test_pipeline_stops_on_error()
async def test_pipeline_fallback_agent_on_failure()
async def test_pipeline_fallback_agent_also_fails()
async def test_pipeline_handoff_tracing()
```

##### 3.4 Retry Logic Integration
- ❌ **GAP**: Retry executor with configurable attempts
- ❌ **GAP**: Exponential backoff delays
- ❌ **GAP**: Retry callback invocation
- ❌ **GAP**: Retry exhaustion raises error

**Test Cases Needed:**
```python
# test_orchestrator_retry.py (enhance existing)
async def test_retry_executor_max_attempts()
async def test_retry_exponential_backoff()
async def test_retry_callback_invoked()
async def test_retry_exhausted_raises()
```

##### 3.5 Circuit Breaker Integration
- ❌ **GAP**: Circuit breaker per-agent isolation
- ❌ **GAP**: Circuit breaker state transitions (CLOSED → OPEN → HALF_OPEN)
- ❌ **GAP**: Circuit breaker blocks execution when OPEN
- ❌ **GAP**: Circuit breaker state change callbacks
- ❌ **GAP**: Circuit breaker success resets failure count

**Test Cases Needed:**
```python
# test_orchestrator_circuit_breaker.py (new file)
async def test_circuit_breaker_per_agent()
async def test_circuit_breaker_opens_after_failures()
async def test_circuit_breaker_blocks_when_open()
async def test_circuit_breaker_half_open_recovery()
async def test_circuit_breaker_success_resets()
async def test_circuit_breaker_state_change_trace()
```

##### 3.6 Dead Letter Store Integration
- ❌ **GAP**: Failure recording in dead letter store
- ❌ **GAP**: Context capture (prompt, agent_names, mode)
- ❌ **GAP**: Dead letter retrieval for debugging

**Test Cases Needed:**
```python
# test_orchestrator_dead_letter.py (new file)
async def test_dead_letter_records_failure()
async def test_dead_letter_captures_context()
async def test_dead_letter_retrieval()
```

##### 3.7 Ray Cluster Integration (if enabled)
- ❌ **GAP**: Ray initialization
- ❌ **GAP**: Ray remote execution
- ❌ **GAP**: Ray fallback to local on failure
- ❌ **GAP**: Ray circuit breaker per agent
- ❌ **GAP**: Ray timeout enforcement

**Test Cases Needed:**
```python
# test_orchestrator_ray.py (new file - conditional on Ray availability)
async def test_ray_initialization()
async def test_ray_remote_execution()
async def test_ray_fallback_to_local()
async def test_ray_circuit_breaker()
async def test_ray_timeout()
```

---

## Coverage Targets by Module

| Module | Current | Target | Gap | Priority |
|--------|---------|--------|-----|----------|
| `auth.py` | ~60% | 95% | +35pp | P0 |
| `router/router.py` | ~55% | 95% | +40pp | P0 |
| `orchestrator/engine.py` | ~65% | 95% | +30pp | P0 |
| `router/providers/*.py` | ~50% | 80% | +30pp | P1 |
| `router/fallback.py` | ~40% | 90% | +50pp | P1 |
| `router/model_registry.py` | ~30% | 85% | +55pp | P1 |
| `router/health_monitor.py` | ~25% | 85% | +60pp | P1 |
| `cache/*.py` | ~45% | 80% | +35pp | P2 |
| `agents/*.py` | ~55% | 80% | +25pp | P2 |
| `config.py` | ~70% | 90% | +20pp | P0 |
| `server.py` (post-refactor) | N/A | 85% | N/A | P1 |

**Overall Target**: 80%+ (from current 49%)

---

## Test Implementation Strategy

### Phase 1: Critical Path Coverage (Weeks 10-11)
**Goal**: Achieve 95%+ coverage on auth, routing, orchestration

1. **Week 10, Days 1-2**: Auth module tests
   - Implement rate limiting test suite
   - Implement RBAC test suite
   - Implement DB auth test suite
   - Implement legacy migration tests

2. **Week 10, Days 3-5**: Router module tests
   - Implement strategy selection tests
   - Implement domain detection/routing tests
   - Implement circuit breaker integration tests
   - Implement caching integration tests

3. **Week 11, Days 1-2**: Orchestrator module tests
   - Implement parallel execution tests
   - Implement pipeline execution tests
   - Implement circuit breaker per-agent tests
   - Implement dead letter store tests

4. **Week 11, Days 3-5**: Retry, fallback, metrics tests
   - Implement retry executor tests
   - Implement fallback sequence tests
   - Implement metrics tracking tests
   - Implement cost calculation tests

### Phase 2: Supporting Modules (Week 11)
**Goal**: Achieve 80%+ coverage on supporting modules

1. **Provider implementations** (`router/providers/*.py`)
   - Test each provider's `send()` and `stream()` methods
   - Test error handling and timeout scenarios
   - Test provider-specific response parsing

2. **Health monitoring** (`router/health_monitor.py`)
   - Test health score calculation
   - Test provider health caching
   - Test health degradation detection

3. **Model registry** (`router/model_registry.py`)
   - Test model registration
   - Test health verification
   - Test model metadata storage

4. **Cache layers** (`cache/*.py`)
   - Test multi-tier cache retrieval
   - Test cache eviction policies
   - Test semantic cache similarity matching

### Phase 3: Integration & E2E Tests (Week 12)
**Goal**: Validate cross-module interactions and end-to-end flows

1. **Integration tests** (`tests/integration/`)
   - Auth → Router integration
   - Router → Provider integration
   - Orchestrator → Router → Provider flow
   - Cache → Router integration

2. **E2E tests** (`tests/e2e/`)
   - Full chat completion flow
   - Multi-agent orchestration workflows
   - Provider failover scenarios
   - Rate limiting under load

---

## Test Patterns & Conventions

### Async Test Pattern (pytest-asyncio)
```python
import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_example():
    """All async tests use @pytest.mark.asyncio decorator"""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post("/v1/chat/completions", json={...})
        assert response.status_code == 200
```

### Fixture Pattern
```python
@pytest.fixture
async def mock_router():
    """Reusable fixtures in conftest.py"""
    router = Router()
    # Setup mock providers
    yield router
    # Cleanup
```

### Parametrized Tests
```python
@pytest.mark.parametrize("strategy,expected_provider", [
    (Strategy.BEST, "anthropic"),
    (Strategy.CHEAPEST, "mistral"),
    (Strategy.FASTEST, "anthropic"),
])
async def test_strategy_selection(strategy, expected_provider):
    """Test multiple scenarios with single test function"""
    ...
```

---

## Coverage Measurement & Enforcement

### Local Development
```bash
# Run tests with coverage report
cd core
python -m pytest --cov=mascarade --cov-report=html --cov-report=term

# View HTML report
open htmlcov/index.html
```

### CI/CD Integration
```yaml
# .github/workflows/test.yml
- name: Run tests with coverage
  run: |
    pytest --cov=mascarade --cov-report=xml --cov-report=term

- name: Enforce coverage threshold
  run: |
    coverage report --fail-under=80

- name: Upload coverage to Codecov
  uses: codecov/codecov-action@v3
```

### pyproject.toml Configuration
```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
asyncio_default_fixture_loop_scope = "function"
testpaths = ["tests"]
addopts = "--cov=mascarade --cov-report=html --cov-report=term --cov-fail-under=80"

[tool.coverage.run]
branch = true
source = ["mascarade"]
omit = ["*/tests/*", "*/migrations/*", "*/__pycache__/*"]

[tool.coverage.report]
precision = 2
show_missing = true
skip_covered = false
```

---

## Success Criteria

### P0 Criteria (Must Have)
- ✅ Overall coverage ≥ 80%
- ✅ Auth module coverage ≥ 95%
- ✅ Router module coverage ≥ 95%
- ✅ Orchestrator module coverage ≥ 95%
- ✅ CI enforces coverage threshold (build fails <80%)
- ✅ No regression in existing test pass rate

### P1 Criteria (Should Have)
- ✅ Provider modules coverage ≥ 80%
- ✅ Cache modules coverage ≥ 80%
- ✅ Config module coverage ≥ 90%
- ✅ Coverage report published with each PR
- ✅ Branch coverage enabled

### P2 Criteria (Nice to Have)
- ⚪ Mutation testing score ≥ 70% (using mutmut or cosmic-ray)
- ⚪ Property-based testing for critical algorithms (using Hypothesis)
- ⚪ Performance regression tests integrated

---

## Test Files to Create/Enhance

### New Test Files
```
core/tests/
├── test_rate_limiting.py              # Rate limiter edge cases
├── test_rbac_integration.py           # RBAC permission enforcement
├── test_db_auth.py                    # Database-backed auth
├── test_legacy_migration.py           # Legacy key migration
├── test_router_strategies.py          # Router strategy selection
├── test_router_circuit_breaker.py     # Circuit breaker integration
├── test_router_caching.py             # Cache integration
├── test_router_metrics.py             # Metrics tracking
├── test_router_streaming.py           # Streaming support
├── test_orchestrator_parallel.py      # Parallel execution
├── test_orchestrator_pipeline.py      # Pipeline execution
├── test_orchestrator_circuit_breaker.py  # Per-agent circuit breakers
├── test_orchestrator_dead_letter.py   # Dead letter store
└── test_orchestrator_ray.py           # Ray cluster integration
```

### Files to Enhance
```
core/tests/
├── test_auth.py                       # Add timing/rotation tests
├── test_router.py                     # Add domain routing tests
├── test_orchestrator.py               # Add trace validation
├── test_orchestrator_retry.py         # Add backoff tests
└── conftest.py                        # Add shared fixtures
```

---

## Risk Mitigation

### Risk: Breaking Existing Tests
**Mitigation**: Run full test suite before and after each change. Maintain baseline test pass rate.

### Risk: Flaky Async Tests
**Mitigation**: Use proper async fixtures (`asyncio_default_fixture_loop_scope = "function"`), avoid shared state, use `asyncio.wait_for()` for timeouts.

### Risk: Mocking Provider API Calls
**Mitigation**: Use `pytest-httpx` for HTTP mocking, create reusable mock fixtures in `conftest.py`.

### Risk: Test Execution Time
**Mitigation**: Mark slow tests with `@pytest.mark.slow`, run fast tests in CI, full suite nightly.

### Risk: Coverage vs Quality Trade-off
**Mitigation**: Focus on critical paths first, emphasize edge cases and error paths, not just happy paths.

---

## Appendix: Coverage Gap Analysis

### Current Coverage by Module (from baseline)
```
Module                              Stmts   Miss  Cover
-------------------------------------------------------
mascarade/__init__.py                   5      0   100%
mascarade/auth.py                     300    120    60%
mascarade/router/router.py            450    200    55%
mascarade/orchestrator/engine.py      320    110    65%
mascarade/router/providers/base.py     40      5    87%
mascarade/config.py                   120     35    71%
mascarade/cache/multi_tier_cache.py   180     95    47%
... (other modules)
-------------------------------------------------------
TOTAL                               11833   6038    49%
```

### Priority Order for Coverage Improvement
1. **auth.py** (+35pp to 95%) - Security-critical, user-facing
2. **router/router.py** (+40pp to 95%) - Core business logic
3. **orchestrator/engine.py** (+30pp to 95%) - Multi-agent coordination
4. **config.py** (+20pp to 90%) - Configuration management (P0)
5. **router/fallback.py** (+50pp to 90%) - Reliability
6. **router/health_monitor.py** (+60pp to 85%) - Observability
7. **router/model_registry.py** (+55pp to 85%) - Model management
8. **cache/*.py** (+35pp to 80%) - Performance optimization

---

## Document Metadata

- **Created**: 2026-03-16
- **Author**: Auto-Claude (subtask-5-3)
- **Phase**: P2 - Establish Testing Baseline
- **Target Release**: v1.1.0
- **Status**: ✅ Complete
- **Next Steps**: Begin implementation of test suites (subtask-5-4)
