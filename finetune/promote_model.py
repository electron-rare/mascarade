#!/usr/bin/env python3
"""Promote a completed batch or benchmark fine-tuning run into a stable local registry."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from run_manifest import load_json, now_ts

SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_REGISTRY = SCRIPT_DIR / "promoted_models.local.json"


def resolve_path(raw: str) -> Path:
    path = Path(raw)
    if not path.is_absolute():
        path = (Path.cwd() / path).resolve()
    return path


def resolve_manifest(run_arg: str) -> Path:
    path = resolve_path(run_arg)
    if path.is_dir():
        candidate = path / "manifest.json"
        if candidate.exists():
            return candidate
        candidate = path / "bench.json"
        if candidate.exists():
            return candidate
    return path


def load_registry(path: Path) -> dict:
    if not path.exists():
        return {"version": 1, "updated_at": now_ts(), "models": {}}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise SystemExit(f"Invalid promoted model registry: {path}")
    payload.setdefault("version", 1)
    payload.setdefault("models", {})
    return payload


def resolve_promotable_run(manifest_path: Path, manifest: dict, domain: str) -> dict:
    kind = str(manifest.get("kind") or "")
    if kind == "batch_local":
        domains = manifest.get("domains", {})
        if domain not in domains:
            raise SystemExit(f"Domain not found in manifest: {domain}")
        payload = domains[domain]
        canonical = str(payload.get("canonical") or domain)
        train = payload.get("train", {})
        if train.get("status") != "completed":
            raise SystemExit(
                f"Cannot promote {domain}: train status is {train.get('status')!r}"
            )
        train_output_dir = resolve_path(str(payload.get("train_output_dir")))
        return {
            "kind": kind,
            "canonical": canonical,
            "train_output_dir": train_output_dir,
            "student_model": manifest.get("config", {}).get("student_model"),
            "teacher_provider": manifest.get("config", {}).get("teacher_provider"),
            "teacher_model": manifest.get("config", {}).get("teacher_model"),
            "source": {
                "kind": "batch_local",
                "run_dir": manifest.get("run_dir"),
                "manifest_path": str(manifest_path),
                "run_label": manifest.get("run_label"),
            },
            "llmfit": train.get("llmfit"),
        }

    if kind == "gpu_slot_benchmark":
        jobs = manifest.get("jobs") or []
        job = next((item for item in jobs if str(item.get("label")) == domain), None)
        if job is None:
            raise SystemExit(f"Domain not found in benchmark: {domain}")
        if job.get("status") != "completed":
            raise SystemExit(
                f"Cannot promote {domain}: benchmark job status is {job.get('status')!r}"
            )
        canonical = str(job.get("canonical") or domain)
        train_output_dir = resolve_path(str(job.get("output_dir")))
        batch_manifest_path = resolve_path(str(manifest.get("batch_manifest")))
        batch_manifest = load_json(batch_manifest_path) or {}
        batch_cfg = (
            batch_manifest.get("config", {}) if isinstance(batch_manifest, dict) else {}
        )
        return {
            "kind": kind,
            "canonical": canonical,
            "train_output_dir": train_output_dir,
            "student_model": manifest.get("student_model"),
            "teacher_provider": batch_cfg.get("teacher_provider"),
            "teacher_model": batch_cfg.get("teacher_model"),
            "source": {
                "kind": "gpu_slot_benchmark",
                "run_dir": manifest.get("run_dir"),
                "manifest_path": str(manifest_path),
                "batch_manifest_path": str(batch_manifest_path),
                "gpu_slots": manifest.get("gpu_slots"),
            },
            "llmfit": None,
        }

    raise SystemExit(
        f"Unsupported run kind for promotion: {kind!r}. Expected 'batch_local' or 'gpu_slot_benchmark'."
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Promote a completed batch-local or GPU benchmark run into a stable local registry"
    )
    parser.add_argument(
        "--run",
        required=True,
        help="Batch run dir/manifest.json or benchmark run dir/bench.json",
    )
    parser.add_argument(
        "--domain",
        required=True,
        help="Domain label present in the batch manifest (e.g. esp32, spice, pio)",
    )
    parser.add_argument(
        "--alias",
        default=None,
        help="Stable promoted alias (defaults to the canonical domain)",
    )
    parser.add_argument(
        "--registry-path",
        default=str(DEFAULT_REGISTRY),
        help="Local promoted-model registry JSON path",
    )
    args = parser.parse_args()

    manifest_path = resolve_manifest(args.run)
    manifest = load_json(manifest_path)
    if not isinstance(manifest, dict):
        raise SystemExit(f"Invalid batch manifest: {manifest_path}")

    promotable = resolve_promotable_run(manifest_path, manifest, args.domain)
    canonical = str(promotable["canonical"])
    alias = args.alias or canonical
    train_output_dir = resolve_path(str(promotable["train_output_dir"]))
    adapter_path = train_output_dir / "adapter"
    training_info_path = train_output_dir / "training_info.json"
    run_manifest_path = train_output_dir / "run.json"
    llmfit_plan_path = train_output_dir / "llmfit_plan.json"

    if not adapter_path.exists():
        raise SystemExit(f"Adapter path not found: {adapter_path}")
    if not training_info_path.exists():
        raise SystemExit(f"Training info not found: {training_info_path}")

    training_info = load_json(training_info_path) or {}
    child_manifest = load_json(run_manifest_path) or {}

    registry_path = resolve_path(args.registry_path)
    registry = load_registry(registry_path)
    registry["models"][alias] = {
        "promoted_at": now_ts(),
        "alias": alias,
        "domain_label": args.domain,
        "canonical_domain": canonical,
        "source": {
            **promotable["source"],
        },
        "artifacts": {
            "train_output_dir": str(train_output_dir),
            "adapter_path": str(adapter_path),
            "training_info_path": str(training_info_path),
            "run_manifest_path": str(run_manifest_path),
            "llmfit_plan_path": str(llmfit_plan_path),
        },
        "student_model": promotable.get("student_model"),
        "teacher_provider": promotable.get("teacher_provider"),
        "teacher_model": promotable.get("teacher_model"),
        "training_info": training_info,
        "llmfit": promotable.get("llmfit") or child_manifest.get("llmfit"),
    }
    registry["updated_at"] = now_ts()
    registry_path.write_text(
        json.dumps(registry, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    print(f"[OK] promoted {args.domain} -> {alias}")
    print(f"[OK] registry: {registry_path}")
    print(f"[OK] adapter: {adapter_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
