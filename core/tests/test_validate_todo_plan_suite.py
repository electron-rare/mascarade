from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path


SCRIPT_PATH = (
    Path(__file__).resolve().parents[2] / "scripts" / "validate_todo_plan_suite.py"
)


def _load_module():
    spec = importlib.util.spec_from_file_location("validate_todo_plan_suite", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _write_registry(root: Path, documents: list[dict[str, object]]) -> None:
    registry_path = root / "docs" / "TODO_PLAN_REGISTRY.yaml"
    _write(registry_path, json.dumps({"documents": documents}, indent=2) + "\n")


def test_active_document_is_valid(tmp_path: Path) -> None:
    _write(
        tmp_path / "docs" / "EXECUTION_HUB.md",
        """# Execution Hub

## File d'execution

| ID | Repo canonique | Titre | Statut | Portee | Depend | Validation |
| --- | --- | --- | --- | --- | --- | --- |
| `M-001` | `mascarade` | Active lot | `PENDING` | `global` | `-` | `pytest -q` |

## Lot en cours
""",
    )
    _write_registry(
        tmp_path,
        [
            {
                "path": "docs/EXECUTION_HUB.md",
                "repo": "mascarade",
                "role": "active",
                "scope": "global",
                "source_of_truth": True,
                "validation": "pytest -q",
                "canonical_ref": "docs/EXECUTION_HUB.md",
                "parser": "execution_hub",
            }
        ],
    )

    module = _load_module()
    report = module.build_report(
        tmp_path / "docs" / "TODO_PLAN_REGISTRY.yaml",
        tmp_path,
        fail_on_duplicates=True,
        fail_on_unclassified=True,
    )

    assert report["summary"]["errors"] == 0
    assert report["documents"][0]["open_item_count"] == 1
    assert report["documents"][0]["items"][0]["classification"] == "active"


def test_historical_document_with_pointer_is_allowed(tmp_path: Path) -> None:
    _write(
        tmp_path / "docs" / "old_plan.md",
        """# Old Plan

Status suite: `historical-reference`
Source active: `docs/EXECUTION_HUB.md`

- [ ] stale task
""",
    )
    _write_registry(
        tmp_path,
        [
            {
                "path": "docs/old_plan.md",
                "repo": "mascarade",
                "role": "historical",
                "source_of_truth": False,
                "validation": "historical reference",
                "canonical_ref": "docs/EXECUTION_HUB.md",
                "parser": "checklist",
            }
        ],
    )

    module = _load_module()
    report = module.build_report(
        tmp_path / "docs" / "TODO_PLAN_REGISTRY.yaml",
        tmp_path,
        fail_on_duplicates=True,
        fail_on_unclassified=True,
    )

    assert report["summary"]["errors"] == 0
    assert report["documents"][0]["open_item_count"] == 1


def test_unclassified_document_is_detected(tmp_path: Path) -> None:
    _write(tmp_path / "docs" / "TODO_A.md", "# TODO A\n")
    _write_registry(tmp_path, [])

    module = _load_module()
    report = module.build_report(
        tmp_path / "docs" / "TODO_PLAN_REGISTRY.yaml",
        tmp_path,
        fail_on_duplicates=True,
        fail_on_unclassified=True,
    )

    assert report["summary"]["errors"] == 1
    assert report["unclassified"] == ["docs/TODO_A.md"]


def test_duplicate_active_items_are_detected(tmp_path: Path) -> None:
    _write(
        tmp_path / "docs" / "EXECUTION_HUB.md",
        """# Execution Hub

## File d'execution

| ID | Repo canonique | Titre | Statut | Portee | Depend | Validation |
| --- | --- | --- | --- | --- | --- | --- |
| `M-001` | `mascarade` | Same thing | `PENDING` | `global` | `-` | `pytest -q` |

## Lot en cours
""",
    )
    _write(
        tmp_path / "TODO_VM.md",
        """# TODO VM

- [ ] Same thing
""",
    )
    _write_registry(
        tmp_path,
        [
            {
                "path": "docs/EXECUTION_HUB.md",
                "repo": "mascarade",
                "role": "active",
                "scope": "global",
                "source_of_truth": True,
                "validation": "pytest -q",
                "canonical_ref": "docs/EXECUTION_HUB.md",
                "parser": "execution_hub",
            },
            {
                "path": "TODO_VM.md",
                "repo": "mascarade",
                "role": "active",
                "scope": "machine:test",
                "source_of_truth": False,
                "validation": "pytest -q",
                "canonical_ref": "docs/EXECUTION_HUB.md",
                "parser": "checklist",
            },
        ],
    )

    module = _load_module()
    report = module.build_report(
        tmp_path / "docs" / "TODO_PLAN_REGISTRY.yaml",
        tmp_path,
        fail_on_duplicates=True,
        fail_on_unclassified=True,
    )

    assert report["summary"]["errors"] == 1
    assert report["duplicates"][0]["paths"] == ["TODO_VM.md", "docs/EXECUTION_HUB.md"]


def test_active_document_without_validation_fails(tmp_path: Path) -> None:
    _write(tmp_path / "TODO_VM.md", "# TODO VM\n- [ ] Task\n")
    _write_registry(
        tmp_path,
        [
            {
                "path": "TODO_VM.md",
                "repo": "mascarade",
                "role": "active",
                "scope": "machine:test",
                "source_of_truth": False,
                "canonical_ref": "docs/EXECUTION_HUB.md",
                "parser": "checklist",
            }
        ],
    )

    module = _load_module()
    report = module.build_report(
        tmp_path / "docs" / "TODO_PLAN_REGISTRY.yaml",
        tmp_path,
        fail_on_duplicates=True,
        fail_on_unclassified=True,
    )

    issue_codes = {issue["code"] for issue in report["issues"]}
    assert "missing-validation" in issue_codes
    assert "missing-item-validation" in issue_codes
    assert report["summary"]["errors"] == 2


def test_superseded_source_of_truth_fails(tmp_path: Path) -> None:
    _write(tmp_path / "plan.md", "# plan\n")
    _write_registry(
        tmp_path,
        [
            {
                "path": "plan.md",
                "repo": "mascarade",
                "role": "historical",
                "source_of_truth": True,
                "superseded_by": "docs/EXECUTION_HUB.md",
                "validation": "historical reference",
                "parser": "none",
            }
        ],
    )

    module = _load_module()
    report = module.build_report(
        tmp_path / "docs" / "TODO_PLAN_REGISTRY.yaml",
        tmp_path,
        fail_on_duplicates=True,
        fail_on_unclassified=True,
    )

    issue_codes = {issue["code"] for issue in report["issues"]}
    assert "superseded-source-of-truth" in issue_codes


def test_cli_emits_markdown_and_json(tmp_path: Path) -> None:
    _write(
        tmp_path / "docs" / "EXECUTION_HUB.md",
        """# Execution Hub

## File d'execution

| ID | Repo canonique | Titre | Statut | Portee | Depend | Validation |
| --- | --- | --- | --- | --- | --- | --- |
| `M-001` | `mascarade` | Active lot | `DONE` | `global` | `-` | `pytest -q` |

## Lot en cours
""",
    )
    _write_registry(
        tmp_path,
        [
            {
                "path": "docs/EXECUTION_HUB.md",
                "repo": "mascarade",
                "role": "active",
                "scope": "global",
                "source_of_truth": True,
                "validation": "pytest -q",
                "canonical_ref": "docs/EXECUTION_HUB.md",
                "parser": "execution_hub",
            }
        ],
    )

    markdown_path = tmp_path / "docs" / "TODO_CROSS_REFERENCE.md"
    json_path = tmp_path / "docs" / "TODO_CROSS_REFERENCE.json"
    completed = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            "--repo-root",
            str(tmp_path),
            "--registry",
            "docs/TODO_PLAN_REGISTRY.yaml",
            "--emit-markdown",
            "docs/TODO_CROSS_REFERENCE.md",
            "--emit-json",
            "docs/TODO_CROSS_REFERENCE.json",
            "--fail-on-duplicates",
            "--fail-on-unclassified",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0
    assert markdown_path.exists()
    assert json_path.exists()
