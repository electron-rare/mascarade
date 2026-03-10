#!/usr/bin/env python3
"""Canonical local paths for shared LLM assets."""

from __future__ import annotations

import os
from pathlib import Path

DEFAULT_LLM_DIR = "/ai/llm"


def llm_root() -> Path:
    return Path(os.environ.get("MASCARADE_LLM_DIR", DEFAULT_LLM_DIR)).resolve()


def hf_home() -> Path:
    return llm_root() / "huggingface"


def hf_hub_cache() -> Path:
    return hf_home() / "hub"


def shared_model_cache_dir() -> Path:
    return llm_root() / "models_cache"


def watch_models_dir() -> Path:
    return llm_root() / "watch_models"


def apple_llm_dir() -> Path:
    return llm_root() / "apple-llm"


def safe_model_dir_name(model_id: str) -> str:
    return model_id.replace("/", "--")


def local_watch_model_dir(model_id: str) -> Path:
    return watch_models_dir() / safe_model_dir_name(model_id)


def ensure_llm_dirs() -> dict[str, Path]:
    roots = {
        "llm_root": llm_root(),
        "hf_home": hf_home(),
        "hf_hub_cache": hf_hub_cache(),
        "models_cache": shared_model_cache_dir(),
        "watch_models": watch_models_dir(),
        "apple_llm": apple_llm_dir(),
    }
    for path in roots.values():
        path.mkdir(parents=True, exist_ok=True)
    return roots


def configure_hf_env() -> dict[str, Path]:
    roots = ensure_llm_dirs()
    os.environ["MASCARADE_LLM_DIR"] = str(roots["llm_root"])
    os.environ["HF_HOME"] = str(roots["hf_home"])
    os.environ["HUGGINGFACE_HUB_CACHE"] = str(roots["hf_hub_cache"])
    os.environ["TRANSFORMERS_CACHE"] = str(roots["hf_hub_cache"])
    return roots


def hf_cache_roots() -> list[Path]:
    configure_hf_env()
    roots: list[Path] = []
    explicit_cache = os.environ.get("HUGGINGFACE_HUB_CACHE")
    if explicit_cache:
        roots.append(Path(explicit_cache))
    explicit_hf_home = os.environ.get("HF_HOME")
    if explicit_hf_home:
        roots.append(Path(explicit_hf_home) / "hub")
    fallback = Path.home() / ".cache" / "huggingface" / "hub"
    if fallback not in roots:
        roots.append(fallback)
    ordered: list[Path] = []
    for root in roots:
        if root not in ordered:
            ordered.append(root)
    return ordered
