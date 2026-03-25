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

from auto_policy import (
    detect_machine_profile,
    resolve_autotune_plan,
    resolve_default_student_model,
    resolve_requested_device,
    resolve_teacher_objective,
    resolve_teacher_selection,
)
from dataset_bootstrap import ensure_seed_dataset
from dataset_quality import (
    DatasetQualityError,
    enforce_dataset_quality,
    summarize_quality_report,
)
from dataset_refresh import refresh_domains
from llmfit_utils import (
    build_llmfit_record,
    env_flag,
    plan_model_with_llmfit,
    write_llmfit_plan,
)
from model_selector import (
    FALLBACK_MODEL as DEFAULT_STUDENT_MODEL,
    ensure_model_selection,
    resolve_model,
)
from promotion_utils import DEFAULT_PROMOTION_QUANT, promote_domain_run
from sharegpt_utils import (
    dedupe_rows_with_stats,
    ensure_row_ids,
    ensure_row_ids_with_stats,
    load_jsonl,
    validate_rows,
    write_jsonl,
)
from workspace_utils import prepare_training_output_dir

SCRIPT_DIR = Path(__file__).resolve().parent
DISTILL_SCRIPT = SCRIPT_DIR / "distill_dataset.py"
RUN_LOCAL_SCRIPT = SCRIPT_DIR / "run_local.py"
DATASETS_DIR = SCRIPT_DIR / "datasets"
RUNS_DIR = SCRIPT_DIR / "runs"
ROOT_DIR = SCRIPT_DIR.parent
DEFAULT_API_URLS = ["http://127.0.0.1:8100"]
LOCAL_HF_PROVIDER = "local-hf"
DEFAULT_OLLAMA_API_URL = "http://127.0.0.1:11434"

DEFAULT_DOMAINS = ["iot", "spice", "platformio"]
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
    "components",
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
    requested_train_output_dir: Path
    train_output_dir: Path
    train_output_mode: str
    train_output_reason: str
    train_run_manifest: Path
    train_llmfit_plan: Path
    distill_log: Path
    train_log: Path


def canonical_domain(raw_domain: str) -> str:
    return ALIAS_MAP.get(raw_domain, raw_domain)


def resolve_student_model_selection(
    explicit_model: str | None,
    machine_profile: dict,
    requested_device: str,
    *,
    seq_len: int,
    offline: bool,
) -> tuple[str, str, dict | None]:
    if explicit_model and explicit_model.strip():
        return explicit_model.strip(), "explicit", None
    if not offline:
        selection_info = ensure_model_selection(
            fallback_model=DEFAULT_STUDENT_MODEL,
            task="code",
            seq_len=seq_len,
            watch=True,
            verbose=False,
        )
        selection_model = str(selection_info.get("model_id") or "").strip()
        if selection_model and selection_info.get("source") != "fallback":
            return selection_model, str(selection_info.get("source")), selection_info
    resolved = resolve_model(DEFAULT_STUDENT_MODEL)
    if resolved != DEFAULT_STUDENT_MODEL:
        return resolved, "selected_model", None
    resolved, _reason = resolve_default_student_model(
        machine_profile=machine_profile,
        fallback_model=DEFAULT_STUDENT_MODEL,
        requested_device=requested_device,
    )
    if resolved != DEFAULT_STUDENT_MODEL:
        return resolved, "hardware_auto", None
    return DEFAULT_STUDENT_MODEL, "default", None


def now_ts() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S")


def resolve_path(raw_path: str | None) -> Path | None:
    if raw_path is None:
        return None
    path = Path(raw_path)
    if not path.is_absolute():
        path = (Path.cwd() / path).resolve()
    return path


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


def summarize_validation_errors(errors: list[str], *, limit: int = 5) -> str:
    snippet = errors[:limit]
    return "; ".join(snippet)


def prevalidate_source_dataset(
    *, label: str, canonical: str, source_dataset: Path
) -> dict[str, object]:
    try:
        raw_rows = load_jsonl(source_dataset)
    except json.JSONDecodeError as exc:
        raise SystemExit(
            f"Invalid JSONL in source dataset for {label}: {source_dataset} ({exc})"
        ) from exc

    normalized_rows, normalized_source_ids = ensure_row_ids_with_stats(
        raw_rows, f"{canonical}-source"
    )
    validation_errors = validate_rows(normalized_rows)
    if validation_errors:
        detail = summarize_validation_errors(validation_errors)
        raise SystemExit(
            f"Source dataset invalid for {label}: {source_dataset} "
            f"({len(validation_errors)} errors; {detail})"
        )

    try:
        quality_report = enforce_dataset_quality(
            normalized_rows,
            label=f"{label} source dataset",
            ids_fixed=normalized_source_ids,
        )
    except DatasetQualityError as exc:
        raise SystemExit(
            f"Source dataset quality gate failed for {label}: {exc}"
        ) from exc

    if normalized_source_ids:
        print(
            f"[INFO] source-prevalidation {label}: "
            f"normalized_ids={normalized_source_ids} source_rows={len(normalized_rows)}"
        )
    if quality_report["warnings"]:
        print(
            f"[WARN] source-quality {label}: {summarize_quality_report(quality_report)}"
        )

    return {
        "source_rows": len(normalized_rows),
        "normalized_source_ids": normalized_source_ids,
        "quality_gate": quality_report,
    }


def final_failed_source_rows(distill_payload: dict) -> int:
    if "failed_source_rows" in distill_payload:
        return int(distill_payload.get("failed_source_rows") or 0)
    retry_failures = distill_payload.get("retry_failures")
    if retry_failures is not None:
        return int(retry_failures or 0)
    return int(distill_payload.get("initial_failures") or 0)


def update_batch_summary(manifest: dict) -> None:
    domains = manifest.get("domains", {})
    distill_payloads = [
        payload.get("distill", {})
        for payload in domains.values()
        if payload.get("distill", {}).get("status") == "completed"
    ]
    manifest["summary"] = {
        "domains_total": len(domains),
        "distills_completed": len(distill_payloads),
        "trains_completed": sum(
            1
            for payload in domains.values()
            if payload.get("train", {}).get("status") == "completed"
        ),
        "source_rows": sum(
            int(item.get("source_rows") or 0) for item in distill_payloads
        ),
        "distilled_rows": sum(
            int(item.get("distilled_rows") or 0) for item in distill_payloads
        ),
        "merged_rows": sum(
            int(item.get("merged_rows") or 0) for item in distill_payloads
        ),
        "duplicates_removed": sum(
            int(item.get("duplicates_removed") or 0) for item in distill_payloads
        ),
        "failed_source_rows": sum(
            final_failed_source_rows(item) for item in distill_payloads
        ),
        "promotions_completed": sum(
            1
            for payload in domains.values()
            if payload.get("promotion", {}).get("status") == "completed"
        ),
        "promotions_pending_manual_review": sum(
            1
            for payload in domains.values()
            if payload.get("promotion", {}).get("status") == "pending_manual_review"
        ),
    }


def build_jobs(
    *,
    labels: list[str],
    run_dir: Path,
    run_label: str,
    stamp: str,
) -> dict[str, DomainJob]:
    jobs: dict[str, DomainJob] = {}
    log_dir = run_dir / "logs"
    for label in labels:
        canonical = canonical_domain(label)
        if canonical not in SUPPORTED_DOMAINS:
            raise SystemExit(f"Unsupported domain: {label} -> {canonical}")
        source_dataset = DATASETS_DIR / f"{canonical}_chat.jsonl"
        if not source_dataset.exists():
            builder = ensure_seed_dataset(SCRIPT_DIR, canonical, source_dataset)
            if builder is not None:
                print(f"[BOOTSTRAP] built seed dataset for {label} via {builder.name}")
        if not source_dataset.exists():
            raise SystemExit(f"Source dataset not found: {source_dataset}")
        requested_train_output_dir = (
            SCRIPT_DIR / "models_local" / f"{label}_{run_label}_{stamp}"
        )
        train_output_workspace = prepare_training_output_dir(requested_train_output_dir)
        train_output_dir = Path(train_output_workspace["output_dir"])
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
            requested_train_output_dir=requested_train_output_dir,
            train_output_dir=train_output_dir,
            train_output_mode=str(train_output_workspace["mode"]),
            train_output_reason=str(train_output_workspace["reason"]),
            train_run_manifest=train_output_dir / "run.json",
            train_llmfit_plan=train_output_dir / "llmfit_plan.json",
            distill_log=log_dir / f"{label}_distill.log",
            train_log=log_dir / f"{label}_train.log",
        )
    return jobs


def maybe_refresh_source_datasets(
    args: argparse.Namespace, labels: list[str]
) -> dict[str, dict]:
    if not args.refresh_datasets:
        return {}
    canonical_labels = sorted({canonical_domain(label) for label in labels})
    reports = refresh_domains(
        canonical_labels,
        dataset_dir=DATASETS_DIR,
        with_hf=args.refresh_with_hf,
        max_samples=args.refresh_max_samples,
        prefer_full_datasets=args.prefer_full_datasets,
        full_datasets_root=resolve_path(args.full_datasets_root),
        research_dir=resolve_path(args.research_dir),
        emit_research_brief=not args.skip_research_briefs,
    )
    for canonical, report in reports.items():
        print(
            f"[REFRESH] {canonical}: mode={report['source_mode']} "
            f"rows={report['row_count']} quality={report['quality']['status']}"
        )
        if report["quality"].get("warnings"):
            print(
                f"[WARN] refresh-quality {canonical}: "
                f"{summarize_quality_report(report['quality'])}"
            )
    return reports


def build_new_manifest(
    args: argparse.Namespace,
    run_dir: Path,
    labels: list[str],
    stamp: str,
    refresh_reports: dict[str, dict] | None = None,
) -> dict:
    jobs = build_jobs(
        labels=labels, run_dir=run_dir, run_label=args.run_label, stamp=stamp
    )
    refresh_reports = refresh_reports or {}
    domains: dict[str, dict] = {}
    for label, job in jobs.items():
        source_prevalidation = prevalidate_source_dataset(
            label=label,
            canonical=job.canonical,
            source_dataset=job.source_dataset,
        )
        domains[label] = {
            "label": label,
            "canonical": job.canonical,
            "source_dataset": str(job.source_dataset),
            "dataset_refresh": refresh_reports.get(job.canonical),
            "source_prevalidation": source_prevalidation,
            "distilled_out": str(job.distilled_out),
            "merged_out": str(job.merged_out),
            "report_path": str(job.report_path),
            "failures_out": str(job.failures_out),
            "retry_out": str(job.retry_out),
            "retry_report_path": str(job.retry_report_path),
            "retry_failures_out": str(job.retry_failures_out),
            "requested_train_output_dir": str(job.requested_train_output_dir),
            "train_output_dir": str(job.train_output_dir),
            "train_output_mode": job.train_output_mode,
            "train_output_reason": job.train_output_reason,
            "train_run_manifest": str(job.train_run_manifest),
            "train_llmfit_plan": str(job.train_llmfit_plan),
            "distill_log": str(job.distill_log),
            "train_log": str(job.train_log),
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
            "teacher_objective": args.teacher_objective,
            "teacher_selection": args.teacher_selection,
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
            "teacher_system_path": args.teacher_system_path,
            "local_hf_device": args.local_hf_device,
            "overlap_teacher_train": args.overlap_teacher_train,
            "device": args.device,
            "machine_profile": args.machine_profile,
            "student_model": args.student_model,
            "student_model_source": args.student_model_source,
            "student_model_selection": args.student_model_selection,
            "student_max_samples": args.student_max_samples,
            "seq_len": args.seq_len,
            "autotune": args.autotune,
            "epochs": args.epochs,
            "tokenize_workers": args.tokenize_workers,
            "skip_train": args.skip_train,
            "offline": args.offline,
            "eval": args.eval,
            "refresh_datasets": args.refresh_datasets,
            "refresh_with_hf": args.refresh_with_hf,
            "refresh_max_samples": args.refresh_max_samples,
            "prefer_full_datasets": args.prefer_full_datasets,
            "full_datasets_root": args.full_datasets_root,
            "research_dir": args.research_dir,
            "skip_research_briefs": args.skip_research_briefs,
            "max_parallel_gpu_trains": args.max_parallel_gpu_trains,
            "gpu_job_vram_mb": args.gpu_job_vram_mb,
            "gpu_buffer_mb": args.gpu_buffer_mb,
            "auto_promote": args.auto_promote,
            "promotion_quant": args.promotion_quant,
            "promotion_registry_path": args.promotion_registry_path,
            "llmfit_preflight": env_flag("LLMFIT_PREFLIGHT", True),
            "llmfit_min_fit": os.environ.get("LLMFIT_MIN_FIT", "marginal"),
            "llmfit_memory": os.environ.get("LLMFIT_MEMORY"),
            "llmfit_bin": os.environ.get("LLMFIT_BIN"),
            "llmfit_root": os.environ.get("LLMFIT_ROOT"),
            "llmfit_allow_cargo_run": env_flag("LLMFIT_ALLOW_CARGO_RUN", False),
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
            requested_train_output_dir=Path(
                payload.get("requested_train_output_dir", payload["train_output_dir"])
            ),
            train_output_dir=Path(payload["train_output_dir"]),
            train_output_mode=str(payload.get("train_output_mode", "requested")),
            train_output_reason=str(
                payload.get(
                    "train_output_reason",
                    f"using requested training output directory under "
                    f"{Path(payload['train_output_dir']).parent}",
                )
            ),
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


def maybe_promote_completed_train(job: DomainJob, config: dict) -> dict | None:
    if not config.get("auto_promote"):
        return None
    training_info_path = job.train_output_dir / "training_info.json"
    if not training_info_path.exists():
        return {
            "status": "skipped",
            "reason": f"training_info.json missing in {job.train_output_dir}",
        }
    registry_path = config.get("promotion_registry_path")
    return promote_domain_run(
        domain=job.label,
        canonical_domain=job.canonical,
        run_output_dir=job.train_output_dir,
        student_model=str(config["student_model"]),
        training_info=read_json(training_info_path),
        run_manifest_path=job.train_run_manifest,
        promotion_quant=str(config.get("promotion_quant") or DEFAULT_PROMOTION_QUANT),
        registry_path=Path(registry_path) if registry_path else None,
    )


def load_jsonl_if_exists(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return load_jsonl(path)


def merge_source_and_distilled(job: DomainJob) -> tuple[int, int, int, int]:
    source_rows = ensure_row_ids(
        load_jsonl(job.source_dataset), f"{job.canonical}-source"
    )
    distilled_rows = ensure_row_ids(
        load_jsonl_if_exists(job.distilled_out), f"{job.canonical}-distill"
    )
    merged_rows, duplicates_removed = dedupe_rows_with_stats(
        source_rows + distilled_rows
    )
    validation_errors = validate_rows(merged_rows)
    if validation_errors:
        raise RuntimeError(
            f"Merged dataset is invalid ({len(validation_errors)} errors)"
        )
    write_jsonl(job.merged_out, merged_rows)
    return len(source_rows), len(distilled_rows), len(merged_rows), duplicates_removed


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
    if config["teacher_provider"] == LOCAL_HF_PROVIDER and config.get(
        "local_hf_device"
    ):
        command.extend(["--local-hf-device", config["local_hf_device"]])
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
        retry_attempted = False

        if (
            initial_failures
            and job.failures_out.exists()
            and job.failures_out.stat().st_size > 0
        ):
            retry_attempted = True
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
            combined_rows, retry_duplicates_removed = dedupe_rows_with_stats(
                base_rows + retry_rows_payload
            )
            write_jsonl(job.distilled_out, combined_rows)
            report["retry_report_path"] = str(job.retry_report_path)
            report["retry_failures_out"] = str(job.retry_failures_out)
            report["retry_generated_rows"] = retry_rows
            report["retry_remaining_failures"] = retry_failures
            report["generated_rows"] = len(combined_rows)
            report["retry_duplicates_removed"] = retry_duplicates_removed
            report_path = job.report_path
            report_path.write_text(
                json.dumps(report, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )

    source_count, distilled_count, merged_count, merged_duplicates_removed = (
        merge_source_and_distilled(job)
    )
    final_failed_rows = retry_failures if retry_attempted else initial_failures
    report["source_rows"] = source_count
    report["distilled_rows"] = distilled_count
    report["merged_rows"] = merged_count
    report["duplicates_removed"] = (
        int(report.get("duplicates_removed") or 0)
        + int(report.get("retry_duplicates_removed") or 0)
        + merged_duplicates_removed
    )
    report["failed_source_rows"] = final_failed_rows
    job.report_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return {
        "initial_failures": initial_failures,
        "retry_failures": retry_failures,
        "retry_rows": retry_rows,
        "source_rows": source_count,
        "distilled_rows": distilled_count,
        "merged_rows": merged_count,
        "duplicates_removed": int(report.get("duplicates_removed") or 0),
        "failed_source_rows": final_failed_rows,
    }


def resolve_overlap_teacher_train(config: dict) -> bool:
    requested = config.get("overlap_teacher_train")
    if requested is not None:
        return bool(requested)
    if str(config.get("device") or "").lower() == "cpu":
        # CPU students can train while the local GPU teacher keeps distilling.
        return True
    if config.get("teacher_provider") == LOCAL_HF_PROVIDER:
        return str(config.get("local_hf_device") or "").strip().lower() == "cpu"
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
    active_trains: dict[str, tuple[subprocess.Popen, object]],
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


def save_updated_manifest(manifest_path: Path, manifest: dict) -> None:
    manifest["updated_at"] = now_ts()
    update_batch_summary(manifest)
    write_manifest(manifest_path, manifest)


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
    parser.add_argument("--max-source-samples", type=int, default=96)
    parser.add_argument("--samples-per-source", type=int, default=1)
    parser.add_argument("--json-retries", type=int, default=3)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--sleep-ms", type=int, default=0)
    parser.add_argument(
        "--refresh-datasets",
        action="store_true",
        help=(
            "Refresh canonical datasets before prevalidation. Prefer the local "
            "mascarade-datasets repo when present, otherwise rebuild from "
            "finetune/datasets/build_*"
        ),
    )
    parser.add_argument(
        "--refresh-with-hf",
        action="store_true",
        help="When refresh falls back to builders, include their Hugging Face enrichment path",
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
    parser.add_argument("--teacher-system-path", default=None)
    parser.add_argument(
        "--local-hf-device",
        default=os.environ.get("MASCARADE_LOCAL_HF_DEVICE"),
        help="Explicit device target for local-hf teachers (auto, cpu, cuda:0, ...)",
    )
    parser.add_argument(
        "--max-parallel-distills",
        type=int,
        default=6,
        help="Global budget for teacher calls across domains",
    )
    parser.add_argument(
        "--max-parallel-gpu-trains",
        type=int,
        default=None,
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
    parser.add_argument("--device", choices=["gpu", "cpu", "auto"], default="auto")
    parser.add_argument(
        "--student-model",
        default=None,
        help=(
            "Override student model. Defaults to selected_model.json when present, "
            f"otherwise {DEFAULT_STUDENT_MODEL}."
        ),
    )
    parser.add_argument("--student-max-samples", type=int, default=None)
    parser.add_argument("--seq-len", type=int, default=None)
    parser.add_argument("--epochs", type=int, default=2)
    parser.add_argument("--tokenize-workers", type=int, default=4)
    parser.add_argument(
        "--auto-promote",
        action="store_true",
        help="After a successful train, replace the live domain alias when merge/GGUF/deploy/smoke all pass",
    )
    parser.add_argument(
        "--promotion-quant",
        default=DEFAULT_PROMOTION_QUANT,
        help="GGUF quant used for auto-promotion",
    )
    parser.add_argument(
        "--promotion-registry-path",
        default=None,
        help="Optional JSON registry path for live promotions",
    )
    parser.add_argument(
        "--teacher-only",
        action="store_true",
        help="Distill/merge only, skip local student training",
    )
    parser.add_argument("--skip-train", action="store_true")
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--eval", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    parser.set_defaults(prefer_full_datasets=True)
    args = parser.parse_args()
    args.teacher_objective = resolve_teacher_objective(args.teacher_objective)
    if args.teacher_only:
        args.skip_train = True
    ensure_local_api_key_env()
    if not args.resume:
        args.machine_profile = detect_machine_profile(requested_device=args.device)
        args.device = resolve_requested_device(args.device, args.machine_profile)
        (
            args.student_model,
            args.student_model_source,
            args.student_model_selection,
        ) = resolve_student_model_selection(
            args.student_model,
            args.machine_profile,
            args.device,
            seq_len=args.seq_len,
            offline=args.offline,
        )
        args.teacher_selection = resolve_teacher_selection(
            machine_profile=args.machine_profile,
            explicit_provider=args.teacher_provider,
            explicit_model=args.teacher_model,
            ollama_api_url=os.environ.get("OLLAMA_API_URL"),
            domains=[
                canonical_domain(label) for label in (args.domains or DEFAULT_DOMAINS)
            ],
            objective=args.teacher_objective,
        )
        args.teacher_provider = args.teacher_selection["provider"]
        args.teacher_model = args.teacher_selection["model"]
        if not args.local_hf_device:
            args.local_hf_device = args.teacher_selection.get("local_hf_device")
        elif args.teacher_provider == LOCAL_HF_PROVIDER:
            args.teacher_selection["local_hf_device"] = args.local_hf_device
            args.teacher_selection["gpu_active"] = (
                str(args.local_hf_device).strip().lower() != "cpu"
            )
        args.autotune = resolve_autotune_plan(
            machine_profile=args.machine_profile,
            student_model=args.student_model,
            requested_device=args.device,
            teacher_selection=args.teacher_selection,
            requested_gpu_slots=args.max_parallel_gpu_trains,
            requested_seq_len=args.seq_len,
            requested_student_max_samples=args.student_max_samples,
        )
        args.max_parallel_gpu_trains = args.autotune["resolved_gpu_slots"]
        args.seq_len = args.autotune["resolved_seq_len"]
        args.student_max_samples = args.autotune["resolved_student_max_samples"]
    else:
        args.machine_profile = None
        args.teacher_selection = None
        args.autotune = None
        args.student_model_selection = None

    if args.max_parallel_gpu_trains is not None and (
        args.max_parallel_gpu_trains < 1 or args.max_parallel_gpu_trains > 2
    ):
        raise SystemExit("--max-parallel-gpu-trains must be 1 or 2")

    if args.resume:
        manifest = load_resume_manifest(resolve_path(args.resume))
        manifest_path = Path(manifest["run_dir"]) / "manifest.json"
    else:
        raw_labels = args.domains or DEFAULT_DOMAINS
        stamp = time.strftime("%Y%m%d_%H%M%S")
        run_dir = RUNS_DIR / f"{args.run_label}_{stamp}"
        refresh_reports = maybe_refresh_source_datasets(args, raw_labels)
        manifest = build_new_manifest(
            args,
            run_dir,
            raw_labels,
            stamp,
            refresh_reports=refresh_reports,
        )
        manifest_path = run_dir / "manifest.json"
        save_updated_manifest(manifest_path, manifest)

    run_dir = Path(manifest["run_dir"])
    jobs = jobs_from_manifest(manifest)
    config = manifest["config"]
    config["api_urls"] = config.get("api_urls") or DEFAULT_API_URLS
    config["teacher_objective"] = resolve_teacher_objective(
        config.get(
            "teacher_objective",
            os.environ.get("MASCARADE_TEACHER_OBJECTIVE", "balanced"),
        )
    )
    config["teacher_system_path"] = config.get("teacher_system_path")
    config["local_hf_device"] = config.get("local_hf_device") or os.environ.get(
        "MASCARADE_LOCAL_HF_DEVICE"
    )
    if config.get("machine_profile") is None:
        config["machine_profile"] = detect_machine_profile(
            requested_device=str(config.get("device") or "auto")
        )
    if config.get("teacher_selection") is None:
        config["teacher_selection"] = {
            "mode": "legacy",
            "objective": config.get("teacher_objective", "legacy"),
            "provider": config.get("teacher_provider"),
            "model": config.get("teacher_model"),
            "local_hf_device": config.get("local_hf_device"),
            "gpu_active": config.get("teacher_provider") == LOCAL_HF_PROVIDER,
            "reason": "legacy manifest without teacher auto-selection metadata",
            "candidates_considered": [],
        }
    else:
        config["teacher_selection"]["objective"] = config["teacher_selection"].get(
            "objective",
            config.get("teacher_objective", "balanced"),
        )
    if config.get("autotune") is None:
        config["autotune"] = {
            "objective": "legacy",
            "reason": "legacy manifest without hardware-adaptive autotune metadata",
            "gpu_slots_source": "legacy",
            "seq_len_source": "legacy",
            "student_max_samples_source": "legacy",
            "resolved_gpu_slots": config.get("max_parallel_gpu_trains"),
            "resolved_seq_len": config.get("seq_len"),
            "resolved_student_max_samples": config.get("student_max_samples"),
        }
    config["student_max_samples"] = config.get("student_max_samples")
    config["teacher_only"] = config.get("teacher_only", False)
    config["skip_train"] = config.get("skip_train", False)
    config["student_model_source"] = config.get("student_model_source", "legacy")
    config["student_model_selection"] = config.get("student_model_selection")
    config["auto_promote"] = config.get("auto_promote", False)
    config["promotion_quant"] = config.get("promotion_quant", DEFAULT_PROMOTION_QUANT)
    config["promotion_registry_path"] = config.get("promotion_registry_path")
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

    print(f"[INFO] run_dir={run_dir}")
    print(f"[INFO] domains={' '.join(jobs.keys())}")
    machine_profile = config.get("machine_profile") or {}
    if machine_profile.get("cuda_available"):
        print(
            "[INFO] machine="
            f"{machine_profile.get('gpu_name')} "
            f"vram_mb={machine_profile.get('total_vram_mb')} "
            f"class={machine_profile.get('hardware_class')}"
        )
    else:
        print(
            "[INFO] machine=cpu-only " f"class={machine_profile.get('hardware_class')}"
        )
    print(f"[INFO] teacher={config['teacher_provider']}/{config['teacher_model']}")
    teacher_selection = config.get("teacher_selection") or {}
    print(
        "[INFO] teacher_mode="
        f"{teacher_selection.get('mode', 'legacy')} "
        f"objective={teacher_selection.get('objective', config.get('teacher_objective', '-'))} "
        f"reason={teacher_selection.get('reason', '-')}"
    )
    if config["teacher_provider"] == LOCAL_HF_PROVIDER and config.get(
        "local_hf_device"
    ):
        print(f"[INFO] local_hf_device={config['local_hf_device']}")
    print(
        f"[INFO] student={config['student_model']} "
        f"(source={config['student_model_source']})"
    )
    student_model_selection = config.get("student_model_selection") or {}
    if student_model_selection:
        print(
            "[INFO] student_selection_reason="
            f"{student_model_selection.get('reason', '-')}"
        )
        if student_model_selection.get("watch_report_path"):
            print(
                "[INFO] student_watch_report="
                f"{student_model_selection['watch_report_path']}"
            )
    autotune = config.get("autotune") or {}
    print(
        "[INFO] gpu_slots="
        f"{config['max_parallel_gpu_trains']} "
        f"(source={autotune.get('gpu_slots_source', 'legacy')})"
    )
    print(
        "[INFO] overlap_teacher_train="
        f"{config['resolved_overlap_teacher_train']} "
        f"gpu_job_vram_mb={config['resolved_gpu_job_vram_mb']}"
    )
    print(
        "[INFO] seq_len="
        f"{config['seq_len']} "
        f"(source={autotune.get('seq_len_source', 'legacy')}) "
        "student_max_samples="
        f"{config['student_max_samples']} "
        f"(source={autotune.get('student_max_samples_source', 'legacy')})"
    )
    sample_job = next(iter(jobs.values()), None)
    if sample_job is not None:
        print(
            "[INFO] train_output_mode="
            f"{sample_job.train_output_mode} "
            f"reason={sample_job.train_output_reason}"
        )
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
                    f"[OK] distill {label}: source={result['source_rows']} "
                    f"distilled={result['distilled_rows']} merged={result['merged_rows']} "
                    f"failed={result['failed_source_rows']}"
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
                    promotion_result = maybe_promote_completed_train(
                        jobs[label], config
                    )
                    if promotion_result is not None:
                        manifest["domains"][label]["promotion"] = promotion_result
                        print(
                            f"[PROMOTE] {label}: "
                            f"{promotion_result.get('status')} "
                            f"{promotion_result.get('reason', '-')}"
                        )
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

            can_launch_distills = overlap_allowed or (
                not pending_trains and not active_trains
            )
            while (
                pending_distills
                and len(active_distills) < max(1, distill_workers)
                and can_launch_distills
            ):
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
