---
description: "Run the fastest relevant stack checks before commit based on changed files, and return a concise go/no-go report."
name: "Pre-Commit Stack Smoke"
argument-hint: "Optional scope override: core | api | web | e2e | finetune | all"
agent: "agent"
tools: [search, read, execute]
---

Run a fast pre-commit validation loop for only the impacted stacks.

Input override:
${input:scope}

## Workflow

1. Detect changed files first.
2. Map paths to impacted stacks.
3. Run only fast smoke checks for those stacks.
4. Return a strict go/no-go summary.

## Path Mapping

- `core/**/*.py` -> core
- `api/src/**/*.ts` -> api
- `web/src/**/*.{ts,tsx}` -> web
- `e2e/**` or `web/e2e/**` -> e2e
- `finetune/**` or `core/mascarade/finetune/**` -> finetune

If no changes detected, run minimal baseline: core + api + web quick checks.

## Quick Commands

Core:
- `cd core && python -m pytest tests/test_router.py -q`
- `cd core && ruff check mascarade/ tests/`

API:
- `cd api && npm test`

Web:
- `cd web && npm test -- --run`

E2E:
- `npm exec --prefix e2e playwright -- test --config e2e/playwright.config.ts tests/api/health.spec.ts --project api`

Finetune:
- `cd core && python -m pytest tests/test_finetune.py -q`

## Output Format

Provide exactly:

1. `Impacted stacks`: list
2. `Executed checks`: one line per command with PASS/FAIL
3. `Blocking failures`: first actionable error per failed command
4. `Next command`: exact command to rerun after fix
5. Final status: `GO` or `NO-GO`

## Rules

- Prefer smallest useful check set.
- Stop early only on hard blockers that invalidate the rest.
- Do not edit files in this prompt run unless user explicitly asks.