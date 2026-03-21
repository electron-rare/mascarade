"""Domain-specific verifiable reward functions for RLVR training."""

from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

logger = logging.getLogger("mascarade.finetune.rlvr.rewards")


@dataclass
class RewardResult:
    """Outcome of a single reward evaluation."""

    score: float  # -1.0 to 1.0
    passed: bool
    details: str
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


class RewardFunction(ABC):
    """Base class for verifiable reward functions.

    Each reward function takes a (prompt, completion) pair and returns
    a deterministic, programmatically-verifiable reward score.
    """

    @abstractmethod
    async def evaluate(self, prompt: str, completion: str) -> RewardResult:
        """Evaluate the completion and return a verifiable reward."""
        ...

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}>"


class CodeCompilationReward(RewardFunction):
    """Reward based on whether generated code compiles/parses.

    Rewards:
        1.0 — Code parses successfully as valid Python
       -0.5 — Syntax error in generated code
       -1.0 — Empty or whitespace-only completion
    """

    async def evaluate(self, prompt: str, completion: str) -> RewardResult:
        import ast

        stripped = completion.strip()
        if not stripped:
            return RewardResult(
                score=-1.0,
                passed=False,
                details="Empty completion",
                errors=["Completion is empty or whitespace-only"],
            )

        try:
            ast.parse(stripped)
            return RewardResult(
                score=1.0,
                passed=True,
                details="Code parses successfully",
            )
        except SyntaxError as e:
            return RewardResult(
                score=-0.5,
                passed=False,
                details=f"Syntax error at line {e.lineno}: {e.msg}",
                errors=[str(e)],
            )


class JSONValidationReward(RewardFunction):
    """Reward based on whether output is valid JSON matching an expected structure.

    Rewards:
        1.0 — Valid JSON that matches expected keys (if provided)
        0.5 — Valid JSON but missing some expected keys
       -0.5 — Invalid JSON
       -1.0 — Empty completion
    """

    def __init__(self, *, expected_keys: list[str] | None = None):
        self._expected_keys = set(expected_keys) if expected_keys else set()

    async def evaluate(self, prompt: str, completion: str) -> RewardResult:
        stripped = completion.strip()
        if not stripped:
            return RewardResult(
                score=-1.0,
                passed=False,
                details="Empty completion",
                errors=["Completion is empty or whitespace-only"],
            )

        try:
            parsed = json.loads(stripped)
        except json.JSONDecodeError as e:
            return RewardResult(
                score=-0.5,
                passed=False,
                details=f"Invalid JSON: {e}",
                errors=[str(e)],
            )

        if not self._expected_keys:
            return RewardResult(
                score=1.0,
                passed=True,
                details="Valid JSON",
            )

        # Check expected keys if the parsed result is a dict
        if not isinstance(parsed, dict):
            return RewardResult(
                score=0.5,
                passed=True,
                details="Valid JSON but not an object — cannot check keys",
                warnings=["Expected a JSON object with specific keys"],
            )

        present = self._expected_keys & set(parsed.keys())
        missing = self._expected_keys - present

        if not missing:
            return RewardResult(
                score=1.0,
                passed=True,
                details=f"Valid JSON with all {len(self._expected_keys)} expected keys",
            )

        ratio = len(present) / len(self._expected_keys)
        return RewardResult(
            score=round(0.5 + 0.5 * ratio, 2),
            passed=True,
            details=f"Valid JSON but missing keys: {sorted(missing)}",
            warnings=[f"Missing key: {k}" for k in sorted(missing)],
        )


class CompositeReward(RewardFunction):
    """Combine multiple reward functions with weighted averaging.

    Example:
        reward = CompositeReward([
            (CodeCompilationReward(), 0.6),
            (JSONValidationReward(expected_keys=["name"]), 0.4),
        ])
    """

    def __init__(self, functions: list[tuple[RewardFunction, float]]):
        if not functions:
            raise ValueError("At least one reward function is required")
        total_weight = sum(w for _, w in functions)
        if abs(total_weight - 1.0) > 1e-6:
            raise ValueError(f"Weights must sum to 1.0, got {total_weight}")
        self._functions = functions

    async def evaluate(self, prompt: str, completion: str) -> RewardResult:
        total_score = 0.0
        all_errors: list[str] = []
        all_warnings: list[str] = []
        details_parts: list[str] = []
        all_passed = True

        for fn, weight in self._functions:
            result = await fn.evaluate(prompt, completion)
            total_score += result.score * weight
            all_errors.extend(result.errors)
            all_warnings.extend(result.warnings)
            details_parts.append(f"{fn.__class__.__name__}: {result.score:.2f}")
            if not result.passed:
                all_passed = False

        return RewardResult(
            score=round(total_score, 4),
            passed=all_passed,
            details=" | ".join(details_parts),
            errors=all_errors,
            warnings=all_warnings,
        )
