"""Tests pour le circuit breaker."""

import time

from mascarade.orchestrator.circuit_breaker import CircuitBreaker, CircuitState


def test_initial_state_is_closed():
    cb = CircuitBreaker()
    assert cb.state == CircuitState.CLOSED
    assert cb.failure_count == 0
    assert cb.success_count == 0
    assert cb.can_execute() is True


def test_record_success_in_closed_state_resets_failure_count():
    cb = CircuitBreaker(failure_threshold=3)
    cb.record_failure()
    cb.record_failure()
    assert cb.failure_count == 2

    cb.record_success()
    assert cb.failure_count == 0
    assert cb.state == CircuitState.CLOSED


def test_circuit_opens_after_failure_threshold():
    cb = CircuitBreaker(failure_threshold=3)

    cb.record_failure()
    assert cb.state == CircuitState.CLOSED

    cb.record_failure()
    assert cb.state == CircuitState.CLOSED

    cb.record_failure()
    assert cb.state == CircuitState.OPEN
    assert cb.can_execute() is False


def test_cannot_execute_when_circuit_is_open():
    cb = CircuitBreaker(failure_threshold=2)

    cb.record_failure()
    cb.record_failure()

    assert cb.state == CircuitState.OPEN
    assert cb.can_execute() is False


def test_circuit_transitions_to_half_open_after_timeout():
    cb = CircuitBreaker(failure_threshold=2, timeout=0.1)

    cb.record_failure()
    cb.record_failure()
    assert cb.state == CircuitState.OPEN

    # Wait for timeout
    time.sleep(0.15)

    # Check if we can execute (should transition to HALF_OPEN)
    can_exec = cb.can_execute()
    assert can_exec is True
    assert cb.state == CircuitState.HALF_OPEN


def test_success_in_half_open_accumulates():
    cb = CircuitBreaker(failure_threshold=2, success_threshold=2, timeout=0.1)

    # Open the circuit
    cb.record_failure()
    cb.record_failure()
    assert cb.state == CircuitState.OPEN

    # Wait for timeout and transition to HALF_OPEN
    time.sleep(0.15)
    cb.can_execute()
    assert cb.state == CircuitState.HALF_OPEN

    # Record first success
    cb.record_success()
    assert cb.state == CircuitState.HALF_OPEN
    assert cb.success_count == 1


def test_enough_successes_in_half_open_close_circuit():
    cb = CircuitBreaker(failure_threshold=2, success_threshold=2, timeout=0.1)

    # Open the circuit
    cb.record_failure()
    cb.record_failure()

    # Transition to HALF_OPEN
    time.sleep(0.15)
    cb.can_execute()
    assert cb.state == CircuitState.HALF_OPEN

    # Record enough successes to close
    cb.record_success()
    assert cb.state == CircuitState.HALF_OPEN

    cb.record_success()
    assert cb.state == CircuitState.CLOSED
    assert cb.can_execute() is True


def test_failure_in_half_open_reopens_circuit_immediately():
    cb = CircuitBreaker(failure_threshold=2, timeout=0.1)

    # Open the circuit
    cb.record_failure()
    cb.record_failure()

    # Transition to HALF_OPEN
    time.sleep(0.15)
    cb.can_execute()
    assert cb.state == CircuitState.HALF_OPEN

    # One failure should reopen immediately
    cb.record_failure()
    assert cb.state == CircuitState.OPEN
    assert cb.can_execute() is False


def test_state_change_callback_is_called():
    transitions = []

    def on_change(old_state, new_state):
        transitions.append((old_state, new_state))

    cb = CircuitBreaker(failure_threshold=2, timeout=0.1)
    cb.on_state_change = on_change

    # Trigger CLOSED -> OPEN
    cb.record_failure()
    cb.record_failure()
    assert (CircuitState.CLOSED, CircuitState.OPEN) in transitions

    # Trigger OPEN -> HALF_OPEN
    time.sleep(0.15)
    cb.can_execute()
    assert (CircuitState.OPEN, CircuitState.HALF_OPEN) in transitions

    # Trigger HALF_OPEN -> CLOSED
    cb.record_success()
    cb.record_success()
    assert (CircuitState.HALF_OPEN, CircuitState.CLOSED) in transitions


def test_state_change_callback_not_called_for_same_state():
    transitions = []

    def on_change(old_state, new_state):
        transitions.append((old_state, new_state))

    cb = CircuitBreaker(failure_threshold=3)
    cb.on_state_change = on_change

    # Multiple failures in CLOSED (not at threshold yet)
    cb.record_failure()
    cb.record_failure()

    # No transition should have occurred
    assert len(transitions) == 0


def test_get_stats_returns_correct_data():
    cb = CircuitBreaker(failure_threshold=5, success_threshold=3, timeout=60.0)

    cb.record_failure()
    cb.record_failure()

    stats = cb.get_stats()

    assert stats["state"] == CircuitState.CLOSED
    assert stats["failure_count"] == 2
    assert stats["success_count"] == 0
    assert stats["failure_threshold"] == 5
    assert stats["success_threshold"] == 3
    assert stats["last_failure_time"] is not None
    assert "time_since_last_change" in stats


def test_reset_returns_to_closed_state():
    cb = CircuitBreaker(failure_threshold=2)

    # Open the circuit
    cb.record_failure()
    cb.record_failure()
    assert cb.state == CircuitState.OPEN
    assert cb.failure_count == 2

    # Reset
    cb.reset()

    assert cb.state == CircuitState.CLOSED
    assert cb.failure_count == 0
    assert cb.success_count == 0
    assert cb.last_failure_time is None
    assert cb.can_execute() is True


def test_custom_thresholds():
    cb = CircuitBreaker(failure_threshold=10, success_threshold=5)

    # Should not open until 10 failures
    for _ in range(9):
        cb.record_failure()
    assert cb.state == CircuitState.CLOSED

    cb.record_failure()
    assert cb.state == CircuitState.OPEN


def test_custom_timeout():
    cb = CircuitBreaker(failure_threshold=1, timeout=0.2)

    cb.record_failure()
    assert cb.state == CircuitState.OPEN

    # Before timeout
    time.sleep(0.1)
    assert cb.can_execute() is False
    assert cb.state == CircuitState.OPEN

    # After timeout
    time.sleep(0.15)
    assert cb.can_execute() is True
    assert cb.state == CircuitState.HALF_OPEN


def test_half_open_allows_execution():
    cb = CircuitBreaker(failure_threshold=2, timeout=0.1)

    # Open the circuit
    cb.record_failure()
    cb.record_failure()

    # Transition to HALF_OPEN
    time.sleep(0.15)
    assert cb.can_execute() is True
    assert cb.state == CircuitState.HALF_OPEN

    # Should still allow execution in HALF_OPEN
    assert cb.can_execute() is True


def test_failure_count_resets_on_transition_to_half_open():
    cb = CircuitBreaker(failure_threshold=3, timeout=0.1)

    cb.record_failure()
    cb.record_failure()
    cb.record_failure()
    assert cb.state == CircuitState.OPEN
    assert cb.failure_count == 3

    # Transition to HALF_OPEN
    time.sleep(0.15)
    cb.can_execute()
    assert cb.state == CircuitState.HALF_OPEN
    assert cb.failure_count == 0


def test_success_count_resets_on_transition_to_closed():
    cb = CircuitBreaker(failure_threshold=2, success_threshold=2, timeout=0.1)

    # Open the circuit
    cb.record_failure()
    cb.record_failure()

    # Transition to HALF_OPEN and close
    time.sleep(0.15)
    cb.can_execute()
    cb.record_success()
    cb.record_success()

    assert cb.state == CircuitState.CLOSED
    assert cb.success_count == 0
    assert cb.failure_count == 0


def test_multiple_cycles_open_half_open_closed():
    cb = CircuitBreaker(failure_threshold=2, success_threshold=2, timeout=0.1)

    # First cycle: CLOSED -> OPEN -> HALF_OPEN -> CLOSED
    cb.record_failure()
    cb.record_failure()
    assert cb.state == CircuitState.OPEN

    time.sleep(0.15)
    cb.can_execute()
    assert cb.state == CircuitState.HALF_OPEN

    cb.record_success()
    cb.record_success()
    assert cb.state == CircuitState.CLOSED

    # Second cycle
    cb.record_failure()
    cb.record_failure()
    assert cb.state == CircuitState.OPEN

    time.sleep(0.15)
    cb.can_execute()
    assert cb.state == CircuitState.HALF_OPEN

    cb.record_success()
    cb.record_success()
    assert cb.state == CircuitState.CLOSED
