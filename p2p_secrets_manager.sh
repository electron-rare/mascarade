#!/usr/bin/env bash
# P2P Secrets Manager
set -euo pipefail

SECRETS_DIR="/opt/mascarade/secrets"
API_KEYS_DIR="/opt/mascarade/api_keys"
ENC_KEY_FILE="$SECRETS_DIR/enc_key"

# Generate encryption key
generate_enc_key() {
    if [ -f "$ENC_KEY_FILE" ]; then
        cat "$ENC_KEY_FILE"
        return
    fi

    openssl rand -base64 32 > "$ENC_KEY_FILE"
    chmod 600 "$ENC_KEY_FILE"
    cat "$ENC_KEY_FILE"
}

# Encrypt file
encrypt_file() {
    local file="$1"
    local enc_key=$(generate_enc_key)
    local enc_file="${file}.enc"

    openssl enc -aes-256-cbc -salt -in "$file" -out "$enc_file" -pass "pass:$enc_key"
    shred -u "$file"
    echo "Encrypted $file to $enc_file"
}

# Decrypt file
decrypt_file() {
    local enc_file="$1"
    local dec_file="${enc_file%.enc}"
    local enc_key=$(generate_enc_key)

    openssl enc -d -aes-256-cbc -in "$enc_file" -out "$dec_file" -pass "pass:$enc_key"
    shred -u "$enc_file"
    echo "Decrypted $enc_file to $dec_file"
}

# Create API key
create_api_key() {
    local service="$1"
    local key_file="$API_KEYS_DIR/${service}_key"

    if [ -f "$key_file" ]; then
        echo "API key already exists for $service"
        return
    fi

    # Generate 32-character API key
    API_KEY=$(tr -dc 'A-Za-z0-9' < /dev/urandom | head -c 32)
    echo "$API_KEY" > "$key_file"
    chmod 600 "$key_file"
    encrypt_file "$key_file"
    echo "Created API key for $service"
}

# Get API key
get_api_key() {
    local service="$1"
    local key_file="$API_KEYS_DIR/${service}_key.enc"

    if [ ! -f "$key_file" ]; then
        echo "API key not found for $service"
        return 1
    fi

    decrypt_file "$key_file"
    cat "$API_KEYS_DIR/${service}_key"
    encrypt_file "$API_KEYS_DIR/${service}_key"
}

# Main
case "${1:-}" in
    encrypt)
        encrypt_file "${2:-}"
        ;;
    decrypt)
        decrypt_file "${2:-}"
        ;;
    create-key)
        create_api_key "${2:-}"
        ;;
    get-key)
        get_api_key "${2:-}"
        ;;
    *)
        echo "Usage: $0 {encrypt|decrypt|create-key|get-key} [args]"
        exit 1
        ;;
esac
