#!/bin/sh
set -eu

CERT_DIR="/etc/nginx/certs"
CERT_FILE="${CERT_DIR}/tls.crt"
KEY_FILE="${CERT_DIR}/tls.key"
SERVER_NAME="${EDGE_PROXY_SERVER_NAME:-localhost}"
TLS_SANS="${EDGE_PROXY_TLS_SANS:-DNS:localhost,IP:127.0.0.1}"

mkdir -p "$CERT_DIR"

if [ -s "$CERT_FILE" ] && [ -s "$KEY_FILE" ]; then
    exit 0
fi

if [ "$SERVER_NAME" != "_" ] && [ "$SERVER_NAME" != "localhost" ]; then
    case "$TLS_SANS" in
        *"$SERVER_NAME"*) ;;
        *)
            case "$SERVER_NAME" in
                *[!0-9.]*)
                    TLS_SANS="${TLS_SANS},DNS:${SERVER_NAME}"
                    ;;
                *)
                    TLS_SANS="${TLS_SANS},IP:${SERVER_NAME}"
                    ;;
            esac
            ;;
    esac
fi

cfg="$(mktemp)"
trap 'rm -f "$cfg"' EXIT

cat >"$cfg" <<EOF
[req]
distinguished_name = req_distinguished_name
x509_extensions = v3_req
prompt = no

[req_distinguished_name]
CN = ${SERVER_NAME}

[v3_req]
subjectAltName = ${TLS_SANS}
EOF

openssl req -x509 -nodes -newkey rsa:2048 -days 825 \
    -keyout "$KEY_FILE" \
    -out "$CERT_FILE" \
    -config "$cfg" >/dev/null 2>&1
