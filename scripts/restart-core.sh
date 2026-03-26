#!/usr/bin/env bash
# restart-core.sh — Redémarre mascarade-core avec les bons réseaux et les fichiers modifiés.
# Usage: ./scripts/restart-core.sh
set -euo pipefail

PROJ=/home/kxkm/mascarade-main
IMAGE=$(docker inspect mascarade-core --format '{{.Image}}' 2>/dev/null || echo "")

if [ -z "$IMAGE" ]; then
  echo "ERROR: mascarade-core container not found" >&2
  exit 1
fi

echo "→ Stopping mascarade-core..."
docker stop mascarade-core && docker rm mascarade-core

echo "→ Starting with all networks..."
# Kill_LIFE mount: optional, enables /v1/cli-agents/run endpoint
KILL_LIFE_ROOT="${KILL_LIFE_ROOT:-}"
KILL_LIFE_MOUNT_ARGS=()
if [ -d "${KILL_LIFE_ROOT:-}" ]; then
  KILL_LIFE_MOUNT_ARGS=(-v "${KILL_LIFE_ROOT}:/workspace/Kill_LIFE:ro" -e "KILL_LIFE_ROOT=/workspace/Kill_LIFE")
  echo "  Kill_LIFE mount: ${KILL_LIFE_ROOT} → /workspace/Kill_LIFE"
else
  echo "  Kill_LIFE mount: skipped (KILL_LIFE_ROOT not set or not found)"
fi

docker run -d \
  --name mascarade-core \
  --restart unless-stopped \
  --network mascarade-main_mascarade-network \
  -p 0.0.0.0:8100:8100 \
  --env-file "$PROJ/.env" \
  -e CORE_HOST=0.0.0.0 -e CORE_PORT=8100 \
  --add-host host.docker.internal:host-gateway \
  -v mascarade-main_core-data:/app/data \
  "${KILL_LIFE_MOUNT_ARGS[@]}" \
  "$IMAGE"

sleep 3
docker network connect mascarade_mascarade-network mascarade-core
docker network connect mascarade-network mascarade-core --alias core

echo "→ Copying modified source files..."
for f in \
  core/mascarade/server.py \
  core/mascarade/config.py \
  core/mascarade/integrations/rag_pipeline.py \
  core/mascarade/agents/firmware_agent.py \
  core/mascarade/agents/skills.py; do
  docker cp "$PROJ/$f" "mascarade-core:/app/${f#core/}"
done

docker restart mascarade-core
sleep 8

echo "→ Verifying..."
curl -s http://localhost:8100/health | python3 -c "
import json,sys; d=json.load(sys.stdin)
print('core OK —', d['agents'], 'agents |', d['providers'])
"
curl -s http://localhost:3100/health | python3 -c "
import json,sys; d=json.load(sys.stdin)
print('api ', d['status'])
"
