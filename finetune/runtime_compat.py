#!/usr/bin/env python3
"""Compatibility helpers for the local fine-tuning stack."""

from __future__ import annotations

from functools import lru_cache


@lru_cache(maxsize=1)
def disable_broken_torchvision() -> str | None:
    """Disable torchvision inside transformers when the install is broken.

    The local training flows are text-only. A mismatched torchvision build can
    break `peft` imports through transformers, even though none of the training
    code needs vision features.
    """

    try:
        from transformers.utils import import_utils
    except Exception:
        return None

    if not import_utils.is_torchvision_available():
        return None

    try:
        import torchvision  # noqa: F401
    except Exception as exc:
        import_utils._torchvision_available = False
        return (
            "torchvision disabled for text-only training "
            f"({exc.__class__.__name__}: {exc})"
        )

    return None
