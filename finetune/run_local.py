#!/usr/bin/env python3
"""Unified launcher for local fine-tuning.

Chooses the GPU QLoRA path when CUDA is usable, otherwise falls back to the
CPU trainer. This keeps the local workflow stable on machines where the CUDA
driver is temporarily unavailable.

Examples:
  python finetune/run_local.py stm32
  python finetune/run_local.py kicad --device gpu --eval
  python finetune/run_local.py embedded --device cpu --model gpt2
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

import torch

SCRIPT_DIR = Path(__file__).resolve().parent
DATASETS_DIR = SCRIPT_DIR / "datasets"
GPU_TRAINER = SCRIPT_DIR / "train_local.py"
CPU_TRAINER = SCRIPT_DIR / "train_cpu.py"

DEFAULT_GPU_MODEL = "TinyLlama/TinyLlama-1.1B-Chat-v1.0"
DEFAULT_CPU_MODEL = "gpt2"
DOMAINS = [
    "stm32",
    "spice",
    "iot",
    "power",
    "dsp",
    "emc",
    "kicad",
    "embedded",
    "platformio",
    "freecad",
]


def dataset_line_count(path: Path) -> int:
    with path.open("r", encoding="utf-8") as handle:
        return sum(1 for _ in handle)


def probe_cuda() -> tuple[bool, str]:
    if not torch.cuda.is_available():
        return False, "CUDA unavailable in PyTorch"

    try:
        _ = torch.zeros(1, device="cuda")
        name = torch.cuda.get_device_name(0)
        total_gb = torch.cuda.get_device_properties(0).total_memory / 1024**3
        torch.cuda.empty_cache()
        return True, f"{name} ({total_gb:.1f} GB VRAM)"
    except Exception as exc:  # pragma: no cover - defensive path
        return False, f"CUDA probe failed: {exc}"


def resolve_cli_path(
    raw_path: str | None, default_path: Path | None = None
) -> Path | None:
    if raw_path is None:
        return default_path
    path = Path(raw_path)
    if not path.is_absolute():
        path = (Path.cwd() / path).resolve()
    return path


def build_command(
    args: argparse.Namespace, resolved_device: str
) -> tuple[list[str], dict[str, str]]:
    if resolved_device == "gpu":
        command = [
            sys.executable,
            str(GPU_TRAINER),
            args.domain,
            "--model",
            args.model or DEFAULT_GPU_MODEL,
            "--seq-len",
            str(args.seq_len),
            "--epochs",
            str(args.epochs),
        ]
        if args.eval:
            command.append("--eval")
    else:
        command = [
            sys.executable,
            str(CPU_TRAINER),
            args.domain,
            "--model",
            args.model or DEFAULT_CPU_MODEL,
            "--seq-len",
            str(args.seq_len),
            "--epochs",
            str(args.epochs),
        ]

    if args.max_samples is not None:
        command.extend(["--max-samples", str(args.max_samples)])
    if args.dataset_path:
        command.extend(["--dataset-path", str(args.dataset_path)])
    if args.output_dir:
        command.extend(["--output-dir", str(args.output_dir)])
    if args.tokenize_workers is not None:
        command.extend(["--tokenize-workers", str(args.tokenize_workers)])
    if args.verbose:
        command.append("--verbose")
    elif args.quiet:
        command.append("--quiet")

    env = os.environ.copy()
    if resolved_device == "cpu":
        env["CUDA_VISIBLE_DEVICES"] = ""
    if args.offline:
        env["HF_HUB_OFFLINE"] = "1"
        env["TRANSFORMERS_OFFLINE"] = "1"

    return command, env


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Launch local fine-tuning with CPU/GPU fallback"
    )
    parser.add_argument("domain", choices=DOMAINS)
    parser.add_argument("--device", choices=["auto", "gpu", "cpu"], default="auto")
    parser.add_argument("--model", default=None, help="Base model override")
    parser.add_argument(
        "--dataset-path", default=None, help="Override ShareGPT JSONL dataset path"
    )
    parser.add_argument(
        "--output-dir", default=None, help="Override training output directory"
    )
    parser.add_argument("--seq-len", type=int, default=256)
    parser.add_argument("--epochs", type=int, default=1)
    parser.add_argument("--max-samples", type=int, default=None)
    parser.add_argument(
        "--tokenize-workers",
        type=int,
        default=0,
        help="CPU workers for tokenization (0=auto)",
    )
    parser.add_argument(
        "--eval", action="store_true", help="Only supported on the GPU trainer"
    )
    parser.add_argument(
        "--offline", action="store_true", help="Force local Hugging Face cache usage"
    )
    verbosity = parser.add_mutually_exclusive_group()
    verbosity.add_argument(
        "--verbose", action="store_true", help="Print detailed launcher information"
    )
    verbosity.add_argument(
        "--quiet", action="store_true", help="Keep launcher output minimal"
    )
    args = parser.parse_args()

    dataset_path = resolve_cli_path(
        args.dataset_path, DATASETS_DIR / f"{args.domain}_chat.jsonl"
    )
    output_dir = resolve_cli_path(args.output_dir) if args.output_dir else None
    args.dataset_path = None if args.dataset_path is None else str(dataset_path)
    args.output_dir = None if output_dir is None else str(output_dir)
    if not dataset_path.exists():
        print(f"Dataset not found: {dataset_path}", file=sys.stderr)
        return 1

    sample_count = dataset_line_count(dataset_path)
    if sample_count < 2:
        print(f"Dataset must contain at least 2 rows: {dataset_path}", file=sys.stderr)
        return 1

    gpu_ready, gpu_reason = probe_cuda()
    if args.device == "gpu" and not gpu_ready:
        print(f"GPU mode requested but unavailable: {gpu_reason}", file=sys.stderr)
        return 1

    resolved_device = (
        "gpu"
        if (args.device == "gpu" or (args.device == "auto" and gpu_ready))
        else "cpu"
    )
    if resolved_device == "cpu" and args.eval:
        print("--eval is only supported with the GPU trainer.", file=sys.stderr)
        return 1

    command, env = build_command(args, resolved_device)

    effective_samples = (
        min(sample_count, args.max_samples) if args.max_samples else sample_count
    )

    if args.quiet:
        print(
            f"[RUN] domain={args.domain} device={resolved_device} samples={effective_samples}/{sample_count}"
        )
    else:
        print("=" * 60)
        print("Local fine-tuning launcher")
        print(f"Domain:  {args.domain}")
        print(f"Device:  {resolved_device}")
        print(f"Samples: {effective_samples}/{sample_count}")
        if resolved_device == "gpu":
            print(f"CUDA:    {gpu_reason}")
            print(f"Model:   {args.model or DEFAULT_GPU_MODEL}")
        else:
            print(f"GPU:     {gpu_reason}")
            print(f"Model:   {args.model or DEFAULT_CPU_MODEL}")
        print(f"Seq Len: {args.seq_len}")
        print(f"Epochs:  {args.epochs}")
        if args.verbose:
            print(f"Dataset: {dataset_path}")
            print(f"Output:  {args.output_dir or '(trainer default)'}")
            print(
                f"Tokenz:  {args.tokenize_workers if args.tokenize_workers else 'auto'}"
            )
            print(f"Cmd:     {' '.join(command)}")
        print("=" * 60)
    sys.stdout.flush()

    completed = subprocess.run(command, cwd=SCRIPT_DIR, env=env)
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
