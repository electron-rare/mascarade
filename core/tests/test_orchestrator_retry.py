"""Tests pour le mécanisme de retry de l'orchestrateur."""

import time

import pytest

from mascarade.orchestrator.retry import (
    BackoffStrategy,
    RetryConfig,
    RetryExecutor,
    RetryState,
)


class TestBackoffStrategy:
    """Tests pour les stratégies de backoff."""

    def test_constant_backoff(self):
        config = RetryConfig(strategy=BackoffStrategy.CONSTANT, initial_delay=2.0, jitter=False)

        assert config.calculate_delay(0) == 2.0
        assert config.calculate_delay(1) == 2.0
        assert config.calculate_delay(5) == 2.0

    def test_linear_backoff(self):
        config = RetryConfig(
            strategy=BackoffStrategy.LINEAR,
            initial_delay=1.0,
            multiplier=2.0,
            jitter=False,
        )

        assert config.calculate_delay(0) == 1.0
        assert config.calculate_delay(1) == 3.0  # 1.0 + (1 * 2.0)
        assert config.calculate_delay(2) == 5.0  # 1.0 + (2 * 2.0)

    def test_exponential_backoff(self):
        config = RetryConfig(
            strategy=BackoffStrategy.EXPONENTIAL,
            initial_delay=1.0,
            multiplier=2.0,
            jitter=False,
        )

        assert config.calculate_delay(0) == 1.0  # 1.0 * (2.0^0)
        assert config.calculate_delay(1) == 2.0  # 1.0 * (2.0^1)
        assert config.calculate_delay(2) == 4.0  # 1.0 * (2.0^2)
        assert config.calculate_delay(3) == 8.0  # 1.0 * (2.0^3)

    def test_max_delay_limit(self):
        config = RetryConfig(
            strategy=BackoffStrategy.EXPONENTIAL,
            initial_delay=1.0,
            multiplier=2.0,
            max_delay=5.0,
            jitter=False,
        )

        assert config.calculate_delay(10) == 5.0  # Would be 1024.0, capped at 5.0

    def test_jitter_adds_randomness(self):
        config = RetryConfig(
            strategy=BackoffStrategy.CONSTANT,
            initial_delay=10.0,
            jitter=True,
        )

        delays = [config.calculate_delay(0) for _ in range(10)]

        # All delays should be between 5.0 and 15.0 (10.0 * [0.5, 1.5])
        assert all(5.0 <= d <= 15.0 for d in delays)
        # They should not all be the same (with high probability)
        assert len(set(delays)) > 1


class TestRetryConfig:
    """Tests pour la configuration de retry."""

    def test_should_retry_on_timeout(self):
        config = RetryConfig(retry_on_timeout=True)

        assert config.should_retry(Exception("Request timeout"))
        assert config.should_retry(Exception("Connection timed out"))
        assert not config.should_retry(Exception("Invalid input"))

    def test_should_retry_on_rate_limit(self):
        config = RetryConfig(retry_on_rate_limit=True)

        assert config.should_retry(Exception("Rate limit exceeded"))
        assert config.should_retry(Exception("Error 429"))
        assert not config.should_retry(Exception("Invalid input"))

    def test_should_retry_on_server_error(self):
        config = RetryConfig(retry_on_server_error=True)

        assert config.should_retry(Exception("500 Internal Server Error"))
        assert config.should_retry(Exception("502 Bad Gateway"))
        assert config.should_retry(Exception("503 Service Unavailable"))
        assert config.should_retry(Exception("504 Gateway Timeout"))
        assert config.should_retry(Exception("Server error occurred"))
        assert not config.should_retry(Exception("404 Not Found"))

    def test_should_not_retry_when_disabled(self):
        config = RetryConfig(
            retry_on_timeout=False,
            retry_on_rate_limit=False,
            retry_on_server_error=False,
        )

        assert not config.should_retry(Exception("Request timeout"))
        assert not config.should_retry(Exception("Rate limit exceeded"))
        assert not config.should_retry(Exception("500 Internal Server Error"))


class TestRetryState:
    """Tests pour l'état de retry."""

    def test_initial_state(self):
        state = RetryState(agent_name="test_agent")

        assert state.agent_name == "test_agent"
        assert state.attempts == 0
        assert state.total_delay == 0.0
        assert state.errors == []

    def test_record_attempt(self):
        state = RetryState(agent_name="test_agent")

        state.record_attempt(error="Error 1", delay=1.0)
        assert state.attempts == 1
        assert state.total_delay == 1.0
        assert state.errors == ["Error 1"]

        state.record_attempt(error="Error 2", delay=2.0)
        assert state.attempts == 2
        assert state.total_delay == 3.0
        assert state.errors == ["Error 1", "Error 2"]

    def test_get_stats(self):
        state = RetryState(agent_name="test_agent")
        state.record_attempt(error="Error 1", delay=1.0)
        state.record_attempt(error="Error 2", delay=2.0)

        stats = state.get_stats()
        assert stats["agent_name"] == "test_agent"
        assert stats["attempts"] == 2
        assert stats["total_delay"] == 3.0
        assert stats["error_count"] == 2
        assert stats["last_error"] == "Error 2"

    def test_reset(self):
        state = RetryState(agent_name="test_agent")
        state.record_attempt(error="Error 1", delay=1.0)

        state.reset()
        assert state.attempts == 0
        assert state.total_delay == 0.0
        assert state.errors == []


class TestRetryExecutor:
    """Tests pour l'exécuteur de retry."""

    @pytest.mark.asyncio
    async def test_successful_execution_no_retry(self):
        executor = RetryExecutor()

        async def success_fn():
            return "success"

        result = await executor.execute_with_retry(success_fn, agent_name="test")
        assert result == "success"

        stats = executor.get_stats("test")
        assert stats["attempts"] == 0  # No retries needed

    @pytest.mark.asyncio
    async def test_retry_on_failure(self):
        executor = RetryExecutor(config=RetryConfig(max_retries=3, initial_delay=0.01, jitter=False))

        call_count = 0

        async def failing_fn():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise Exception("Temporary error")
            return "success"

        result = await executor.execute_with_retry(failing_fn, agent_name="test")
        assert result == "success"
        assert call_count == 3

        stats = executor.get_stats("test")
        assert stats["attempts"] == 2  # 2 retries (3 total attempts)

    @pytest.mark.asyncio
    async def test_max_retries_exhausted(self):
        executor = RetryExecutor(config=RetryConfig(max_retries=2, initial_delay=0.01, jitter=False))

        call_count = 0

        async def always_fails():
            nonlocal call_count
            call_count += 1
            raise Exception("Permanent error")

        with pytest.raises(Exception, match="Permanent error"):
            await executor.execute_with_retry(always_fails, agent_name="test")

        assert call_count == 3  # Initial + 2 retries
        stats = executor.get_stats("test")
        assert stats["attempts"] == 3

    @pytest.mark.asyncio
    async def test_custom_max_retries_override(self):
        executor = RetryExecutor(config=RetryConfig(max_retries=10, initial_delay=0.01, jitter=False))

        call_count = 0

        async def always_fails():
            nonlocal call_count
            call_count += 1
            raise Exception("Error")

        with pytest.raises(Exception):
            await executor.execute_with_retry(always_fails, agent_name="test", max_retries=1)

        assert call_count == 2  # Initial + 1 retry (override of default 10)

    @pytest.mark.asyncio
    async def test_custom_config_override(self):
        executor = RetryExecutor(config=RetryConfig(initial_delay=10.0, jitter=False))

        custom_config = RetryConfig(max_retries=1, initial_delay=0.01, jitter=False)

        call_count = 0

        async def always_fails():
            nonlocal call_count
            call_count += 1
            raise Exception("Error")

        start_time = time.time()
        with pytest.raises(Exception):
            await executor.execute_with_retry(always_fails, agent_name="test", config=custom_config)
        elapsed = time.time() - start_time

        # Should use custom_config's 0.01s delay, not default 10.0s
        assert elapsed < 1.0
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_on_retry_callback(self):
        executor = RetryExecutor(config=RetryConfig(max_retries=2, initial_delay=0.01, jitter=False))

        retry_calls = []

        def on_retry(attempt, error, delay):
            retry_calls.append({"attempt": attempt, "error": error, "delay": delay})

        call_count = 0

        async def failing_fn():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise Exception(f"Error {call_count}")
            return "success"

        result = await executor.execute_with_retry(
            failing_fn,
            agent_name="test",
            on_retry=on_retry,
        )

        assert result == "success"
        assert len(retry_calls) == 2
        assert retry_calls[0]["attempt"] == 1
        assert "Error 1" in retry_calls[0]["error"]
        assert retry_calls[1]["attempt"] == 2
        assert "Error 2" in retry_calls[1]["error"]

    @pytest.mark.asyncio
    async def test_sync_function_support(self):
        executor = RetryExecutor(config=RetryConfig(max_retries=2, initial_delay=0.01, jitter=False))

        call_count = 0

        def sync_fn():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise Exception("Sync error")
            return "sync success"

        result = await executor.execute_with_retry(sync_fn, agent_name="test")
        assert result == "sync success"
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_backoff_timing(self):
        executor = RetryExecutor(
            config=RetryConfig(
                strategy=BackoffStrategy.EXPONENTIAL,
                max_retries=2,
                initial_delay=0.1,
                multiplier=2.0,
                jitter=False,
            )
        )

        async def always_fails():
            raise Exception("Error")

        start_time = time.time()
        with pytest.raises(Exception):
            await executor.execute_with_retry(always_fails, agent_name="test")
        elapsed = time.time() - start_time

        # Should have delays: 0.1s + 0.2s = 0.3s total (approximately)
        assert 0.25 < elapsed < 0.5

    @pytest.mark.asyncio
    async def test_multiple_agents_tracking(self):
        executor = RetryExecutor(config=RetryConfig(max_retries=1, initial_delay=0.01, jitter=False))

        async def agent1_fn():
            raise Exception("Agent 1 error")

        async def agent2_fn():
            raise Exception("Agent 2 error")

        with pytest.raises(Exception):
            await executor.execute_with_retry(agent1_fn, agent_name="agent1")

        with pytest.raises(Exception):
            await executor.execute_with_retry(agent2_fn, agent_name="agent2")

        stats = executor.get_stats()
        assert "agent1" in stats
        assert "agent2" in stats
        assert stats["agent1"]["attempts"] == 2
        assert stats["agent2"]["attempts"] == 2

    def test_get_stats_all_agents(self):
        executor = RetryExecutor()
        executor.states["agent1"] = RetryState(agent_name="agent1")
        executor.states["agent1"].record_attempt(error="Error 1", delay=1.0)
        executor.states["agent2"] = RetryState(agent_name="agent2")
        executor.states["agent2"].record_attempt(error="Error 2", delay=2.0)

        stats = executor.get_stats()
        assert len(stats) == 2
        assert stats["agent1"]["attempts"] == 1
        assert stats["agent2"]["attempts"] == 1

    def test_reset_specific_agent(self):
        executor = RetryExecutor()
        executor.states["agent1"] = RetryState(agent_name="agent1")
        executor.states["agent1"].record_attempt(error="Error 1", delay=1.0)
        executor.states["agent2"] = RetryState(agent_name="agent2")
        executor.states["agent2"].record_attempt(error="Error 2", delay=2.0)

        executor.reset("agent1")

        assert executor.states["agent1"].attempts == 0
        assert executor.states["agent2"].attempts == 1

    def test_reset_all_agents(self):
        executor = RetryExecutor()
        executor.states["agent1"] = RetryState(agent_name="agent1")
        executor.states["agent1"].record_attempt(error="Error 1", delay=1.0)
        executor.states["agent2"] = RetryState(agent_name="agent2")
        executor.states["agent2"].record_attempt(error="Error 2", delay=2.0)

        executor.reset()

        assert len(executor.states) == 0

    @pytest.mark.asyncio
    async def test_error_tracking_in_state(self):
        executor = RetryExecutor(config=RetryConfig(max_retries=2, initial_delay=0.01, jitter=False))

        call_count = 0

        async def failing_fn():
            nonlocal call_count
            call_count += 1
            raise Exception(f"Error attempt {call_count}")

        with pytest.raises(Exception):
            await executor.execute_with_retry(failing_fn, agent_name="test")

        stats = executor.get_stats("test")
        assert stats["error_count"] == 3
        assert stats["last_error"] == "Error attempt 3"

        state = executor.states["test"]
        assert len(state.errors) == 3
        assert state.errors[0] == "Error attempt 1"
        assert state.errors[1] == "Error attempt 2"
        assert state.errors[2] == "Error attempt 3"
