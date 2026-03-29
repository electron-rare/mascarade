#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DISCOVERY_PATTERN = re.compile(r"(^|[_-])(todo|plan)([_-]|\d|\.|$)", re.IGNORECASE)
CHECKBOX_PATTERN = re.compile(r"^\s*-\s+\[\s\]\s+(?P<text>.+?)\s*$")
ORDERED_PATTERN = re.compile(r"^\s*\d+\.\s+(?P<text>.+?)\s*$")
TABLE_SECTION_PATTERN = re.compile(
    r"^## File d'execution\n(?P<body>.*?)(?=^## |\Z)",
    re.MULTILINE | re.DOTALL,
)
EXCLUDED_PARTS = {
    ".git",
    ".venv",
    "__pycache__",
    "build",
    "dist",
    "htmlcov",
    "node_modules",
}
SUPPORTED_ROLES = {
    "active",
    "audit",
    "external-canonical",
    "historical",
    "implemented",
}
SUPPORTED_PARSERS = {"actionable", "checklist", "execution_hub", "none"}
HUB_ACTIVE_STATUSES = {"BLOCKED", "IN_PROGRESS", "PENDING"}
HUB_DONE_STATUSES = {"DEFERRED", "DONE"}


@dataclass
class RegistryEntry:
    path: str
    repo: str
    role: str
    scope: str | None = None
    source_of_truth: bool = False
    supersedes: list[str] = field(default_factory=list)
    superseded_by: str | None = None
    external_ref: str | None = None
    validation: str | None = None
    canonical_ref: str | None = None
    parser: str = "checklist"

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "RegistryEntry":
        supersedes = payload.get("supersedes", [])
        if isinstance(supersedes, str):
            supersedes = [supersedes]
        return cls(
            path=str(payload["path"]),
            repo=str(payload["repo"]),
            role=str(payload["role"]),
            scope=_optional_str(payload.get("scope")),
            source_of_truth=bool(payload.get("source_of_truth", False)),
            supersedes=[str(item) for item in supersedes],
            superseded_by=_optional_str(payload.get("superseded_by")),
            external_ref=_optional_str(payload.get("external_ref")),
            validation=_optional_str(payload.get("validation")),
            canonical_ref=_optional_str(payload.get("canonical_ref")),
            parser=str(payload.get("parser", "checklist")),
        )


@dataclass
class Issue:
    severity: str
    code: str
    path: str
    message: str

    def as_dict(self) -> dict[str, str]:
        return asdict(self)


@dataclass
class ItemRecord:
    identifier: str
    text: str
    normalized: str
    classification: str
    status: str | None = None
    scope: str | None = None
    validation: str | None = None

    def as_dict(self) -> dict[str, str | None]:
        return asdict(self)


@dataclass
class DocumentResult:
    path: str
    role: str
    repo: str
    parser: str
    source_of_truth: bool
    exists: bool
    open_item_count: int
    items: list[ItemRecord]
    issues: list[Issue]

    def status(self) -> str:
        if any(issue.severity == "error" for issue in self.issues):
            return "invalid"
        if any(issue.severity == "warning" for issue in self.issues):
            return "warning"
        return "ok"

    def as_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "role": self.role,
            "repo": self.repo,
            "parser": self.parser,
            "source_of_truth": self.source_of_truth,
            "exists": self.exists,
            "open_item_count": self.open_item_count,
            "status": self.status(),
            "items": [item.as_dict() for item in self.items],
            "issues": [issue.as_dict() for issue in self.issues],
        }


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _load_registry_payload(registry_path: Path) -> dict[str, Any]:
    raw = registry_path.read_text(encoding="utf-8")
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        try:
            import yaml  # type: ignore
        except ModuleNotFoundError as exc:
            raise SystemExit(
                "docs/TODO_PLAN_REGISTRY.yaml must be JSON-compatible YAML "
                "unless PyYAML is installed."
            ) from exc
        payload = yaml.safe_load(raw)
    if not isinstance(payload, dict):
        raise SystemExit("Registry payload must be a mapping.")
    return payload


def load_registry(registry_path: Path) -> list[RegistryEntry]:
    payload = _load_registry_payload(registry_path)
    documents = payload.get("documents")
    if not isinstance(documents, list):
        raise SystemExit("Registry payload must define a top-level 'documents' list.")
    return [RegistryEntry.from_dict(item) for item in documents]


def discover_candidate_docs(repo_root: Path) -> list[str]:
    matches: list[str] = []
    for path in repo_root.rglob("*.md"):
        rel_path = path.relative_to(repo_root)
        if any(part in EXCLUDED_PARTS for part in rel_path.parts):
            continue
        name = rel_path.name.lower()
        if name == "execution_hub.md" or DISCOVERY_PATTERN.search(name):
            matches.append(rel_path.as_posix())
    return sorted(set(matches))


def _normalize_item_text(text: str) -> str:
    lowered = text.strip().lower()
    lowered = re.sub(r"`([^`]+)`", r"\1", lowered)
    lowered = re.sub(r"[*_~]", "", lowered)
    lowered = re.sub(r"[^a-z0-9]+", " ", lowered)
    return re.sub(r"\s+", " ", lowered).strip()


def _parse_hub_items(text: str, entry: RegistryEntry) -> list[ItemRecord]:
    match = TABLE_SECTION_PATTERN.search(text)
    if not match:
        return []
    items: list[ItemRecord] = []
    for raw_line in match.group("body").splitlines():
        line = raw_line.strip()
        if not line.startswith("|"):
            continue
        if line.startswith("| ID ") or line.startswith("| --- "):
            continue
        cells = [cell.strip() for cell in raw_line.split("|")[1:-1]]
        if len(cells) != 7:
            continue
        lot_id = _clean_table_cell(cells[0])
        title = _clean_table_cell(cells[2])
        status = _clean_table_cell(cells[3]).upper()
        scope = _clean_table_cell(cells[4]) or entry.scope
        validation = _clean_table_cell(cells[6]) or entry.validation
        if status in HUB_DONE_STATUSES:
            continue
        classification = "blocked" if status == "BLOCKED" else "active"
        items.append(
            ItemRecord(
                identifier=lot_id,
                text=title,
                normalized=_normalize_item_text(title),
                classification=classification,
                status=status,
                scope=scope,
                validation=validation,
            )
        )
    return items


def _clean_table_cell(value: str) -> str:
    cleaned = value.strip()
    if cleaned.startswith("`") and cleaned.endswith("`") and cleaned.count("`") == 2:
        return cleaned[1:-1].strip()
    return cleaned


def _parse_checklist_items(text: str, entry: RegistryEntry) -> list[ItemRecord]:
    items: list[ItemRecord] = []
    in_code_block = False
    for line in text.splitlines():
        if line.strip().startswith("```"):
            in_code_block = not in_code_block
            continue
        if in_code_block:
            continue
        match = CHECKBOX_PATTERN.match(line)
        if not match:
            continue
        item_text = match.group("text").strip()
        items.append(
            ItemRecord(
                identifier=f"{entry.path}:{len(items) + 1}",
                text=item_text,
                normalized=_normalize_item_text(item_text),
                classification=_classification_for_role(entry.role),
                scope=entry.scope,
                validation=entry.validation,
            )
        )
    return items


def _parse_actionable_items(text: str, entry: RegistryEntry) -> list[ItemRecord]:
    checklist_items = _parse_checklist_items(text, entry)
    if checklist_items:
        return checklist_items
    items: list[ItemRecord] = []
    in_code_block = False
    for line in text.splitlines():
        if line.strip().startswith("```"):
            in_code_block = not in_code_block
            continue
        if in_code_block:
            continue
        match = ORDERED_PATTERN.match(line)
        if not match:
            continue
        item_text = match.group("text").strip()
        items.append(
            ItemRecord(
                identifier=f"{entry.path}:{len(items) + 1}",
                text=item_text,
                normalized=_normalize_item_text(item_text),
                classification=_classification_for_role(entry.role),
                scope=entry.scope,
                validation=entry.validation,
            )
        )
    return items


def _classification_for_role(role: str) -> str:
    if role == "active":
        return "active"
    if role == "external-canonical":
        return "external"
    if role == "implemented":
        return "done-but-not-canonical"
    return "historical"


def parse_items(text: str, entry: RegistryEntry) -> list[ItemRecord]:
    if entry.parser == "execution_hub":
        return _parse_hub_items(text, entry)
    if entry.parser == "actionable":
        return _parse_actionable_items(text, entry)
    if entry.parser == "checklist":
        return _parse_checklist_items(text, entry)
    return []


def validate_entry(
    entry: RegistryEntry,
    repo_root: Path,
) -> DocumentResult:
    issues: list[Issue] = []
    if entry.role not in SUPPORTED_ROLES:
        issues.append(
            Issue("error", "invalid-role", entry.path, f"Unsupported role '{entry.role}'.")
        )
    if entry.parser not in SUPPORTED_PARSERS:
        issues.append(
            Issue(
                "error",
                "invalid-parser",
                entry.path,
                f"Unsupported parser '{entry.parser}'.",
            )
        )
    if not entry.validation:
        issues.append(
            Issue(
                "error",
                "missing-validation",
                entry.path,
                "Registry entry is missing validation evidence or command.",
            )
        )
    if entry.role in {"active", "external-canonical"} and not entry.scope:
        issues.append(
            Issue(
                "error",
                "missing-scope",
                entry.path,
                "Active or external canonical entries must define a scope.",
            )
        )
    if entry.role == "external-canonical" and not entry.external_ref:
        issues.append(
            Issue(
                "error",
                "missing-external-ref",
                entry.path,
                "External canonical entries must define external_ref.",
            )
        )
    if entry.source_of_truth and entry.superseded_by:
        issues.append(
            Issue(
                "error",
                "superseded-source-of-truth",
                entry.path,
                "A superseded document cannot remain source_of_truth.",
            )
        )

    target_path = (repo_root / entry.path).resolve()
    exists = target_path.exists()
    if not exists:
        severity = "warning" if entry.role == "external-canonical" else "error"
        issues.append(
            Issue(
                severity,
                "missing-document",
                entry.path,
                f"Referenced document not found at {target_path}.",
            )
        )
        return DocumentResult(
            path=entry.path,
            role=entry.role,
            repo=entry.repo,
            parser=entry.parser,
            source_of_truth=entry.source_of_truth,
            exists=False,
            open_item_count=0,
            items=[],
            issues=issues,
        )

    text = target_path.read_text(encoding="utf-8")
    items = parse_items(text, entry)

    if entry.role in {"active", "external-canonical"}:
        if not entry.canonical_ref:
            issues.append(
                Issue(
                    "error",
                    "missing-canonical-ref",
                    entry.path,
                    "Active or external canonical entries must define canonical_ref.",
                )
            )
        for item in items:
            if not item.scope:
                issues.append(
                    Issue(
                        "error",
                        "missing-item-scope",
                        entry.path,
                        f"Item '{item.text}' is missing scope information.",
                    )
                )
            if not item.validation:
                issues.append(
                    Issue(
                        "error",
                        "missing-item-validation",
                        entry.path,
                        f"Item '{item.text}' is missing validation information.",
                    )
                )
    elif items and entry.canonical_ref and entry.canonical_ref not in text:
        issues.append(
            Issue(
                "error",
                "missing-canonical-pointer",
                entry.path,
                f"Historical or implemented doc still has open items but does not point to {entry.canonical_ref}.",
            )
        )

    return DocumentResult(
        path=entry.path,
        role=entry.role,
        repo=entry.repo,
        parser=entry.parser,
        source_of_truth=entry.source_of_truth,
        exists=True,
        open_item_count=len(items),
        items=items,
        issues=issues,
    )


def build_report(
    registry_path: Path,
    repo_root: Path,
    *,
    fail_on_duplicates: bool,
    fail_on_unclassified: bool,
) -> dict[str, Any]:
    entries = load_registry(registry_path)
    entry_map = {entry.path: entry for entry in entries}
    issues: list[Issue] = []
    discovered = discover_candidate_docs(repo_root)
    unclassified = [path for path in discovered if path not in entry_map]
    if unclassified:
        severity = "error" if fail_on_unclassified else "warning"
        issues.extend(
            Issue(
                severity,
                "unclassified-document",
                path,
                "Discovered TODO/plan document is not registered.",
            )
            for path in unclassified
        )

    document_results = [
        validate_entry(entry, repo_root)
        for entry in entries
    ]
    for result in document_results:
        issues.extend(result.issues)

    duplicates = _find_duplicate_active_items(document_results)
    if duplicates:
        severity = "error" if fail_on_duplicates else "warning"
        issues.extend(
            Issue(
                severity,
                "duplicate-active-item",
                ",".join(group["paths"]),
                f"Duplicate active item '{group['normalized']}' appears in multiple active docs.",
            )
            for group in duplicates
        )

    item_summary = _summarize_items(document_results)
    role_summary = _summarize_roles(document_results)
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "registry_path": registry_path.as_posix(),
        "repo_root": repo_root.as_posix(),
        "summary": {
            "documents": len(document_results),
            "active_documents": sum(1 for item in document_results if item.role == "active"),
            "source_of_truth_documents": sum(
                1 for item in document_results if item.source_of_truth
            ),
            "unclassified_documents": len(unclassified),
            "duplicate_groups": len(duplicates),
            "errors": sum(1 for issue in issues if issue.severity == "error"),
            "warnings": sum(1 for issue in issues if issue.severity == "warning"),
            "items": item_summary,
            "roles": role_summary,
        },
        "documents": [result.as_dict() for result in document_results],
        "duplicates": duplicates,
        "unclassified": unclassified,
        "issues": [issue.as_dict() for issue in issues],
    }
    return report


def _find_duplicate_active_items(
    document_results: list[DocumentResult],
) -> list[dict[str, Any]]:
    index: dict[str, list[tuple[str, str]]] = {}
    for result in document_results:
        if result.role != "active":
            continue
        for item in result.items:
            if item.classification not in {"active", "blocked"}:
                continue
            if not item.normalized:
                continue
            index.setdefault(item.normalized, []).append((result.path, item.text))
    duplicates: list[dict[str, Any]] = []
    for normalized, occurrences in sorted(index.items()):
        paths = sorted({path for path, _ in occurrences})
        if len(paths) < 2:
            continue
        duplicates.append(
            {
                "normalized": normalized,
                "paths": paths,
                "items": [
                    {"path": path, "text": text}
                    for path, text in sorted(occurrences, key=lambda value: value[0])
                ],
            }
        )
    return duplicates


def _summarize_items(document_results: list[DocumentResult]) -> dict[str, int]:
    summary: dict[str, int] = {}
    for result in document_results:
        for item in result.items:
            summary[item.classification] = summary.get(item.classification, 0) + 1
    return dict(sorted(summary.items()))


def _summarize_roles(document_results: list[DocumentResult]) -> dict[str, int]:
    summary: dict[str, int] = {}
    for result in document_results:
        summary[result.role] = summary.get(result.role, 0) + 1
    return dict(sorted(summary.items()))


def render_markdown(report: dict[str, Any]) -> str:
    lines: list[str] = []
    summary = report["summary"]
    lines.append("# TODO/Plan Suite Report")
    lines.append("")
    lines.append(f"Generated: `{report['generated_at']}`")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append("| Metric | Value |")
    lines.append("| --- | --- |")
    lines.append(f"| Registered documents | {summary['documents']} |")
    lines.append(f"| Active documents | {summary['active_documents']} |")
    lines.append(f"| Source-of-truth documents | {summary['source_of_truth_documents']} |")
    lines.append(f"| Unclassified documents | {summary['unclassified_documents']} |")
    lines.append(f"| Duplicate active item groups | {summary['duplicate_groups']} |")
    lines.append(f"| Errors | {summary['errors']} |")
    lines.append(f"| Warnings | {summary['warnings']} |")
    lines.append("")
    lines.append("## Documents")
    lines.append("")
    lines.append("| Path | Role | Source of truth | Parser | Open items | Status |")
    lines.append("| --- | --- | --- | --- | --- | --- |")
    for document in report["documents"]:
        lines.append(
            "| `{path}` | `{role}` | `{source}` | `{parser}` | {open_items} | `{status}` |".format(
                path=document["path"],
                role=document["role"],
                source="yes" if document["source_of_truth"] else "no",
                parser=document["parser"],
                open_items=document["open_item_count"],
                status=document["status"],
            )
        )
    lines.append("")
    lines.append("## Item Classes")
    lines.append("")
    lines.append("| Classification | Count |")
    lines.append("| --- | --- |")
    for classification, count in sorted(summary["items"].items()):
        lines.append(f"| `{classification}` | {count} |")
    lines.append("")
    lines.append("## Duplicates")
    lines.append("")
    if report["duplicates"]:
        for group in report["duplicates"]:
            lines.append(f"- `{group['normalized']}`")
            for item in group["items"]:
                lines.append(f"  - `{item['path']}`: {item['text']}")
    else:
        lines.append("- None")
    lines.append("")
    lines.append("## Unclassified Docs")
    lines.append("")
    if report["unclassified"]:
        for path in report["unclassified"]:
            lines.append(f"- `{path}`")
    else:
        lines.append("- None")
    lines.append("")
    lines.append("## Issues")
    lines.append("")
    if report["issues"]:
        for issue in report["issues"]:
            lines.append(
                f"- `{issue['severity']}` `{issue['code']}` `{issue['path']}`: {issue['message']}"
            )
    else:
        lines.append("- None")
    lines.append("")
    return "\n".join(lines)


def _write_output(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--registry",
        default="docs/TODO_PLAN_REGISTRY.yaml",
        help="Path to the TODO/plan registry.",
    )
    parser.add_argument(
        "--repo-root",
        default=".",
        help="Repository root used for discovery and relative paths.",
    )
    parser.add_argument(
        "--emit-markdown",
        help="Optional path for a Markdown report.",
    )
    parser.add_argument(
        "--emit-json",
        help="Optional path for a JSON report.",
    )
    parser.add_argument(
        "--fail-on-duplicates",
        action="store_true",
        help="Treat duplicate active items as fatal errors.",
    )
    parser.add_argument(
        "--fail-on-unclassified",
        action="store_true",
        help="Treat unregistered discovered docs as fatal errors.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    repo_root = Path(args.repo_root).resolve()
    registry_path = (repo_root / args.registry).resolve()
    report = build_report(
        registry_path,
        repo_root,
        fail_on_duplicates=args.fail_on_duplicates,
        fail_on_unclassified=args.fail_on_unclassified,
    )
    markdown = render_markdown(report)
    if args.emit_markdown:
        _write_output((repo_root / args.emit_markdown).resolve(), markdown)
    if args.emit_json:
        _write_output(
            (repo_root / args.emit_json).resolve(),
            json.dumps(report, indent=2, ensure_ascii=True, sort_keys=True) + "\n",
        )
    if not args.emit_markdown and not args.emit_json:
        print(markdown)
    return 1 if report["summary"]["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
