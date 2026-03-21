"""Unsloth fine-tuning module.

Provides optimized 4-bit quantized fine-tuning using the Unsloth library.
Features gradient checkpointing and memory-efficient training for consumer GPUs.

Example:
    >>> from unsloth import UnslothPipeline, UnslothConfig
    >>> config = UnslothConfig(model_name="unsloth/qwen2.5-coder-1.5b-bnb-4bit")
    >>> pipeline = UnslothPipeline(config)
    >>> pipeline.load_model()
    >>> # ... prepare dataset and train
"""

from .config import UNSLOTH_MODEL_CONFIGS, UnslothConfig, get_config
from .pipeline import UnslothPipeline

__all__ = [
    "UnslothPipeline",
    "UnslothConfig",
    "get_config",
    "UNSLOTH_MODEL_CONFIGS",
]
