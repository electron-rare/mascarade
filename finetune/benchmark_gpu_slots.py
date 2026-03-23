#!/usr/bin/env python3
"""Benchmark GPU training slot counts against an existing completed batch run."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from collections import deque
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
RUN_LOCAL_SCRIPT = SCRIPT_DIR / "run_local.py"
RUNS_DIR = SCRIPT_DIR / "runs"
DEFAULT_SOURCE_MANIFEST = (
    RUNS_DIR / "sessions-4090-parallel-750x2_20260307_040828" / "manifest.json"
)


def now_ts() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S")


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def normalize_label(raw: str) -> str:
    safe = "".join(ch if ch.isalnum() or ch in "-._" else "-" for ch in raw).strip(".-")
    if not safe:
        raise SystemExit("Benchmark label must contain at least one alphanumeric character")
    return safe


def parse_csv_list(raw: str) -> list[str]:
    return [item.strip() for item in raw.split(",") if item.strip()]


def parse_slot_list(raw: str) -> list[int]:
    slots = []
    for part in parse_csv_list(raw):
        try:
            slot = int(part)
        except ValueError as exc:
            raise SystemExit(f"Invalid slot count: {part}") from exc
        if slot < 1:
            raise SystemExit("Slot counts must be >= 1")
        slots.append(slot)
    if not slots:
        raise SystemExit("At least one slot count is required")
    return slots


def resolve_source_manifest(raw: str | None) -> Path:
    if raw is None:
        return DEFAULT_SOURCE_MANIFEST
    path = Path(raw)
    if path.is_dir():
        path = path / "manifest.json"
    if not path.is_absolute():
        path = (Path.cwd() / path).resolve()
    return path


def resolve_domains(source_manifest: dict, explicit: list[str] | None) -> list[str]:
    available = list(source_manifest.get("domains", {}).keys())
    if explicit:
        missing = [domain for domain in explicit if domain not in available]
        if missing:
            raise SystemExit(
                f"Domains missing from source manifest: {', '.join(missing)}"
            )
        return explicit
    return available


def start_gpu_sampler(samples_path: Path) -> subprocess.Popen | None:
    cmd = (
        "while true; do "
        "ts=$(date -Iseconds); "
        "nvidia-smi --query-gpu=memory.used,memory.total,utilization.gpu "
        "--format=csv,noheader,nounits | "
        "awk -F', ' -v ts=\"$ts\" '{print ts\",\"$1\",\"$2\",\"$3}'; "
        "sleep 2; "
        "done"
    )
    handle = samples_path.open("w", encoding="utf-8")
    handle.write("timestamp,memory_used_mb,memory_total_mb,utilization_gpu\n")
    handle.flush()
    process = subprocess.Popen(
        ["bash", "-lc", cmd],
        stdout=handle,
        stderr=subprocess.DEVNULL,
        text=True,
    )
    process._log_handle = handle  # type: ignore[attr-defined]
    return process


def stop_sampler(process: subprocess.Popen | None) -> None:
    if process is None:
        return
    try:
        process.terminate()
        process.wait(timeout=5)
    except Exception:
        try:
            process.kill()
        except Exception:
            pass
    handle = getattr(process, "_log_handle", None)
    if handle is not None:
        try:
            handle.close()
        except Exception:
            pass


def summarize_gpu_samples(samples_path: Path) -> dict:
    peak_used = 0
    max_util = 0
    total_mb = None
    count = 0
    if not samples_path.exists():
        return {
            "samples_path": str(samples_path),
            "sample_count": 0,
            "peak_memory_used_mb": 0,
            "memory_total_mb": None,
            "peak_utilization_gpu": 0,
        }
    with samples_path.open("r", encoding="utf-8") as handle:
        next(handle, None)
        for line in handle:
            parts = line.strip().split(",")
            if len(parts) != 4:
                continue
            _ts, used_raw, total_raw, util_raw = parts
            try:
                used = int(used_raw)
                total = int(total_raw)
                util = int(util_raw)
            except ValueError:
                continue
            peak_used = max(peak_used, used)
            max_util = max(max_util, util)
            total_mb = total
            count += 1
    return {
        "samples_path": str(samples_path),
        "sample_count": count,
        "peak_memory_used_mb": peak_used,
        "memory_total_mb": total_mb,
        "peak_utilization_gpu": max_util,
    }


def build_command(
    *,
    domain: str,
    dataset_path: Path,
    output_dir: Path,
    model_name: str,
    seq_len: int,
    epochs: int,
    max_samples: int | None,
    tokenize_workers: int,
    device: str,
    offline: bool,
    eval_enabled: bool,
) -> list[str]:
    command = [
        sys.executable,
        str(RUN_LOCAL_SCRIPT),
        domain,
        "--device",
        device,
        "--dataset-path",
        str(dataset_path),
        "--model",
        model_name,
        "--seq-len",
        str(seq_len),
        "--epochs",
        str(epochs),
        "--tokenize-workers",
        str(tokenize_workers),
        "--output-dir",
        str(output_dir),
        "--verbose",
    ]
    if max_samples is not None:
        command.extend(["--max-samples", str(max_samples)])
    if offline:
        command.append("--offline")
    if eval_enabled:
        command.append("--eval")
    return command


def terminate_active(processes: dict[str, tuple[subprocess.Popen, object]]) -> None:
    for process, handle in processes.values():
        try:
            process.terminate()
        except Exception:
            pass
        try:
            handle.close()
        except Exception:
            pass
    time.sleep(2)
    for process, _handle in processes.values():
        if process.poll() is None:
            try:
                process.kill()
            except Exception:
                pass


def run_slot_benchmark(
    *,
    source_manifest: dict,
    domains: list[str],
    slots: int,
    benchmark_root: Path,
    student_model: str,
    seq_len: int,
    epochs: int,
    max_samples: int | None,
    tokenize_workers: int,
    device: str,
    offline: bool,
    eval_enabled: bool,
) -> dict:
    slot_dir = benchmark_root / f"slots-{slots}"
    logs_dir = slot_dir / "logs"
    outputs_dir = slot_dir / "models"
    logs_dir.mkdir(parents=True, exist_ok=True)
    outputs_dir.mkdir(parents=True, exist_ok=True)
    samples_path = slot_dir / "gpu_samples.csv"

    manifest = {
        "version": 1,
        "created_at": now_ts(),
        "updated_at": now_ts(),
        "slot_count": slots,
        "student_model": student_model,
        "seq_len": seq_len,
        "epochs": epochs,
        "max_samples": max_samples,
        "tokenize_workers": tokenize_workers,
        "resolved_tokenize_workers_per_job": max(1, tokenize_workers // max(1, slots)),
        "device": device,
        "offline": offline,
        "eval": eval_enabled,
        "domains": {},
    }
    manifest_path = slot_dir / "manifest.json"

    pending = deque(domains)
    active: dict[str, tuple[subprocess.Popen, object]] = {}
    start_ts = time.time()
    sampler = start_gpu_sampler(samples_path)

    try:
        while pending or active:
            while pending and len(active) < slots:
                domain = pending.popleft()
                payload = source_manifest["domains"][domain]
                dataset_path = Path(payload["merged_out"])
                output_dir = outputs_dir / domain
                log_path = logs_dir / f"{domain}.log"
                effective_workers = max(1, tokenize_workers // max(1, slots))
                command = build_command(
                    domain=domain,
                    dataset_path=dataset_path,
                    output_dir=output_dir,
                    model_name=student_model,
                    seq_len=seq_len,
                    epochs=epochs,
                    max_samples=max_samples,
                    tokenize_workers=effective_workers,
                    device=device,
                    offline=offline,
                    eval_enabled=eval_enabled,
                )
                env = os.environ.copy()
                log_handle = log_path.open("w", encoding="utf-8")
                log_handle.write("$ " + " ".join(command) + "\n")
                log_handle.flush()
                process = subprocess.Popen(
                    command,
                    cwd=SCRIPT_DIR,
                    stdout=log_handle,
                    stderr=subprocess.STDOUT,
                    env=env,
                )
                active[domain] = (process, log_handle)
                manifest["domains"][domain] = {
                    "dataset_path": str(dataset_path),
                    "output_dir": str(output_dir),
                    "log_path": str(log_path),
                    "status": "running",
                    "started_at": now_ts(),
                    "pid": process.pid,
                }
                manifest["updated_at"] = now_ts()
                write_json(manifest_path, manifest)

            finished = []
            for domain, (process, log_handle) in active.items():
                returncode = process.poll()
                if returncode is None:
                    continue
                finished.append((domain, returncode, log_handle))

            for domain, returncode, log_handle in finished:
                log_handle.close()
                payload = manifest["domains"][domain]
                payload["status"] = "completed" if returncode == 0 else "failed"
                payload["completed_at"] = now_ts()
                payload["returncode"] = returncode
                run_json = Path(payload["output_dir"]) / "run.json"
                if run_json.exists():
                    try:
                        payload["run_manifest_path"] = str(run_json)
                        child = read_json(run_json)
                        llmfit = child.get("llmfit")
                        if llmfit is not None:
                            payload["llmfit"] = llmfit
                    except Exception:
                        pass
                del active[domain]
                manifest["updated_at"] = now_ts()
                write_json(manifest_path, manifest)
                if returncode != 0:
                    terminate_active(active)
                    raise SystemExit(
                        f"GPU slot benchmark failed for {domain} (see {payload['log_path']})"
                    )

            if pending or active:
                time.sleep(2)
    finally:
        stop_sampler(sampler)

    duration_seconds = round(time.time() - start_ts, 2)
    gpu_summary = summarize_gpu_samples(samples_path)
    manifest["updated_at"] = now_ts()
    manifest["duration_seconds"] = duration_seconds
    manifest["gpu"] = gpu_summary
    manifest["summary"] = {
        "domains_total": len(domains),
        "trains_completed": sum(
            1 for payload in manifest["domains"].values() if payload["status"] == "completed"
        ),
        "trains_failed": sum(
            1 for payload in manifest["domains"].values() if payload["status"] == "failed"
        ),
    }
    write_json(manifest_path, manifest)
    return {
        "slot_count": slots,
        "duration_seconds": duration_seconds,
        "gpu": gpu_summary,
        "manifest_path": str(manifest_path),
        "summary": manifest["summary"],
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Benchmark training slot counts against merged datasets from a prior batch run."
    )
    parser.add_argument(
        "--source-manifest",
        default=str(DEFAULT_SOURCE_MANIFEST),
        help="Source batch manifest or its run directory",
    )
    parser.add_argument(
        "--domains",
        default="",
        help="Comma-separated domain list (defaults to all domains in the source manifest)",
    )
    parser.add_argument(
        "--slots",
        default="1,2",
        help="Comma-separated slot counts to benchmark (default: 1,2)",
    )
    parser.add_argument(
        "--label",
        default="gpu-slots-benchmark",
        help="Benchmark run label",
    )
    parser.add_argument("--student-model", default=None)
    parser.add_argument("--seq-len", type=int, default=None)
    parser.add_argument("--epochs", type=int, default=None)
    parser.add_argument("--max-samples", type=int, default=None)
    parser.add_argument("--tokenize-workers", type=int, default=None)
    parser.add_argument("--device", default="gpu")
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--eval", action="store_true")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    source_manifest_path = resolve_source_manifest(args.source_manifest)
    if not source_manifest_path.exists():
        raise SystemExit(f"Source manifest not found: {source_manifest_path}")

    source_manifest = read_json(source_manifest_path)
    domains = resolve_domains(
        source_manifest,
        parse_csv_list(args.domains) if args.domains.strip() else None,
    )
    config = source_manifest.get("config", {})
    student_model = args.student_model or config.get("student_model")
    if not student_model:
        raise SystemExit("Student model missing from source manifest and CLI")

    seq_len = int(args.seq_len or config.get("seq_len") or 256)
    epochs = int(args.epochs or config.get("epochs") or 1)
    max_samples = args.max_samples
    if max_samples is None and config.get("student_max_samples") is not None:
        max_samples = int(config["student_max_samples"])
    tokenize_workers = int(args.tokenize_workers or config.get("tokenize_workers") or 1)
    slot_counts = parse_slot_list(args.slots)

    stamp = time.strftime("%Y%m%d_%H%M%S")
    benchmark_root = RUNS_DIR / f"{normalize_label(args.label)}_{stamp}"
    benchmark_root.mkdir(parents=True, exist_ok=True)

    summary = {
        "version": 1,
        "created_at": now_ts(),
        "source_manifest": str(source_manifest_path),
        "domains": domains,
        "student_model": student_model,
        "seq_len": seq_len,
        "epochs": epochs,
        "max_samples": max_samples,
        "tokenize_workers": tokenize_workers,
        "device": args.device,
        "offline": args.offline,
        "eval": args.eval,
        "results": [],
    }
    summary_path = benchmark_root / "summary.json"
    write_json(summary_path, summary)

    for slot_count in slot_counts:
        result = run_slot_benchmark(
            source_manifest=source_manifest,
            domains=domains,
            slots=slot_count,
            benchmark_root=benchmark_root,
            student_model=student_model,
            seq_len=seq_len,
            epochs=epochs,
            max_samples=max_samples,
            tokenize_workers=tokenize_workers,
            device=args.device,
            offline=args.offline,
            eval_enabled=args.eval,
        )
        summary["results"].append(result)
        write_json(summary_path, summary)

    if len(summary["results"]) >= 2:
        baseline = summary["results"][0]
        for result in summary["results"][1:]:
            if result["duration_seconds"] <= 0:
                continue
            result["speedup_vs_first"] = round(
                baseline["duration_seconds"] / result["duration_seconds"], 3
            )
        write_json(summary_path, summary)

    print(f"[DONE] summary={summary_path}")
    for result in summary["results"]:
        gpu = result["gpu"]
        print(
            f"[RESULT] slots={result['slot_count']} "
            f"duration={result['duration_seconds']}s "
            f"peak_vram={gpu['peak_memory_used_mb']}MB "
            f"peak_util={gpu['peak_utilization_gpu']}%"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
