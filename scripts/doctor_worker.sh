#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

usage() {
  cat <<'EOF'
Usage: ./scripts/doctor_worker.sh [options]

Worker CPU de diagnostic/doctor pour la tuning party.

Options:
  --domains CSV        Domaines de la session
  --threads N          Budget threads du worker (default: 4)
  -h, --help           Affiche l'aide
EOF
}

die() {
  echo "doctor-worker: $*" >&2
  exit 1
}

ensure_positive_integer() {
  local name="$1"
  local value="$2"
  [[ "$value" =~ ^[0-9]+$ ]] || die "$name must be a non-negative integer: $value"
}

DOMAINS_CSV="stm32,freecad,iot,dsp,kicad,emc,platformio,embedded,power,spice"
THREADS=4

while [[ $# -gt 0 ]]; do
  case "$1" in
    --domains)
      [[ $# -ge 2 ]] || die "--domains requires a value"
      DOMAINS_CSV="$2"
      shift 2
      ;;
    --threads)
      [[ $# -ge 2 ]] || die "--threads requires a value"
      ensure_positive_integer "--threads" "$2"
      THREADS="$2"
      shift 2
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

export OMP_NUM_THREADS="$THREADS"
export MKL_NUM_THREADS="$THREADS"
export OPENBLAS_NUM_THREADS="$THREADS"
export NUMEXPR_NUM_THREADS="$THREADS"

if [[ -f "$ROOT_DIR/venv_tuning/bin/activate" ]]; then
  # shellcheck disable=SC1091
  source "$ROOT_DIR/venv_tuning/bin/activate"
else
  die "missing venv_tuning. Run ./scripts/bootstrap_finetune_env.sh first."
fi

echo "[doctor] domains=${DOMAINS_CSV}"
echo "[doctor] threads=${THREADS}"
echo "[doctor] host=$(hostname)"
echo "[doctor] cpu_threads=$(nproc)"
echo "[doctor] mem=$(free -h | awk '/Mem:/ {print $2 \" total, \" $7 \" available\"}')"
echo "[doctor] gpu=$(nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader 2>/dev/null | head -n 1 || echo unavailable)"

echo "[doctor] model_selector refresh"
python finetune/model_selector.py --refresh --vram 24 --max-params 9 --top 10 || true

echo "[doctor] cad_stack doctor"
"$ROOT_DIR/scripts/cad_stack.sh" doctor || true

echo "[doctor] kicad plugin doctor"
"$ROOT_DIR/scripts/install_kicad_plugins.sh" doctor all || true

echo "[doctor] research summary"
python - "$ROOT_DIR" "$DOMAINS_CSV" <<'PY'
import json
import sys
from pathlib import Path

root = Path(sys.argv[1])
domains = [d.strip() for d in sys.argv[2].split(",") if d.strip()]
research_dir = root / "finetune" / "research"
for domain in domains:
    path = research_dir / f"{domain}_refresh.json"
    if not path.exists():
        print(f"[doctor] {domain}: research=missing")
        continue
    payload = json.loads(path.read_text(encoding="utf-8"))
    rv = payload.get("research_validation", {})
    quality = payload.get("quality", {})
    print(
        f"[doctor] {domain}: research={'ok' if rv.get('valid') else 'blocked'} "
        f"quality={rv.get('quality_score', 0)}/{rv.get('minimum_quality_score', 0)} "
        f"rows={payload.get('row_count', 0)} quality_status={quality.get('status', 'n/a')}"
    )
PY

echo "[doctor] complete"
