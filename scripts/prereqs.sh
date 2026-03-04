#!/usr/bin/env bash
# scripts/prereqs.sh — Verification et installation des prerequis

# ── Detection gestionnaire de paquets ──
detect_pkg_manager() {
    local mgr=""
    if command -v apt-get &>/dev/null; then mgr="apt"
    elif command -v dnf &>/dev/null; then mgr="dnf"
    elif command -v yum &>/dev/null; then mgr="yum"
    elif command -v pacman &>/dev/null; then mgr="pacman"
    elif command -v tdnf &>/dev/null; then mgr="tdnf"
    fi
    dbg "detect_pkg_manager: $mgr"
    echo "$mgr"
}

# ── Sudo helper ──
ensure_sudo() {
    if [[ $EUID -eq 0 ]]; then
        dbg "ensure_sudo: deja root"
        echo ""; return 0
    fi
    if command -v sudo &>/dev/null; then
        dbg "ensure_sudo: sudo disponible"
        echo "sudo"; return 0
    fi
    err "sudo non disponible et pas root — installation impossible"
    return 1
}

# ── Installation Docker multi-distro ──
install_docker() {
    local sudo_cmd pkg_mgr
    sudo_cmd=$(ensure_sudo) || return 1
    pkg_mgr=$(detect_pkg_manager)
    dbg "install_docker: pkg_mgr=$pkg_mgr sudo_cmd='$sudo_cmd'"

    spin_start "Installation de Docker Engine + Compose..."

    case "$pkg_mgr" in
        apt)
            dbg "  apt-get update..."
            $sudo_cmd apt-get update -qq >/dev/null 2>&1
            dbg "  apt-get install ca-certificates curl gnupg..."
            $sudo_cmd apt-get install -y -qq ca-certificates curl gnupg >/dev/null 2>&1
            $sudo_cmd install -m 0755 -d /etc/apt/keyrings
            if [[ ! -f /etc/apt/keyrings/docker.asc ]]; then
                dbg "  import cle GPG Docker..."
                curl -fsSL https://download.docker.com/linux/ubuntu/gpg | $sudo_cmd tee /etc/apt/keyrings/docker.asc > /dev/null
                $sudo_cmd chmod a+r /etc/apt/keyrings/docker.asc
            else
                dbg "  cle GPG Docker deja presente"
            fi
            local codename
            codename=$(. /etc/os-release && echo "$VERSION_CODENAME")
            dbg "  codename=$codename arch=$(dpkg --print-architecture)"
            echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu $codename stable" | \
                $sudo_cmd tee /etc/apt/sources.list.d/docker.list > /dev/null
            $sudo_cmd apt-get update -qq >/dev/null 2>&1
            dbg "  apt-get install docker-ce docker-compose-plugin..."
            $sudo_cmd apt-get install -y -qq docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin >/dev/null 2>&1
            ;;
        dnf|yum)
            dbg "  $pkg_mgr install Docker..."
            $sudo_cmd "$pkg_mgr" install -y -q dnf-plugins-core 2>/dev/null || true
            $sudo_cmd "$pkg_mgr" config-manager --add-repo https://download.docker.com/linux/fedora/docker-ce.repo 2>/dev/null || \
                $sudo_cmd "$pkg_mgr" config-manager --add-repo https://download.docker.com/linux/centos/docker-ce.repo 2>/dev/null
            $sudo_cmd "$pkg_mgr" install -y -q docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
            ;;
        pacman)
            dbg "  pacman install Docker..."
            $sudo_cmd pacman -S --noconfirm docker docker-compose >/dev/null 2>&1
            ;;
        tdnf)
            dbg "  tdnf install Docker..."
            $sudo_cmd tdnf install -y docker-engine docker-cli docker-compose-plugin >/dev/null 2>&1
            ;;
        *)
            spin_stop false
            err "Gestionnaire de paquets non supporte"
            info "Installe manuellement : https://docs.docker.com/engine/install/"
            return 1
            ;;
    esac

    dbg "  systemctl start/enable docker..."
    $sudo_cmd systemctl start docker 2>/dev/null || true
    $sudo_cmd systemctl enable docker 2>/dev/null || true

    if [[ $EUID -ne 0 ]]; then
        dbg "  usermod -aG docker $USER..."
        $sudo_cmd usermod -aG docker "$USER" 2>/dev/null || true
    fi

    spin_stop

    if command -v docker &>/dev/null; then
        local dver
        dver=$(docker --version 2>/dev/null | grep -oP '\d+\.\d+\.\d+' | head -1)
        ok "Docker $dver installe"
        dbg "  docker version=$dver path=$(command -v docker)"
        return 0
    else
        err "L'installation de Docker a echoue"
        dbg "  docker introuvable apres installation"
        return 1
    fi
}

# ── Installation Node.js 22 ──
install_node22() {
    local sudo_cmd pkg_mgr
    sudo_cmd=$(ensure_sudo) || return 1
    pkg_mgr=$(detect_pkg_manager)
    dbg "install_node22: pkg_mgr=$pkg_mgr"

    # Methode 1 : fnm
    if command -v fnm &>/dev/null; then
        dbg "  methode: fnm ($(command -v fnm))"
        spin_start "Installation Node.js 22 via fnm..."
        fnm install 22 >/dev/null 2>&1
        fnm use 22 >/dev/null 2>&1
        fnm default 22 >/dev/null 2>&1
        spin_stop
        ok "Node.js $(node -v) installe via fnm"
        return 0
    fi

    # Methode 2 : nvm
    if [[ -s "$HOME/.nvm/nvm.sh" ]]; then
        dbg "  methode: nvm ($HOME/.nvm/nvm.sh)"
        spin_start "Installation Node.js 22 via nvm..."
        # shellcheck disable=SC1091
        source "$HOME/.nvm/nvm.sh"
        nvm install 22 >/dev/null 2>&1
        nvm use 22 >/dev/null 2>&1
        nvm alias default 22 >/dev/null 2>&1
        spin_stop
        ok "Node.js $(node -v) installe via nvm"
        return 0
    fi

    # Methode 3 : package manager
    dbg "  methode: package manager ($pkg_mgr)"
    spin_start "Installation Node.js 22..."
    case "$pkg_mgr" in
        apt)
            dbg "  nodesource setup_22.x..."
            curl -fsSL https://deb.nodesource.com/setup_22.x | $sudo_cmd bash - >/dev/null 2>&1
            $sudo_cmd apt-get install -y -qq nodejs >/dev/null 2>&1
            ;;
        dnf|yum)
            dbg "  nodesource rpm setup_22.x..."
            curl -fsSL https://rpm.nodesource.com/setup_22.x | $sudo_cmd bash - >/dev/null 2>&1
            $sudo_cmd "$pkg_mgr" install -y -q nodejs >/dev/null 2>&1
            ;;
        pacman)
            $sudo_cmd pacman -S --noconfirm nodejs npm >/dev/null 2>&1
            ;;
        tdnf)
            $sudo_cmd tdnf install -y nodejs >/dev/null 2>&1
            ;;
        *)
            # Fallback : installer nvm
            dbg "  fallback: installation nvm..."
            curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.1/install.sh | bash >/dev/null 2>&1
            export NVM_DIR="$HOME/.nvm"
            # shellcheck disable=SC1091
            [ -s "$NVM_DIR/nvm.sh" ] && source "$NVM_DIR/nvm.sh"
            nvm install 22 >/dev/null 2>&1
            nvm use 22 >/dev/null 2>&1
            nvm alias default 22 >/dev/null 2>&1
            ;;
    esac
    spin_stop

    if command -v node &>/dev/null; then
        local ver major
        ver=$(node -v)
        major=${ver#v}; major=${major%%.*}
        dbg "  node installe: $ver (major=$major) path=$(command -v node)"
        if [[ $major -ge 22 ]]; then
            ok "Node.js $ver installe"
            return 0
        else
            warn "Node.js $ver installe (attendu 22+)"
            return 1
        fi
    else
        err "L'installation de Node.js a echoue"
        dbg "  node introuvable apres installation"
        return 1
    fi
}

# ── Verification complete des prerequis ──
check_prerequisites() {
    section "Verification des prerequis"
    dbg "check_prerequisites: debut"

    local missing_docker=false
    local missing_node=false
    local node_outdated=false

    # Python — requis si core selectionne
    if svc_selected "core"; then
        dbg "Core selectionne — verification Python..."
        if command -v python3 &>/dev/null; then
            local pyver pypath
            pypath=$(command -v python3)
            pyver=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
            dbg "  python3=$pypath version=$pyver"
            if python3 -c 'import sys; exit(0 if sys.version_info >= (3,11) else 1)' 2>/dev/null; then
                ok "Python $pyver"
            else
                warn "Python 3.11+ recommande (trouve $pyver)"
            fi
            # Verifier python3-venv (Ubuntu/Debian n'inclut pas ensurepip par defaut)
            if python3 -c 'import ensurepip' 2>/dev/null; then
                dbg "  ensurepip disponible"
            else
                dbg "  ensurepip ABSENT — python3-venv manquant"
                warn "Module python3-venv manquant (pip ne sera pas disponible dans les venvs)"
                if confirm "Installer python3-venv ? (necessite sudo)"; then
                    local sudo_cmd=""
                    sudo_cmd=$(ensure_sudo) || true
                    if [[ -n "$sudo_cmd" || $EUID -eq 0 ]]; then
                        dbg "  apt-get install python3-venv..."
                        $sudo_cmd apt-get install -y -qq "python3-venv" >/dev/null 2>&1 || \
                            $sudo_cmd apt-get install -y -qq "python${pyver}-venv" >/dev/null 2>&1 || true
                        if python3 -c 'import ensurepip' 2>/dev/null; then
                            ok "python3-venv installe"
                            dbg "  ensurepip maintenant disponible"
                        else
                            warn "Installation python3-venv echouee"
                            dbg "  ensurepip toujours absent apres install"
                        fi
                    fi
                fi
            fi
        else
            warn "Python 3 non trouve (optionnel si Docker uniquement)"
            dbg "  python3 non trouve dans PATH"
        fi
    else
        dbg "Core non selectionne — skip Python"
    fi

    # Node — requis si api selectionne
    if svc_selected "api"; then
        dbg "API selectionne — verification Node.js..."
        if command -v node &>/dev/null; then
            local nodever nodemajor nodepath
            nodepath=$(command -v node)
            nodever=$(node -v)
            nodemajor=${nodever#v}; nodemajor=${nodemajor%%.*}
            dbg "  node=$nodepath version=$nodever major=$nodemajor"
            if [[ $nodemajor -ge 22 ]]; then
                ok "Node.js $nodever"
            else
                warn "Node.js $nodever detecte — requis v22+"
                node_outdated=true
            fi
        else
            warn "Node.js non trouve"
            dbg "  node non trouve dans PATH"
            missing_node=true
        fi

        if command -v npm &>/dev/null; then
            local npmver npmpath
            npmpath=$(command -v npm)
            npmver=$(npm -v)
            dbg "  npm=$npmpath version=$npmver"
            ok "npm $npmver"
        else
            warn "npm non trouve"
            dbg "  npm non trouve dans PATH"
        fi
    else
        dbg "API non selectionne — skip Node.js"
    fi

    # Docker — requis pour les containers
    dbg "Verification Docker..."
    if command -v docker &>/dev/null; then
        local dver dpath
        dpath=$(command -v docker)
        dver=$(docker --version 2>/dev/null | grep -oP '\d+\.\d+\.\d+' | head -1)
        dbg "  docker=$dpath version=$dver"
        ok "Docker $dver"
        if docker compose version &>/dev/null || sudo docker compose version &>/dev/null 2>&1; then
            local dcver
            dcver=$(docker compose version --short 2>/dev/null || sudo docker compose version --short 2>/dev/null)
            dbg "  docker compose version=$dcver"
            ok "Docker Compose $dcver"
        else
            warn "Plugin Docker Compose manquant"
            dbg "  docker compose version FAILED"
            missing_docker=true
        fi
        # Verifier les permissions Docker
        if docker info &>/dev/null; then
            dbg "  docker info OK (permissions OK)"
        else
            dbg "  docker info FAILED (permission denied)"
            warn "Pas de permission Docker pour l'utilisateur $USER"
            if confirm "Ajouter $USER au groupe docker ? (necessite sudo)"; then
                local sudo_cmd=""
                sudo_cmd=$(ensure_sudo) || true
                if [[ -n "$sudo_cmd" || $EUID -eq 0 ]]; then
                    dbg "  usermod -aG docker $USER..."
                    $sudo_cmd usermod -aG docker "$USER" 2>/dev/null || true
                    ok "$USER ajoute au groupe docker"
                    warn "Il faudra te re-loguer (ou 'newgrp docker') pour que ca prenne effet"
                    info "En attendant, les commandes docker utiliseront sudo"
                    _DOCKER_NEEDS_SUDO=true
                    dbg "  _DOCKER_NEEDS_SUDO=true"
                fi
            fi
        fi
    else
        dbg "  docker non trouve dans PATH"
        missing_docker=true
    fi

    # curl
    if command -v curl &>/dev/null; then
        local curlver
        curlver=$(curl --version 2>/dev/null | head -1 | grep -oP '\d+\.\d+\.\d+' | head -1)
        dbg "  curl=$(command -v curl) version=$curlver"
        ok "curl $curlver"
    else
        warn "curl non trouve (necessaire pour les health checks)"
        dbg "  curl non trouve dans PATH"
    fi

    # Git
    if command -v git &>/dev/null; then
        local gitver
        gitver=$(git --version | awk '{print $3}')
        dbg "  git=$(command -v git) version=$gitver"
        ok "Git $gitver"
    else
        dbg "  git non trouve"
    fi

    # ── Proposer l'installation automatique ──
    local need_install=false

    if [[ "$missing_docker" == true ]]; then
        echo ""
        warn "Docker n'est pas installe."
        info "Docker est necessaire pour deployer les services."
        if confirm "Installer Docker Engine + Compose automatiquement ?"; then
            install_docker && need_install=true
        else
            warn "Docker non installe — le deploiement ne fonctionnera pas"
        fi
    fi

    if [[ "$missing_node" == true || "$node_outdated" == true ]]; then
        echo ""
        if [[ "$missing_node" == true ]]; then
            warn "Node.js n'est pas installe."
        else
            warn "Node.js est trop ancien (requis v22+)."
        fi
        info "Node.js 22+ est necessaire pour l'API Hono."

        menu_select "Comment installer Node.js 22 ?" \
            "NodeSource (apt/dnf, recommande)" \
            "nvm (multi-versions)" \
            "Ne pas installer"

        case $MENU_RESULT in
            0) install_node22 && need_install=true ;;
            1)
                dbg "Installation via nvm..."
                spin_start "Installation de nvm..."
                if [[ ! -s "$HOME/.nvm/nvm.sh" ]]; then
                    dbg "  telechargement nvm..."
                    curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.1/install.sh | bash >/dev/null 2>&1
                    export NVM_DIR="$HOME/.nvm"
                    # shellcheck disable=SC1091
                    [ -s "$NVM_DIR/nvm.sh" ] && source "$NVM_DIR/nvm.sh"
                fi
                # shellcheck disable=SC1091
                [ -s "$HOME/.nvm/nvm.sh" ] && source "$HOME/.nvm/nvm.sh"
                nvm install 22 >/dev/null 2>&1
                nvm use 22 >/dev/null 2>&1
                nvm alias default 22 >/dev/null 2>&1
                spin_stop
                if command -v node &>/dev/null; then
                    ok "Node.js $(node -v) installe via nvm"
                    dbg "  node=$(command -v node) version=$(node -v)"
                fi
                need_install=true
                ;;
            2)
                warn "Node.js 22 non installe"
                dbg "Installation Node.js refusee"
                ;;
        esac
    fi

    if [[ "$need_install" == true ]]; then
        echo ""
        log "Verification post-installation..."
        command -v docker &>/dev/null && ok "Docker $(docker --version 2>/dev/null | grep -oP '\d+\.\d+\.\d+' | head -1)"
        command -v node &>/dev/null   && ok "Node.js $(node -v)"
        command -v npm &>/dev/null    && ok "npm $(npm -v)"
    fi

    dbg "check_prerequisites: termine"
}
