#!/usr/bin/env python3
"""Helpers for using llmfit as a hardware preflight for local training."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_LLMFIT_ROOT = SCRIPT_DIR.parents[1] / "llmfit"

FIT_ORDER = {
    "too_tight": 0,
    "marginal": 1,
    "good": 2,
    "perfect": 3,
}


@dataclass
class LlmfitTool:
    command_prefix: list[str]
    source: str


@dataclass
class LlmfitPlanSummary:
    source: str
    plan: dict
    current_fit_level: str
    current_run_mode: str
    gpu_path_feasible: bool
    minimum_vram_gb: float | None
    recommended_vram_gb: float | None
    quantization: str


def env_flag(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() not in {"", "0", "false", "no", "off"}


def normalize_fit_level(value: object) -> str:
    text = str(value or "").strip()
    if not text:
        return "unknown"
    compact = text.replace("-", "_")
    normalized = []
    for char in compact:
        if char.isupper():
            if normalized and normalized[-1] != "_":
                normalized.append("_")
            normalized.append(char.lower())
        else:
            normalized.append(char)
    return "".join(normalized).strip("_")


def fit_level_meets_threshold(current_fit: str, minimum_fit: str) -> bool:
    current = FIT_ORDER.get(normalize_fit_level(current_fit), -1)
    minimum = FIT_ORDER.get(normalize_fit_level(minimum_fit), -1)
    return current >= minimum


def default_llmfit_root() -> Path:
    return DEFAULT_LLMFIT_ROOT


def resolve_llmfit_tool(
    *,
    llmfit_bin: str | None = None,
    llmfit_root: str | None = None,
    allow_cargo_run: bool = False,
) -> LlmfitTool | None:
    root = Path(llmfit_root).resolve() if llmfit_root else default_llmfit_root()

    explicit_bin = llmfit_bin or os.environ.get("LLMFIT_BIN")
    if explicit_bin:
        candidate = Path(explicit_bin).expanduser()
        if candidate.exists() and os.access(candidate, os.X_OK):
            return LlmfitTool([str(candidate)], "explicit-bin")

    path_bin = shutil.which("llmfit")
    if path_bin:
        return LlmfitTool([path_bin], "path")

    for rel_path, source in (
        (root / "target" / "release" / "llmfit", "release-binary"),
        (root / "target" / "debug" / "llmfit", "debug-binary"),
    ):
        if rel_path.exists() and os.access(rel_path, os.X_OK):
            return LlmfitTool([str(rel_path)], source)

    if allow_cargo_run and shutil.which("cargo") and (root / "Cargo.toml").exists():
        return LlmfitTool(
            [
                "cargo",
                "+stable",
                "run",
                "--quiet",
                "--manifest-path",
                str(root / "Cargo.toml"),
                "-p",
                "llmfit",
                "--",
            ],
            "cargo-run",
        )

    return None


def plan_model_with_llmfit(
    *,
    model_name: str,
    context: int,
    llmfit_bin: str | None = None,
    llmfit_root: str | None = None,
    memory_override: str | None = None,
    allow_cargo_run: bool = False,
    timeout: int = 120,
) -> LlmfitPlanSummary | None:
    tool = resolve_llmfit_tool(
        llmfit_bin=llmfit_bin,
        llmfit_root=llmfit_root,
        allow_cargo_run=allow_cargo_run,
    )
    if tool is None:
        return None

    command = list(tool.command_prefix)
    if memory_override:
        command.extend(["--memory", memory_override])
    command.extend(
        [
            "--json",
            "plan",
            model_name,
            "--context",
            str(context),
        ]
    )

    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "").strip()
        raise RuntimeError(
            f"llmfit plan failed for {model_name}: {detail or completed.returncode}"
        )

    try:
        plan = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"llmfit returned non-JSON output for {model_name}: {completed.stdout[:400]}"
        ) from exc

    gpu_path = next(
        (
            path
            for path in plan.get("run_paths", [])
            if str(path.get("path", "")).strip().lower() == "gpu"
        ),
        {},
    )
    current = plan.get("current", {})
    minimum = plan.get("minimum", {})
    recommended = plan.get("recommended", {})

    return LlmfitPlanSummary(
        source=tool.source,
        plan=plan,
        current_fit_level=normalize_fit_level(current.get("fit_level")),
        current_run_mode=normalize_fit_level(current.get("run_mode")),
        gpu_path_feasible=bool(gpu_path.get("feasible")),
        minimum_vram_gb=minimum.get("vram_gb"),
        recommended_vram_gb=recommended.get("vram_gb"),
        quantization=str(plan.get("quantization", "")).strip(),
    )


def write_llmfit_plan(path: Path, summary: LlmfitPlanSummary) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(summary.plan, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def llmfit_summary_payload(
    summary: LlmfitPlanSummary, report_path: str | Path | None = None
) -> dict[str, Any]:
    return {
        "source": summary.source,
        "current_fit_level": summary.current_fit_level,
        "current_run_mode": summary.current_run_mode,
        "gpu_path_feasible": summary.gpu_path_feasible,
        "minimum_vram_gb": summary.minimum_vram_gb,
        "recommended_vram_gb": summary.recommended_vram_gb,
        "quantization": summary.quantization,
        "report_path": None if report_path is None else str(report_path),
    }


def llmfit_gate_status(
    *,
    requested_device: str,
    summary: LlmfitPlanSummary | None,
    minimum_fit: str,
    context: int | None = None,
) -> tuple[str, str | None]:
    if requested_device != "gpu":
        return "not_applicable", "CPU training does not require a GPU llmfit gate"
    if summary is None:
        return "unavailable", "llmfit result unavailable"
    if not summary.gpu_path_feasible:
        return (
            "rejected",
            (
                "llmfit rejected GPU training: no feasible GPU path"
                if context is None
                else (
                    "llmfit rejected GPU training: "
                    f"no feasible GPU path at context {context}"
                )
            ),
        )
    if summary.current_fit_level == "too_tight":
        return "rejected", "llmfit rejected GPU training: fit=too_tight"
    if not fit_level_meets_threshold(summary.current_fit_level, minimum_fit):
        return (
            "warning",
            f"llmfit fit below threshold ({summary.current_fit_level} < {minimum_fit})",
        )
    return "validated", None


def build_llmfit_record(
    *,
    enabled: bool,
    requested_device: str,
    model_name: str,
    context: int,
    minimum_fit: str,
    summary: LlmfitPlanSummary | None = None,
    report_path: str | Path | None = None,
    warning: str | None = None,
) -> dict[str, Any]:
    status, reason = llmfit_gate_status(
        requested_device=requested_device,
        summary=summary,
        minimum_fit=minimum_fit,
        context=context,
    )
    if not enabled:
        status = "disabled"
        reason = "llmfit preflight disabled"
    elif summary is None and warning is not None:
        status = "unavailable"
        reason = warning

    payload: dict[str, Any] = {
        "enabled": enabled,
        "requested_device": requested_device,
        "model": model_name,
        "context": context,
        "minimum_fit": minimum_fit,
        "status": status,
    }
    if reason is not None:
        payload["reason"] = reason
    if warning is not None:
        payload["warning"] = warning
    if summary is not None:
        payload.update(llmfit_summary_payload(summary, report_path=report_path))
    elif report_path is not None:
        payload["report_path"] = str(report_path)
    return payload
