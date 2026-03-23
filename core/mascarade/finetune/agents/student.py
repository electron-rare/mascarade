"""Student agent — fine-tunes models with LoRA/QLoRA.

Supports two GPU backends:
- trl/peft: Standard HuggingFace stack
- unsloth: 2-5x faster, 70% less VRAM (recommended)
"""

from __future__ import annotations

import json
import logging
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger("mascarade.finetune.student")


def _has_unsloth() -> bool:
    """Check if unsloth is available at import time."""
    try:
        import unsloth  # noqa: F401
        return True
    except ImportError:
        return False


@dataclass
class LoRAConfig:
    r: int = 16
    lora_alpha: int = 32
    lora_dropout: float = 0.05
    target_modules: list[str] = field(default_factory=lambda: ["q_proj", "v_proj"])
    learning_rate: float = 2e-4
    num_epochs: int = 3
    batch_size: int = 4
    gradient_accumulation_steps: int = 4
    max_seq_length: int = 2048
    quantization: str = "4bit"  # "4bit", "8bit", "none"
    backend: str = "auto"  # "auto", "unsloth", "trl"


@dataclass
class TrainingResult:
    output_dir: str
    base_model: str
    dataset: str
    method: str
    training_time_seconds: float = 0.0
    final_loss: float = 0.0
    metrics: dict = field(default_factory=dict)


class StudentAgent:
    """Fine-tunes models using LoRA/QLoRA with trl or llama.cpp.

    Supports two backends:
    - trl/peft: For GPU (CUDA) or Metal (MPS) training
    - llama.cpp: For CPU-based fine-tuning of GGUF models

    P2P capability: ft-student
    """

    def __init__(self, *, output_base: Path | str = "~/.mascarade/finetune/runs"):
        self.output_base = Path(output_base).expanduser()
        self.output_base.mkdir(parents=True, exist_ok=True)

    def _resolve_backend(self, config: LoRAConfig) -> str:
        """Resolve which backend to use: unsloth or trl."""
        if config.backend == "unsloth":
            if not _has_unsloth():
                raise RuntimeError("Unsloth requested but not installed")
            return "unsloth"
        if config.backend == "trl":
            return "trl"
        # auto: prefer unsloth if available and on CUDA
        import torch
        if _has_unsloth() and torch.cuda.is_available():
            logger.info("Auto-selected Unsloth backend (CUDA available)")
            return "unsloth"
        logger.info("Auto-selected trl backend")
        return "trl"

    async def train_lora(
        self,
        base_model: str,
        dataset_path: str,
        config: LoRAConfig,
        *,
        run_id: str | None = None,
    ) -> TrainingResult:
        """Train a LoRA adapter. Auto-selects Unsloth (faster) or trl backend."""
        backend = self._resolve_backend(config)
        if backend == "unsloth":
            return await self._train_unsloth(base_model, dataset_path, config, run_id=run_id)
        return await self._train_trl(base_model, dataset_path, config, run_id=run_id)

    async def _train_unsloth(
        self,
        base_model: str,
        dataset_path: str,
        config: LoRAConfig,
        *,
        run_id: str | None = None,
    ) -> TrainingResult:
        """Train using Unsloth — 2-5x faster, 70% less VRAM than trl."""
        from trl import SFTConfig, SFTTrainer
        from unsloth import FastLanguageModel

        run_id = run_id or f"unsloth-{int(time.time())}"
        output_dir = self.output_base / run_id
        output_dir.mkdir(parents=True, exist_ok=True)

        logger.info("Starting Unsloth training: model=%s dataset=%s → %s", base_model, dataset_path, output_dir)
        start = time.time()

        # Unsloth handles quantization internally
        load_in_4bit = config.quantization == "4bit"
        model, tokenizer = FastLanguageModel.from_pretrained(
            model_name=base_model,
            max_seq_length=config.max_seq_length,
            load_in_4bit=load_in_4bit,
            dtype=None,  # auto-detect
        )

        model = FastLanguageModel.get_peft_model(
            model,
            r=config.r,
            lora_alpha=config.lora_alpha,
            lora_dropout=config.lora_dropout,
            target_modules=config.target_modules,
            use_gradient_checkpointing="unsloth",  # 30% less VRAM
        )

        training_args = SFTConfig(
            output_dir=str(output_dir),
            num_train_epochs=config.num_epochs,
            per_device_train_batch_size=config.batch_size,
            gradient_accumulation_steps=config.gradient_accumulation_steps,
            learning_rate=config.learning_rate,
            bf16=True,
            logging_steps=10,
            save_strategy="epoch",
            report_to="none",
            max_length=config.max_seq_length,
            warmup_ratio=0.03,
            optim="adamw_8bit",
            seed=42,
        )

        dataset = self._load_dataset(dataset_path)

        trainer = SFTTrainer(
            model=model,
            args=training_args,
            train_dataset=dataset,
            processing_class=tokenizer,
        )

        trainer.train()
        # Save LoRA adapter
        model.save_pretrained(str(output_dir / "adapter"))
        tokenizer.save_pretrained(str(output_dir / "adapter"))

        elapsed = time.time() - start
        logs = trainer.state.log_history
        final_loss = logs[-1].get("loss", 0.0) if logs else 0.0

        result = TrainingResult(
            output_dir=str(output_dir),
            base_model=base_model,
            dataset=dataset_path,
            method=f"unsloth-qlora-{config.quantization}" if load_in_4bit else "unsloth-lora",
            training_time_seconds=round(elapsed, 1),
            final_loss=round(final_loss, 4),
            metrics={"epochs": config.num_epochs, "lr": config.learning_rate, "backend": "unsloth"},
        )

        (output_dir / "result.json").write_text(json.dumps(result.__dict__, indent=2, default=str))
        logger.info("Unsloth training complete in %.0fs, loss=%.4f → %s", elapsed, final_loss, output_dir)
        return result

    async def _train_trl(
        self,
        base_model: str,
        dataset_path: str,
        config: LoRAConfig,
        *,
        run_id: str | None = None,
    ) -> TrainingResult:
        """Train using standard trl/peft stack."""
        import torch
        from peft import LoraConfig as PeftLoraConfig
        from transformers import (
            AutoModelForCausalLM,
            AutoTokenizer,
            BitsAndBytesConfig,
        )
        from trl import SFTConfig, SFTTrainer

        run_id = run_id or f"lora-{int(time.time())}"
        output_dir = self.output_base / run_id
        output_dir.mkdir(parents=True, exist_ok=True)

        logger.info("Starting trl training: model=%s dataset=%s → %s", base_model, dataset_path, output_dir)
        start = time.time()

        bnb_config = None
        if config.quantization == "4bit":
            bnb_config = BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_quant_type="nf4",
                bnb_4bit_compute_dtype=torch.bfloat16,
            )
        elif config.quantization == "8bit":
            bnb_config = BitsAndBytesConfig(load_in_8bit=True)

        device_map = "auto"
        if torch.backends.mps.is_available():
            device_map = "mps"
            bnb_config = None

        tokenizer = AutoTokenizer.from_pretrained(base_model)
        if tokenizer.pad_token is None:
            tokenizer.pad_token = tokenizer.eos_token

        model = AutoModelForCausalLM.from_pretrained(
            base_model,
            quantization_config=bnb_config,
            device_map=device_map,
            torch_dtype=torch.bfloat16,
        )

        lora_config = PeftLoraConfig(
            r=config.r,
            lora_alpha=config.lora_alpha,
            lora_dropout=config.lora_dropout,
            target_modules=config.target_modules,
            task_type="CAUSAL_LM",
        )

        use_bf16 = torch.cuda.is_available() and not torch.backends.mps.is_available()
        training_args = SFTConfig(
            output_dir=str(output_dir),
            num_train_epochs=config.num_epochs,
            per_device_train_batch_size=config.batch_size,
            gradient_accumulation_steps=config.gradient_accumulation_steps,
            learning_rate=config.learning_rate,
            bf16=use_bf16,
            logging_steps=10,
            save_strategy="epoch",
            report_to="none",
            max_length=config.max_seq_length,
        )

        dataset = self._load_dataset(dataset_path)

        trainer = SFTTrainer(
            model=model,
            args=training_args,
            train_dataset=dataset,
            peft_config=lora_config,
            processing_class=tokenizer,
        )

        trainer.train()
        trainer.save_model(str(output_dir / "adapter"))
        tokenizer.save_pretrained(str(output_dir / "adapter"))

        elapsed = time.time() - start
        logs = trainer.state.log_history
        final_loss = logs[-1].get("loss", 0.0) if logs else 0.0

        result = TrainingResult(
            output_dir=str(output_dir),
            base_model=base_model,
            dataset=dataset_path,
            method="lora" if config.quantization == "none" else f"qlora-{config.quantization}",
            training_time_seconds=round(elapsed, 1),
            final_loss=round(final_loss, 4),
            metrics={"epochs": config.num_epochs, "lr": config.learning_rate, "backend": "trl"},
        )

        (output_dir / "result.json").write_text(json.dumps(result.__dict__, indent=2, default=str))
        logger.info("trl training complete in %.0fs, loss=%.4f → %s", elapsed, final_loss, output_dir)
        return result

    @staticmethod
    def _load_dataset(dataset_path: str):
        """Load dataset from local file or HuggingFace Hub."""
        from datasets import load_dataset as _load_dataset
        if Path(dataset_path).exists():
            if dataset_path.endswith(".jsonl"):
                return _load_dataset("json", data_files=dataset_path, split="train")
            return _load_dataset(dataset_path, split="train")
        return _load_dataset(dataset_path, split="train")

    async def train_llamacpp(
        self,
        gguf_model: str,
        dataset_path: str,
        *,
        run_id: str | None = None,
        n_epochs: int = 3,
        n_ctx: int = 2048,
        n_batch: int = 32,
    ) -> TrainingResult:
        """Fine-tune using llama.cpp finetune binary (CPU-based, GGUF models)."""
        run_id = run_id or f"llamacpp-{int(time.time())}"
        output_dir = self.output_base / run_id
        output_dir.mkdir(parents=True, exist_ok=True)

        lora_out = output_dir / "ggml-lora-adapter.bin"
        logger.info("Starting llama.cpp fine-tune: model=%s → %s", gguf_model, lora_out)
        start = time.time()

        cmd = [
            "llama-finetune",
            "--model", gguf_model,
            "--train-data", dataset_path,
            "--lora-out", str(lora_out),
            "--epochs", str(n_epochs),
            "--ctx", str(n_ctx),
            "--batch", str(n_batch),
            "--threads", "4",
        ]

        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=7200)
        elapsed = time.time() - start

        if proc.returncode != 0:
            logger.error("llama.cpp finetune failed: %s", proc.stderr[-500:])
            return TrainingResult(
                output_dir=str(output_dir),
                base_model=gguf_model,
                dataset=dataset_path,
                method="llamacpp",
                training_time_seconds=round(elapsed, 1),
                metrics={"error": proc.stderr[-500:]},
            )

        result = TrainingResult(
            output_dir=str(output_dir),
            base_model=gguf_model,
            dataset=dataset_path,
            method="llamacpp",
            training_time_seconds=round(elapsed, 1),
        )
        (output_dir / "result.json").write_text(json.dumps(result.__dict__, indent=2, default=str))
        logger.info("llama.cpp fine-tune complete in %.0fs → %s", elapsed, lora_out)
        return result

    async def merge_and_quantize(
        self,
        base_model: str,
        adapter_path: str,
        *,
        quant_method: str = "Q4_K_M",
        output_gguf: str | None = None,
    ) -> str:
        """Merge LoRA adapter into base model and export to GGUF.

        If Unsloth is available, uses its native GGUF export (fastest).
        Otherwise, merges via peft then converts with llama.cpp.
        """
        merged_dir = self.output_base / "merged"
        merged_dir.mkdir(parents=True, exist_ok=True)
        if output_gguf is None:
            output_gguf = str(merged_dir / f"model-{quant_method}.gguf")

        logger.info("Merge+quantize: %s + %s → %s (%s)", base_model, adapter_path, output_gguf, quant_method)

        if _has_unsloth():
            return await self._export_gguf_unsloth(base_model, adapter_path, output_gguf, quant_method)
        return await self._export_gguf_peft(base_model, adapter_path, output_gguf, quant_method)

    async def _export_gguf_unsloth(
        self, base_model: str, adapter_path: str, output_gguf: str, quant_method: str,
    ) -> str:
        """Export GGUF using Unsloth's native save_pretrained_gguf."""
        from unsloth import FastLanguageModel

        model, tokenizer = FastLanguageModel.from_pretrained(
            model_name=adapter_path,
            max_seq_length=2048,
            load_in_4bit=True,
        )
        model.save_pretrained_gguf(
            output_gguf.replace(".gguf", ""),
            tokenizer,
            quantization_method=quant_method.lower().replace("_", "-"),
        )
        logger.info("Unsloth GGUF export complete → %s", output_gguf)
        return output_gguf

    async def _export_gguf_peft(
        self, base_model: str, adapter_path: str, output_gguf: str, quant_method: str,
    ) -> str:
        """Merge via peft then convert with llama.cpp convert script."""
        import shutil

        import torch
        from peft import PeftModel
        from transformers import AutoModelForCausalLM, AutoTokenizer

        merged_hf_dir = str(Path(output_gguf).parent / "merged_hf")
        Path(merged_hf_dir).mkdir(parents=True, exist_ok=True)

        logger.info("Merging adapter into base model (peft)...")
        base = AutoModelForCausalLM.from_pretrained(base_model, torch_dtype=torch.float16)
        model = PeftModel.from_pretrained(base, adapter_path)
        merged = model.merge_and_unload()
        merged.save_pretrained(merged_hf_dir)
        tokenizer = AutoTokenizer.from_pretrained(adapter_path)
        tokenizer.save_pretrained(merged_hf_dir)

        convert_script = shutil.which("llama-convert") or shutil.which("convert_hf_to_gguf.py")
        if not convert_script:
            logger.warning("No GGUF convert tool found, returning merged HF dir: %s", merged_hf_dir)
            return merged_hf_dir

        logger.info("Converting to GGUF with %s...", convert_script)
        proc = subprocess.run(
            [convert_script, merged_hf_dir, "--outfile", output_gguf, "--outtype", quant_method],
            capture_output=True, text=True, timeout=600,
        )
        if proc.returncode != 0:
            logger.error("GGUF conversion failed: %s", proc.stderr[-300:])
            return merged_hf_dir

        logger.info("GGUF export complete → %s", output_gguf)
        return output_gguf
