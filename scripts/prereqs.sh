#!/usr/bin/env bash
# scripts/prereqs.sh — Verification et installation des prerequis

# ── Detection gestionnaire de paquets ──
detect_pkg_manager() {
    if command -v apt-get &>/dev/null; then echo "apt"
    elif command -v dnf &>/dev/null; then echo "dnf"
    elif command -v yum &>/dev/null; then echo "yum"
    elif command -v pacman &>/dev/null; then echo "pacman"
    elif command -v tdnf &>/dev/null; then echo "tdnf"
    else echo ""
    fi
}

# ── Sudo helper ──
ensure_sudo() {
    if [[ $EUID -eq 0 ]]; then echo ""; return 0; fi
    if command -v sudo &>/dev/null; then echo "sudo"; return 0; fi
    err "sudo non disponible et pas root — installation impossible"
    return 1
}

# ── Installation Docker multi-distro ──
install_docker() {
    local sudo_cmd pkg_mgr
    sudo_cmd=$(ensure_sudo) || return 1
    pkg_mgr=$(detect_pkg_manager)

    spin_start "Installation de Docker Engine + Compose..."

    case "$pkg_mgr" in
        apt)
            $sudo_cmd apt-get update -qq >/dev/null 2>&1
            $sudo_cmd apt-get install -y -qq ca-certificates curl gnupg >/dev/null 2>&1
            $sudo_cmd install -m 0755 -d /etc/apt/keyrings
            if [[ ! -f /etc/apt/keyrings/docker.asc ]]; then
                curl -fsSL https://download.docker.com/linux/ubuntu/gpg | $sudo_cmd tee /etc/apt/keyrings/docker.asc > /dev/null
                $sudo_cmd chmod a+r /etc/apt/keyrings/docker.asc
            fi
            local codename
            codename=$(. /etc/os-release && echo "$VERSION_CODENAME")
            echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu $codename stable" | \
                $sudo_cmd tee /etc/apt/sources.list.d/docker.list > /dev/null
            $sudo_cmd apt-get update -qq >/dev/null 2>&1
            $sudo_cmd apt-get install -y -qq docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin >/dev/null 2>&1
            ;;
        dnf|yum)
            $sudo_cmd "$pkg_mgr" install -y -q dnf-plugins-core 2>/dev/null || true
            $sudo_cmd "$pkg_mgr" config-manager --add-repo https://download.docker.com/linux/fedora/docker-ce.repo 2>/dev/null || \
                $sudo_cmd "$pkg_mgr" config-manager --add-repo https://download.docker.com/linux/centos/docker-ce.repo 2>/dev/null
            $sudo_cmd "$pkg_mgr" install -y -q docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
            ;;
        pacman)
            $sudo_cmd pacman -S --noconfirm docker docker-compose >/dev/null 2>&1
            ;;
        tdnf)
            $sudo_cmd tdnf install -y docker-engine docker-cli docker-compose-plugin >/dev/null 2>&1
            ;;
        *)
            spin_stop false
            err "Gestionnaire de paquets non supporte"
            info "Installe manuellement : https://docs.docker.com/engine/install/"
            return 1
            ;;
    esac

    $sudo_cmd systemctl start docker 2>/dev/null || true
    $sudo_cmd systemctl enable docker 2>/dev/null || true

    if [[ $EUID -ne 0 ]]; then
        $sudo_cmd usermod -aG docker "$USER" 2>/dev/null || true
    fi

    spin_stop

    if command -v docker &>/dev/null; then
        ok "Docker $(docker --version 2>/dev/null | grep -oP '\d+\.\d+\.\d+' | head -1) installe"
        return 0
    else
        err "L'installation de Docker a echoue"
        return 1
    fi
}

# ── Installation Node.js 22 ──
install_node22() {
    local sudo_cmd pkg_mgr
    sudo_cmd=$(ensure_sudo) || return 1
    pkg_mgr=$(detect_pkg_manager)

    # Methode 1 : fnm
    if command -v fnm &>/dev/null; then
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
    spin_start "Installation Node.js 22..."
    case "$pkg_mgr" in
        apt)
            curl -fsSL https://deb.nodesource.com/setup_22.x | $sudo_cmd bash - >/dev/null 2>&1
            $sudo_cmd apt-get install -y -qq nodejs >/dev/null 2>&1
            ;;
        dnf|yum)
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
        if [[ $major -ge 22 ]]; then
            ok "Node.js $ver installe"
            return 0
        else
            warn "Node.js $ver installe (attendu 22+)"
            return 1
        fi
    else
        err "L'installation de Node.js a echoue"
        return 1
    fi
}

# ── Verification complete des prerequis ──
check_prerequisites() {
    section "Verification des prerequis"

    local missing_docker=false
    local missing_node=false
    local node_outdated=false

    # Python — requis si core selectionne
    if svc_selected "core"; then
        if command -v python3 &>/dev/null; then
            local pyver
            pyver=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
            if python3 -c 'import sys; exit(0 if sys.version_info >= (3,11) else 1)' 2>/dev/null; then
                ok "Python $pyver"
            else
                warn "Python 3.11+ recommande (trouve $pyver)"
            fi
        else
            warn "Python 3 non trouve (optionnel si Docker uniquement)"
        fi
    fi

    # Node — requis si api selectionne
    if svc_selected "api"; then
        if command -v node &>/dev/null; then
            local nodever nodemajor
            nodever=$(node -v)
            nodemajor=${nodever#v}; nodemajor=${nodemajor%%.*}
            if [[ $nodemajor -ge 22 ]]; then
                ok "Node.js $nodever"
            else
                warn "Node.js $nodever detecte — requis v22+"
                node_outdated=true
            fi
        else
            warn "Node.js non trouve"
            missing_node=true
        fi

        if command -v npm &>/dev/null; then
            ok "npm $(npm -v)"
        else
            warn "npm non trouve"
        fi
    fi

    # Docker — requis pour les containers
    if command -v docker &>/dev/null; then
        ok "Docker $(docker --version 2>/dev/null | grep -oP '\d+\.\d+\.\d+' | head -1)"
        if docker compose version &>/dev/null; then
            ok "Docker Compose $(docker compose version --short 2>/dev/null)"
        else
            warn "Plugin Docker Compose manquant"
            missing_docker=true
        fi
    else
        missing_docker=true
    fi

    # curl
    if command -v curl &>/dev/null; then
        ok "curl $(curl --version 2>/dev/null | head -1 | grep -oP '\d+\.\d+\.\d+' | head -1)"
    else
        warn "curl non trouve (necessaire pour les health checks)"
    fi

    # Git
    command -v git &>/dev/null && ok "Git $(git --version | awk '{print $3}')"

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
                spin_start "Installation de nvm..."
                if [[ ! -s "$HOME/.nvm/nvm.sh" ]]; then
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
                command -v node &>/dev/null && ok "Node.js $(node -v) installe via nvm"
                need_install=true
                ;;
            2) warn "Node.js 22 non installe" ;;
        esac
    fi

    if [[ "$need_install" == true ]]; then
        echo ""
        log "Verification post-installation..."
        command -v docker &>/dev/null && ok "Docker $(docker --version 2>/dev/null | grep -oP '\d+\.\d+\.\d+' | head -1)"
        command -v node &>/dev/null   && ok "Node.js $(node -v)"
        command -v npm &>/dev/null    && ok "npm $(npm -v)"
    fi
}
