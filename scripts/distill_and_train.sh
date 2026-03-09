#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

TEACHER_ONLY="${TEACHER_ONLY:-0}"
SKIP_TRAIN="${SKIP_TRAIN:-0}"
ARGS=()
TEACHER_ONLY_FLAG_SEEN=0

while (($#)); do
    case "$1" in
        --teacher-only)
            TEACHER_ONLY=1
            TEACHER_ONLY_FLAG_SEEN=1
            ARGS+=("$1")
            shift
            ;;
        --skip-train)
            SKIP_TRAIN=1
            ARGS+=("$1")
            shift
            ;;
        *)
            ARGS+=("$1")
            shift
            ;;
    esac
done

if [ -z "${MASCARADE_API_KEY:-}" ] && [ -f "$ROOT_DIR/.env" ]; then
    MASCARADE_API_KEY="$(
        awk -F= '
            $1 == "MASCARADE_API_KEY" {
                value = substr($0, index($0, "=") + 1)
                gsub(/^"/, "", value)
                gsub(/"$/, "", value)
                print value
                exit
            }
        ' "$ROOT_DIR/.env"
    )"
    export MASCARADE_API_KEY
fi

for VENV in \
    "$ROOT_DIR/finetune/.venv/bin/activate" \
    "$ROOT_DIR/venv_tuning/bin/activate"
do
    if [ -f "$VENV" ]; then
        # shellcheck disable=SC1090
        source "$VENV"
        FOUND_VENV=1
        break
    fi
done

if [ "${FOUND_VENV:-0}" -ne 1 ]; then
    echo "No fine-tuning virtualenv found." >&2
    echo "Run ./scripts/bootstrap_finetune_env.sh first." >&2
    exit 1
fi

if [ "$TEACHER_ONLY" = "1" ] && [ "$TEACHER_ONLY_FLAG_SEEN" != "1" ]; then
    ARGS+=(--teacher-only)
fi

exec python finetune/distill_and_train.py "${ARGS[@]}"
