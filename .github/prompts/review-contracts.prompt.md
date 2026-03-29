---
description: "Review api ↔ core contract changes with the dedicated cross-stack reviewer and return actionable findings before merge."
name: "Review Contracts"
argument-hint: "Optional scope: all | auth | rag | openburo | agents | providers"
agent: "api-core-contract-reviewer"
tools: [search, read]
---

Run a focused cross-stack contract review for `api/` ↔ `core/`.

Input:
${input:scope}

## Workflow

1. Inspect changed files first.
2. Prioritize paths in:
- `api/src/routes/**`
- `core/mascarade/routers/**`
- auth and provider boundaries
3. Review contract compatibility:
- endpoint path/method parity
- request/response schema consistency
- auth and error mapping behavior
4. Return findings ordered by severity.

## Output Format

1. `Findings` (high/medium/low)
- file
- mismatch
- impact
- minimal fix direction

2. `Contract Risks`
- backward compatibility concerns
- missing tests to lock behavior

3. `Verdict`
- ready | needs-fixes | blocked

## Rules

- Do not suggest broad rewrites.
- Keep recommendations minimal and contract-safe.
- If no findings, explicitly state that no regressions were found and list residual test gaps.