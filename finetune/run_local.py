#!/usr/bin/env python3
"""Unified launcher for local fine-tuning.

Chooses the GPU QLoRA path when CUDA is usable, otherwise falls back to the
CPU trainer. This keeps the local workflow stable on machines where the CUDA
driver is temporarily unavailable.

Examples:
  python finetune/run_local.py stm32
  python finetune/run_local.py kicad --device gpu --eval
  python finetune/run_local.py embedded --device cpu --model Qwen/Qwen2.5-Coder-1.5B-Instruct
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import time
from pathlib import Path

import torch
from auto_policy import detect_machine_profile, resolve_default_student_model
from dataset_bootstrap import ensure_seed_dataset
from dataset_quality import DatasetQualityError, enforce_dataset_quality, summarize_quality_report
from dataset_refresh import refresh_dataset
from llm_paths import configure_hf_env, hf_cache_roots
from llmfit_utils import (
    build_llmfit_record,
    env_flag,
    fit_level_meets_threshold,
    llmfit_summary_payload,
    plan_model_with_llmfit,
    write_llmfit_plan,
)
from run_manifest import load_json, now_ts, redact_command, write_manifest
from sharegpt_utils import ensure_row_ids_with_stats, load_jsonl, validate_rows
from workspace_utils import prepare_training_output_dir

configure_hf_env()

SCRIPT_DIR = Path(__file__).resolve().parent
DATASETS_DIR = SCRIPT_DIR / "datasets"
RUNS_DIR = SCRIPT_DIR / "runs"
GPU_TRAINER = SCRIPT_DIR / "train_local.py"
CPU_TRAINER = SCRIPT_DIR / "train_cpu.py"

try:
    from model_selector import (
        SELECTION_FILE as _SELECTION_FILE,
        ensure_model_selection as _ensure_model_selection,
        resolve_model as _resolve_selected_model,
    )

    SELECTED_MODEL_FILE = _SELECTION_FILE
except Exception:
    _ensure_model_selection = None
    _resolve_selected_model = None
    SELECTED_MODEL_FILE = None
DEFAULT_GPU_MODEL = "Qwen/Qwen2.5-Coder-1.5B-Instruct"
DEFAULT_CPU_MODEL = DEFAULT_GPU_MODEL
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
    "components",
]

TEACHER_ONLY_STUDENT_PATTERNS = {
    "qwen/qwen3.5-35b-a3b-gptq-int4": (
        "teacher-only in this pipeline: GPTQ Int4 MoE checkpoint intended for inference/teacher use"
    ),
    "qwen/qwen3-next-80b-a3b-instruct-fp8": (
        "teacher-only in this pipeline: FP8 MoE checkpoint intended for serving/teacher use"
    ),
    "devstral-small-2507": (
        "teacher-only in this pipeline: Mistral coding teacher/inference model"
    ),
    "mistralai/devstral-small-2-24b-instruct-2512": (
        "teacher-only in this pipeline: recent Devstral local teacher/inference model"
    ),
    "mistral-small-3.1": (
        "teacher-only in this pipeline: Mistral teacher/inference model"
    ),
    "mistralai/mistral-small-3.1-24b-base-2503": (
        "teacher-only in this pipeline: recent Mistral 24B local teacher/inference model"
    ),
    "mistralai/mistral-small-3.2-24b-instruct-2506": (
        "teacher-only in this pipeline: recent Mistral 24B instruct local teacher/inference model"
    ),
    "deepseek-ai/deepseek-r1": (
        "teacher-only in this pipeline: DeepSeek reasoning teacher model"
    ),
    "deepseek-ai/deepseek-v3": (
        "teacher-only in this pipeline: DeepSeek V3 teacher model"
    ),
    "deepseek-ai/deepseek-coder-v2-lite-instruct": (
        "teacher-only in this pipeline: DeepSeek coder teacher model for code-domain distillation"
    ),
}


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


def has_hf_cache(model_id: str) -> bool:
    suffix = f"models--{model_id.replace('/', '--')}"
    for cache_root in hf_cache_roots():
        model_dir = cache_root / suffix
        if model_dir.exists():
            return True
    return False


def resolve_model(
    requested_model: str | None, resolved_device: str, offline: bool, seq_len: int
) -> tuple[str, str | None, dict | None]:
    if requested_model:
        return requested_model, None, None
    selection_info = None
    if not offline and _ensure_model_selection is not None:
        selection_info = _ensure_model_selection(
            fallback_model=DEFAULT_GPU_MODEL
            if resolved_device == "gpu"
            else DEFAULT_CPU_MODEL,
            task="code",
            seq_len=seq_len,
            watch=True,
            verbose=False,
        )
        selection_model = str(selection_info.get("model_id") or "").strip()
        if selection_model and selection_info.get("source") != "fallback":
            note = (
                f"[INFO] student selector {selection_info.get('source')}: "
                f"{selection_model} ({selection_info.get('reason', 'no reason')})"
            )
            return selection_model, note, selection_info
    if SELECTED_MODEL_FILE is not None and SELECTED_MODEL_FILE.exists():
        selected_model = (
            _resolve_selected_model(DEFAULT_GPU_MODEL)
            if _resolve_selected_model is not None
            else DEFAULT_GPU_MODEL
        )
        return selected_model, None, selection_info
    machine_profile = detect_machine_profile(requested_device=resolved_device)
    auto_model, auto_reason = resolve_default_student_model(
        machine_profile=machine_profile,
        fallback_model=DEFAULT_GPU_MODEL if resolved_device == "gpu" else DEFAULT_CPU_MODEL,
        requested_device=resolved_device,
    )
    if resolved_device == "gpu":
        return (
            auto_model,
            f"[INFO] hardware auto-selected student: {auto_model} ({auto_reason})",
            selection_info,
        )
    if not offline or has_hf_cache(auto_model):
        return (
            auto_model,
            f"[INFO] hardware auto-selected student: {auto_model} ({auto_reason})",
            selection_info,
        )
    if has_hf_cache(DEFAULT_GPU_MODEL):
        return (
            DEFAULT_GPU_MODEL,
            (
                f"[INFO] offline CPU fallback: {DEFAULT_CPU_MODEL} not cached, "
                f"reusing cached {DEFAULT_GPU_MODEL}"
            ),
            selection_info,
        )
    raise SystemExit(
        "Offline CPU fallback requires a cached model. "
        f"Missing caches: {DEFAULT_CPU_MODEL}, {DEFAULT_GPU_MODEL}"
    )


def reject_teacher_only_student(model_name: str) -> None:
    name = model_name.lower()
    for pattern, reason in TEACHER_ONLY_STUDENT_PATTERNS.items():
        if pattern in name:
            raise SystemExit(f"Unsupported student model {model_name}: {reason}")


def resolve_cli_path(
    raw_path: str | None, default_path: Path | None = None
) -> Path | None:
    if raw_path is None:
        return default_path
    path = Path(raw_path)
    if not path.is_absolute():
        path = (Path.cwd() / path).resolve()
    return path


def normalize_run_label(run_label: str | None, smoke: bool) -> str | None:
    label = run_label or ("smoke" if smoke else None)
    if label is None:
        return None
    normalized = re.sub(r"[^A-Za-z0-9._-]+", "-", label).strip(".-")
    if not normalized:
        raise SystemExit("Run label must contain at least one alphanumeric character")
    return normalized


def build_run_dir(run_label: str, domain: str) -> Path:
    stamp = time.strftime("%Y%m%d_%H%M%S")
    return RUNS_DIR / f"{run_label}_{domain}_{stamp}"


def make_manifest(
    *,
    run_dir: Path | None,
    run_label: str | None,
    args: argparse.Namespace,
    dataset_path: Path,
    requested_output_dir: Path,
    output_dir: Path,
    resolved_device: str,
    model_name: str,
    sample_count: int,
    effective_samples: int,
    dataset_quality_report: dict,
    dataset_refresh_report: dict | None,
    gpu_reason: str,
    trainer_command: list[str],
    llmfit_report_path: Path | None,
) -> tuple[Path, dict]:
    manifest_path = (
        (run_dir / "run.json") if run_dir is not None else (output_dir / "run.json")
    )
    training_info_path = output_dir / "training_info.json"
    manifest = {
        "version": 1,
        "kind": "run_local",
        "created_at": now_ts(),
        "updated_at": now_ts(),
        "status": "running",
        "run_dir": None if run_dir is None else str(run_dir),
        "run_label": run_label,
        "domain": args.domain,
        "paths": {
            "dataset_path": str(dataset_path),
            "requested_output_dir": str(requested_output_dir),
            "output_dir": str(output_dir),
            "training_info_path": str(training_info_path),
            "llmfit_plan_path": (
                None if llmfit_report_path is None else str(llmfit_report_path)
            ),
        },
        "config": {
            "requested_device": args.device,
            "resolved_device": resolved_device,
            "model": model_name,
            "model_source": (
                "explicit"
                if args.model
                else (
                    "selector"
                    if getattr(args, "model_selection", None)
                    and args.model_selection.get("source") != "fallback"
                    else "hardware_auto"
                )
            ),
            "model_selection": getattr(args, "model_selection", None),
            "offline": args.offline,
            "eval": args.eval,
            "seq_len": args.seq_len,
            "epochs": args.epochs,
            "max_samples": args.max_samples,
            "tokenize_workers": args.tokenize_workers,
            "sample_count": sample_count,
            "effective_samples": effective_samples,
            "dataset_quality": dataset_quality_report,
            "dataset_refresh": dataset_refresh_report,
            "gpu_probe": gpu_reason,
            "output_mode": args.output_workspace["mode"],
            "output_reason": args.output_workspace["reason"],
            "llmfit_preflight": args.llmfit_preflight,
            "llmfit_context": args.llmfit_context or args.seq_len,
            "llmfit_min_fit": args.llmfit_min_fit,
        },
        "command": redact_command(trainer_command),
        "result": {
            "returncode": None,
        },
    }
    return manifest_path, manifest


def build_command(
    args: argparse.Namespace, resolved_device: str, model_name: str
) -> tuple[list[str], dict[str, str]]:
    if resolved_device == "gpu":
        command = [
            sys.executable,
            str(GPU_TRAINER),
            args.domain,
            "--model",
            model_name,
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
            model_name,
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


def resolve_llmfit_report_path(
    args: argparse.Namespace, output_dir: Path | None, run_dir: Path | None
) -> Path | None:
    if args.llmfit_report_path:
        return resolve_cli_path(args.llmfit_report_path)
    if output_dir is not None:
        return output_dir / "llmfit_plan.json"
    if run_dir is not None:
        return run_dir / "llmfit_plan.json"
    return None


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
        "--refresh-dataset",
        action="store_true",
        help=(
            "Refresh the canonical domain dataset before training. Prefer the local "
            "mascarade-datasets repo when present, otherwise rebuild from "
            "finetune/datasets/build_*"
        ),
    )
    parser.add_argument(
        "--refresh-with-hf",
        action="store_true",
        help="When dataset refresh falls back to builders, include their Hugging Face enrichment path",
    )
    parser.add_argument(
        "--refresh-max-samples",
        type=int,
        default=None,
        help="Max samples forwarded to builder refresh runs when --refresh-with-hf is enabled",
    )
    parser.add_argument(
        "--no-prefer-full-datasets",
        dest="prefer_full_datasets",
        action="store_false",
        help="Do not sync from the sibling mascarade-datasets repo during refresh",
    )
    parser.add_argument(
        "--full-datasets-root",
        default=None,
        help="Optional path to the full mascarade-datasets repo used during refresh",
    )
    parser.add_argument(
        "--research-dir",
        default=None,
        help="Directory where dataset refresh web-research briefs are written",
    )
    parser.add_argument(
        "--skip-research-briefs",
        action="store_true",
        help="Refresh datasets without emitting Markdown/JSON research briefs",
    )
    parser.add_argument(
        "--output-dir", default=None, help="Override training output directory"
    )
    parser.add_argument(
        "--run-label",
        default=None,
        help="Isolate temporary outputs under finetune/runs/<label>_<domain>_<stamp>/",
    )
    parser.add_argument(
        "--smoke",
        action="store_true",
        help="Shortcut for --run-label smoke",
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
    parser.add_argument(
        "--llmfit-preflight",
        dest="llmfit_preflight",
        action="store_true",
        default=env_flag("LLMFIT_PREFLIGHT", True),
        help="Run llmfit model-fit preflight before local training",
    )
    parser.add_argument(
        "--no-llmfit-preflight",
        dest="llmfit_preflight",
        action="store_false",
        help="Disable llmfit model-fit preflight",
    )
    parser.add_argument(
        "--llmfit-bin",
        default=os.environ.get("LLMFIT_BIN"),
        help="Explicit llmfit binary path",
    )
    parser.add_argument(
        "--llmfit-root",
        default=os.environ.get("LLMFIT_ROOT"),
        help="Local llmfit repo root used to resolve a built binary",
    )
    parser.add_argument(
        "--llmfit-memory",
        default=os.environ.get("LLMFIT_MEMORY"),
        help="Optional llmfit --memory override, e.g. 24G",
    )
    parser.add_argument(
        "--llmfit-context",
        type=int,
        default=None,
        help="Context passed to llmfit plan (defaults to --seq-len)",
    )
    parser.add_argument(
        "--llmfit-min-fit",
        default=os.environ.get("LLMFIT_MIN_FIT", "marginal"),
        help="Warn when llmfit current fit is below this level",
    )
    parser.add_argument(
        "--llmfit-report-path",
        default=None,
        help="Optional JSON path for the raw llmfit plan output",
    )
    parser.add_argument(
        "--llmfit-allow-cargo-run",
        action="store_true",
        default=env_flag("LLMFIT_ALLOW_CARGO_RUN", False),
        help="Allow llmfit fallback via cargo run when no built binary is found",
    )
    verbosity = parser.add_mutually_exclusive_group()
    verbosity.add_argument(
        "--verbose", action="store_true", help="Print detailed launcher information"
    )
    verbosity.add_argument(
        "--quiet", action="store_true", help="Keep launcher output minimal"
    )
    parser.set_defaults(prefer_full_datasets=True)
    args = parser.parse_args()

    if args.refresh_dataset and args.dataset_path is not None:
        raise SystemExit("--refresh-dataset cannot be used with --dataset-path")

    dataset_path = resolve_cli_path(
        args.dataset_path, DATASETS_DIR / f"{args.domain}_chat.jsonl"
    )
    output_dir = resolve_cli_path(args.output_dir) if args.output_dir else None
    args.dataset_path = None if args.dataset_path is None else str(dataset_path)
    dataset_refresh_report = None
    if args.refresh_dataset:
        try:
            dataset_refresh_report = refresh_dataset(
                args.domain,
                dataset_dir=DATASETS_DIR,
                with_hf=args.refresh_with_hf,
                max_samples=args.refresh_max_samples,
                prefer_full_datasets=args.prefer_full_datasets,
                full_datasets_root=resolve_cli_path(args.full_datasets_root),
                research_dir=resolve_cli_path(args.research_dir),
                emit_research_brief=not args.skip_research_briefs,
            )
        except Exception as exc:  # noqa: BLE001
            print(f"Dataset refresh failed: {exc}", file=sys.stderr)
            return 1
        if not args.quiet:
            print(
                f"[REFRESH] {args.domain}: mode={dataset_refresh_report['source_mode']} "
                f"rows={dataset_refresh_report['row_count']} "
                f"quality={dataset_refresh_report['quality']['status']}"
            )
            if dataset_refresh_report["quality"].get("warnings"):
                print(
                    f"[WARN] refresh-quality: "
                    f"{summarize_quality_report(dataset_refresh_report['quality'])}"
                )
    if args.dataset_path is None:
        builder = ensure_seed_dataset(SCRIPT_DIR, args.domain, dataset_path)
        if builder is not None and not args.quiet:
            print(f"[BOOTSTRAP] built seed dataset via {builder.name}")
    if not dataset_path.exists():
        print(f"Dataset not found: {dataset_path}", file=sys.stderr)
        return 1

    raw_rows = load_jsonl(dataset_path)
    normalized_rows, normalized_source_ids = ensure_row_ids_with_stats(
        raw_rows, f"{args.domain}-dataset"
    )
    validation_errors = validate_rows(normalized_rows)
    if validation_errors:
        print(
            f"Dataset is invalid ({len(validation_errors)} errors): {validation_errors[0]}",
            file=sys.stderr,
        )
        return 1
    try:
        dataset_quality_report = enforce_dataset_quality(
            normalized_rows,
            label=f"{args.domain} dataset",
            ids_fixed=normalized_source_ids,
        )
    except DatasetQualityError as exc:
        print(f"Dataset quality gate failed: {exc}", file=sys.stderr)
        return 1
    if dataset_quality_report["warnings"] and not args.quiet:
        print(
            f"[WARN] dataset-quality: {summarize_quality_report(dataset_quality_report)}"
        )

    sample_count = len(normalized_rows)
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

    run_label = normalize_run_label(args.run_label, args.smoke)
    run_dir = None
    if output_dir is None and run_label is not None:
        run_dir = build_run_dir(run_label, args.domain)
        output_dir = run_dir / "train_output"
    requested_output_dir = output_dir
    args.output_workspace = None
    if output_dir is not None:
        output_workspace = prepare_training_output_dir(output_dir)
        args.output_workspace = output_workspace
        requested_output_dir = Path(output_workspace["requested_output_dir"])
        output_dir = Path(output_workspace["output_dir"])
    args.output_dir = None if output_dir is None else str(output_dir)

    model_name, model_note, model_selection = resolve_model(
        args.model,
        resolved_device,
        args.offline,
        args.seq_len,
    )
    args.model_selection = model_selection
    reject_teacher_only_student(model_name)
    llmfit_context = args.llmfit_context or args.seq_len
    llmfit_report_path = resolve_llmfit_report_path(args, output_dir, run_dir)
    command, env = build_command(args, resolved_device, model_name)

    effective_samples = (
        min(sample_count, args.max_samples) if args.max_samples else sample_count
    )
    manifest_path = None
    manifest = None
    if output_dir is not None:
        manifest_path, manifest = make_manifest(
            run_dir=run_dir,
            run_label=run_label,
            args=args,
            dataset_path=dataset_path,
            requested_output_dir=requested_output_dir,
            output_dir=output_dir,
            resolved_device=resolved_device,
            model_name=model_name,
            sample_count=sample_count,
            effective_samples=effective_samples,
            dataset_quality_report=dataset_quality_report,
            dataset_refresh_report=dataset_refresh_report,
            gpu_reason=gpu_reason,
            trainer_command=command,
            llmfit_report_path=llmfit_report_path,
        )
        manifest["llmfit"] = {
            "enabled": args.llmfit_preflight,
            "requested_device": resolved_device,
            "model": model_name,
            "context": llmfit_context,
            "minimum_fit": args.llmfit_min_fit,
            "status": "pending" if args.llmfit_preflight else "disabled",
        }
        write_manifest(manifest_path, manifest)

    llmfit_summary = None
    llmfit_warning = None
    llmfit_record = build_llmfit_record(
        enabled=args.llmfit_preflight,
        requested_device=resolved_device,
        model_name=model_name,
        context=llmfit_context,
        minimum_fit=args.llmfit_min_fit,
    )
    if args.llmfit_preflight:
        try:
            llmfit_summary = plan_model_with_llmfit(
                model_name=model_name,
                context=llmfit_context,
                llmfit_bin=args.llmfit_bin,
                llmfit_root=args.llmfit_root,
                memory_override=args.llmfit_memory,
                allow_cargo_run=args.llmfit_allow_cargo_run,
            )
            if llmfit_summary is None:
                llmfit_warning = (
                    "llmfit preflight skipped: no llmfit binary found. "
                    "Build /ai/saisail/llmfit with cargo +stable build --release -p llmfit "
                    "or set LLMFIT_BIN."
                )
            else:
                if llmfit_report_path is not None:
                    write_llmfit_plan(llmfit_report_path, llmfit_summary)
                if not fit_level_meets_threshold(
                    llmfit_summary.current_fit_level, args.llmfit_min_fit
                ):
                    llmfit_warning = (
                        "llmfit fit below threshold "
                        f"({llmfit_summary.current_fit_level} < {args.llmfit_min_fit})"
                    )
        except Exception as exc:  # noqa: BLE001
            llmfit_warning = f"llmfit preflight skipped: {exc}"
        llmfit_record = build_llmfit_record(
            enabled=args.llmfit_preflight,
            requested_device=resolved_device,
            model_name=model_name,
            context=llmfit_context,
            minimum_fit=args.llmfit_min_fit,
            summary=llmfit_summary,
            report_path=llmfit_report_path,
            warning=llmfit_warning,
        )
    if manifest is not None and manifest_path is not None:
        manifest["llmfit"] = llmfit_record
        write_manifest(manifest_path, manifest)

    if args.quiet:
        print(
            f"[RUN] domain={args.domain} device={resolved_device} samples={effective_samples}/{sample_count}"
        )
        if run_dir is not None:
            print(f"[RUN_DIR] {run_dir}")
        if args.output_workspace is not None:
            print(
                f"[OUTPUT] mode={args.output_workspace['mode']} "
                f"path={output_dir}"
            )
        if llmfit_warning:
            print(f"[WARN] {llmfit_warning}")
    else:
        print("=" * 60)
        print("Local fine-tuning launcher")
        print(f"Domain:  {args.domain}")
        print(f"Device:  {resolved_device}")
        print(f"Samples: {effective_samples}/{sample_count}")
        if run_dir is not None:
            print(f"Run Dir: {run_dir}")
        if resolved_device == "gpu":
            print(f"CUDA:    {gpu_reason}")
            print(f"Model:   {model_name}")
        else:
            print(f"GPU:     {gpu_reason}")
            print(f"Model:   {model_name}")
        if args.output_workspace is not None:
            print(
                "Output:  "
                f"{output_dir} "
                f"({args.output_workspace['mode']}: {args.output_workspace['reason']})"
            )
        if llmfit_summary is not None:
            print(
                "llmfit:  "
                f"fit={llmfit_summary.current_fit_level} "
                f"run={llmfit_summary.current_run_mode} "
                f"gpu_path={'yes' if llmfit_summary.gpu_path_feasible else 'no'} "
                f"quant={llmfit_summary.quantization or '-'} "
                f"source={llmfit_summary.source}"
            )
            if llmfit_report_path is not None:
                print(f"Plan:    {llmfit_report_path}")
        elif args.llmfit_preflight:
            print("llmfit:  unavailable")
        print(f"Seq Len: {args.seq_len}")
        print(f"Epochs:  {args.epochs}")
        if model_note:
            print(model_note)
        if (
            getattr(args, "model_selection", None)
            and args.model_selection.get("watch_report_path")
        ):
            print(f"[INFO] student_watch_report: {args.model_selection['watch_report_path']}")
        if llmfit_warning:
            print(f"[WARN]  {llmfit_warning}")
        if args.verbose:
            print(f"Dataset: {dataset_path}")
            print(
                f"Tokenz:  {args.tokenize_workers if args.tokenize_workers else 'auto'}"
            )
            print(f"Cmd:     {' '.join(command)}")
        print("=" * 60)
    sys.stdout.flush()

    returncode = 1
    error = None
    try:
        if llmfit_record["status"] == "rejected":
            error = str(llmfit_record.get("reason") or "llmfit rejected GPU training")
            print(error, file=sys.stderr)
            return 1
        completed = subprocess.run(command, cwd=SCRIPT_DIR, env=env)
        returncode = completed.returncode
        return returncode
    except Exception as exc:  # noqa: BLE001
        error = str(exc)
        raise
    finally:
        if manifest_path is not None and manifest is not None:
            manifest["status"] = "completed" if returncode == 0 else "failed"
            manifest["result"] = {
                "returncode": returncode,
            }
            if error is not None:
                manifest["result"]["error"] = error
            training_info = load_json(Path(args.output_dir) / "training_info.json")
            if training_info is not None:
                manifest["artifacts"] = {
                    "training_info": training_info,
                }
            if llmfit_summary is not None:
                manifest.setdefault("artifacts", {})
                manifest["artifacts"]["llmfit"] = llmfit_summary_payload(
                    llmfit_summary,
                    report_path=llmfit_report_path,
                )
            if llmfit_warning is not None:
                manifest.setdefault("artifacts", {})
                manifest["artifacts"]["llmfit_warning"] = llmfit_warning
            manifest["llmfit"] = llmfit_record
            write_manifest(manifest_path, manifest)


if __name__ == "__main__":
    raise SystemExit(main())
