#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/Users/electron/mascarade/scripts/lib.sh
source "$SCRIPT_DIR/lib.sh"

setup_trap

ACTION="run"
AUTO_YES=false
KEEP_LOG=false
REPORT_PATH=""
declare -a TARGET_REPOS=()

usage() {
    cat <<'EOF'
Usage: bash scripts/repo_deep_analysis_tui.sh [run|status] [options]

Analyse documentaire et structurelle des repos canoniques du chantier.

Options:
  --repo <name>     Repo cible: mascarade | crazy_life | Kill_LIFE | all
  --out <path>      Ecrire le rapport Markdown a cet emplacement
  --keep-log        Conserver le log temporaire au lieu de le supprimer
  --plain           Forcer le mode non-TUI
  --yes             Eviter la confirmation interactive
  -v, --verbose     Activer les traces debug
  -h, --help        Afficher cette aide
EOF
}

repo_root() {
    case "$1" in
        mascarade) echo "/Users/electron/mascarade" ;;
        crazy_life) echo "/Users/electron/crazy_life" ;;
        Kill_LIFE|kill_life) echo "/Users/electron/Kill_LIFE" ;;
        *) return 1 ;;
    esac
}

normalize_repo_name() {
    case "$1" in
        all) echo "all" ;;
        mascarade) echo "mascarade" ;;
        crazy_life) echo "crazy_life" ;;
        Kill_LIFE|kill_life) echo "Kill_LIFE" ;;
        *) return 1 ;;
    esac
}

ensure_targets() {
    if [[ ${#TARGET_REPOS[@]} -eq 0 ]]; then
        TARGET_REPOS=("mascarade" "crazy_life" "Kill_LIFE")
    fi
}

tmp_log=""
cleanup_local() {
    if [[ -n "$tmp_log" && -f "$tmp_log" && "$KEEP_LOG" != true ]]; then
        rm -f "$tmp_log"
    fi
}
trap cleanup_local EXIT

log_event() {
    local ts
    ts="$(date '+%Y-%m-%d %H:%M:%S')"
    printf '[%s] %s\n' "$ts" "$*" >> "$tmp_log"
}

count_files() {
    local repo="$1" pattern="$2"
    local matches
    matches="$(rg --files "$repo" | rg "$pattern" || true)"
    if [[ -z "$matches" ]]; then
        echo "0"
    else
        printf '%s\n' "$matches" | wc -l | tr -d ' '
    fi
}

count_match_files() {
    local repo="$1" pattern="$2"
    local matches
    matches="$(rg -l \
        --glob '*.md' \
        --glob '*.mmd' \
        --glob '*.puml' \
        --glob '!**/.git/**' \
        --glob '!node_modules/**' \
        --glob '!dist/**' \
        --glob '!build/**' \
        "$pattern" "$repo" || true)"
    if [[ -z "$matches" ]]; then
        echo "0"
    else
        printf '%s\n' "$matches" | wc -l | tr -d ' '
    fi
}

top_readme() {
    local repo="$1"
    if [[ -f "$repo/README.md" ]]; then
        echo "README.md"
    elif [[ -f "$repo/README" ]]; then
        echo "README"
    else
        echo "-"
    fi
}

top_plan() {
    local repo="$1"
    if [[ -f "$repo/plan.md" ]]; then
        echo "plan.md"
    elif [[ -f "$repo/docs/plans/README.md" ]]; then
        echo "docs/plans/README.md"
    else
        echo "-"
    fi
}

top_todo() {
    local repo="$1"
    local candidate
    candidate="$(rg --files "$repo" | rg '(^|/)(TODO|TODO_.*|04_tasks\.md)$' | sed -n '1p' || true)"
    if [[ -n "$candidate" ]]; then
        python3 - <<'PY' "$repo" "$candidate"
from pathlib import Path
import sys
root = Path(sys.argv[1]).resolve()
path = Path(sys.argv[2]).resolve()
print(path.relative_to(root))
PY
    else
        echo "-"
    fi
}

write_repo_section() {
    local repo_name="$1" root="$2" report="$3"
    local branch dirty readmes manifests plans todos mermaid sequences feature_maps tests shells py tsx
    branch="$(git -C "$root" branch --show-current 2>/dev/null || echo '?')"
    dirty="$(git -C "$root" status --short 2>/dev/null | wc -l | tr -d ' ')"
    readmes="$(count_files "$root" '(^|/)(README|README\.md)$')"
    manifests="$(count_files "$root" '(^|/)(MANIFEST\.md)$')"
    plans="$(count_files "$root" '(^|/)(plan\.md|03_plan\.md|docs/plans/.*\.md)$')"
    todos="$(count_files "$root" '(^|/)(TODO|TODO_.*|04_tasks\.md)$')"
    mermaid="$(count_match_files "$root" '```mermaid|@startuml|flowchart|graph TD')"
    sequences="$(count_match_files "$root" 'sequenceDiagram|diagramme de sequence|sequence diagram')"
    feature_maps="$(count_match_files "$root" 'feature map|functional map|carte de fonctionnal|product surface|workflow registry|fonctionnalites principales')"
    tests="$(count_files "$root" '(^|/)(test_.*\.py|.*\.test\.(ts|tsx|js)|.*spec\.(ts|tsx|js)|tests?/.*)$')"
    shells="$(count_files "$root" '\.sh$')"
    py="$(count_files "$root" '\.py$')"
    tsx="$(count_files "$root" '\.(ts|tsx)$')"

    log_event "repo=$repo_name branch=$branch dirty=$dirty readmes=$readmes manifests=$manifests plans=$plans todos=$todos mermaid=$mermaid sequences=$sequences feature_maps=$feature_maps tests=$tests shells=$shells py=$py ts_tsx=$tsx"

    {
        echo "## $repo_name"
        echo
        echo "- Root: \`$root\`"
        echo "- Branch: \`$branch\`"
        echo "- Dirty entries: \`$dirty\`"
        echo "- Primary README: \`$(top_readme "$root")\`"
        echo "- Primary plan anchor: \`$(top_plan "$root")\`"
        echo "- First TODO anchor: \`$(top_todo "$root")\`"
        echo
        echo "| Metric | Value |"
        echo "| --- | --- |"
        echo "| README files | $readmes |"
        echo "| MANIFEST files | $manifests |"
        echo "| Plan files | $plans |"
        echo "| TODO/task files | $todos |"
        echo "| Diagram files | $mermaid |"
        echo "| Sequence diagram files | $sequences |"
        echo "| Feature-map-like files | $feature_maps |"
        echo "| Test files | $tests |"
        echo "| Shell scripts | $shells |"
        echo "| Python files | $py |"
        echo "| TS/TSX files | $tsx |"
        echo
        echo "### Gaps"
        if [[ "$sequences" == "0" ]]; then
            echo "- Missing explicit sequence diagrams."
        fi
        if [[ "$feature_maps" == "0" ]]; then
            echo "- Missing explicit feature map or functional cartography."
        fi
        if [[ "$readmes" == "0" ]]; then
            echo "- Missing root README."
        fi
        if [[ "$plans" == "0" ]]; then
            echo "- Missing plan anchor."
        fi
        if [[ "$sequences" != "0" && "$feature_maps" != "0" && "$readmes" != "0" && "$plans" != "0" ]]; then
            echo "- Baseline documentation anchors exist; refresh and alignment remain required."
        fi
        echo
    } >> "$report"
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        run|status)
            ACTION="$1"
            shift
            ;;
        --repo)
            [[ $# -lt 2 ]] && { err "--repo requiert une valeur"; usage; exit 2; }
            normalized="$(normalize_repo_name "$2")" || { err "Repo inconnu: $2"; exit 2; }
            if [[ "$normalized" == "all" ]]; then
                TARGET_REPOS=("mascarade" "crazy_life" "Kill_LIFE")
            else
                TARGET_REPOS+=("$normalized")
            fi
            shift 2
            ;;
        --out)
            [[ $# -lt 2 ]] && { err "--out requiert un chemin"; usage; exit 2; }
            REPORT_PATH="$2"
            shift 2
            ;;
        --keep-log)
            KEEP_LOG=true
            shift
            ;;
        --plain)
            export MASCARADE_TUI_MODE=plain
            shift
            ;;
        --yes)
            AUTO_YES=true
            shift
            ;;
        -v|--verbose)
            VERBOSE=true
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            err "Argument inconnu: $1"
            usage
            exit 2
            ;;
    esac
done

ensure_targets
tmp_log="$(mktemp "${TMPDIR:-/tmp}/repo-deep-analysis.XXXXXX")"
log_event "action=$ACTION targets=${TARGET_REPOS[*]}"

if [[ "$ACTION" == "status" ]]; then
    section "Repo Deep Analysis Status"
    info "Targets: ${TARGET_REPOS[*]}"
    info "Log temporaire: $tmp_log"
    ok "Aucun audit execute en mode status."
    exit 0
fi

banner
section "Repo Deep Analysis"
info "Targets: ${TARGET_REPOS[*]}"
info "Mode TUI: ${MASCARADE_TUI_MODE:-auto}"

if [[ "$AUTO_YES" != true ]]; then
    confirm "Lancer l'audit documentaire et structurel des repos cibles ?" || {
        warn "Audit annule."
        exit 1
    }
fi

if [[ -z "$REPORT_PATH" ]]; then
    REPORT_PATH="$REPO_DIR/docs/audit/MULTI_REPO_BASELINE_$(date +%F).md"
fi
mkdir -p "$(dirname "$REPORT_PATH")"
rm -f "$REPORT_PATH"

{
    echo "# Multi-Repo Baseline — $(date +%F)"
    echo
    echo "- Generated by: \`scripts/repo_deep_analysis_tui.sh\`"
    echo "- Targets: \`${TARGET_REPOS[*]}\`"
    echo "- Operator root: \`$REPO_DIR\`"
    echo
} >> "$REPORT_PATH"

for repo_name in "${TARGET_REPOS[@]}"; do
    root="$(repo_root "$repo_name")" || { warn "Repo non resolu: $repo_name"; continue; }
    section "Analyse $repo_name"
    info "$root"
    write_repo_section "$repo_name" "$root" "$REPORT_PATH"
    ok "Section ecrite pour $repo_name"
done

section "Synthese"
ok "Rapport cree: $REPORT_PATH"
if [[ "$KEEP_LOG" == true ]]; then
    info "Log conserve: $tmp_log"
else
    info "Log temporaire relu puis supprime a la sortie."
fi
