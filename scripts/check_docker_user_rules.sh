#!/usr/bin/env bash
# check_docker_user_rules.sh — Validate DOCKER-USER iptables rules for Mascarade
#
# Docker's default FORWARD chain allows all container traffic.
# DOCKER-USER is the correct chain to add host-level access controls.
#
# Required rules (ports exposed on LAN / host interface):
#   80/tcp   — ops-console, Dify Web
#   3500/tcp — Dify API (internal bridge only on prod)
#   5001/tcp — Dify Worker API (internal bridge only on prod)
#
# Usage:
#   ./scripts/check_docker_user_rules.sh          # check only
#   ./scripts/check_docker_user_rules.sh --fix    # print iptables commands to add missing rules
#   ./scripts/check_docker_user_rules.sh --apply  # apply missing rules (requires sudo)

set -euo pipefail

PORTS=(80 3500 5001)
CHAIN="DOCKER-USER"
MISSING=()

check_rule() {
    local port=$1
    if sudo iptables -C "$CHAIN" -p tcp --dport "$port" -j RETURN 2>/dev/null; then
        echo "  [OK]  DOCKER-USER RETURN rule for TCP/$port exists"
    else
        echo "  [!!]  DOCKER-USER RETURN rule for TCP/$port is MISSING"
        MISSING+=("$port")
    fi
}

echo "=== DOCKER-USER iptables check (Mascarade) ==="
echo ""
echo "Chain: $CHAIN"
echo "Ports: ${PORTS[*]}"
echo ""

# Check if DOCKER-USER chain exists
if ! sudo iptables -L "$CHAIN" -n > /dev/null 2>&1; then
    echo "[WARN] Chain $CHAIN does not exist — Docker may not be running or iptables backend differs."
    echo "       Try: sudo iptables -N $CHAIN && sudo iptables -I FORWARD -j $CHAIN"
    exit 1
fi

for port in "${PORTS[@]}"; do
    check_rule "$port"
done

echo ""

if [[ ${#MISSING[@]} -eq 0 ]]; then
    echo "[PASS] All required DOCKER-USER rules are present."
    exit 0
fi

echo "[FAIL] Missing rules for ports: ${MISSING[*]}"
echo ""

if [[ "${1:-}" == "--apply" ]]; then
    echo "Applying missing rules..."
    for port in "${MISSING[@]}"; do
        sudo iptables -I "$CHAIN" 1 -p tcp --dport "$port" -j RETURN
        echo "  [+] Added RETURN rule for TCP/$port"
    done
    echo ""
    echo "Rules applied. Verify with: sudo iptables -L $CHAIN -n --line-numbers"
    echo ""
    echo "[WARN] These rules are NOT persistent across reboots."
    echo "       Add them to /etc/iptables/rules.v4 or use iptables-persistent."
elif [[ "${1:-}" == "--fix" ]]; then
    echo "Run these commands to fix (requires sudo):"
    for port in "${MISSING[@]}"; do
        echo "  sudo iptables -I $CHAIN 1 -p tcp --dport $port -j RETURN"
    done
    echo ""
    echo "To make persistent:"
    echo "  sudo apt install iptables-persistent"
    echo "  sudo netfilter-persistent save"
else
    echo "Re-run with --fix to see the iptables commands, or --apply to apply them directly."
fi

exit 2
