#!/usr/bin/env python3
"""QA validator for scripts/tui/todo_manager.py active TODO registry.

Checks:
- Active IDs match expected source-of-truth list.
- Priority per ID matches expected values.
- Required references exist on disk (file or directory).
- Required dependency/fork metadata exists for selected IDs.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
TODO_MANAGER_PATH = REPO_ROOT / "scripts" / "tui" / "todo_manager.py"

EXPECTED = {
    "P1": {"priority": "CRITIQUE"},
    "F25": {"priority": "HAUTE"},
    "F3": {"priority": "HAUTE"},
    "F6": {"priority": "HAUTE"},
    "F7": {"priority": "HAUTE"},
    "F8": {"priority": "HAUTE"},
    "F9": {"priority": "HAUTE"},
    "I1": {"priority": "HAUTE"},
    "F23": {"priority": "MOYENNE"},
    "F29": {"priority": "MOYENNE"},
    "I8": {"priority": "MOYENNE"},
    "I9": {"priority": "MOYENNE"},
    "F12": {"priority": "FAIBLE"},
    "F13": {"priority": "FAIBLE"},
    "F14": {"priority": "FAIBLE"},
    "F20": {"priority": "FAIBLE"},
    "I11": {"priority": "FAIBLE"},
}

REQUIRED_METADATA = {
    "P1": {
        "dependencies": {"checkpoint_resume", "apple_coreml", "lot_priority_models"},
        "refs": {"scripts/run_next_useful_lot.sh"},
    },
    "F23": {
        "dependencies": {"gcc-arm-none-eabi", "ngspice", "rejection_sampling.py"},
        "refs": {"finetune/rejection_sampling.py"},
    },
    "F12": {
        "forks": {"jochemkroon/KiC-AI", "mixelpixx/KiCAD-MCP-Server"},
    },
    "F3": {
        "forks": {"electron-rare/mascarade"},
    },
}


def load_todos():
    spec = importlib.util.spec_from_file_location("todo_manager", TODO_MANAGER_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load module from {TODO_MANAGER_PATH}")
    mod = importlib.util.module_from_spec(spec)
    # Required for Python 3.14 dataclass internals during dynamic module loading.
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod.ALL_TODOS


def fail(msg: str) -> None:
    print(f"[FAIL] {msg}")
    raise SystemExit(1)


def main() -> int:
    if not TODO_MANAGER_PATH.exists():
        fail(f"Missing file: {TODO_MANAGER_PATH}")

    todos = load_todos()
    by_id = {item.id: item for item in todos}

    actual_ids = set(by_id.keys())
    expected_ids = set(EXPECTED.keys())

    missing = sorted(expected_ids - actual_ids)
    extra = sorted(actual_ids - expected_ids)

    if missing:
        fail(f"Missing TODO IDs: {missing}")
    if extra:
        fail(f"Unexpected TODO IDs in active registry: {extra}")

    for todo_id, expected in EXPECTED.items():
        item = by_id[todo_id]
        if item.priority != expected["priority"]:
            fail(
                f"Priority mismatch for {todo_id}: got={item.priority}, expected={expected['priority']}"
            )

    for todo_id, rule in REQUIRED_METADATA.items():
        item = by_id[todo_id]
        deps = set(item.dependencies)
        refs = set(item.refs)
        forks = set(item.github_forks)

        if "dependencies" in rule and not set(rule["dependencies"]).issubset(deps):
            fail(
                f"Dependencies missing for {todo_id}: expected subset {sorted(rule['dependencies'])}, got {sorted(deps)}"
            )

        if "refs" in rule and not set(rule["refs"]).issubset(refs):
            fail(f"Refs missing for {todo_id}: expected subset {sorted(rule['refs'])}, got {sorted(refs)}")

        if "forks" in rule and not set(rule["forks"]).issubset(forks):
            fail(
                f"Fork metadata missing for {todo_id}: expected subset {sorted(rule['forks'])}, got {sorted(forks)}"
            )

    missing_refs: list[str] = []
    for item in todos:
        for ref in item.refs:
            path = REPO_ROOT / ref
            if not path.exists():
                missing_refs.append(f"{item.id}:{ref}")

    if missing_refs:
        print("[WARN] Missing TODO refs (non-blocking):")
        for miss in missing_refs:
            print(f"  - {miss}")

    print(f"[OK] Active TODO registry valid ({len(todos)} items)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
