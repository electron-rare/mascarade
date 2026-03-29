---
description: "Use when working on finetune pipeline code, dataset curation, alignment methods, or Hugging Face publication in finetune/ and core finetune modules. Enforces security, validation, and release safety checks."
name: "Finetune Pipeline Guardrails"
applyTo: "finetune/**,core/mascarade/finetune/**,core/tests/test_finetune*.py,scripts/qa/qa-finetune.sh"
---

# Finetune Pipeline Instructions

## Scope

Apply these rules for any change touching:
- finetune pipeline code and scripts
- core finetune orchestration and agents
- finetune tests and publication helpers

## Security Guardrails

- Never hardcode secrets, tokens, or credentials.
- Read authentication values from environment variables only.
- Mask sensitive values in logs, manifests, and command output.
- For publication flows, require explicit token presence checks before upload.
- Do not auto-publish model artifacts in background without an explicit user-triggered step.

## Validation Requirements

- Validate all user and CLI inputs at boundaries.
- Fail fast with clear actionable errors when dataset paths, model IDs, or required tools are missing.
- Keep safety checks for unsupported models and invalid alignment method combinations.
- For alignment updates, preserve explicit method handling and deterministic fallback behavior.

## Hugging Face Publication Rules

- Keep publication steps idempotent when possible.
- Require a local artifact integrity check before publish.
- Ensure publish metadata is explicit: model ID, dataset ID, run label, revision context.
- Never silently skip failed upload steps; report precise failure reasons.

## Testing And Verification

Run checks proportional to the touched scope:

- Core finetune tests:
  - cd core && python -m pytest tests/test_finetune.py -q
- Finetune pipeline tests:
  - cd core && python -m pytest tests/test_finetune_pipeline.py -q
- RLVR tests when alignment or rewards change:
  - cd core && python -m pytest tests/test_rlvr.py -q
- Lint on finetune core when Python internals change:
  - cd core && python -m ruff check mascarade/finetune

## Change Discipline

- Keep patches minimal and scoped to the target flow.
- Avoid unrelated refactors during pipeline/security fixes.
- If publication behavior changes, document expected operator impact in PR notes.