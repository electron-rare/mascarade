#!/usr/bin/env bash
# validate-config.sh — Validate .env before deployment
# Exit codes: 0 = OK, 1 = failures, 2 = warnings only
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
ENV_FILE="${1:-$PROJECT_ROOT/.env}"
ENV_EXAMPLE="$PROJECT_ROOT/.env.example"

# ── Colors ──
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

FAILURES=0
WARNINGS=0

pass()  { printf "${GREEN}[PASS]${NC}  %s\n" "$1"; }
warn()  { printf "${YELLOW}[WARN]${NC}  %s\n" "$1"; WARNINGS=$((WARNINGS + 1)); }
fail()  { printf "${RED}[FAIL]${NC}  %s\n" "$1"; FAILURES=$((FAILURES + 1)); }

# ── Pre-flight ──
if [[ ! -f "$ENV_FILE" ]]; then
    fail ".env file not found: $ENV_FILE"
    exit 1
fi

if [[ ! -f "$ENV_EXAMPLE" ]]; then
    warn ".env.example not found — skipping completeness check"
fi

echo "Validating $ENV_FILE ..."
echo ""

# ── 1. Required variables ──
REQUIRED_VARS=(
    MASCARADE_API_KEY
    CORE_PORT
    API_PORT
)

for var in "${REQUIRED_VARS[@]}"; do
    val=$(grep -E "^${var}=" "$ENV_FILE" 2>/dev/null | head -1 | cut -d'=' -f2-)
    if [[ -z "$val" ]]; then
        fail "Required variable $var is empty or missing"
    else
        pass "Required variable $var is set"
    fi
done

# ── 2. Placeholder detection ──
echo ""
PLACEHOLDER_PATTERNS=(
    "sk-\.\.\."
    "ntn_\.\.\."
    "REPLACE_WITH_"
)

while IFS='=' read -r key val; do
    # Skip comments and empty lines
    [[ -z "$key" || "$key" =~ ^[[:space:]]*# ]] && continue
    # Strip inline comments
    val="${val%%#*}"
    # Trim whitespace
    val="$(echo "$val" | xargs 2>/dev/null || true)"
    [[ -z "$val" ]] && continue

    for pattern in "${PLACEHOLDER_PATTERNS[@]}"; do
        if echo "$val" | grep -qE "$pattern"; then
            fail "Variable $key contains placeholder value: $val"
        fi
    done
done < "$ENV_FILE"
pass "Placeholder check complete"

# ── 3. URL format validation ──
echo ""
URL_VARS=(
    CORE_URL
    REDIS_URL
    OLLAMA_BASE_URL
    MASCARADE_API_BASE_URL
    OTEL_COLLECTOR_HTTP_ENDPOINT
    OPS_AGENT_URL
    LOKI_URL
    LITELLM_BASE_URL
    EXO_BASE_URL
)

while IFS='=' read -r key val; do
    [[ -z "$key" || "$key" =~ ^[[:space:]]*# ]] && continue
    val="${val%%#*}"
    val="$(echo "$val" | xargs 2>/dev/null || true)"
    [[ -z "$val" ]] && continue

    for url_var in "${URL_VARS[@]}"; do
        if [[ "$key" == "$url_var" ]]; then
            if ! echo "$val" | grep -qE '^https?://'; then
                fail "Variable $key has invalid URL format (must start with http:// or https://): $val"
            else
                pass "URL variable $key is valid"
            fi
        fi
    done
done < "$ENV_FILE"

# ── 4. Numeric port validation ──
echo ""
PORT_VARS=(
    CORE_PORT
    API_PORT
    POSTGRES_PORT
    REDIS_PORT
    CLICKHOUSE_HTTP_PORT
    CLICKHOUSE_NATIVE_PORT
    OLLAMA_PORT
    LITELLM_PORT
    N8N_PORT
    LANGFUSE_PORT
    FIRECRAWL_PORT
    MEM0_PORT
    DIFY_API_PORT
    DIFY_WEB_PORT
    QDRANT_PORT
    GRAFANA_PORT
    PROMETHEUS_PORT
    OPS_AGENT_PORT
    LOKI_PORT
    EDGE_PROXY_HTTP_PORT
    EDGE_PROXY_HTTPS_PORT
)

while IFS='=' read -r key val; do
    [[ -z "$key" || "$key" =~ ^[[:space:]]*# ]] && continue
    val="${val%%#*}"
    val="$(echo "$val" | xargs 2>/dev/null || true)"
    [[ -z "$val" ]] && continue

    for port_var in "${PORT_VARS[@]}"; do
        if [[ "$key" == "$port_var" ]]; then
            if ! [[ "$val" =~ ^[0-9]+$ ]]; then
                fail "Port variable $key is not numeric: $val"
            elif (( val < 1 || val > 65535 )); then
                fail "Port variable $key is out of range (1-65535): $val"
            else
                pass "Port variable $key = $val"
            fi
        fi
    done
done < "$ENV_FILE"

# ── 5. Duplicate variable definitions ──
echo ""
DUPES=$(grep -E '^[A-Za-z_][A-Za-z0-9_]*=' "$ENV_FILE" | cut -d'=' -f1 | sort | uniq -d)
if [[ -n "$DUPES" ]]; then
    while IFS= read -r dup; do
        warn "Duplicate variable definition: $dup"
    done <<< "$DUPES"
else
    pass "No duplicate variable definitions"
fi

# ── 6. File permissions ──
echo ""
if [[ "$(uname)" == "Darwin" ]]; then
    PERMS=$(stat -f '%Lp' "$ENV_FILE" 2>/dev/null || echo "???")
else
    PERMS=$(stat -c '%a' "$ENV_FILE" 2>/dev/null || echo "???")
fi

if [[ "$PERMS" == "???" ]]; then
    warn "Could not read file permissions for $ENV_FILE"
elif [[ "${PERMS: -1}" != "0" ]]; then
    warn ".env is world-readable (permissions: $PERMS) — recommend chmod 640 or 600"
else
    pass ".env file permissions OK ($PERMS)"
fi

# ── 7. Completeness check against .env.example ──
echo ""
if [[ -f "$ENV_EXAMPLE" ]]; then
    MISSING=0
    while IFS='=' read -r key _; do
        [[ -z "$key" || "$key" =~ ^[[:space:]]*# ]] && continue
        key="$(echo "$key" | xargs 2>/dev/null || true)"
        [[ -z "$key" ]] && continue
        if ! grep -qE "^${key}=" "$ENV_FILE" 2>/dev/null; then
            warn "Variable $key from .env.example is missing in .env"
            MISSING=$((MISSING + 1))
        fi
    done < "$ENV_EXAMPLE"
    if [[ "$MISSING" -eq 0 ]]; then
        pass "All .env.example variables present in .env"
    fi
fi

# ── Summary ──
echo ""
echo "────────────────────────────────"
if [[ "$FAILURES" -gt 0 ]]; then
    printf "${RED}RESULT: %d failure(s), %d warning(s)${NC}\n" "$FAILURES" "$WARNINGS"
    exit 1
elif [[ "$WARNINGS" -gt 0 ]]; then
    printf "${YELLOW}RESULT: 0 failures, %d warning(s)${NC}\n" "$WARNINGS"
    exit 2
else
    printf "${GREEN}RESULT: All checks passed${NC}\n"
    exit 0
fi
