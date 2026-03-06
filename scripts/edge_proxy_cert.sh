#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$REPO_DIR/.env"
ACME_IMAGE="${ACME_IMAGE:-neilpang/acme.sh:latest}"
ACME_HOME_VOLUME="mascarade-edge-proxy-acme"
CERTS_VOLUME="mascarade-edge-proxy-certs"

usage() {
    cat <<'EOF'
Usage:
  bash scripts/edge_proxy_cert.sh issue [options]
  bash scripts/edge_proxy_cert.sh renew [options]
  bash scripts/edge_proxy_cert.sh info

Options:
  --provider <name>     DNS provider: cloudflare or manual
  --email <email>       Override EDGE_PROXY_ACME_EMAIL
  --domains <csv>       Override EDGE_PROXY_ACME_DOMAINS
  --token <token>       Override CLOUDFLARE_API_TOKEN
  --server <ca>         Override EDGE_PROXY_ACME_CA (default: letsencrypt)
  --keylength <value>   Override EDGE_PROXY_ACME_KEY_LENGTH (default: ec-256)
  --dnssleep <seconds>  Override EDGE_PROXY_ACME_DNS_SLEEP (default: 30)
  --force               Force a new issuance
  --no-reload           Skip nginx reload/restart after install
  -h, --help            Show this help
EOF
}

die() {
    echo "error: $*" >&2
    exit 1
}

info() {
    echo "info: $*" >&2
}

load_env_file() {
    [[ -f "$ENV_FILE" ]] || die "Missing $ENV_FILE"
    set -a
    # shellcheck disable=SC1090
    source "$ENV_FILE"
    set +a
    EDGE_PROXY_ACME_DNS_PROVIDER="${EDGE_PROXY_ACME_DNS_PROVIDER:-cloudflare}"
    EDGE_PROXY_ACME_CA="${EDGE_PROXY_ACME_CA:-letsencrypt}"
    EDGE_PROXY_ACME_KEY_LENGTH="${EDGE_PROXY_ACME_KEY_LENGTH:-ec-256}"
    EDGE_PROXY_ACME_DNS_SLEEP="${EDGE_PROXY_ACME_DNS_SLEEP:-30}"
}

trim() {
    local value="$1"
    value="${value#"${value%%[![:space:]]*}"}"
    value="${value%"${value##*[![:space:]]}"}"
    printf '%s' "$value"
}

require_cmd() {
    command -v "$1" >/dev/null 2>&1 || die "Missing command: $1"
}

ensure_edge_proxy_running() {
    docker compose up -d edge-proxy >/dev/null
}

is_ecc_keylength() {
    [[ "${EDGE_PROXY_ACME_KEY_LENGTH:-}" == ec-* ]]
}

is_manual_provider() {
    [[ "${EDGE_PROXY_ACME_DNS_PROVIDER:-cloudflare}" == "manual" ]]
}

build_domain_args() {
    local raw="${EDGE_PROXY_ACME_DOMAINS:-}"
    [[ -n "$raw" ]] || die "EDGE_PROXY_ACME_DOMAINS is empty"
    DOMAIN_ARGS=()
    PRIMARY_DOMAIN=""
    IFS=',' read -r -a raw_domains <<< "$raw"
    for item in "${raw_domains[@]}"; do
        item="$(trim "$item")"
        [[ -n "$item" ]] || continue
        DOMAIN_ARGS+=("-d" "$item")
        if [[ -z "$PRIMARY_DOMAIN" ]]; then
            PRIMARY_DOMAIN="$item"
        fi
    done
    [[ -n "$PRIMARY_DOMAIN" ]] || die "No valid domains in EDGE_PROXY_ACME_DOMAINS"
}

acme_run() {
    require_cmd docker
    docker run --rm \
        -e "CF_Token=${CLOUDFLARE_API_TOKEN:-}" \
        -v "${ACME_HOME_VOLUME}:/acme.sh" \
        -v "${CERTS_VOLUME}:/certs" \
        "$ACME_IMAGE" acme.sh "$@"
}

reload_edge_proxy() {
    if [[ "$NO_RELOAD" == true ]]; then
        info "Skipping edge-proxy reload (--no-reload)"
        return 0
    fi

    if docker compose exec -T edge-proxy nginx -s reload >/dev/null 2>&1; then
        info "edge-proxy reloaded"
        return 0
    fi

    docker compose restart edge-proxy >/dev/null
    info "edge-proxy restarted"
}

issue_cert() {
    [[ -n "${EDGE_PROXY_ACME_EMAIL:-}" ]] || die "EDGE_PROXY_ACME_EMAIL is empty"
    build_domain_args
    ensure_edge_proxy_running

    info "Register ACME account: ${EDGE_PROXY_ACME_EMAIL}"
    acme_run --home /acme.sh --server "${EDGE_PROXY_ACME_CA}" --register-account -m "${EDGE_PROXY_ACME_EMAIL}" >/dev/null || true

    info "Issue certificate for: ${EDGE_PROXY_ACME_DOMAINS}"
    local issue_args=(--home /acme.sh --server "${EDGE_PROXY_ACME_CA}" --issue)
    if is_manual_provider; then
        issue_args+=(--dns --yes-I-know-dns-manual-mode-enough-go-ahead-please)
    else
        [[ -n "${CLOUDFLARE_API_TOKEN:-}" ]] || die "CLOUDFLARE_API_TOKEN is empty"
        issue_args+=(--dns dns_cf)
    fi
    issue_args+=("${DOMAIN_ARGS[@]}")
    issue_args+=(--dnssleep "${EDGE_PROXY_ACME_DNS_SLEEP}" --keylength "${EDGE_PROXY_ACME_KEY_LENGTH}")
    [[ "$FORCE" == true ]] && issue_args+=(--force)
    if is_manual_provider; then
        local rc=0
        set +e
        acme_run "${issue_args[@]}"
        rc=$?
        set -e
        if [[ $rc -ne 0 && $rc -ne 3 ]]; then
            return "$rc"
        fi
        info "Ajoute le TXT ACME dans Cloudflare, puis relance: bash scripts/edge_proxy_cert.sh renew --provider manual"
        return 0
    fi
    acme_run "${issue_args[@]}"
    install_cert
}

install_cert() {
    build_domain_args
    local install_args=(--home /acme.sh --install-cert -d "${PRIMARY_DOMAIN}" --key-file /certs/tls.key --fullchain-file /certs/tls.crt)
    if is_ecc_keylength; then
        install_args=(--home /acme.sh --install-cert --ecc -d "${PRIMARY_DOMAIN}" --key-file /certs/tls.key --fullchain-file /certs/tls.crt)
    fi
    info "Install certificate into ${CERTS_VOLUME}"
    acme_run "${install_args[@]}"
    reload_edge_proxy
}

renew_cert() {
    build_domain_args
    ensure_edge_proxy_running

    local renew_args=(--home /acme.sh --server "${EDGE_PROXY_ACME_CA}" --renew -d "${PRIMARY_DOMAIN}")
    if is_ecc_keylength; then
        renew_args=(--home /acme.sh --server "${EDGE_PROXY_ACME_CA}" --renew --ecc -d "${PRIMARY_DOMAIN}")
    fi
    if is_manual_provider; then
        renew_args+=(--yes-I-know-dns-manual-mode-enough-go-ahead-please)
    else
        [[ -n "${CLOUDFLARE_API_TOKEN:-}" ]] || die "CLOUDFLARE_API_TOKEN is empty"
    fi
    info "Renew certificate for: ${PRIMARY_DOMAIN}"
    acme_run "${renew_args[@]}"

    install_cert
}

show_info() {
    build_domain_args
    local info_args=(--home /acme.sh --info -d "${PRIMARY_DOMAIN}")
    if is_ecc_keylength; then
        info_args=(--home /acme.sh --info --ecc -d "${PRIMARY_DOMAIN}")
    fi
    acme_run "${info_args[@]}"
}

ACTION=""
FORCE=false
NO_RELOAD=false

load_env_file

while [[ $# -gt 0 ]]; do
    case "$1" in
        issue|renew|info)
            ACTION="$1"
            shift
            ;;
        --email)
            EDGE_PROXY_ACME_EMAIL="${2:-}"
            shift 2
            ;;
        --provider)
            EDGE_PROXY_ACME_DNS_PROVIDER="${2:-}"
            shift 2
            ;;
        --domains)
            EDGE_PROXY_ACME_DOMAINS="${2:-}"
            shift 2
            ;;
        --token)
            CLOUDFLARE_API_TOKEN="${2:-}"
            shift 2
            ;;
        --server)
            EDGE_PROXY_ACME_CA="${2:-}"
            shift 2
            ;;
        --keylength)
            EDGE_PROXY_ACME_KEY_LENGTH="${2:-}"
            shift 2
            ;;
        --dnssleep)
            EDGE_PROXY_ACME_DNS_SLEEP="${2:-}"
            shift 2
            ;;
        --force)
            FORCE=true
            shift
            ;;
        --no-reload)
            NO_RELOAD=true
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            die "Unknown argument: $1"
            ;;
    esac
done

require_cmd docker
cd "$REPO_DIR"

case "${ACTION:-}" in
    issue)
        issue_cert
        ;;
    renew)
        renew_cert
        ;;
    info)
        show_info
        ;;
    *)
        usage
        exit 2
        ;;
esac
