#!/usr/bin/env bash
set -euo pipefail

# Guard task closure on frontend changes if validation has not passed.
# Input contract: JSON payload on stdin for hook events.
PAYLOAD="$(cat || true)"

# Only gate task completion call.
if ! echo "$PAYLOAD" | grep -q '"toolName"[[:space:]]*:[[:space:]]*"task_complete"'; then
  exit 0
fi

# Only gate if frontend files are changed.
if ! git status --porcelain 2>/dev/null | grep -E ' web/src/|web/package.json|web/tsconfig|web/vite' >/dev/null; then
  exit 0
fi

# Run required frontend checks quietly.
if (cd web && npm run build >/tmp/frontend_guard_build.log 2>&1 && npm test -- --run >/tmp/frontend_guard_test.log 2>&1); then
  # Explicit allow decision for PreToolUse hook.
  cat <<'JSON'
{
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "permissionDecision": "allow",
    "permissionDecisionReason": "Frontend validation passed (build + tests)."
  }
}
JSON
  exit 0
fi

cat <<'JSON'
{
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "permissionDecision": "deny",
    "permissionDecisionReason": "Frontend validation failed. Run: cd web && npm run build && npm test -- --run"
  }
}
JSON
exit 2
