"""Reinforcer agent — DPO/SimPO/KTO/RLHF improvement cycles."""

from __future__ import annotations

import hashlib
import json
import logging
import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx

from mascarade.config import settings

logger = logging.getLogger("mascarade.finetune.reinforcer")


@dataclass
class DPOPair:
    prompt: str
    chosen: str
    rejected: str
    persona: str = ""
    project_id: str = ""
    source: str = "local"


@dataclass
class KTOExample:
    """Single example for KTO training (binary feedback, no pairs needed)."""
    prompt: str
    completion: str
    label: bool  # True = desirable, False = undesirable
    persona: str = ""
    project_id: str = ""
    source: str = "local"


@dataclass
class ReinforcementResult:
    dataset_path: str
    total_pairs: int
    method: str = "dpo"  # "dpo", "simpo", "kto", or "rlvr"
    ready_for_training: bool = True


class ReinforcerAgent:
    """Creates alignment training data from detected errors and triggers re-training.

    Supported alignment methods:
    - DPO: Direct Preference Optimization (preference pairs, requires reference model)
    - SimPO: Simple Preference Optimization (reference-free, length-normalized reward)
    - KTO: Kahneman-Tversky Optimization (binary feedback, no pairs needed)
    - RLVR: Reinforcement Learning with Verifiable Rewards (GRPO/DAPO with domain rewards)

    Workflow:
    1. Analyst detects errors in student output
    2. Reinforcer collects errors
    3. Teacher generates correct (chosen) responses
    4. Reinforcer formats training data (DPO pairs or KTO examples)
    5. Student re-trains with alignment data

    P2P capability: ft-reinforcement
    """

    def __init__(self, *, teacher=None, output_dir: Path | str = "~/.mascarade/finetune/dpo"):
        self.teacher = teacher
        self.output_dir = Path(output_dir).expanduser()
        self.output_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _normalize_scope(
        *,
        project_id: str | None = None,
        federation_scope: list[str] | tuple[str, ...] | None = None,
        knowledge_scope: str = "project",
    ) -> tuple[str, list[str], str]:
        normalized_project = (project_id or settings.mascarade_project_id).strip() or "default"
        normalized_scope = (knowledge_scope or "project").strip().lower() or "project"
        if normalized_scope not in {"project", "federated"}:
            raise ValueError(f"Unsupported knowledge_scope: {knowledge_scope}")

        cleaned_federation = [
            item.strip()
            for item in (federation_scope or [])
            if str(item).strip()
        ]
        if normalized_scope == "project":
            cleaned_federation = [normalized_project]
        elif not cleaned_federation:
            raise ValueError("federation_scope is required when knowledge_scope is federated")
        elif normalized_project not in cleaned_federation:
            cleaned_federation = [normalized_project, *cleaned_federation]

        return normalized_project, list(dict.fromkeys(cleaned_federation)), normalized_scope

    async def collect_kxkm_feedback(
        self,
        persona: str | None = None,
        project_id: str | None = None,
        *,
        federation_scope: list[str] | tuple[str, ...] | None = None,
        knowledge_scope: str = "project",
    ) -> list[DPOPair]:
        normalized_project, normalized_federation, normalized_scope = self._normalize_scope(
            project_id=project_id,
            federation_scope=federation_scope,
            knowledge_scope=knowledge_scope,
        )
        selected_persona = (persona or settings.kxkm_dpo_persona).strip()
        if not selected_persona:
            return []

        base_url = settings.kxkm_rag_url.strip().rstrip("/")
        if not base_url:
            logger.warning("KXKM_RAG_URL is not configured, skipping kxkm DPO feedback")
            return []

        async with httpx.AsyncClient(timeout=settings.kxkm_timeout_seconds) as client:
            response = await client.get(
                f"{base_url}/api/v2/export/dpo",
                params={
                    "persona": selected_persona,
                    "project_id": normalized_project,
                    "knowledge_scope": normalized_scope,
                    "federation_scope": ",".join(normalized_federation),
                },
                headers={
                    "x-mascarade-project-id": normalized_project,
                    "x-mascarade-knowledge-scope": normalized_scope,
                    "x-mascarade-federation-scope": ",".join(normalized_federation),
                },
            )
            response.raise_for_status()
            payload = response.json()

        data = payload.get("data", payload) if isinstance(payload, dict) else {}
        raw_pairs = data.get("pairs") or []
        normalized_pairs: list[DPOPair] = []
        for pair in raw_pairs:
            if not isinstance(pair, dict):
                continue
            prompt = str(pair.get("prompt") or "").strip()
            chosen = str(pair.get("chosen") or "").strip()
            rejected = str(pair.get("rejected") or "").strip()
            if not prompt or not chosen or not rejected:
                continue
            normalized_pairs.append(
                DPOPair(
                    prompt=prompt,
                    chosen=chosen,
                    rejected=rejected,
                    persona=str(pair.get("persona") or selected_persona).strip(),
                    project_id=str(pair.get("project_id") or normalized_project).strip() or normalized_project,
                    source="kxkm",
                )
            )
        return normalized_pairs

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
        persona: str | None = None,
        project_id: str | None = None,
        federation_scope: list[str] | tuple[str, ...] | None = None,
        knowledge_scope: str = "project",
        include_kxkm_feedback: bool = True,
    ) -> ReinforcementResult:
        """Generate DPO training pairs from collected errors.

        Uses Teacher agent to generate the 'chosen' (correct) responses.
        The 'rejected' responses come from the student model's errors.
        """
        run_id = run_id or f"dpo-{int(time.time())}"
        output_path = self.output_dir / f"{run_id}.jsonl"
        combined_pairs: list[DPOPair] = []

        if errors:
            if self.teacher is None:
                raise RuntimeError("ReinforcerAgent requires a TeacherAgent for DPO pair generation")

            from mascarade.finetune.agents.teacher import TeacherConfig
            await self.teacher.generate_corrections(
                errors=errors,
                config=TeacherConfig(task_description="Generate correct response for DPO training"),
                output_path=output_path,
            )
            combined_pairs.extend(self._load_pairs(output_path, source="teacher"))

        if include_kxkm_feedback:
            try:
                combined_pairs.extend(
                    await self.collect_kxkm_feedback(
                        persona=persona,
                        project_id=project_id,
                        federation_scope=federation_scope,
                        knowledge_scope=knowledge_scope,
                    )
                )
            except Exception as exc:
                logger.warning("Failed to collect kxkm DPO feedback: %s", exc)

        deduped_pairs = self._dedupe_pairs(combined_pairs)
        with open(output_path, "w", encoding="utf-8") as handle:
            for pair in deduped_pairs:
                handle.write(json.dumps(pair, ensure_ascii=False) + "\n")

        return ReinforcementResult(
            dataset_path=str(output_path),
            total_pairs=len(deduped_pairs),
        )

    @staticmethod
    def _load_pairs(path: Path, *, source: str) -> list[DPOPair]:
        if not path.exists():
            return []
        pairs: list[DPOPair] = []
        for raw_line in path.read_text(encoding="utf-8").splitlines():
            if not raw_line.strip():
                continue
            data = json.loads(raw_line)
            prompt = str(data.get("prompt") or "").strip()
            chosen = str(data.get("chosen") or "").strip()
            rejected = str(data.get("rejected") or "").strip()
            if not prompt or not chosen or not rejected:
                continue
            pairs.append(
                DPOPair(
                    prompt=prompt,
                    chosen=chosen,
                    rejected=rejected,
                    persona=str(data.get("persona") or settings.kxkm_dpo_persona).strip(),
                    project_id=str(data.get("project_id") or settings.mascarade_project_id).strip(),
                    source=str(data.get("source") or source).strip() or source,
                )
            )
        return pairs

    @staticmethod
    def _pair_key(pair: DPOPair) -> str:
        payload = {
            "prompt": pair.prompt,
            "chosen": pair.chosen,
            "rejected": pair.rejected,
            "persona": pair.persona,
            "project_id": pair.project_id,
        }
        return hashlib.sha256(
            json.dumps(payload, sort_keys=True, ensure_ascii=True).encode("utf-8")
        ).hexdigest()

    def _dedupe_pairs(self, pairs: list[DPOPair]) -> list[dict[str, Any]]:
        seen: set[str] = set()
        output: list[dict[str, Any]] = []
        for pair in pairs:
            key = self._pair_key(pair)
            if key in seen:
                continue
            seen.add(key)
            output.append(
                {
                    "prompt": pair.prompt,
                    "chosen": pair.chosen,
                    "rejected": pair.rejected,
                    "persona": pair.persona,
                    "project_id": pair.project_id or settings.mascarade_project_id,
                    "source": pair.source,
                }
            )
        return output

    async def train_alignment(
        self,
        model_path: str,
        dataset_path: str,
        *,
        method: str = "simpo",
        run_id: str | None = None,
        beta: float | None = None,
        gamma: float = 0.5,
        learning_rate: float = 5e-7,
        num_epochs: int = 1,
        max_length: int = 1024,
        desirable_weight: float = 1.0,
        undesirable_weight: float = 1.0,
    ) -> dict:
        """Run alignment training using the specified method.

        Supported methods:
        - "dpo": Direct Preference Optimization (preference pairs, reference model)
        - "simpo": Simple Preference Optimization (reference-free, length-normalized)
        - "kto": Kahneman-Tversky Optimization (binary feedback, no pairs needed)

        Default beta values per method: dpo=0.1, simpo=2.0, kto=0.1
        """
        valid_methods = {"dpo", "simpo", "kto", "rlvr"}
        if method not in valid_methods:
            raise ValueError(f"Unknown alignment method '{method}', must be one of {valid_methods}")

        if method == "rlvr":
            return await self._train_rlvr(
                model_path, dataset_path,
                run_id=run_id,
                learning_rate=learning_rate,
                num_epochs=num_epochs,
                max_length=max_length,
                beta=beta if beta is not None else 0.04,
            )

        if method == "kto":
            return await self._train_kto(
                model_path, dataset_path,
                run_id=run_id,
                beta=beta if beta is not None else 0.1,
                learning_rate=learning_rate,
                num_epochs=num_epochs,
                max_length=max_length,
                desirable_weight=desirable_weight,
                undesirable_weight=undesirable_weight,
            )

        if method == "simpo":
            return await self._train_simpo(
                model_path, dataset_path,
                run_id=run_id,
                beta=beta if beta is not None else 2.0,
                gamma=gamma,
                learning_rate=learning_rate,
                num_epochs=num_epochs,
                max_length=max_length,
            )

        # Default: DPO
        return await self._train_dpo(
            model_path, dataset_path,
            run_id=run_id,
            beta=beta if beta is not None else 0.1,
            learning_rate=learning_rate,
            num_epochs=num_epochs,
            max_length=max_length,
        )

    async def _train_rlvr(
        self,
        model_path: str,
        dataset_path: str,
        *,
        run_id: str | None = None,
        beta: float = 0.04,
        learning_rate: float = 1e-6,
        num_epochs: int = 3,
        max_length: int = 2048,
        reward_functions: list[str] | None = None,
        loss_type: str = "dapo",
        num_generations: int = 16,
    ) -> dict:
        """Run RLVR alignment using GRPO/DAPO with verifiable reward functions.

        RLVR (Reinforcement Learning with Verifiable Rewards):
        - Uses domain-specific programmatic rewards (code compilation, KiCad DRC, etc.)
        - No human preference data needed — self-improving via verifiable checks
        - Supports GRPO and DAPO loss types
        - Works with QLoRA via Unsloth for low-VRAM training
        """
        from mascarade.finetune.rlvr.trainer import RLVRConfig, RLVRTrainer

        config = RLVRConfig(
            base_model=model_path,
            reward_functions=reward_functions or ["code_compilation"],
            num_generations=num_generations,
            loss_type=loss_type,
            max_completion_length=max_length,
            learning_rate=learning_rate,
            num_epochs=num_epochs,
            batch_size=4,
            beta=beta,
        )

        trainer = RLVRTrainer()
        result = await trainer.train(config, dataset_path)

        return {
            "output_dir": result.output_dir,
            "method": "rlvr",
            "training_time_seconds": result.training_time_seconds,
            "final_loss": result.final_loss,
            "final_reward_mean": result.final_reward_mean,
            "model_path": result.model_path,
            "reward_functions": result.reward_functions,
        }

    async def _train_dpo(
        self,
        model_path: str,
        dataset_path: str,
        *,
        run_id: str | None = None,
        beta: float = 0.1,
        learning_rate: float = 5e-7,
        num_epochs: int = 1,
        max_length: int = 1024,
    ) -> dict:
        """Run standard DPO alignment (preference pairs, reference model)."""
        from trl import DPOConfig, DPOTrainer

        run_id = run_id or f"dpo-{int(time.time())}"
        output_dir = Path(f"~/.mascarade/finetune/runs/{run_id}").expanduser()
        output_dir.mkdir(parents=True, exist_ok=True)

        logger.info("Starting DPO alignment: model=%s dataset=%s", model_path, dataset_path)
        start = time.time()

        dataset = self._load_alignment_dataset(dataset_path)

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
            loss_type="sigmoid",
            beta=beta,
        )

        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer

        tokenizer = AutoTokenizer.from_pretrained(model_path)
        if tokenizer.pad_token is None:
            tokenizer.pad_token = tokenizer.eos_token

        model = AutoModelForCausalLM.from_pretrained(
            model_path, torch_dtype=torch.bfloat16, device_map="auto",
        )

        trainer = DPOTrainer(
            model=model,
            ref_model=model,
            args=training_args,
            train_dataset=dataset,
            processing_class=tokenizer,
        )

        return self._run_trainer(trainer, tokenizer, output_dir, "dpo", start)

    async def _train_simpo(
        self,
        model_path: str,
        dataset_path: str,
        *,
        run_id: str | None = None,
        beta: float = 2.0,
        gamma: float = 0.5,
        learning_rate: float = 5e-7,
        num_epochs: int = 1,
        max_length: int = 1024,
    ) -> dict:
        """Run SimPO alignment (reference-free, length-normalized reward).

        SimPO (Simple Preference Optimization):
        - No reference model needed -> 50% less VRAM
        - +6.4 over DPO on AlpacaEval benchmarks
        - beta: reward margin scaling, gamma: length normalization bonus

        Tries dedicated SimPOTrainer/SimPOConfig first (trl>=0.25),
        falls back to DPOTrainer with loss_type="simpo" for older trl versions.
        """
        run_id = run_id or f"simpo-{int(time.time())}"
        output_dir = Path(f"~/.mascarade/finetune/runs/{run_id}").expanduser()
        output_dir.mkdir(parents=True, exist_ok=True)

        logger.info("Starting SimPO alignment: model=%s dataset=%s beta=%.1f gamma=%.1f",
                     model_path, dataset_path, beta, gamma)
        start = time.time()

        dataset = self._load_alignment_dataset(dataset_path)

        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer

        tokenizer = AutoTokenizer.from_pretrained(model_path)
        if tokenizer.pad_token is None:
            tokenizer.pad_token = tokenizer.eos_token

        model = AutoModelForCausalLM.from_pretrained(
            model_path, torch_dtype=torch.bfloat16, device_map="auto",
        )

        # Try dedicated SimPOTrainer first (trl >= 0.25)
        try:
            from trl import SimPOConfig, SimPOTrainer

            training_args = SimPOConfig(
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
                beta=beta,
                simpo_gamma=gamma,
            )

            trainer = SimPOTrainer(
                model=model,
                args=training_args,
                train_dataset=dataset,
                processing_class=tokenizer,
            )
            logger.info("Using dedicated SimPOTrainer (trl >= 0.25)")

        except ImportError:
            # Fallback: DPOTrainer with loss_type="simpo"
            from trl import DPOConfig, DPOTrainer

            logger.info("SimPOTrainer not available, falling back to DPOTrainer(loss_type='simpo')")

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
                loss_type="simpo",
                beta=beta,
            )
            if hasattr(training_args, "simpo_gamma"):
                training_args.simpo_gamma = gamma

            trainer = DPOTrainer(
                model=model,
                ref_model=None,
                args=training_args,
                train_dataset=dataset,
                processing_class=tokenizer,
            )

        return self._run_trainer(trainer, tokenizer, output_dir, "simpo", start)

    async def _train_kto(
        self,
        model_path: str,
        dataset_path: str,
        *,
        run_id: str | None = None,
        beta: float = 0.1,
        learning_rate: float = 5e-7,
        num_epochs: int = 1,
        max_length: int = 1024,
        desirable_weight: float = 1.0,
        undesirable_weight: float = 1.0,
    ) -> dict:
        """Run KTO alignment (binary feedback, no preference pairs needed).

        KTO (Kahneman-Tversky Optimization):
        - Works with binary feedback (good/bad) instead of preference pairs
        - Useful for production feedback loops where paired comparisons are unavailable
        - Dataset format: {"prompt": str, "completion": str, "label": bool}
        - beta: KL penalty strength
        - desirable_weight / undesirable_weight: balance positive vs negative examples
        """
        try:
            from trl import KTOConfig, KTOTrainer
        except ImportError:
            raise RuntimeError(
                "KTO requires trl >= 0.25. Install with: pip install 'trl>=0.25'"
            )

        run_id = run_id or f"kto-{int(time.time())}"
        output_dir = Path(f"~/.mascarade/finetune/runs/{run_id}").expanduser()
        output_dir.mkdir(parents=True, exist_ok=True)

        logger.info(
            "Starting KTO alignment: model=%s dataset=%s beta=%.2f desirable_w=%.1f undesirable_w=%.1f",
            model_path, dataset_path, beta, desirable_weight, undesirable_weight,
        )
        start = time.time()

        dataset = self._load_alignment_dataset(dataset_path)

        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer

        tokenizer = AutoTokenizer.from_pretrained(model_path)
        if tokenizer.pad_token is None:
            tokenizer.pad_token = tokenizer.eos_token

        model = AutoModelForCausalLM.from_pretrained(
            model_path, torch_dtype=torch.bfloat16, device_map="auto",
        )

        training_args = KTOConfig(
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
            beta=beta,
            desirable_weight=desirable_weight,
            undesirable_weight=undesirable_weight,
        )

        trainer = KTOTrainer(
            model=model,
            args=training_args,
            train_dataset=dataset,
            processing_class=tokenizer,
        )

        return self._run_trainer(trainer, tokenizer, output_dir, "kto", start)

    @staticmethod
    def _load_alignment_dataset(dataset_path: str):
        """Load alignment dataset from local file or HuggingFace Hub."""
        from datasets import load_dataset as _load_dataset
        if Path(dataset_path).exists():
            return _load_dataset("json", data_files=dataset_path, split="train")
        return _load_dataset(dataset_path, split="train")

    def _run_trainer(self, trainer, tokenizer, output_dir: Path, method: str, start: float) -> dict:
        """Execute training and return standardized result dict."""
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
