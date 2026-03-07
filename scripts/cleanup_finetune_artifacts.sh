#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

usage() {
    cat <<'EOF'
Usage: ./scripts/cleanup_finetune_artifacts.sh [options]

Clean generated fine-tuning artifacts, logs, and smoke outputs.

Options:
  --smoke          Remove smoke-labeled run directories and model outputs
  --label LABEL    Remove run directories and legacy model outputs for one run label
  --logs           Remove run log directories and finetune/logs
  --distilled      Remove files under finetune/datasets/distilled/
  --runs           Remove all finetune/runs/* directories
  --models-local   Remove all finetune/models_local/* directories
  --models-cpu     Remove all finetune/models_cpu/* directories
  --path PATH      Remove one additional path (repeatable)
  --dry-run        Print what would be removed without deleting
  --yes            Skip confirmation prompt
  --help           Show this help

Examples:
  ./scripts/cleanup_finetune_artifacts.sh --smoke --logs --dry-run
  ./scripts/cleanup_finetune_artifacts.sh --smoke --distilled --yes
  ./scripts/cleanup_finetune_artifacts.sh --label smoke2 --yes
  ./scripts/cleanup_finetune_artifacts.sh --path finetune/models_cpu/embedded --yes
EOF
}

log() {
    printf '%s\n' "$*"
}

die() {
    printf 'Error: %s\n' "$*" >&2
    exit 2
}

declare -a TARGETS=()
declare -a TARGET_MODES=()
declare -A SEEN=()
declare -a EXTRA_PATHS=()
declare -a LABELS=()
DRY_RUN=0
ASSUME_YES=0

add_target() {
    local target=$1
    local existing
    local -a filtered_targets=()
    if [ ! -e "$target" ]; then
        return 0
    fi
    for existing in "${TARGETS[@]}"; do
        if [[ "$target" == "$existing" || "$target" == "$existing"/* ]]; then
            return 0
        fi
    done
    if [ -n "${SEEN[$target]:-}" ]; then
        return 0
    fi
    for existing in "${TARGETS[@]}"; do
        if [[ "$existing" == "$target"/* ]]; then
            unset 'SEEN[$existing]'
            continue
        fi
        filtered_targets+=("$existing")
    done
    TARGETS=("${filtered_targets[@]}")
    SEEN["$target"]=1
    TARGETS+=("$target")
}

add_glob_targets() {
    local pattern=$1
    local match
    while IFS= read -r match; do
        [ -n "$match" ] || continue
        add_target "$match"
    done < <(compgen -G "$pattern" || true)
}

resolve_extra_path() {
    local raw_path=$1
    if [[ "$raw_path" = /* ]]; then
        printf '%s\n' "$raw_path"
    else
        printf '%s\n' "$ROOT_DIR/$raw_path"
    fi
}

add_label_targets() {
    local label=$1
    [ -n "$label" ] || return 0
    add_glob_targets "$ROOT_DIR/finetune/runs/${label}_*"
    add_glob_targets "$ROOT_DIR/finetune/models_local/*_${label}_*"
    add_glob_targets "$ROOT_DIR/finetune/models_cpu/*_${label}_*"
}

while [ "$#" -gt 0 ]; do
    case "$1" in
        --smoke|--logs|--distilled|--runs|--models-local|--models-cpu)
            TARGET_MODES+=("$1")
            shift
            ;;
        --label)
            [ "$#" -ge 2 ] || die "--label requires an argument"
            LABELS+=("$2")
            shift 2
            ;;
        --path)
            [ "$#" -ge 2 ] || die "--path requires an argument"
            EXTRA_PATHS+=("$(resolve_extra_path "$2")")
            shift 2
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
            die "unknown option: $1"
            ;;
    esac
done

if [ "${#TARGET_MODES[@]}" -eq 0 ] && [ "${#EXTRA_PATHS[@]}" -eq 0 ] && [ "${#LABELS[@]}" -eq 0 ]; then
    usage
    exit 2
fi

for mode in "${TARGET_MODES[@]}"; do
    case "$mode" in
        --smoke)
            add_label_targets "smoke"
            ;;
        --logs)
            add_glob_targets "$ROOT_DIR/finetune/runs/*/logs"
            add_target "$ROOT_DIR/finetune/logs"
            ;;
        --distilled)
            add_glob_targets "$ROOT_DIR/finetune/datasets/distilled/*"
            ;;
        --runs)
            add_glob_targets "$ROOT_DIR/finetune/runs/*"
            ;;
        --models-local)
            add_glob_targets "$ROOT_DIR/finetune/models_local/*"
            ;;
        --models-cpu)
            add_glob_targets "$ROOT_DIR/finetune/models_cpu/*"
            ;;
    esac
done

for label in "${LABELS[@]}"; do
    add_label_targets "$label"
done

for extra_path in "${EXTRA_PATHS[@]}"; do
    add_target "$extra_path"
done

if [ "${#TARGETS[@]}" -eq 0 ]; then
    log "Nothing to remove."
    exit 0
fi

log "Cleanup targets:"
for target in "${TARGETS[@]}"; do
    log "  - ${target#$ROOT_DIR/}"
done

if [ "$DRY_RUN" -eq 1 ]; then
    log "Dry-run only; nothing removed."
    exit 0
fi

if [ "$ASSUME_YES" -ne 1 ]; then
    if [ ! -t 0 ]; then
        die "refusing destructive cleanup without --yes or --dry-run in non-interactive mode"
    fi
    read -r -p "Remove these paths? [y/N] " reply
    case "$reply" in
        y|Y|yes|YES)
            ;;
        *)
            log "Aborted."
            exit 1
            ;;
    esac
fi

for target in "${TARGETS[@]}"; do
    rm -rf -- "$target"
done

log "Removed ${#TARGETS[@]} path(s)."
