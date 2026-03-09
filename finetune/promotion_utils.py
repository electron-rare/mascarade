#!/usr/bin/env python3
"""Helpers for opt-in live promotion of validated fine-tune outputs."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

try:
    from .ollama_runtime import OllamaRuntimeError, resolve_ollama_runtime, run_model
except ImportError:  # pragma: no cover - script execution path
    from ollama_runtime import OllamaRuntimeError, resolve_ollama_runtime, run_model

SCRIPT_DIR = Path(__file__).resolve().parent
PIPELINE_SCRIPT = SCRIPT_DIR / "pipeline.py"
MODELS_DIR = SCRIPT_DIR / "models_local"
DEFAULT_REGISTRY_PATH = MODELS_DIR / "promotion_registry.json"
DEFAULT_PROMOTION_QUANT = "q4_k_m"
PROMOTION_WORKDIR_ENV = "MASCARADE_PROMOTION_WORKDIR"
DEFAULT_PROMOTION_WORKDIR = Path("/dev/shm/mascarade-promotion")
DEFAULT_PROMOTION_REQUIRED_BYTES = 16 * 1024**3
PROMOTION_REVIEW_DIR_ENV = "MASCARADE_PROMOTION_REVIEW_DIR"
DEFAULT_PROMOTION_REVIEW_DIR = Path("/dev/shm/mascarade-review")
MANUAL_REVIEW_DOMAINS = {"components"}
SMOKE_PROMPTS = {
    "stm32": "Write a simple GPIO toggle on STM32F4.",
    "spice": "Write a SPICE netlist for a voltage divider.",
    "iot": "Write MQTT publish code for ESP32.",
    "power": "Calculate the inductor for a 12V to 5V buck converter at 2A.",
    "dsp": "Implement a moving average filter in C.",
    "emc": "Give PCB decoupling rules for a 100 MHz digital IC.",
    "kicad": "How do I configure DRC rules in KiCad for JLCPCB?",
    "embedded": "Write bare-metal SysTick init for Cortex-M4.",
    "platformio": "Show a minimal PlatformIO pio.ini for ESP32.",
    "freecad": "Write a simple FreeCAD Python macro that creates a cube.",
    "components": "Suggest two alternatives to LM317 and explain the tradeoffs.",
}


def manual_review_domains() -> set[str]:
    explicit = os.environ.get("MASCARADE_PROMOTION_MANUAL_REVIEW_DOMAINS")
    if explicit is None:
        return set(MANUAL_REVIEW_DOMAINS)
    return {
        item.strip()
        for item in explicit.split(",")
        if item.strip()
    }


def domain_requires_manual_review(domain: str) -> bool:
    return domain in manual_review_domains()


def review_alias_for(domain: str) -> str:
    return f"mascarade-{domain}-review"


def _resolve_pipeline_python() -> str:
    explicit = os.environ.get("MASCARADE_FINETUNE_PYTHON")
    if explicit:
        return explicit
    venv_python = SCRIPT_DIR.parent / "venv_tuning" / "bin" / "python"
    if venv_python.exists():
        return str(venv_python)
    return sys.executable


def _now_ts() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S")



def _load_json(path: Path) -> dict | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))



def load_registry(path: Path | None = None) -> dict:
    registry_path = path or DEFAULT_REGISTRY_PATH
    payload = _load_json(registry_path)
    if payload is not None:
        return payload
    return {"version": 1, "updated_at": _now_ts(), "domains": {}}



def write_registry(payload: dict, path: Path | None = None) -> Path:
    registry_path = path or DEFAULT_REGISTRY_PATH
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    payload["updated_at"] = _now_ts()
    registry_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return registry_path



def training_loss(training_info: dict | None) -> float | None:
    if not training_info:
        return None
    value = training_info.get("loss")
    try:
        return float(value)
    except (TypeError, ValueError):
        return None



def should_promote(existing: dict | None, candidate: dict) -> tuple[bool, str]:
    if existing is None:
        return True, "first promoted candidate for this domain"

    existing_smoke = bool(existing.get("smoke_ok"))
    if not existing_smoke:
        return True, "replacing a live alias without a successful smoke result"

    existing_loss = existing.get("loss")
    candidate_loss = candidate.get("loss")
    try:
        existing_loss = None if existing_loss is None else float(existing_loss)
    except (TypeError, ValueError):
        existing_loss = None
    try:
        candidate_loss = None if candidate_loss is None else float(candidate_loss)
    except (TypeError, ValueError):
        candidate_loss = None

    if candidate_loss is not None and existing_loss is not None:
        if candidate_loss < existing_loss:
            return True, f"better training loss ({candidate_loss:.4f} < {existing_loss:.4f})"
        return False, f"existing live loss is already better ({existing_loss:.4f} <= {candidate_loss:.4f})"

    existing_ts = str(existing.get("promoted_at") or "")
    candidate_ts = str(candidate.get("completed_at") or "")
    if candidate_ts > existing_ts:
        return True, "same validation level; keeping the most recent successful run"
    return False, "existing live candidate is at least as recent"



def _replace_directory_from_source(source_dir: Path, target_dir: Path, *, backup_folder: str) -> Path | None:
    if source_dir.resolve() == target_dir.resolve():
        return None
    backup_dir = None
    if target_dir.exists():
        backup_root = target_dir.parent / backup_folder
        backup_root.mkdir(parents=True, exist_ok=True)
        backup_dir = backup_root / f"{target_dir.name}_{time.strftime('%Y%m%d_%H%M%S')}"
        if backup_dir.exists():
            shutil.rmtree(backup_dir)
        shutil.copytree(target_dir, backup_dir)
        shutil.rmtree(target_dir)
    shutil.copytree(source_dir, target_dir)
    return backup_dir


def _directory_size_bytes(path: Path) -> int:
    total = 0
    for file_path in path.rglob("*"):
        if file_path.is_file():
            total += file_path.stat().st_size
    return total


def _disk_free_bytes(path: Path) -> int:
    probe = path
    while not probe.exists() and probe != probe.parent:
        probe = probe.parent
    return shutil.disk_usage(probe).free


def _prepare_promotion_workspace(
    run_output_dir: Path,
    live_dir: Path,
    canonical_domain: str,
) -> tuple[Path, Path, Path | None, str, str]:
    required_bytes = max(
        DEFAULT_PROMOTION_REQUIRED_BYTES,
        _directory_size_bytes(run_output_dir) * 4,
    )
    live_root = live_dir.parent
    live_free = _disk_free_bytes(live_root)
    if live_free >= required_bytes:
        backup_dir = _replace_directory_from_source(
            run_output_dir, live_dir, backup_folder=".promotion_backups"
        )
        return live_root, live_dir, backup_dir, "live", (
            f"using live workspace under {live_root} (free={live_free} bytes)"
        )

    scratch_root = Path(
        os.environ.get(PROMOTION_WORKDIR_ENV, str(DEFAULT_PROMOTION_WORKDIR))
    )
    scratch_free = _disk_free_bytes(scratch_root)
    if scratch_free < required_bytes:
        raise RuntimeError(
            "promotion workspace is full: "
            f"need about {required_bytes} bytes, "
            f"live_free={live_free}, scratch_free={scratch_free}"
        )

    workspace_root = scratch_root / f"{canonical_domain}_{time.strftime('%Y%m%d_%H%M%S')}"
    workspace_root.mkdir(parents=True, exist_ok=True)
    workspace_dir = workspace_root / canonical_domain
    shutil.copytree(run_output_dir, workspace_dir)
    return workspace_root, workspace_dir, None, "scratch", (
        f"using scratch workspace under {workspace_root} because live_free={live_free} bytes"
    )



def _restore_backup(backup_dir: Path | None, live_dir: Path) -> None:
    if backup_dir is None or not backup_dir.exists():
        return
    if live_dir.exists():
        shutil.rmtree(live_dir)
    shutil.copytree(backup_dir, live_dir)


def _prepare_manual_review_workspace(
    run_output_dir: Path,
    canonical_domain: str,
) -> tuple[Path, Path, Path | None, str]:
    review_root = Path(
        os.environ.get(PROMOTION_REVIEW_DIR_ENV, str(DEFAULT_PROMOTION_REVIEW_DIR))
    )
    review_root.mkdir(parents=True, exist_ok=True)
    review_dir = review_root / canonical_domain
    backup_dir = _replace_directory_from_source(
        run_output_dir,
        review_dir,
        backup_folder=".review_backups",
    )
    return review_root, review_dir, backup_dir, (
        f"staged manual-review workspace under {review_dir}"
    )



def _run_pipeline_step(
    domain: str,
    step: str,
    *,
    base_model: str,
    quant: str,
    models_dir: Path | None = None,
    deploy_alias: str | None = None,
) -> tuple[bool, str]:
    command = [_resolve_pipeline_python(), str(PIPELINE_SCRIPT), domain, "--step", step]
    if step == "merge":
        command.extend(["--base", base_model])
    if step == "gguf":
        command.extend(["--quant", quant])
    if step == "deploy" and deploy_alias:
        command.extend(["--deploy-alias", deploy_alias])
    env = os.environ.copy()
    if models_dir is not None:
        env["MASCARADE_FINETUNE_MODELS_DIR"] = str(models_dir)
    completed = subprocess.run(
        command,
        cwd=SCRIPT_DIR,
        capture_output=True,
        text=True,
        env=env,
    )
    combined = (completed.stdout or "") + (completed.stderr or "")
    return completed.returncode == 0, combined[-4000:]



def _smoke_alias(domain: str, *, model_name: str | None = None) -> tuple[bool, str]:
    resolved_model_name = model_name or f"mascarade-{domain}"
    prompt = SMOKE_PROMPTS.get(domain, "Describe your specialty in one paragraph.")
    try:
        runtime = resolve_ollama_runtime()
    except OllamaRuntimeError as exc:
        return False, str(exc)
    completed = run_model(runtime, model_name=resolved_model_name, prompt=prompt, timeout=180)
    output = ((completed.stdout or "") + (completed.stderr or "")).strip()
    return completed.returncode == 0, output[:600]



def promote_domain_run(
    *,
    domain: str,
    canonical_domain: str,
    run_output_dir: Path,
    student_model: str,
    training_info: dict | None,
    run_manifest_path: Path | None,
    promotion_quant: str = DEFAULT_PROMOTION_QUANT,
    registry_path: Path | None = None,
) -> dict:
    registry = load_registry(registry_path)
    live_dir = MODELS_DIR / canonical_domain
    review_required = domain_requires_manual_review(canonical_domain)
    review_alias = review_alias_for(canonical_domain) if review_required else None
    candidate = {
        "domain": domain,
        "canonical_domain": canonical_domain,
        "student_model": student_model,
        "run_output_dir": str(run_output_dir),
        "run_manifest_path": None if run_manifest_path is None else str(run_manifest_path),
        "loss": training_loss(training_info),
        "completed_at": _now_ts(),
        "promotion_quant": promotion_quant,
        "live_alias": f"mascarade-{canonical_domain}",
        "review_required": review_required,
        "review_alias": review_alias,
    }
    existing = registry.get("domains", {}).get(canonical_domain)
    should_replace, selection_reason = should_promote(existing, candidate)
    if not should_replace:
        return {
            "status": "skipped",
            "reason": selection_reason,
            "registry_path": str(registry_path or DEFAULT_REGISTRY_PATH),
            "live_alias": candidate["live_alias"],
        }

    backup_dir = None
    workspace_root: Path | None = None
    workspace_dir: Path | None = None
    workspace_mode = "live"
    workspace_reason = "default live workspace"
    step_logs: dict[str, str] = {}
    try:
        if review_required:
            workspace_root, workspace_dir, backup_dir, workspace_reason = (
                _prepare_manual_review_workspace(run_output_dir, canonical_domain)
            )
            workspace_mode = "review"
        else:
            workspace_root, workspace_dir, backup_dir, workspace_mode, workspace_reason = (
                _prepare_promotion_workspace(run_output_dir, live_dir, canonical_domain)
            )
        for step in ("merge", "gguf", "deploy"):
            ok, log_tail = _run_pipeline_step(
                canonical_domain,
                step,
                base_model=student_model,
                quant=promotion_quant,
                models_dir=workspace_root,
                deploy_alias=review_alias if review_required and step == "deploy" else None,
            )
            step_logs[step] = log_tail
            if not ok:
                raise RuntimeError(f"pipeline step {step} failed")
        smoke_ok, smoke_output = _smoke_alias(
            canonical_domain,
            model_name=review_alias if review_required else None,
        )
        if not smoke_ok:
            raise RuntimeError(f"live smoke failed: {smoke_output}")

        candidate.update(
            {
                "selection_reason": selection_reason,
                "backup_path": None if backup_dir is None else str(backup_dir),
                "workspace_mode": workspace_mode,
                "workspace_reason": workspace_reason,
            }
        )
        if review_required:
            candidate.update(
                {
                    "status": "pending_manual_review",
                    "review_output_dir": str(workspace_dir),
                    "review_smoke_ok": True,
                    "review_smoke_output": smoke_output,
                }
            )
        else:
            candidate.update(
                {
                    "status": "completed",
                    "smoke_ok": True,
                    "smoke_output": smoke_output,
                }
            )
        registry.setdefault("domains", {})[canonical_domain] = candidate
        registry_file = write_registry(registry, registry_path)
        if workspace_mode == "scratch" and workspace_root and workspace_root.exists():
            shutil.rmtree(workspace_root)
        return {
            "status": "pending_manual_review" if review_required else "completed",
            "reason": selection_reason,
            "registry_path": str(registry_file),
            "live_alias": candidate["live_alias"],
            "review_alias": review_alias,
            "backup_path": candidate.get("backup_path"),
            "workspace_mode": workspace_mode,
            "workspace_reason": workspace_reason,
            "smoke_output": smoke_output,
            "steps": {key: value[-600:] for key, value in step_logs.items()},
        }
    except Exception as exc:  # noqa: BLE001
        _restore_backup(backup_dir, workspace_dir or live_dir)
        if workspace_mode == "scratch" and workspace_root and workspace_root.exists():
            shutil.rmtree(workspace_root)
        return {
            "status": "failed",
            "reason": str(exc),
            "registry_path": str(registry_path or DEFAULT_REGISTRY_PATH),
            "live_alias": candidate["live_alias"],
            "review_alias": review_alias,
            "backup_path": None if backup_dir is None else str(backup_dir),
            "workspace_mode": workspace_mode,
            "workspace_reason": workspace_reason,
            "steps": {key: value[-600:] for key, value in step_logs.items()},
        }


def approve_reviewed_domain(
    domain: str,
    *,
    registry_path: Path | None = None,
) -> dict:
    registry = load_registry(registry_path)
    entry = registry.get("domains", {}).get(domain)
    if entry is None:
        return {
            "status": "failed",
            "reason": f"no promotion entry found for {domain}",
            "registry_path": str(registry_path or DEFAULT_REGISTRY_PATH),
        }
    if entry.get("status") != "pending_manual_review":
        return {
            "status": "failed",
            "reason": f"{domain} is not waiting for manual review",
            "registry_path": str(registry_path or DEFAULT_REGISTRY_PATH),
        }

    review_output_dir = Path(str(entry.get("review_output_dir") or ""))
    if not review_output_dir.exists():
        return {
            "status": "failed",
            "reason": f"review output dir missing: {review_output_dir}",
            "registry_path": str(registry_path or DEFAULT_REGISTRY_PATH),
        }

    live_alias = str(entry.get("live_alias") or f"mascarade-{domain}")
    step_ok, deploy_log = _run_pipeline_step(
        domain,
        "deploy",
        base_model=str(entry.get("student_model") or ""),
        quant=str(entry.get("promotion_quant") or DEFAULT_PROMOTION_QUANT),
        models_dir=review_output_dir.parent,
        deploy_alias=live_alias,
    )
    if not step_ok:
        entry["last_manual_review_error"] = "pipeline step deploy failed"
        registry_file = write_registry(registry, registry_path)
        return {
            "status": "failed",
            "reason": "pipeline step deploy failed",
            "registry_path": str(registry_file),
            "live_alias": live_alias,
            "steps": {"deploy": deploy_log[-600:]},
        }

    smoke_ok, smoke_output = _smoke_alias(domain, model_name=live_alias)
    if not smoke_ok:
        entry["last_manual_review_error"] = f"live smoke failed: {smoke_output}"
        registry_file = write_registry(registry, registry_path)
        return {
            "status": "failed",
            "reason": f"live smoke failed: {smoke_output}",
            "registry_path": str(registry_file),
            "live_alias": live_alias,
            "steps": {"deploy": deploy_log[-600:]},
        }

    entry["status"] = "completed"
    entry["approved_at"] = _now_ts()
    entry["smoke_ok"] = True
    entry["smoke_output"] = smoke_output
    entry.pop("last_manual_review_error", None)
    registry_file = write_registry(registry, registry_path)
    return {
        "status": "completed",
        "reason": "manual review approved and live alias replaced",
        "registry_path": str(registry_file),
        "live_alias": live_alias,
        "review_alias": entry.get("review_alias"),
        "smoke_output": smoke_output,
        "steps": {"deploy": deploy_log[-600:]},
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Promotion helpers for fine-tune outputs")
    subparsers = parser.add_subparsers(dest="command", required=True)

    stage = subparsers.add_parser("stage", help="Stage a run for live promotion or manual review")
    stage.add_argument("domain", help="Canonical domain name")
    stage.add_argument("--run-output-dir", required=True)
    stage.add_argument("--student-model", required=True)
    stage.add_argument("--training-info", default=None)
    stage.add_argument("--run-manifest-path", default=None)
    stage.add_argument("--promotion-quant", default=DEFAULT_PROMOTION_QUANT)
    stage.add_argument("--registry-path", default=None)

    approve = subparsers.add_parser("approve", help="Approve a staged manual-review promotion")
    approve.add_argument("domain", help="Canonical domain name")
    approve.add_argument("--registry-path", default=None)

    status = subparsers.add_parser("status", help="Show the promotion registry entry for a domain")
    status.add_argument("domain", help="Canonical domain name")
    status.add_argument("--registry-path", default=None)
    return parser


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()
    registry_path = Path(args.registry_path).resolve() if args.registry_path else None

    if args.command == "stage":
        training_info = None
        if args.training_info:
            training_info = _load_json(Path(args.training_info).resolve())
        result = promote_domain_run(
            domain=args.domain,
            canonical_domain=args.domain,
            run_output_dir=Path(args.run_output_dir).resolve(),
            student_model=args.student_model,
            training_info=training_info,
            run_manifest_path=(
                None
                if args.run_manifest_path is None
                else Path(args.run_manifest_path).resolve()
            ),
            promotion_quant=args.promotion_quant,
            registry_path=registry_path,
        )
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0 if result.get("status") in {"completed", "pending_manual_review"} else 1

    if args.command == "approve":
        result = approve_reviewed_domain(args.domain, registry_path=registry_path)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0 if result.get("status") == "completed" else 1

    registry = load_registry(registry_path)
    payload = registry.get("domains", {}).get(args.domain)
    if payload is None:
        print(
            json.dumps(
                {
                    "status": "missing",
                    "domain": args.domain,
                    "registry_path": str(registry_path or DEFAULT_REGISTRY_PATH),
                },
                indent=2,
                ensure_ascii=False,
            )
        )
        return 1
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
