#!/usr/bin/env python3
"""Batch orchestration for local teacher distillation and GPU fine-tuning."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from urllib import error, request

import torch

from dataset_bootstrap import ensure_seed_dataset
from llmfit_utils import (
    build_llmfit_record,
    env_flag,
    plan_model_with_llmfit,
    write_llmfit_plan,
)
from run_local import (
    probe_cuda as probe_run_local_cuda,
    reject_teacher_only_student,
    resolve_model as resolve_run_local_model,
)
from sharegpt_utils import (
    count_missing_row_ids,
    dedupe_rows,
    ensure_row_ids,
    load_jsonl,
    validate_rows,
    write_jsonl,
)

SCRIPT_DIR = Path(__file__).resolve().parent
DISTILL_SCRIPT = SCRIPT_DIR / "distill_dataset.py"
RUN_LOCAL_SCRIPT = SCRIPT_DIR / "run_local.py"
DATASETS_DIR = SCRIPT_DIR / "datasets"
RUNS_DIR = SCRIPT_DIR / "runs"
ROOT_DIR = SCRIPT_DIR.parent
DEFAULT_API_URLS = ["http://127.0.0.1:8100"]
LOCAL_HF_PROVIDER = "local-hf"
DEFAULT_OLLAMA_API_URL = "http://127.0.0.1:11434"

DEFAULT_DOMAINS = ["esp32", "spice", "pio"]
ALIAS_MAP = {
    "esp32": "iot",
    "pio": "platformio",
}
SUPPORTED_DOMAINS = [
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
    "project",
]


@dataclass
class DomainJob:
    label: str
    canonical: str
    source_dataset: Path
    distilled_out: Path
    merged_out: Path
    report_path: Path
    failures_out: Path
    retry_out: Path
    retry_report_path: Path
    retry_failures_out: Path
    train_output_dir: Path
    train_run_manifest: Path
    train_llmfit_plan: Path
    distill_log: Path
    train_log: Path


def canonical_domain(raw_domain: str) -> str:
    return ALIAS_MAP.get(raw_domain, raw_domain)


def now_ts() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S")


def resolve_path(raw_path: str | None) -> Path | None:
    if raw_path is None:
        return None
    path = Path(raw_path)
    if not path.is_absolute():
        path = (Path.cwd() / path).resolve()
    return path


def resolve_batch_student_model(config: dict) -> tuple[str, str | None, str]:
    requested_model = config.get("student_model")
    gpu_ready, _gpu_reason = probe_run_local_cuda()
    resolved_device = (
        "gpu"
        if (
            config.get("device") == "gpu"
            or (config.get("device") == "auto" and gpu_ready)
        )
        else "cpu"
    )
    model_name, model_note = resolve_run_local_model(
        requested_model,
        resolved_device,
        bool(config.get("offline")),
    )
    reject_teacher_only_student(model_name)
    return model_name, model_note, resolved_device


def load_env_var_from_dotenv(name: str) -> str | None:
    env_path = ROOT_DIR / ".env"
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


def write_manifest(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def build_jobs(
    *,
    labels: list[str],
    run_dir: Path,
    run_label: str,
    stamp: str,
    source_dataset_override: Path | None = None,
) -> dict[str, DomainJob]:
    jobs: dict[str, DomainJob] = {}
    log_dir = run_dir / "logs"
    if source_dataset_override is not None and len(labels) != 1:
        raise SystemExit("--source-dataset only supports a single domain label")
    for label in labels:
        canonical = canonical_domain(label)
        if canonical not in SUPPORTED_DOMAINS:
            raise SystemExit(f"Unsupported domain: {label} -> {canonical}")
        source_dataset = (
            source_dataset_override
            if source_dataset_override is not None
            else DATASETS_DIR / f"{canonical}_chat.jsonl"
        )
        if not source_dataset.exists():
            builder = ensure_seed_dataset(SCRIPT_DIR, canonical, source_dataset)
            if builder is not None:
                print(f"[BOOTSTRAP] built seed dataset for {label} via {builder.name}")
        if not source_dataset.exists():
            raise SystemExit(f"Source dataset not found: {source_dataset}")
        jobs[label] = DomainJob(
            label=label,
            canonical=canonical,
            source_dataset=source_dataset,
            distilled_out=run_dir / f"{label}_teacher_{stamp}.jsonl",
            merged_out=run_dir / f"{label}_teacher_mix_{stamp}.jsonl",
            report_path=run_dir / f"{label}_teacher_{stamp}.report.json",
            failures_out=run_dir / f"{label}_teacher_{stamp}.failures.jsonl",
            retry_out=run_dir / f"{label}_teacher_retry_{stamp}.jsonl",
            retry_report_path=run_dir / f"{label}_teacher_retry_{stamp}.report.json",
            retry_failures_out=run_dir
            / f"{label}_teacher_retry_{stamp}.failures.jsonl",
            train_output_dir=SCRIPT_DIR
            / "models_local"
            / f"{label}_{run_label}_{stamp}",
            train_run_manifest=SCRIPT_DIR
            / "models_local"
            / f"{label}_{run_label}_{stamp}"
            / "run.json",
            train_llmfit_plan=SCRIPT_DIR
            / "models_local"
            / f"{label}_{run_label}_{stamp}"
            / "llmfit_plan.json",
            distill_log=log_dir / f"{label}_distill.log",
            train_log=log_dir / f"{label}_train.log",
        )
    return jobs


def build_new_manifest(
    args: argparse.Namespace, run_dir: Path, labels: list[str], stamp: str
) -> dict:
    jobs = build_jobs(
        labels=labels,
        run_dir=run_dir,
        run_label=args.run_label,
        stamp=stamp,
        source_dataset_override=resolve_path(args.source_dataset),
    )
    domains: dict[str, dict] = {}
    for label, job in jobs.items():
        domains[label] = {
            "label": label,
            "canonical": job.canonical,
            "source_dataset": str(job.source_dataset),
            "distilled_out": str(job.distilled_out),
            "merged_out": str(job.merged_out),
            "report_path": str(job.report_path),
            "failures_out": str(job.failures_out),
            "retry_out": str(job.retry_out),
            "retry_report_path": str(job.retry_report_path),
            "retry_failures_out": str(job.retry_failures_out),
            "train_output_dir": str(job.train_output_dir),
            "train_run_manifest": str(job.train_run_manifest),
            "train_llmfit_plan": str(job.train_llmfit_plan),
            "distill_log": str(job.distill_log),
            "train_log": str(job.train_log),
            "source_validation": {"status": "pending"},
            "distill": {"status": "pending"},
            "train": {
                "status": "skipped" if args.skip_train else "pending",
            },
        }
    return {
        "version": 1,
        "created_at": now_ts(),
        "updated_at": now_ts(),
        "run_dir": str(run_dir),
        "run_label": args.run_label,
        "stamp": stamp,
        "config": {
            "teacher_provider": args.teacher_provider,
            "teacher_model": args.teacher_model,
            "api_urls": args.api_urls or DEFAULT_API_URLS,
            "teacher_only": args.teacher_only,
            "strategy": args.strategy,
            "temperature": args.temperature,
            "max_tokens": args.max_tokens,
            "timeout": args.timeout,
            "max_source_samples": args.max_source_samples,
            "samples_per_source": args.samples_per_source,
            "max_parallel_distills": args.max_parallel_distills,
            "json_retries": args.json_retries,
            "seed": args.seed,
            "sleep_ms": args.sleep_ms,
            "source_dataset_override": args.source_dataset,
            "teacher_system_path": args.teacher_system_path,
            "overlap_teacher_train": args.overlap_teacher_train,
            "device": args.device,
            "student_model": args.student_model,
            "student_max_samples": args.student_max_samples,
            "seq_len": args.seq_len,
            "epochs": args.epochs,
            "tokenize_workers": args.tokenize_workers,
            "skip_train": args.skip_train,
            "offline": args.offline,
            "eval": args.eval,
            "max_parallel_gpu_trains": args.max_parallel_gpu_trains,
            "gpu_job_vram_mb": args.gpu_job_vram_mb,
            "gpu_buffer_mb": args.gpu_buffer_mb,
            "llmfit_preflight": env_flag("LLMFIT_PREFLIGHT", True),
            "llmfit_min_fit": os.environ.get("LLMFIT_MIN_FIT", "marginal"),
            "llmfit_memory": os.environ.get("LLMFIT_MEMORY"),
            "llmfit_bin": os.environ.get("LLMFIT_BIN"),
            "llmfit_root": os.environ.get("LLMFIT_ROOT"),
            "llmfit_allow_cargo_run": env_flag("LLMFIT_ALLOW_CARGO_RUN", False),
        },
        "reports": {
            "dataset_report": str(run_dir / "dataset_report.json"),
        },
        "domains": domains,
    }


def load_resume_manifest(resume_path: Path) -> dict:
    manifest_path = (
        resume_path / "manifest.json" if resume_path.is_dir() else resume_path
    )
    if not manifest_path.exists():
        raise SystemExit(f"Resume manifest not found: {manifest_path}")
    return json.loads(manifest_path.read_text(encoding="utf-8"))


def pid_is_running(pid: int | None) -> bool:
    if pid is None or pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def reconcile_resume_manifest(manifest: dict, jobs: dict[str, DomainJob]) -> bool:
    changed = False
    for label, payload in manifest["domains"].items():
        train = payload.get("train", {})
        if train.get("status") != "running":
            continue

        job = jobs[label]
        child_run = load_json_if_exists(job.train_run_manifest) or {}
        child_status = child_run.get("status")
        child_llmfit = child_run.get("llmfit")

        if child_status == "completed":
            payload["train"] = {
                "status": "completed",
                "completed_at": child_run.get("updated_at") or now_ts(),
                "returncode": (child_run.get("result") or {}).get("returncode", 0),
                "run_manifest_path": str(job.train_run_manifest),
            }
            if child_llmfit is not None:
                payload["train"]["llmfit"] = child_llmfit
            training_info = (child_run.get("artifacts", {}) or {}).get("training_info")
            if training_info is not None:
                payload["train"]["training_info"] = training_info
            changed = True
            continue

        pid = train.get("pid")
        pid_int = int(pid) if isinstance(pid, int) or str(pid).isdigit() else None
        if pid_is_running(pid_int):
            continue

        payload["train"] = {
            "status": "pending",
            "llmfit": train.get("llmfit"),
        }
        changed = True
    return changed


def jobs_from_manifest(manifest: dict) -> dict[str, DomainJob]:
    jobs: dict[str, DomainJob] = {}
    for label, payload in manifest["domains"].items():
        jobs[label] = DomainJob(
            label=label,
            canonical=payload["canonical"],
            source_dataset=Path(payload["source_dataset"]),
            distilled_out=Path(payload["distilled_out"]),
            merged_out=Path(payload["merged_out"]),
            report_path=Path(payload["report_path"]),
            failures_out=Path(payload["failures_out"]),
            retry_out=Path(payload["retry_out"]),
            retry_report_path=Path(payload["retry_report_path"]),
            retry_failures_out=Path(payload["retry_failures_out"]),
            train_output_dir=Path(payload["train_output_dir"]),
            train_run_manifest=Path(payload["train_run_manifest"]),
            train_llmfit_plan=Path(payload["train_llmfit_plan"]),
            distill_log=Path(payload["distill_log"]),
            train_log=Path(payload["train_log"]),
        )
    return jobs


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def load_json_if_exists(path: Path) -> dict | None:
    if not path.exists():
        return None
    return read_json(path)


def load_jsonl_if_exists(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return load_jsonl(path)


def load_normalized_rows(path: Path, prefix: str) -> tuple[list[dict], int]:
    raw_rows = load_jsonl(path)
    missing_ids_fixed = count_missing_row_ids(raw_rows)
    normalized_rows = ensure_row_ids(raw_rows, prefix)
    return normalized_rows, missing_ids_fixed


def prevalidate_source_dataset(job: DomainJob) -> dict:
    source_rows, missing_ids_fixed = load_normalized_rows(
        job.source_dataset, f"{job.canonical}-source"
    )
    if not source_rows:
        raise RuntimeError(f"Source dataset is empty: {job.source_dataset}")
    validation_errors = validate_rows(source_rows)
    if validation_errors:
        sample = "; ".join(validation_errors[:3])
        raise RuntimeError(
            f"Source dataset invalid ({len(validation_errors)} errors): {sample}"
        )
    return {
        "status": "completed",
        "validated_at": now_ts(),
        "source_rows": len(source_rows),
        "missing_ids_fixed": missing_ids_fixed,
    }


def merge_source_and_distilled(job: DomainJob) -> dict[str, int]:
    source_rows, source_missing_ids_fixed = load_normalized_rows(
        job.source_dataset, f"{job.canonical}-source"
    )
    distilled_payload = load_jsonl_if_exists(job.distilled_out)
    distilled_missing_ids_fixed = count_missing_row_ids(distilled_payload)
    distilled_rows = ensure_row_ids(distilled_payload, f"{job.canonical}-distill")
    merged_rows = dedupe_rows(source_rows + distilled_rows)
    validation_errors = validate_rows(merged_rows)
    if validation_errors:
        raise RuntimeError(
            f"Merged dataset is invalid ({len(validation_errors)} errors)"
        )
    write_jsonl(job.merged_out, merged_rows)
    return {
        "source_rows": len(source_rows),
        "source_missing_ids_fixed": source_missing_ids_fixed,
        "distilled_rows": len(distilled_rows),
        "distilled_missing_ids_fixed": distilled_missing_ids_fixed,
        "merged_rows": len(merged_rows),
    }


def append_command_header(handle, command: list[str]) -> None:
    handle.write(f"$ {' '.join(command)}\n")
    handle.flush()


def run_distill_pass(
    *,
    job: DomainJob,
    config: dict,
    source_dataset: Path,
    out_path: Path,
    report_path: Path,
    failures_out: Path,
    concurrency: int,
    log_handle,
) -> None:
    command = [
        sys.executable,
        str(DISTILL_SCRIPT),
        job.canonical,
        "--source-dataset",
        str(source_dataset),
        "--out",
        str(out_path),
        "--report-path",
        str(report_path),
        "--failures-out",
        str(failures_out),
        "--strategy",
        config["strategy"],
        "--temperature",
        str(config["temperature"]),
        "--max-tokens",
        str(config["max_tokens"]),
        "--timeout",
        str(config["timeout"]),
        "--max-source-samples",
        str(config["max_source_samples"]),
        "--samples-per-source",
        str(config["samples_per_source"]),
        "--concurrency",
        str(concurrency),
        "--json-retries",
        str(config["json_retries"]),
        "--seed",
        str(config["seed"]),
        "--sleep-ms",
        str(config["sleep_ms"]),
        "--teacher-provider",
        config["teacher_provider"],
        "--teacher-model",
        config["teacher_model"],
        "--verbose",
    ]
    if config["teacher_system_path"]:
        command.extend(["--teacher-system-path", config["teacher_system_path"]])
    for api_url in config["api_urls"]:
        command.extend(["--api-url", api_url])
    append_command_header(log_handle, command)
    completed = subprocess.run(
        command, cwd=SCRIPT_DIR, stdout=log_handle, stderr=subprocess.STDOUT
    )
    if completed.returncode != 0:
        raise RuntimeError(f"distill pass failed ({completed.returncode})")


def run_distill_job(job: DomainJob, config: dict, concurrency: int) -> dict:
    job.distill_log.parent.mkdir(parents=True, exist_ok=True)
    job.distilled_out.parent.mkdir(parents=True, exist_ok=True)
    with job.distill_log.open("a", encoding="utf-8") as log_handle:
        run_distill_pass(
            job=job,
            config=config,
            source_dataset=job.source_dataset,
            out_path=job.distilled_out,
            report_path=job.report_path,
            failures_out=job.failures_out,
            concurrency=concurrency,
            log_handle=log_handle,
        )

        report = read_json(job.report_path)
        initial_failures = len(report.get("failures", []))
        retry_failures = 0
        retry_rows = 0

        if (
            initial_failures
            and job.failures_out.exists()
            and job.failures_out.stat().st_size > 0
        ):
            log_handle.write("\n[RETRY] rerunning failures with concurrency=1\n")
            log_handle.flush()
            run_distill_pass(
                job=job,
                config=config,
                source_dataset=job.failures_out,
                out_path=job.retry_out,
                report_path=job.retry_report_path,
                failures_out=job.retry_failures_out,
                concurrency=1,
                log_handle=log_handle,
            )
            retry_report = read_json(job.retry_report_path)
            retry_failures = len(retry_report.get("failures", []))
            base_rows = load_jsonl_if_exists(job.distilled_out)
            retry_rows_payload = load_jsonl_if_exists(job.retry_out)
            retry_rows = len(retry_rows_payload)
            combined_rows = dedupe_rows(base_rows + retry_rows_payload)
            write_jsonl(job.distilled_out, combined_rows)
            report["retry_report_path"] = str(job.retry_report_path)
            report["retry_failures_out"] = str(job.retry_failures_out)
            report["retry_generated_rows"] = retry_rows
            report["retry_remaining_failures"] = retry_failures
            report["generated_rows"] = len(combined_rows)
            report_path = job.report_path
            report_path.write_text(
                json.dumps(report, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )

    merge_stats = merge_source_and_distilled(job)
    return {
        "initial_failures": initial_failures,
        "retry_failures": retry_failures,
        "retry_rows": retry_rows,
        **merge_stats,
    }


def resolve_overlap_teacher_train(config: dict) -> bool:
    requested = config.get("overlap_teacher_train")
    if requested is not None:
        return bool(requested)
    if config.get("teacher_provider") == LOCAL_HF_PROVIDER:
        return False
    return True


def resolve_train_slot_limit(config: dict, active_distills: dict[object, str]) -> int:
    slots = max(1, int(config.get("max_parallel_gpu_trains") or 1))
    if slots <= 1:
        return 1
    if active_distills:
        # A 14B Ollama teacher plus 2x 4B students overruns a single 4090.
        return 1
    return slots


def resolve_ollama_api_url(config: dict) -> str:
    return str(
        config.get("teacher_ollama_api_url")
        or os.environ.get("OLLAMA_API_URL")
        or DEFAULT_OLLAMA_API_URL
    ).rstrip("/")


def unload_ollama_model(config: dict) -> tuple[bool, str]:
    if str(config.get("teacher_provider") or "").lower() != "ollama":
        return False, "teacher unload skipped: provider is not ollama"

    model = str(config.get("teacher_model") or "").strip()
    if not model:
        return False, "teacher unload skipped: no teacher model configured"

    api_url = resolve_ollama_api_url(config)
    body = json.dumps(
        {
            "model": model,
            "prompt": "",
            "stream": False,
            "keep_alive": 0,
        }
    ).encode("utf-8")
    req = request.Request(
        f"{api_url}/api/generate",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=15) as response:
            response.read()
        return True, f"teacher unloaded via Ollama API: {model}"
    except error.URLError as exc:
        return False, f"teacher unload skipped: {exc}"


def estimate_student_train_vram_mb(
    config: dict, llmfit_record: dict | None = None
) -> int:
    explicit = int(config.get("gpu_job_vram_mb") or 0)
    if explicit > 0:
        return explicit

    model_name = str(config.get("student_model") or "").lower()
    seq_len = int(config.get("seq_len") or 512)
    recommended_vram_gb = None
    if llmfit_record is not None:
        recommended_vram_gb = llmfit_record.get("recommended_vram_gb")

    if recommended_vram_gb is None:
        try:
            summary = plan_model_with_llmfit(
                model_name=str(config.get("student_model")),
                context=seq_len,
                llmfit_bin=os.environ.get("LLMFIT_BIN"),
                llmfit_root=os.environ.get("LLMFIT_ROOT"),
                memory_override=os.environ.get("LLMFIT_MEMORY"),
                allow_cargo_run=env_flag("LLMFIT_ALLOW_CARGO_RUN", False),
                timeout=30,
            )
        except Exception:
            summary = None
        if summary is not None:
            recommended_vram_gb = summary.recommended_vram_gb

    if recommended_vram_gb is not None:
        base = int(recommended_vram_gb * 1024 * 1.6)
    elif "qwen/qwen3.5-9b" in model_name or "qwen/qwen3-8b" in model_name:
        base = 12288
    elif "qwen/qwen2.5-coder-7b" in model_name or "7b" in model_name:
        base = 10240
    elif "qwen/qwen3-4b" in model_name or "4b" in model_name:
        base = 6144
    elif "qwen/qwen2.5-coder-1.5b" in model_name or "1.5b" in model_name:
        base = 4096
    elif "tinyllama" in model_name or "1.1b" in model_name:
        base = 3072
    else:
        base = 6144

    if seq_len > 512:
        base += int(((seq_len - 512) / 256) * 512)
    return max(2048, base)


def probe_vram_mb() -> tuple[int, int]:
    if not torch.cuda.is_available():
        return 0, 0
    free_bytes, total_bytes = torch.cuda.mem_get_info()
    return int(free_bytes / 1024**2), int(total_bytes / 1024**2)


def gpu_wait_reason(config: dict, active_gpu_jobs: int) -> str | None:
    if config["device"] != "gpu":
        return None
    if not torch.cuda.is_available():
        return "CUDA unavailable for batch training"
    free_mb, _total_mb = probe_vram_mb()
    required_mb = config["resolved_gpu_job_vram_mb"] + config["gpu_buffer_mb"]
    if free_mb < required_mb:
        return (
            f"GPU memory busy: free={free_mb}MB required>={required_mb}MB "
            f"active_batch_jobs={active_gpu_jobs}"
        )
    return None


def can_start_gpu_job(config: dict, active_gpu_jobs: int) -> bool:
    return gpu_wait_reason(config, active_gpu_jobs) is None


def start_train_process(
    job: DomainJob, config: dict, train_slot_limit: int | None = None
):
    job.train_log.parent.mkdir(parents=True, exist_ok=True)
    tokenize_workers = config["tokenize_workers"]
    effective_slots = max(1, train_slot_limit or config["max_parallel_gpu_trains"])
    if tokenize_workers > 1 and effective_slots > 1:
        tokenize_workers = max(1, tokenize_workers // effective_slots)

    command = [
        sys.executable,
        str(RUN_LOCAL_SCRIPT),
        job.canonical,
        "--device",
        config["device"],
        "--dataset-path",
        str(job.merged_out),
        "--model",
        config["student_model"],
        "--seq-len",
        str(config["seq_len"]),
        "--epochs",
        str(config["epochs"]),
        "--tokenize-workers",
        str(tokenize_workers),
        "--output-dir",
        str(job.train_output_dir),
        "--verbose",
    ]
    if config["student_max_samples"] is not None:
        command.extend(["--max-samples", str(config["student_max_samples"])])
    if config["offline"]:
        command.append("--offline")
    if config["eval"]:
        command.append("--eval")

    log_handle = job.train_log.open("a", encoding="utf-8")
    append_command_header(log_handle, command)
    process = subprocess.Popen(
        command,
        cwd=SCRIPT_DIR,
        stdout=log_handle,
        stderr=subprocess.STDOUT,
    )
    return process, log_handle


def stop_active_trains(
    active_trains: dict[str, tuple[subprocess.Popen, object]]
) -> None:
    for process, log_handle in active_trains.values():
        try:
            process.terminate()
        except Exception:
            pass
        try:
            log_handle.close()
        except Exception:
            pass


def write_dataset_report(path: Path, manifest: dict) -> None:
    domains_report: dict[str, dict] = {}
    for label, payload in manifest.get("domains", {}).items():
        source_validation = payload.get("source_validation", {})
        distill = payload.get("distill", {})
        train = payload.get("train", {})
        domains_report[label] = {
            "canonical": payload.get("canonical"),
            "source_status": source_validation.get("status"),
            "source_rows": source_validation.get("source_rows"),
            "source_missing_ids_fixed": source_validation.get("missing_ids_fixed"),
            "distill_status": distill.get("status"),
            "distilled_rows": distill.get("distilled_rows"),
            "distilled_missing_ids_fixed": distill.get("distilled_missing_ids_fixed"),
            "merged_rows": distill.get("merged_rows"),
            "train_status": train.get("status"),
        }
    write_manifest(
        path,
        {
            "generated_at": now_ts(),
            "run_dir": manifest["run_dir"],
            "run_label": manifest.get("run_label"),
            "domains": domains_report,
        },
    )


def save_updated_manifest(manifest_path: Path, manifest: dict) -> None:
    manifest["updated_at"] = now_ts()
    write_manifest(manifest_path, manifest)
    dataset_report_path = (
        Path(manifest.get("reports", {}).get("dataset_report"))
        if manifest.get("reports", {}).get("dataset_report")
        else Path(manifest["run_dir"]) / "dataset_report.json"
    )
    write_dataset_report(dataset_report_path, manifest)


def domain_done(payload: dict, phase: str) -> bool:
    return payload[phase]["status"] == "completed"


def resolve_batch_llmfit(config: dict, run_dir: Path) -> dict:
    enabled = bool(config.get("llmfit_preflight", True))
    requested_device = str(config.get("device") or "gpu")
    model_name = str(config.get("student_model") or "")
    context = int(config.get("seq_len") or 256)
    minimum_fit = str(config.get("llmfit_min_fit") or "marginal")
    report_path = run_dir / "llmfit_plan.json"

    if config.get("skip_train"):
        return {
            "enabled": enabled,
            "requested_device": requested_device,
            "model": model_name,
            "context": context,
            "minimum_fit": minimum_fit,
            "status": "skipped",
            "reason": "Training skipped by configuration",
            "train_blocked": False,
            "report_path": str(report_path),
        }

    if requested_device != "gpu":
        record = build_llmfit_record(
            enabled=enabled,
            requested_device=requested_device,
            model_name=model_name,
            context=context,
            minimum_fit=minimum_fit,
        )
        record["train_blocked"] = False
        return record

    summary = None
    warning = None
    if enabled:
        try:
            summary = plan_model_with_llmfit(
                model_name=model_name,
                context=context,
                llmfit_bin=config.get("llmfit_bin"),
                llmfit_root=config.get("llmfit_root"),
                memory_override=config.get("llmfit_memory"),
                allow_cargo_run=bool(config.get("llmfit_allow_cargo_run")),
                timeout=30,
            )
            if summary is None:
                warning = (
                    "llmfit preflight skipped: no llmfit binary found. "
                    "Build /ai/saisail/llmfit with cargo +stable build --release -p llmfit "
                    "or set LLMFIT_BIN."
                )
            else:
                write_llmfit_plan(report_path, summary)
        except Exception as exc:  # noqa: BLE001
            warning = f"llmfit preflight skipped: {exc}"

    record = build_llmfit_record(
        enabled=enabled,
        requested_device=requested_device,
        model_name=model_name,
        context=context,
        minimum_fit=minimum_fit,
        summary=summary,
        report_path=report_path if summary is not None else None,
        warning=warning,
    )
    record["train_blocked"] = record["status"] == "rejected"
    return record


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Batch local distillation + GPU training orchestrator"
    )
    parser.add_argument(
        "domains", nargs="*", help="Domain labels or aliases (default: esp32 spice pio)"
    )
    parser.add_argument(
        "--resume", default=None, help="Existing run dir or manifest.json to resume"
    )
    parser.add_argument("--run-label", default="batch")
    parser.add_argument(
        "--api-url",
        action="append",
        dest="api_urls",
        help="Mascarade base URL, repeatable",
    )
    parser.add_argument("--teacher-provider", default="ollama")
    parser.add_argument("--teacher-model", default="qwen2.5:14b")
    parser.add_argument("--strategy", default="best")
    parser.add_argument("--temperature", type=float, default=0.4)
    parser.add_argument("--max-tokens", type=int, default=2048)
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--max-source-samples", type=int, default=96)
    parser.add_argument("--samples-per-source", type=int, default=1)
    parser.add_argument("--json-retries", type=int, default=3)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--sleep-ms", type=int, default=0)
    parser.add_argument(
        "--source-dataset",
        default=None,
        help="Override source ShareGPT JSONL path for a single-domain run",
    )
    parser.add_argument("--teacher-system-path", default=None)
    parser.add_argument(
        "--max-parallel-distills",
        type=int,
        default=6,
        help="Global budget for teacher calls across domains",
    )
    parser.add_argument(
        "--max-parallel-gpu-trains",
        type=int,
        default=1,
        help="GPU training slots (1 or 2)",
    )
    parser.add_argument("--gpu-job-vram-mb", type=int, default=0)
    parser.add_argument("--gpu-buffer-mb", type=int, default=512)
    parser.add_argument(
        "--overlap-teacher-train",
        dest="overlap_teacher_train",
        action="store_true",
        default=None,
        help="Allow training to start while other domains are still distilling",
    )
    parser.add_argument(
        "--no-overlap-teacher-train",
        dest="overlap_teacher_train",
        action="store_false",
        help="Force the old two-phase behavior: all distills, then all trainings",
    )
    parser.add_argument("--device", choices=["gpu", "cpu", "auto"], default="gpu")
    parser.add_argument("--student-model", default=None)
    parser.add_argument("--student-max-samples", type=int, default=None)
    parser.add_argument("--seq-len", type=int, default=256)
    parser.add_argument("--epochs", type=int, default=2)
    parser.add_argument("--tokenize-workers", type=int, default=4)
    parser.add_argument(
        "--teacher-only",
        action="store_true",
        help="Distill/merge only, skip local student training",
    )
    parser.add_argument("--skip-train", action="store_true")
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--eval", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()
    if args.teacher_only:
        args.skip_train = True
    ensure_local_api_key_env()

    if args.max_parallel_gpu_trains < 1 or args.max_parallel_gpu_trains > 2:
        raise SystemExit("--max-parallel-gpu-trains must be 1 or 2")

    if args.resume:
        manifest = load_resume_manifest(resolve_path(args.resume))
        manifest_path = Path(manifest["run_dir"]) / "manifest.json"
    else:
        raw_labels = args.domains or DEFAULT_DOMAINS
        stamp = time.strftime("%Y%m%d_%H%M%S")
        run_dir = RUNS_DIR / f"{args.run_label}_{stamp}"
        manifest = build_new_manifest(args, run_dir, raw_labels, stamp)
        manifest_path = run_dir / "manifest.json"
        save_updated_manifest(manifest_path, manifest)

    run_dir = Path(manifest["run_dir"])
    jobs = jobs_from_manifest(manifest)
    if args.resume and reconcile_resume_manifest(manifest, jobs):
        save_updated_manifest(manifest_path, manifest)
    config = manifest["config"]
    config["api_urls"] = config.get("api_urls") or DEFAULT_API_URLS
    config["teacher_system_path"] = config.get("teacher_system_path")
    config["student_max_samples"] = config.get("student_max_samples")
    config["teacher_only"] = config.get("teacher_only", False)
    config["skip_train"] = config.get("skip_train", False)
    config["llmfit_preflight"] = config.get(
        "llmfit_preflight", env_flag("LLMFIT_PREFLIGHT", True)
    )
    config["llmfit_min_fit"] = config.get(
        "llmfit_min_fit", os.environ.get("LLMFIT_MIN_FIT", "marginal")
    )
    config["llmfit_memory"] = config.get(
        "llmfit_memory", os.environ.get("LLMFIT_MEMORY")
    )
    config["llmfit_bin"] = config.get("llmfit_bin", os.environ.get("LLMFIT_BIN"))
    config["llmfit_root"] = config.get("llmfit_root", os.environ.get("LLMFIT_ROOT"))
    config["llmfit_allow_cargo_run"] = config.get(
        "llmfit_allow_cargo_run",
        env_flag("LLMFIT_ALLOW_CARGO_RUN", False),
    )
    requested_student_model = config.get("student_model")
    resolved_student_model, student_model_note, resolved_student_device = (
        resolve_batch_student_model(config)
    )
    config["requested_student_model"] = requested_student_model
    config["student_model"] = resolved_student_model
    config["resolved_student_device"] = resolved_student_device
    manifest["config"]["requested_student_model"] = requested_student_model
    manifest["config"]["student_model"] = resolved_student_model
    manifest["config"]["resolved_student_device"] = resolved_student_device
    if student_model_note:
        manifest["config"]["student_model_note"] = student_model_note
    config["teacher_ollama_api_url"] = resolve_ollama_api_url(config)
    config["resolved_overlap_teacher_train"] = resolve_overlap_teacher_train(config)
    batch_llmfit = resolve_batch_llmfit(config, run_dir)
    manifest["llmfit"] = batch_llmfit
    config["resolved_gpu_job_vram_mb"] = estimate_student_train_vram_mb(
        config,
        llmfit_record=batch_llmfit,
    )
    train_blocked_by_llmfit = bool(batch_llmfit.get("train_blocked"))
    for payload in manifest["domains"].values():
        if payload["train"]["status"] == "pending":
            payload["train"]["llmfit"] = {
                "status": batch_llmfit["status"],
                "reason": batch_llmfit.get("reason"),
                "report_path": batch_llmfit.get("report_path"),
            }
    save_updated_manifest(manifest_path, manifest)

    for label, payload in manifest["domains"].items():
        if payload["distill"]["status"] == "completed":
            continue
        try:
            source_validation = prevalidate_source_dataset(jobs[label])
        except Exception as exc:  # noqa: BLE001
            manifest["domains"][label]["source_validation"] = {
                "status": "failed",
                "validated_at": now_ts(),
                "error": str(exc),
            }
            save_updated_manifest(manifest_path, manifest)
            raise
        manifest["domains"][label]["source_validation"] = source_validation
        save_updated_manifest(manifest_path, manifest)
        print(f"[OK] source {label}: rows={source_validation['source_rows']}")
        if source_validation["missing_ids_fixed"]:
            print(
                f"[INFO] normalize {label}/source: "
                f"inserted_ids={source_validation['missing_ids_fixed']}"
            )

    print(f"[INFO] run_dir={run_dir}")
    print(f"[INFO] domains={' '.join(jobs.keys())}")
    print(f"[INFO] teacher={config['teacher_provider']}/{config['teacher_model']}")
    print(
        f"[INFO] student={config['student_model']} "
        f"(requested={config.get('requested_student_model') or 'auto'})"
    )
    print(f"[INFO] gpu_slots={config['max_parallel_gpu_trains']}")
    print(
        "[INFO] overlap_teacher_train="
        f"{config['resolved_overlap_teacher_train']} "
        f"gpu_job_vram_mb={config['resolved_gpu_job_vram_mb']}"
    )
    if student_model_note:
        print(student_model_note)
    if config["device"] == "gpu" and not config["skip_train"]:
        print(
            "[INFO] llmfit="
            f"{batch_llmfit['status']} "
            f"fit={batch_llmfit.get('current_fit_level', '-')} "
            f"gpu_path={'yes' if batch_llmfit.get('gpu_path_feasible') else 'no'}"
        )
        if batch_llmfit.get("reason"):
            print(f"[INFO] llmfit_reason={batch_llmfit['reason']}")

    pending_distills = deque(
        label
        for label, payload in manifest["domains"].items()
        if not domain_done(payload, "distill")
    )
    pending_trains = deque(
        label
        for label, payload in manifest["domains"].items()
        if not config["skip_train"]
        and not train_blocked_by_llmfit
        and payload["distill"]["status"] == "completed"
        and payload["train"]["status"] == "pending"
    )
    active_trains: dict[str, tuple[subprocess.Popen, object]] = {}
    active_distills: dict[object, str] = {}
    last_wait_notice = 0.0
    teacher_released_for_parallel_trains = False

    per_domain_concurrency = 1
    distill_workers = 0
    if pending_distills:
        if config["teacher_provider"] == LOCAL_HF_PROVIDER:
            config["max_parallel_distills"] = 1
        per_domain_concurrency = max(
            1, config["max_parallel_distills"] // max(1, len(pending_distills))
        )
        per_domain_concurrency = min(
            per_domain_concurrency, config["max_source_samples"]
        )
        if config["teacher_provider"] == LOCAL_HF_PROVIDER:
            per_domain_concurrency = 1
        distill_workers = (
            1
            if config["teacher_provider"] == LOCAL_HF_PROVIDER
            else max(
                1,
                min(
                    len(pending_distills),
                    max(1, config["max_parallel_distills"] // per_domain_concurrency),
                ),
            )
        )
        print(
            f"[INFO] pending_distills={len(pending_distills)} "
            f"per_domain_concurrency={per_domain_concurrency} "
            f"distill_workers={distill_workers}"
        )
    if pending_trains:
        print(f"[INFO] pending_trains={len(pending_trains)}")

    with ThreadPoolExecutor(max_workers=max(1, distill_workers or 1)) as executor:
        while pending_distills or active_distills or pending_trains or active_trains:
            while pending_distills and len(active_distills) < max(1, distill_workers):
                label = pending_distills.popleft()
                manifest["domains"][label]["distill"] = {
                    "status": "running",
                    "started_at": now_ts(),
                    "per_domain_concurrency": per_domain_concurrency,
                }
                save_updated_manifest(manifest_path, manifest)
                future = executor.submit(
                    run_distill_job, jobs[label], config, per_domain_concurrency
                )
                active_distills[future] = label

            for future, label in list(active_distills.items()):
                if not future.done():
                    continue
                del active_distills[future]
                try:
                    result = future.result()
                except Exception as exc:  # noqa: BLE001
                    stop_active_trains(active_trains)
                    manifest["domains"][label]["distill"] = {
                        "status": "failed",
                        "completed_at": now_ts(),
                        "error": str(exc),
                    }
                    save_updated_manifest(manifest_path, manifest)
                    raise

                manifest["domains"][label]["distill"] = {
                    "status": "completed",
                    "completed_at": now_ts(),
                    **result,
                }
                save_updated_manifest(manifest_path, manifest)
                print(
                    f"[OK] distill {label}: "
                    f"source={result['source_rows']} "
                    f"distilled={result['distilled_rows']} "
                    f"merged={result['merged_rows']} "
                    f"retry_failures={result['retry_failures']}"
                )
                if result["distilled_missing_ids_fixed"]:
                    print(
                        f"[INFO] normalize {label}/distilled: "
                        f"inserted_ids={result['distilled_missing_ids_fixed']}"
                    )
                if (
                    not config["skip_train"]
                    and not train_blocked_by_llmfit
                    and manifest["domains"][label]["train"]["status"] == "pending"
                ):
                    pending_trains.append(label)

            for label in list(active_trains):
                process, log_handle = active_trains[label]
                returncode = process.poll()
                if returncode is None:
                    continue
                log_handle.close()
                child_run = load_json_if_exists(jobs[label].train_run_manifest)
                child_llmfit = None if child_run is None else child_run.get("llmfit")
                if returncode == 0:
                    manifest["domains"][label]["train"] = {
                        "status": "completed",
                        "completed_at": now_ts(),
                        "returncode": 0,
                        "run_manifest_path": str(jobs[label].train_run_manifest),
                    }
                    if child_llmfit is not None:
                        manifest["domains"][label]["train"]["llmfit"] = child_llmfit
                    if child_run is not None:
                        training_info = (child_run.get("artifacts", {}) or {}).get(
                            "training_info"
                        )
                        if training_info is not None:
                            manifest["domains"][label]["train"][
                                "training_info"
                            ] = training_info
                    print(f"[OK] train {label}")
                else:
                    if (
                        child_llmfit is not None
                        and child_llmfit.get("status") == "rejected"
                    ):
                        train_blocked_by_llmfit = True
                        manifest["llmfit"] = child_llmfit
                        pending_trains.clear()
                        manifest["domains"][label]["train"] = {
                            "status": "blocked",
                            "completed_at": now_ts(),
                            "returncode": returncode,
                            "reason": child_llmfit.get("reason"),
                            "run_manifest_path": str(jobs[label].train_run_manifest),
                            "llmfit": child_llmfit,
                        }
                        print(f"[BLOCK] train {label}: {child_llmfit.get('reason')}")
                        save_updated_manifest(manifest_path, manifest)
                        del active_trains[label]
                        continue
                    stop_active_trains(active_trains)
                    manifest["domains"][label]["train"] = {
                        "status": "failed",
                        "completed_at": now_ts(),
                        "returncode": returncode,
                        "run_manifest_path": str(jobs[label].train_run_manifest),
                    }
                    if child_llmfit is not None:
                        manifest["domains"][label]["train"]["llmfit"] = child_llmfit
                    save_updated_manifest(manifest_path, manifest)
                    raise SystemExit(
                        f"Training failed for {label} (see {jobs[label].train_log})"
                    )
                save_updated_manifest(manifest_path, manifest)
                del active_trains[label]

            overlap_allowed = config["resolved_overlap_teacher_train"]
            if (
                pending_trains
                and not pending_distills
                and not active_distills
                and not teacher_released_for_parallel_trains
                and int(config.get("max_parallel_gpu_trains") or 1) > 1
            ):
                released, message = unload_ollama_model(config)
                teacher_released_for_parallel_trains = True
                print(f"[INFO] {message}")
                if released:
                    time.sleep(2)

            train_slot_limit = resolve_train_slot_limit(config, active_distills)
            while pending_trains and len(active_trains) < train_slot_limit:
                if active_distills and not overlap_allowed:
                    break
                wait_reason = gpu_wait_reason(config, len(active_trains))
                if wait_reason is not None:
                    now = time.time()
                    if now - last_wait_notice >= 15:
                        print(f"[WAIT] {wait_reason}")
                        last_wait_notice = now
                    break
                label = pending_trains.popleft()
                process, log_handle = start_train_process(
                    jobs[label], config, train_slot_limit=train_slot_limit
                )
                manifest["domains"][label]["train"] = {
                    "status": "running",
                    "started_at": now_ts(),
                    "pid": process.pid,
                }
                save_updated_manifest(manifest_path, manifest)
                active_trains[label] = (process, log_handle)
                print(f"[RUN] train {label} pid={process.pid}")

            if pending_distills or active_distills or pending_trains or active_trains:
                time.sleep(2)

    if config["skip_train"] or train_blocked_by_llmfit:
        for label, payload in manifest["domains"].items():
            if (
                payload["distill"]["status"] == "completed"
                and payload["train"]["status"] == "pending"
            ):
                payload["train"] = {
                    "status": "blocked" if train_blocked_by_llmfit else "skipped",
                    "completed_at": now_ts(),
                    "reason": (
                        batch_llmfit.get("reason") if train_blocked_by_llmfit else None
                    ),
                    "llmfit": {
                        "status": batch_llmfit["status"],
                        "reason": batch_llmfit.get("reason"),
                        "report_path": batch_llmfit.get("report_path"),
                    },
                }
        save_updated_manifest(manifest_path, manifest)
        if train_blocked_by_llmfit:
            print(f"[BLOCK] training disabled by llmfit ({batch_llmfit.get('reason')})")
        else:
            print(f"[SKIP] training disabled (teacher_only={config['teacher_only']})")
        print(f"[DONE] manifest={manifest_path}")
        return 0

    print(f"[DONE] manifest={manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
