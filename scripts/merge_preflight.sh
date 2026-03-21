#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORKSPACE_ROOT="$(cd "${ROOT_DIR}/.." && pwd)"
NOW_UTC="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"

REPO_NAMES=(
  "mascarade-main"
  "mascarade"
  "mascarade-api-deps"
  "mascarade-apple-coreml"
  "mascarade-frontend-pr"
  "crazy_life"
  "Kill_LIFE"
)

usage() {
  cat <<'EOF'
Usage: bash scripts/merge_preflight.sh <command> [options]

Commands:
  snapshot         Print multi-repo git snapshot and write a markdown report
  baseline         Validate merge baseline for mascarade-main
  all              Run baseline then snapshot

Options:
  --report-dir DIR       Directory for markdown reports
  --allow-non-main       Do not fail baseline when current branch is not main
  --strict-clean         Fail baseline if mascarade-main has local changes
  -h, --help             Show help

Examples:
  bash scripts/merge_preflight.sh snapshot
  bash scripts/merge_preflight.sh baseline --strict-clean
  bash scripts/merge_preflight.sh all --report-dir docs/audit
EOF
}

COMMAND="${1:-}"
if [[ -z "${COMMAND}" ]]; then
  usage
  exit 2
fi
shift || true

REPORT_DIR="${ROOT_DIR}/docs/audit"
ALLOW_NON_MAIN=false
STRICT_CLEAN=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    --report-dir)
      shift
      [[ $# -gt 0 ]] || { echo "Missing value for --report-dir" >&2; exit 2; }
      REPORT_DIR="$1"
      ;;
    --allow-non-main)
      ALLOW_NON_MAIN=true
      ;;
    --strict-clean)
      STRICT_CLEAN=true
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
  shift
 done

repo_path() {
  local name="$1"
  echo "${WORKSPACE_ROOT}/${name}"
}

repo_exists() {
  local path="$1"
  [[ -d "${path}" ]] && git -C "${path}" rev-parse --is-inside-work-tree >/dev/null 2>&1
}

repo_branch() {
  local path="$1"
  git -C "${path}" rev-parse --abbrev-ref HEAD 2>/dev/null || echo "unknown"
}

repo_remote() {
  local path="$1"
  git -C "${path}" remote get-url origin 2>/dev/null || echo "no-origin"
}

repo_dirty_count() {
  local path="$1"
  git -C "${path}" status --porcelain 2>/dev/null | wc -l | tr -d ' '
}

repo_last_commit() {
  local path="$1"
  git -C "${path}" log -1 --pretty=format:'%h %ad %s' --date=short 2>/dev/null || echo "no-commit"
}

ensure_report_dir() {
  mkdir -p "${REPORT_DIR}"
}

print_snapshot_table() {
  printf "%-26s %-36s %-7s %s\n" "repo" "branch" "dirty" "last commit"
  printf "%-26s %-36s %-7s %s\n" "--------------------------" "------------------------------------" "-------" "-----------"

  local name path branch dirty last
  for name in "${REPO_NAMES[@]}"; do
    path="$(repo_path "${name}")"
    if repo_exists "${path}"; then
      branch="$(repo_branch "${path}")"
      dirty="$(repo_dirty_count "${path}")"
      last="$(repo_last_commit "${path}")"
      printf "%-26s %-36s %-7s %s\n" "${name}" "${branch}" "${dirty}" "${last}"
    else
      printf "%-26s %-36s %-7s %s\n" "${name}" "missing" "n/a" "repo not found"
    fi
  done
}

write_snapshot_report() {
  ensure_report_dir
  local report_file="${REPORT_DIR}/MERGE_PREFLIGHT_SNAPSHOT_$(date -u +"%Y-%m-%d_%H%M%S").md"

  {
    echo "# Merge Preflight Snapshot"
    echo
    echo "- generated_at_utc: ${NOW_UTC}"
    echo "- workspace_root: ${WORKSPACE_ROOT}"
    echo
    echo "## Repos"
    echo
    echo "| Repo | Branch | Dirty files | Origin | Last commit |"
    echo "| --- | --- | ---: | --- | --- |"

    local name path branch dirty origin last
    for name in "${REPO_NAMES[@]}"; do
      path="$(repo_path "${name}")"
      if repo_exists "${path}"; then
        branch="$(repo_branch "${path}")"
        dirty="$(repo_dirty_count "${path}")"
        origin="$(repo_remote "${path}")"
        last="$(repo_last_commit "${path}")"
        echo "| ${name} | ${branch} | ${dirty} | ${origin} | ${last} |"
      else
        echo "| ${name} | missing | n/a | n/a | repo not found |"
      fi
    done

    echo
    echo "## Worktree map (mascarade)"
    echo
    if repo_exists "$(repo_path "mascarade")"; then
      echo '```text'
      git -C "$(repo_path "mascarade")" worktree list --porcelain || true
      echo '```'
    else
      echo "mascarade repo missing"
    fi
  } > "${report_file}"

  echo "report: ${report_file}"
}

run_baseline() {
  local mm_path
  mm_path="$(repo_path "mascarade-main")"

  if ! repo_exists "${mm_path}"; then
    echo "baseline error: mascarade-main repo missing at ${mm_path}" >&2
    return 1
  fi

  local branch
  branch="$(repo_branch "${mm_path}")"
  if [[ "${ALLOW_NON_MAIN}" == false && "${branch}" != "main" ]]; then
    echo "baseline error: expected branch main, got ${branch}" >&2
    return 1
  fi

  if git -C "${mm_path}" rev-parse -q --verify MERGE_HEAD >/dev/null 2>&1; then
    echo "baseline error: merge in progress in mascarade-main" >&2
    return 1
  fi

  if git -C "${mm_path}" rev-parse -q --verify CHERRY_PICK_HEAD >/dev/null 2>&1; then
    echo "baseline error: cherry-pick in progress in mascarade-main" >&2
    return 1
  fi

  local dirty
  dirty="$(repo_dirty_count "${mm_path}")"
  if [[ "${STRICT_CLEAN}" == true && "${dirty}" != "0" ]]; then
    echo "baseline error: mascarade-main has ${dirty} local changes (strict mode)" >&2
    return 1
  fi

  local required=(
    "${mm_path}/core/pyproject.toml"
    "${mm_path}/api/package.json"
    "${mm_path}/docker-compose.yml"
    "${mm_path}/scripts/test_python.sh"
  )

  local file
  for file in "${required[@]}"; do
    if [[ ! -f "${file}" ]]; then
      echo "baseline error: required file missing: ${file}" >&2
      return 1
    fi
  done

  echo "baseline ok"
  echo "- repo: ${mm_path}"
  echo "- branch: ${branch}"
  echo "- local changes: ${dirty}"
  echo "- timestamp: ${NOW_UTC}"
}

case "${COMMAND}" in
  snapshot)
    print_snapshot_table
    write_snapshot_report
    ;;
  baseline)
    run_baseline
    ;;
  all)
    run_baseline
    echo
    print_snapshot_table
    write_snapshot_report
    ;;
  *)
    echo "Unknown command: ${COMMAND}" >&2
    usage >&2
    exit 2
    ;;
esac
