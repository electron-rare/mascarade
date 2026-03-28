---
applyTo: core/**/*.py
description: "Use when modifying Python code in core. Enforces async-first patterns and targeted validation."
---

# Core Python Instructions

- Keep async-first code style for I/O.
- Follow existing provider abstractions in core/mascarade/router/providers/.
- Preserve public behavior unless explicitly requested.
- Prefer explicit typing; avoid weakening type contracts.

Validation commands:
- cd core && python -m pytest
- cd core && ruff check mascarade/ tests/
- cd core && mypy mascarade/