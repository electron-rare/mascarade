#!/usr/bin/env bash
# propagate-cli-agents.sh — Propage le endpoint /v1/api/cli-agents/run sur les machines du mesh.
# Usage: ./scripts/propagate-cli-agents.sh [host1 host2 ...]
# Défaut: toutes les machines du mesh définies dans HOST_TARGETS
set -euo pipefail

PROJ_LOCAL="$(cd "$(dirname "$0")/.." && pwd)"
BRANCH="feat/cli-agents-run"

# Machines du mesh (label:user@host:mascarade_root:kill_life_root_or_empty)
MACHINES=(
  "clems:clems@192.168.0.120:/home/clems/mascarade:/home/clems/Kill_LIFE"
  "kxkm-root:root@192.168.0.119:/root/mascarade-main:"
  "cils:cils@100.126.225.111:/Users/cils/mascarade-main:"
)

TARGETS=("$@")
if [ ${#TARGETS[@]} -eq 0 ]; then
  TARGETS=("${MACHINES[@]}")
fi

propagate_one() {
  local spec="$1"
  local label host mascarade_root kill_life_root
  IFS=: read -r label host mascarade_root kill_life_root <<< "$spec"

  echo ""
  echo "═══ $label ($host) ═══"

  # Test SSH
  if ! ssh -o ConnectTimeout=5 -o BatchMode=yes "$host" true 2>/dev/null; then
    echo "  ✗ SSH inaccessible — skipped"
    return 0
  fi

  # git pull sur la branche
  ssh "$host" bash <<SSH
set -euo pipefail
cd "${mascarade_root}"
git fetch origin "${BRANCH}" 2>/dev/null || true
git cherry-pick --no-commit origin/${BRANCH} 2>/dev/null || git checkout origin/${BRANCH} -- \\
  api/src/client/core.ts \\
  api/src/index.ts \\
  api/src/routes/cliAgents.ts \\
  core/mascarade/server.py
echo "  ✓ fichiers mis à jour"
SSH

  # docker cp server.py si mascarade-core tourne
  ssh "$host" bash <<SSH
if docker inspect mascarade-core &>/dev/null 2>&1; then
  docker cp "${mascarade_root}/core/mascarade/server.py" mascarade-core:/app/mascarade/server.py
  echo "  ✓ server.py copié dans mascarade-core"
  # Rebuild dist TypeScript si node_modules/.bin/tsc existe
  if [ -f "${mascarade_root}/api/node_modules/.bin/tsc" ]; then
    (cd "${mascarade_root}/api" && node_modules/.bin/tsc 2>/dev/null)
    docker cp "${mascarade_root}/api/dist/routes/cliAgents.js" mascarade-api:/app/dist/routes/cliAgents.js 2>/dev/null || true
    docker cp "${mascarade_root}/api/dist/client/core.js" mascarade-api:/app/dist/client/core.js 2>/dev/null || true
    echo "  ✓ dist API mis à jour"
  fi
  # Redémarrer mascarade-core avec mount Kill_LIFE si disponible
  if [ -n "${kill_life_root}" ] && [ -d "${kill_life_root}" ]; then
    export KILL_LIFE_ROOT="${kill_life_root}"
    bash "${mascarade_root}/scripts/restart-core.sh" 2>/dev/null || true
    echo "  ✓ mascarade-core redémarré avec Kill_LIFE mount"
  else
    docker restart mascarade-core 2>/dev/null || true
    echo "  ✓ mascarade-core redémarré (sans Kill_LIFE mount)"
  fi
else
  echo "  ⚠ mascarade-core non trouvé sur cette machine"
fi
SSH
  echo "  ✓ $label propagé"
}

for target in "${TARGETS[@]}"; do
  propagate_one "$target" || echo "  ✗ Échec pour $target"
done

echo ""
echo "Propagation terminée."
