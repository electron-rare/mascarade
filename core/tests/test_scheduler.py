"""Tests for the distributed scheduler."""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from mascarade.scheduler.worker_state import WorkerState, WorkerStatus, WorkerRuntime
from mascarade.scheduler.scheduler import ResourceAwareScheduler, ScheduledRequest
from mascarade.scheduler.heartbeat import HeartbeatMonitor


# --- WorkerState ---


class TestWorkerState:
    def test_initial_state(self):
        w = WorkerState(node_id="test", url="http://localhost:8201")
        assert w.status == WorkerStatus.DEAD
        assert not w.alive
        assert w.avg_latency_ms == 1000.0
        assert w.error_rate == 0.0

    def test_alive_status(self):
        w = WorkerState(node_id="test", url="http://localhost:8201", status=WorkerStatus.ALIVE)
        assert w.alive
        w.status = WorkerStatus.SLOW
        assert w.alive
        w.status = WorkerStatus.DEAD
        assert not w.alive

    def test_request_tracking(self):
        w = WorkerState(node_id="test", url="http://localhost:8201")
        w.request_started()
        assert w.current_load == 1
        assert w.total_requests == 1

        w.request_completed(latency_ms=150.0, success=True)
        assert w.current_load == 0
        assert w.avg_latency_ms == 150.0
        assert w.error_rate == 0.0

    def test_error_tracking(self):
        w = WorkerState(node_id="test", url="http://localhost:8201")
        w.request_started()
        w.request_completed(latency_ms=5000.0, success=False)
        assert w.error_count == 1
        assert w.error_rate == 1.0

    def test_model_fit(self):
        w = WorkerState(
            node_id="test",
            url="http://localhost:8201",
            vram_total_mb=24000,
            vram_free_mb=10000,
            loaded_models=["llama-8b"],
        )
        assert w.can_fit_model("llama-8b")  # already loaded
        assert w.can_fit_model("new-model", estimated_vram_mb=5000)  # fits
        assert not w.can_fit_model("huge-model", estimated_vram_mb=20000)  # too big

    def test_has_capacity(self):
        w = WorkerState(
            node_id="test",
            url="http://localhost:8201",
            status=WorkerStatus.ALIVE,
            max_concurrent=2,
        )
        assert w.has_capacity()
        w.current_load = 2
        assert not w.has_capacity()

    def test_update_from_health(self):
        w = WorkerState(node_id="test", url="http://localhost:8201")
        w.update_from_health({
            "vram_total_mb": 24000,
            "vram_free_mb": 18000,
            "cpu_percent": 45.0,
            "loaded_models": ["llama-8b", "qwen-1.5b"],
            "runtime": "ollama",
            "max_concurrent": 4,
        })
        assert w.vram_total_mb == 24000
        assert w.vram_free_mb == 18000
        assert w.cpu_percent == 45.0
        assert w.loaded_models == ["llama-8b", "qwen-1.5b"]
        assert w.runtime == WorkerRuntime.OLLAMA
        assert w.max_concurrent == 4
        assert w.missed_heartbeats == 0

    def test_vram_usage_pct(self):
        w = WorkerState(
            node_id="test",
            url="http://localhost:8201",
            vram_total_mb=24000,
            vram_free_mb=6000,
        )
        assert w.vram_usage_pct == 75.0

    def test_to_dict(self):
        w = WorkerState(node_id="test", url="http://localhost:8201")
        d = w.to_dict()
        assert d["node_id"] == "test"
        assert "alive" in d
        assert "avg_latency_ms" in d


# --- ResourceAwareScheduler ---


class TestScheduler:
    def _make_worker(self, node_id: str, **kwargs) -> WorkerState:
        defaults = {
            "url": f"http://{node_id}:8201",
            "status": WorkerStatus.ALIVE,
            "max_concurrent": 4,
            "loaded_models": [],
        }
        defaults.update(kwargs)
        return WorkerState(node_id=node_id, **defaults)

    def test_register_worker(self):
        s = ResourceAwareScheduler()
        w = self._make_worker("kxkm")
        s.register_worker(w)
        assert "kxkm" in s.workers

    def test_select_only_worker(self):
        s = ResourceAwareScheduler()
        s.register_worker(self._make_worker("kxkm", loaded_models=["llama-8b"]))
        req = ScheduledRequest(model="llama-8b", messages=[{"role": "user", "content": "hi"}])
        result = s.select_worker(req)
        assert result.node_id == "kxkm"

    def test_affinity_wins(self):
        s = ResourceAwareScheduler()
        s.register_worker(self._make_worker("kxkm", loaded_models=["llama-8b"]))
        s.register_worker(self._make_worker("tower", loaded_models=["qwen-1.5b"]))

        req = ScheduledRequest(model="llama-8b", messages=[{"role": "user", "content": "hi"}])
        result = s.select_worker(req)
        assert result.node_id == "kxkm"  # has the model

    def test_load_balancing(self):
        s = ResourceAwareScheduler()
        w1 = self._make_worker("kxkm", loaded_models=["llama-8b"])
        w1.current_load = 3  # almost full
        s.register_worker(w1)

        w2 = self._make_worker("tower", loaded_models=["llama-8b"])
        w2.current_load = 0  # empty
        s.register_worker(w2)

        req = ScheduledRequest(model="llama-8b", messages=[{"role": "user", "content": "hi"}])
        result = s.select_worker(req)
        assert result.node_id == "tower"  # less loaded

    def test_no_alive_workers_raises(self):
        s = ResourceAwareScheduler()
        s.register_worker(self._make_worker("dead", status=WorkerStatus.DEAD))

        req = ScheduledRequest(model="any", messages=[{"role": "user", "content": "hi"}])
        with pytest.raises(HTTPException) as exc_info:
            s.select_worker(req)
        assert exc_info.value.status_code == 503

    def test_admission_control_queue_full(self):
        s = ResourceAwareScheduler()
        w = self._make_worker("kxkm")
        w.queue_depth = 200
        s.register_worker(w)

        req = ScheduledRequest(model="any", messages=[{"role": "user", "content": "hi"}])
        with pytest.raises(HTTPException) as exc_info:
            s.admit(req)
        assert exc_info.value.status_code == 429

    def test_slow_worker_penalty(self):
        s = ResourceAwareScheduler()
        slow = self._make_worker("slow", status=WorkerStatus.SLOW, loaded_models=["m"])
        fast = self._make_worker("fast", loaded_models=["m"])
        s.register_worker(slow)
        s.register_worker(fast)

        req = ScheduledRequest(model="m", messages=[{"role": "user", "content": "hi"}])
        result = s.select_worker(req)
        assert result.node_id == "fast"

    def test_error_rate_penalty(self):
        s = ResourceAwareScheduler()
        bad = self._make_worker("bad", loaded_models=["m"])
        bad.error_count = 50
        bad.total_requests = 100
        s.register_worker(bad)

        good = self._make_worker("good", loaded_models=["m"])
        good.total_requests = 100
        s.register_worker(good)

        req = ScheduledRequest(model="m", messages=[{"role": "user", "content": "hi"}])
        result = s.select_worker(req)
        assert result.node_id == "good"

    def test_get_status(self):
        s = ResourceAwareScheduler()
        s.register_worker(self._make_worker("kxkm"))
        status = s.get_status()
        assert status["alive_workers"] == 1
        assert "kxkm" in status["workers"]


# --- HeartbeatMonitor ---


class TestHeartbeatMonitor:
    def test_init(self):
        workers = {"w1": WorkerState(node_id="w1", url="http://localhost:8201")}
        hb = HeartbeatMonitor(workers)
        assert hb._interval == 5

    def test_get_alive_workers(self):
        w1 = WorkerState(node_id="w1", url="http://w1:8201", status=WorkerStatus.ALIVE)
        w2 = WorkerState(node_id="w2", url="http://w2:8201", status=WorkerStatus.DEAD)
        hb = HeartbeatMonitor({"w1": w1, "w2": w2})
        alive = hb.get_alive_workers()
        assert len(alive) == 1
        assert alive[0].node_id == "w1"

    def test_handle_failure_threshold(self):
        w = WorkerState(node_id="w1", url="http://w1:8201", status=WorkerStatus.ALIVE)
        hb = HeartbeatMonitor({"w1": w})

        # 2 failures: still alive
        hb._handle_failure(w)
        hb._handle_failure(w)
        assert w.status == WorkerStatus.ALIVE

        # 3rd failure: dead
        hb._handle_failure(w)
        assert w.status == WorkerStatus.DEAD

    def test_get_dead_workers(self):
        w1 = WorkerState(node_id="w1", url="http://w1:8201", status=WorkerStatus.ALIVE)
        w2 = WorkerState(node_id="w2", url="http://w2:8201", status=WorkerStatus.DEAD)
        w3 = WorkerState(node_id="w3", url="http://w3:8201", status=WorkerStatus.DEAD)
        hb = HeartbeatMonitor({"w1": w1, "w2": w2, "w3": w3})
        dead = hb.get_dead_workers()
        assert len(dead) == 2
        assert {d.node_id for d in dead} == {"w2", "w3"}

    def test_handle_failure_idempotent_after_dead(self):
        """Calling _handle_failure on already-dead worker stays dead."""
        w = WorkerState(node_id="w1", url="http://w1:8201", status=WorkerStatus.DEAD)
        w.missed_heartbeats = 10
        hb = HeartbeatMonitor({"w1": w})
        hb._handle_failure(w)
        assert w.status == WorkerStatus.DEAD
        assert w.missed_heartbeats == 11


# --- Additional WorkerState tests ---


class TestWorkerStateExtended:
    def test_p95_latency_default(self):
        w = WorkerState(node_id="test", url="http://localhost:8201")
        assert w.p95_latency_ms == 5000.0

    def test_p95_latency_computed(self):
        w = WorkerState(node_id="test", url="http://localhost:8201")
        for i in range(100):
            w.response_times_ms.append(float(i * 10))
        # p95 should be around 950
        assert w.p95_latency_ms >= 900

    def test_draining_status_no_capacity(self):
        w = WorkerState(
            node_id="test",
            url="http://localhost:8201",
            status=WorkerStatus.DRAINING,
            max_concurrent=10,
        )
        assert not w.has_capacity()
        assert w.alive is False

    def test_request_completed_decrements_load(self):
        w = WorkerState(node_id="test", url="http://localhost:8201")
        w.request_started()
        w.request_started()
        assert w.current_load == 2
        w.request_completed(100.0, True)
        assert w.current_load == 1

    def test_error_rate_zero_when_no_requests(self):
        w = WorkerState(node_id="test", url="http://localhost:8201")
        assert w.error_rate == 0.0

    def test_vram_usage_pct_zero_vram(self):
        w = WorkerState(node_id="test", url="http://localhost:8201", vram_total_mb=0)
        assert w.vram_usage_pct == 0.0

    def test_update_from_health_unknown_runtime(self):
        w = WorkerState(node_id="test", url="http://localhost:8201")
        w.update_from_health({"runtime": "invalid_runtime_xyz"})
        assert w.runtime == WorkerRuntime.UNKNOWN

    def test_to_dict_completeness(self):
        w = WorkerState(node_id="test", url="http://localhost:8201")
        d = w.to_dict()
        expected_keys = {
            "node_id", "url", "runtime", "status", "vram_total_mb", "vram_free_mb",
            "vram_usage_pct", "ram_total_mb", "ram_free_mb", "cpu_percent", "gpu_percent",
            "current_load", "max_concurrent", "queue_depth", "loaded_models",
            "avg_latency_ms", "p95_latency_ms", "error_rate", "total_requests", "alive",
        }
        assert set(d.keys()) == expected_keys


# --- Additional Scheduler tests ---


class TestSchedulerExtended:
    def _make_worker(self, node_id, **kwargs):
        defaults = {
            "url": f"http://{node_id}:8201",
            "status": WorkerStatus.ALIVE,
            "max_concurrent": 4,
            "loaded_models": [],
        }
        defaults.update(kwargs)
        return WorkerState(node_id=node_id, **defaults)

    def test_remove_worker(self):
        s = ResourceAwareScheduler()
        s.register_worker(self._make_worker("w1"))
        assert "w1" in s.workers
        s.remove_worker("w1")
        assert "w1" not in s.workers

    def test_remove_nonexistent_worker_no_error(self):
        s = ResourceAwareScheduler()
        s.remove_worker("nonexistent")  # should not raise

    def test_total_queue_depth(self):
        s = ResourceAwareScheduler()
        w1 = self._make_worker("w1")
        w1.queue_depth = 10
        w2 = self._make_worker("w2")
        w2.queue_depth = 20
        s.register_worker(w1)
        s.register_worker(w2)
        assert s.total_queue_depth == 30

    def test_workers_for_model_with_capacity(self):
        s = ResourceAwareScheduler()
        w1 = self._make_worker("w1", loaded_models=["llama-8b"])
        w2 = self._make_worker("w2", loaded_models=["qwen-7b"])
        s.register_worker(w1)
        s.register_worker(w2)
        # Both can serve llama-8b: w1 has it, w2 has capacity
        result = s.workers_for_model("llama-8b")
        assert len(result) == 2

    def test_estimate_wait_no_workers(self):
        s = ResourceAwareScheduler()
        req = ScheduledRequest(model="any", messages=[{"role": "user", "content": "hi"}])
        assert s.estimate_wait(req) == float("inf")

    def test_admit_no_capable_worker(self):
        s = ResourceAwareScheduler()
        # Only dead workers
        s.register_worker(self._make_worker("dead", status=WorkerStatus.DEAD))
        req = ScheduledRequest(model="any", messages=[{"role": "user", "content": "hi"}])
        with pytest.raises(HTTPException) as exc_info:
            s.admit(req)
        assert exc_info.value.status_code == 503

    def test_vram_scoring_prefers_more_free_vram(self):
        s = ResourceAwareScheduler()
        low_vram = self._make_worker(
            "low", loaded_models=["m"], vram_total_mb=24000, vram_free_mb=2000,
        )
        high_vram = self._make_worker(
            "high", loaded_models=["m"], vram_total_mb=24000, vram_free_mb=20000,
        )
        s.register_worker(low_vram)
        s.register_worker(high_vram)
        req = ScheduledRequest(model="m", messages=[{"role": "user", "content": "hi"}])
        result = s.select_worker(req)
        assert result.node_id == "high"

    def test_dispatch_count_increments(self):
        s = ResourceAwareScheduler()
        s.register_worker(self._make_worker("w1", loaded_models=["m"]))
        req = ScheduledRequest(model="m", messages=[{"role": "user", "content": "hi"}])
        assert s._dispatch_count == 0
        s.select_worker(req)
        assert s._dispatch_count == 1
        s.select_worker(req)
        assert s._dispatch_count == 2
