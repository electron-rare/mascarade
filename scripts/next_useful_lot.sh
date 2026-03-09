#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MASCARADE_ROOT="$ROOT_DIR"
CRAZY_LIFE_ROOT="$(cd "$ROOT_DIR/../crazy_life" && pwd)"
KILL_LIFE_ROOT="$(cd "$ROOT_DIR/../Kill_LIFE" && pwd)"
AGENT_FACTORY_ROOT="$(cd "$ROOT_DIR/../agent-factory-cockpit" && pwd)"
STATE_DOC="$ROOT_DIR/docs/NEXT_USEFUL_LOT_STATE.md"

SUBCOMMAND="detect"
FORMAT="text"
TARGET_LOT=""
WRITE_STATE=0
DRY_RUN=0

DETECTED_LOT_ID=""
DETECTED_KIND=""
DETECTED_PRIMARY_REPO=""
DETECTED_PRIMARY_ROOT=""
DETECTED_REASON=""
DETECTED_COMPANIONS=()
DETECTED_CHECKS=()
DETECTED_SCOPE_PATHS=()

usage() {
  cat <<'EOF'
Usage: bash scripts/next_useful_lot.sh [subcommand] [options]

Subcommands:
  detect     Detect the next useful lot (default)
  checks     Run canonical checks for the detected lot or a provided lot
  state      Print or write the generated markdown state for the detected lot
  paths      Print the scope paths for the detected lot

Options:
  --lot LOT          Force a specific lot id instead of auto-detecting
  --format FORMAT    text | json | markdown (default: text)
  --write            For `state`, write the markdown to docs/NEXT_USEFUL_LOT_STATE.md
  --dry-run          For `checks`, print commands without executing them
  --help             Show this help

Known lot ids:
  industrial-dcs-governed-sandbox
  industrial-minimal-contract-intake
  agent-factory-cockpit-followup
  mascarade-followup
  crazy-life-followup
  kill-life-followup
  external-only
EOF
}

repo_label() {
  case "$1" in
    "$MASCARADE_ROOT") echo "mascarade" ;;
    "$CRAZY_LIFE_ROOT") echo "crazy_life" ;;
    "$KILL_LIFE_ROOT") echo "Kill_LIFE" ;;
    "$AGENT_FACTORY_ROOT") echo "agent-factory-cockpit" ;;
    *) echo "$1" ;;
  esac
}

repo_paths() {
  local repo_root="$1"
  local state_rel=""
  if [[ "$repo_root" == "$MASCARADE_ROOT" ]]; then
    state_rel="${STATE_DOC#${repo_root}/}"
  fi

  git -C "$repo_root" status --porcelain=1 | while IFS= read -r line; do
    local path="${line#???}"
    path="${path##* -> }"
    if [[ -n "${state_rel}" && "${path}" == "${state_rel}" ]]; then
      continue
    fi
    printf '%s\n' "$path"
  done
}

repo_dirty_count() {
  local repo_root="$1"
  repo_paths "$repo_root" | wc -l | tr -d ' '
}

list_external_blockers() {
  awk '
    /^## Restes reels/ {in_block=1; next}
    /^## / && in_block {exit}
    in_block && /^- / {print}
  ' "$ROOT_DIR/TODO_VM.md"
}

matches_any_regex() {
  local regex="$1"
  shift
  local path
  for path in "$@"; do
    if [[ "$path" =~ $regex ]]; then
      return 0
    fi
  done
  return 1
}

set_lot() {
  DETECTED_LOT_ID="$1"
  DETECTED_KIND="$2"
  DETECTED_PRIMARY_REPO="$3"
  DETECTED_PRIMARY_ROOT="$4"
  DETECTED_REASON="$5"
  shift 5
  DETECTED_COMPANIONS=()
  DETECTED_CHECKS=()
  DETECTED_SCOPE_PATHS=()
}

load_lot_definition() {
  local lot_id="$1"

  case "$lot_id" in
    industrial-dcs-governed-sandbox)
      set_lot \
        "industrial-dcs-governed-sandbox" \
        "local" \
        "agent-factory-cockpit" \
        "$AGENT_FACTORY_ROOT" \
        "The DCS sandbox lane is the only active industrial lot: local tracked changes cover the DCS contract, topology, sandbox runtime, cockpit UI, tests, and companion state docs."
      DETECTED_COMPANIONS=("mascarade" "crazy_life")
      DETECTED_SCOPE_PATHS=(
        "README.md"
        "Makefile"
        "agent_factory_cockpit/dcs_sandbox.py"
        "contracts/vendors/dcs/contract.yaml"
        "contracts/vendors/dcs/openapi.yaml"
        "docs/IMPLEMENTATION_TODO.md"
        "examples/dcs-governed-sandbox.json"
        "src/main.js"
        "src/styles.css"
        "tests/test_topology.py"
        "topology/dcs.yaml"
      )
      DETECTED_CHECKS=(
        "cd $AGENT_FACTORY_ROOT && python3 -m py_compile serve.py agent_factory_cockpit/*.py scripts/lotctl.py"
        "cd $AGENT_FACTORY_ROOT && python3 -m unittest tests.test_topology tests.test_validation tests.test_runtime -q"
        "cd $AGENT_FACTORY_ROOT && python3 -m unittest tests.test_execution tests.test_mcp tests.test_dcs_sandbox tests.test_lotctl -q"
        "cd $AGENT_FACTORY_ROOT && make demo-dcs-sandbox"
        "git -C $AGENT_FACTORY_ROOT diff --check"
      )
      ;;
    industrial-minimal-contract-intake)
      set_lot \
        "industrial-minimal-contract-intake" \
        "local" \
        "agent-factory-cockpit" \
        "$AGENT_FACTORY_ROOT" \
        "A new industrial contract-intake lot is active locally: minimal vendor contract YAMLs, topology dossier wiring, and vendor-intake automation now span PLM/QMS/MES/ERP/WMS/DCS."
      DETECTED_CHECKS=(
        "cd $AGENT_FACTORY_ROOT && python3 -m py_compile serve.py agent_factory_cockpit/*.py scripts/lotctl.py scripts/vendor_contract_intake.py"
        "cd $AGENT_FACTORY_ROOT && bash -n scripts/vendor_contract.sh scripts/industrial_lot.sh scripts/lotctl.sh"
        "cd $AGENT_FACTORY_ROOT && python3 -m unittest tests.test_topology tests.test_validation tests.test_lotctl -q"
        "git -C $AGENT_FACTORY_ROOT diff --check"
      )
      ;;
    agent-factory-cockpit-followup)
      set_lot \
        "agent-factory-cockpit-followup" \
        "local" \
        "agent-factory-cockpit" \
        "$AGENT_FACTORY_ROOT" \
        "Tracked local changes remain in agent-factory-cockpit, but they do not match a more specific automation rule yet."
      DETECTED_CHECKS=(
        "cd $AGENT_FACTORY_ROOT && python3 -m unittest discover -s tests -q"
        "git -C $AGENT_FACTORY_ROOT diff --check"
      )
      ;;
    mascarade-followup)
      set_lot \
        "mascarade-followup" \
        "local" \
        "mascarade" \
        "$MASCARADE_ROOT" \
        "Tracked local changes remain in mascarade and need the usual runtime/docs/build pass before publication."
      DETECTED_CHECKS=(
        "cd $MASCARADE_ROOT && bash scripts/review_local_change_bundle.sh all status"
        "cd $MASCARADE_ROOT && npm --prefix api run build"
        "cd $MASCARADE_ROOT && npm --prefix web run build:api-public"
        "git -C $MASCARADE_ROOT diff --check"
      )
      ;;
    crazy-life-followup)
      set_lot \
        "crazy-life-followup" \
        "local" \
        "crazy_life" \
        "$CRAZY_LIFE_ROOT" \
        "Tracked local changes remain in crazy_life and should be checked as a cockpit mirror follow-up."
      DETECTED_CHECKS=(
        "cd $CRAZY_LIFE_ROOT && npm run build"
        "cd $CRAZY_LIFE_ROOT && bash scripts/publish_preflight.sh check"
        "git -C $CRAZY_LIFE_ROOT diff --check"
      )
      ;;
    kill-life-followup)
      set_lot \
        "kill-life-followup" \
        "local" \
        "Kill_LIFE" \
        "$KILL_LIFE_ROOT" \
        "Tracked local changes remain in Kill_LIFE and should be checked with the stable Python/spec suite."
      DETECTED_CHECKS=(
        "cd $KILL_LIFE_ROOT && bash tools/test_python.sh --suite stable"
        "cd $KILL_LIFE_ROOT && python3 tools/validate_specs.py --json"
        "git -C $KILL_LIFE_ROOT diff --check"
      )
      ;;
    external-only)
      set_lot \
        "external-only" \
        "external" \
        "none" \
        "-" \
        "No tracked local implementation lot is open. Only external blockers or operator-side actions remain."
      ;;
    *)
      echo "Unknown lot id: $lot_id" >&2
      exit 2
      ;;
  esac
}

populate_scope_paths_for_current_lot() {
  case "$DETECTED_LOT_ID" in
    agent-factory-cockpit-followup)
      mapfile -t DETECTED_SCOPE_PATHS < <(repo_paths "$AGENT_FACTORY_ROOT")
      ;;
    mascarade-followup)
      mapfile -t DETECTED_SCOPE_PATHS < <(repo_paths "$MASCARADE_ROOT")
      ;;
    crazy-life-followup)
      mapfile -t DETECTED_SCOPE_PATHS < <(repo_paths "$CRAZY_LIFE_ROOT")
      ;;
    kill-life-followup)
      mapfile -t DETECTED_SCOPE_PATHS < <(repo_paths "$KILL_LIFE_ROOT")
      ;;
    industrial-minimal-contract-intake)
      mapfile -t DETECTED_SCOPE_PATHS < <(repo_paths "$AGENT_FACTORY_ROOT")
      ;;
  esac
}

detect_next_lot() {
  if [[ -n "$TARGET_LOT" ]]; then
    load_lot_definition "$TARGET_LOT"
    populate_scope_paths_for_current_lot
    return 0
  fi

  mapfile -t afc_paths < <(repo_paths "$AGENT_FACTORY_ROOT")
  mapfile -t masc_paths < <(repo_paths "$MASCARADE_ROOT")
  mapfile -t crazy_paths < <(repo_paths "$CRAZY_LIFE_ROOT")
  mapfile -t kill_paths < <(repo_paths "$KILL_LIFE_ROOT")

  if [[ "${#afc_paths[@]}" -gt 0 ]] && matches_any_regex '(^agent_factory_cockpit/vendor_contracts\.py$|^contracts/vendors/.+/minimal-contract\.yaml$|^scripts/vendor_contract\.sh$|^scripts/vendor_contract_intake\.py$|^topology/(plm|qms|mes|erp|wms|dcs)\.yaml$)' "${afc_paths[@]}"; then
    load_lot_definition "industrial-minimal-contract-intake"
    DETECTED_SCOPE_PATHS=("${afc_paths[@]}")
    return 0
  fi

  if [[ "${#afc_paths[@]}" -gt 0 ]] && matches_any_regex '(^agent_factory_cockpit/dcs_sandbox\.py$|^contracts/vendors/dcs/|^topology/dcs\.yaml$|^examples/dcs-governed-sandbox\.json$|^src/main\.js$|^src/styles\.css$|^tests/test_topology\.py$|^README\.md$|^docs/IMPLEMENTATION_TODO\.md$|^Makefile$)' "${afc_paths[@]}"; then
    load_lot_definition "industrial-dcs-governed-sandbox"
    return 0
  fi

  if [[ "${#afc_paths[@]}" -gt 0 ]]; then
    load_lot_definition "agent-factory-cockpit-followup"
    DETECTED_SCOPE_PATHS=("${afc_paths[@]}")
    return 0
  fi

  if [[ "${#masc_paths[@]}" -gt 0 ]]; then
    load_lot_definition "mascarade-followup"
    DETECTED_SCOPE_PATHS=("${masc_paths[@]}")
    return 0
  fi

  if [[ "${#crazy_paths[@]}" -gt 0 ]]; then
    load_lot_definition "crazy-life-followup"
    DETECTED_SCOPE_PATHS=("${crazy_paths[@]}")
    return 0
  fi

  if [[ "${#kill_paths[@]}" -gt 0 ]]; then
    load_lot_definition "kill-life-followup"
    DETECTED_SCOPE_PATHS=("${kill_paths[@]}")
    return 0
  fi

  load_lot_definition "external-only"
}

emit_detect_text() {
  printf 'lot_id=%s\n' "$DETECTED_LOT_ID"
  printf 'kind=%s\n' "$DETECTED_KIND"
  printf 'primary_repo=%s\n' "$DETECTED_PRIMARY_REPO"
  printf 'primary_root=%s\n' "$DETECTED_PRIMARY_ROOT"
  printf 'reason=%s\n' "$DETECTED_REASON"
  if [[ "${#DETECTED_COMPANIONS[@]}" -gt 0 ]]; then
    printf 'companions=%s\n' "$(IFS=,; echo "${DETECTED_COMPANIONS[*]}")"
  else
    printf 'companions=\n'
  fi
}

emit_detect_json() {
  local companions_json="[]"
  if [[ "${#DETECTED_COMPANIONS[@]}" -gt 0 ]]; then
    companions_json="$(printf '%s\n' "${DETECTED_COMPANIONS[@]}" | python3 -c 'import json,sys; print(json.dumps([line.strip() for line in sys.stdin if line.strip()]))')"
  fi
  python3 - "$DETECTED_LOT_ID" "$DETECTED_KIND" "$DETECTED_PRIMARY_REPO" "$DETECTED_PRIMARY_ROOT" "$DETECTED_REASON" "$companions_json" <<'PY'
import json, sys
lot_id, kind, primary_repo, primary_root, reason, companions = sys.argv[1:]
print(json.dumps({
    "lot_id": lot_id,
    "kind": kind,
    "primary_repo": primary_repo,
    "primary_root": primary_root,
    "reason": reason,
    "companions": json.loads(companions),
}, indent=2))
PY
}

emit_scope_paths() {
  if [[ "${#DETECTED_SCOPE_PATHS[@]}" -eq 0 ]]; then
    return 0
  fi
  printf '%s\n' "${DETECTED_SCOPE_PATHS[@]}"
}

render_state_markdown() {
  local dirty_masc dirty_crazy dirty_kill dirty_afc
  dirty_masc="$(repo_dirty_count "$MASCARADE_ROOT")"
  dirty_crazy="$(repo_dirty_count "$CRAZY_LIFE_ROOT")"
  dirty_kill="$(repo_dirty_count "$KILL_LIFE_ROOT")"
  dirty_afc="$(repo_dirty_count "$AGENT_FACTORY_ROOT")"

  cat <<EOF
# Next Useful Lot State

Generated: $(date '+%Y-%m-%d %H:%M:%S %Z')

## Summary

- Detected lot: \`$DETECTED_LOT_ID\`
- Kind: \`$DETECTED_KIND\`
- Primary repo: \`$DETECTED_PRIMARY_REPO\`
- Primary root: \`$DETECTED_PRIMARY_ROOT\`
- Reason: $DETECTED_REASON
EOF

  if [[ "${#DETECTED_COMPANIONS[@]}" -gt 0 ]]; then
    printf -- "- Companion repos: \`%s\`\n" "$(IFS=', '; echo "${DETECTED_COMPANIONS[*]}")"
  fi

  cat <<EOF

## Repo Snapshot

- \`mascarade\`: ${dirty_masc} tracked delta(s)
- \`crazy_life\`: ${dirty_crazy} tracked delta(s)
- \`Kill_LIFE\`: ${dirty_kill} tracked delta(s)
- \`agent-factory-cockpit\`: ${dirty_afc} tracked delta(s)

## Scope Paths
EOF

  if [[ "${#DETECTED_SCOPE_PATHS[@]}" -gt 0 ]]; then
    printf '\n'
    for path in "${DETECTED_SCOPE_PATHS[@]}"; do
      printf -- '- `%s`\n' "$path"
    done
  else
    printf '\n- none (no local lot detected)\n'
  fi

  cat <<EOF

## Canonical Checks
EOF

  if [[ "${#DETECTED_CHECKS[@]}" -gt 0 ]]; then
    printf '\n```bash\n'
    printf '%s\n' "${DETECTED_CHECKS[@]}"
    printf '```\n'
  else
    printf '\n- none; only external blockers remain\n'
  fi

  cat <<EOF

## External Blockers After Local Lots
EOF
  local blockers
  blockers="$(list_external_blockers || true)"
  if [[ -n "$blockers" ]]; then
    printf '\n%s\n' "$blockers"
  else
    printf '\n- none listed\n'
  fi
}

run_checks() {
  if [[ "${#DETECTED_CHECKS[@]}" -eq 0 ]]; then
    echo "No local checks to run for lot '$DETECTED_LOT_ID'." >&2
    return 0
  fi

  local cmd
  for cmd in "${DETECTED_CHECKS[@]}"; do
    if [[ "$DRY_RUN" -eq 1 ]]; then
      printf '%s\n' "$cmd"
      continue
    fi
    echo "+ $cmd"
    bash -lc "$cmd"
  done
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    detect|checks|state|paths)
      SUBCOMMAND="$1"
      shift
      ;;
    --lot)
      TARGET_LOT="${2:-}"
      shift 2
      ;;
    --format)
      FORMAT="${2:-}"
      shift 2
      ;;
    --write)
      WRITE_STATE=1
      shift
      ;;
    --dry-run)
      DRY_RUN=1
      shift
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

detect_next_lot

case "$SUBCOMMAND" in
  detect)
    case "$FORMAT" in
      text) emit_detect_text ;;
      json) emit_detect_json ;;
      *)
        echo "Unsupported format for detect: $FORMAT" >&2
        exit 2
        ;;
    esac
    ;;
  checks)
    run_checks
    ;;
  paths)
    emit_scope_paths
    ;;
  state)
    case "$FORMAT" in
      text|markdown)
        if [[ "$WRITE_STATE" -eq 1 ]]; then
          render_state_markdown >"$STATE_DOC"
          printf '%s\n' "$STATE_DOC"
        else
          render_state_markdown
        fi
        ;;
      *)
        echo "Unsupported format for state: $FORMAT" >&2
        exit 2
        ;;
    esac
    ;;
esac
