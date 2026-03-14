# Health Monitoring & Circuit Breaker - Integration Testing

This document describes how to run the end-to-end integration tests for the health monitoring and circuit breaker feature.

## Test Files

### 1. Unit/Integration Tests (`core/tests/test_health_integration.py`)

Comprehensive pytest test suite that verifies:

- **Health Score Calculation**: Tests that health scores are computed correctly based on latency and error rates
- **Circuit Breaker Opens on Failures**: Verifies circuit opens after threshold failures (3 failures in 60s)
- **Circuit Breaker Recovery**: Tests CLOSED → OPEN → HALF_OPEN → CLOSED transitions
- **Health-Aware Routing**: Verifies degraded providers are excluded from routing
- **Multi-Provider Health Ranking**: Tests that providers are ranked by health score
- **Health Metrics Exposure**: Verifies metrics are properly exposed through API
- **Per-Provider Isolation**: Tests that circuit breakers are isolated per provider
- **End-to-End Workflow**: Complete simulation of degradation, failover, and recovery

### 2. E2E Verification Script (`scripts/verify_health_monitoring.py`)

Manual verification script for running services:

- Checks `/health/providers` endpoint structure
- Verifies `/api/ops/summary` includes provider health
- Sends test requests to build metrics
- Validates circuit breaker metrics exposure
- Checks Grafana dashboard accessibility (optional)

## Running the Tests

### Prerequisites

1. **Set up Python environment:**
   ```bash
   cd core
   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

2. **For E2E tests, start all services:**
   ```bash
   # Terminal 1: Core service
   cd core
   source .venv/bin/activate
   uvicorn mascarade.server:app --reload --host 0.0.0.0 --port 8100

   # Terminal 2: API service
   cd api
   npm install
   npm run dev

   # Terminal 3: Grafana (optional)
   docker compose up grafana
   ```

### Running Unit/Integration Tests

```bash
cd core
source .venv/bin/activate
python -m pytest tests/test_health_integration.py -v
```

**Individual test functions:**

```bash
# Test health score calculation
pytest tests/test_health_integration.py::test_health_score_calculation -v

# Test circuit breaker opens on failures
pytest tests/test_health_integration.py::test_circuit_breaker_opens_on_failures -v

# Test circuit breaker recovery
pytest tests/test_health_integration.py::test_circuit_breaker_recovery -v

# Test health-aware routing
pytest tests/test_health_integration.py::test_health_aware_routing -v

# Run complete end-to-end workflow
pytest tests/test_health_integration.py::test_end_to_end_health_workflow -v
```

### Running E2E Verification Script

With all services running:

```bash
python scripts/verify_health_monitoring.py
```

**What it verifies:**

1. ✓ Core health endpoint (`GET /health/providers`)
2. ✓ Sends 10 test requests to build metrics
3. ✓ Health metrics populated with data
4. ✓ Circuit breaker metrics exposed
5. ✓ API ops summary includes provider health
6. ✓ Grafana dashboard accessible (optional)
7. ✓ Health-aware routing (manual check)

## Manual Verification Steps

### 1. Verify Health Monitoring

```bash
# Check provider health
curl http://localhost:8100/health/providers | jq

# Expected output:
{
  "openai": {
    "health_score": 0.95,
    "circuit_state": "closed",
    "latency_p50": 0.234,
    "latency_p95": 0.567,
    "latency_p99": 0.789,
    "error_rate": 0.02,
    "availability": 0.98,
    "total_requests": 150
  }
}
```

### 2. Verify Circuit Breaker

```bash
# Check circuit breaker stats
curl http://localhost:8100/metrics | jq .circuit_breaker

# Expected output:
{
  "providers": {
    "openai": {
      "state": "closed",
      "failure_count": 0,
      "failure_threshold": 5,
      "last_failure_time": null,
      "half_open_calls": 0
    }
  }
}
```

### 3. Verify API Ops Summary

```bash
# Check ops summary
curl http://localhost:3000/api/ops/summary | jq .provider_health

# Expected output:
{
  "openai": {
    "health_score": 0.95,
    "circuit_state": "closed",
    ...
  }
}
```

### 4. Verify Grafana Dashboard

1. Open http://localhost:3001/d/mascarade-ops-overview
2. Look for "Provider Health Score" panel
3. Verify health scores are displayed per provider
4. Check color-coded thresholds:
   - Green: health score ≥ 80%
   - Yellow: health score 50-80%
   - Red: health score < 50%

## Simulating Provider Failures

To test circuit breaker behavior manually:

```python
# Create a test script: test_circuit_breaker.py
import asyncio
import httpx

async def test_failures():
    client = httpx.AsyncClient()

    # Send requests that will fail (invalid provider)
    for i in range(5):
        try:
            resp = await client.post(
                "http://localhost:8100/router/send",
                json={
                    "messages": [{"role": "user", "content": "test"}],
                    "strategy": "specific",
                    "provider": "nonexistent"
                }
            )
        except:
            pass

    # Check circuit state
    metrics = await client.get("http://localhost:8100/metrics")
    print(metrics.json()["circuit_breaker"])

asyncio.run(test_failures())
```

## Expected Test Results

### All Tests Should Pass

```
tests/test_health_integration.py::test_health_score_calculation PASSED
tests/test_health_integration.py::test_circuit_breaker_opens_on_failures PASSED
tests/test_health_integration.py::test_circuit_breaker_recovery PASSED
tests/test_health_integration.py::test_health_aware_routing PASSED
tests/test_health_integration.py::test_multiple_providers_health_ranking PASSED
tests/test_health_integration.py::test_health_metrics_exposure PASSED
tests/test_health_integration.py::test_circuit_breaker_per_provider_isolation PASSED
tests/test_health_integration.py::test_end_to_end_health_workflow PASSED

========================== 8 passed in 15.23s ===========================
```

### E2E Verification Should Pass

```
============================================================
VERIFICATION SUMMARY
============================================================
✓ PASS   Core Health Endpoint
✓ PASS   Test Requests
✓ PASS   Health Metrics with Data
✓ PASS   Circuit Breaker Metrics
✓ PASS   API Ops Summary
✓ PASS   Grafana Dashboard
✓ PASS   Health-Aware Routing
------------------------------------------------------------
Total: 7 passed, 0 failed
============================================================
```

## Troubleshooting

### Tests Fail with ImportError

```bash
# Ensure dependencies are installed
cd core
pip install -r requirements.txt
```

### E2E Script Fails with Connection Error

```bash
# Verify services are running
curl http://localhost:8100/health  # Core service
curl http://localhost:3000/api/health  # API service

# Check docker compose status
docker compose ps
```

### Circuit Breaker Doesn't Open

- Check failure threshold configuration (default: 5 failures)
- Verify failures are within the window_size (default: 120s)
- Old failures outside window are automatically cleaned

### Health Scores Are All 1.0

- Need at least 5 requests per provider for reliable scoring
- Send more test requests to build metrics
- Check that providers are actually responding

## Additional Resources

- **Spec**: `./.auto-claude/specs/007-provider-health-monitoring-smart-fallback/spec.md`
- **Implementation Plan**: `./.auto-claude/specs/007-provider-health-monitoring-smart-fallback/implementation_plan.json`
- **Build Progress**: `./.auto-claude/specs/007-provider-health-monitoring-smart-fallback/build-progress.txt`
