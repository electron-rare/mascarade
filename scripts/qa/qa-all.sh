#!/usr/bin/env bash
# scripts/qa/qa-all.sh — Runner QA global Mascarade
# Orchestre tous les scripts de chaîne. Passe les arguments à chaque runner.
# Usage: ./scripts/qa/qa-all.sh [--chain <name>] [--fast] [--ci]
#   --chain   ne lancer qu'une chaîne (ex: router, rag, p2p)
#   --fast    ignorer les tests lents (intégration, e2e)
#   --ci      mode CI (pas de couleurs, exit 1 en cas d'échec)
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
QA_DIR="$ROOT/scripts/qa"

# ── couleurs ──────────────────────────────────────────────────────────────────
if [[ "${CI:-}" == "true" ]]; then
  RED=""; GREEN=""; YELLOW=""; BLUE=""; BOLD=""; RESET=""
else
  RED="\033[0;31m"; GREEN="\033[0;32m"; YELLOW="\033[1;33m"
  BLUE="\033[0;34m"; BOLD="\033[1m"; RESET="\033[0m"
fi

CHAIN_FILTER=""
FAST_MODE=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    --chain) CHAIN_FILTER="$2"; shift 2 ;;
    --fast)  FAST_MODE=true; shift ;;
    --ci)    shift ;;
    *) echo "Usage: $0 [--chain <name>] [--fast] [--ci]"; exit 1 ;;
  esac
done

export FAST_MODE CI ROOT

# ── chaînes ordonnées ─────────────────────────────────────────────────────────
declare -a CHAINS=(
  "docs:qa-docs.sh"
  "core-python:qa-core-python.sh"
  "api:qa-api.sh"
  "web:qa-web.sh"
  "router:qa-router.sh"
  "orchestrator:qa-orchestrator.sh"
  "rag:qa-rag.sh"
  "node-engine:qa-node-engine.sh"
  "p2p:qa-p2p.sh"
  "agents:qa-agents.sh"
  "finetune:qa-finetune.sh"
  "compose:qa-compose.sh"
  "e2e:qa-e2e.sh"
)

PASS=()
FAIL=()
SKIP=()
START_ALL=$(date +%s)

run_chain() {
  local name="$1" script="$2"
  if [[ -n "$CHAIN_FILTER" && "$name" != "$CHAIN_FILTER" ]]; then
    return
  fi
  if [[ ! -f "$QA_DIR/$script" ]]; then
    echo -e "${YELLOW}[SKIP]${RESET} $name — script manquant"
    SKIP+=("$name")
    return
  fi
  echo ""
  echo -e "${BLUE}${BOLD}━━━ $name ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}"
  local t0=$(date +%s)
  if bash "$QA_DIR/$script"; then
    local elapsed=$(( $(date +%s) - t0 ))
    echo -e "${GREEN}[PASS]${RESET} $name (${elapsed}s)"
    PASS+=("$name")
  else
    local elapsed=$(( $(date +%s) - t0 ))
    echo -e "${RED}[FAIL]${RESET} $name (${elapsed}s)"
    FAIL+=("$name")
  fi
}

for chain_def in "${CHAINS[@]}"; do
  name="${chain_def%%:*}"
  script="${chain_def##*:}"
  run_chain "$name" "$script"
done

# ── résumé ────────────────────────────────────────────────────────────────────
TOTAL=$(( $(date +%s) - START_ALL ))
echo ""
echo -e "${BOLD}══════════════════════════════════════════════════${RESET}"
echo -e "${BOLD}  QA Mascarade — résumé (${TOTAL}s)${RESET}"
echo -e "${BOLD}══════════════════════════════════════════════════${RESET}"
printf "  %-14s %s\n" "Passées:" "${GREEN}${PASS[*]:-aucune}${RESET}"
printf "  %-14s %s\n" "Ignorées:" "${YELLOW}${SKIP[*]:-aucune}${RESET}"
printf "  %-14s %s\n" "Échouées:" "${RED}${FAIL[*]:-aucune}${RESET}"
echo ""

if [[ ${#FAIL[@]} -gt 0 ]]; then
  exit 1
fi
