#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

usage() {
  cat <<'EOF'
Usage: ./scripts/reviewer_consolidator.sh [options]

Worker CPU de revue/consolidation pour la tuning party.

Options:
  --domains CSV               Domaines a consolider
  --probe-domain-workers N    Parallelisme des probes web (default: 6)
  --refresh-missing-only      Ne rafraichit que les domains missing
  -h, --help                  Affiche l'aide
EOF
}

die() {
  echo "reviewer-consolidator: $*" >&2
  exit 1
}

ensure_positive_integer() {
  local name="$1"
  local value="$2"
  [[ "$value" =~ ^[0-9]+$ ]] || die "$name must be a non-negative integer: $value"
}

DOMAINS_CSV="stm32,freecad,iot,dsp,kicad,emc,platformio,embedded,power,spice"
PROBE_DOMAIN_WORKERS=6
REFRESH_MISSING_ONLY=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --domains)
      [[ $# -ge 2 ]] || die "--domains requires a value"
      DOMAINS_CSV="$2"
      shift 2
      ;;
    --probe-domain-workers)
      [[ $# -ge 2 ]] || die "--probe-domain-workers requires a value"
      ensure_positive_integer "--probe-domain-workers" "$2"
      PROBE_DOMAIN_WORKERS="$2"
      shift 2
      ;;
    --refresh-missing-only)
      REFRESH_MISSING_ONLY=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      die "unknown option: $1"
      ;;
  esac
done

if [[ -f "$ROOT_DIR/venv_tuning/bin/activate" ]]; then
  # shellcheck disable=SC1091
  source "$ROOT_DIR/venv_tuning/bin/activate"
else
  die "missing venv_tuning. Run ./scripts/bootstrap_finetune_env.sh first."
fi

missing_domains() {
  python - "$ROOT_DIR" "$1" <<'PY'
import sys
from pathlib import Path
root = Path(sys.argv[1])
domains = [d.strip() for d in sys.argv[2].split(",") if d.strip()]
research_dir = root / "finetune" / "research"
missing = [d for d in domains if not (research_dir / f"{d}_refresh.json").exists()]
print(" ".join(missing))
PY
}

DOMAINS="$DOMAINS_CSV"
if [[ "$REFRESH_MISSING_ONLY" -eq 1 ]]; then
  DOMAINS="$(missing_domains "$DOMAINS_CSV" | tr ' ' ',')"
fi

echo "[reviewer] domains=${DOMAINS_CSV}"
echo "[reviewer] probe_domain_workers=${PROBE_DOMAIN_WORKERS}"
echo "[reviewer] refresh_missing_only=${REFRESH_MISSING_ONLY}"

echo "[reviewer] sync_research_sources"
nice -n 10 ionice -c2 -n7 "$ROOT_DIR/scripts/sync_research_sources.sh" --probe-domain-workers "$PROBE_DOMAIN_WORKERS"

if [[ -n "${DOMAINS//,/}" ]]; then
  echo "[reviewer] dataset_refresh domains=${DOMAINS}"
  python finetune/dataset_refresh.py ${DOMAINS//,/ } --with-hf
else
  echo "[reviewer] no domains selected for dataset_refresh"
fi

echo "[reviewer] next_finetune_lots"
nice -n 10 ionice -c2 -n7 "$ROOT_DIR/scripts/next_finetune_lots.sh" --continue-on-error

echo "[reviewer] complete"
