"""Reinforcer agent — DPO/RLHF improvement cycles."""

from __future__ import annotations

import json
import logging
import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger("mascarade.finetune.reinforcer")


@dataclass
class DPOPair:
    prompt: str
    chosen: str
    rejected: str


@dataclass
class ReinforcementResult:
    dataset_path: str
    total_pairs: int
    method: str = "dpo"  # "dpo" or "simpo"
    ready_for_training: bool = True


class ReinforcerAgent:
    """Creates DPO training data from detected errors and triggers re-training.

    Workflow:
    1. Analyst detects errors in student output
    2. Reinforcer collects errors
    3. Teacher generates correct (chosen) responses
    4. Reinforcer formats DPO pairs (chosen/rejected)
    5. Student re-trains with DPO data

    P2P capability: ft-reinforcement
    """

    def __init__(self, *, teacher=None, output_dir: Path | str = "~/.mascarade/finetune/dpo"):
        self.teacher = teacher
        self.output_dir = Path(output_dir).expanduser()
        self.output_dir.mkdir(parents=True, exist_ok=True)

    async def collect_errors(
        self,
        eval_report: dict,
        model_path: str,
        test_prompts: list[str],
    ) -> list[dict]:
        """Identify errors by running model on test prompts and checking quality."""
        import subprocess
        if not shutil.which("llama-cli"):
            logger.warning("llama-cli not found in PATH, cannot collect errors")
            return []
        errors = []
        for prompt in test_prompts:
            try:
                result = subprocess.run(
                    ["llama-cli", "--model", model_path, "--prompt", prompt,
                     "--n-predict", "256", "--threads", "4", "--no-display-prompt"],
                    capture_output=True, text=True, timeout=60,
                )
                response = result.stdout.strip()
                # Simple quality heuristic: too short, repetitive, or empty
                if len(response) < 20 or self._is_repetitive(response):
                    errors.append({
                        "prompt": prompt,
                        "bad_response": response,
                        "error_description": "low quality or repetitive",
                    })
            except Exception as e:
                logger.warning("Error collecting: %s", e)

        logger.info("Collected %d errors from %d prompts", len(errors), len(test_prompts))
        return errors

    async def generate_dpo_pairs(
        self,
        errors: list[dict],
        *,
        run_id: str | None = None,
    ) -> ReinforcementResult:
        """Generate DPO training pairs from collected errors.

        Uses Teacher agent to generate the 'chosen' (correct) responses.
        The 'rejected' responses come from the student model's errors.
        """
        run_id = run_id or f"dpo-{int(time.time())}"
        output_path = self.output_dir / f"{run_id}.jsonl"

        if self.teacher is None:
            raise RuntimeError("ReinforcerAgent requires a TeacherAgent for DPO pair generation")

        from mascarade.finetune.agents.teacher import TeacherConfig
        result = await self.teacher.generate_corrections(
            errors=errors,
            config=TeacherConfig(task_description="Generate correct response for DPO training"),
            output_path=output_path,
        )

        return ReinforcementResult(
            dataset_path=str(output_path),
            total_pairs=result["total"],
        )

    async def train_alignment(
        self,
        model_path: str,
        dpo_dataset_path: str,
        *,
        method: str = "simpo",
        run_id: str | None = None,
        beta: float = 2.0,
        gamma: float = 0.5,
        learning_rate: float = 5e-7,
        num_epochs: int = 1,
        max_length: int = 1024,
    ) -> dict:
        """Run DPO or SimPO alignment training.

        SimPO (Simple Preference Optimization) is recommended:
        - No reference model needed → 50% less VRAM
        - +6.4 over DPO on AlpacaEval benchmarks
        - beta: reward margin scaling, gamma: length normalization
        """
        from trl import DPOConfig, DPOTrainer

        run_id = run_id or f"{method}-{int(time.time())}"
        output_dir = Path(f"~/.mascarade/finetune/runs/{run_id}").expanduser()
        output_dir.mkdir(parents=True, exist_ok=True)

        logger.info("Starting %s alignment: model=%s dataset=%s", method, model_path, dpo_dataset_path)
        start = time.time()

        from datasets import load_dataset as _load_dataset
        if Path(dpo_dataset_path).exists():
            dataset = _load_dataset("json", data_files=dpo_dataset_path, split="train")
        else:
            dataset = _load_dataset(dpo_dataset_path, split="train")

        training_args = DPOConfig(
            output_dir=str(output_dir),
            num_train_epochs=num_epochs,
            per_device_train_batch_size=2,
            gradient_accumulation_steps=4,
            learning_rate=learning_rate,
            bf16=True,
            logging_steps=10,
            save_strategy="epoch",
            report_to="none",
            max_length=max_length,
            max_prompt_length=max_length // 2,
            loss_type="simpo" if method == "simpo" else "sigmoid",
            beta=beta,
        )

        # SimPO-specific: add gamma for length normalization
        if method == "simpo" and hasattr(training_args, "simpo_gamma"):
            training_args.simpo_gamma = gamma

        from transformers import AutoModelForCausalLM, AutoTokenizer
        import torch

        tokenizer = AutoTokenizer.from_pretrained(model_path)
        if tokenizer.pad_token is None:
            tokenizer.pad_token = tokenizer.eos_token

        model = AutoModelForCausalLM.from_pretrained(
            model_path, torch_dtype=torch.bfloat16, device_map="auto",
        )

        trainer = DPOTrainer(
            model=model,
            ref_model=None if method == "simpo" else model,
            args=training_args,
            train_dataset=dataset,
            processing_class=tokenizer,
        )

        trainer.train()
        trainer.save_model(str(output_dir / "aligned"))
        tokenizer.save_pretrained(str(output_dir / "aligned"))

        elapsed = time.time() - start
        logs = trainer.state.log_history
        final_loss = logs[-1].get("loss", 0.0) if logs else 0.0

        result = {
            "output_dir": str(output_dir),
            "method": method,
            "training_time_seconds": round(elapsed, 1),
            "final_loss": round(final_loss, 4),
            "model_path": str(output_dir / "aligned"),
        }
        (output_dir / "alignment_result.json").write_text(json.dumps(result, indent=2, default=str))
        logger.info("%s alignment complete in %.0fs, loss=%.4f → %s", method, elapsed, final_loss, output_dir)
        return result

    async def train_grpo(
        self,
        model_path: str,
        prompts: list[str],
        *,
        reward_fn=None,
        run_id: str | None = None,
        num_epochs: int = 1,
        learning_rate: float = 5e-6,
        max_length: int = 1024,
        num_generations: int = 4,
    ) -> dict:
        """Train using GRPO (Group Relative Policy Optimization) for reasoning.

        GRPO removes the need for a value model, making RL training accessible
        on consumer GPUs. Works with QLoRA via Unsloth (5GB VRAM minimum).

        reward_fn: callable(completions, prompts) -> list[float] scores
        """
        run_id = run_id or f"grpo-{int(time.time())}"
        output_dir = Path(f"~/.mascarade/finetune/runs/{run_id}").expanduser()
        output_dir.mkdir(parents=True, exist_ok=True)

        logger.info("Starting GRPO training: model=%s, %d prompts", model_path, len(prompts))
        start = time.time()

        try:
            from trl import GRPOConfig, GRPOTrainer
        except ImportError:
            raise RuntimeError("GRPO requires trl >= 0.24. Install with: pip install trl>=0.24")

        from datasets import Dataset

        dataset = Dataset.from_dict({"prompt": prompts})

        if reward_fn is None:
            reward_fn = self._default_code_reward

        training_args = GRPOConfig(
            output_dir=str(output_dir),
            num_train_epochs=num_epochs,
            per_device_train_batch_size=2,
            gradient_accumulation_steps=4,
            learning_rate=learning_rate,
            bf16=True,
            logging_steps=10,
            save_strategy="epoch",
            report_to="none",
            max_completion_length=max_length,
            num_generations=num_generations,
        )

        try:
            from unsloth import FastLanguageModel
            model, tokenizer = FastLanguageModel.from_pretrained(
                model_name=model_path,
                max_seq_length=max_length * 2,
                load_in_4bit=True,
            )
            model = FastLanguageModel.get_peft_model(
                model, r=16, lora_alpha=32, lora_dropout=0.05,
                target_modules=["q_proj", "v_proj"],
                use_gradient_checkpointing="unsloth",
            )
            logger.info("Using Unsloth backend for GRPO")
        except ImportError:
            import torch
            from transformers import AutoModelForCausalLM, AutoTokenizer
            model = AutoModelForCausalLM.from_pretrained(
                model_path, torch_dtype=torch.bfloat16, device_map="auto",
            )
            tokenizer = AutoTokenizer.from_pretrained(model_path)
            if tokenizer.pad_token is None:
                tokenizer.pad_token = tokenizer.eos_token
            logger.info("Using standard transformers backend for GRPO")

        trainer = GRPOTrainer(
            model=model,
            args=training_args,
            train_dataset=dataset,
            processing_class=tokenizer,
            reward_funcs=reward_fn,
        )

        trainer.train()
        trainer.save_model(str(output_dir / "grpo"))
        tokenizer.save_pretrained(str(output_dir / "grpo"))

        elapsed = time.time() - start
        logs = trainer.state.log_history
        final_loss = logs[-1].get("loss", 0.0) if logs else 0.0

        result = {
            "output_dir": str(output_dir),
            "method": "grpo",
            "training_time_seconds": round(elapsed, 1),
            "final_loss": round(final_loss, 4),
            "model_path": str(output_dir / "grpo"),
        }
        (output_dir / "grpo_result.json").write_text(json.dumps(result, indent=2, default=str))
        logger.info("GRPO training complete in %.0fs, loss=%.4f → %s", elapsed, final_loss, output_dir)
        return result

    @staticmethod
    def _default_code_reward(completions: list[list[dict]], prompts: list[str], **kwargs) -> list[float]:
        """Simple reward function for code generation quality."""
        rewards = []
        for completion_group in completions:
            text = completion_group[0].get("content", "") if completion_group else ""
            score = 0.0
            if len(text) > 50:
                score += 0.3
            if "def " in text or "class " in text or "function" in text:
                score += 0.3
            if "return" in text:
                score += 0.2
            if not ReinforcerAgent._is_repetitive(text):
                score += 0.2
            rewards.append(score)
        return rewards

    @staticmethod
    def _is_repetitive(text: str, threshold: float = 0.5) -> bool:
        """Check if text has too many repeated n-grams."""
        words = text.split()
        if len(words) < 10:
            return False
        trigrams = [" ".join(words[i:i+3]) for i in range(len(words)-2)]
        unique_ratio = len(set(trigrams)) / len(trigrams) if trigrams else 1.0
        return unique_ratio < threshold
