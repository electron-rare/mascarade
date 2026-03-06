#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

HTOP_VERSION="3.4.0"
HTOP_DEB_URL="https://archive.ubuntu.com/ubuntu/pool/main/h/htop/htop_3.4.0-2_amd64.deb"
HTOP_DEB_SHA256="d75c63b385cfe6873802c3a79a6f4a9860cadbf5bf82f821cbedf84d0e34fe3e"

usage() {
    cat <<'HELP'
Usage: scripts/install_repo_htop.sh [--quiet]

Installe htop 3.4.0 dans le repo, sans sudo, sous tools/.local/.
Expose ensuite un lanceur stable via ./tools/htop.
HELP
}

QUIET=false
while [[ $# -gt 0 ]]; do
    case "$1" in
        --quiet)
            QUIET=true
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

log() {
    if [[ "$QUIET" != true ]]; then
        echo "$@"
    fi
}

fail() {
    echo "$@" >&2
    exit 1
}

sha256_file() {
    local file="$1"
    if command -v sha256sum >/dev/null 2>&1; then
        sha256sum "$file" | awk '{print $1}'
        return 0
    fi
    if command -v shasum >/dev/null 2>&1; then
        shasum -a 256 "$file" | awk '{print $1}'
        return 0
    fi
    fail "No SHA-256 tool available (sha256sum or shasum required)"
}

if [[ "$(uname -s)" != "Linux" ]]; then
    fail "Repo htop install only supports Linux"
fi

if [[ "$(uname -m)" != "x86_64" ]]; then
    fail "Repo htop install only supports x86_64 for now"
fi

command -v curl >/dev/null 2>&1 || fail "curl is required"
command -v dpkg-deb >/dev/null 2>&1 || fail "dpkg-deb is required"

INSTALL_ROOT="$REPO_DIR/tools/.local"
HTOP_ROOT="$INSTALL_ROOT/htop-$HTOP_VERSION"
BIN_DIR="$INSTALL_ROOT/bin"
BIN_PATH="$BIN_DIR/htop"

if [[ -x "$BIN_PATH" ]]; then
    current_version="$("$BIN_PATH" --version 2>/dev/null | awk '{print $2}')"
    if [[ "$current_version" == "$HTOP_VERSION" ]]; then
        log "htop $HTOP_VERSION already installed in $BIN_PATH"
        exit 0
    fi
fi

tmp_dir="$(mktemp -d)"
cleanup() {
    rm -rf "$tmp_dir"
}
trap cleanup EXIT

log "Downloading htop $HTOP_VERSION from Ubuntu archive..."
curl -fsSLo "$tmp_dir/htop.deb" "$HTOP_DEB_URL"

downloaded_sha="$(sha256_file "$tmp_dir/htop.deb")"
if [[ "$downloaded_sha" != "$HTOP_DEB_SHA256" ]]; then
    fail "SHA-256 mismatch for downloaded htop package"
fi

rm -rf "$HTOP_ROOT"
mkdir -p "$HTOP_ROOT" "$BIN_DIR"
dpkg-deb -x "$tmp_dir/htop.deb" "$HTOP_ROOT"
ln -sfn "../htop-$HTOP_VERSION/usr/bin/htop" "$BIN_PATH"

installed_version="$("$BIN_PATH" --version 2>/dev/null | awk '{print $2}')"
if [[ "$installed_version" != "$HTOP_VERSION" ]]; then
    fail "Installed htop version mismatch: expected $HTOP_VERSION, got ${installed_version:-unknown}"
fi

log "Installed htop $installed_version in $BIN_PATH"
