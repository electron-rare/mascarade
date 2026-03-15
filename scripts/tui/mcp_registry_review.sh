#!/usr/bin/env bash
set -euo pipefail

SCRIPT_NAME="$(basename "$0")"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

CMD="run"
REPO_DIR="$REPO_ROOT"
OPS_DIR="$REPO_ROOT/.ops/registry-first"
INVENTORY_FILE="$REPO_ROOT/scripts/data/mcp_registry_inventory.json"
CONFIG_FILE=""
VERBOSE=0
ASSUME_YES=0
AUTO_PURGE_RAW=0

if [[ -n "${NO_COLOR:-}" ]]; then
  C_RESET=""
  C_ACCENT=""
  C_WARN=""
  C_ERR=""
else
  C_RESET=$'\033[0m'
  C_ACCENT=$'\033[38;5;117m'
  C_WARN=$'\033[38;5;214m'
  C_ERR=$'\033[38;5;196m'
fi

usage() {
  cat <<EOF
Usage: $SCRIPT_NAME <run|audit|purge-raw|purge> [options]

Commands:
  run         Review config, write report, then optionally purge raw artifacts
  audit       Review config and keep raw artifacts
  purge-raw   Delete raw artifacts but keep report.md when present
  purge       Delete the full ops directory

Options:
  --config <path>      MCP config file to review
  --repo-dir <path>    Repository root used for drift checks (default: $REPO_DIR)
  --ops-dir <path>     Review artifacts directory (default: $OPS_DIR)
  --inventory <path>   Inventory JSON (default: $INVENTORY_FILE)
  --purge-raw          Auto-purge raw artifacts after review (run command)
  --yes                Non-interactive confirmation for destructive steps
  --verbose            Print extra execution details
  -h, --help           Show this help
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
    local answer=""
    printf "%s [y/N]: " "$prompt"
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
      run|audit|purge-raw|purge)
        CMD="$1"
        shift
        ;;
      --config)
        [[ $# -ge 2 ]] || { err "--config requires a value"; exit 2; }
        CONFIG_FILE="$2"
        shift 2
        ;;
      --repo-dir)
        [[ $# -ge 2 ]] || { err "--repo-dir requires a value"; exit 2; }
        REPO_DIR="$2"
        shift 2
        ;;
      --ops-dir)
        [[ $# -ge 2 ]] || { err "--ops-dir requires a value"; exit 2; }
        OPS_DIR="$2"
        shift 2
        ;;
      --inventory)
        [[ $# -ge 2 ]] || { err "--inventory requires a value"; exit 2; }
        INVENTORY_FILE="$2"
        shift 2
        ;;
      --purge-raw)
        AUTO_PURGE_RAW=1
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

pick_default_config() {
  local candidates=(
    "$HOME/.codex/config.toml"
    "$HOME/.claude/settings.json"
    "$HOME/Library/Application Support/Claude/claude_desktop_config.json"
    "$HOME/.config/Code/User/globalStorage/saoudrizwan.claude-dev/settings/cline_mcp_settings.json"
    "$HOME/.cursor/mcp.json"
    "$HOME/.vscode/mcp.json"
    "$REPO_DIR/.vscode/mcp.json"
  )
  local found=()
  local candidate=""
  for candidate in "${candidates[@]}"; do
    if [[ -f "$candidate" ]]; then
      found+=("$candidate")
    fi
  done

  if [[ "${#found[@]}" -eq 0 ]]; then
    err "No known MCP config file found. Use --config <path>."
    exit 1
  fi

  if [[ "${#found[@]}" -gt 1 ]]; then
    warn "Multiple config files found; using ${found[0]}"
    debug "found_configs=${found[*]}"
  fi
  CONFIG_FILE="${found[0]}"
}

run_review() {
  [[ -f "$INVENTORY_FILE" ]] || { err "Inventory file not found: $INVENTORY_FILE"; exit 1; }
  if [[ -z "$CONFIG_FILE" ]]; then
    pick_default_config
  fi
  [[ -f "$CONFIG_FILE" ]] || { err "Config file not found: $CONFIG_FILE"; exit 1; }

  mkdir -p "$OPS_DIR"
  local ts
  ts="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"

  local execution_log="$OPS_DIR/execution.log"
  local raw_json="$OPS_DIR/review.raw.json"
  local raw_tsv="$OPS_DIR/review.raw.tsv"
  local report="$OPS_DIR/report.md"

  : > "$execution_log"
  {
    echo "date_utc=$ts"
    echo "cmd=$CMD"
    echo "repo_dir=$REPO_DIR"
    echo "config_file=$CONFIG_FILE"
    echo "inventory_file=$INVENTORY_FILE"
  } >> "$execution_log"

  info "MCP registry review started ($ts)"
  debug "config_file=$CONFIG_FILE"
  debug "repo_dir=$REPO_DIR"

  python3 - "$INVENTORY_FILE" "$CONFIG_FILE" "$REPO_DIR" "$raw_json" "$raw_tsv" "$report" "$ts" <<'PY'
import json
import re
import sys
from pathlib import Path

inventory_path = Path(sys.argv[1])
config_path = Path(sys.argv[2])
repo_dir = Path(sys.argv[3]).resolve()
raw_json_path = Path(sys.argv[4])
raw_tsv_path = Path(sys.argv[5])
report_path = Path(sys.argv[6])
ts = sys.argv[7]

SENSITIVE_RE = re.compile(r"(token|key|secret|password|authorization)", re.I)


def sanitize_env(env):
    clean = {}
    for key, value in (env or {}).items():
        if SENSITIVE_RE.search(key):
            clean[key] = "<redacted>"
        else:
            clean[key] = value
    return clean


def load_config(path: Path):
    if path.suffix == ".toml":
        import tomllib

        data = tomllib.loads(path.read_text())
        servers = data.get("mcp_servers") or {}
        fmt = "codex-toml"
    else:
        data = json.loads(path.read_text())
        if isinstance(data, dict) and isinstance(data.get("mcpServers"), dict):
            servers = data["mcpServers"]
            fmt = "json-mcpServers"
        elif isinstance(data, dict) and isinstance(data.get("servers"), dict):
            servers = data["servers"]
            fmt = "json-servers"
        else:
            raise SystemExit(f"Unsupported MCP config structure: {path}")

    normalized = {}
    for name, entry in servers.items():
        if not isinstance(entry, dict):
            continue
        normalized[name] = {
            "name": name,
            "url": entry.get("url"),
            "command": entry.get("command"),
            "args": [str(item) for item in entry.get("args", [])] if isinstance(entry.get("args"), list) else [],
            "env": sanitize_env(entry.get("env") if isinstance(entry.get("env"), dict) else {}),
            "startup_timeout_sec": entry.get("startup_timeout_sec"),
            "transport": "remote" if entry.get("url") else "local",
        }
    return fmt, normalized


def bool_word(value: bool) -> str:
    return "yes" if value else "no"


def parse_timeout(value):
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


inventory = json.loads(inventory_path.read_text())
config_format, config_servers = load_config(config_path)

server_specs = inventory.get("servers", [])
known_names = set()
rows = []
aligned = 0
drift = 0
absent = 0

for spec in server_specs:
    aliases = set(spec.get("config_names") or [])
    aliases.add(spec["key"])
    known_names.update(aliases)
    present_name = next((name for name in aliases if name in config_servers), None)
    config_entry = config_servers.get(present_name) if present_name else None
    notes = list(spec.get("notes") or [])
    status = "absent"

    if config_entry:
        status = "aligned"
        if config_entry["transport"] != spec.get("expected_transport"):
            status = "drift"
            notes.append(
                f"transport mismatch: expected {spec.get('expected_transport')}, got {config_entry['transport']}"
            )

        if config_entry["transport"] == "remote":
            url = config_entry.get("url") or ""
            prefixes = spec.get("url_prefixes") or []
            if prefixes and not any(url.startswith(prefix) for prefix in prefixes):
                status = "drift"
                notes.append(f"url mismatch: {url}")
        else:
            command = config_entry.get("command") or ""
            allowed_commands = spec.get("command_prefixes") or []
            if allowed_commands and command not in allowed_commands:
                status = "drift"
                notes.append(f"command mismatch: {command}")
            args_text = " ".join(config_entry.get("args") or [])
            required_fragments = spec.get("arg_contains") or []
            missing = [fragment for fragment in required_fragments if fragment not in args_text]
            if missing:
                status = "drift"
                notes.append("missing arg fragments: " + ", ".join(missing))
            for env_key in spec.get("repo_dir_env_keys") or []:
                env_value = (config_entry.get("env") or {}).get(env_key)
                if not env_value:
                    status = "drift"
                    notes.append(f"missing env {env_key}")
                    continue
                try:
                    normalized_env_path = Path(str(env_value)).expanduser().resolve()
                except OSError:
                    normalized_env_path = Path(str(env_value)).expanduser()
                if normalized_env_path != repo_dir:
                    status = "drift"
                    notes.append(f"{env_key} points to {normalized_env_path}, repo is {repo_dir}")
            minimum_startup_timeout = spec.get("min_startup_timeout_sec")
            recommended_startup_timeout = spec.get("recommended_startup_timeout_sec") or minimum_startup_timeout
            configured_startup_timeout = parse_timeout(config_entry.get("startup_timeout_sec"))
            if minimum_startup_timeout is not None:
                if config_entry.get("startup_timeout_sec") is None:
                    status = "drift"
                    notes.append(
                        f"missing startup_timeout_sec; keep >= {minimum_startup_timeout}s"
                        f" (recommended {recommended_startup_timeout}s)"
                    )
                elif configured_startup_timeout is None:
                    status = "drift"
                    notes.append(f"invalid startup_timeout_sec: {config_entry.get('startup_timeout_sec')}")
                elif configured_startup_timeout < float(minimum_startup_timeout):
                    status = "drift"
                    notes.append(
                        f"startup_timeout_sec={configured_startup_timeout:g} below minimum"
                        f" {minimum_startup_timeout}s (recommended {recommended_startup_timeout}s)"
                    )
    if status == "aligned":
        aligned += 1
    elif status == "drift":
        drift += 1
    else:
        absent += 1

    rows.append(
        {
            "key": spec["key"],
            "label": spec["label"],
            "classification": spec["classification"],
            "registry_status": spec["registry_status"],
            "integration_scope": spec.get("integration_scope") or [],
            "config_present": bool(config_entry),
            "config_name": present_name,
            "status": status,
            "startup_timeout_sec": config_entry.get("startup_timeout_sec") if config_entry else None,
            "config_entry": config_entry,
            "notes": notes,
        }
    )

unknown_config = [
    config_servers[name]
    for name in sorted(config_servers)
    if name not in known_names
]

payload = {
    "generated_at_utc": ts,
    "repo_dir": str(repo_dir),
    "inventory_file": str(inventory_path),
    "config_file": str(config_path),
    "config_format": config_format,
    "inventory_version": inventory.get("version"),
    "summary": {
        "inventory_servers": len(server_specs),
        "configured_servers": len(config_servers),
        "configured_known": sum(1 for row in rows if row["config_present"]),
        "configured_unknown": len(unknown_config),
        "aligned": aligned,
        "drift": drift,
        "absent": absent,
    },
    "rows": rows,
    "unknown_config": unknown_config,
}

raw_json_path.write_text(json.dumps(payload, indent=2) + "\n")

with raw_tsv_path.open("w", encoding="utf-8") as handle:
    handle.write("key\tclassification\tregistry_status\tconfig_present\tstatus\tconfig_name\tstartup_timeout_sec\n")
    for row in rows:
        handle.write(
            "\t".join(
                [
                    row["key"],
                    row["classification"],
                    row["registry_status"],
                    bool_word(row["config_present"]),
                    row["status"],
                    row["config_name"] or "",
                    str(row["startup_timeout_sec"] or ""),
                ]
            )
            + "\n"
        )

lines = [
    "# MCP Registry Review",
    "",
    f"- generated_at_utc: {ts}",
    f"- config_file: {config_path}",
    f"- config_format: {config_format}",
    f"- repo_dir: {repo_dir}",
    f"- inventory_version: {inventory.get('version')}",
    f"- inventory_servers: {len(server_specs)}",
    f"- configured_servers: {len(config_servers)}",
    f"- aligned: {aligned}",
    f"- drift: {drift}",
    f"- absent: {absent}",
    "",
    "## Managed Servers",
    "",
    "| Server | Class | Registry | Config | Startup | Status | Notes |",
    "| --- | --- | --- | --- | --- | --- | --- |",
]

for row in rows:
    notes = "; ".join(row["notes"][:3]) if row["notes"] else ""
    startup_timeout = "-"
    if row["config_entry"] and row["config_entry"].get("transport") == "local":
        startup_timeout = row["config_entry"].get("startup_timeout_sec")
        if startup_timeout is None:
            startup_timeout = "-"
    lines.append(
        f"| `{row['key']}` | `{row['classification']}` | `{row['registry_status']}` | "
        f"`{row['config_name'] or '-'}` | `{startup_timeout}` | `{row['status']}` | {notes} |"
    )

if unknown_config:
    lines.extend(
        [
            "",
            "## Unknown Config Entries",
            "",
            "| Name | Transport | Command/URL |",
            "| --- | --- | --- |",
        ]
    )
    for entry in unknown_config:
        target = entry.get("url") or f"{entry.get('command') or '-'} {' '.join(entry.get('args') or [])}".strip()
        lines.append(f"| `{entry['name']}` | `{entry['transport']}` | `{target}` |")

drift_rows = [row for row in rows if row["status"] == "drift"]
if drift_rows:
    lines.extend(["", "## Drift Details", ""])
    for row in drift_rows:
        lines.append(f"- `{row['key']}`: {'; '.join(row['notes'])}")

report_path.write_text("\n".join(lines) + "\n")
PY

  {
    echo "raw_json=$raw_json"
    echo "raw_tsv=$raw_tsv"
    echo "report=$report"
  } >> "$execution_log"

  info "Review complete"
  log "report:    $report"
  log "raw json:  $raw_json"
  log "raw tsv:   $raw_tsv"
  log "log:       $execution_log"
}

purge_raw_artifacts() {
  if [[ ! -d "$OPS_DIR" ]]; then
    warn "Nothing to purge in $OPS_DIR"
    return 0
  fi
  if ! confirm_action "Delete raw registry review artifacts in $OPS_DIR ?"; then
    warn "Raw purge cancelled."
    return 1
  fi
  rm -f "$OPS_DIR"/*.log "$OPS_DIR"/*.json "$OPS_DIR"/*.tsv
  info "Purged raw artifacts under $OPS_DIR"
}

purge_all_artifacts() {
  if [[ ! -d "$OPS_DIR" ]]; then
    warn "Nothing to purge: $OPS_DIR"
    return 0
  fi
  if ! confirm_action "Delete the full registry review directory $OPS_DIR ?"; then
    warn "Full purge cancelled."
    return 1
  fi
  rm -rf "$OPS_DIR"
  info "Purged: $OPS_DIR"
}

main() {
  parse_args "$@"
  case "$CMD" in
    audit)
      run_review
      ;;
    purge-raw)
      purge_raw_artifacts
      ;;
    purge)
      purge_all_artifacts
      ;;
    run)
      run_review
      if [[ "$AUTO_PURGE_RAW" -eq 1 ]]; then
        purge_raw_artifacts || true
      elif confirm_action "Purge raw registry review artifacts now?"; then
        purge_raw_artifacts || true
      fi
      ;;
    *)
      err "Unsupported command: $CMD"
      exit 2
      ;;
  esac
}

main "$@"
