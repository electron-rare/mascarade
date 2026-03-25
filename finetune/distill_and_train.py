#!/usr/bin/env python3
"""Teacher distillation followed by local student fine-tuning."""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import time
from pathlib import Path

from auto_policy import (
    detect_machine_profile,
    resolve_teacher_objective,
    resolve_teacher_selection,
)
from dataset_bootstrap import ensure_seed_dataset
from dataset_quality import (
    DatasetQualityError,
    enforce_dataset_quality,
    summarize_quality_report,
)
from run_manifest import load_json, now_ts, redact_command, write_manifest
from sharegpt_utils import (
    dedupe_rows_with_stats,
    ensure_row_ids,
    ensure_row_ids_with_stats,
    load_jsonl,
    validate_rows,
    write_jsonl,
)

SCRIPT_DIR = Path(__file__).resolve().parent
DISTILL_SCRIPT = SCRIPT_DIR / "distill_dataset.py"
RUN_LOCAL_SCRIPT = SCRIPT_DIR / "run_local.py"
RUNS_DIR = SCRIPT_DIR / "runs"
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


def load_env_var_from_dotenv(name: str) -> str | None:
    env_path = Path(__file__).resolve().parents[1] / ".env"
    if not env_path.exists():
        return None
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key != name:
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        return value
    return None


def ensure_local_api_key_env() -> None:
    if os.environ.get("MASCARADE_API_KEY"):
        return
    api_key = load_env_var_from_dotenv("MASCARADE_API_KEY")
    if api_key:
        os.environ["MASCARADE_API_KEY"] = api_key


def default_path(kind: str, domain: str) -> Path:
    stamp = time.strftime("%Y%m%d_%H%M%S")
    base = SCRIPT_DIR / "datasets" / "distilled"
    if kind == "distilled":
        return base / f"{domain}_teacher_{stamp}.jsonl"
    return base / f"{domain}_teacher_mix_{stamp}.jsonl"


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
    run_dir: Path,
    run_label: str,
    args: argparse.Namespace,
    source_dataset: Path,
    distilled_out: Path,
    merged_out: Path,
    report_path: Path,
    train_output_dir: Path | None,
) -> tuple[Path, dict]:
    manifest_path = run_dir / "run.json"
    manifest = {
        "version": 1,
        "kind": "distill_and_train",
        "created_at": now_ts(),
        "updated_at": now_ts(),
        "status": "running",
        "run_dir": str(run_dir),
        "run_label": run_label,
        "domain": args.domain,
        "paths": {
            "source_dataset": str(source_dataset),
            "distilled_out": str(distilled_out),
            "merged_out": str(merged_out),
            "report_path": str(report_path),
            "train_output_dir": (
                None if train_output_dir is None else str(train_output_dir)
            ),
            "train_run_manifest": (
                None if train_output_dir is None else str(train_output_dir / "run.json")
            ),
            "training_info_path": (
                None
                if train_output_dir is None
                else str(train_output_dir / "training_info.json")
            ),
        },
        "config": {
            "api_urls": args.api_urls or [],
            "teacher_provider": args.teacher_provider,
            "teacher_model": args.teacher_model,
            "teacher_objective": args.teacher_objective,
            "teacher_selection": args.teacher_selection,
            "teacher_only": args.teacher_only,
            "strategy": args.strategy,
            "temperature": args.temperature,
            "max_tokens": args.max_tokens,
            "timeout": args.timeout,
            "max_source_samples": args.max_source_samples,
            "samples_per_source": args.samples_per_source,
            "distill_concurrency": args.distill_concurrency,
            "json_retries": args.json_retries,
            "seed": args.seed,
            "sleep_ms": args.sleep_ms,
            "teacher_system_path": args.teacher_system_path,
            "local_hf_device": args.local_hf_device,
            "machine_profile": args.machine_profile,
            "device": args.device,
            "student_model": args.student_model,
            "student_max_samples": args.student_max_samples,
            "seq_len": args.seq_len,
            "epochs": args.epochs,
            "tokenize_workers": args.tokenize_workers,
            "offline": args.offline,
            "eval": args.eval,
            "dry_run": args.dry_run,
            "skip_distill": args.skip_distill,
            "skip_train": args.skip_train,
        },
        "steps": {
            "distill": {
                "status": "skipped" if args.skip_distill else "pending",
            },
            "merge": {
                "status": "pending",
            },
            "train": {
                "status": "skipped" if args.skip_train else "pending",
            },
        },
    }
    return manifest_path, manifest


def run_command(
    command: list[str], *, verbose: bool = False, quiet: bool = False
) -> int:
    if quiet:
        print(f"[RUN] {Path(command[1]).name}", flush=True)
    elif verbose:
        print(f"[RUN] {' '.join(command)}", flush=True)
    else:
        print(f"[RUN] {Path(command[1]).name}", flush=True)
    completed = subprocess.run(command, cwd=SCRIPT_DIR)
    return completed.returncode


def main() -> int:
    ensure_local_api_key_env()
    parser = argparse.ArgumentParser(
        description="Distill with a teacher model then fine-tune locally"
    )
    parser.add_argument("domain", choices=DOMAINS)
    parser.add_argument("--source-dataset", default=None)
    parser.add_argument("--distilled-out", default=None)
    parser.add_argument("--merged-out", default=None)
    parser.add_argument("--report-path", default=None)
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
    parser.add_argument(
        "--api-url",
        action="append",
        dest="api_urls",
        help="Mascarade base URL, repeatable",
    )
    parser.add_argument("--api-key", default=os.environ.get("MASCARADE_API_KEY", ""))
    parser.add_argument("--teacher-provider", default=None)
    parser.add_argument("--teacher-model", default=None)
    parser.add_argument(
        "--teacher-objective",
        choices=["fast", "balanced", "quality"],
        default=os.environ.get("MASCARADE_TEACHER_OBJECTIVE", "balanced"),
        help="Auto teacher policy: fast=true GPU 4B/7B first, quality=35B/24B offload first",
    )
    parser.add_argument("--strategy", default="best")
    parser.add_argument("--temperature", type=float, default=0.4)
    parser.add_argument("--max-tokens", type=int, default=2048)
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--max-source-samples", type=int, default=32)
    parser.add_argument("--samples-per-source", type=int, default=2)
    parser.add_argument(
        "--distill-concurrency",
        type=int,
        default=0,
        help="Teacher calls in parallel (0=auto)",
    )
    parser.add_argument(
        "--json-retries",
        type=int,
        default=1,
        help="Retry count when teacher returns invalid JSON",
    )
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--sleep-ms", type=int, default=0)
    parser.add_argument("--teacher-system-path", default=None)
    parser.add_argument(
        "--local-hf-device",
        default=os.environ.get("MASCARADE_LOCAL_HF_DEVICE"),
        help="Explicit device target for local-hf teachers (auto, cpu, cuda:0, ...)",
    )
    parser.add_argument("--device", choices=["auto", "gpu", "cpu"], default="auto")
    parser.add_argument("--student-model", default=None)
    parser.add_argument("--student-max-samples", type=int, default=None)
    parser.add_argument("--train-output-dir", default=None)
    parser.add_argument("--seq-len", type=int, default=256)
    parser.add_argument("--epochs", type=int, default=1)
    parser.add_argument(
        "--tokenize-workers",
        type=int,
        default=0,
        help="CPU workers for tokenization (0=auto)",
    )
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--eval", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--teacher-only",
        action="store_true",
        help="Teacher/distillation only, skip local student training",
    )
    parser.add_argument("--skip-train", action="store_true")
    parser.add_argument("--skip-distill", action="store_true")
    verbosity = parser.add_mutually_exclusive_group()
    verbosity.add_argument(
        "--verbose", action="store_true", help="Print detailed step information"
    )
    verbosity.add_argument(
        "--quiet", action="store_true", help="Keep pipeline output minimal"
    )
    args = parser.parse_args()
    args.teacher_objective = resolve_teacher_objective(args.teacher_objective)
    if args.teacher_only:
        args.skip_train = True
    args.machine_profile = detect_machine_profile(requested_device=args.device)
    args.teacher_selection = resolve_teacher_selection(
        machine_profile=args.machine_profile,
        explicit_provider=args.teacher_provider,
        explicit_model=args.teacher_model,
        ollama_api_url=os.environ.get("OLLAMA_API_URL"),
        domains=[args.domain],
        objective=args.teacher_objective,
    )
    args.teacher_provider = args.teacher_selection["provider"]
    args.teacher_model = args.teacher_selection["model"]
    if not args.local_hf_device:
        args.local_hf_device = args.teacher_selection.get("local_hf_device")
    elif args.teacher_provider == "local-hf":
        args.teacher_selection["local_hf_device"] = args.local_hf_device
        args.teacher_selection["gpu_active"] = (
            str(args.local_hf_device).strip().lower() != "cpu"
        )

    def emit(message: str, *, important: bool = False) -> None:
        if args.quiet and not important:
            return
        print(message, flush=True)

    run_label = normalize_run_label(args.run_label, args.smoke)
    run_dir = build_run_dir(run_label, args.domain) if run_label is not None else None

    source_dataset = resolve_cli_path(
        args.source_dataset, SCRIPT_DIR / "datasets" / f"{args.domain}_chat.jsonl"
    )
    if run_dir is not None:
        default_distilled = run_dir / f"{args.domain}_teacher.jsonl"
        default_merged = run_dir / f"{args.domain}_teacher_mix.jsonl"
        default_report = run_dir / f"{args.domain}_teacher.report.json"
        default_train_output_dir = run_dir / "train_output"
    else:
        default_distilled = default_path("distilled", args.domain)
        default_merged = default_path("merged", args.domain)
        default_report = default_distilled.with_suffix(".report.json")
        default_train_output_dir = None

    distilled_out = resolve_cli_path(args.distilled_out, default_distilled)
    merged_out = resolve_cli_path(args.merged_out, default_merged)
    report_default = (
        resolve_cli_path(args.distilled_out).with_suffix(".report.json")
        if args.distilled_out is not None
        else default_report
    )
    report_path = resolve_cli_path(args.report_path, report_default)
    train_output_dir = (
        resolve_cli_path(args.train_output_dir, default_train_output_dir)
        if (args.train_output_dir or default_train_output_dir is not None)
        else None
    )
    manifest_path = None
    manifest = None
    if run_dir is not None and run_label is not None:
        manifest_path, manifest = make_manifest(
            run_dir=run_dir,
            run_label=run_label,
            args=args,
            source_dataset=source_dataset,
            distilled_out=distilled_out,
            merged_out=merged_out,
            report_path=report_path,
            train_output_dir=train_output_dir,
        )
        write_manifest(manifest_path, manifest)

    if args.source_dataset is None:
        builder = ensure_seed_dataset(SCRIPT_DIR, args.domain, source_dataset)
        if builder is not None:
            emit(f"[BOOTSTRAP] built seed dataset via {builder.name}", important=True)

    if not source_dataset.exists():
        raise SystemExit(f"Source dataset not found: {source_dataset}")

    raw_source_rows = load_jsonl(source_dataset)
    source_quality_rows, normalized_source_ids = ensure_row_ids_with_stats(
        raw_source_rows, f"{args.domain}-source"
    )
    source_validation_errors = validate_rows(source_quality_rows)
    if source_validation_errors:
        for error in source_validation_errors[:20]:
            print(f"[ERROR] {error}")
        raise SystemExit(
            f"Source dataset is invalid ({len(source_validation_errors)} errors)"
        )
    try:
        source_quality = enforce_dataset_quality(
            source_quality_rows,
            label=f"{args.domain} source dataset",
            ids_fixed=normalized_source_ids,
        )
    except DatasetQualityError as exc:
        raise SystemExit(f"Source dataset quality gate failed: {exc}") from exc
    if source_quality["warnings"]:
        emit(
            f"[WARN] source-quality: {summarize_quality_report(source_quality)}",
            important=True,
        )

    emit(
        f"[PLAN] domain={args.domain} distill={'no' if args.skip_distill else 'yes'} train={'no' if args.skip_train else 'yes'}",
        important=True,
    )
    emit(
        "[INFO] teacher="
        f"{args.teacher_provider}/{args.teacher_model} "
        f"objective={args.teacher_objective} "
        f"mode={args.teacher_selection.get('mode', 'auto')}",
        important=True,
    )
    emit(
        f"[INFO] teacher_reason={args.teacher_selection.get('reason', '-')}",
        important=True,
    )
    if args.teacher_provider == "local-hf" and args.local_hf_device:
        emit(f"[INFO] local_hf_device={args.local_hf_device}", important=True)
    if run_dir is not None:
        emit(f"[INFO] run_dir={run_dir}", important=True)
    if args.verbose:
        emit(f"[INFO] source={source_dataset}", important=True)
        emit(f"[INFO] distilled_out={distilled_out}", important=True)
        emit(f"[INFO] merged_out={merged_out}", important=True)
        if train_output_dir is not None:
            emit(f"[INFO] train_output_dir={train_output_dir}", important=True)

    if not args.skip_distill:
        emit("[1/3] Distilling teacher dataset", important=True)
        distill_cmd = [
            sys.executable,
            str(DISTILL_SCRIPT),
            args.domain,
            "--source-dataset",
            str(source_dataset),
            "--out",
            str(distilled_out),
            "--report-path",
            str(report_path),
            "--strategy",
            args.strategy,
            "--temperature",
            str(args.temperature),
            "--max-tokens",
            str(args.max_tokens),
            "--timeout",
            str(args.timeout),
            "--max-source-samples",
            str(args.max_source_samples),
            "--samples-per-source",
            str(args.samples_per_source),
            "--concurrency",
            str(args.distill_concurrency),
            "--json-retries",
            str(args.json_retries),
            "--seed",
            str(args.seed),
            "--sleep-ms",
            str(args.sleep_ms),
        ]
        if args.api_key:
            distill_cmd.extend(["--api-key", args.api_key])
        if args.teacher_provider:
            distill_cmd.extend(["--teacher-provider", args.teacher_provider])
        if args.teacher_model:
            distill_cmd.extend(["--teacher-model", args.teacher_model])
        if args.local_hf_device:
            distill_cmd.extend(["--local-hf-device", args.local_hf_device])
        if args.teacher_system_path:
            distill_cmd.extend(["--teacher-system-path", args.teacher_system_path])
        if args.dry_run:
            distill_cmd.append("--dry-run")
        if args.verbose:
            distill_cmd.append("--verbose")
        elif args.quiet:
            distill_cmd.append("--quiet")
        for api_url in args.api_urls or []:
            distill_cmd.extend(["--api-url", api_url])

        if manifest is not None and manifest_path is not None:
            manifest["steps"]["distill"] = {
                "status": "running",
                "command": redact_command(distill_cmd),
            }
            write_manifest(manifest_path, manifest)

        distill_rc = run_command(distill_cmd, verbose=args.verbose, quiet=args.quiet)
        if manifest is not None and manifest_path is not None:
            manifest["steps"]["distill"] = {
                "status": "completed" if distill_rc == 0 else "failed",
                "command": redact_command(distill_cmd),
                "returncode": distill_rc,
            }
            distill_report = load_json(report_path)
            if distill_report is not None:
                manifest["steps"]["distill"]["report"] = distill_report
            if distill_rc != 0:
                manifest["status"] = "failed"
            write_manifest(manifest_path, manifest)
        if distill_rc != 0:
            return 1

    if not distilled_out.exists():
        if manifest is not None and manifest_path is not None:
            manifest["status"] = "failed"
            manifest["steps"]["merge"] = {
                "status": "failed",
                "error": f"Distilled dataset not found: {distilled_out}",
            }
            write_manifest(manifest_path, manifest)
        raise SystemExit(f"Distilled dataset not found: {distilled_out}")

    emit("[2/3] Merging source and distilled datasets", important=True)
    if manifest is not None and manifest_path is not None:
        manifest["steps"]["merge"] = {
            "status": "running",
        }
        write_manifest(manifest_path, manifest)
    source_rows = ensure_row_ids(load_jsonl(source_dataset), f"{args.domain}-source")
    distilled_rows = ensure_row_ids(load_jsonl(distilled_out), f"{args.domain}-distill")
    merged_rows, merged_duplicates_removed = dedupe_rows_with_stats(
        source_rows + distilled_rows
    )
    validation_errors = validate_rows(merged_rows)
    if validation_errors:
        if manifest is not None and manifest_path is not None:
            manifest["status"] = "failed"
            manifest["steps"]["merge"] = {
                "status": "failed",
                "validation_errors": validation_errors[:20],
                "validation_error_count": len(validation_errors),
            }
            write_manifest(manifest_path, manifest)
        for error in validation_errors[:20]:
            print(f"[ERROR] {error}")
        raise SystemExit(f"Merged dataset is invalid ({len(validation_errors)} errors)")
    try:
        merged_quality = enforce_dataset_quality(
            merged_rows,
            label=f"{args.domain} merged dataset",
        )
    except DatasetQualityError as exc:
        if manifest is not None and manifest_path is not None:
            manifest["status"] = "failed"
            manifest["steps"]["merge"] = {
                "status": "failed",
                "quality_gate": str(exc),
            }
            write_manifest(manifest_path, manifest)
        raise SystemExit(f"Merged dataset quality gate failed: {exc}") from exc

    write_jsonl(merged_out, merged_rows)
    if manifest is not None and manifest_path is not None:
        manifest["steps"]["merge"] = {
            "status": "completed",
            "source_rows": len(source_rows),
            "distilled_rows": len(distilled_rows),
            "merged_rows": len(merged_rows),
            "duplicates_removed": merged_duplicates_removed,
            "source_quality": source_quality,
            "quality_gate": merged_quality,
        }
        write_manifest(manifest_path, manifest)
    emit(f"[OK] wrote merged dataset: {merged_out}", important=True)
    emit(
        f"[OK] source={len(source_rows)} distilled={len(distilled_rows)} merged={len(merged_rows)}",
        important=True,
    )
    if merged_duplicates_removed:
        emit(
            f"[INFO] removed duplicate rows during consolidation: {merged_duplicates_removed}",
            important=True,
        )
    if merged_quality["warnings"]:
        emit(
            f"[WARN] merged-quality: {summarize_quality_report(merged_quality)}",
            important=True,
        )

    if args.skip_train:
        if manifest is not None and manifest_path is not None:
            manifest["status"] = "completed"
            write_manifest(manifest_path, manifest)
        return 0

    emit("[3/3] Launching local student training", important=True)
    train_cmd = [
        sys.executable,
        str(RUN_LOCAL_SCRIPT),
        args.domain,
        "--device",
        args.device,
        "--dataset-path",
        str(merged_out),
        "--seq-len",
        str(args.seq_len),
        "--epochs",
        str(args.epochs),
        "--tokenize-workers",
        str(args.tokenize_workers),
    ]
    if args.student_model:
        train_cmd.extend(["--model", args.student_model])
    if args.student_max_samples is not None:
        train_cmd.extend(["--max-samples", str(args.student_max_samples)])
    if train_output_dir is not None:
        train_cmd.extend(["--output-dir", str(train_output_dir)])
    if args.offline:
        train_cmd.append("--offline")
    if args.eval:
        train_cmd.append("--eval")
    if args.verbose:
        train_cmd.append("--verbose")
    elif args.quiet:
        train_cmd.append("--quiet")

    if manifest is not None and manifest_path is not None:
        manifest["steps"]["train"] = {
            "status": "running",
            "command": redact_command(train_cmd),
        }
        write_manifest(manifest_path, manifest)

    train_rc = run_command(train_cmd, verbose=args.verbose, quiet=args.quiet)
    if manifest is not None and manifest_path is not None:
        manifest["steps"]["train"] = {
            "status": "completed" if train_rc == 0 else "failed",
            "command": redact_command(train_cmd),
            "returncode": train_rc,
        }
        if train_output_dir is not None:
            child_run = load_json(train_output_dir / "run.json")
            if child_run is not None and child_run.get("llmfit") is not None:
                manifest["steps"]["train"]["llmfit"] = child_run["llmfit"]
            training_info = load_json(train_output_dir / "training_info.json")
            if training_info is not None:
                manifest["steps"]["train"]["training_info"] = training_info
        manifest["status"] = "completed" if train_rc == 0 else "failed"
        write_manifest(manifest_path, manifest)
    return train_rc


if __name__ == "__main__":
    raise SystemExit(main())
