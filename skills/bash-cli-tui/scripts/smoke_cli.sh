#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 <script-path> [extra-args...]" >&2
  exit 2
fi

TARGET="$1"
shift || true

if [[ ! -x "$TARGET" ]]; then
  echo "[ERROR] target not executable: $TARGET" >&2
  exit 2
fi

echo "[1/4] help"
"$TARGET" --help "$@" >/dev/null

echo "[2/4] invalid arg returns non-zero"
if "$TARGET" --definitely-invalid-flag "$@" >/dev/null 2>&1; then
  echo "[ERROR] invalid flag unexpectedly succeeded" >&2
  exit 1
fi

echo "[3/4] non-interactive run (best effort)"
if "$TARGET" --yes "$@" >/dev/null 2>&1; then
  echo "[OK] --yes path succeeded"
else
  echo "[WARN] --yes path failed (check script-specific requirements)"
fi

echo "[4/4] verbose path (best effort)"
if "$TARGET" --verbose --yes "$@" >/dev/null 2>&1; then
  echo "[OK] --verbose path succeeded"
else
  echo "[WARN] --verbose path failed (check script-specific requirements)"
fi

echo "Smoke checks finished."
