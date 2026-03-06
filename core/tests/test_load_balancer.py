"""Tests pour le système de load balancing."""

from mascarade.load_balancer.balancer import LoadBalancer


def test_register_provider():
    lb = LoadBalancer()
    lb.register_provider("claude")
    lb.register_provider("openai")
    assert "claude" in lb.providers
    assert "openai" in lb.providers
    assert lb.providers["claude"].current_load == 0


def test_round_robin_selection():
    lb = LoadBalancer()
    lb.register_provider("a")
    lb.register_provider("b")
    # Both have last_used=0, so order depends on min()
    first = lb.select_provider(["a", "b"], "round_robin")
    assert first in ("a", "b")
    lb.request_started(first)
    # Now first has a later last_used, so second should be picked
    second = lb.select_provider(["a", "b"], "round_robin")
    assert second != first


def test_least_connections():
    lb = LoadBalancer()
    lb.register_provider("a")
    lb.register_provider("b")
    lb.request_started("a")
    lb.request_started("a")
    lb.request_started("b")
    # a has load=2, b has load=1
    chosen = lb.select_provider(["a", "b"], "least_connections")
    assert chosen == "b"


def test_fastest_response():
    lb = LoadBalancer()
    lb.register_provider("slow")
    lb.register_provider("fast")
    lb.request_started("slow")
    lb.request_completed("slow", response_time=2.0, success=True)
    lb.request_started("fast")
    lb.request_completed("fast", response_time=0.1, success=True)
    chosen = lb.select_provider(["slow", "fast"], "fastest_response")
    assert chosen == "fast"


def test_least_errors():
    lb = LoadBalancer()
    lb.register_provider("good")
    lb.register_provider("bad")
    for _ in range(5):
        lb.request_started("good")
        lb.request_completed("good", response_time=0.1, success=True)
    for _ in range(5):
        lb.request_started("bad")
        lb.request_completed("bad", response_time=0.1, success=False)
    chosen = lb.select_provider(["good", "bad"], "least_errors")
    assert chosen == "good"


def test_request_lifecycle():
    lb = LoadBalancer()
    lb.register_provider("p")
    assert lb.providers["p"].current_load == 0
    lb.request_started("p")
    assert lb.providers["p"].current_load == 1
    assert lb.providers["p"].pending_requests == 1
    lb.request_completed("p", response_time=0.5, success=True)
    assert lb.providers["p"].current_load == 0
    assert lb.providers["p"].pending_requests == 0
    assert len(lb.providers["p"].response_times) == 1


def test_error_count():
    lb = LoadBalancer()
    lb.register_provider("p")
    lb.request_started("p")
    lb.request_completed("p", response_time=0.5, success=False)
    assert lb.providers["p"].error_count == 1
    assert lb.providers["p"].error_rate() > 0


def test_get_load_stats():
    lb = LoadBalancer()
    lb.register_provider("a")
    lb.request_started("a")
    stats = lb.get_load_stats()
    assert stats["total_requests"] == 1
    assert "a" in stats["providers"]


def test_reset_stats():
    lb = LoadBalancer()
    lb.register_provider("a")
    lb.request_started("a")
    lb.request_completed("a", response_time=0.5, success=True)
    lb.reset_stats()
    assert lb.providers["a"].total_requests == 0
    assert lb.providers["a"].error_count == 0


def test_unknown_provider_ignored():
    lb = LoadBalancer()
    lb.register_provider("a")
    # These should not raise
    lb.request_started("unknown")
    lb.request_completed("unknown", response_time=0.1, success=True)


def test_empty_provider_list():
    lb = LoadBalancer()
    result = lb.select_provider([], "round_robin")
    assert result is None


def test_weighted_random():
    lb = LoadBalancer()
    lb.register_provider("a")
    lb.register_provider("b")
    # Should not raise even with no history
    chosen = lb.select_provider(["a", "b"], "weighted")
    assert chosen in ("a", "b")
