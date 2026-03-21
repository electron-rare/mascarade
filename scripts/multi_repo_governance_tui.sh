#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib.sh"

setup_trap

ACTION="run"
AUTO_YES=false
KEEP_LOG=false
REPORT_PATH=""
LOG_SUMMARY_PATH=""
TODAY="$(date +%F)"
declare -a TARGET_REPOS=()

declare -A REPO_ROOTS=(
    [agent-factory-cockpit]="/Users/electron/agent-factory-cockpit"
    [crazy_life]="/Users/electron/crazy_life"
    [Kill_LIFE]="/Users/electron/Kill_LIFE"
    [mascarade]="/Users/electron/mascarade"
    [mascarade-api-deps]="/Users/electron/mascarade-api-deps"
    [mascarade-apple-coreml]="/Users/electron/mascarade-apple-coreml"
    [mascarade-frontend-pr]="/Users/electron/mascarade-frontend-pr"
    [mascarade-main]="/Users/electron/mascarade-main"
)

usage() {
    cat <<'EOF'
Usage: bash scripts/multi_repo_governance_tui.sh [run|repair|status] [options]

Audit et maintenance documentaire multi-repo (spec, diagrams, feature maps, plans, README).

Actions:
  run      audit uniquement
  repair   audit + creation des artefacts manquants
  status   affiche les cibles sans executer

Options:
  --repo <name>     cible un repo (utilisable plusieurs fois), ou all
  --out <path>      chemin de rapport markdown
  --log-summary <path>  chemin de synthese logs markdown
  --keep-log        conserve les logs temporaires
  --plain           force le mode non-TUI
  --yes             evite la confirmation interactive
  -v, --verbose     traces debug
  -h, --help        aide
EOF
}

normalize_repo_name() {
    local name="$1"
    case "$name" in
        all) echo "all" ;;
        agent-factory-cockpit|crazy_life|Kill_LIFE|mascarade|mascarade-api-deps|mascarade-apple-coreml|mascarade-frontend-pr|mascarade-main)
            echo "$name"
            ;;
        *) return 1 ;;
    esac
}

ensure_targets() {
    if [[ ${#TARGET_REPOS[@]} -eq 0 ]]; then
        TARGET_REPOS=(agent-factory-cockpit crazy_life Kill_LIFE mascarade mascarade-api-deps mascarade-apple-coreml mascarade-frontend-pr mascarade-main)
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
    matches="$(rg -l --glob '*.md' --glob '*.mmd' --glob '*.puml' --glob '!**/.git/**' --glob '!node_modules/**' --glob '!dist/**' --glob '!build/**' "$pattern" "$repo" || true)"
    if [[ -z "$matches" ]]; then
        echo "0"
    else
        printf '%s\n' "$matches" | wc -l | tr -d ' '
    fi
}

has_file() {
    [[ -f "$1" ]] && echo "yes" || echo "no"
}

ensure_repo_exists() {
    local root="$1"
    if [[ ! -d "$root" ]]; then
        mkdir -p "$root"
        log_event "repo_created root=$root"
    fi
}

ensure_readme() {
    local repo_name="$1" root="$2"
    if [[ ! -f "$root/README.md" ]]; then
        cat > "$root/README.md" <<EOF
# $repo_name

Ce depot est gere via la gouvernance multi-repo.

## Objectif
- clarifier le role du depot
- centraliser les spec minimales et la cartographie fonctionnelle
- maintenir un plan de taches enchainables

## Artefacts
- docs/REPO_SPEC_$TODAY.md
- docs/FEATURE_MAP_$TODAY.md
- docs/RUNTIME_SEQUENCE_$TODAY.md
- docs/AGENT_ASSIGNMENT_$TODAY.md
- docs/TODO_CHAIN_$TODAY.md
EOF
        log_event "created repo=$repo_name file=README.md"
    fi
}

ensure_plan() {
    local repo_name="$1" root="$2"
    local plan_file="$root/plan.md"
    if [[ "$repo_name" == "Kill_LIFE" ]]; then
        return 0
    fi
    if [[ ! -f "$plan_file" ]]; then
        cat > "$plan_file" <<EOF
# Plan - $repo_name - $TODAY

## But
Mettre le depot en posture operationnelle continue avec spec, feature map, sequence et backlog chainable.

## Lots
1. Documentation critique (spec + diagrammes)
2. Alignement README et conventions
3. Correctifs scripts et hygiene
4. Tests et validation

## Criteres de sortie
- artefacts minimaux presents
- TODO chaines priorises
- rapport d'analyse mis a jour
EOF
        log_event "created repo=$repo_name file=plan.md"
    fi
}

ensure_spec_doc() {
    local repo_name="$1" root="$2"
    local spec_count
    spec_count="$(count_files "$root" '(^|/)(specs/|SPEC_.*\.md$|.*_SPEC\.md$)')"
    if [[ "$spec_count" == "0" ]]; then
        mkdir -p "$root/docs"
        local f="$root/docs/REPO_SPEC_$TODAY.md"
        if [[ ! -f "$f" ]]; then
            cat > "$f" <<EOF
# Spec Repo - $repo_name

## Exigences
- Le depot MUST documenter son role et ses interfaces principales.
- Le depot MUST maintenir un backlog executable.
- Le depot SHOULD fournir un diagramme de sequence runtime.
- Le depot SHOULD fournir une carte de fonctionnalites.
- Le depot MAY deleguer des details techniques aux docs specialisees.

## Acceptance Criteria
- README present et coherent.
- Plan de travail accessible.
- Diagramme Mermaid de sequence disponible.
- Carte fonctionnelle Mermaid disponible.
EOF
            log_event "created repo=$repo_name file=docs/REPO_SPEC_$TODAY.md"
        fi
    fi
}

ensure_sequence_doc() {
    local repo_name="$1" root="$2"
    local seq_count
    seq_count="$(count_match_files "$root" 'sequenceDiagram|diagramme de sequence|sequence diagram')"
    if [[ "$seq_count" == "0" ]]; then
        mkdir -p "$root/docs"
        local f="$root/docs/RUNTIME_SEQUENCE_$TODAY.md"
        if [[ ! -f "$f" ]]; then
            cat > "$f" <<EOF
# Runtime Sequence - $repo_name

\`\`\`mermaid
sequenceDiagram
    participant User as Operateur
    participant Repo as Repo Runtime
    participant API as Surface API
    participant Core as Moteur Core
    participant Logs as Journaux

    User->>Repo: lancer action
    Repo->>API: valider entree
    API->>Core: executer logique
    Core-->>API: resultat + metriques
    API-->>Repo: reponse structuree
    Repo->>Logs: ecrire evidence et statut
\`\`\`
EOF
            log_event "created repo=$repo_name file=docs/RUNTIME_SEQUENCE_$TODAY.md"
        fi
    fi
}

ensure_feature_map_doc() {
    local repo_name="$1" root="$2"
    local fmap_count
    fmap_count="$(count_match_files "$root" 'feature map|functional map|carte de fonctionnal|fonctionnalites principales|workflow registry')"
    if [[ "$fmap_count" == "0" ]]; then
        mkdir -p "$root/docs"
        local f="$root/docs/FEATURE_MAP_$TODAY.md"
        if [[ ! -f "$f" ]]; then
            cat > "$f" <<EOF
# Feature Map - $repo_name

\`\`\`mermaid
flowchart TD
    A[Entrants] --> B[Validation]
    B --> C[Orchestration]
    C --> D[Execution]
    D --> E[Observabilite]
    E --> F[Backlog et amelioration continue]
\`\`\`

## Surfaces
- Entrants: API, scripts, UI ou CLI
- Validation: schema, auth, garde-fous
- Orchestration: routeur, agents, workflows
- Execution: services coeur
- Observabilite: logs, traces, evidence
- Continuite: TODO, plan, priorisation
EOF
            log_event "created repo=$repo_name file=docs/FEATURE_MAP_$TODAY.md"
        fi
    fi
}

ensure_agent_assignment_doc() {
    local repo_name="$1" root="$2"
    mkdir -p "$root/docs"
    local f="$root/docs/AGENT_ASSIGNMENT_$TODAY.md"
    if [[ ! -f "$f" ]]; then
        cat > "$f" <<EOF
# Agent Assignment - $repo_name

## Agents
- architect_agent: architecture et decoupage lots
- qa_agent: tests, risques, non-regression
- doc_agent: coherence README, spec, runbooks
- Explore (subagent): exploration rapide read-only

## Competences
- spec-first, diagrammes Mermaid, backlog chainable
- hygiene scripts shell + logs
- analyse code orientee corrections faibles risques

## Taches initiales
1. verifier ecarts doc/plan/todo
2. traiter correctifs P0/P1 faibles risques
3. valider commandes de test
4. publier evidence de verification
EOF
        log_event "created repo=$repo_name file=docs/AGENT_ASSIGNMENT_$TODAY.md"
    fi
}

ensure_todo_chain_doc() {
    local repo_name="$1" root="$2"
    mkdir -p "$root/docs"
    local f="$root/docs/TODO_CHAIN_$TODAY.md"
    if [[ ! -f "$f" ]]; then
        cat > "$f" <<EOF
# TODO Chain - $repo_name - $TODAY

- [ ] cloturer gaps documentaires critiques
- [ ] corriger chemins/scripts fragiles
- [ ] executer tests minimaux et capturer resultats
- [ ] reviser README et references
- [ ] programmer le lot suivant
EOF
        log_event "created repo=$repo_name file=docs/TODO_CHAIN_$TODAY.md"
    fi
}

write_repo_section() {
    local repo_name="$1" root="$2" report="$3"
    local branch dirty readme manifest plan spec_dirs spec_files sequence_count feature_count mermaid_count tests shell_count py_count ts_count

    branch="$(git -C "$root" branch --show-current 2>/dev/null || echo '?')"
    dirty="$(git -C "$root" status --short 2>/dev/null | wc -l | tr -d ' ' || echo '0')"
    readme="$(has_file "$root/README.md")"
    manifest="$(has_file "$root/MANIFEST.md")"
    plan="$(has_file "$root/plan.md")"
    spec_dirs="$(find "$root" -maxdepth 2 -type d -name specs 2>/dev/null | wc -l | tr -d ' ')"
    spec_files="$(count_files "$root" '(SPEC_.*\.md$|.*_SPEC\.md$)')"
    sequence_count="$(count_match_files "$root" 'sequenceDiagram|diagramme de sequence|sequence diagram')"
    feature_count="$(count_match_files "$root" 'feature map|functional map|carte de fonctionnal|fonctionnalites principales|workflow registry')"
    mermaid_count="$(count_match_files "$root" '```mermaid|flowchart|graph TD|sequenceDiagram')"
    tests="$(count_files "$root" '(^|/)(test_.*\.py|.*\.test\.(ts|tsx|js)|.*spec\.(ts|tsx|js)|tests?/.*)$')"
    shell_count="$(count_files "$root" '\.sh$')"
    py_count="$(count_files "$root" '\.py$')"
    ts_count="$(count_files "$root" '\.(ts|tsx)$')"

    log_event "repo=$repo_name branch=$branch dirty=$dirty readme=$readme manifest=$manifest plan=$plan spec_dirs=$spec_dirs spec_files=$spec_files sequence=$sequence_count feature=$feature_count mermaid=$mermaid_count tests=$tests sh=$shell_count py=$py_count ts=$ts_count"

    {
        echo "## $repo_name"
        echo
        echo "- Root: $root"
        echo "- Branch: $branch"
        echo "- Dirty entries: $dirty"
        echo
        echo "| Metric | Value |"
        echo "| --- | --- |"
        echo "| README | $readme |"
        echo "| MANIFEST | $manifest |"
        echo "| Plan | $plan |"
        echo "| Spec dirs | $spec_dirs |"
        echo "| Spec files | $spec_files |"
        echo "| Sequence docs | $sequence_count |"
        echo "| Feature-map docs | $feature_count |"
        echo "| Mermaid docs | $mermaid_count |"
        echo "| Test files | $tests |"
        echo "| Shell scripts | $shell_count |"
        echo "| Python files | $py_count |"
        echo "| TS/TSX files | $ts_count |"
        echo
        echo "### Next actions"
        if [[ "$readme" == "no" || "$plan" == "no" || "$sequence_count" == "0" || "$feature_count" == "0" ]]; then
            echo "- Gaps detectes: appliquer action repair pour generer les artefacts minimas."
        else
            echo "- Baseline documentaire presente: passer aux correctifs code et tests."
        fi
        echo
    } >> "$report"
}

write_log_summary() {
    local summary_path="$1"
    local created_count updated_count

    created_count="$(rg -n "created repo=" "$tmp_log" | wc -l | tr -d ' ')"
    updated_count="$(rg -n "repo=.*" "$tmp_log" | wc -l | tr -d ' ')"

    cat > "$summary_path" <<EOF
# Log Summary - $TODAY

- Source log: $tmp_log
- Entries: $(wc -l < "$tmp_log" | tr -d ' ')
- Creations: $created_count
- Repo metrics lines: $updated_count

## Extraits
$(tail -n 40 "$tmp_log")
EOF
}

run_repair_for_repo() {
    local repo_name="$1" root="$2"
    ensure_repo_exists "$root"
    ensure_readme "$repo_name" "$root"
    ensure_plan "$repo_name" "$root"
    ensure_spec_doc "$repo_name" "$root"
    ensure_sequence_doc "$repo_name" "$root"
    ensure_feature_map_doc "$repo_name" "$root"
    ensure_agent_assignment_doc "$repo_name" "$root"
    ensure_todo_chain_doc "$repo_name" "$root"
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        run|repair|status)
            ACTION="$1"
            shift
            ;;
        --repo)
            [[ $# -lt 2 ]] && { err "--repo requiert une valeur"; usage; exit 2; }
            normalized="$(normalize_repo_name "$2")" || { err "Repo inconnu: $2"; exit 2; }
            if [[ "$normalized" == "all" ]]; then
                TARGET_REPOS=(agent-factory-cockpit crazy_life Kill_LIFE mascarade mascarade-api-deps mascarade-apple-coreml mascarade-frontend-pr mascarade-main)
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
        --log-summary)
            [[ $# -lt 2 ]] && { err "--log-summary requiert un chemin"; usage; exit 2; }
            LOG_SUMMARY_PATH="$2"
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
tmp_log="$(mktemp "${TMPDIR:-/tmp}/multi-repo-governance.XXXXXX")"
log_event "action=$ACTION targets=${TARGET_REPOS[*]}"

if [[ "$ACTION" == "status" ]]; then
    section "Multi-Repo Governance Status"
    info "Targets: ${TARGET_REPOS[*]}"
    info "Log temporaire: $tmp_log"
    ok "Aucune execution en mode status."
    exit 0
fi

banner
section "Multi-Repo Governance"
info "Action: $ACTION"
info "Targets: ${TARGET_REPOS[*]}"
info "Mode TUI: ${MASCARADE_TUI_MODE:-auto}"

if [[ "$AUTO_YES" != true ]]; then
    confirm "Executer l'audit multi-repo et la maintenance documentaire ?" || {
        warn "Operation annulee."
        exit 1
    }
fi

if [[ -z "$REPORT_PATH" ]]; then
    REPORT_PATH="$REPO_DIR/docs/audit/MULTI_REPO_GOVERNANCE_$TODAY.md"
fi
mkdir -p "$(dirname "$REPORT_PATH")"
rm -f "$REPORT_PATH"

{
    echo "# Multi-Repo Governance - $TODAY"
    echo
    echo "- Generated by: scripts/multi_repo_governance_tui.sh"
    echo "- Action: $ACTION"
    echo "- Targets: ${TARGET_REPOS[*]}"
    echo "- Operator root: $REPO_DIR"
    echo
} >> "$REPORT_PATH"

for repo_name in "${TARGET_REPOS[@]}"; do
    root="${REPO_ROOTS[$repo_name]}"
    section "Analyse $repo_name"
    info "$root"

    if [[ "$ACTION" == "repair" ]]; then
        run_repair_for_repo "$repo_name" "$root"
        ok "Repair applique pour $repo_name"
    fi

    write_repo_section "$repo_name" "$root" "$REPORT_PATH"
    ok "Section ecrite pour $repo_name"
done

if [[ -n "$LOG_SUMMARY_PATH" ]]; then
    mkdir -p "$(dirname "$LOG_SUMMARY_PATH")"
    write_log_summary "$LOG_SUMMARY_PATH"
    ok "Synthese logs ecrite: $LOG_SUMMARY_PATH"
fi

section "Synthese"
ok "Rapport cree: $REPORT_PATH"
if [[ "$KEEP_LOG" == true ]]; then
    info "Log conserve: $tmp_log"
else
    info "Log relu et supprime en sortie."
fi
