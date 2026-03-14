"""Tests for benchmark system."""

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from mascarade.server import app


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def mock_auth():
    """Mock authentication."""
    with patch("mascarade.auth.require_auth") as mock:
        mock.return_value = None
        yield mock


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

    with patch("mascarade.server.BenchmarkStorage", return_value=mock_storage):
        response = client.get("/v1/analytics/benchmarks")

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

    with patch("mascarade.server.BenchmarkStorage", return_value=mock_storage):
        response = client.get(
            "/v1/analytics/benchmarks",
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
        "/v1/analytics/benchmarks",
        params={"order_by": "invalid_column"},
    )

    assert response.status_code == 400
    assert "Invalid order_by parameter" in response.json()["detail"]


def test_api_endpoint_limit_validation(client, mock_auth):
    """Test endpoint validates limit parameter."""
    # Test limit too high
    response = client.get(
        "/v1/analytics/benchmarks",
        params={"limit": 200},
    )
    assert response.status_code == 422  # Validation error

    # Test limit too low
    response = client.get(
        "/v1/analytics/benchmarks",
        params={"limit": 0},
    )
    assert response.status_code == 422  # Validation error
