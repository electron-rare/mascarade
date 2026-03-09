#!/usr/bin/env python3
"""Benchmark GPU training slot counts from an existing batch manifest."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

from run_manifest import load_json, now_ts, redact_command

SCRIPT_DIR = Path(__file__).resolve().parent
RUN_LOCAL = SCRIPT_DIR / "run_local.py"
RUNS_DIR = SCRIPT_DIR / "runs"


def resolve_path(raw: str) -> Path:
    path = Path(raw)
    if not path.is_absolute():
        path = (Path.cwd() / path).resolve()
    return path


def resolve_manifest(raw: str) -> Path:
    path = resolve_path(raw)
    if path.is_dir():
        path = path / "manifest.json"
    return path


def bench_run_dir(label: str) -> Path:
    stamp = time.strftime("%Y%m%d_%H%M%S")
    return RUNS_DIR / f"{label}_{stamp}"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Benchmark 1 or 2 GPU training slots using merged datasets from a batch manifest"
    )
    parser.add_argument(
        "--batch-run", required=True, help="Batch run dir or manifest.json"
    )
    parser.add_argument(
        "--domains",
        nargs="*",
        default=None,
        help="Subset of manifest domains to train (default: all completed distills)",
    )
    parser.add_argument("--gpu-slots", type=int, choices=[1, 2], required=True)
    parser.add_argument("--student-model", required=True)
    parser.add_argument("--student-max-samples", type=int, default=96)
    parser.add_argument("--epochs", type=int, default=2)
    parser.add_argument("--seq-len", type=int, default=256)
    parser.add_argument("--tokenize-workers", type=int, default=4)
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--run-label", default="gpu_slot_bench")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    manifest_path = resolve_manifest(args.batch_run)
    manifest = load_json(manifest_path)
    if not isinstance(manifest, dict):
        raise SystemExit(f"Invalid manifest: {manifest_path}")

    selected = args.domains or list((manifest.get("domains") or {}).keys())
    run_dir = bench_run_dir(f"{args.run_label}_slots{args.gpu_slots}")
    logs_dir = run_dir / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)

    jobs: list[dict] = []
    for label in selected:
        payload = (manifest.get("domains") or {}).get(label)
        if payload is None:
            raise SystemExit(f"Domain not found in manifest: {label}")
        if payload.get("distill", {}).get("status") != "completed":
            raise SystemExit(f"Domain {label} does not have a completed distill step")
        canonical = str(payload.get("canonical") or label)
        merged_out = resolve_path(str(payload["merged_out"]))
        if not merged_out.exists():
            raise SystemExit(f"Merged dataset not found: {merged_out}")
        output_dir = SCRIPT_DIR / "models_local" / f"{label}_{run_dir.name}"
        command = [
            sys.executable,
            str(RUN_LOCAL),
            canonical,
            "--device",
            "gpu",
            "--model",
            args.student_model,
            "--dataset-path",
            str(merged_out),
            "--output-dir",
            str(output_dir),
            "--max-samples",
            str(args.student_max_samples),
            "--epochs",
            str(args.epochs),
            "--seq-len",
            str(args.seq_len),
            "--tokenize-workers",
            str(args.tokenize_workers),
            "--quiet",
        ]
        if args.offline:
            command.append("--offline")
        jobs.append(
            {
                "label": label,
                "canonical": canonical,
                "merged_out": str(merged_out),
                "output_dir": str(output_dir),
                "command": command,
                "log_path": str(logs_dir / f"{label}.log"),
                "status": "pending",
            }
        )

    report = {
        "version": 1,
        "kind": "gpu_slot_benchmark",
        "created_at": now_ts(),
        "updated_at": now_ts(),
        "run_dir": str(run_dir),
        "batch_manifest": str(manifest_path),
        "gpu_slots": args.gpu_slots,
        "student_model": args.student_model,
        "student_max_samples": args.student_max_samples,
        "epochs": args.epochs,
        "seq_len": args.seq_len,
        "tokenize_workers": args.tokenize_workers,
        "offline": args.offline,
        "jobs": jobs,
    }

    start_time = time.monotonic()
    active: list[tuple[subprocess.Popen, dict, object]] = []
    queue = jobs[:]

    while queue or active:
        while queue and len(active) < args.gpu_slots:
            job = queue.pop(0)
            log_handle = open(job["log_path"], "w", encoding="utf-8")
            job["status"] = "running"
            job["started_at"] = now_ts()
            job["started_monotonic"] = time.monotonic()
            if args.verbose:
                print(f"[RUN] {job['label']} -> {job['output_dir']}", flush=True)
            env = os.environ.copy()
            env["MASCARADE_GPU_GLOBAL_SLOTS"] = str(args.gpu_slots)
            process = subprocess.Popen(
                job["command"],
                cwd=SCRIPT_DIR,
                env=env,
                stdout=log_handle,
                stderr=subprocess.STDOUT,
            )
            active.append((process, job, log_handle))

        time.sleep(2)
        next_active: list[tuple[subprocess.Popen, dict, object]] = []
        for process, job, log_handle in active:
            returncode = process.poll()
            if returncode is None:
                next_active.append((process, job, log_handle))
                continue
            log_handle.close()
            job["completed_at"] = now_ts()
            job["returncode"] = returncode
            job["duration_seconds"] = round(
                time.monotonic() - float(job["started_monotonic"]), 2
            )
            job.pop("started_monotonic", None)
            job["status"] = "completed" if returncode == 0 else "failed"
            training_info = load_json(Path(job["output_dir"]) / "training_info.json")
            if training_info:
                job["training_info"] = training_info
            if args.verbose:
                print(
                    f"[{'OK' if returncode == 0 else 'FAIL'}] {job['label']} rc={returncode}",
                    flush=True,
                )
        active = next_active

    report["updated_at"] = now_ts()
    report["wall_time_seconds"] = round(time.monotonic() - start_time, 2)
    report["jobs"] = [
        {
            **job,
            "command": redact_command(job["command"]),
        }
        for job in jobs
    ]
    report_path = run_dir / "bench.json"
    report_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    print(f"[OK] report: {report_path}")
    print(f"[OK] wall_time_seconds: {report['wall_time_seconds']}")
    for job in report["jobs"]:
        info = job.get("training_info") or {}
        loss = info.get("loss")
        print(
            f"[OK] {job['label']}: status={job['status']} "
            f"duration={job.get('duration_seconds')} loss={loss}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
