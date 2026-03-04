#!/usr/bin/env bash
# Rebind Docker Compose published ports from 127.0.0.1 to a target IP.
# Example:
#   ./scripts/bind-docker-ip.sh --ip 0.0.0.0
#   ./scripts/bind-docker-ip.sh --ip 192.168.1.20 --dry-run

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

TARGET_IP="0.0.0.0"
COMPOSE_FILE="${REPO_DIR}/docker-compose.yml"
DRY_RUN=false

usage() {
    cat <<'EOF'
Usage: bind-docker-ip.sh [options]

Options:
  --ip <addr>         Target bind IP (default: 0.0.0.0)
  --localhost         Shortcut for --ip 127.0.0.1
  --compose-file <f>  Path to docker-compose.yml
  --dry-run           Show diff only, do not modify file
  -h, --help          Show help
EOF
}

err() {
    echo "error: $*" >&2
}

is_valid_ipv4() {
    local ip="$1"
    [[ "$ip" =~ ^([0-9]{1,3}\.){3}[0-9]{1,3}$ ]] || return 1
    local IFS=.
    local o
    for o in $ip; do
        ((o >= 0 && o <= 255)) || return 1
    done
    return 0
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --ip)
            [[ $# -ge 2 ]] || { err "--ip requires a value"; exit 2; }
            TARGET_IP="$2"
            shift
            ;;
        --localhost)
            TARGET_IP="127.0.0.1"
            ;;
        --compose-file)
            [[ $# -ge 2 ]] || { err "--compose-file requires a value"; exit 2; }
            COMPOSE_FILE="$2"
            shift
            ;;
        --dry-run)
            DRY_RUN=true
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            err "unknown option: $1"
            usage
            exit 2
            ;;
    esac
    shift
done

is_valid_ipv4 "$TARGET_IP" || {
    err "invalid IPv4: $TARGET_IP"
    exit 2
}

[[ -f "$COMPOSE_FILE" ]] || {
    err "compose file not found: $COMPOSE_FILE"
    exit 1
}

tmp_file="$(mktemp)"
cleanup() {
    rm -f "$tmp_file"
}
trap cleanup EXIT

TARGET_IP="$TARGET_IP" perl -pe 's/^(\s*-\s*")127\.0\.0\.1(:\$\{[A-Z0-9_]+\}:[0-9]+")/$1$ENV{TARGET_IP}$2/gm' \
    "$COMPOSE_FILE" > "$tmp_file"

before_count="$( (rg -N '127\.0\.0\.1:\$\{[A-Z0-9_]+\}:[0-9]+' "$COMPOSE_FILE" || true) | wc -l | tr -d ' ' )"
after_count="$( (rg -N '127\.0\.0\.1:\$\{[A-Z0-9_]+\}:[0-9]+' "$tmp_file" || true) | wc -l | tr -d ' ' )"
changed_lines="$(( before_count - after_count ))"

if cmp -s "$COMPOSE_FILE" "$tmp_file"; then
    echo "No change needed in $COMPOSE_FILE"
    exit 0
fi

if [[ "$DRY_RUN" == true ]]; then
    echo "Dry run: $changed_lines line(s) would be updated in $COMPOSE_FILE"
    diff -u "$COMPOSE_FILE" "$tmp_file" || true
    exit 0
fi

backup="${COMPOSE_FILE}.bak.$(date +%s)"
cp "$COMPOSE_FILE" "$backup"
mv "$tmp_file" "$COMPOSE_FILE"
trap - EXIT

echo "Updated $COMPOSE_FILE"
echo "Changed bind IP on $changed_lines line(s) -> $TARGET_IP"
echo "Backup saved: $backup"
