#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

. "$ROOT_DIR/scripts/llm_env.sh"

EXECUTE=0
CLEANUP=0
LINK_HOME_CACHE=0
VERBOSE=0

usage() {
  cat <<'EOF'
Usage: ./scripts/migrate_models_to_llm.sh [options]

Consolidate legacy model stores into /ai/llm.

Default mode is dry-run. Use --execute to copy data into /ai/llm.
Use --cleanup only after verifying the migrated copies.

Options:
  --execute    Copy legacy model stores into /ai/llm
  --cleanup    Remove the legacy source directories after a successful copy
  --link-home-cache
               Replace ~/.cache/huggingface/hub with a symlink to /ai/llm/huggingface/hub
  --verbose    Print each copied path
  -h, --help   Show this help
EOF
}

copy_tree() {
  local src="$1"
  local dst="$2"
  mkdir -p "$dst"
  if command -v rsync >/dev/null 2>&1; then
    rsync -a "$src"/ "$dst"/
  else
    cp -a "$src"/. "$dst"/
  fi
}

print_plan() {
  local src="$1"
  local dst="$2"
  printf '[llm-migrate] source=%s target=%s cleanup=%s\n' "$src" "$dst" "$CLEANUP"
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --execute)
      EXECUTE=1
      shift
      ;;
    --cleanup)
      CLEANUP=1
      shift
      ;;
    --link-home-cache)
      LINK_HOME_CACHE=1
      shift
      ;;
    --verbose)
      VERBOSE=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

declare -a SOURCES=(
  "${HOME}/.cache/huggingface/hub|${HUGGINGFACE_HUB_CACHE}"
  "${ROOT_DIR}/finetune/models_cache|${MASCARADE_MODELS_CACHE_DIR}"
  "${ROOT_DIR}/.tmp/hf-models|${MASCARADE_WATCH_MODELS_DIR}"
  "${HOME}/Models/mascarade/apple-llm|${APPLE_LLM_MODEL_ROOT}"
)

for mapping in "${SOURCES[@]}"; do
  src="${mapping%%|*}"
  dst="${mapping##*|}"
  if [ ! -e "$src" ]; then
    continue
  fi
  print_plan "$src" "$dst"
  if [ "$EXECUTE" -ne 1 ]; then
    continue
  fi
  [ "$VERBOSE" -eq 1 ] && echo "[llm-migrate] copying $src -> $dst"
  copy_tree "$src" "$dst"
  if [ "$CLEANUP" -eq 1 ]; then
    rm -rf "$src"
  fi
done

if [ "$EXECUTE" -eq 1 ] && [ "$LINK_HOME_CACHE" -eq 1 ]; then
  mkdir -p "${HOME}/.cache/huggingface"
  rm -rf "${HOME}/.cache/huggingface/hub"
  ln -s "${HUGGINGFACE_HUB_CACHE}" "${HOME}/.cache/huggingface/hub"
fi

printf '[llm-migrate] llm_root=%s execute=%s cleanup=%s link_home_cache=%s\n' "$MASCARADE_LLM_DIR" "$EXECUTE" "$CLEANUP" "$LINK_HOME_CACHE"
