#!/usr/bin/env bash
# Mascarade P2P Secure Sync with Rsync
set -euo pipefail

# Configuration
SYNC_PORT=8730
BASE_DIR="$HOME/mascarade_data"
SECRETS_DIR="$BASE_DIR/secrets"
API_KEYS_DIR="$BASE_DIR/api_keys"
KNOWN_HOSTS_FILE="$SECRETS_DIR/known_hosts"
AUTH_TOKEN_FILE="$SECRETS_DIR/auth_token"
PUBLIC_KEY_FILE="$SECRETS_DIR/public_key"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Initialize directories
init_directories() {
    mkdir -p "$SECRETS_DIR" "$API_KEYS_DIR"
    chmod 700 "$SECRETS_DIR" "$API_KEYS_DIR"
}

# Generate 8-character public key
generate_public_key() {
    if [ -f "$PUBLIC_KEY_FILE" ]; then
        cat "$PUBLIC_KEY_FILE"
        return
    fi

    # Generate 8-character alphanumeric key
    PUBLIC_KEY=$(tr -dc 'A-Za-z0-9' < /dev/urandom | head -c 8)
    echo "$PUBLIC_KEY" > "$PUBLIC_KEY_FILE"
    chmod 600 "$PUBLIC_KEY_FILE"
    echo "$PUBLIC_KEY"
}

# Generate auth token (32 chars)
generate_auth_token() {
    if [ -f "$AUTH_TOKEN_FILE" ]; then
        cat "$AUTH_TOKEN_FILE"
        return
    fi

    AUTH_TOKEN=$(tr -dc 'A-Za-z0-9' < /dev/urandom | head -c 32)
    echo "$AUTH_TOKEN" > "$AUTH_TOKEN_FILE"
    chmod 600 "$AUTH_TOKEN_FILE"
    echo "$AUTH_TOKEN"
}

# Add host to known hosts
add_known_host() {
    local host="$1"
    local key="$2"

    if ! grep -q "$host" "$KNOWN_HOSTS_FILE" 2>/dev/null; then
        echo "$host:$key" >> "$KNOWN_HOSTS_FILE"
        chmod 600 "$KNOWN_HOSTS_FILE"
        echo "Added $host to known hosts"
    fi
}

# Verify host key
verify_host() {
    local host="$1"

    if [ ! -f "$KNOWN_HOSTS_FILE" ]; then
        echo "${YELLOW}Warning: No known hosts file${NC}"
        return 1
    fi

    local stored_key=$(grep "^$host:" "$KNOWN_HOSTS_FILE" | cut -d: -f2)
    if [ -z "$stored_key" ]; then
        echo "${RED}Error: Unknown host $host${NC}"
        return 1
    fi

    echo "Host $host verified with key $stored_key"
    return 0
}

# Start rsync daemon (server mode)
start_rsync_daemon() {
    local auth_token=$(generate_auth_token)
    local public_key=$(generate_public_key)

    cat > /etc/rsyncd.conf <<EOF
uid = nobody
gid = nogroup
max connections = 4
timeout = 300

[env_files]
    path = $SECRETS_DIR
    comment = Environment files
    auth users = mascarade
    secrets file = /etc/rsyncd.secrets
    read only = no
    list = yes

[api_keys]
    path = $API_KEYS_DIR
    comment = API keys
    auth users = mascarade
    secrets file = /etc/rsyncd.secrets
    read only = no
    list = yes
EOF

    # Create rsync secrets file
    echo "mascarade:$auth_token" > /etc/rsyncd.secrets
    chmod 600 /etc/rsyncd.secrets

    # Start rsync daemon
    rsync --daemon --port=$SYNC_PORT --config=/etc/rsyncd.conf
    echo "Rsync daemon started on port $SYNC_PORT"
    echo "Public key: $public_key"
    echo "Auth token: $auth_token (keep this secret!)"
}

# Stop rsync daemon
stop_rsync_daemon() {
    pkill -f "rsync --daemon" || true
    rm -f /etc/rsyncd.conf /etc/rsyncd.secrets
    echo "Rsync daemon stopped"
}

# Sync from remote (client mode)
sync_from_remote() {
    local remote_host="$1"
    local remote_key="$2"
    local module="$3"
    local auth_token=$(generate_auth_token)

    if ! verify_host "$remote_host"; then
        read -p "Add $remote_host to known hosts? [y/N] " confirm
        if [[ "$confirm" =~ ^[Yy]$ ]]; then
            add_known_host "$remote_host" "$remote_key"
        else
            echo "Aborting sync"
            return 1
        fi
    fi

    echo "Syncing $module from $remote_host..."
    rsync -avz --port=$SYNC_PORT --password-file=<(echo "$auth_token") \
        "mascarade@$remote_host::$module/" "$(dirname ${!module})/"

    echo "${GREEN}Sync completed successfully${NC}"
}

# Main menu
main() {
    init_directories

    case "${1:-}" in
        server)
            start_rsync_daemon
            ;;
        client)
            shift
            if [ $# -lt 3 ]; then
                echo "Usage: $0 client <remote_host> <remote_key> <module>"
                exit 1
            fi
            sync_from_remote "$1" "$2" "$3"
            ;;
        stop)
            stop_rsync_daemon
            ;;
        key)
            generate_public_key
            ;;
        token)
            generate_auth_token
            ;;
        *)
            echo "Usage: $0 {server|client <host> <key> <module>|stop|key|token}"
            exit 1
            ;;
    esac
}

main "$@"
