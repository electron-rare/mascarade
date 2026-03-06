#!/usr/bin/env python3
"""Summarize local batch manifests produced by finetune/batch_local.py."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_RUNS_DIR = SCRIPT_DIR / "runs"


def load_manifest(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def find_manifests(runs_dir: Path) -> list[Path]:
    return sorted(runs_dir.glob("*/manifest.json"), key=lambda p: p.stat().st_mtime, reverse=True)


def compact_status(payload: dict) -> str:
    distill = payload.get("distill", "?")
    train = payload.get("train", "?")
    return f"d={distill},t={train}"


def summarize_manifest(path: Path) -> dict:
    manifest = load_manifest(path)
    domains = manifest.get("domains", {})
    summary = {
        "path": str(path),
        "run_dir": manifest.get("run_dir", str(path.parent)),
        "run_label": manifest.get("run_label", path.parent.name),
        "updated_at": manifest.get("updated_at", "?"),
        "teacher": f"{manifest.get('config', {}).get('teacher_provider', '?')}/{manifest.get('config', {}).get('teacher_model', '?')}",
        "device": manifest.get("config", {}).get("device", "?"),
        "domains": [],
    }
    for label, payload in domains.items():
        summary["domains"].append(
            {
                "label": label,
                "canonical": payload.get("canonical", "?"),
                "distill": payload.get("distill", {}).get("status", "?"),
                "train": payload.get("train", {}).get("status", "?"),
                "merged_rows": payload.get("distill", {}).get("merged_rows"),
                "distilled_rows": payload.get("distill", {}).get("distilled_rows"),
                "error": payload.get("distill", {}).get("error")
                or payload.get("train", {}).get("error"),
            }
        )
    return summary


def format_overview(items: list[dict]) -> str:
    if not items:
        return "No batch manifests found."

    headers = ["run", "updated_at", "device", "teacher", "domains"]
    rows = []
    for item in items:
        domain_summary = " ".join(
            f"{domain['label']}[{compact_status(domain)}]" for domain in item["domains"]
        )
        rows.append(
            [
                item["run_label"],
                item["updated_at"],
                item["device"],
                item["teacher"],
                domain_summary,
            ]
        )

    widths = [len(header) for header in headers]
    for row in rows:
        for idx, value in enumerate(row):
            widths[idx] = max(widths[idx], len(str(value)))

    lines = []
    lines.append("  ".join(header.ljust(widths[idx]) for idx, header in enumerate(headers)))
    lines.append("  ".join("-" * widths[idx] for idx in range(len(headers))))
    for row in rows:
        lines.append("  ".join(str(value).ljust(widths[idx]) for idx, value in enumerate(row)))
    return "\n".join(lines)


def format_detail(item: dict) -> str:
    lines = [
        f"run_dir:   {item['run_dir']}",
        f"updated:   {item['updated_at']}",
        f"teacher:   {item['teacher']}",
        f"device:    {item['device']}",
        "",
        "domains:",
    ]
    for domain in item["domains"]:
        lines.append(
            f"  - {domain['label']} ({domain['canonical']}): "
            f"distill={domain['distill']} train={domain['train']} "
            f"merged={domain['merged_rows']} distilled={domain['distilled_rows']}"
        )
        if domain["error"]:
            lines.append(f"    error: {domain['error']}")
    return "\n".join(lines)


def resolve_manifest_target(run_arg: str) -> Path:
    path = Path(run_arg)
    if not path.is_absolute():
        path = (Path.cwd() / path).resolve()
    if path.is_dir():
        path = path / "manifest.json"
    return path


def main() -> int:
    parser = argparse.ArgumentParser(description="Summarize finetune batch manifests")
    parser.add_argument("--runs-dir", default=str(DEFAULT_RUNS_DIR))
    parser.add_argument("--latest", type=int, default=5, help="Number of latest runs to show")
    parser.add_argument("--run", default=None, help="Specific run dir or manifest.json to inspect")
    parser.add_argument("--json", action="store_true", help="Emit raw JSON summary")
    args = parser.parse_args()

    if args.run:
        manifest_path = resolve_manifest_target(args.run)
        if not manifest_path.exists():
            raise SystemExit(f"Manifest not found: {manifest_path}")
        summary = summarize_manifest(manifest_path)
        if args.json:
            print(json.dumps(summary, indent=2, ensure_ascii=False))
        else:
            print(format_detail(summary))
        return 0

    runs_dir = Path(args.runs_dir)
    manifests = find_manifests(runs_dir)[: max(1, args.latest)]
    summaries = [summarize_manifest(path) for path in manifests]
    if args.json:
        print(json.dumps(summaries, indent=2, ensure_ascii=False))
    else:
        print(format_overview(summaries))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
