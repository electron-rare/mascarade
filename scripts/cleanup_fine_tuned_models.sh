#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
TARGET_ROOT="$ROOT_DIR/fine_tuned_models"
KEEP_CHECKPOINTS=2
CLEAN_LOGS=0
CLEAN_CACHE=0
CLEAN_CHECKPOINTS=1
DRY_RUN=0
ASSUME_YES=0

usage() {
  cat <<'USAGE'
Usage: ./scripts/cleanup_fine_tuned_models.sh [options]

Clean fine_tuned_models artifacts safely (logs, .cache, old checkpoints).

Options:
  --root DIR           Directory to clean (default: fine_tuned_models/)
  --keep N             Keep last N checkpoint-* dirs per parent dir (default: 2)
  --logs               Remove *.log *.tmp *.out *.err under target
  --cache              Remove .cache directories under target
  --all                Enable --logs and --cache
  --no-checkpoints     Skip checkpoint cleanup
  --dry-run            Show what would be deleted only
  --yes                Skip interactive confirmation
  --help               Show this help

Examples:
  ./scripts/cleanup_fine_tuned_models.sh --all --dry-run
  ./scripts/cleanup_fine_tuned_models.sh --keep 3 --cache --logs --yes
USAGE
}

log() { printf '%s\n' "$*"; }
die() { printf 'Error: %s\n' "$*" >&2; exit 2; }

TARGETS=()
declare -A SEEN=()

add_target() {
  local p=$1
  [ -e "$p" ] || return 0
  if [ -n "${SEEN[$p]+x}" ]; then
    return 0
  fi
  SEEN[$p]=1
  TARGETS+=("$p")
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --root)
      [ "$#" -ge 2 ] || die "--root requires a path"
      TARGET_ROOT=$2
      shift 2
      ;;
    --keep)
      [ "$#" -ge 2 ] || die "--keep requires a number"
      KEEP_CHECKPOINTS=$2
      if ! [[ "$KEEP_CHECKPOINTS" =~ ^[0-9]+$ ]]; then
        die "--keep must be a non-negative integer"
      fi
      shift 2
      ;;
    --logs)
      CLEAN_LOGS=1
      shift
      ;;
    --cache)
      CLEAN_CACHE=1
      shift
      ;;
    --all)
      CLEAN_LOGS=1
      CLEAN_CACHE=1
      shift
      ;;
    --no-checkpoints)
      CLEAN_CHECKPOINTS=0
      shift
      ;;
    --dry-run)
      DRY_RUN=1
      shift
      ;;
    --yes)
      ASSUME_YES=1
      shift
      ;;
    --help)
      usage
      exit 0
      ;;
    *)
      die "Unknown option: $1"
      ;;
  esac
done

if [ ! -d "$TARGET_ROOT" ]; then
  die "Root directory does not exist: $TARGET_ROOT"
fi

if [ "$CLEAN_CHECKPOINTS" -eq 1 ]; then
  declare -A PARENTS=()
  while IFS= read -r -d '' ck; do
    parent=$(dirname "$ck")
    PARENTS["$parent"]=1
  done < <(find "$TARGET_ROOT" -type d -name 'checkpoint-*' -print0)

  for parent in "${!PARENTS[@]}"; do
    [ -d "$parent" ] || continue
    mapfile -t sorted < <(
      find "$parent" -maxdepth 1 -mindepth 1 -type d -name 'checkpoint-*' -printf '%f\n' \
      | awk -F 'checkpoint-' -v parent="$parent" '$2 ~ /^[0-9]+$/ { print $2 " " parent "/" $0 }' \
      | sort -n
    )

    total=${#sorted[@]}
    if [ "$KEEP_CHECKPOINTS" -eq 0 ]; then
      remove_limit=$total
    else
      remove_limit=$(( total > KEEP_CHECKPOINTS ? total - KEEP_CHECKPOINTS : 0 ))
    fi

    for ((i = 0; i < remove_limit; i++)); do
      ck_path=${sorted[i]#* }
      add_target "$ck_path"
    done
  done
fi

if [ "$CLEAN_LOGS" -eq 1 ]; then
  while IFS= read -r -d '' f; do
    add_target "$f"
  done < <(find "$TARGET_ROOT" -type f \( -name '*.log' -o -name '*.tmp' -o -name '*.out' -o -name '*.err' \) -print0)
fi

if [ "$CLEAN_CACHE" -eq 1 ]; then
  while IFS= read -r -d '' d; do
    add_target "$d"
  done < <(find "$TARGET_ROOT" -type d -name '.cache' -print0)
fi

if [ "${#TARGETS[@]}" -eq 0 ]; then
  log "Nothing to remove."
  exit 0
fi

log "Cleanup targets:"
for target in "${TARGETS[@]}"; do
  log "  - ${target#$TARGET_ROOT/}"
 done

if [ "$DRY_RUN" -eq 1 ]; then
  log "Dry-run mode: no files were removed."
  exit 0
fi

if [ "$ASSUME_YES" -ne 1 ]; then
  if [ ! -t 0 ]; then
    die "Refusing destructive cleanup without --yes in non-interactive mode"
  fi
  read -r -p "Delete ${#TARGETS[@]} items from $TARGET_ROOT? [y/N] " ans
  case "$ans" in
    y|Y|yes|YES) ;;
    *)
      log "Aborted."
      exit 1
      ;;
  esac
fi

for target in "${TARGETS[@]}"; do
  rm -rf -- "$target"
done

log "Removed ${#TARGETS[@]} item(s)."
