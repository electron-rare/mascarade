"""Integration with EleutherAI lm-evaluation-harness for standardized benchmarks.

Wraps lm-evaluation-harness as an optional dependency and routes all inference
through the Mascarade router so any configured provider/model can be evaluated
on standard academic benchmarks (HellaSwag, MMLU, ARC, TruthfulQA, GSM8K, etc.).
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

from mascarade.benchmarks.storage import BenchmarkStorage
from mascarade.config import settings
from mascarade.router.router import Router, Strategy

logger = logging.getLogger("mascarade.benchmarks.eval_harness")

# ---------------------------------------------------------------------------
# Optional dependency guard
# ---------------------------------------------------------------------------
try:
    import lm_eval
    from lm_eval.api.instance import Instance
    from lm_eval.api.model import LM

    _HAS_LM_EVAL = True
except ImportError:
    _HAS_LM_EVAL = False
    LM = object  # type: ignore[assignment,misc]
    Instance = None  # type: ignore[assignment,misc]

# ---------------------------------------------------------------------------
# Supported tasks (subset safe for API-based models)
# ---------------------------------------------------------------------------
SUPPORTED_TASKS = frozenset({
    "hellaswag",
    "mmlu",
    "arc_easy",
    "arc_challenge",
    "truthfulqa_mc2",
    "gsm8k",
})


class EvalRunStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class EvalRunResult:
    """Result of a single evaluation run."""

    run_id: str
    task: str
    provider: str
    model: str
    status: EvalRunStatus = EvalRunStatus.PENDING
    num_samples: int | None = None
    scores: dict[str, float] = field(default_factory=dict)
    raw_results: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None

    @property
    def duration_seconds(self) -> float:
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "task": self.task,
            "provider": self.provider,
            "model": self.model,
            "status": self.status.value,
            "num_samples": self.num_samples,
            "scores": self.scores,
            "error": self.error,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "duration_seconds": self.duration_seconds,
        }


def _check_available() -> None:
    """Raise if lm-evaluation-harness is not installed."""
    if not _HAS_LM_EVAL:
        raise ImportError(
            "lm-evaluation-harness is not installed. "
            "Install it with: pip install 'mascarade-core[eval]'"
        )


# ---------------------------------------------------------------------------
# MascaradeLM — bridges lm_eval's LM interface to Mascarade's Router
# ---------------------------------------------------------------------------
class MascaradeLM(LM):  # type: ignore[misc]
    """lm-evaluation-harness compatible LM that routes through Mascarade."""

    def __init__(
        self,
        router: Router | None = None,
        provider: str | None = None,
        model: str | None = None,
        max_tokens: int = 1024,
        temperature: float = 0.0,
        batch_size: int = 1,
    ) -> None:
        _check_available()
        super().__init__()
        self.router = router or Router()
        self.provider = provider
        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature
        self._batch_size = batch_size

    # -- helpers -------------------------------------------------------------

    def _build_strategy(self) -> Strategy:
        return Strategy.SPECIFIC if self.provider else Strategy.BEST

    async def _send(self, prompt: str, max_tokens: int | None = None) -> str:
        """Send a single prompt through the router and return the text."""
        response = await self.router.send(
            messages=[{"role": "user", "content": prompt}],
            strategy=self._build_strategy(),
            provider=self.provider,
            model=self.model,
            temperature=self.temperature,
            max_tokens=max_tokens or self.max_tokens,
        )
        return response.content

    def _run_async(self, coro: Any) -> Any:
        """Run an async coroutine from sync context."""
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            # We're inside an existing event loop — use a thread.
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                return pool.submit(asyncio.run, coro).result()
        return asyncio.run(coro)

    # -- lm_eval LM interface -----------------------------------------------

    def generate_until(self, requests: list[Instance]) -> list[str]:
        """Generate text completions for each request.

        Each Instance has .args = (prompt_text, generation_kwargs_dict).
        """
        results: list[str] = []
        for req in requests:
            prompt, kwargs = req.args
            max_tokens = kwargs.get("max_gen_toks", self.max_tokens)
            try:
                text = self._run_async(self._send(prompt, max_tokens=max_tokens))
            except Exception as exc:
                logger.warning("generate_until failed: %s", exc)
                text = ""
            results.append(text)
        return results

    def loglikelihood(self, requests: list[Instance]) -> list[tuple[float, bool]]:
        """Approximate log-likelihoods via generation scoring.

        Most API-based models do not expose log-probabilities directly.
        We use a simple heuristic: ask the model whether the continuation is
        a plausible completion.  This yields a coarse 0/1 estimate rather than
        a true log-prob, which is the standard trade-off for API-only models.
        """
        results: list[tuple[float, bool]] = []
        for req in requests:
            context, continuation = req.args
            prompt = (
                f"Does the following continuation logically follow the context?\n\n"
                f"Context: {context}\n"
                f"Continuation: {continuation}\n\n"
                f"Answer with only 'yes' or 'no'."
            )
            try:
                text = self._run_async(self._send(prompt, max_tokens=8))
                is_match = "yes" in text.lower()
                score = 0.0 if is_match else -100.0
            except Exception as exc:
                logger.warning("loglikelihood failed: %s", exc)
                score = -100.0
                is_match = False
            results.append((score, is_match))
        return results

    def loglikelihood_rolling(self, requests: list[Instance]) -> list[float]:
        """Rolling log-likelihood — not meaningfully supported via API."""
        return [-100.0] * len(requests)


# ---------------------------------------------------------------------------
# Run orchestrator
# ---------------------------------------------------------------------------
class EvalHarnessRunner:
    """Manages evaluation runs and persists results."""

    def __init__(self, router: Router | None = None) -> None:
        _check_available()
        self.router = router or Router()
        self.runs: dict[str, EvalRunResult] = {}
        self._storage = BenchmarkStorage()
        self._cache_dir = Path(
            getattr(settings, "eval_harness_cache_dir", "data/eval_cache")
        )
        self._cache_dir.mkdir(parents=True, exist_ok=True)

    def _generate_run_id(self) -> str:
        return f"eval_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"

    async def run_eval(
        self,
        task: str,
        *,
        provider: str | None = None,
        model: str | None = None,
        num_samples: int | None = None,
    ) -> EvalRunResult:
        """Execute an evaluation run for a single task.

        Args:
            task: lm-evaluation-harness task name (e.g. "hellaswag").
            provider: Route to this provider specifically (optional).
            model: Use this model (optional).
            num_samples: Limit the number of samples evaluated (optional).

        Returns:
            EvalRunResult with scores and metadata.
        """
        _check_available()

        if task not in SUPPORTED_TASKS:
            raise ValueError(
                f"Unsupported task '{task}'. Supported: {sorted(SUPPORTED_TASKS)}"
            )

        run_id = self._generate_run_id()
        result = EvalRunResult(
            run_id=run_id,
            task=task,
            provider=provider or "best",
            model=model or "default",
            num_samples=num_samples,
            started_at=datetime.now(),
            status=EvalRunStatus.RUNNING,
        )
        self.runs[run_id] = result

        try:
            lm = MascaradeLM(
                router=self.router,
                provider=provider,
                model=model,
                temperature=0.0,
            )

            eval_kwargs: dict[str, Any] = {
                "model": lm,
                "tasks": [task],
                "batch_size": 1,
                "cache_requests": str(self._cache_dir),
            }
            if num_samples is not None:
                eval_kwargs["limit"] = num_samples

            raw = lm_eval.simple_evaluate(**eval_kwargs)

            # Extract scores from results
            task_results = raw.get("results", {}).get(task, {})
            scores: dict[str, float] = {}
            for metric_key, value in task_results.items():
                if isinstance(value, (int, float)):
                    scores[metric_key] = float(value)

            result.scores = scores
            result.raw_results = {
                k: v
                for k, v in task_results.items()
                if isinstance(v, (int, float, str, bool))
            }
            result.status = EvalRunStatus.COMPLETED

            # Persist to ClickHouse (best-effort)
            quality = scores.get("acc", scores.get("acc_norm", 0.0)) * 100
            self._storage.write_result(
                provider=result.provider,
                model=result.model,
                domain=f"eval:{task}",
                latency_p50=result.duration_seconds,
                latency_p95=result.duration_seconds,
                quality_score=quality,
                cost=0.0,
                request_count=num_samples or 0,
                notes=f"lm-eval-harness {task}",
            )

        except Exception as exc:
            logger.error("Eval run %s failed: %s", run_id, exc)
            result.status = EvalRunStatus.FAILED
            result.error = str(exc)

        result.completed_at = datetime.now()
        return result

    def get_run(self, run_id: str) -> EvalRunResult | None:
        return self.runs.get(run_id)

    def list_runs(self) -> list[dict[str, Any]]:
        return [r.to_dict() for r in self.runs.values()]
