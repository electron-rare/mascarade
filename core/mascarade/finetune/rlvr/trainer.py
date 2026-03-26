"""GRPO/DAPO trainer wrapper for RLVR with domain-specific verifiable rewards."""

from __future__ import annotations

import importlib
import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from mascarade.finetune.rlvr.reward_functions import RewardFunction

logger = logging.getLogger("mascarade.finetune.rlvr.trainer")

# Registry of built-in reward functions by name
_REWARD_REGISTRY: dict[str, type[RewardFunction]] = {}


def _populate_registry() -> None:
    """Lazily populate the reward function registry."""
    if _REWARD_REGISTRY:
        return
    from mascarade.finetune.rlvr.kicad_verifier import KiCadDRCReward
    from mascarade.finetune.rlvr.reward_functions import (
        CodeCompilationReward,
        CompositeReward,
        JSONValidationReward,
    )

    _REWARD_REGISTRY.update(
        {
            "code_compilation": CodeCompilationReward,
            "json_validation": JSONValidationReward,
            "kicad_drc": KiCadDRCReward,
            "composite": CompositeReward,
        }
    )


def get_reward_function(name: str) -> RewardFunction:
    """Resolve a reward function name to an instance.

    Supports:
    - Built-in names: "code_compilation", "json_validation", "kicad_drc"
    - Dotted paths: "my_module.MyReward" (must subclass RewardFunction)
    """
    _populate_registry()

    if name in _REWARD_REGISTRY:
        return _REWARD_REGISTRY[name]()

    # Try dotted import path
    if "." in name:
        module_path, _, cls_name = name.rpartition(".")
        try:
            module = importlib.import_module(module_path)
            cls = getattr(module, cls_name)
            if not (isinstance(cls, type) and issubclass(cls, RewardFunction)):
                raise TypeError(f"{name} is not a RewardFunction subclass")
            return cls()
        except (ImportError, AttributeError) as e:
            raise ValueError(f"Cannot resolve reward function '{name}': {e}") from e

    available = sorted(_REWARD_REGISTRY.keys())
    raise ValueError(f"Unknown reward function '{name}'. Available: {available}")


@dataclass
class RLVRConfig:
    """Configuration for an RLVR training run."""

    base_model: str
    reward_functions: list[str]  # names of reward functions to use
    num_generations: int = 16  # group size for GRPO
    loss_type: str = "dapo"  # "grpo" or "dapo"
    max_completion_length: int = 2048
    learning_rate: float = 1e-6
    num_epochs: int = 3
    batch_size: int = 4
    beta: float = 0.04  # KL penalty
    output_dir: str = "~/.mascarade/finetune/rlvr"
    use_unsloth: bool = True  # attempt Unsloth QLoRA for low-VRAM training
    lora_r: int = 16
    lora_alpha: int = 32
    lora_dropout: float = 0.05
    use_dora: bool = True  # DoRA: Weight-Decomposed Low-Rank Adaptation (QDoRA when quantized)


@dataclass
class RLVRResult:
    """Result of an RLVR training run."""

    output_dir: str
    base_model: str
    reward_functions: list[str]
    training_time_seconds: float = 0.0
    final_reward_mean: float = 0.0
    final_loss: float = 0.0
    model_path: str = ""
    metrics: dict[str, Any] = field(default_factory=dict)


class RLVRTrainer:
    """Orchestrates GRPO/DAPO training with domain-specific verifiable rewards.

    Unlike DPO/SimPO/KTO which rely on human preference data, RLVR uses
    programmatically-verifiable reward functions (code compilation, DRC checks,
    JSON schema validation, etc.) to train via group relative policy optimization.

    This enables:
    - Self-improving loops without human annotation
    - Domain-specific quality guarantees (e.g., valid KiCad output)
    - Scalable RL training on consumer GPUs via Unsloth + QLoRA
    """

    def __init__(self) -> None:
        self._reward_fns: list[RewardFunction] = []

    async def train(self, config: RLVRConfig, dataset_path: str) -> RLVRResult:
        """Run RLVR training with verifiable rewards.

        Args:
            config: Training configuration.
            dataset_path: Path to JSONL with {"prompt": str} entries,
                or a HuggingFace dataset identifier.

        Returns:
            RLVRResult with output model path and metrics.
        """
        try:
            from trl import GRPOConfig, GRPOTrainer
        except ImportError:
            raise RuntimeError(
                "trl>=0.17 required for RLVR. Install with: pip install 'trl>=0.17'"
            ) from None

        # Resolve reward functions
        self._reward_fns = [get_reward_function(name) for name in config.reward_functions]
        logger.info(
            "RLVR: %d reward functions: %s",
            len(self._reward_fns),
            [str(fn) for fn in self._reward_fns],
        )

        run_id = f"rlvr-{config.loss_type}-{int(time.time())}"
        output_dir = Path(config.output_dir).expanduser() / run_id
        output_dir.mkdir(parents=True, exist_ok=True)

        start = time.time()

        # Load dataset
        dataset = self._load_dataset(dataset_path)
        logger.info("RLVR: loaded %d prompts from %s", len(dataset), dataset_path)

        # Load model (try Unsloth first for QLoRA)
        model, tokenizer = self._load_model(config)

        # Build reward wrapper for trl GRPOTrainer
        reward_fn = self._build_trl_reward_fn()

        # Configure GRPO training
        training_args = GRPOConfig(
            output_dir=str(output_dir),
            num_train_epochs=config.num_epochs,
            per_device_train_batch_size=config.batch_size,
            gradient_accumulation_steps=4,
            learning_rate=config.learning_rate,
            bf16=True,
            logging_steps=10,
            save_strategy="epoch",
            report_to="none",
            max_completion_length=config.max_completion_length,
            num_generations=config.num_generations,
        )

        trainer = GRPOTrainer(
            model=model,
            args=training_args,
            train_dataset=dataset,
            processing_class=tokenizer,
            reward_funcs=reward_fn,
        )

        logger.info(
            "RLVR: starting %s training on %s",
            config.loss_type.upper(),
            config.base_model,
        )
        trainer.train()

        # Save
        model_path = str(output_dir / "rlvr_model")
        trainer.save_model(model_path)
        tokenizer.save_pretrained(model_path)

        elapsed = time.time() - start
        logs = trainer.state.log_history
        final_loss = logs[-1].get("loss", 0.0) if logs else 0.0

        # Compute final reward mean on a sample
        final_reward_mean = await self._eval_reward_sample(dataset, model_path, config)

        result = RLVRResult(
            output_dir=str(output_dir),
            base_model=config.base_model,
            reward_functions=config.reward_functions,
            training_time_seconds=round(elapsed, 1),
            final_reward_mean=round(final_reward_mean, 4),
            final_loss=round(final_loss, 4),
            model_path=model_path,
            metrics={
                "loss_type": config.loss_type,
                "num_generations": config.num_generations,
                "num_epochs": config.num_epochs,
                "learning_rate": config.learning_rate,
                "beta": config.beta,
            },
        )

        # Persist result
        (output_dir / "rlvr_result.json").write_text(
            json.dumps(
                {
                    "output_dir": result.output_dir,
                    "base_model": result.base_model,
                    "reward_functions": result.reward_functions,
                    "training_time_seconds": result.training_time_seconds,
                    "final_reward_mean": result.final_reward_mean,
                    "final_loss": result.final_loss,
                    "model_path": result.model_path,
                    "metrics": result.metrics,
                },
                indent=2,
                default=str,
            )
        )

        logger.info(
            "RLVR: complete in %.0fs — loss=%.4f reward_mean=%.4f -> %s",
            elapsed,
            final_loss,
            final_reward_mean,
            model_path,
        )
        return result

    def _load_model(self, config: RLVRConfig) -> tuple[Any, Any]:
        """Load model, preferring Unsloth QLoRA for low-VRAM training."""
        if config.use_unsloth:
            try:
                from unsloth import FastLanguageModel

                model, tokenizer = FastLanguageModel.from_pretrained(
                    model_name=config.base_model,
                    max_seq_length=config.max_completion_length * 2,
                    load_in_4bit=True,
                )
                model = FastLanguageModel.get_peft_model(
                    model,
                    r=config.lora_r,
                    lora_alpha=config.lora_alpha,
                    lora_dropout=config.lora_dropout,
                    target_modules=["all-linear"],
                    use_dora=config.use_dora,
                    use_gradient_checkpointing="unsloth",
                )
                logger.info("RLVR: loaded model via Unsloth QLoRA (4-bit)")
                return model, tokenizer
            except ImportError:
                logger.info("RLVR: Unsloth not available, falling back to transformers")

        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer

        model = AutoModelForCausalLM.from_pretrained(
            config.base_model, torch_dtype=torch.bfloat16, device_map="auto"
        )
        tokenizer = AutoTokenizer.from_pretrained(config.base_model)
        if tokenizer.pad_token is None:
            tokenizer.pad_token = tokenizer.eos_token
        logger.info("RLVR: loaded model via transformers (bfloat16)")
        return model, tokenizer

    @staticmethod
    def _load_dataset(dataset_path: str) -> Any:
        """Load prompt dataset from local JSONL or HuggingFace Hub."""
        from datasets import load_dataset as _load_dataset

        if Path(dataset_path).exists():
            return _load_dataset("json", data_files=dataset_path, split="train")
        return _load_dataset(dataset_path, split="train")

    def _build_trl_reward_fn(self):
        """Build a reward function compatible with trl GRPOTrainer.

        GRPOTrainer expects: reward_fn(completions, prompts, **kwargs) -> list[float]
        """
        import asyncio

        reward_fns = self._reward_fns

        def trl_reward(
            completions: list[list[dict]], prompts: list[str], **kwargs: Any
        ) -> list[float]:
            scores: list[float] = []
            loop = asyncio.new_event_loop()
            try:
                for completion_group, prompt in zip(completions, prompts, strict=False):
                    text = completion_group[0].get("content", "") if completion_group else ""
                    # Average score across all reward functions
                    fn_scores: list[float] = []
                    for fn in reward_fns:
                        result = loop.run_until_complete(fn.evaluate(prompt, text))
                        fn_scores.append(result.score)
                    avg = sum(fn_scores) / len(fn_scores) if fn_scores else 0.0
                    scores.append(avg)
            finally:
                loop.close()
            return scores

        return trl_reward

    async def _eval_reward_sample(
        self,
        dataset: Any,
        model_path: str,
        config: RLVRConfig,
        sample_size: int = 20,
    ) -> float:
        """Evaluate mean reward on a small sample after training."""
        import shutil
        import subprocess

        if not shutil.which("llama-cli"):
            logger.info("RLVR: llama-cli not found, skipping post-training reward eval")
            return 0.0

        prompts = [row["prompt"] for row in dataset.select(range(min(sample_size, len(dataset))))]
        total_score = 0.0
        count = 0

        for prompt in prompts:
            try:
                result = subprocess.run(
                    [
                        "llama-cli",
                        "--model",
                        model_path,
                        "--prompt",
                        prompt,
                        "--n-predict",
                        "256",
                        "--threads",
                        "4",
                        "--no-display-prompt",
                    ],
                    capture_output=True,
                    text=True,
                    timeout=60,
                )
                completion = result.stdout.strip()
                for fn in self._reward_fns:
                    r = await fn.evaluate(prompt, completion)
                    total_score += r.score
                    count += 1
            except Exception as e:
                logger.debug("RLVR eval sample error: %s", e)

        return total_score / count if count > 0 else 0.0
