"""RLVR — Reinforcement Learning with Verifiable Rewards.

Domain-specific reward functions and GRPO/DAPO trainer for mascarade finetune pipeline.
"""

from mascarade.finetune.rlvr.reward_functions import (
    RewardFunction,
    RewardResult,
    CodeCompilationReward,
    JSONValidationReward,
)
from mascarade.finetune.rlvr.kicad_verifier import KiCadDRCReward
from mascarade.finetune.rlvr.trainer import RLVRConfig, RLVRResult, RLVRTrainer

__all__ = [
    "RewardFunction",
    "RewardResult",
    "CodeCompilationReward",
    "JSONValidationReward",
    "KiCadDRCReward",
    "RLVRConfig",
    "RLVRResult",
    "RLVRTrainer",
]
