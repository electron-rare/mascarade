#!/usr/bin/env bash

set -euo pipefail

cp_script_dir() {
  local source_file="${BASH_SOURCE[1]:-${BASH_SOURCE[0]}}"
  cd "$(dirname "$source_file")" && pwd
}

cp_project_root() {
  local script_dir
  script_dir="$(cp_script_dir)"
  cd "$script_dir/.." && pwd
}

cp_require_tools() {
  local missing=()
  for tool in "$@"; do
    if ! command -v "$tool" >/dev/null 2>&1; then
      missing+=("$tool")
    fi
  done

  if (( ${#missing[@]} > 0 )); then
    printf 'Missing required tools: %s\n' "${missing[*]}" >&2
    exit 2
  fi
}

cp_is_tty() {
  [[ -t 0 && -t 1 ]]
}

cp_log() {
  local level="$1"
  shift
  if [[ "${VERBOSE:-0}" == "1" ]]; then
    printf '[%s] %s\n' "$level" "$*" >&2
  fi
}

cp_die() {
  printf 'ERROR: %s\n' "$*" >&2
  exit 1
}

cp_confirm() {
  local prompt="${1:-Proceed?}"
  if [[ "${YES:-0}" == "1" ]]; then
    return 0
  fi

  if ! cp_is_tty; then
    cp_die "Refusing to continue without --yes in non-interactive mode"
  fi

  local answer=""
  read -r -p "$prompt [y/N] " answer
  case "$answer" in
    y|Y|yes|YES) return 0 ;;
    *) return 1 ;;
  esac
}

cp_choose() {
  local prompt="$1"
  shift

  if command -v gum >/dev/null 2>&1 && cp_is_tty; then
    gum choose --header "$prompt" "$@"
    return
  fi

  if ! cp_is_tty; then
    cp_die "Interactive selection requires a TTY"
  fi

  local options=("$@")
  local idx=1
  printf '%s\n' "$prompt"
  for option in "${options[@]}"; do
    printf '  %d) %s\n' "$idx" "$option"
    idx=$((idx + 1))
  done

  local choice=""
  read -r -p "Choice: " choice
  if [[ "$choice" =~ ^[0-9]+$ ]] && (( choice >= 1 && choice <= ${#options[@]} )); then
    printf '%s\n' "${options[$((choice - 1))]}"
    return
  fi

  cp_die "Invalid selection"
}

cp_default_log_dir() {
  local root
  root="$(cp_project_root)"
  printf '%s\n' "${CONTROL_PLANE_LOG_DIR:-$root/api/logs}"
}

cp_http() {
  local method="$1"
  local path="$2"
  local body="${3-}"
  local url="${CONTROL_PLANE_URL%/}${path}"
  local tmp
  tmp="$(mktemp)"

  cp_log DEBUG "HTTP ${method} ${url}"

  local -a args=(
    --silent
    --show-error
    --location
    --request "$method"
    --header "accept: application/json"
    --connect-timeout "${CONTROL_PLANE_CONNECT_TIMEOUT:-5}"
    --max-time "${CONTROL_PLANE_MAX_TIME:-20}"
    --output "$tmp"
    --write-out '%{http_code}'
  )

  if [[ -n "${CONTROL_PLANE_SHARED_TOKEN:-}" ]]; then
    args+=(--header "x-mascarade-node-token: ${CONTROL_PLANE_SHARED_TOKEN}")
  fi

  if [[ -n "$body" ]]; then
    args+=(--header "content-type: application/json")
  fi

  local http_code
  if [[ -n "$body" ]]; then
    http_code="$(printf '%s' "$body" | curl "${args[@]}" --data-binary @- "$url")" || {
      rm -f "$tmp"
      cp_die "HTTP request failed: ${method} ${path}"
    }
  else
    http_code="$(curl "${args[@]}" "$url")" || {
      rm -f "$tmp"
      cp_die "HTTP request failed: ${method} ${path}"
    }
  fi

  if [[ "$http_code" == 2* ]]; then
    cat "$tmp"
    rm -f "$tmp"
    return 0
  fi

  local response
  response="$(cat "$tmp" 2>/dev/null || true)"
  rm -f "$tmp"
  if [[ -n "$response" ]]; then
    printf '%s\n' "$response" >&2
  fi
  cp_die "HTTP ${http_code} for ${method} ${path}"
}

cp_json_pretty() {
  python3 -m json.tool
}

