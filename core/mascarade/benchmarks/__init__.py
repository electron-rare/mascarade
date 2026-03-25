"""Mascarade benchmarking suite for model performance evaluation."""

from mascarade.benchmarks.test_prompts import get_all_domains, get_test_prompts

__all__ = ["get_test_prompts", "get_all_domains"]

# Lazy re-export — only available when lm-eval is installed
def __getattr__(name: str):  # noqa: ANN001
    if name in ("MascaradeLM", "EvalHarnessRunner", "EvalRunResult", "SUPPORTED_TASKS"):
        from mascarade.benchmarks.eval_harness import (
            SUPPORTED_TASKS,
            EvalHarnessRunner,
            EvalRunResult,
            MascaradeLM,
        )
        _exports = {
            "MascaradeLM": MascaradeLM,
            "EvalHarnessRunner": EvalHarnessRunner,
            "EvalRunResult": EvalRunResult,
            "SUPPORTED_TASKS": SUPPORTED_TASKS,
        }
        return _exports[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
