#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

. "$ROOT_DIR/scripts/llm_env.sh"

MODEL_ID=""
DOMAIN="stm32"
SEQ_LEN="512"
MAX_SAMPLES="16"
EPOCHS="1"
TOKENIZE_WORKERS="1"
RUN_LABEL="watch-bench"
EXECUTE=0
REFRESH_WATCH=0
FORCE=0
VERBOSE=0

usage() {
  cat <<'EOF'
Usage: ./scripts/bench_watch_candidate.sh [options]

Dry-run or execute a local smoke benchmark for the next watch candidate.

Options:
  --model <id>          Explicit model id to benchmark
  --domain <name>       Training domain (default: stm32)
  --seq-len <n>         Sequence length (default: 512)
  --max-samples <n>     Max dataset samples (default: 16)
  --epochs <n>          Epochs (default: 1)
  --tokenize-workers <n>
                        Tokenization workers (default: 1)
  --run-label <label>   Run label prefix (default: watch-bench)
  --refresh-watch       Refresh watch report before resolving candidate
  --execute             Download into /ai/llm and launch the smoke run
  --force               Run even if the GPU preflight reports low free VRAM
  --verbose             Print extra command context
  -h, --help            Show this help
EOF
}

log() {
  printf '[watch-bench] %s\n' "$*"
}

activate_venv() {
  if [ -f "$ROOT_DIR/venv_tuning/bin/activate" ]; then
    # shellcheck disable=SC1091
    source "$ROOT_DIR/venv_tuning/bin/activate"
    return 0
  fi
  echo "Missing venv_tuning. Run ./scripts/bootstrap_finetune_env.sh first." >&2
  return 1
}

resolve_watch_model() {
  python - <<'PY'
import json
from pathlib import Path

candidates = [
    Path("/dev/shm/mascarade-finetune-state/model_watch_report.json"),
    Path("/tmp/mascarade-finetune-state/model_watch_report.json"),
    Path("finetune/model_watch_report.json"),
]
for report_path in candidates:
    if not report_path.exists():
        continue
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    for key in ("student_watch", "entries"):
        entries = payload.get(key) or []
        for entry in entries:
            if key == "entries" and entry.get("suggested_lane") != "student_watch":
                continue
            model_id = str(entry.get("model_id") or "").strip()
            if model_id:
                print(model_id)
                raise SystemExit(0)
raise SystemExit(1)
PY
}

resolve_selected_model() {
  python - <<'PY'
import json
from pathlib import Path

candidates = [
    Path("/dev/shm/mascarade-finetune-state/selected_model.json"),
    Path("/tmp/mascarade-finetune-state/selected_model.json"),
    Path("finetune/selected_model.json"),
]
for selection_path in candidates:
    if not selection_path.exists():
        continue
    payload = json.loads(selection_path.read_text(encoding="utf-8"))
    model_id = str(payload.get("model_id") or "").strip()
    if model_id:
        print(model_id)
        raise SystemExit(0)
raise SystemExit(1)
PY
}

required_free_vram_mb() {
  python - <<'PY' "$1"
import re
import sys

model = sys.argv[1].lower()
match = re.search(r"(\d+(?:\.\d+)?)b", model)
param_b = float(match.group(1)) if match else 7.0
if param_b <= 2.0:
    print(8000)
elif param_b <= 4.5:
    print(14000)
elif param_b <= 9.5:
    print(22000)
else:
    print(26000)
PY
}

parse_nvidia_metric() {
  local value="$1"
  value="$(printf '%s' "$value" | tr -cd '0-9')"
  printf '%s' "${value:-0}"
}

gpu_preflight() {
  command -v nvidia-smi >/dev/null 2>&1 || return 0
  local line free_mb used_mb total_mb required_mb
  line="$(nvidia-smi --query-gpu=memory.free,memory.used,memory.total --format=csv,noheader,nounits 2>/dev/null | head -n1 || true)"
  [ -n "$line" ] || return 0
  free_mb="$(printf '%s' "$line" | cut -d, -f1 | tr -d ' ')"
  used_mb="$(printf '%s' "$line" | cut -d, -f2 | tr -d ' ')"
  total_mb="$(printf '%s' "$line" | cut -d, -f3 | tr -d ' ')"
  free_mb="$(parse_nvidia_metric "$free_mb")"
  used_mb="$(parse_nvidia_metric "$used_mb")"
  total_mb="$(parse_nvidia_metric "$total_mb")"
  if ! [[ "$free_mb" =~ ^[0-9]+$ && "$used_mb" =~ ^[0-9]+$ && "$total_mb" =~ ^[0-9]+$ ]]; then
    log "gpu_preflight=blocked invalid nvidia-smi payload: $line"
    return 1
  fi
  required_mb="$(required_free_vram_mb "$MODEL_ID")"
  if [ "${free_mb:-0}" -ge "$required_mb" ]; then
    [ "$VERBOSE" -eq 1 ] && log "gpu_preflight=ok free_mb=$free_mb required_mb=$required_mb used_mb=$used_mb total_mb=$total_mb"
    return 0
  fi
  log "gpu_preflight=blocked free_mb=${free_mb:-0} required_mb=$required_mb used_mb=${used_mb:-0} total_mb=${total_mb:-0}"
  nvidia-smi --query-compute-apps=pid,process_name,used_memory --format=csv,noheader,nounits 2>/dev/null || true
  return 1
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --model)
      [ "$#" -ge 2 ] || { echo "--model requires a value" >&2; exit 2; }
      MODEL_ID="$2"
      shift 2
      ;;
    --domain)
      [ "$#" -ge 2 ] || { echo "--domain requires a value" >&2; exit 2; }
      DOMAIN="$2"
      shift 2
      ;;
    --seq-len)
      [ "$#" -ge 2 ] || { echo "--seq-len requires a value" >&2; exit 2; }
      SEQ_LEN="$2"
      shift 2
      ;;
    --max-samples)
      [ "$#" -ge 2 ] || { echo "--max-samples requires a value" >&2; exit 2; }
      MAX_SAMPLES="$2"
      shift 2
      ;;
    --epochs)
      [ "$#" -ge 2 ] || { echo "--epochs requires a value" >&2; exit 2; }
      EPOCHS="$2"
      shift 2
      ;;
    --tokenize-workers)
      [ "$#" -ge 2 ] || { echo "--tokenize-workers requires a value" >&2; exit 2; }
      TOKENIZE_WORKERS="$2"
      shift 2
      ;;
    --run-label)
      [ "$#" -ge 2 ] || { echo "--run-label requires a value" >&2; exit 2; }
      RUN_LABEL="$2"
      shift 2
      ;;
    --refresh-watch)
      REFRESH_WATCH=1
      shift
      ;;
    --execute)
      EXECUTE=1
      shift
      ;;
    --force)
      FORCE=1
      shift
      ;;
    --verbose)
      VERBOSE=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

activate_venv

resolve_model_ref() {
  python - <<'PY' "$1"
from pathlib import Path
import sys

sys.path.insert(0, str(Path("finetune").resolve()))
from llm_paths import hf_cache_roots, local_watch_model_dir

model_id = sys.argv[1]
watch_dir = local_watch_model_dir(model_id)
if (watch_dir / "config.json").exists():
    print(str(watch_dir))
    raise SystemExit(0)

suffix = f"models--{model_id.replace('/', '--')}"
for root in hf_cache_roots():
    model_root = root / suffix
    snapshots = model_root / "snapshots"
    if snapshots.exists():
        for snapshot in sorted((p for p in snapshots.iterdir() if p.is_dir()), key=lambda p: p.stat().st_mtime, reverse=True):
            if (snapshot / "config.json").exists():
                print(str(snapshot))
                raise SystemExit(0)
    if (model_root / "config.json").exists():
        print(str(model_root))
        raise SystemExit(0)

print(model_id)
PY
}

if [ "$REFRESH_WATCH" -eq 1 ]; then
  python finetune/model_selector.py --watch --refresh --task code --watch-top 8 --top 6 --auto >/dev/null
fi

if [ -z "$MODEL_ID" ]; then
  MODEL_ID="$(resolve_watch_model || true)"
fi

if [ -z "$MODEL_ID" ]; then
  MODEL_ID="$(resolve_selected_model || true)"
fi

if [ -z "$MODEL_ID" ]; then
  echo "No student_watch candidate or selected model available." >&2
  exit 1
fi

SAFE_LABEL="$(printf '%s' "$MODEL_ID" | tr '/:.' '-' | tr -s '-')"
if [[ "$RUN_LABEL" != *"$SAFE_LABEL"* ]]; then
  RUN_LABEL="${RUN_LABEL}-${SAFE_LABEL}"
else
  RUN_LABEL="${RUN_LABEL}"
fi
MODEL_REF="$(resolve_model_ref "$MODEL_ID")"

if [ "$VERBOSE" -eq 1 ]; then
  log "llm_root=$MASCARADE_LLM_DIR"
  log "hf_cache=$HUGGINGFACE_HUB_CACHE"
  log "model_ref=$MODEL_REF"
fi

python - <<'PY' "$MODEL_ID" "$MODEL_REF" "$DOMAIN" "$SEQ_LEN" "$MAX_SAMPLES" "$EPOCHS" "$TOKENIZE_WORKERS" "$RUN_LABEL" "$EXECUTE"
import json
import sys

payload = {
    "model_id": sys.argv[1],
    "model_ref": sys.argv[2],
    "domain": sys.argv[3],
    "seq_len": int(sys.argv[4]),
    "max_samples": int(sys.argv[5]),
    "epochs": int(sys.argv[6]),
    "tokenize_workers": int(sys.argv[7]),
    "run_label": sys.argv[8],
    "execute": sys.argv[9] == "1",
    "command": [
        "python",
        "finetune/run_local.py",
        sys.argv[3],
        "--device",
        "gpu",
        "--model",
        sys.argv[2],
        "--offline",
        "--max-samples",
        sys.argv[5],
        "--epochs",
        sys.argv[6],
        "--seq-len",
        sys.argv[4],
        "--tokenize-workers",
        sys.argv[7],
        "--run-label",
        sys.argv[8],
        "--verbose",
    ],
}
print(json.dumps(payload, indent=2))
PY

if [ "$EXECUTE" -ne 1 ]; then
  exit 0
fi

if [ "$FORCE" -ne 1 ] && ! gpu_preflight; then
  echo "GPU preflight blocked the watch benchmark. Re-run with --force if you want to ignore current VRAM pressure." >&2
  exit 2
fi

if [ "$MODEL_REF" = "$MODEL_ID" ]; then
  log "download=$MODEL_ID"
  python "$ROOT_DIR/finetune/probe_hf_repo.py" "$MODEL_ID" --repo-type model >/dev/null
  python - <<'PY' "$MODEL_ID"
import sys
from huggingface_hub import snapshot_download

path = snapshot_download(sys.argv[1])
print(path)
PY
  MODEL_REF="$(resolve_model_ref "$MODEL_ID")"
else
  log "download=skipped using local_ref=$MODEL_REF"
fi

log "benchmark=$MODEL_ID domain=$DOMAIN"
python finetune/run_local.py \
  "$DOMAIN" \
  --device gpu \
  --model "$MODEL_REF" \
  --offline \
  --max-samples "$MAX_SAMPLES" \
  --epochs "$EPOCHS" \
  --seq-len "$SEQ_LEN" \
  --tokenize-workers "$TOKENIZE_WORKERS" \
  --run-label "$RUN_LABEL" \
  --verbose
