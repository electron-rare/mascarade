#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/lib/control_plane_cli.sh
source "$SCRIPT_DIR/lib/control_plane_cli.sh"

ROOT="$(cp_project_root)"
LOG_DIR="${LOG_DIR:-$(cp_default_log_dir)}"
CONTROL_PLANE_URL="${CONTROL_PLANE_URL:-http://127.0.0.1:3000}"
CONTROL_PLANE_SHARED_TOKEN="${CONTROL_PLANE_SHARED_TOKEN:-}"
VERBOSE="${VERBOSE:-0}"
YES="${YES:-0}"
LIMIT="${LIMIT:-50}"
LINES="${LINES:-200}"
RAW="${RAW:-0}"
ALL="${ALL:-0}"
FILE="${FILE:-}"
PATTERN="${PATTERN:-}"
SERVICE="${SERVICE:-mascarade-control-plane.service}"

usage() {
  cat <<'EOF'
Usage:
  scripts/log_manager.sh [options] <command>

Commands:
  list       List available log files
  tail       Tail a log file
  grep       Search inside a log file
  summary    Summarize a log file
  events     Show recent control-plane events
  journal    Tail journald for a control-plane service
  delete     Delete one or more log files
  menu       Interactive menu

Options:
  --url URL     Control-plane base URL
  --token TOKEN Shared auth token
  --dir PATH    Log directory (default: api/logs)
  --file PATH   Log file to operate on
  --pattern RE  Pattern for grep
  --service U   systemd unit for journal mode (default: mascarade-control-plane.service)
  --limit N     Limit for remote events (default: 50)
  --lines N     Tail lines (default: 200)
  --all         Operate on all files for delete
  --raw         Print raw JSON for remote events
  --verbose     Log actions
  --yes         Non-interactive confirmation for delete actions
  --help        Show this help
EOF
}

parse_args() {
  COMMAND=""
  while (($# > 0)); do
    case "$1" in
      --url)
        CONTROL_PLANE_URL="${2:?missing value for --url}"
        shift 2
        ;;
      --token)
        CONTROL_PLANE_SHARED_TOKEN="${2:?missing value for --token}"
        shift 2
        ;;
      --dir)
        LOG_DIR="${2:?missing value for --dir}"
        shift 2
        ;;
      --file)
        FILE="${2:?missing value for --file}"
        shift 2
        ;;
      --pattern)
        PATTERN="${2:?missing value for --pattern}"
        shift 2
        ;;
      --service)
        SERVICE="${2:?missing value for --service}"
        shift 2
        ;;
      --limit)
        LIMIT="${2:?missing value for --limit}"
        shift 2
        ;;
      --lines)
        LINES="${2:?missing value for --lines}"
        shift 2
        ;;
      --all)
        ALL=1
        shift
        ;;
      --raw)
        RAW=1
        shift
        ;;
      --verbose)
        VERBOSE=1
        shift
        ;;
      --yes)
        YES=1
        shift
        ;;
      --help|-h)
        usage
        exit 0
        ;;
      --)
        shift
        break
        ;;
      -*)
        cp_die "Unknown option: $1"
        ;;
      *)
        COMMAND="$1"
        shift
        break
        ;;
    esac
  done
}

log_files() {
  if [[ -d "$LOG_DIR" ]]; then
    find "$LOG_DIR" -maxdepth 1 -type f \( -name '*.log' -o -name '*.jsonl' -o -name '*.log.*' \) | sort
  fi
}

latest_log_file() {
  python3 - "$LOG_DIR" <<'PY'
from pathlib import Path
import sys

log_dir = Path(sys.argv[1])
if not log_dir.exists():
    print("")
    raise SystemExit(0)

files = sorted(
    [
        path
        for path in log_dir.iterdir()
        if path.is_file() and (
            path.name.endswith(".log")
            or ".log." in path.name
            or path.name.endswith(".jsonl")
        )
    ],
    key=lambda path: path.stat().st_mtime,
)
print(files[-1] if files else "")
PY
}

pick_log_file() {
  local fallback="${1:-}"
  if [[ -n "$FILE" ]]; then
    printf '%s\n' "$FILE"
    return
  fi
  if [[ -n "$fallback" ]]; then
    printf '%s\n' "$fallback"
    return
  fi
  latest_log_file
}

render_list() {
  local files=()
  while IFS= read -r file; do
    [[ -n "$file" ]] && files+=("$file")
  done < <(log_files)

  if (( ${#files[@]} == 0 )); then
    printf 'No log files found in %s\n' "$LOG_DIR"
    return 0
  fi

  printf '%-4s %-10s %-19s %s\n' "#" "size" "modified" "file"
  printf '%s\n' "-----------------------------------------------------------------------"
  local idx=1
  for file in "${files[@]}"; do
    local size modified
    size="$(du -h "$file" | awk '{print $1}')"
    modified="$(stat -f '%Sm' -t '%Y-%m-%d %H:%M:%S' "$file" 2>/dev/null || stat -c '%y' "$file" 2>/dev/null | cut -d. -f1)"
    printf '%-4d %-10s %-19s %s\n' "$idx" "$size" "$modified" "$file"
    idx=$((idx + 1))
  done
}

render_tail() {
  local file="$1"
  tail -n "$LINES" "$file"
}

render_grep() {
  local file="$1"
  local pattern="$2"
  grep -n -i -- "$pattern" "$file" || true
}

render_summary() {
  local file="$1"
  python3 - "$file" <<'PY'
import json
import sys
from collections import Counter
from pathlib import Path

path = Path(sys.argv[1])
if not path.exists():
    print(f"missing log file: {path}", file=sys.stderr)
    raise SystemExit(1)

level_counts = Counter()
event_counts = Counter()
total = 0
raw_lines = 0
last_ts = None

with path.open("r", encoding="utf-8", errors="replace") as handle:
    for line in handle:
        if not line.strip():
            continue
        total += 1
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            raw_lines += 1
            continue

        level_counts[entry.get("level", "unknown")] += 1
        event_counts[entry.get("event_type", "unknown")] += 1
        last_ts = entry.get("ts") or last_ts

print(f"file: {path}")
print(f"lines: {total}")
print(f"raw_lines: {raw_lines}")
print(f"last_ts: {last_ts or '-'}")
print("levels:")
for level, count in sorted(level_counts.items()):
    print(f"  {level}: {count}")
print("top_events:")
for event, count in event_counts.most_common(10):
    print(f"  {event}: {count}")
PY
}

render_events() {
  local events_json
  events_json="$(cp_http GET "/api/cluster/events?limit=${LIMIT}")"
  if [[ "$RAW" == "1" ]]; then
    printf '%s\n' "$events_json" | cp_json_pretty
    return
  fi

  python3 - "$events_json" <<'PY'
import json
import sys

data = json.loads(sys.argv[1])
events = data.get("events", [])
if not events:
    print("No recent control-plane events.")
    raise SystemExit(0)

header = f"{'ts':<24} {'level':<6} {'event_type':<28} {'project':<14} {'node':<12} {'request':<16} {'lease':<16}"
print(header)
print("-" * len(header))
for event in events:
    payload = event.get("data", {})
    print(
        f"{event.get('ts', '-'):24.24} "
        f"{event.get('level', '-'):6.6} "
        f"{event.get('event_type', '-'):28.28} "
        f"{(payload.get('project_id') or '-'):14.14} "
        f"{(payload.get('node_id') or '-'):12.12} "
        f"{(payload.get('request_id') or '-'):16.16} "
        f"{(payload.get('lease_id') or '-'):16.16}"
    )
PY
}

render_journal() {
  if ! command -v journalctl >/dev/null 2>&1; then
    cp_die "journalctl is required for journal mode"
  fi
  journalctl -u "$SERVICE" -n "$LINES" --no-pager
}

delete_files() {
  local files=()
  if [[ -n "$FILE" ]]; then
    files+=("$FILE")
  elif [[ "$ALL" == "1" ]]; then
    while IFS= read -r file; do
      [[ -n "$file" ]] && files+=("$file")
    done < <(log_files)
  else
    local candidates=()
    while IFS= read -r file; do
      [[ -n "$file" ]] && candidates+=("$file")
    done < <(log_files)

    if (( ${#candidates[@]} == 0 )); then
      printf 'No log files found in %s\n' "$LOG_DIR"
      return 0
    fi

    if cp_is_tty; then
      local selected
      selected="$(cp_choose "Select a log file to delete" "${candidates[@]}")"
      files+=("$selected")
    else
      cp_die "Specify --file or --all for delete in non-interactive mode"
    fi
  fi

  if (( ${#files[@]} == 0 )); then
    printf 'No log files selected.\n'
    return 0
  fi

  printf 'Selected files:\n'
  local file
  for file in "${files[@]}"; do
    python3 - "$LOG_DIR" "$file" <<'PY'
from pathlib import Path
import sys

log_dir = Path(sys.argv[1]).resolve()
target = Path(sys.argv[2]).resolve()
if log_dir not in target.parents and target != log_dir:
    print(f"ERROR: refusing to manage file outside log dir: {target}", file=sys.stderr)
    raise SystemExit(1)
PY
    printf '  %s\n' "$file"
  done

  cp_confirm "Delete the selected log files?" || return 1

  for file in "${files[@]}"; do
    if [[ -f "$file" ]]; then
      rm -f -- "$file"
      cp_log INFO "deleted_log_file $file"
    fi
  done

  printf 'Deletion complete.\n'
}

menu_loop() {
  while true; do
    local choice
    choice="$(cp_choose "Mascarade log manager" list tail grep summary events journal delete quit)"
    case "$choice" in
      list) render_list ;;
      tail)
        local file
        file="$(pick_log_file "$(latest_log_file)")"
        [[ -z "$file" ]] && cp_die "No log file available"
        render_tail "$file"
        ;;
      grep)
        local file pattern
        file="$(pick_log_file "$(latest_log_file)")"
        [[ -z "$file" ]] && cp_die "No log file available"
        if [[ -n "$PATTERN" ]]; then
          pattern="$PATTERN"
        elif cp_is_tty; then
          read -r -p "Pattern: " pattern
        else
          cp_die "Missing --pattern in non-interactive mode"
        fi
        render_grep "$file" "$pattern"
        ;;
      summary)
        local file
        file="$(pick_log_file "$(latest_log_file)")"
        [[ -z "$file" ]] && cp_die "No log file available"
        render_summary "$file"
        ;;
      events) render_events ;;
      journal) render_journal ;;
      delete) delete_files ;;
      quit) return 0 ;;
    esac

    if cp_is_tty; then
      read -r -p "Press Enter to continue..." _
    fi
  done
}

main() {
  cp_require_tools curl python3 du stat tail grep rm find awk
  parse_args "$@"

  if [[ -z "${COMMAND:-}" ]]; then
    if [[ "$YES" == "1" || ! cp_is_tty ]]; then
      COMMAND="summary"
    else
      COMMAND="menu"
    fi
  fi

  case "$COMMAND" in
    list) render_list ;;
    tail)
      local_file=""
      local_file="$(pick_log_file "$(latest_log_file)")"
      [[ -z "$local_file" ]] && cp_die "No log file available"
      render_tail "$local_file"
      ;;
    grep)
      local_file=""
      local_file="$(pick_log_file "$(latest_log_file)")"
      [[ -z "$local_file" ]] && cp_die "No log file available"
      if [[ -z "$PATTERN" ]]; then
        cp_die "Missing --pattern for grep"
      fi
      render_grep "$local_file" "$PATTERN"
      ;;
    summary)
      local_file=""
      local_file="$(pick_log_file "$(latest_log_file)")"
      [[ -z "$local_file" ]] && cp_die "No log file available"
      render_summary "$local_file"
      ;;
    events) render_events ;;
    journal) render_journal ;;
    delete) delete_files ;;
    menu) menu_loop ;;
    *)
      usage
      exit 2
      ;;
  esac
}

main "$@"
