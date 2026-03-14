#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "=== Deploying P2P auto-start ==="

# VM (systemd)
echo "--- VM (systemd) ---"
scp "$SCRIPT_DIR/node_start_bootstrap.py" root@192.168.0.119:/mascarade/core/scripts/p2p/
scp "$SCRIPT_DIR/systemd/mascarade-p2p.service" root@192.168.0.119:/etc/systemd/system/
ssh root@192.168.0.119 "sed -i 's|node_start.py|node_start_bootstrap.py|' /etc/systemd/system/mascarade-p2p.service; systemctl daemon-reload; systemctl enable mascarade-p2p; systemctl restart mascarade-p2p; systemctl status mascarade-p2p --no-pager" 2>&1

# Workers
for node_spec in "cils@192.168.0.210:CILS MacBook:kicad-validation,firmware-build" "clems@192.168.0.120:Tower:compute,storage" "kxkm@kxkm-ai:KXKM-AI:audio,media"; do
    IFS=: read -r ssh_target label caps <<< "$node_spec"
    echo "--- $ssh_target ($label) ---"
    scp "$SCRIPT_DIR/node_start_worker.py" "$ssh_target:~/mascarade/core/scripts/p2p/" 2>/dev/null || echo "  scp failed"
done

echo "=== Done ==="
