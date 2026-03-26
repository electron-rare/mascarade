"""Logging filter that masks secrets in log messages."""

from __future__ import annotations

import logging
import re

# Patterns that look like API keys / tokens / secrets.
_SECRET_PATTERNS = [
    re.compile(r"(sk-ant-api\d{2}-)[A-Za-z0-9_-]{20,}", re.ASCII),
    re.compile(r"(sk-)[A-Za-z0-9_-]{20,}", re.ASCII),
    re.compile(r"(Bearer\s+)[A-Za-z0-9._-]{20,}", re.ASCII | re.IGNORECASE),
    re.compile(r"(ntn_)[A-Za-z0-9_-]{20,}", re.ASCII),
    re.compile(r"(hf_)[A-Za-z0-9_-]{20,}", re.ASCII),
    re.compile(r"(ghp_)[A-Za-z0-9_-]{20,}", re.ASCII),
    re.compile(r"(gho_)[A-Za-z0-9_-]{20,}", re.ASCII),
    re.compile(r"(AKIA)[A-Z0-9]{12,}", re.ASCII),
    re.compile(r"(AIza)[A-Za-z0-9_-]{30,}", re.ASCII),
]


def _mask(match: re.Match) -> str:
    prefix = match.group(1)
    return prefix + "***"


def mask_secrets(text: str) -> str:
    """Replace known secret patterns with masked versions."""
    for pattern in _SECRET_PATTERNS:
        text = pattern.sub(_mask, text)
    return text


class SecretMaskingFilter(logging.Filter):
    """Logging filter that redacts API keys and tokens from log records."""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = mask_secrets(record.msg)
        if record.args:
            if isinstance(record.args, dict):
                record.args = {
                    k: mask_secrets(str(v)) if isinstance(v, str) else v
                    for k, v in record.args.items()
                }
            elif isinstance(record.args, tuple):
                record.args = tuple(
                    mask_secrets(str(a)) if isinstance(a, str) else a for a in record.args
                )
        return True


def install_secret_masking() -> None:
    """Install the secret masking filter on the root logger."""
    root = logging.getLogger()
    root.addFilter(SecretMaskingFilter())
