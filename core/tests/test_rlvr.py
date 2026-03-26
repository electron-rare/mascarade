"""Comprehensive tests for the RLVR reward functions and config modules."""

from __future__ import annotations

import pytest

from mascarade.finetune.rlvr.reward_functions import (
    CodeCompilationReward,
    CompositeReward,
    JSONValidationReward,
    RewardResult,
)
from mascarade.finetune.rlvr.trainer import RLVRConfig, RLVRResult

# ---------------------------------------------------------------------------
# RewardResult dataclass
# ---------------------------------------------------------------------------


class TestRewardResult:
    def test_creation_minimal(self):
        r = RewardResult(score=0.5, passed=True, details="ok")
        assert r.score == 0.5
        assert r.passed is True
        assert r.details == "ok"
        assert r.errors == []
        assert r.warnings == []

    def test_creation_with_errors_and_warnings(self):
        r = RewardResult(
            score=-0.5,
            passed=False,
            details="bad",
            errors=["err1", "err2"],
            warnings=["warn1"],
        )
        assert len(r.errors) == 2
        assert len(r.warnings) == 1

    def test_score_range(self):
        """RewardResult accepts scores in the documented -1.0 to 1.0 range."""
        r_min = RewardResult(score=-1.0, passed=False, details="min")
        r_max = RewardResult(score=1.0, passed=True, details="max")
        assert r_min.score == -1.0
        assert r_max.score == 1.0


# ---------------------------------------------------------------------------
# CodeCompilationReward
# ---------------------------------------------------------------------------


class TestCodeCompilationReward:
    @pytest.fixture
    def reward(self):
        return CodeCompilationReward()

    async def test_valid_python(self, reward):
        result = await reward.evaluate("write code", "def hello():\n    return 42")
        assert result.score == 1.0
        assert result.passed is True
        assert "parses successfully" in result.details

    async def test_invalid_python(self, reward):
        result = await reward.evaluate("write code", "def hello(\n    return")
        assert result.score == -0.5
        assert result.passed is False
        assert "Syntax error" in result.details
        assert len(result.errors) > 0

    async def test_empty_completion(self, reward):
        result = await reward.evaluate("write code", "")
        assert result.score == -1.0
        assert result.passed is False
        assert "Empty" in result.details

    async def test_whitespace_only_completion(self, reward):
        result = await reward.evaluate("write code", "   \n\t  \n  ")
        assert result.score == -1.0
        assert result.passed is False

    async def test_complex_valid_python(self, reward):
        code = """
import os
from pathlib import Path

class Config:
    def __init__(self, name: str):
        self.name = name

    async def load(self):
        return {"name": self.name}
"""
        result = await reward.evaluate("complex code", code)
        assert result.score == 1.0
        assert result.passed is True


# ---------------------------------------------------------------------------
# JSONValidationReward
# ---------------------------------------------------------------------------


class TestJSONValidationReward:
    async def test_valid_json_no_keys(self):
        reward = JSONValidationReward()
        result = await reward.evaluate("json please", '{"name": "test", "value": 42}')
        assert result.score == 1.0
        assert result.passed is True
        assert "Valid JSON" in result.details

    async def test_invalid_json(self):
        reward = JSONValidationReward()
        result = await reward.evaluate("json please", "{not valid json}")
        assert result.score == -0.5
        assert result.passed is False
        assert "Invalid JSON" in result.details

    async def test_empty_completion(self):
        reward = JSONValidationReward()
        result = await reward.evaluate("json please", "")
        assert result.score == -1.0
        assert result.passed is False

    async def test_valid_json_all_expected_keys(self):
        reward = JSONValidationReward(expected_keys=["name", "value"])
        result = await reward.evaluate("json", '{"name": "x", "value": 1}')
        assert result.score == 1.0
        assert result.passed is True

    async def test_valid_json_missing_some_keys(self):
        reward = JSONValidationReward(expected_keys=["name", "value", "extra"])
        result = await reward.evaluate("json", '{"name": "x"}')
        assert result.passed is True
        # 1 of 3 keys present: score = 0.5 + 0.5 * (1/3) ~ 0.67
        assert 0.5 < result.score < 1.0
        assert len(result.warnings) > 0

    async def test_valid_json_not_object(self):
        reward = JSONValidationReward(expected_keys=["name"])
        result = await reward.evaluate("json", "[1, 2, 3]")
        assert result.score == 0.5
        assert result.passed is True
        assert "not an object" in result.details


# ---------------------------------------------------------------------------
# CompositeReward
# ---------------------------------------------------------------------------


class TestCompositeReward:
    async def test_combines_scores(self):
        composite = CompositeReward(
            [
                (CodeCompilationReward(), 0.6),
                (JSONValidationReward(), 0.4),
            ]
        )
        # Valid Python, valid JSON
        code_json = '{"key": "value"}'  # valid JSON and valid Python expression
        result = await composite.evaluate("test", code_json)
        # Both pass: 1.0 * 0.6 + 1.0 * 0.4 = 1.0
        assert abs(result.score - 1.0) < 0.01
        assert result.passed is True

    async def test_mixed_pass_fail(self):
        composite = CompositeReward(
            [
                (CodeCompilationReward(), 0.5),
                (JSONValidationReward(), 0.5),
            ]
        )
        # Valid Python but invalid JSON
        result = await composite.evaluate("test", "def foo(): pass")
        # code: 1.0 * 0.5 = 0.5, json: -0.5 * 0.5 = -0.25 => 0.25
        assert result.passed is False  # JSON did not pass
        assert abs(result.score - 0.25) < 0.01

    async def test_empty_functions_raises(self):
        with pytest.raises(ValueError, match="At least one"):
            CompositeReward([])

    async def test_weights_must_sum_to_one(self):
        with pytest.raises(ValueError, match="sum to 1.0"):
            CompositeReward(
                [
                    (CodeCompilationReward(), 0.3),
                    (JSONValidationReward(), 0.3),
                ]
            )

    async def test_details_include_component_names(self):
        composite = CompositeReward(
            [
                (CodeCompilationReward(), 0.5),
                (JSONValidationReward(), 0.5),
            ]
        )
        result = await composite.evaluate("test", '{"a": 1}')
        assert "CodeCompilationReward" in result.details
        assert "JSONValidationReward" in result.details


# ---------------------------------------------------------------------------
# RLVRConfig defaults
# ---------------------------------------------------------------------------


class TestRLVRConfig:
    def test_defaults(self):
        cfg = RLVRConfig(base_model="meta-llama/Llama-3-8B", reward_functions=["code_compilation"])
        assert cfg.num_generations == 16
        assert cfg.loss_type == "dapo"
        assert cfg.max_completion_length == 2048
        assert cfg.learning_rate == 1e-6
        assert cfg.num_epochs == 3
        assert cfg.batch_size == 4
        assert cfg.beta == 0.04
        assert cfg.use_unsloth is True
        assert cfg.lora_r == 16
        assert cfg.lora_alpha == 32
        assert cfg.lora_dropout == 0.05

    def test_custom_values(self):
        cfg = RLVRConfig(
            base_model="model",
            reward_functions=["json_validation"],
            num_generations=32,
            loss_type="grpo",
            learning_rate=5e-5,
        )
        assert cfg.num_generations == 32
        assert cfg.loss_type == "grpo"
        assert cfg.learning_rate == 5e-5


# ---------------------------------------------------------------------------
# RLVRResult creation
# ---------------------------------------------------------------------------


class TestRLVRResult:
    def test_creation_minimal(self):
        r = RLVRResult(
            output_dir="/tmp/out",
            base_model="llama3",
            reward_functions=["code_compilation"],
        )
        assert r.output_dir == "/tmp/out"
        assert r.training_time_seconds == 0.0
        assert r.final_reward_mean == 0.0
        assert r.final_loss == 0.0
        assert r.model_path == ""
        assert r.metrics == {}

    def test_creation_full(self):
        r = RLVRResult(
            output_dir="/tmp/out",
            base_model="llama3",
            reward_functions=["code_compilation", "json_validation"],
            training_time_seconds=123.4,
            final_reward_mean=0.85,
            final_loss=0.12,
            model_path="/tmp/model",
            metrics={"steps": 100},
        )
        assert r.training_time_seconds == 123.4
        assert r.final_reward_mean == 0.85
        assert r.metrics["steps"] == 100
