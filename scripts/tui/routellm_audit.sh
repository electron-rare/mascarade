#!/usr/bin/env bash
set -euo pipefail

SCRIPT_NAME="$(basename "$0")"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

CMD="run"
TARGET_DIR="$REPO_ROOT"
OPS_DIR="$REPO_ROOT/.ops/routellm-audit"
VERBOSE=0
ASSUME_YES=0
AUTO_PURGE=0
STRICT_MODE=0

if [[ "${NO_COLOR:-}" != "" ]]; then
  C_RESET=""
  C_ACCENT=""
  C_WARN=""
  C_ERR=""
else
  C_RESET=$'\033[0m'
  C_ACCENT=$'\033[38;5;220m'
  C_WARN=$'\033[38;5;214m'
  C_ERR=$'\033[38;5;196m'
fi

usage() {
  cat <<EOF
Usage: $SCRIPT_NAME <run|audit|purge> [options]

Commands:
  run       Audit then optionally purge logs (interactive confirm)
  audit     Generate report + raw logs only
  purge     Remove audit artifacts directory

Options:
  --repo-dir <path>   Repository root to scan (default: $REPO_ROOT)
  --ops-dir <path>    Artifacts directory (default: $OPS_DIR)
  --purge             Auto-purge after audit (run command)
  --strict            Disable compatibility allowlist filtering
  --yes               Non-interactive approval for destructive actions
  --verbose           Print extra execution details
  -h, --help          Show this help
EOF
}

log() {
  printf "%s\n" "$*"
}

info() {
  printf "%s%s%s\n" "$C_ACCENT" "$*" "$C_RESET"
}

warn() {
  printf "%s%s%s\n" "$C_WARN" "$*" "$C_RESET" >&2
}

err() {
  printf "%s%s%s\n" "$C_ERR" "$*" "$C_RESET" >&2
}

debug() {
  if [[ "$VERBOSE" -eq 1 ]]; then
    log "[debug] $*"
  fi
}

is_interactive() {
  [[ -t 0 && -t 1 ]]
}

has_gum() {
  command -v gum >/dev/null 2>&1
}

confirm_action() {
  local prompt="$1"
  if [[ "$ASSUME_YES" -eq 1 ]]; then
    return 0
  fi
  if is_interactive && has_gum; then
    gum confirm "$prompt"
    return $?
  fi
  if is_interactive; then
    printf "%s [y/N]: " "$prompt"
    local answer=""
    read -r answer
    [[ "${answer,,}" == "y" || "${answer,,}" == "yes" ]]
    return $?
  fi
  warn "Non-interactive mode: confirmation required. Re-run with --yes."
  return 1
}

parse_args() {
  local positional=()
  while [[ $# -gt 0 ]]; do
    case "$1" in
      run|audit|purge)
        CMD="$1"
        shift
        ;;
      --repo-dir)
        [[ $# -ge 2 ]] || { err "--repo-dir requires a value"; exit 2; }
        TARGET_DIR="$2"
        shift 2
        ;;
      --ops-dir)
        [[ $# -ge 2 ]] || { err "--ops-dir requires a value"; exit 2; }
        OPS_DIR="$2"
        shift 2
        ;;
      --purge)
        AUTO_PURGE=1
        shift
        ;;
      --strict)
        STRICT_MODE=1
        shift
        ;;
      --yes)
        ASSUME_YES=1
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
        positional+=("$1")
        shift
        ;;
    esac
  done

  if [[ "${#positional[@]}" -gt 0 ]]; then
    err "Unexpected arguments: ${positional[*]}"
    usage
    exit 2
  fi
}

run_audit() {
  mkdir -p "$OPS_DIR"
  local ts
  ts="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"

  local raw_all_log="$OPS_DIR/legacy_strategy_hits.all.log"
  local raw_log="$OPS_DIR/legacy_strategy_hits.log"
  local ignored_log="$OPS_DIR/legacy_strategy_hits.ignored.log"
  local report="$OPS_DIR/report.md"

  info "RouteLLM audit started ($ts)"
  debug "target_dir=$TARGET_DIR"
  debug "ops_dir=$OPS_DIR"
  debug "strict_mode=$STRICT_MODE"

  local rg_pattern
  rg_pattern='strategy[^\\n]{0,40}(best|cheapest|fastest)|\"strategy\"\\s*:\\s*\"(best|cheapest|fastest)\"'

  (
    cd "$TARGET_DIR"
    rg -n --hidden --glob '!**/.git/**' --glob '!**/node_modules/**' --glob '!**/.ops/**' --glob '!**/api/public/assets/**' \
      -e "$rg_pattern" \
      README.md docs core api web 2>/dev/null || true
  ) > "$raw_all_log"

  : > "$ignored_log"
  if [[ "$STRICT_MODE" -eq 1 ]]; then
    cp "$raw_all_log" "$raw_log"
  else
    awk '
      /^core\/mascarade\/orchestrator\/engine\.py:.*strategy_raw == "(cheapest|fastest|best)"/ {
        print > ignored_file
        next
      }
      /^core\/mascarade\/load_balancer\/balancer\.py:.*fastest_response/ {
        print > ignored_file
        next
      }
      { print }
    ' ignored_file="$ignored_log" "$raw_all_log" > "$raw_log"
  fi

  local hits files raw_hits ignored_hits
  raw_hits="$(wc -l < "$raw_all_log" | tr -d ' ')"
  hits="$(wc -l < "$raw_log" | tr -d ' ')"
  ignored_hits="$(wc -l < "$ignored_log" | tr -d ' ')"
  files="$(awk -F: 'NF>1{print $1}' "$raw_log" | sort -u | wc -l | tr -d ' ')"

  {
    echo "# RouteLLM Legacy Strategy Audit"
    echo
    echo "- date_utc: $ts"
    echo "- target_dir: $TARGET_DIR"
    echo "- raw_hits: $raw_hits"
    echo "- ignored_hits: $ignored_hits"
    echo "- actionable_hits: $hits"
    echo "- actionable_files: $files"
    echo "- strict_mode: $STRICT_MODE"
    echo
    if [[ "$STRICT_MODE" -eq 0 ]]; then
      echo "## Compatibility Allowlist"
      echo
      echo "- core/mascarade/orchestrator/engine.py legacy strategy mapping kept intentionally for backward compatibility"
      echo "- core/mascarade/load_balancer/balancer.py fastest_response wording is not a RouteLLM strategy hit"
      echo
    fi
    echo
    echo "## Hotspots (top 20 files)"
    awk -F: 'NF>1{print $1}' "$raw_log" | sort | uniq -c | sort -nr | head -20 | sed 's/^/ - /'
    echo
    if [[ "$ignored_hits" -gt 0 ]]; then
      echo "## Ignored Matches"
      sed -n '1,80p' "$ignored_log"
      echo
    fi
    echo "## Actionable Matches (first 200)"
    sed -n '1,200p' "$raw_log"
  } > "$report"

  info "Audit complete"
  log "report: $report"
  log "raw:    $raw_log"
}

purge_ops() {
  if [[ ! -d "$OPS_DIR" ]]; then
    warn "Nothing to purge: $OPS_DIR"
    return 0
  fi
  if ! confirm_action "Delete audit artifacts at $OPS_DIR ?"; then
    warn "Purge cancelled."
    return 1
  fi
  rm -rf "$OPS_DIR"
  info "Purged: $OPS_DIR"
}

main() {
  parse_args "$@"
  case "$CMD" in
    audit)
      run_audit
      ;;
    purge)
      purge_ops
      ;;
    run)
      run_audit
      if [[ "$AUTO_PURGE" -eq 1 ]]; then
        purge_ops || true
      elif confirm_action "Purge raw logs now?"; then
        purge_ops || true
      else
        warn "Logs kept under $OPS_DIR"
      fi
      ;;
    *)
      err "Unknown command: $CMD"
      usage
      exit 2
      ;;
  esac
}

main "$@"
