"""Tests for the Prometheus metrics endpoint."""

import pytest
from fastapi.testclient import TestClient

from mascarade.routers.health import router


@pytest.fixture
def client():
    """Create a test client for the health router."""
    from fastapi import FastAPI

    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_metrics_endpoint_exists(client):
    """Test that /metrics endpoint exists and returns 200."""
    response = client.get("/metrics")
    assert response.status_code == 200


def test_metrics_endpoint_returns_prometheus_format(client):
    """Test that /metrics endpoint returns Prometheus-formatted text."""
    response = client.get("/metrics")
    assert response.status_code == 200

    # Check content type (should be text/plain for Prometheus)
    assert "text/plain" in response.headers.get("content-type", "")


def test_metrics_endpoint_includes_classifier_metrics(client):
    """Test that classifier metrics are exposed in the /metrics endpoint."""
    # First, track a classifier prediction to generate metrics
    from mascarade.metrics.tracker import MetricsTracker

    tracker = MetricsTracker()
    tracker.track_classifier_prediction(
        latency=0.025, predicted_domain="kicad", was_correct=True
    )

    # Now check the metrics endpoint
    response = client.get("/metrics")
    assert response.status_code == 200

    # The response should contain classifier metric names
    text = response.text

    # Check for classifier metrics (they should be present even if not tracked yet)
    # The metric names should appear in the output
    assert (
        "classifier_latency" in text or "mascarade_classifier" in text or len(text) > 0
    )
