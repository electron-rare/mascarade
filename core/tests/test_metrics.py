"""Tests pour le système de métriques."""

from mascarade.metrics.tracker import ClassifierMetrics, MetricsTracker, ProviderMetrics


def test_provider_metrics_update_success():
    m = ProviderMetrics(provider_name="test")
    m.update(tokens=100, cost=0.01, response_time=0.5, success=True)
    assert m.total_requests == 1
    assert m.total_tokens == 100
    assert m.total_cost == 0.01
    assert m.avg_response_time == 0.5
    assert m.error_rate == 0.0
    assert m.last_used is not None


def test_provider_metrics_error_rate():
    m = ProviderMetrics(provider_name="test")
    # 1 success, 1 failure → 50% error rate
    m.update(tokens=100, cost=0.01, response_time=0.5, success=True)
    m.update(tokens=100, cost=0.01, response_time=0.5, success=False)
    assert abs(m.error_rate - 0.5) < 0.01

    # 1 more success → ~33% error rate
    m.update(tokens=100, cost=0.01, response_time=0.5, success=True)
    assert abs(m.error_rate - 1.0 / 3.0) < 0.01


def test_error_rate_decreases_on_success():
    m = ProviderMetrics(provider_name="test")
    m.update(tokens=10, cost=0.0, response_time=0.1, success=False)
    assert m.error_rate == 1.0
    m.update(tokens=10, cost=0.0, response_time=0.1, success=True)
    assert m.error_rate == 0.5
    m.update(tokens=10, cost=0.0, response_time=0.1, success=True)
    assert abs(m.error_rate - 1.0 / 3.0) < 0.01


def test_avg_response_time():
    m = ProviderMetrics(provider_name="test")
    m.update(tokens=10, cost=0.0, response_time=1.0, success=True)
    m.update(tokens=10, cost=0.0, response_time=3.0, success=True)
    assert abs(m.avg_response_time - 2.0) < 0.01


def test_tracker_track_request():
    t = MetricsTracker()
    t.track_request("claude", tokens=100, cost=0.01, response_time=0.5, success=True)
    assert "claude" in t.providers
    assert t.providers["claude"].total_requests == 1
    assert len(t.request_history) == 1


def test_tracker_history_bounded():
    t = MetricsTracker()
    for _ in range(1500):
        t.track_request("p", tokens=1, cost=0.0, response_time=0.01, success=True)
    # deque(maxlen=1000) should cap at 1000
    assert len(t.request_history) == 1000


def test_tracker_summary():
    t = MetricsTracker()
    t.track_request("a", tokens=50, cost=0.005, response_time=0.3, success=True)
    t.track_request("b", tokens=100, cost=0.01, response_time=0.5, success=True)
    summary = t.get_summary()
    assert summary["total_requests"] == 2
    assert "a" in summary["providers"]
    assert "b" in summary["providers"]


def test_tracker_reset():
    t = MetricsTracker()
    t.track_request("a", tokens=50, cost=0.005, response_time=0.3, success=True)
    t.reset()
    assert len(t.providers) == 0
    assert len(t.request_history) == 0


def test_best_performer():
    t = MetricsTracker()
    # Need >= 5 requests per provider to qualify
    for _ in range(6):
        t.track_request("fast", tokens=10, cost=0.0, response_time=0.1, success=True)
    for _ in range(6):
        t.track_request("slow", tokens=10, cost=0.0, response_time=2.0, success=True)
    summary = t.get_summary()
    assert summary["best_performer"] == "fast"


def test_classifier_metrics_update():
    m = ClassifierMetrics()
    m.update(latency=0.05, predicted_domain="kicad", was_correct=True)
    assert m.total_predictions == 1
    assert m.correct_predictions == 1
    assert m.accuracy == 1.0
    assert m.avg_latency == 0.05
    assert m.predictions_by_domain["kicad"] == 1
    assert m.last_used is not None


def test_classifier_metrics_accuracy():
    m = ClassifierMetrics()
    # 2 correct, 1 incorrect → 66.7% accuracy
    m.update(latency=0.01, predicted_domain="kicad", was_correct=True)
    m.update(latency=0.02, predicted_domain="spice", was_correct=True)
    m.update(latency=0.03, predicted_domain="freecad", was_correct=False)
    assert m.total_predictions == 3
    assert m.correct_predictions == 2
    assert abs(m.accuracy - 2.0 / 3.0) < 0.01


def test_classifier_metrics_latency():
    m = ClassifierMetrics()
    m.update(latency=0.01, predicted_domain="kicad")
    m.update(latency=0.03, predicted_domain="spice")
    assert abs(m.avg_latency - 0.02) < 0.001


def test_classifier_metrics_domain_counts():
    m = ClassifierMetrics()
    m.update(latency=0.01, predicted_domain="kicad")
    m.update(latency=0.01, predicted_domain="kicad")
    m.update(latency=0.01, predicted_domain="spice")
    assert m.predictions_by_domain["kicad"] == 2
    assert m.predictions_by_domain["spice"] == 1


def test_tracker_classifier_prediction():
    t = MetricsTracker()
    t.track_classifier_prediction(
        latency=0.05, predicted_domain="kicad", was_correct=True
    )
    assert t.classifier.total_predictions == 1
    stats = t.get_classifier_stats()
    assert stats["total_predictions"] == 1
    assert stats["accuracy"] == 1.0
    assert stats["avg_latency_ms"] == 50.0


def test_tracker_classifier_in_summary():
    t = MetricsTracker()
    t.track_classifier_prediction(latency=0.01, predicted_domain="kicad")
    summary = t.get_summary()
    assert "classifier" in summary
    assert summary["classifier"]["total_predictions"] == 1


def test_tracker_reset_includes_classifier():
    t = MetricsTracker()
    t.track_classifier_prediction(latency=0.01, predicted_domain="kicad")
    t.reset()
    assert t.classifier.total_predictions == 0
