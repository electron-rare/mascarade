#!/usr/bin/env python3
"""Prepare canonical fine-tuning datasets for Hugging Face dataset publication."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from dataset_quality import (
    DatasetQualityError,
    enforce_dataset_quality,
    summarize_quality_report,
)
from dataset_refresh import DOMAIN_RESEARCH, SUPPORTED_DOMAINS
from sharegpt_utils import (
    dedupe_rows_with_stats,
    ensure_row_ids_with_stats,
    load_jsonl,
    validate_rows,
    write_jsonl,
)

SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_DATASETS_DIR = SCRIPT_DIR / "datasets"
DEFAULT_OUTPUT_ROOT = SCRIPT_DIR / "hf_datasets"
DEFAULT_RESEARCH_DIR = SCRIPT_DIR / "research"

DOMAIN_TAGS = {
    "stm32": ["electronics", "embedded", "stm32", "firmware", "code-generation"],
    "spice": ["electronics", "spice", "eda", "simulation", "code-generation"],
    "iot": ["electronics", "iot", "esp32", "mqtt", "embedded"],
    "power": ["electronics", "power-electronics", "analog", "components"],
    "dsp": ["electronics", "dsp", "signal-processing", "embedded"],
    "emc": ["electronics", "emc", "emi", "pcb-design"],
    "kicad": ["electronics", "kicad", "pcb-design", "eda"],
    "embedded": ["electronics", "embedded", "firmware", "microcontroller"],
    "platformio": ["electronics", "platformio", "embedded", "code-generation"],
    "freecad": ["cad", "mechanical-design", "freecad", "openscad", "cadquery"],
    "components": [
        "electronics",
        "components",
        "datasheets",
        "sourcing",
        "bom",
        "altium",
        "easyeda",
    ],
}

DOMAIN_LICENSE_HINTS = {
    "components": ["CC-BY-SA-3.0", "Apache-2.0", "seed-authored"],
}


def _title(domain: str) -> str:
    return f"Mascarade {domain.replace('-', ' ').title()} Dataset"


def _size_category(row_count: int) -> str:
    if row_count < 1000:
        return "n<1K"
    if row_count < 10000:
        return "1K<n<10K"
    if row_count < 100000:
        return "10K<n<100K"
    return "100K<n<1M"


def _load_research_payload(domain: str, research_dir: Path) -> dict:
    path = research_dir / f"{domain}_refresh.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    metadata = DOMAIN_RESEARCH.get(domain, {})
    return {
        "domain": domain,
        "topic": metadata.get("topic", domain),
        "authoritative_urls": [
            {"label": label, "url": url}
            for label, url in metadata.get("authoritative_urls", [])
        ],
        "github_repos": [
            {"label": label, "url": url}
            for label, url in metadata.get("github_repos", [])
        ],
        "software_sources": [
            {"label": label, "url": url}
            for label, url in metadata.get("software_sources", [])
        ],
        "datasheet_roots": [
            {"label": label, "url": url}
            for label, url in metadata.get("datasheet_roots", [])
        ],
        "hf_sources": [
            {"name": source, "url": f"https://huggingface.co/datasets/{source}"}
            for source in metadata.get("hf_sources", [])
        ],
        "queries": metadata.get("queries", []),
    }


def _render_dataset_card(
    *,
    domain: str,
    username: str,
    dataset_file: str,
    row_count: int,
    quality_report: dict,
    research_payload: dict,
    duplicates_removed: int,
) -> str:
    repo_id = f"{username}/mascarade-{domain}-dataset"
    tags = DOMAIN_TAGS.get(domain, [domain])
    license_hints = DOMAIN_LICENSE_HINTS.get(domain, ["other"])
    lines = [
        "---",
        f"pretty_name: {_title(domain)}",
        "language:",
        "- en",
        "license: other",
        "task_categories:",
        "- text-generation",
        "task_ids:",
        "- question-answering",
        "tags:",
    ]
    lines.extend(f"- {tag}" for tag in tags)
    lines.extend(
        [
            "size_categories:",
            f"- {_size_category(row_count)}",
            "---",
            "",
            f"# {_title(domain)}",
            "",
            f"- Hugging Face repo target: `{repo_id}`",
            f"- Canonical file: `{dataset_file}`",
            f"- Rows: `{row_count}`",
            f"- Quality status: `{quality_report['status']}`",
            f"- Quality summary: {summarize_quality_report(quality_report)}",
            f"- Duplicates removed during HF packaging: `{duplicates_removed}`",
            "",
            "## Summary",
            "",
            f"This dataset packages the canonical Mascarade `{domain}` ShareGPT corpus for local fine-tuning "
            "and reproducible publication to the Hugging Face Hub.",
            "",
            "## Format",
            "",
            "Each row is ShareGPT-style JSONL with persistent `id` plus `system` / `human` / `gpt` messages.",
            "",
            "## Source roots",
            "",
            "### Official docs",
        ]
    )
    for item in research_payload.get("authoritative_urls", []):
        lines.append(f"- [{item['label']}]({item['url']})")
    if research_payload.get("github_repos"):
        lines.extend(["", "### Official GitHub"])
        for item in research_payload["github_repos"]:
            lines.append(f"- [{item['label']}]({item['url']})")
    if research_payload.get("software_sources"):
        lines.extend(["", "### Software sources"])
        for item in research_payload["software_sources"]:
            lines.append(f"- [{item['label']}]({item['url']})")
    if research_payload.get("datasheet_roots"):
        lines.extend(["", "### Datasheet and vendor roots"])
        for item in research_payload["datasheet_roots"]:
            lines.append(f"- [{item['label']}]({item['url']})")
    if research_payload.get("hf_sources"):
        lines.extend(["", "### Upstream Hugging Face datasets"])
        for item in research_payload["hf_sources"]:
            lines.append(f"- [{item['name']}]({item['url']})")
    lines.extend(
        [
            "",
            "## Licensing note",
            "",
            "This package aggregates seed-authored material and filtered upstream sources. Review upstream dataset "
            "licenses before public redistribution.",
            "",
            "Observed license families during packaging:",
        ]
    )
    lines.extend(f"- `{item}`" for item in license_hints)
    lines.extend(
        [
            "",
            "## Publication commands",
            "",
            "```bash",
            f"huggingface-cli repo create {repo_id} --type dataset -y",
            f"huggingface-cli upload {repo_id} README.md README.md --repo-type dataset",
            f"huggingface-cli upload {repo_id} {dataset_file} {dataset_file} --repo-type dataset",
            "huggingface-cli upload "
            f"{repo_id} metadata.json metadata.json --repo-type dataset",
            "```",
            "",
            "## Quality report",
            "",
            "```json",
            json.dumps(quality_report, indent=2, ensure_ascii=False),
            "```",
            "",
        ]
    )
    return "\n".join(lines)


def prepare_domain(
    *,
    domain: str,
    datasets_dir: Path,
    output_root: Path,
    research_dir: Path,
    username: str,
) -> dict:
    dataset_path = datasets_dir / f"{domain}_chat.jsonl"
    if not dataset_path.exists():
        raise SystemExit(f"Dataset not found: {dataset_path}")

    raw_rows = load_jsonl(dataset_path)
    normalized_rows, ids_fixed = ensure_row_ids_with_stats(raw_rows, f"{domain}-hf")
    deduped_rows, duplicates_removed = dedupe_rows_with_stats(normalized_rows)
    validation_errors = validate_rows(deduped_rows)
    if validation_errors:
        raise SystemExit(
            f"{domain}: dataset invalid for HF packaging ({len(validation_errors)} errors; {validation_errors[0]})"
        )
    try:
        quality_report = enforce_dataset_quality(
            deduped_rows,
            label=f"{domain} hf dataset",
            ids_fixed=ids_fixed,
        )
    except DatasetQualityError as exc:
        raise SystemExit(f"{domain}: HF dataset quality gate failed: {exc}") from exc

    domain_dir = output_root / domain
    domain_dir.mkdir(parents=True, exist_ok=True)
    dataset_file = f"{domain}_chat.jsonl"
    staged_dataset = domain_dir / dataset_file
    write_jsonl(staged_dataset, deduped_rows)

    research_payload = _load_research_payload(domain, research_dir)
    metadata = {
        "version": 1,
        "domain": domain,
        "repo_id": f"{username}/mascarade-{domain}-dataset",
        "dataset_file": dataset_file,
        "row_count": len(deduped_rows),
        "ids_fixed_during_packaging": ids_fixed,
        "duplicates_removed_during_packaging": duplicates_removed,
        "quality": quality_report,
        "research": research_payload,
    }
    (domain_dir / "metadata.json").write_text(
        json.dumps(metadata, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    (domain_dir / "README.md").write_text(
        _render_dataset_card(
            domain=domain,
            username=username,
            dataset_file=dataset_file,
            row_count=len(deduped_rows),
            quality_report=quality_report,
            research_payload=research_payload,
            duplicates_removed=duplicates_removed,
        )
        + "\n",
        encoding="utf-8",
    )
    return {
        "domain": domain,
        "output_dir": str(domain_dir),
        "dataset_path": str(staged_dataset),
        "repo_id": metadata["repo_id"],
        "row_count": metadata["row_count"],
        "quality_status": quality_report["status"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Prepare canonical datasets for HF publication"
    )
    parser.add_argument("domains", nargs="+", choices=SUPPORTED_DOMAINS)
    parser.add_argument("--dataset-dir", default=str(DEFAULT_DATASETS_DIR))
    parser.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT))
    parser.add_argument("--research-dir", default=str(DEFAULT_RESEARCH_DIR))
    parser.add_argument("--username", default=os.environ.get("HF_USER", "clemsail"))
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    datasets_dir = Path(args.dataset_dir).resolve()
    output_root = Path(args.output_root).resolve()
    research_dir = Path(args.research_dir).resolve()
    reports = [
        prepare_domain(
            domain=domain,
            datasets_dir=datasets_dir,
            output_root=output_root,
            research_dir=research_dir,
            username=args.username,
        )
        for domain in args.domains
    ]
    if args.json:
        print(json.dumps(reports, indent=2, ensure_ascii=False))
    else:
        for report in reports:
            print(
                f"[HF-DATASET] {report['domain']}: rows={report['row_count']} "
                f"quality={report['quality_status']} dir={report['output_dir']}"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
