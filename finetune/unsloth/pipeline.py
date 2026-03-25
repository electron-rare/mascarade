#!/usr/bin/env python3
"""Unsloth fine-tuning pipeline.

Efficient 4-bit quantized fine-tuning pipeline using Unsloth library.
Optimized for consumer GPUs with gradient checkpointing and memory-efficient training.

Usage:
    from unsloth.pipeline import UnslothPipeline
    from unsloth.config import UnslothConfig

    config = UnslothConfig(
        model_name="unsloth/qwen2.5-coder-1.5b-bnb-4bit",
        max_seq_length=2048,
        lora_r=16,
    )

    pipeline = UnslothPipeline(config)
    pipeline.load_model()
    pipeline.prepare_dataset(train_data, eval_data)
    pipeline.train()
    pipeline.save_model("./output")
"""

from __future__ import annotations

import gc
from pathlib import Path
from typing import Any

try:
    import torch

    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False
    torch = None

try:
    from datasets import Dataset

    DATASETS_AVAILABLE = True
except ImportError:
    DATASETS_AVAILABLE = False
    Dataset = None

try:
    from unsloth import FastLanguageModel
    from unsloth import is_bfloat16_supported

    UNSLOTH_AVAILABLE = True
except ImportError:
    UNSLOTH_AVAILABLE = False
    FastLanguageModel = None
    is_bfloat16_supported = None

from .config import UnslothConfig


class UnslothPipeline:
    """Fine-tuning pipeline using Unsloth for optimized 4-bit training.

    Unsloth provides:
    - 4-bit quantization with optimized kernels
    - Gradient checkpointing for memory efficiency
    - 2x faster training compared to standard QLoRA
    - Support for long context (up to 32k tokens)

    Example:
        >>> config = UnslothConfig(model_name="unsloth/qwen2.5-coder-1.5b-bnb-4bit")
        >>> pipeline = UnslothPipeline(config)
        >>> pipeline.load_model()
        >>> pipeline.train()
    """

    def __init__(self, config: UnslothConfig):
        """Initialize the Unsloth pipeline.

        Args:
            config: UnslothConfig instance with training parameters

        Raises:
            ImportError: If required libraries are not installed
        """
        if not TORCH_AVAILABLE:
            raise ImportError("PyTorch not found. Install with: " "pip install torch")

        if not DATASETS_AVAILABLE:
            raise ImportError(
                "Datasets library not found. Install with: " "pip install datasets"
            )

        if not UNSLOTH_AVAILABLE:
            raise ImportError(
                "Unsloth library not found. Install with: " "pip install unsloth"
            )

        self.config = config
        self.model = None
        self.tokenizer = None
        self.trainer = None

    def load_model(self) -> None:
        """Load model and tokenizer with 4-bit quantization.

        Uses Unsloth's FastLanguageModel for optimized loading.
        """
        if self.model is not None:
            return

        dtype = None
        if self.config.bf16 and is_bfloat16_supported():
            dtype = torch.bfloat16
        elif self.config.fp16:
            dtype = torch.float16

        self.model, self.tokenizer = FastLanguageModel.from_pretrained(
            model_name=self.config.model_name,
            max_seq_length=self.config.max_seq_length,
            dtype=dtype,
            load_in_4bit=self.config.load_in_4bit,
        )

        self.model = FastLanguageModel.get_peft_model(
            self.model,
            r=self.config.lora_r,
            target_modules=self.config.target_modules,
            lora_alpha=self.config.lora_alpha,
            lora_dropout=self.config.lora_dropout,
            bias="none",
            use_gradient_checkpointing=self.config.use_gradient_checkpointing,
            random_state=self.config.seed,
        )

    def prepare_dataset(
        self,
        train_dataset: Dataset,
        eval_dataset: Dataset | None = None,
    ) -> None:
        """Prepare datasets for training.

        Args:
            train_dataset: Training dataset (HuggingFace Dataset)
            eval_dataset: Optional evaluation dataset
        """
        self.train_dataset = train_dataset
        self.eval_dataset = eval_dataset

    def train(self) -> dict[str, Any]:
        """Run fine-tuning.

        Returns:
            Training metrics dictionary

        Raises:
            RuntimeError: If model not loaded or dataset not prepared
        """
        if self.model is None:
            raise RuntimeError("Model not loaded. Call load_model() first.")
        if not hasattr(self, "train_dataset"):
            raise RuntimeError("Dataset not prepared. Call prepare_dataset() first.")

        from transformers import TrainingArguments
        from trl import SFTTrainer

        training_args = TrainingArguments(
            **self.config.to_training_args_dict(),
            report_to="none",
        )

        self.trainer = SFTTrainer(
            model=self.model,
            tokenizer=self.tokenizer,
            train_dataset=self.train_dataset,
            eval_dataset=self.eval_dataset,
            dataset_text_field="text",
            max_seq_length=self.config.max_seq_length,
            dataset_num_proc=2,
            packing=False,
            args=training_args,
        )

        self.model.config.use_cache = False

        result = self.trainer.train()

        return {
            "training_loss": result.training_loss,
            "epochs": self.config.num_train_epochs,
            "steps": result.global_step,
        }

    def save_model(
        self,
        output_dir: str | Path,
        save_method: str = "merged_16bit",
    ) -> None:
        """Save the fine-tuned model.

        Args:
            output_dir: Directory to save the model
            save_method: Save format - one of:
                - "merged_16bit": Merge LoRA and save in 16-bit (default)
                - "merged_4bit": Merge LoRA and save in 4-bit
                - "lora": Save only LoRA adapters

        Raises:
            RuntimeError: If model not trained
        """
        if self.model is None:
            raise RuntimeError("No model to save. Train a model first.")

        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        if save_method == "lora":
            self.model.save_pretrained(str(output_path))
            self.tokenizer.save_pretrained(str(output_path))
        elif save_method == "merged_16bit":
            self.model.save_pretrained_merged(
                str(output_path),
                self.tokenizer,
                save_method="merged_16bit",
            )
        elif save_method == "merged_4bit":
            self.model.save_pretrained_merged(
                str(output_path),
                self.tokenizer,
                save_method="merged_4bit",
            )
        else:
            raise ValueError(
                f"Unknown save_method: {save_method}. "
                "Use 'merged_16bit', 'merged_4bit', or 'lora'"
            )

    def save_to_gguf(
        self,
        output_path: str | Path,
        quantization_method: str = "q4_k_m",
    ) -> None:
        """Export model to GGUF format for use with llama.cpp/Ollama.

        Args:
            output_path: Path for the output GGUF file
            quantization_method: GGUF quantization method (q4_k_m, q5_k_m, q8_0, etc.)

        Raises:
            RuntimeError: If model not trained
        """
        if self.model is None:
            raise RuntimeError("No model to export. Train a model first.")

        self.model.save_pretrained_gguf(
            str(output_path),
            self.tokenizer,
            quantization_method=quantization_method,
        )

    def cleanup(self) -> None:
        """Free GPU memory by deleting model and trainer."""
        if self.model is not None:
            del self.model
            self.model = None

        if self.trainer is not None:
            del self.trainer
            self.trainer = None

        if self.tokenizer is not None:
            del self.tokenizer
            self.tokenizer = None

        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - cleanup resources."""
        self.cleanup()
        return False
