---
description: "Run only the relevant stack checks based on modified files (core/api/web/finetune), then return a concise pass/fail report with failing commands and next fixes."
name: "Run Stack Checks"
argument-hint: "Optional scope hint, for example: core router only, api routes only, web admin page, finetune pipeline"
agent: "agent"
tools: [search, read, execute]
---

Detect changed files first, then execute only the minimum relevant verification commands.

Input hint from user:
${input:scope}

Workflow:

1. Identify changed files in the workspace.
2. Map changed paths to stacks:
- core/**/*.py -> Python core checks
- api/src/**/*.ts -> API checks
- web/src/**/*.{ts,tsx} -> Web checks
- finetune/** or core/mascarade/finetune/** -> Finetune checks
3. Execute only relevant commands (skip unrelated stacks).
4. Return a compact report with:
- executed commands
- pass/fail per command
- first actionable failure cause
- exact next command to rerun after fix

Command set:

Core:
- cd core && python -m pytest -k <pattern>
- cd core && ruff check mascarade/ tests/

API:
- cd api && npm run build
- cd api && npm test

Web:
- cd web && npm run build
- cd web && npm test -- --run

Finetune:
- cd core && python -m pytest tests/test_finetune.py -q
- cd core && python -m pytest tests/test_finetune_pipeline.py -q
- cd core && python -m pytest tests/test_rlvr.py -q

Rules:

- Prefer fastest relevant subset first.
- Stop only on hard failure that blocks all next checks.
- If dependencies are missing, report it clearly and continue with checks that can still run.
- Do not edit files in this prompt run unless explicitly asked.