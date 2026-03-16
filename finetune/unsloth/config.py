#!/usr/bin/env python3
"""Unsloth fine-tuning configuration.

Provides configuration for 4-bit quantized fine-tuning with gradient checkpointing
using the Unsloth library for optimized GPU training.
"""

from dataclasses import dataclass, field
from typing import Literal


@dataclass
class UnslothConfig:
    """Configuration for Unsloth-based fine-tuning.

    Unsloth provides optimized 4-bit quantization and gradient checkpointing
    for efficient fine-tuning on consumer GPUs.
    """

    # Model configuration
    model_name: str = "unsloth/qwen2.5-coder-1.5b-bnb-4bit"
    max_seq_length: int = 2048
    load_in_4bit: bool = True

    # LoRA configuration
    lora_r: int = 16
    lora_alpha: int = 16
    lora_dropout: float = 0.0
    target_modules: list[str] = field(default_factory=lambda: [
        "q_proj", "k_proj", "v_proj", "o_proj",
        "gate_proj", "up_proj", "down_proj"
    ])
    use_gradient_checkpointing: bool = True

    # Training configuration
    per_device_train_batch_size: int = 2
    gradient_accumulation_steps: int = 4
    warmup_steps: int = 10
    num_train_epochs: int = 1
    learning_rate: float = 2e-4
    fp16: bool = False
    bf16: bool = True

    # Optimizer configuration
    optim: Literal["adamw_8bit", "paged_adamw_8bit"] = "adamw_8bit"
    weight_decay: float = 0.01
    lr_scheduler_type: Literal["linear", "cosine", "constant"] = "linear"

    # Logging and checkpointing
    logging_steps: int = 1
    save_strategy: Literal["steps", "epoch", "no"] = "steps"
    save_steps: int = 100
    save_total_limit: int = 2

    # Output
    output_dir: str = "./unsloth_output"
    seed: int = 42

    def to_training_args_dict(self) -> dict:
        """Convert to TrainingArguments compatible dict."""
        return {
            "per_device_train_batch_size": self.per_device_train_batch_size,
            "gradient_accumulation_steps": self.gradient_accumulation_steps,
            "warmup_steps": self.warmup_steps,
            "num_train_epochs": self.num_train_epochs,
            "learning_rate": self.learning_rate,
            "fp16": self.fp16,
            "bf16": self.bf16,
            "logging_steps": self.logging_steps,
            "optim": self.optim,
            "weight_decay": self.weight_decay,
            "lr_scheduler_type": self.lr_scheduler_type,
            "save_strategy": self.save_strategy,
            "save_steps": self.save_steps,
            "save_total_limit": self.save_total_limit,
            "output_dir": self.output_dir,
            "seed": self.seed,
        }


# Default configurations for common models
UNSLOTH_MODEL_CONFIGS = {
    "qwen2.5-coder-1.5b": UnslothConfig(
        model_name="unsloth/qwen2.5-coder-1.5b-bnb-4bit",
        max_seq_length=2048,
        lora_r=16,
        lora_alpha=16,
    ),
    "qwen2.5-coder-7b": UnslothConfig(
        model_name="unsloth/qwen2.5-coder-7b-bnb-4bit",
        max_seq_length=2048,
        lora_r=32,
        lora_alpha=32,
        per_device_train_batch_size=1,
        gradient_accumulation_steps=8,
    ),
    "llama-3.2-1b": UnslothConfig(
        model_name="unsloth/Llama-3.2-1B-bnb-4bit",
        max_seq_length=2048,
        lora_r=16,
        lora_alpha=16,
    ),
    "llama-3.2-3b": UnslothConfig(
        model_name="unsloth/Llama-3.2-3B-bnb-4bit",
        max_seq_length=2048,
        lora_r=16,
        lora_alpha=16,
        per_device_train_batch_size=1,
        gradient_accumulation_steps=8,
    ),
    "mistral-7b": UnslothConfig(
        model_name="unsloth/mistral-7b-v0.3-bnb-4bit",
        max_seq_length=2048,
        lora_r=32,
        lora_alpha=32,
        per_device_train_batch_size=1,
        gradient_accumulation_steps=8,
    ),
}


def get_config(model_key: str) -> UnslothConfig:
    """Get a pre-configured UnslothConfig for a known model.

    Args:
        model_key: Key for the model configuration (e.g., "qwen2.5-coder-1.5b")

    Returns:
        UnslothConfig instance

    Raises:
        KeyError: If model_key is not found
    """
    if model_key not in UNSLOTH_MODEL_CONFIGS:
        available = ", ".join(UNSLOTH_MODEL_CONFIGS.keys())
        raise KeyError(
            f"Unknown model key: {model_key}. "
            f"Available models: {available}"
        )
    return UNSLOTH_MODEL_CONFIGS[model_key]
