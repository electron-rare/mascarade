#!/usr/bin/env python3
"""Scenario matrix orchestrator built on top of batch_local.py."""

from __future__ import annotations

import argparse
import os
import shlex
import subprocess
import sys
import time
from pathlib import Path

from llmfit_utils import build_llmfit_record, env_flag, plan_model_with_llmfit
from run_manifest import load_json, now_ts, write_manifest
from scenario_matrix import (
    CPU_STUDENT_MODELS,
    GPU_STUDENT_MODELS,
    PASS_SPECS,
    SCENARIO_SPECS,
    TEACHER_ONLY_MODELS,
    canonical_domain,
)

SCRIPT_DIR = Path(__file__).resolve().parent
RUNS_DIR = SCRIPT_DIR / "runs"
BATCH_LOCAL_SCRIPT = SCRIPT_DIR / "batch_local.py"
DEFAULT_API_URLS = ["http://127.0.0.1:8100"]


def resolve_cli_path(raw_path: str | None) -> Path | None:
    if raw_path is None:
        return None
    path = Path(raw_path)
    if not path.is_absolute():
        path = (Path.cwd() / path).resolve()
    return path


def normalize_run_label(label: str) -> str:
    value = "".join(c if c.isalnum() or c in "._-" else "-" for c in label).strip(".-")
    if not value:
        raise SystemExit("Run label must contain at least one alphanumeric character")
    return value


def resolve_scenarios(names: list[str], scenario_group: str) -> list:
    if names:
        missing = [name for name in names if name not in SCENARIO_SPECS]
        if missing:
            raise SystemExit(f"Unknown scenarios: {', '.join(missing)}")
        return [SCENARIO_SPECS[name] for name in names]
    if scenario_group == "all":
        return list(SCENARIO_SPECS.values())
    return [spec for spec in SCENARIO_SPECS.values() if spec.group == scenario_group]


def resolve_passes(pass_selector: str) -> list:
    if pass_selector == "all":
        return [PASS_SPECS[key] for key in ("1", "2", "3")]
    return [PASS_SPECS[pass_selector]]


def resolve_domains(
    explicit_domains: list[str], scenario_domains: tuple[str, ...]
) -> list[str]:
    if not explicit_domains:
        return list(scenario_domains)
    resolved = [canonical_domain(domain) for domain in explicit_domains]
    supported = [domain for domain in resolved if domain in scenario_domains]
    if not supported:
        raise SystemExit(
            f"Explicit domains {', '.join(explicit_domains)} do not overlap with scenario domains {', '.join(scenario_domains)}"
        )
    return supported


def assert_scenario_supported(spec) -> None:
    if (
        spec.teacher_model in GPU_STUDENT_MODELS
        or spec.teacher_model in CPU_STUDENT_MODELS
    ):
        return
    if spec.teacher_model in TEACHER_ONLY_MODELS:
        return
    if spec.student_model is None:
        return
    if spec.device == "cpu" and spec.student_model not in CPU_STUDENT_MODELS:
        raise SystemExit(
            f"Unsupported CPU student model for scenario {spec.name}: {spec.student_model}"
        )
    if spec.device == "gpu" and spec.student_model not in GPU_STUDENT_MODELS:
        raise SystemExit(
            f"Unsupported GPU student model for scenario {spec.name}: {spec.student_model}"
        )


def child_run_dir(prefix: str) -> str | None:
    matches = sorted(
        RUNS_DIR.glob(f"{prefix}_*"),
        key=lambda path: path.stat().st_mtime,
    )
    if not matches:
        return None
    return str(matches[-1])


def resolve_job_llmfit(spec, cache: dict[tuple[str, str, int | None], dict]) -> dict:
    enabled = env_flag("LLMFIT_PREFLIGHT", True)
    minimum_fit = os.environ.get("LLMFIT_MIN_FIT", "marginal")
    context = spec.seq_len or 0
    cache_key = (spec.device, spec.student_model or "", spec.seq_len)
    if cache_key in cache:
        return dict(cache[cache_key])

    if spec.teacher_only or spec.student_model is None:
        record = {
            "enabled": enabled,
            "requested_device": spec.device,
            "model": spec.student_model,
            "context": context,
            "minimum_fit": minimum_fit,
            "status": "skipped",
            "reason": "Teacher-only scenario",
            "train_blocked": False,
        }
    elif spec.device != "gpu":
        record = build_llmfit_record(
            enabled=enabled,
            requested_device=spec.device,
            model_name=spec.student_model,
            context=context,
            minimum_fit=minimum_fit,
        )
        record["train_blocked"] = False
    else:
        summary = None
        warning = None
        if enabled:
            try:
                summary = plan_model_with_llmfit(
                    model_name=spec.student_model,
                    context=context,
                    llmfit_bin=os.environ.get("LLMFIT_BIN"),
                    llmfit_root=os.environ.get("LLMFIT_ROOT"),
                    memory_override=os.environ.get("LLMFIT_MEMORY"),
                    allow_cargo_run=env_flag("LLMFIT_ALLOW_CARGO_RUN", False),
                    timeout=30,
                )
                if summary is None:
                    warning = (
                        "llmfit preflight skipped: no llmfit binary found. "
                        "Build /ai/saisail/llmfit with cargo +stable build --release -p llmfit "
                        "or set LLMFIT_BIN."
                    )
            except Exception as exc:  # noqa: BLE001
                warning = f"llmfit preflight skipped: {exc}"
        record = build_llmfit_record(
            enabled=enabled,
            requested_device=spec.device,
            model_name=spec.student_model,
            context=context,
            minimum_fit=minimum_fit,
            summary=summary,
            warning=warning,
        )
        record["train_blocked"] = record["status"] == "rejected"

    cache[cache_key] = dict(record)
    return dict(record)


def summarize_domain_trains(child_manifest: dict | None) -> dict | None:
    if child_manifest is None:
        return None
    counts: dict[str, int] = {}
    for payload in (child_manifest.get("domains") or {}).values():
        status = ((payload.get("train") or {}).get("status")) or "unknown"
        counts[status] = counts.get(status, 0) + 1
    return counts


def refresh_manifest_summary(manifest: dict) -> None:
    counts: dict[str, int] = {}
    llmfit_counts: dict[str, int] = {}
    for job in manifest["jobs"]:
        counts[job["status"]] = counts.get(job["status"], 0) + 1
        llmfit = job.get("llmfit") or {}
        llmfit_status = llmfit.get("status")
        if llmfit_status:
            llmfit_counts[llmfit_status] = llmfit_counts.get(llmfit_status, 0) + 1
    manifest["summary"] = {
        "job_status": counts,
        "llmfit": llmfit_counts,
    }


def build_job(
    spec,
    pass_spec,
    args,
    run_label: str,
    explicit_domains: list[str],
    llmfit_cache: dict[tuple[str, str, int | None], dict],
) -> dict:
    assert_scenario_supported(spec)
    domains = resolve_domains(explicit_domains, spec.domains)
    child_label = normalize_run_label(f"{run_label}_{spec.name}_p{pass_spec.name}")
    llmfit = resolve_job_llmfit(spec, llmfit_cache)
    local_hf_device = args.local_hf_device or getattr(spec, "local_hf_device", None)
    command = [
        sys.executable,
        str(BATCH_LOCAL_SCRIPT),
        *domains,
        "--run-label",
        child_label,
        "--max-tokens",
        str(spec.max_tokens),
        "--max-source-samples",
        str(pass_spec.max_source_samples),
        "--samples-per-source",
        str(pass_spec.samples_per_source),
        "--max-parallel-distills",
        str(args.max_parallel_distills),
        "--max-parallel-gpu-trains",
        str(args.max_parallel_gpu_trains),
        "--tokenize-workers",
        str(args.tokenize_workers),
    ]
    if spec.teacher_provider:
        command.extend(["--teacher-provider", spec.teacher_provider])
    if spec.teacher_model:
        command.extend(["--teacher-model", spec.teacher_model])
    if spec.teacher_objective:
        command.extend(["--teacher-objective", spec.teacher_objective])
    for api_url in args.api_urls or []:
        command.extend(["--api-url", api_url])
    if args.teacher_system_path:
        command.extend(["--teacher-system-path", args.teacher_system_path])
    if (spec.teacher_provider in {None, "local-hf"}) and local_hf_device:
        command.extend(["--local-hf-device", local_hf_device])
    if args.offline:
        command.append("--offline")
    if args.verbose:
        command.append("--verbose")

    if spec.teacher_only:
        command.append("--teacher-only")
    else:
        command.extend(
            [
                "--device",
                spec.device,
                "--student-model",
                spec.student_model,
                "--student-max-samples",
                str(pass_spec.student_max_samples),
                "--epochs",
                str(pass_spec.epochs),
                "--seq-len",
                str(spec.seq_len),
            ]
        )

    return {
        "id": f"{spec.name}_p{pass_spec.name}",
        "name": spec.name,
        "group": spec.group,
        "domains": domains,
        "teacher_provider": spec.teacher_provider,
        "teacher_model": spec.teacher_model,
        "teacher_objective": spec.teacher_objective,
        "local_hf_device": local_hf_device,
        "student_model": spec.student_model,
        "device": spec.device,
        "teacher_only": spec.teacher_only,
        "llmfit": llmfit,
        "pass": {
            "name": pass_spec.name,
            "max_source_samples": pass_spec.max_source_samples,
            "samples_per_source": pass_spec.samples_per_source,
            "student_max_samples": pass_spec.student_max_samples,
            "epochs": pass_spec.epochs,
        },
        "status": "pending",
        "child_run_label": child_label,
        "child_run_dir": None,
        "child_manifest_path": None,
        "command": command,
    }


def build_manifest(args: argparse.Namespace, run_dir: Path, jobs: list[dict]) -> dict:
    manifest = {
        "version": 1,
        "kind": "batch_scenarios",
        "created_at": now_ts(),
        "updated_at": now_ts(),
        "run_dir": str(run_dir),
        "run_label": args.run_label,
        "prepare_only": args.prepare_only,
        "scenario_group": args.scenario_group,
        "selected_scenarios": args.scenario or [],
        "pass_selector": args.pass_selector,
        "api_urls": args.api_urls or DEFAULT_API_URLS,
        "jobs": jobs,
    }
    refresh_manifest_summary(manifest)
    return manifest


def write_commands_file(run_dir: Path, jobs: list[dict]) -> None:
    path = run_dir / "commands.sh"
    lines = ["#!/usr/bin/env bash", "set -euo pipefail", ""]
    lines.extend(shlex.join(job["command"]) for job in jobs)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    path.chmod(0o755)


def load_resume_manifest(resume_path: Path) -> tuple[Path, dict]:
    manifest_path = resume_path / "matrix.json" if resume_path.is_dir() else resume_path
    manifest = load_json(manifest_path)
    if manifest is None:
        raise SystemExit(f"Scenario matrix manifest not found: {manifest_path}")
    for job in manifest["jobs"]:
        if job["status"] == "running":
            job["status"] = "pending"
            job.pop("started_at", None)
    refresh_manifest_summary(manifest)
    return manifest_path, manifest


def execute_job(job: dict, log_path: Path) -> tuple[int, str | None]:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(f"$ {shlex.join(job['command'])}\n")
        handle.flush()
        process = subprocess.Popen(
            job["command"],
            cwd=SCRIPT_DIR,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        detected_run_dir = None
        assert process.stdout is not None
        for line in process.stdout:
            handle.write(line)
            handle.flush()
            if line.startswith("[INFO] run_dir="):
                detected_run_dir = line.split("=", 1)[1].strip()
        return process.wait(), detected_run_dir


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Prepare or execute teacher/student scenario batches"
    )
    parser.add_argument("domains", nargs="*", help="Optional domains or aliases")
    parser.add_argument("--scenario", action="append", help="Specific scenario name")
    parser.add_argument(
        "--scenario-group",
        choices=["all", "auto", "qwen", "mistral", "deepseek"],
        default="all",
    )
    parser.add_argument(
        "--pass",
        dest="pass_selector",
        choices=["1", "2", "3", "all"],
        default="all",
    )
    parser.add_argument("--run-label", default="scenario-matrix")
    parser.add_argument("--resume", default=None)
    parser.add_argument("--prepare-only", action="store_true")
    parser.add_argument("--api-url", action="append", dest="api_urls")
    parser.add_argument("--teacher-system-path", default=None)
    parser.add_argument(
        "--local-hf-device",
        default=os.environ.get("MASCARADE_LOCAL_HF_DEVICE"),
        help="Override local-hf teacher device target (auto, cpu, cuda:0, ...)",
    )
    parser.add_argument("--max-parallel-distills", type=int, default=6)
    parser.add_argument("--max-parallel-gpu-trains", type=int, default=1)
    parser.add_argument("--tokenize-workers", type=int, default=4)
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()
    args.run_label = normalize_run_label(args.run_label)

    if args.resume:
        manifest_path, manifest = load_resume_manifest(resolve_cli_path(args.resume))
        run_dir = Path(manifest["run_dir"])
        jobs = manifest["jobs"]
    else:
        stamp = time.strftime("%Y%m%d_%H%M%S")
        run_dir = RUNS_DIR / f"{args.run_label}_{stamp}"
        scenarios = resolve_scenarios(args.scenario or [], args.scenario_group)
        passes = resolve_passes(args.pass_selector)
        llmfit_cache: dict[tuple[str, str, int | None], dict] = {}
        jobs = [
            build_job(
                spec,
                pass_spec,
                args,
                args.run_label,
                args.domains,
                llmfit_cache,
            )
            for spec in scenarios
            for pass_spec in passes
        ]
        manifest = build_manifest(args, run_dir, jobs)
        manifest_path = run_dir / "matrix.json"
        write_manifest(manifest_path, manifest)
        write_commands_file(run_dir, jobs)

    print(f"[INFO] run_dir={run_dir}")
    print(f"[INFO] jobs={len(jobs)}")
    print(f"[INFO] manifest={manifest_path}")
    if args.prepare_only:
        print(f"[DONE] prepare_only manifest={manifest_path}")
        return 0

    logs_dir = run_dir / "logs"
    for job in jobs:
        if job["status"] in {"completed", "blocked"}:
            continue
        llmfit = job.get("llmfit") or {}
        if llmfit.get("status") == "rejected":
            job["status"] = "blocked"
            job["completed_at"] = now_ts()
            job["reason"] = llmfit.get("reason")
            refresh_manifest_summary(manifest)
            write_manifest(manifest_path, manifest)
            print(f"[BLOCK] {job['id']}: {llmfit.get('reason')}")
            continue
        job["status"] = "running"
        job["started_at"] = now_ts()
        refresh_manifest_summary(manifest)
        write_manifest(manifest_path, manifest)
        print(f"[RUN] {job['id']}")
        returncode, detected_run_dir = execute_job(
            job,
            logs_dir / f"{job['id']}.log",
        )
        if detected_run_dir is None:
            detected_run_dir = child_run_dir(job["child_run_label"])
        job["child_run_dir"] = detected_run_dir
        child_manifest = None
        if detected_run_dir is not None:
            child_manifest_path = Path(detected_run_dir) / "manifest.json"
            if child_manifest_path.exists():
                child_manifest = load_json(child_manifest_path)
                job["child_manifest_path"] = str(child_manifest_path)
        if child_manifest is not None and child_manifest.get("llmfit") is not None:
            job["llmfit"] = child_manifest["llmfit"]
            job["domain_train_status"] = summarize_domain_trains(child_manifest)
        if child_manifest is not None:
            child_config = child_manifest.get("config") or {}
            if child_config.get("teacher_selection") is not None:
                job["resolved_teacher_selection"] = child_config["teacher_selection"]
            if child_config.get("teacher_provider") is not None:
                job["resolved_teacher_provider"] = child_config["teacher_provider"]
            if child_config.get("teacher_model") is not None:
                job["resolved_teacher_model"] = child_config["teacher_model"]
        job["completed_at"] = now_ts()
        job["returncode"] = returncode
        if (job.get("llmfit") or {}).get("status") == "rejected":
            job["status"] = "blocked"
            job["reason"] = (job["llmfit"] or {}).get("reason")
            print(f"[BLOCK] {job['id']}: {job['reason']}")
        elif returncode == 0:
            job["status"] = "completed"
            print(f"[OK] {job['id']}")
        else:
            job["status"] = "failed"
            refresh_manifest_summary(manifest)
            write_manifest(manifest_path, manifest)
            log_file = logs_dir / f"{job['id']}.log"
            raise SystemExit(f"Scenario job failed: {job['id']} (see {log_file})")
        refresh_manifest_summary(manifest)
        write_manifest(manifest_path, manifest)

    print(f"[DONE] manifest={manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
