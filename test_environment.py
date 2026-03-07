#!/usr/bin/env python3
"""Environment check for local fine-tuning."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

import psutil
import torch
from finetune.runtime_compat import disable_broken_torchvision

ROOT_DIR = Path(__file__).resolve().parent
DATASETS_DIR = ROOT_DIR / "finetune" / "datasets"
RUNTIME_COMPAT_NOTE = disable_broken_torchvision()

REQUIRED_LIBS = [
    "torch",
    "transformers",
    "peft",
    "accelerate",
    "bitsandbytes",
    "datasets",
]

OPTIONAL_MODELS = {
    "cpu_default": "gpt2",
    "gpu_default": "TinyLlama/TinyLlama-1.1B-Chat-v1.0",
}


def detect_cpu_fallback_model() -> str | None:
    for model_id in (
        OPTIONAL_MODELS["cpu_default"],
        OPTIONAL_MODELS["gpu_default"],
    ):
        if has_hf_cache(model_id):
            return model_id
    return None


def has_hf_cache(model_id: str) -> bool:
    cache_root = Path.home() / ".cache" / "huggingface" / "hub"
    model_dir = cache_root / f"models--{model_id.replace('/', '--')}"
    return model_dir.exists()


def print_header(title: str) -> None:
    print("=" * 60)
    print(title)
    print("=" * 60)


def check_libraries() -> list[str]:
    print_header("LIBRARIES")
    missing: list[str] = []
    for name in REQUIRED_LIBS:
        try:
            module = importlib.import_module(name)
            version = getattr(module, "__version__", "unknown")
            print(f"[ok] {name:<14} {version}")
        except Exception as exc:
            missing.append(name)
            print(f"[ko] {name:<14} {exc}")
    print()
    return missing


def check_system() -> None:
    print_header("SYSTEM")
    mem = psutil.virtual_memory()
    print(f"Python:        {sys.version.split()[0]}")
    print(f"RAM total:     {mem.total / 1024**3:.2f} GB")
    print(f"RAM available: {mem.available / 1024**3:.2f} GB")
    print(f"CUDA in torch: {torch.cuda.is_available()}")
    if RUNTIME_COMPAT_NOTE:
        print(f"Compat mode:   {RUNTIME_COMPAT_NOTE}")
    if torch.cuda.is_available():
        try:
            name = torch.cuda.get_device_name(0)
            total_gb = torch.cuda.get_device_properties(0).total_memory / 1024**3
            _ = torch.zeros(1, device="cuda")
            torch.cuda.empty_cache()
            print(f"GPU:           {name}")
            print(f"VRAM total:    {total_gb:.2f} GB")
            print("GPU probe:     ok")
        except Exception as exc:
            print(f"GPU probe:     failed ({exc})")
    else:
        print("GPU probe:     unavailable")
    print()


def check_local_assets() -> None:
    print_header("LOCAL ASSETS")
    datasets = sorted(DATASETS_DIR.glob("*_chat.jsonl"))
    for dataset in datasets:
        with dataset.open("r", encoding="utf-8") as handle:
            rows = sum(1 for _ in handle)
        print(f"[ok] {dataset.name:<24} {rows:>6} rows")

    for label, model_id in OPTIONAL_MODELS.items():
        status = "ok" if has_hf_cache(model_id) else "missing"
        print(f"[{status}] cache {label:<11} {model_id}")
    print()


def summary(missing: list[str]) -> int:
    print_header("SUMMARY")
    gpu_ready = False
    if torch.cuda.is_available():
        try:
            _ = torch.zeros(1, device="cuda")
            torch.cuda.empty_cache()
            gpu_ready = True
        except Exception:
            gpu_ready = False

    cpu_model = detect_cpu_fallback_model()
    cpu_ready = not missing and cpu_model is not None

    if missing:
        print(f"Missing libraries: {', '.join(missing)}")
        print("Suggested bootstrap: ./scripts/bootstrap_finetune_env.sh")
        print("Status: blocked")
        return 1

    if gpu_ready:
        print("Status: GPU fine-tuning available")
        if cpu_ready:
            print(f"CPU fallback cache: {cpu_model}")
        else:
            print("CPU fallback cache: missing (will require a model download)")
        print("Suggested command: python finetune/run_local.py stm32")
        return 0

    if cpu_ready:
        print(f"Status: CPU fallback available with cached model {cpu_model}")
        print("Suggested command: python finetune/run_local.py stm32 --device cpu")
        return 0

    print("Status: partially configured")
    print("Reason: no cached CPU fallback model and GPU is unavailable")
    print("Suggested bootstrap: ./scripts/bootstrap_finetune_env.sh")
    print(
        "Suggested command after model download: python finetune/run_local.py stm32 --device cpu"
    )
    return 1


def main() -> int:
    print()
    print_header("LOCAL FINE-TUNING ENVIRONMENT")
    missing = check_libraries()
    check_system()
    check_local_assets()
    return summary(missing)


if __name__ == "__main__":
    raise SystemExit(main())
