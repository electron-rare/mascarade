#!/usr/bin/env bash
# scripts/lib.sh — Bibliotheque TUI partagee pour Mascarade
# Source par setup, update, config
# Utilise gum (charmbracelet) pour les composants interactifs

# ── Strict mode ──
set -euo pipefail

# ── Repertoire racine ──
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

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

# ── Verbose mode ──
VERBOSE="${VERBOSE:-false}"

# ── Logging ──
line()    { echo -e "${DIM}  ──────────────────────────────────────────${NC}"; }
log()     { echo -e "  ${CYAN}▸${NC} $*"; }
ok()      { echo -e "  ${GREEN}✓${NC} $*"; }
warn()    { echo -e "  ${YELLOW}!${NC} $*"; }
err()     { echo -e "  ${RED}✗${NC} $*" >&2; }
info()    { echo -e "  ${DIM}$*${NC}"; }
section() { echo ""; echo -e "  ${MAGENTA}${BOLD}$*${NC}"; line; }
dbg()     { [[ "$VERBOSE" == true ]] && echo -e "  ${DIM}[dbg]${NC} $*" >&2 || true; }

# ── Args communs (appeler dans chaque script) ──
# Usage : parse_args "setup" "Description." "$@"
parse_args() {
    local script_name="$1" description="$2"; shift 2
    dbg "parse_args: script=$script_name argc=$#"
    for arg in "$@"; do
        case "$arg" in
            -v|--verbose) VERBOSE=true; dbg "Mode verbose active" ;;
            -h|--help)
                echo "Usage: ./$script_name [--verbose|-v]"
                echo ""
                echo "$description"
                echo ""
                echo "Options :"
                echo "  -v, --verbose   Afficher les traces de debug"
                exit 0
                ;;
            *) dbg "  arg ignore: '$arg'" ;;
        esac
    done
}

# ── Easter eggs — taglines du MANIFEST ──
_TAGLINES=(
    "Don't Panic. — H2G2"
    "42 secondes si tu es presse"
    "L'electron rare — unstable by design"
    "Un agent peut-il rever de conformite ?"
    "Si tu vois un plasma violet, c'est que tu es dans le groove."
    "KEEP THE BEAT — BPM 125"
    "Ce projet a ete valide par un oscilloscope et une IA"
    "Si tu rates un bouton, c'est que tu danses trop fort."
    "Bienvenue dans le cockpit le plus funky du multivers!"
    "J'ai vu des evidence packs briller dans l'obscurite..."
    "Vous avez la frequence — KEEP THE BEAT"
    "Orchestration LLM agentic — groove edition"
    "Si un enfant demande 'c'est quoi un ion ?', c'est un electron qui a trop fait la fete !"
    "MoldBot → MoltBot → ClawdBot → OpenClaw → Mascarade"
)

_random_tagline() {
    echo "${_TAGLINES[RANDOM % ${#_TAGLINES[@]}]}"
}

# ── Gum detection & installation ──
# Cached flag — evite de forker command -v a chaque appel TUI
_GUM_AVAILABLE=false

_has_tty() { [[ -t 0 && -t 1 ]]; }
_has_gum() { [[ "$_GUM_AVAILABLE" == true ]] && _has_tty; }

_detect_gum() {
    if command -v gum &>/dev/null; then
        _GUM_AVAILABLE=true
        dbg "gum detecte: $(command -v gum) version=$(gum --version 2>/dev/null || echo '?')"
    else
        _GUM_AVAILABLE=false
        dbg "gum non trouve dans PATH"
    fi
}

ensure_gum() {
    _detect_gum
    if _has_gum; then
        dbg "gum deja disponible, skip installation"
        return 0
    fi

    echo -e "  ${CYAN}▸${NC} Installation de gum (TUI toolkit)..."
    local sudo_cmd=""
    [[ $EUID -ne 0 ]] && command -v sudo &>/dev/null && sudo_cmd="sudo"
    dbg "ensure_gum: sudo_cmd='$sudo_cmd' EUID=$EUID"

    local pkg_mgr="unknown"
    if command -v apt-get &>/dev/null; then
        pkg_mgr="apt"
        dbg "Installation gum via apt..."
        $sudo_cmd mkdir -p /etc/apt/keyrings 2>/dev/null || true
        if ! curl -fsSL https://repo.charm.sh/apt/gpg.key | $sudo_cmd gpg --dearmor -o /etc/apt/keyrings/charm.gpg 2>/dev/null; then
            warn "Import GPG charm echoue"
            dbg "gpg --dearmor FAILED"
        fi
        echo "deb [signed-by=/etc/apt/keyrings/charm.gpg] https://repo.charm.sh/apt/ * *" | \
            $sudo_cmd tee /etc/apt/sources.list.d/charm.list > /dev/null
        $sudo_cmd apt-get update -qq >/dev/null 2>&1 || true
        $sudo_cmd apt-get install -y -qq gum >/dev/null 2>&1 || true
    elif command -v dnf &>/dev/null || command -v yum &>/dev/null; then
        local mgr="dnf"
        command -v dnf &>/dev/null || mgr="yum"
        pkg_mgr="$mgr"
        dbg "Installation gum via $mgr..."
        echo '[charm]
name=Charm
baseurl=https://repo.charm.sh/yum/
enabled=1
gpgcheck=1
gpgkey=https://repo.charm.sh/yum/gpg.key' | $sudo_cmd tee /etc/yum.repos.d/charm.repo > /dev/null
        $sudo_cmd "$mgr" install -y gum >/dev/null 2>&1 || true
    elif command -v pacman &>/dev/null; then
        pkg_mgr="pacman"
        dbg "Installation gum via pacman..."
        $sudo_cmd pacman -S --noconfirm gum >/dev/null 2>&1 || true
    else
        pkg_mgr="binary"
        # Fallback : binaire direct depuis GitHub
        local arch
        arch=$(uname -m)
        dbg "Fallback binaire — arch=$arch"
        case "$arch" in
            x86_64)  arch="amd64" ;;
            aarch64) arch="arm64" ;;
        esac
        local tmp_dir ver="0.14.5"
        tmp_dir=$(mktemp -d)
        dbg "Telechargement gum v$ver pour $arch dans $tmp_dir..."
        if curl -fsSL "https://github.com/charmbracelet/gum/releases/download/v${ver}/gum_${ver}_Linux_${arch}.tar.gz" \
            -o "$tmp_dir/gum.tar.gz" 2>/dev/null; then
            tar -xzf "$tmp_dir/gum.tar.gz" -C "$tmp_dir" 2>/dev/null || true
            dbg "Contenu archive: $(ls "$tmp_dir/" 2>/dev/null)"
            $sudo_cmd install -m 755 "$tmp_dir/gum" /usr/local/bin/gum 2>/dev/null || \
                install -m 755 "$tmp_dir/gum" "$HOME/.local/bin/gum" 2>/dev/null || true
            export PATH="$HOME/.local/bin:$PATH"
        else
            dbg "curl telechargement gum FAILED"
        fi
        rm -rf "$tmp_dir"
    fi
    dbg "Installation tentee via $pkg_mgr"

    _detect_gum
    if _has_gum; then
        ok "gum installe"
        return 0
    else
        warn "gum non installe — fallback TUI basique"
        return 1
    fi
}

# Auto-install gum au chargement de lib.sh
ensure_gum 2>/dev/null || true

dbg "lib.sh charge — REPO_DIR=$REPO_DIR gum=$_GUM_AVAILABLE shell=$BASH_VERSION pid=$$ ppid=$PPID"
dbg "  uname=$(uname -srm) user=$USER home=$HOME"
dbg "  pwd=$(pwd) terminal=${TERM:-?} tty=$(tty 2>/dev/null || echo '?')"

# ── Theme gum (couleurs Mascarade) ──
export GUM_CHOOSE_CURSOR_FOREGROUND="212"
export GUM_CHOOSE_SELECTED_FOREGROUND="212"
export GUM_CHOOSE_HEADER_FOREGROUND="99"
export GUM_CONFIRM_PROMPT_FOREGROUND="212"
export GUM_INPUT_PROMPT_FOREGROUND="212"
export GUM_INPUT_CURSOR_FOREGROUND="212"
export GUM_FILTER_INDICATOR_FOREGROUND="212"

# ── Spinner (background) ──
_SPIN_PID=""
spin_start() {
    local msg="${1:-Chargement...}"
    dbg "spin_start: '$msg'"

    # Eviter la sortie illisible en mode verbose/non-interactif.
    if [[ "$VERBOSE" == true || ! -t 2 ]]; then
        info "$msg"
        _SPIN_PID=""
        return 0
    fi

    {
        local chars='⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏'
        local i=0
        while true; do
            printf "\r  \033[0;36m%s\033[0m %s" "${chars:i%10:1}" "$msg" >&2
            ((i++)) || true
            sleep 0.1
        done
    } &
    _SPIN_PID=$!
    disown "$_SPIN_PID" 2>/dev/null || true
    dbg "  spinner pid=$_SPIN_PID"
}

spin_stop() {
    if [[ -n "$_SPIN_PID" ]]; then
        dbg "spin_stop: kill $_SPIN_PID"
        kill "$_SPIN_PID" 2>/dev/null || true
        wait "$_SPIN_PID" 2>/dev/null || true
        _SPIN_PID=""
    fi
    printf "\r\033[K" >&2
}

# Cleanup spinner + cursor on exit/signal
_cleanup() {
    local rc=$?
    dbg "_cleanup: rc=$rc spin_pid=${_SPIN_PID:-none}"
    spin_stop 2>/dev/null || true
    tput cnorm 2>/dev/null || true
    return $rc
}
_cleanup_exit() {
    dbg "_cleanup_exit: signal recu, nettoyage..."
    _cleanup
    echo "" >&2
    exit 130
}
trap '_cleanup' EXIT
trap '_cleanup_exit' INT TERM HUP

# ── Banner ──
banner() {
    local tagline
    tagline=$(_random_tagline)
    dbg "banner: tagline='$tagline'"

    if _has_gum; then
        echo ""
        gum style \
            --border double \
            --border-foreground 212 \
            --padding "1 3" \
            --margin "0 2" \
            --foreground 212 \
            "╔╦╗╔═╗╔═╗╔═╗╔═╗╦═╗╔═╗╔╦╗╔═╗" \
            "║║║╠═╣╚═╗║  ╠═╣╠╦╝╠═╣ ║║║╣ " \
            "╩ ╩╩ ╩╚═╝╚═╝╩ ╩╩╚═╩ ╩═╩╝╚═╝"
        gum style --foreground 99 --italic --margin "0 4" "$tagline"
        echo ""
    else
        echo ""
        cat << 'ART'
    ╔╦╗╔═╗╔═╗╔═╗╔═╗╦═╗╔═╗╔╦╗╔═╗
    ║║║╠═╣╚═╗║  ╠═╣╠╦╝╠═╣ ║║║╣
    ╩ ╩╩ ╩╚═╝╚═╝╩ ╩╩╚═╩ ╩═╩╝╚═╝
ART
        echo -e "    ${DIM}${tagline}${NC}"
        echo ""
    fi
}

# ── Confirmation ──
confirm() {
    local prompt="${1:-Continuer ?}"
    dbg "confirm: '$prompt'"
    if _has_gum; then
        local rc=0
        gum confirm --default=yes \
            --affirmative "Oui" \
            --negative "Non" \
            "$prompt" || rc=$?
        dbg "  confirm rc=$rc (0=oui, 1=non, 130=ctrl-c)"
        [[ $rc -eq 130 ]] && _cleanup_exit
        return $rc
    else
        if ! _has_tty; then
            dbg "  confirm: non-tty -> oui par defaut"
            return 0
        fi
        echo -ne "  ${YELLOW}?${NC} ${prompt} ${DIM}[O/n]${NC} " >&2
        read -r answer || true
        dbg "  confirm reponse='$answer'"
        case "${answer,,}" in
            ""|o|y|oui|yes) return 0 ;;
            *) return 1 ;;
        esac
    fi
}

# ── Input standard ──
input_value() {
    local prompt="$1" default="${2:-}"
    dbg "input_value: '$prompt' default='$default'"
    if _has_gum; then
        local result rc=0
        result=$(gum input \
            --header "$prompt" \
            --value "$default" \
            --placeholder "$default" \
            --width 60) || rc=$?
        dbg "  input_value rc=$rc result='${result:-<vide>}'"
        [[ $rc -eq 130 ]] && _cleanup_exit
        # Esc (rc=1 + vide) → garder le default
        echo "${result:-$default}"
    else
        if ! _has_tty; then
            dbg "  input_value: non-tty -> default"
            echo "$default"
            return 0
        fi
        echo -ne "  ${YELLOW}?${NC} ${prompt} ${DIM}[${default}]${NC} " >&2
        read -r value || true
        dbg "  input_value reponse='${value:-<vide>}' → '${value:-$default}'"
        echo "${value:-$default}"
    fi
}

# ── Input secret (masque) ──
input_secret() {
    local prompt="$1" default="${2:-}"
    dbg "input_secret: '$prompt' (valeur ${default:+presente, ${#default} chars}${default:-vide})"
    # Masquage commun aux deux branches
    local masked=""
    if [[ -n "$default" ]]; then
        if (( ${#default} > 12 )); then
            masked="${default:0:8}...${default: -4}"
        else
            masked="***"
        fi
    fi
    if _has_gum; then
        local result rc=0
        result=$(gum input \
            --header "$prompt" \
            --password \
            --placeholder "${masked:-vide}" \
            --width 60) || rc=$?
        dbg "  input_secret rc=$rc result_len=${#result}"
        [[ $rc -eq 130 ]] && _cleanup_exit
        echo "${result:-$default}"
    else
        if ! _has_tty; then
            dbg "  input_secret: non-tty -> default"
            echo "$default"
            return 0
        fi
        echo -ne "  ${YELLOW}?${NC} ${prompt} ${DIM}[${masked:-vide}]${NC} " >&2
        read -rs value || true
        echo "" >&2
        dbg "  input_secret reponse_len=${#value}"
        echo "${value:-$default}"
    fi
}

# ── Menu selection unique ──
# Usage : menu_select "Titre ?" "Option 1" "Option 2" "Option 3"
# Resultat dans $MENU_RESULT (index 0-based)
MENU_RESULT=0
menu_select() {
    local title="$1"; shift
    local options=("$@")
    dbg "menu_select: '$title' (${#options[@]} options: ${options[*]})"

    if _has_gum; then
        local result rc=0
        result=$(gum choose --header "$title" "${options[@]}") || rc=$?
        dbg "  gum choose rc=$rc result='$result'"
        [[ $rc -eq 130 ]] && _cleanup_exit
        # Esc (rc=1 + vide) → sortie propre
        if [[ $rc -ne 0 && -z "$result" ]]; then
            dbg "menu_select: abandon (Esc, rc=$rc)"
            echo "" >&2
            info "Abandon"
            exit 0
        fi
        # Trouver l'index
        MENU_RESULT=0
        for i in "${!options[@]}"; do
            if [[ "${options[$i]}" == "$result" ]]; then
                MENU_RESULT=$i
                break
            fi
        done
        dbg "menu_select: resultat=$MENU_RESULT '${options[$MENU_RESULT]}'"
    else
        if ! _has_tty; then
            dbg "menu_select: non-tty -> index 0"
            MENU_RESULT=0
            return 0
        fi
        echo ""
        echo -e "  ${BOLD}$title${NC}"
        for i in "${!options[@]}"; do
            echo -e "  ${DIM}$((i+1)))${NC} ${options[$i]}"
        done
        echo -ne "  ${YELLOW}?${NC} Choix ${DIM}[1]${NC} " >&2
        read -r choice || true
        choice=${choice:-1}
        MENU_RESULT=$(( choice - 1 ))
        (( MENU_RESULT < 0 )) && MENU_RESULT=0
        (( MENU_RESULT >= ${#options[@]} )) && MENU_RESULT=0
        dbg "menu_select: choix=$choice → index=$MENU_RESULT '${options[$MENU_RESULT]}'"
    fi
}

# ── Checkbox multi-select ──
# Usage : checkbox_select
# Requiert SVC_IDS, SVC_LABEL, SVC_DESC, SVC_PORT, SVC_CAT, SVC_ON
checkbox_select() {
    dbg "checkbox_select: ${#SVC_IDS[@]} services disponibles"
    if _has_gum; then
        local items=() selected_items=() id_map=()

        for id in "${SVC_IDS[@]}"; do
            local port_info=""
            [[ "${SVC_PORT[$id]}" != "—" ]] && port_info=":${SVC_PORT[$id]} "
            local item="${SVC_LABEL[$id]} ${port_info}— ${SVC_DESC[$id]}"
            items+=("$item")
            id_map+=("$id")
            if [[ "${SVC_ON[$id]}" == "1" ]]; then
                selected_items+=("$item")
                dbg "  pre-selected: $id"
            fi
        done
        dbg "  ${#selected_items[@]}/${#items[@]} pre-selectionnes"

        # Construire le flag --selected (gum accepte les virgules)
        local selected_flag=""
        if [[ ${#selected_items[@]} -gt 0 ]]; then
            local IFS=","
            selected_flag="${selected_items[*]}"
        fi

        local result="" rc=0
        if [[ -n "$selected_flag" ]]; then
            result=$(printf '%s\n' "${items[@]}" | \
                gum choose --no-limit \
                    --header "Services a installer (Tab = toggle, Entree = valider)" \
                    --selected "$selected_flag" \
                    --height 20) || rc=$?
        else
            result=$(printf '%s\n' "${items[@]}" | \
                gum choose --no-limit \
                    --header "Services a installer (Tab = toggle, Entree = valider)" \
                    --height 20) || rc=$?
        fi
        dbg "  gum choose --no-limit rc=$rc result_lines=$(echo "$result" | wc -l)"
        [[ $rc -eq 130 ]] && _cleanup_exit
        # Esc → sortie propre
        if [[ $rc -ne 0 && -z "$result" ]]; then
            dbg "checkbox_select: abandon (Esc)"
            info "Abandon"
            exit 0
        fi

        # Reset puis parser
        for id in "${SVC_IDS[@]}"; do SVC_ON[$id]="0"; done
        while IFS= read -r line; do
            [[ -z "$line" ]] && continue
            for i in "${!items[@]}"; do
                if [[ "$line" == "${items[$i]}" ]]; then
                    SVC_ON[${id_map[$i]}]="1"
                    dbg "  selected: ${id_map[$i]}"
                    break
                fi
            done
        done <<< "$result"
    else
        if ! _has_tty; then
            dbg "checkbox_select: non-tty -> conserver preselection"
            return 0
        fi
        echo ""
        echo -e "  ${BOLD}Services disponibles :${NC}"
        local idx=1 id_list=()
        for id in "${SVC_IDS[@]}"; do
            local check=" "
            [[ "${SVC_ON[$id]}" == "1" ]] && check="x"
            echo -e "  ${DIM}${idx})${NC} [${check}] ${SVC_LABEL[$id]} — ${SVC_DESC[$id]}"
            id_list+=("$id")
            ((idx++)) || true
        done
        echo ""
        echo -e "  ${DIM}Entrer les numeros (ex: 1 2 5), 'a' tout, 'v' valider${NC}"
        echo -ne "  ${YELLOW}?${NC} Selection : " >&2
        read -r sel || true
        dbg "  selection manuelle: '$sel'"
        case "$sel" in
            a) for id in "${SVC_IDS[@]}"; do SVC_ON[$id]="1"; done; dbg "  → tout selectionne" ;;
            v|"") dbg "  → garder selection courante" ;;
            *)
                for id in "${SVC_IDS[@]}"; do SVC_ON[$id]="0"; done
                for num in $sel; do
                    local i=$(( num - 1 ))
                    if [[ $i -ge 0 && $i -lt ${#id_list[@]} ]]; then
                        SVC_ON[${id_list[$i]}]="1"
                        dbg "  → ${id_list[$i]} ON"
                    fi
                done
                ;;
        esac
    fi

    # Resume de la selection
    dbg "checkbox_select resultat:"
    for id in "${SVC_IDS[@]}"; do
        dbg "  $id = ${SVC_ON[$id]}"
    done
}

# ── Progress bar ──
step_progress() {
    local current="$1" total="$2" label="$3"
    dbg "step_progress: $current/$total '$label'"
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
health_check() {
    local url="$1" name="$2" retries="${3:-10}" delay="${4:-2}"
    dbg "health_check: $name → $url (max ${retries}x${delay}s)"
    for ((i=1; i<=retries; i++)); do
        local http_code
        http_code=$(curl -sf --max-time 5 -o /dev/null -w '%{http_code}' "$url" 2>/dev/null || echo "000")
        dbg "  tentative $i/$retries → HTTP $http_code"
        if [[ "$http_code" =~ ^2 ]]; then
            ok "${name} operationnel (HTTP $http_code)"
            return 0
        fi
        sleep "$delay"
    done
    warn "${name} ne repond pas apres $((retries * delay))s"
    return 1
}

# ── Docker wrapper (sudo si necessaire) ──
_DOCKER_NEEDS_SUDO="${_DOCKER_NEEDS_SUDO:-false}"

_ensure_docker_access() {
    dbg "_ensure_docker_access: _DOCKER_NEEDS_SUDO=$_DOCKER_NEEDS_SUDO"
    if [[ "$_DOCKER_NEEDS_SUDO" == true ]]; then
        dbg "  sudo deja active"
        return
    fi
    if docker info &>/dev/null 2>&1; then
        dbg "  docker accessible sans sudo"
        return
    fi
    dbg "  docker info FAILED sans sudo, test avec sudo..."
    if command -v sudo &>/dev/null && sudo docker info &>/dev/null 2>&1; then
        _DOCKER_NEEDS_SUDO=true
        dbg "  Docker necessite sudo — activation automatique"
    else
        dbg "  docker inaccessible meme avec sudo"
    fi
}

# Wrapper : utilise sudo docker si necessaire
docker_cmd() {
    dbg "docker_cmd: ${*}"
    if [[ "$_DOCKER_NEEDS_SUDO" == true ]]; then
        sudo docker "$@"
    else
        docker "$@"
    fi
}

docker_compose_cmd() {
    dbg "docker_compose_cmd: ${*}"
    local has_env_file=false
    local arg=""
    for arg in "$@"; do
        if [[ "$arg" == "--env-file" ]]; then
            has_env_file=true
            break
        fi
    done

    local compose_args=()
    if [[ "$has_env_file" == false && -f "$REPO_DIR/.env" ]]; then
        compose_args+=(--env-file "$REPO_DIR/.env")
    fi

    if [[ "$_DOCKER_NEEDS_SUDO" == true ]]; then
        sudo docker compose "${compose_args[@]}" "$@"
    else
        docker compose "${compose_args[@]}" "$@"
    fi
}

# ── Docker container status (colore) ──
# Usage: container_status_line "service_name" → printf une ligne coloree
# Requiert: docker
_docker_ps_cache=""
_docker_ps_cached=false

_cache_docker_ps() {
    if [[ "$_docker_ps_cached" == false ]]; then
        dbg "_cache_docker_ps: interrogation Docker..."
        _docker_ps_cache=$(docker_compose_cmd -f "$REPO_DIR/docker-compose.yml" ps --format '{{.Name}}\t{{.Status}}\t{{.Image}}' 2>/dev/null || true)
        _docker_ps_cached=true
        local count
        count=$(echo "$_docker_ps_cache" | grep -c . || true)
        dbg "  $count containers dans le cache"
        if [[ "$VERBOSE" == true && -n "$_docker_ps_cache" ]]; then
            while IFS= read -r cline; do
                dbg "  cache: $cline"
            done <<< "$_docker_ps_cache"
        fi
    else
        dbg "_cache_docker_ps: utilisation du cache"
    fi
}

invalidate_docker_cache() {
    dbg "invalidate_docker_cache"
    _docker_ps_cached=false
}

# ── Port availability check ──
port_available() {
    local port="$1"
    if ss -tlnp 2>/dev/null | grep -q ":${port} "; then
        dbg "port_available: $port → OCCUPE"
        return 1
    fi
    dbg "port_available: $port → libre"
    return 0
}

# ── Backup file before overwrite ──
backup_file() {
    local file="$1"
    if [[ -f "$file" ]]; then
        local backup="${file}.bak.$(date +%s)"
        cp "$file" "$backup"
        dbg "backup_file: $file → $backup ($(wc -c < "$file") octets)"
        info "Backup : $backup"
    else
        dbg "backup_file: $file n'existe pas, skip"
    fi
}

# ── Service status table ──
# Utilise un seul appel docker compose ps, puis docker inspect par container
show_status_table() {
    dbg "show_status_table: debut"
    _cache_docker_ps
    printf "\n  ${BOLD}%-18s %-7s %-12s %-30s${NC}\n" "Service" "Port" "Statut" "Image"
    line
    for id in "${SVC_IDS[@]}"; do
        [[ "${SVC_ON[$id]}" != "1" ]] && continue
        local port="${SVC_PORT[$id]}"
        local status="○ Absent"
        local status_color="$DIM"
        local image="-"
        local container=""

        # Chercher dans le cache
        container=$(echo "$_docker_ps_cache" | grep -i "$id" | head -1 || true)
        if [[ -n "$container" ]]; then
            local c_name c_status c_image
            c_name=$(echo "$container" | cut -f1)
            c_status=$(echo "$container" | cut -f2)
            c_image=$(echo "$container" | cut -f3 | sed 's|.*/||')
            image="${c_image:-$image}"
            dbg "  $id: container=$c_name status='$c_status' image=$c_image"
            case "$c_status" in
                *Up*|*running*) status="● Running"; status_color="$GREEN" ;;
                *Exited*|*exited*) status="○ Stopped"; status_color="$YELLOW" ;;
                *) status="◌ ${c_status:0:10}"; status_color="$RED" ;;
            esac
        else
            dbg "  $id: pas de container trouve dans le cache"
        fi
        printf "  %-18s %-7s ${status_color}%-12s${NC} ${DIM}%-30s${NC}\n" \
            "${SVC_LABEL[$id]}" "$port" "$status" "$image"
    done
    echo ""
}

# ── Load existing .env into variables ──
# Blocklist : ne jamais ecraser les variables shell critiques
_ENV_BLOCKLIST="PATH IFS HOME SHELL USER TERM LANG BASH_VERSION BASH_SOURCE REPO_DIR SCRIPT_DIR VERBOSE"

load_env() {
    local env_file="${1:-$REPO_DIR/.env}"
    dbg "load_env: $env_file"
    if [[ -f "$env_file" ]]; then
        dbg "  fichier existe: $(wc -l < "$env_file") lignes, $(wc -c < "$env_file") octets"
        local line_count=0 skip_count=0
        while IFS='=' read -r key value; do
            [[ -z "$key" || "$key" == \#* ]] && continue
            key="${key%%[[:space:]]}"
            value="${value##[[:space:]]}"
            value="${value%\"}" ; value="${value#\"}"
            value="${value%\'}" ; value="${value#\'}"
            [[ "$key" =~ ^[A-Z][A-Z0-9_]*$ ]] || continue
            # Bloquer les variables critiques
            if [[ " $_ENV_BLOCKLIST " == *" $key "* ]]; then
                dbg "  SKIP $key (blocklist)"
                ((skip_count++)) || true
                continue
            fi
            local preview="$value"
            if [[ ${#preview} -gt 30 ]]; then
                preview="${preview:0:30}..."
            fi
            dbg "  SET $key=$preview (${#value} chars)"
            printf -v "$key" '%s' "$value" 2>/dev/null || true
            ((line_count++)) || true
        done < "$env_file"
        dbg "  $line_count variables chargees, $skip_count bloquees"
        return 0
    fi
    dbg "  fichier introuvable: $env_file"
    return 1
}

# ── Run pytest (shared entre setup et update) ──
run_pytest() {
    local allow_continue="${1:-false}"
    dbg "run_pytest: allow_continue=$allow_continue"
    if [[ ! -d "$REPO_DIR/core/.venv" ]]; then
        dbg "  pas de venv dans core/, skip"
        return 0
    fi
    if [[ ! -f "$REPO_DIR/core/.venv/bin/python" ]]; then
        dbg "  pas de python dans venv, skip"
        return 0
    fi
    if [[ ! -f "$REPO_DIR/core/.venv/bin/pytest" ]]; then
        dbg "  pytest non installe dans le venv, skip"
        info "pytest non installe — skip tests"
        return 0
    fi
    if ! confirm "Lancer les tests ?"; then
        dbg "  tests refuses par l'utilisateur"
        return 0
    fi
    dbg "  lancement pytest dans $REPO_DIR/core..."
    spin_start "Tests en cours..."
    local rc=0 test_output=""
    test_output=$(cd "$REPO_DIR/core" && .venv/bin/python -m pytest -q 2>&1) || rc=$?
    spin_stop
    dbg "pytest exit code: $rc"
    if [[ "$VERBOSE" == true && -n "$test_output" ]]; then
        dbg "pytest output:"
        while IFS= read -r tl; do
            dbg "  | $tl"
        done <<< "$test_output"
    fi
    if [[ $rc -eq 0 ]]; then
        ok "Tests passes"
    else
        warn "Certains tests ont echoue (code $rc)"
        if [[ "$allow_continue" == true ]]; then
            if ! confirm "Continuer malgre les echecs ?"; then
                exit 1
            fi
        fi
    fi
    return $rc
}
