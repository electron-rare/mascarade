#!/usr/bin/env python3
"""Teacher distillation followed by local student fine-tuning."""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

from sharegpt_utils import (
    dedupe_rows,
    ensure_row_ids,
    load_jsonl,
    validate_rows,
    write_jsonl,
)

SCRIPT_DIR = Path(__file__).resolve().parent
DISTILL_SCRIPT = SCRIPT_DIR / "distill_dataset.py"
RUN_LOCAL_SCRIPT = SCRIPT_DIR / "run_local.py"
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
    parser = argparse.ArgumentParser(
        description="Distill with a teacher model then fine-tune locally"
    )
    parser.add_argument("domain", choices=DOMAINS)
    parser.add_argument("--source-dataset", default=None)
    parser.add_argument("--distilled-out", default=None)
    parser.add_argument("--merged-out", default=None)
    parser.add_argument("--report-path", default=None)
    parser.add_argument(
        "--api-url",
        action="append",
        dest="api_urls",
        help="Mascarade base URL, repeatable",
    )
    parser.add_argument("--api-key", default="")
    parser.add_argument("--teacher-provider", default=None)
    parser.add_argument("--teacher-model", default=None)
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

    def emit(message: str, *, important: bool = False) -> None:
        if args.quiet and not important:
            return
        print(message, flush=True)

    source_dataset = resolve_cli_path(
        args.source_dataset, SCRIPT_DIR / "datasets" / f"{args.domain}_chat.jsonl"
    )
    distilled_out = resolve_cli_path(
        args.distilled_out, default_path("distilled", args.domain)
    )
    merged_out = resolve_cli_path(args.merged_out, default_path("merged", args.domain))
    report_path = resolve_cli_path(
        args.report_path, distilled_out.with_suffix(".report.json")
    )
    train_output_dir = (
        resolve_cli_path(args.train_output_dir) if args.train_output_dir else None
    )

    if not source_dataset.exists():
        raise SystemExit(f"Source dataset not found: {source_dataset}")

    emit(
        f"[PLAN] domain={args.domain} distill={'no' if args.skip_distill else 'yes'} train={'no' if args.skip_train else 'yes'}",
        important=True,
    )
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

        if run_command(distill_cmd, verbose=args.verbose, quiet=args.quiet) != 0:
            return 1

    if not distilled_out.exists():
        raise SystemExit(f"Distilled dataset not found: {distilled_out}")

    emit("[2/3] Merging source and distilled datasets", important=True)
    source_rows = ensure_row_ids(load_jsonl(source_dataset), f"{args.domain}-source")
    distilled_rows = ensure_row_ids(load_jsonl(distilled_out), f"{args.domain}-distill")
    merged_rows = dedupe_rows(source_rows + distilled_rows)
    validation_errors = validate_rows(merged_rows)
    if validation_errors:
        for error in validation_errors[:20]:
            print(f"[ERROR] {error}")
        raise SystemExit(f"Merged dataset is invalid ({len(validation_errors)} errors)")

    write_jsonl(merged_out, merged_rows)
    emit(f"[OK] wrote merged dataset: {merged_out}", important=True)
    emit(
        f"[OK] source={len(source_rows)} distilled={len(distilled_rows)} merged={len(merged_rows)}",
        important=True,
    )

    if args.skip_train:
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
    if args.train_output_dir:
        train_cmd.extend(["--output-dir", str(train_output_dir)])
    if args.offline:
        train_cmd.append("--offline")
    if args.eval:
        train_cmd.append("--eval")
    if args.verbose:
        train_cmd.append("--verbose")
    elif args.quiet:
        train_cmd.append("--quiet")

    return run_command(train_cmd, verbose=args.verbose, quiet=args.quiet)


if __name__ == "__main__":
    raise SystemExit(main())
