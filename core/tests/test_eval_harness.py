"""Tests for mascarade.benchmarks.eval_harness and mascarade.routers.eval."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mascarade.benchmarks.eval_harness import (
    SUPPORTED_TASKS,
    EvalRunResult,
    EvalRunStatus,
)

# lm_eval is optional — skip the MascaradeLM tests if not available
lm_eval = pytest.importorskip("lm_eval", reason="lm-evaluation-harness not installed")


# ---------------------------------------------------------------------------
# EvalRunResult
# ---------------------------------------------------------------------------


class TestEvalRunResult:
    def test_defaults(self):
        r = EvalRunResult(run_id="r1", task="mmlu", provider="openai", model="gpt-4")
        assert r.status == EvalRunStatus.PENDING
        assert r.scores == {}
        assert r.error is None
        assert r.duration_seconds == 0.0

    def test_duration(self):
        r = EvalRunResult(
            run_id="r1",
            task="mmlu",
            provider="openai",
            model="gpt-4",
            started_at=datetime(2026, 1, 1, 12, 0, 0),
            completed_at=datetime(2026, 1, 1, 12, 1, 30),
        )
        assert r.duration_seconds == 90.0

    def test_to_dict(self):
        r = EvalRunResult(
            run_id="r1",
            task="hellaswag",
            provider="claude",
            model="opus",
            status=EvalRunStatus.COMPLETED,
            scores={"acc": 0.85},
        )
        d = r.to_dict()
        assert d["run_id"] == "r1"
        assert d["task"] == "hellaswag"
        assert d["status"] == "completed"
        assert d["scores"]["acc"] == 0.85


class TestEvalRunStatus:
    def test_values(self):
        assert EvalRunStatus.PENDING == "pending"
        assert EvalRunStatus.RUNNING == "running"
        assert EvalRunStatus.COMPLETED == "completed"
        assert EvalRunStatus.FAILED == "failed"


class TestSupportedTasks:
    def test_known_tasks(self):
        assert "hellaswag" in SUPPORTED_TASKS
        assert "mmlu" in SUPPORTED_TASKS
        assert "gsm8k" in SUPPORTED_TASKS

    def test_unsupported_task(self):
        assert "imagenet" not in SUPPORTED_TASKS


# ---------------------------------------------------------------------------
# MascaradeLM (requires lm_eval)
# ---------------------------------------------------------------------------


class TestMascaradeLM:
    @pytest.fixture()
    def mock_router(self):
        router = MagicMock()
        response = MagicMock()
        response.content = "The answer is 42."
        router.send = AsyncMock(return_value=response)
        return router

    def test_init(self, mock_router):
        from mascarade.benchmarks.eval_harness import MascaradeLM

        lm = MascaradeLM(router=mock_router, provider="openai", model="gpt-4")
        assert lm.provider == "openai"
        assert lm.model == "gpt-4"
        assert lm.max_tokens == 1024

    def test_build_strategy_specific(self, mock_router):
        from mascarade.benchmarks.eval_harness import MascaradeLM
        from mascarade.router.router import Strategy

        lm = MascaradeLM(router=mock_router, provider="openai")
        assert lm._build_strategy() == Strategy.SPECIFIC

    def test_build_strategy_best(self, mock_router):
        from mascarade.benchmarks.eval_harness import MascaradeLM
        from mascarade.router.router import Strategy

        lm = MascaradeLM(router=mock_router, provider=None)
        assert lm._build_strategy() == Strategy.BEST

    def test_generate_until(self, mock_router):
        from lm_eval.api.instance import Instance

        from mascarade.benchmarks.eval_harness import MascaradeLM

        lm = MascaradeLM(router=mock_router)

        req = Instance(
            request_type="generate_until",
            doc={},
            arguments=("What is 6*7?", {"max_gen_toks": 50}),
            idx=0,
        )
        results = lm.generate_until([req])
        assert len(results) == 1
        assert results[0] == "The answer is 42."
        mock_router.send.assert_called_once()

    def test_generate_until_error(self, mock_router):
        from lm_eval.api.instance import Instance

        from mascarade.benchmarks.eval_harness import MascaradeLM

        mock_router.send.side_effect = RuntimeError("provider down")
        lm = MascaradeLM(router=mock_router)

        req = Instance(
            request_type="generate_until",
            doc={},
            arguments=("prompt", {}),
            idx=0,
        )
        results = lm.generate_until([req])
        assert results == [""]

    def test_loglikelihood(self, mock_router):
        from lm_eval.api.instance import Instance

        from mascarade.benchmarks.eval_harness import MascaradeLM

        mock_router.send.return_value.content = "yes"
        lm = MascaradeLM(router=mock_router)

        req = Instance(
            request_type="loglikelihood",
            doc={},
            arguments=("The cat sat on the", " mat."),
            idx=0,
        )
        results = lm.loglikelihood([req])
        assert len(results) == 1
        score, is_match = results[0]
        assert is_match is True
        assert score == 0.0

    def test_loglikelihood_no(self, mock_router):
        from lm_eval.api.instance import Instance

        from mascarade.benchmarks.eval_harness import MascaradeLM

        mock_router.send.return_value.content = "no"
        lm = MascaradeLM(router=mock_router)

        req = Instance(
            request_type="loglikelihood",
            doc={},
            arguments=("The cat sat on the", " banana republic."),
            idx=0,
        )
        results = lm.loglikelihood([req])
        score, is_match = results[0]
        assert is_match is False
        assert score == -100.0

    def test_loglikelihood_rolling(self, mock_router):
        from lm_eval.api.instance import Instance

        from mascarade.benchmarks.eval_harness import MascaradeLM

        lm = MascaradeLM(router=mock_router)

        req = Instance(
            request_type="loglikelihood_rolling",
            doc={},
            arguments=("some text",),
            idx=0,
        )
        results = lm.loglikelihood_rolling([req])
        assert results == [-100.0]


# ---------------------------------------------------------------------------
# EvalHarnessRunner
# ---------------------------------------------------------------------------


class TestEvalHarnessRunner:
    @pytest.fixture()
    def mock_runner(self, mock_router=None):
        """Create an EvalHarnessRunner with mocked dependencies."""
        from mascarade.benchmarks.eval_harness import EvalHarnessRunner

        router = MagicMock()
        router.send = AsyncMock(return_value=MagicMock(content="42"))

        with (
            patch("mascarade.benchmarks.eval_harness.BenchmarkStorage"),
            patch("pathlib.Path.mkdir"),
        ):
            runner = EvalHarnessRunner(router=router)
        return runner

    def test_generate_run_id(self, mock_runner):
        rid = mock_runner._generate_run_id()
        assert rid.startswith("eval_")

    def test_list_runs_empty(self, mock_runner):
        assert mock_runner.list_runs() == []

    def test_get_run_missing(self, mock_runner):
        assert mock_runner.get_run("nonexistent") is None

    @pytest.mark.asyncio
    async def test_run_eval_unsupported_task(self, mock_runner):
        with pytest.raises(ValueError, match="Unsupported task"):
            await mock_runner.run_eval("imagenet")

    @pytest.mark.asyncio
    async def test_run_eval_success(self, mock_runner):
        """Mock lm_eval.simple_evaluate to test the full flow."""
        fake_results = {
            "results": {
                "hellaswag": {
                    "acc": 0.75,
                    "acc_norm": 0.80,
                    "acc_stderr": 0.02,
                }
            }
        }
        with patch("mascarade.benchmarks.eval_harness.lm_eval") as mock_lm_eval:
            mock_lm_eval.simple_evaluate.return_value = fake_results
            result = await mock_runner.run_eval("hellaswag", num_samples=10)

        assert result.status == EvalRunStatus.COMPLETED
        assert result.scores["acc"] == 0.75
        assert result.scores["acc_norm"] == 0.80
        assert result.task == "hellaswag"

    @pytest.mark.asyncio
    async def test_run_eval_failure(self, mock_runner):
        """When lm_eval raises, the run should be marked FAILED."""
        with patch("mascarade.benchmarks.eval_harness.lm_eval") as mock_lm_eval:
            mock_lm_eval.simple_evaluate.side_effect = RuntimeError("eval crashed")
            result = await mock_runner.run_eval("mmlu")

        assert result.status == EvalRunStatus.FAILED
        assert "eval crashed" in result.error


# ---------------------------------------------------------------------------
# Router endpoints (FastAPI TestClient)
# ---------------------------------------------------------------------------


class TestEvalRouter:
    @pytest.fixture()
    def mock_app(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from mascarade.routers.eval import router as eval_router

        app = FastAPI()
        app.include_router(eval_router)
        return TestClient(app)

    def test_list_runs_disabled(self, mock_app):
        """When eval harness is disabled, endpoints return 503."""
        with patch("mascarade.routers.eval.settings") as mock_settings:
            mock_settings.eval_harness_enabled = False
            resp = mock_app.get("/v1/eval/runs")
        assert resp.status_code == 503

    def test_get_run_not_found(self, mock_app):
        """GET /v1/eval/runs/{run_id} with unknown id returns 404."""
        mock_runner = MagicMock()
        mock_runner.get_run.return_value = None

        with patch("mascarade.routers.eval._runner", mock_runner), \
             patch("mascarade.routers.eval.settings") as mock_settings:
            mock_settings.eval_harness_enabled = True
            resp = mock_app.get("/v1/eval/runs/nonexistent")
        assert resp.status_code == 404

    def test_post_run_invalid_task(self, mock_app):
        """POST /v1/eval/run with an unsupported task returns 400."""
        mock_runner = MagicMock()

        with patch("mascarade.routers.eval._runner", mock_runner), \
             patch("mascarade.routers.eval.settings") as mock_settings:
            mock_settings.eval_harness_enabled = True
            resp = mock_app.post(
                "/v1/eval/run",
                json={"task": "imagenet"},
            )
        assert resp.status_code == 400
