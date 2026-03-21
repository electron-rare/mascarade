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
