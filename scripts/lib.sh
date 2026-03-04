#!/usr/bin/env bash
# scripts/lib.sh — Bibliotheque TUI partagee pour Mascarade
# Source par setup, update, config

# ── Strict mode ──
set -euo pipefail

# ── Repertoire racine ──
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[1]:-${BASH_SOURCE[0]}}")/.." 2>/dev/null && pwd || cd "$(dirname "$0")/.." && pwd)"

# ── Couleurs (respect NO_COLOR) ──
if [[ -z "${NO_COLOR:-}" ]] && [[ -t 1 ]]; then
    BOLD='\033[1m'
    DIM='\033[2m'
    RED='\033[0;31m'
    GREEN='\033[0;32m'
    YELLOW='\033[0;33m'
    CYAN='\033[0;36m'
    MAGENTA='\033[0;35m'
    WHITE='\033[1;37m'
    NC='\033[0m'
else
    BOLD='' DIM='' RED='' GREEN='' YELLOW='' CYAN='' MAGENTA='' WHITE='' NC=''
fi

# ── Logging ──
line()    { echo -e "${DIM}  ──────────────────────────────────────────${NC}"; }
log()     { echo -e "  ${CYAN}▸${NC} $*"; }
ok()      { echo -e "  ${GREEN}✓${NC} $*"; }
warn()    { echo -e "  ${YELLOW}!${NC} $*"; }
err()     { echo -e "  ${RED}✗${NC} $*" >&2; }
info()    { echo -e "  ${DIM}$*${NC}"; }
section() { echo ""; echo -e "  ${MAGENTA}${BOLD}$*${NC}"; line; }

# ── Banner ──
banner() {
    echo ""
    cat << 'ART'
    ╔╦╗╔═╗╔═╗╔═╗╔═╗╦═╗╔═╗╔╦╗╔═╗
    ║║║╠═╣╚═╗║  ╠═╣╠╦╝╠═╣ ║║║╣
    ╩ ╩╩ ╩╚═╝╚═╝╩ ╩╩╚═╩ ╩═╩╝╚═╝
ART
    echo -e "    ${DIM}Orchestration LLM agentic${NC}"
    echo ""
}

# ── Confirmation ──
confirm() {
    local prompt="${1:-Continuer ?}"
    echo -ne "  ${YELLOW}?${NC} ${prompt} ${DIM}[O/n]${NC} " >&2
    read -r answer
    case "${answer,,}" in
        ""|o|y|oui|yes) return 0 ;;
        *) return 1 ;;
    esac
}

# ── Input standard ──
input_value() {
    local prompt="$1" default="${2:-}"
    echo -ne "  ${YELLOW}?${NC} ${prompt} ${DIM}[${default}]${NC} " >&2
    read -r value
    echo "${value:-$default}"
}

# ── Input secret (masque) ──
input_secret() {
    local prompt="$1" default="${2:-}" masked=""
    if [[ -n "$default" ]]; then
        local len=${#default}
        if (( len > 12 )); then
            masked="${default:0:8}...${default: -4}"
        else
            masked="***"
        fi
    fi
    echo -ne "  ${YELLOW}?${NC} ${prompt} ${DIM}[${masked:-vide}]${NC} " >&2
    read -rs value
    echo "" >&2
    echo "${value:-$default}"
}

# ── Menu selection unique (fleches + enter) ──
# Usage : menu_select "Titre ?" "Option 1" "Option 2" "Option 3"
# Resultat dans $MENU_RESULT (index 0-based)
MENU_RESULT=0
menu_select() {
    local title="$1"; shift
    local options=("$@")
    local selected=0
    local count=${#options[@]}

    tput civis 2>/dev/null || true
    trap 'tput cnorm 2>/dev/null || true' RETURN

    while true; do
        echo -e "\n  ${BOLD}$title${NC}\n"
        for i in "${!options[@]}"; do
            if [[ $i -eq $selected ]]; then
                echo -e "  ${CYAN}${BOLD} ▶ ${options[$i]} ${NC}"
            else
                echo -e "  ${DIM}   ${options[$i]}${NC}"
            fi
        done
        echo -e "\n  ${DIM}↑/↓ naviguer, Entree valider${NC}"

        read -rsn1 key
        if [[ "$key" == $'\e' ]]; then read -rsn2 seq; key="$seq"; fi
        case "$key" in
            '[A') ((selected > 0)) && ((selected--)) || true ;;
            '[B') ((selected < count - 1)) && ((selected++)) || true ;;
            '') break ;;
        esac

        tput cuu $((count + 4)) 2>/dev/null || true
        for ((i = 0; i < count + 4; i++)); do
            tput el 2>/dev/null || true; tput cud1 2>/dev/null || true
        done
        tput cuu $((count + 4)) 2>/dev/null || true
    done
    MENU_RESULT=$selected
}

# ── Checkbox multi-select (fleches + espace + enter) ──
# Usage : checkbox_select
# Requiert SVC_IDS, SVC_LABEL, SVC_DESC, SVC_CAT, SVC_ON deja definis
checkbox_select() {
    local current_cat=""
    local display_ids=()
    local cat_lines=0

    # Compter lignes totales (categories + services)
    for id in "${SVC_IDS[@]}"; do
        local cat="${SVC_CAT[$id]}"
        if [[ "$cat" != "$current_cat" ]]; then
            current_cat="$cat"
            ((cat_lines++)) || true
        fi
        display_ids+=("$id")
    done
    local count=${#display_ids[@]}
    local total_lines=$((count + cat_lines + 5))
    local selected=0

    tput civis 2>/dev/null || true
    trap 'tput cnorm 2>/dev/null || true' RETURN

    while true; do
        current_cat=""
        local line_idx=0
        echo -e "\n  ${BOLD}Services a installer${NC} ${DIM}(Espace=toggle, a=tous, n=aucun, Entree=valider)${NC}\n"

        for i in "${!display_ids[@]}"; do
            local id="${display_ids[$i]}"
            local cat="${SVC_CAT[$id]}"

            if [[ "$cat" != "$current_cat" ]]; then
                current_cat="$cat"
                local cat_label
                case "$cat" in
                    mascarade) cat_label="Mascarade" ;;
                    tools) cat_label="Outils" ;;
                    infra) cat_label="Infrastructure" ;;
                    *) cat_label="$cat" ;;
                esac
                echo -e "  ${MAGENTA}${BOLD}── ${cat_label} ──${NC}"
            fi

            local check=" "
            [[ "${SVC_ON[$id]}" == "1" ]] && check="${GREEN}✓${NC}"
            local port_info=""
            [[ "${SVC_PORT[$id]}" != "—" ]] && port_info=" ${DIM}:${SVC_PORT[$id]}${NC}"

            if [[ $i -eq $selected ]]; then
                echo -e "  ${CYAN}${BOLD} ▶ [${check}${CYAN}${BOLD}] ${SVC_LABEL[$id]}${port_info} ${DIM}— ${SVC_DESC[$id]}${NC}"
            else
                echo -e "  ${DIM}   [${check}${DIM}] ${SVC_LABEL[$id]}${port_info} — ${SVC_DESC[$id]}${NC}"
            fi
        done

        local sel_count=0
        for id in "${SVC_IDS[@]}"; do
            [[ "${SVC_ON[$id]}" == "1" ]] && ((sel_count++)) || true
        done
        echo -e "\n  ${DIM}${sel_count} service(s) selectionne(s)${NC}"

        read -rsn1 key
        if [[ "$key" == $'\e' ]]; then read -rsn2 seq; key="$seq"; fi
        case "$key" in
            '[A') ((selected > 0)) && ((selected--)) || true ;;
            '[B') ((selected < count - 1)) && ((selected++)) || true ;;
            ' ')
                local tid="${display_ids[$selected]}"
                if [[ "${SVC_ON[$tid]}" == "1" ]]; then
                    SVC_ON[$tid]="0"
                else
                    SVC_ON[$tid]="1"
                fi
                ;;
            a) for id in "${SVC_IDS[@]}"; do SVC_ON[$id]="1"; done ;;
            n) for id in "${SVC_IDS[@]}"; do SVC_ON[$id]="0"; done ;;
            '') break ;;
        esac

        tput cuu "$total_lines" 2>/dev/null || true
        for ((i = 0; i < total_lines; i++)); do
            tput el 2>/dev/null || true; tput cud1 2>/dev/null || true
        done
        tput cuu "$total_lines" 2>/dev/null || true
    done
}

# ── Spinner (background) ──
_SPIN_PID=""
spin_start() {
    local msg="${1:-Chargement...}"
    {
        local chars='⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏'
        local i=0
        while true; do
            printf "\r  ${CYAN}%s${NC} %s" "${chars:i%10:1}" "$msg" >&2
            ((i++)) || true
            sleep 0.1
        done
    } &
    _SPIN_PID=$!
    disown "$_SPIN_PID" 2>/dev/null || true
}

spin_stop() {
    local success="${1:-true}"
    if [[ -n "$_SPIN_PID" ]]; then
        kill "$_SPIN_PID" 2>/dev/null || true
        wait "$_SPIN_PID" 2>/dev/null || true
        _SPIN_PID=""
    fi
    printf "\r\033[K" >&2
}

# ── Progress bar ──
# Usage : step_progress 4 7 "Configuration .env"
step_progress() {
    local current="$1" total="$2" label="$3"
    local width=36
    local filled=$(( current * width / total ))
    local empty=$(( width - filled ))
    local bar=""
    for ((i=0; i<filled; i++)); do bar+="━"; done
    for ((i=0; i<empty; i++)); do bar+="╌"; done

    echo ""
    echo -e "  ${CYAN}${bar}${NC} ${BOLD}${current}/${total}${NC}"
    echo -e "  ${CYAN}▸${NC} ${label}"
    echo ""
}

# ── Health check avec retry ──
# Usage : health_check "http://localhost:8100/health" "Core" 10 2
health_check() {
    local url="$1" name="$2" retries="${3:-10}" delay="${4:-2}"
    for ((i=1; i<=retries; i++)); do
        if curl -sf --max-time 5 "$url" > /dev/null 2>&1; then
            ok "${name} operationnel"
            return 0
        fi
        sleep "$delay"
    done
    warn "${name} ne repond pas apres $((retries * delay))s"
    return 1
}

# ── Docker container status ──
# Usage : docker_status "mascarade-core-1" → "running" / "stopped" / "absent"
docker_status() {
    local name="$1"
    local state
    state=$(docker inspect --format='{{.State.Status}}' "$name" 2>/dev/null || echo "absent")
    echo "$state"
}

# ── Port availability check ──
port_available() {
    local port="$1"
    if ss -tlnp 2>/dev/null | grep -q ":${port} "; then
        return 1  # port in use
    fi
    return 0
}

# ── Backup file before overwrite ──
backup_file() {
    local file="$1"
    if [[ -f "$file" ]]; then
        local backup="${file}.bak.$(date +%s)"
        cp "$file" "$backup"
        info "Backup : $backup"
    fi
}

# ── Service status table ──
# Usage : show_status_table (uses SVC_IDS, SVC_LABEL, SVC_PORT, SVC_ON)
show_status_table() {
    printf "\n  ${BOLD}%-18s %-7s %-12s %-30s${NC}\n" "Service" "Port" "Statut" "Image"
    line
    for id in "${SVC_IDS[@]}"; do
        [[ "${SVC_ON[$id]}" != "1" ]] && continue
        local port="${SVC_PORT[$id]}"
        local container
        container=$(docker compose -f "$REPO_DIR/docker-compose.yml" ps --format '{{.Name}}' 2>/dev/null | grep -i "$id" | head -1 || true)
        local status="○ Absent"
        local status_color="$DIM"
        local image="-"

        if [[ -n "$container" ]]; then
            local state
            state=$(docker inspect --format='{{.State.Status}}' "$container" 2>/dev/null || echo "absent")
            image=$(docker inspect --format='{{.Config.Image}}' "$container" 2>/dev/null | sed 's|.*/||' || echo "-")
            case "$state" in
                running) status="● Running"; status_color="$GREEN" ;;
                exited)  status="○ Stopped"; status_color="$YELLOW" ;;
                *)       status="◌ $state"; status_color="$RED" ;;
            esac
        fi
        printf "  %-18s %-7s ${status_color}%-12s${NC} ${DIM}%-30s${NC}\n" \
            "${SVC_LABEL[$id]}" "$port" "$status" "$image"
    done
    echo ""
}

# ── Load existing .env into variables ──
load_env() {
    local env_file="${1:-$REPO_DIR/.env}"
    if [[ -f "$env_file" ]]; then
        while IFS='=' read -r key value; do
            [[ -z "$key" || "$key" == \#* ]] && continue
            key="${key%%[[:space:]]}"
            value="${value##[[:space:]]}"
            value="${value%\"}" ; value="${value#\"}"
            value="${value%\'}" ; value="${value#\'}"
            [[ "$key" =~ ^[A-Z][A-Z0-9_]*$ ]] || continue
            printf -v "$key" '%s' "$value" 2>/dev/null || true
        done < "$env_file"
        return 0
    fi
    return 1
}
