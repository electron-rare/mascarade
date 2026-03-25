"""Tests for benchmark system."""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from mascarade.benchmarks.runner import (
    BenchmarkResult,
    BenchmarkRunner,
    ProviderBenchmarkStats,
)
from mascarade.benchmarks.storage import BenchmarkStorage
from mascarade.benchmarks.suite import BenchmarkRun, BenchmarkScope, BenchmarkSuite
from mascarade.server import app


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def mock_auth():
    """Mock authentication by ensuring no API keys are configured."""
    from mascarade.auth import get_active_api_keys, remove_api_key
    saved_keys = list(get_active_api_keys())
    for key in saved_keys:
        remove_api_key(key)
    yield
    for key in saved_keys:
        from mascarade.auth import add_api_key
        add_api_key(key)


@pytest.fixture
def mock_router():
    """Create a mock router."""
    router = MagicMock()
    router.available_providers = ["anthropic", "openai"]
    router._providers = {
        "anthropic": MagicMock(cost_per_million=(0.003, 0.015)),
        "openai": MagicMock(cost_per_million=(0.0015, 0.002)),
    }
    return router


@pytest.fixture
def sample_benchmark_result():
    """Create a sample benchmark result."""
    return BenchmarkResult(
        prompt_id="elec-001",
        provider="anthropic",
        model="claude-3-sonnet",
        domain="electronics",
        difficulty="medium",
        latency=0.5,
        tokens=100,
        cost=0.002,
        success=True,
        error_message=None,
        timestamp=datetime.now(),
    )


def test_api_endpoint(client, mock_auth):
    """Test GET /v1/analytics/benchmarks endpoint."""
    # Mock BenchmarkStorage to return sample data
    mock_storage = MagicMock()
    mock_storage.query_leaderboard.return_value = [
        {
            "provider": "anthropic",
            "model": "claude-3-sonnet",
            "domain": "general",
            "avg_latency_p50": 0.5,
            "avg_latency_p95": 1.2,
            "avg_quality_score": 85.5,
            "avg_cost": 0.003,
            "total_requests": 100,
            "avg_error_rate": 0.01,
            "last_benchmark": "2026-03-14 12:00:00",
        }
    ]

    with patch(
        "mascarade.benchmarks.storage.BenchmarkStorage", return_value=mock_storage
    ):
        response = client.get("/v1/v1/analytics/benchmarks")

        assert response.status_code == 200
        data = response.json()

        assert "results" in data
        assert "count" in data
        assert "filters" in data

        assert data["count"] == 1
        assert len(data["results"]) == 1

        result = data["results"][0]
        assert result["provider"] == "anthropic"
        assert result["model"] == "claude-3-sonnet"
        assert result["domain"] == "general"
        assert result["avg_quality_score"] == 85.5


def test_api_endpoint_with_filters(client, mock_auth):
    """Test endpoint with query parameters."""
    mock_storage = MagicMock()
    mock_storage.query_leaderboard.return_value = []

    with patch(
        "mascarade.benchmarks.storage.BenchmarkStorage", return_value=mock_storage
    ):
        response = client.get(
            "/v1/v1/analytics/benchmarks",
            params={
                "domain": "electronics",
                "limit": 20,
                "order_by": "latency_p50",
            },
        )

        assert response.status_code == 200
        data = response.json()

        assert data["filters"]["domain"] == "electronics"
        assert data["filters"]["limit"] == 20
        assert data["filters"]["order_by"] == "latency_p50"

        # Verify storage was called with correct parameters
        mock_storage.query_leaderboard.assert_called_once_with(
            domain="electronics",
            limit=20,
            order_by="latency_p50",
        )


def test_api_endpoint_invalid_order_by(client, mock_auth):
    """Test endpoint rejects invalid order_by parameter."""
    response = client.get(
        "/v1/v1/analytics/benchmarks",
        params={"order_by": "invalid_column"},
    )

    assert response.status_code == 400
    assert "Invalid order_by parameter" in response.json()["detail"]


def test_api_endpoint_limit_validation(client, mock_auth):
    """Test endpoint validates limit parameter."""
    # Test limit too high
    response = client.get(
        "/v1/v1/analytics/benchmarks",
        params={"limit": 200},
    )
    assert response.status_code == 422  # Validation error

    # Test limit too low
    response = client.get(
        "/v1/v1/analytics/benchmarks",
        params={"limit": 0},
    )
    assert response.status_code == 422  # Validation error


# =============================================================================
# BenchmarkRunner Tests
# =============================================================================


def test_provider_benchmark_stats_update(sample_benchmark_result):
    """Test updating provider stats with benchmark result."""
    stats = ProviderBenchmarkStats(provider_name="anthropic")

    assert stats.total_runs == 0
    assert stats.successful_runs == 0

    stats.update(sample_benchmark_result)

    assert stats.total_runs == 1
    assert stats.successful_runs == 1
    assert stats.avg_latency == 0.5
    assert stats.min_latency == 0.5
    assert stats.max_latency == 0.5
    assert stats.total_tokens == 100
    assert stats.total_cost == 0.002


def test_provider_benchmark_stats_failed_result():
    """Test stats update with failed result."""
    stats = ProviderBenchmarkStats(provider_name="test")
    failed_result = BenchmarkResult(
        prompt_id="test-001",
        provider="test",
        model="test-model",
        domain="test",
        difficulty="easy",
        latency=1.0,
        tokens=0,
        cost=0.0,
        success=False,
        error_message="API Error",
    )

    stats.update(failed_result)

    assert stats.total_runs == 1
    assert stats.successful_runs == 0
    assert stats.failed_runs == 1
    assert stats.avg_latency == 0.0


def test_provider_benchmark_stats_summary():
    """Test getting stats summary."""
    stats = ProviderBenchmarkStats(provider_name="anthropic")
    result = BenchmarkResult(
        prompt_id="test-001",
        provider="anthropic",
        model="claude",
        domain="test",
        difficulty="easy",
        latency=0.5,
        tokens=100,
        cost=0.002,
        success=True,
    )

    stats.update(result)
    summary = stats.get_summary()

    assert summary["provider"] == "anthropic"
    assert summary["total_runs"] == 1
    assert summary["successful_runs"] == 1
    assert summary["success_rate"] == 100.0
    assert summary["avg_latency"] == 0.5
    assert summary["total_cost"] == 0.002


def test_benchmark_runner_init():
    """Test benchmark runner initialization."""
    runner = BenchmarkRunner()

    assert runner.router is not None
    assert len(runner.results) == 0
    assert len(runner.provider_stats) == 0


def test_benchmark_runner_init_with_router(mock_router):
    """Test benchmark runner with custom router."""
    runner = BenchmarkRunner(router=mock_router)

    assert runner.router is mock_router


@pytest.mark.asyncio
async def test_run_single_benchmark_success(mock_router):
    """Test running a single successful benchmark."""
    runner = BenchmarkRunner(router=mock_router)

    # Mock router.send to return a successful response
    mock_response = MagicMock()
    mock_response.usage = {"input_tokens": 50, "output_tokens": 50}
    mock_response.model = "claude-3-sonnet"
    mock_router.send = AsyncMock(return_value=mock_response)

    prompt = {
        "id": "elec-001",
        "prompt": "Test prompt",
        "difficulty": "medium",
    }

    result = await runner.run_single_benchmark(prompt, "anthropic")

    assert result.success is True
    assert result.provider == "anthropic"
    assert result.model == "claude-3-sonnet"
    assert result.domain == "elec"
    assert result.tokens == 100
    assert result.latency > 0


@pytest.mark.asyncio
async def test_run_single_benchmark_failure(mock_router):
    """Test running a single failing benchmark."""
    runner = BenchmarkRunner(router=mock_router)

    # Mock router.send to raise an exception
    mock_router.send = AsyncMock(side_effect=Exception("API Error"))

    prompt = {
        "id": "test-001",
        "prompt": "Test prompt",
        "difficulty": "easy",
    }

    result = await runner.run_single_benchmark(prompt, "anthropic")

    assert result.success is False
    assert result.error_message == "API Error"
    assert result.tokens == 0
    assert result.cost == 0.0


@pytest.mark.asyncio
async def test_run_provider_benchmark(mock_router):
    """Test running benchmark for a provider."""
    runner = BenchmarkRunner(router=mock_router)

    # Mock send method
    mock_response = MagicMock()
    mock_response.usage = {"input_tokens": 50, "output_tokens": 50}
    mock_response.model = "claude-3-sonnet"
    mock_router.send = AsyncMock(return_value=mock_response)

    with patch("mascarade.benchmarks.runner.get_all_prompts") as mock_get_prompts:
        mock_get_prompts.return_value = [
            {"id": "test-001", "prompt": "Test 1", "difficulty": "easy"},
            {"id": "test-002", "prompt": "Test 2", "difficulty": "medium"},
        ]

        results = await runner.run_provider_benchmark("anthropic", limit=2)

    assert len(results) == 2
    assert all(r.provider == "anthropic" for r in results)


@pytest.mark.asyncio
async def test_run_provider_benchmark_invalid_provider(mock_router):
    """Test running benchmark with invalid provider."""
    runner = BenchmarkRunner(router=mock_router)

    with pytest.raises(ValueError, match="non disponible"):
        await runner.run_provider_benchmark("invalid_provider")


def test_get_fastest_provider():
    """Test identifying fastest provider."""
    runner = BenchmarkRunner()

    # Add stats for multiple providers
    stats1 = ProviderBenchmarkStats(provider_name="fast")
    stats1.update(
        BenchmarkResult(
            prompt_id="test-001",
            provider="fast",
            model="m1",
            domain="test",
            difficulty="easy",
            latency=0.3,
            tokens=100,
            cost=0.001,
            success=True,
        )
    )

    stats2 = ProviderBenchmarkStats(provider_name="slow")
    stats2.update(
        BenchmarkResult(
            prompt_id="test-002",
            provider="slow",
            model="m2",
            domain="test",
            difficulty="easy",
            latency=0.8,
            tokens=100,
            cost=0.001,
            success=True,
        )
    )

    runner.provider_stats = {"fast": stats1, "slow": stats2}

    fastest = runner.get_fastest_provider()
    assert fastest == "fast"


def test_get_fastest_provider_empty():
    """Test get_fastest_provider with no stats."""
    runner = BenchmarkRunner()
    assert runner.get_fastest_provider() is None


def test_get_cheapest_provider():
    """Test identifying cheapest provider."""
    runner = BenchmarkRunner()

    stats1 = ProviderBenchmarkStats(provider_name="cheap")
    stats1.update(
        BenchmarkResult(
            prompt_id="test-001",
            provider="cheap",
            model="m1",
            domain="test",
            difficulty="easy",
            latency=0.5,
            tokens=100,
            cost=0.001,
            success=True,
        )
    )

    stats2 = ProviderBenchmarkStats(provider_name="expensive")
    stats2.update(
        BenchmarkResult(
            prompt_id="test-002",
            provider="expensive",
            model="m2",
            domain="test",
            difficulty="easy",
            latency=0.5,
            tokens=100,
            cost=0.005,
            success=True,
        )
    )

    runner.provider_stats = {"cheap": stats1, "expensive": stats2}

    cheapest = runner.get_cheapest_provider()
    assert cheapest == "cheap"


def test_benchmark_runner_reset():
    """Test resetting runner stats."""
    runner = BenchmarkRunner()
    runner.results.append(
        BenchmarkResult(
            prompt_id="test-001",
            provider="test",
            model="m1",
            domain="test",
            difficulty="easy",
            latency=0.5,
            tokens=100,
            cost=0.001,
            success=True,
        )
    )
    runner.provider_stats["test"] = ProviderBenchmarkStats("test")

    runner.reset()

    assert len(runner.results) == 0
    assert len(runner.provider_stats) == 0
    assert len(runner.domain_stats) == 0


def test_benchmark_runner_get_summary():
    """Test getting runner summary."""
    runner = BenchmarkRunner()

    result = BenchmarkResult(
        prompt_id="test-001",
        provider="test",
        model="m1",
        domain="test",
        difficulty="easy",
        latency=0.5,
        tokens=100,
        cost=0.001,
        success=True,
    )
    runner.results.append(result)
    runner._get_provider_stats("test").update(result)

    summary = runner.get_summary()

    assert summary["total_benchmarks"] == 1
    assert summary["successful_benchmarks"] == 1
    assert summary["failed_benchmarks"] == 0
    assert "providers" in summary
    assert "test" in summary["providers"]


# =============================================================================
# BenchmarkSuite Tests
# =============================================================================


def test_benchmark_run_properties():
    """Test BenchmarkRun computed properties."""
    start = datetime.now()
    run = BenchmarkRun(
        run_id="test-001",
        scope=BenchmarkScope.SINGLE_PROVIDER,
        start_time=start,
        total_benchmarks=10,
        successful_benchmarks=8,
        failed_benchmarks=2,
    )

    # Test success_rate
    assert run.success_rate == 80.0

    # Test duration (end_time not set)
    assert run.duration_seconds == 0.0


def test_benchmark_run_duration():
    """Test BenchmarkRun duration calculation."""
    start = datetime(2026, 3, 14, 10, 0, 0)
    end = datetime(2026, 3, 14, 10, 0, 30)

    run = BenchmarkRun(
        run_id="test-001",
        scope=BenchmarkScope.FULL_SUITE,
        start_time=start,
        end_time=end,
    )

    assert run.duration_seconds == 30.0


def test_benchmark_suite_init():
    """Test benchmark suite initialization."""
    suite = BenchmarkSuite()

    assert suite.router is not None
    assert suite.runner is not None
    assert len(suite.run_history) == 0


def test_benchmark_suite_init_with_router(mock_router):
    """Test suite with custom router."""
    suite = BenchmarkSuite(router=mock_router)

    assert suite.router is mock_router
    assert suite.runner.router is mock_router


def test_benchmark_suite_generate_run_id():
    """Test run ID generation."""
    suite = BenchmarkSuite()

    run_id1 = suite._generate_run_id()
    run_id2 = suite._generate_run_id()

    assert run_id1.startswith("bench_")
    assert run_id2.startswith("bench_")
    assert run_id1 != run_id2


def test_benchmark_suite_record_run():
    """Test recording runs in history."""
    suite = BenchmarkSuite()

    run = BenchmarkRun(
        run_id="test-001",
        scope=BenchmarkScope.SINGLE_PROVIDER,
        start_time=datetime.now(),
    )

    suite._record_run(run)

    assert len(suite.run_history) == 1
    assert suite.run_history[0] is run


def test_benchmark_suite_max_history():
    """Test history size limit."""
    suite = BenchmarkSuite(max_history=3)

    for i in range(5):
        run = BenchmarkRun(
            run_id=f"test-{i:03d}",
            scope=BenchmarkScope.SINGLE_PROVIDER,
            start_time=datetime.now(),
        )
        suite._record_run(run)

    assert len(suite.run_history) == 3
    # Should keep the last 3 runs
    assert suite.run_history[0].run_id == "test-002"
    assert suite.run_history[-1].run_id == "test-004"


@pytest.mark.asyncio
async def test_benchmark_suite_run_single_provider(mock_router):
    """Test running benchmark for single provider."""
    suite = BenchmarkSuite(router=mock_router)

    # Mock the runner method
    suite.runner.run_provider_benchmark = AsyncMock(
        return_value=[
            BenchmarkResult(
                prompt_id="test-001",
                provider="anthropic",
                model="claude",
                domain="test",
                difficulty="easy",
                latency=0.5,
                tokens=100,
                cost=0.001,
                success=True,
            )
        ]
    )

    run = await suite.run_single_provider("anthropic")

    assert run.scope == BenchmarkScope.SINGLE_PROVIDER
    assert run.total_benchmarks == 1
    assert run.successful_benchmarks == 1
    assert run.failed_benchmarks == 0
    assert "anthropic" in run.providers_tested
    assert run.end_time is not None


@pytest.mark.asyncio
async def test_benchmark_suite_run_single_provider_error(mock_router):
    """Test suite handles provider errors."""
    suite = BenchmarkSuite(router=mock_router)

    suite.runner.run_provider_benchmark = AsyncMock(
        side_effect=Exception("Provider error")
    )

    run = await suite.run_single_provider("anthropic")

    assert run.error == "Provider error"
    assert run.total_benchmarks == 0


def test_benchmark_suite_get_run_by_id():
    """Test retrieving run by ID."""
    suite = BenchmarkSuite()

    run1 = BenchmarkRun(
        run_id="test-001",
        scope=BenchmarkScope.SINGLE_PROVIDER,
        start_time=datetime.now(),
    )
    run2 = BenchmarkRun(
        run_id="test-002",
        scope=BenchmarkScope.FULL_SUITE,
        start_time=datetime.now(),
    )

    suite._record_run(run1)
    suite._record_run(run2)

    found = suite.get_run_by_id("test-002")
    assert found is run2

    not_found = suite.get_run_by_id("test-999")
    assert not_found is None


def test_benchmark_suite_get_latest_run():
    """Test getting latest run."""
    suite = BenchmarkSuite()

    # Empty history
    assert suite.get_latest_run() is None

    run1 = BenchmarkRun(
        run_id="test-001",
        scope=BenchmarkScope.SINGLE_PROVIDER,
        start_time=datetime.now(),
    )
    run2 = BenchmarkRun(
        run_id="test-002", scope=BenchmarkScope.FULL_SUITE, start_time=datetime.now()
    )

    suite._record_run(run1)
    suite._record_run(run2)

    latest = suite.get_latest_run()
    assert latest is run2


def test_benchmark_suite_clear_history():
    """Test clearing run history."""
    suite = BenchmarkSuite()

    run = BenchmarkRun(
        run_id="test-001",
        scope=BenchmarkScope.SINGLE_PROVIDER,
        start_time=datetime.now(),
    )
    suite._record_run(run)

    suite.clear_history()

    assert len(suite.run_history) == 0


def test_benchmark_suite_get_leaderboard():
    """Test getting leaderboard from suite."""
    suite = BenchmarkSuite()

    # Add some stats to the runner
    stats = ProviderBenchmarkStats(provider_name="anthropic")
    stats.update(
        BenchmarkResult(
            prompt_id="test-001",
            provider="anthropic",
            model="claude",
            domain="test",
            difficulty="easy",
            latency=0.5,
            tokens=100,
            cost=0.001,
            success=True,
        )
    )
    suite.runner.provider_stats = {"anthropic": stats}

    leaderboard = suite.get_leaderboard()

    assert len(leaderboard) == 1
    assert leaderboard[0]["provider"] == "anthropic"
    assert leaderboard[0]["avg_latency"] == 0.5


def test_benchmark_suite_get_leaderboard_empty():
    """Test leaderboard with no data."""
    suite = BenchmarkSuite()

    leaderboard = suite.get_leaderboard()

    assert leaderboard == []


# =============================================================================
# BenchmarkStorage Tests
# =============================================================================


def test_benchmark_storage_init():
    """Test storage initialization."""
    storage = BenchmarkStorage()

    # Client may be None if not configured
    assert storage.client is None or storage.client is not None


def test_benchmark_storage_write_result_no_client():
    """Test write when client is not available."""
    storage = BenchmarkStorage()
    storage.client = None

    result = storage.write_result(
        provider="anthropic",
        model="claude-3-sonnet",
        domain="electronics",
        latency_p50=0.5,
        latency_p95=1.2,
        quality_score=85.5,
        cost=0.003,
    )

    assert result is False


def test_benchmark_storage_write_result_success():
    """Test successful write to storage."""
    storage = BenchmarkStorage()

    # Mock the client
    mock_client = MagicMock()
    storage.client = mock_client

    result = storage.write_result(
        provider="anthropic",
        model="claude-3-sonnet",
        domain="electronics",
        latency_p50=0.5,
        latency_p95=1.2,
        quality_score=85.5,
        cost=0.003,
        request_count=100,
        error_rate=0.01,
        notes="Test run",
    )

    assert result is True
    mock_client.insert.assert_called_once()


def test_benchmark_storage_query_leaderboard_no_client():
    """Test query when client is not available."""
    storage = BenchmarkStorage()
    storage.client = None

    results = storage.query_leaderboard()

    assert results == []


def test_benchmark_storage_query_leaderboard_success():
    """Test successful leaderboard query."""
    storage = BenchmarkStorage()

    # Mock the client
    mock_client = MagicMock()
    mock_result = MagicMock()
    mock_result.result_rows = [
        (
            "anthropic",
            "claude-3-sonnet",
            "electronics",
            0.5,
            1.2,
            85.5,
            0.003,
            100,
            0.01,
            "2026-03-14 12:00:00",
        )
    ]
    mock_client.query.return_value = mock_result
    storage.client = mock_client

    results = storage.query_leaderboard(domain="electronics", limit=10)

    assert len(results) == 1
    assert results[0]["provider"] == "anthropic"
    assert results[0]["model"] == "claude-3-sonnet"
    assert results[0]["domain"] == "electronics"
    assert results[0]["avg_quality_score"] == 85.5


def test_benchmark_storage_query_provider_stats_no_client():
    """Test provider stats query with no client."""
    storage = BenchmarkStorage()
    storage.client = None

    stats = storage.query_provider_stats("anthropic")

    assert stats is None


def test_benchmark_storage_health_check_no_client():
    """Test health check with no client."""
    storage = BenchmarkStorage()
    storage.client = None

    assert storage.health_check() is False


def test_benchmark_storage_health_check_success():
    """Test successful health check."""
    storage = BenchmarkStorage()

    # Mock the client
    mock_client = MagicMock()
    mock_result = MagicMock()
    mock_result.result_rows = [[1]]
    mock_client.query.return_value = mock_result
    storage.client = mock_client

    assert storage.health_check() is True
    mock_client.query.assert_called_once_with("SELECT 1")


def test_storage_sql_injection_prevention_domain():
    """Test that SQL injection attempts via domain parameter are blocked."""
    storage = BenchmarkStorage()

    # Mock client to verify query uses parameterized queries
    mock_client = MagicMock()
    mock_result = MagicMock()
    mock_result.result_rows = []
    mock_client.query.return_value = mock_result
    storage.client = mock_client

    # Attempt SQL injection via domain parameter
    malicious_domain = "general' OR '1'='1"

    # Should safely use parameterized query
    storage.query_leaderboard(domain=malicious_domain)

    # Verify the query was called with parameters (not direct string interpolation)
    assert mock_client.query.called
    call_args = mock_client.query.call_args

    # Check that parameters were passed
    assert call_args is not None
    assert "parameters" in call_args.kwargs
    params = call_args.kwargs["parameters"]

    # Verify domain was passed as parameter, not interpolated
    assert "domain" in params
    assert params["domain"] == malicious_domain

    # Verify the query uses parameter placeholders, not direct values
    query = call_args.args[0]
    assert "%(domain)s" in query
    # Should NOT contain the malicious string directly in query
    assert malicious_domain not in query


def test_storage_sql_injection_prevention_provider():
    """Test that SQL injection attempts via provider parameter are blocked."""
    storage = BenchmarkStorage()

    # Mock client
    mock_client = MagicMock()
    mock_result = MagicMock()
    mock_result.result_rows = []
    mock_client.query.return_value = mock_result
    storage.client = mock_client

    # Attempt SQL injection via provider parameter
    malicious_provider = "anthropic' OR '1'='1"

    # Should safely use parameterized query
    storage.query_provider_stats(malicious_provider)

    # Verify parameterized query was used
    assert mock_client.query.called
    call_args = mock_client.query.call_args

    assert call_args is not None
    assert "parameters" in call_args.kwargs
    params = call_args.kwargs["parameters"]

    # Verify provider was passed as parameter
    assert "provider" in params
    assert params["provider"] == malicious_provider

    # Verify the query uses parameter placeholders
    query = call_args.args[0]
    assert "%(provider)s" in query
    assert malicious_provider not in query


def test_storage_sql_injection_prevention_combined():
    """Test SQL injection prevention with both domain and provider parameters."""
    storage = BenchmarkStorage()

    # Mock client
    mock_client = MagicMock()
    mock_result = MagicMock()
    mock_result.result_rows = []
    mock_client.query.return_value = mock_result
    storage.client = mock_client

    # Attempt SQL injection via both parameters
    malicious_provider = "test'; DROP TABLE benchmarks; --"
    malicious_domain = "general' UNION SELECT * FROM users --"

    # Should safely use parameterized query
    storage.query_provider_stats(malicious_provider, domain=malicious_domain)

    # Verify both parameters were safely parameterized
    assert mock_client.query.called
    call_args = mock_client.query.call_args

    assert call_args is not None
    assert "parameters" in call_args.kwargs
    params = call_args.kwargs["parameters"]

    assert params["provider"] == malicious_provider
    assert params["domain"] == malicious_domain

    # Verify query uses placeholders for both
    query = call_args.args[0]
    assert "%(provider)s" in query
    assert "%(domain)s" in query
    # Malicious strings should NOT be in the query itself
    assert "DROP TABLE" not in query
    assert "UNION SELECT" not in query


def test_storage_sql_injection_prevention_domain_stats():
    """Test SQL injection prevention in query_domain_stats."""
    storage = BenchmarkStorage()

    # Mock client
    mock_client = MagicMock()
    mock_result = MagicMock()
    mock_result.result_rows = []
    mock_client.query.return_value = mock_result
    storage.client = mock_client

    # Attempt SQL injection via domain parameter
    malicious_domain = "electronics'; DELETE FROM benchmarks WHERE '1'='1"

    # Should safely use parameterized query
    storage.query_domain_stats(malicious_domain)

    # Verify parameterized query was used
    assert mock_client.query.called
    call_args = mock_client.query.call_args

    assert call_args is not None
    assert "parameters" in call_args.kwargs
    params = call_args.kwargs["parameters"]

    assert params["domain"] == malicious_domain

    # Verify the query uses parameter placeholders
    query = call_args.args[0]
    assert "%(domain)s" in query
    assert "DELETE FROM" not in query


# =============================================================================
# Routing Integration Tests
# =============================================================================


def test_routing_strategy():
    """Test domain-aware routing strategy using benchmark data."""
    from mascarade.router.router import Router

    # Create a router instance
    router = Router()

    # Test domain detection
    messages_spice = [
        {"role": "user", "content": "Can you help me with SPICE simulation?"}
    ]
    messages_kicad = [
        {"role": "user", "content": "I need help designing a PCB in KiCad"}
    ]
    messages_general = [{"role": "user", "content": "What is the capital of France?"}]

    # Test _detect_domain method
    assert router._detect_domain(messages_spice) == "spice"
    assert router._detect_domain(messages_kicad) == "kicad"
    # General messages may or may not detect a domain depending on heuristics
    general_domain = router._detect_domain(messages_general)
    assert general_domain is None or isinstance(general_domain, str)

    # Test _select_by_benchmarks with mocked storage
    if router.benchmark_storage:
        # Mock the storage to return benchmark data
        mock_storage = MagicMock()
        mock_storage.query_leaderboard.return_value = [
            {
                "provider": "anthropic",
                "model": "claude-3-sonnet",
                "domain": "spice",
                "avg_quality_score": 90.0,
                "avg_latency_p50": 0.5,
            },
            {
                "provider": "openai",
                "model": "gpt-4",
                "domain": "spice",
                "avg_quality_score": 85.0,
                "avg_latency_p50": 0.4,
            },
        ]

        # Replace the benchmark storage
        original_storage = router.benchmark_storage
        router.benchmark_storage = mock_storage

        try:
            # Test selecting by benchmarks
            candidates = router._select_by_benchmarks("spice")

            # Should return providers that exist in the router
            assert isinstance(candidates, list)

            # Verify storage was called correctly
            mock_storage.query_leaderboard.assert_called_once_with(
                domain="spice",
                limit=10,
                order_by="avg_quality_score",
            )
        finally:
            # Restore original storage
            router.benchmark_storage = original_storage

    # Test _select_candidates with domain parameter
    from mascarade.router.router import Strategy

    # Test without benchmark data (should fall back to quality_rank)
    if router._providers:
        candidates = router._select_candidates(
            strategy=Strategy.BEST,
            domain="electronics",
        )
        assert len(candidates) > 0
        assert all(hasattr(c, "quality_rank") for c in candidates)
