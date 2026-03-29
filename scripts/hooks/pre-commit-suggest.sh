#!/usr/bin/env bash
set -euo pipefail

# Non-blocking suggestion hook: reminds the user to run the fast pre-commit prompt when code changes are detected.
if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  exit 0
fi

changed_count="$(git diff --name-only | wc -l | tr -d ' ')"
if [[ "${changed_count}" == "0" ]]; then
  exit 0
fi

cat <<'JSON'
{
  "continue": true,
  "systemMessage": "Suggestion pre-commit: lancez /Pre-Commit Stack Smoke pour valider rapidement les stacks impactées avant commit."
}
JSON
