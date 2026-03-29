---
description: "Validate frontend and API Playwright tests quickly before commit, with focused rerun commands and failure triage."
name: "Playwright Test Validation"
argument-hint: "Target optionnel: api | web | spec path (ex: tests/api/rag.spec.ts)"
agent: "playwright-qa-cicd"
tools: [search, read, execute]
---

Run a fast Playwright validation workflow on the requested scope.

Input:
${input:target}

## Workflow

1. Resolve target:
- if `api` -> run `tests/api/**` with project `api`
- if `web` -> run `tests/web/**` with project `web`
- if spec path provided -> run that spec only with matching project
- if empty -> run `tests/api/health.spec.ts` then `tests/web/navigation.spec.ts`

2. Execute from repo root using config-aware command:

```bash
npm exec --prefix e2e playwright -- test --config e2e/playwright.config.ts <target> --project <api|web>
```

3. If failure:
- classify root cause: `config`, `mock`, `selector`, `contract`, `regression`
- output one exact rerun command and one minimal fix direction

## Output Format

- `Target`
- `Executed command(s)`
- `Result`: PASS/FAIL
- `First failing test` (if any)
- `Root cause category`
- `Next rerun command`
- `Minimal fix suggestion`

## Rules

- Keep output concise and actionable.
- Do not modify files unless explicitly requested.
- Prefer deterministic commands that work from monorepo root.
