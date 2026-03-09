#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

. "$ROOT_DIR/scripts/llm_env.sh"

LABEL="auto-next-lots"
DOMAIN="stm32"
SEQ_LEN="512"
MAX_SAMPLES="16"
EPOCHS="1"
TOKENIZE_WORKERS="1"
ITERATIONS="1"
PLAN_ONLY=0
RUN_EXECUTE=0
FORCE=0
CONTINUE_ON_ERROR=0
WATCH_REFRESH=1
VERBOSE=0
REPORT_DIR=""
PLAN_REPORT_DIR=""
CHAIN_STATUS_FILE=""
CANDIDATES_FILE=""
WATCH_REPORT=""
PLAN_STATUS="pending"

usage() {
  cat <<'EOF'
Usage: ./scripts/auto_chain_next_lots.sh [options]

Chaîne automatiquement le prochain lot utile: plan -> extraction des candidats
watch -> benchmarks (séquentiels).

Options:
  --label NAME                Prefixe des labels de run
  --iterations N              Nombre max de candidats watch à traiter (default: 1)
  --domain NAME               Domaine pour le benchmark watch (default: stm32)
  --seq-len N                 Seq len run_local (default: 512)
  --max-samples N             Max samples run_local (default: 16)
  --epochs N                  Epochs run_local (default: 1)
  --tokenize-workers N        Tokenize workers (default: 1)
  --skip-watch-refresh        Ne pas relancer model_selector
  --plan-only                 Planification uniquement (pas de benchmark)
  --execute                   Exécuter réellement les watch benchmarks
  --force                     Passe le préflight VRAM (utile avec --execute)
  --continue-on-error         Continue avec le candidat suivant en cas d'erreur
  --verbose                   Affiche les commandes exécutées
  --report-dir PATH           Répertoire d'artefacts (default: finetune/runs/<label>_<timestamp>)
  -h, --help                  Affiche l'aide
EOF
}

log() {
  printf '[auto-chain] %s\n' "$*"
}

die() {
  echo "auto-chain: $*" >&2
  exit 1
}

activate_venv() {
  if [ -f "$ROOT_DIR/venv_tuning/bin/activate" ]; then
    # shellcheck disable=SC1091
    source "$ROOT_DIR/venv_tuning/bin/activate"
    return 0
  fi
  die "No venv_tuning found. Run ./scripts/bootstrap_finetune_env.sh first."
}

safe_slug() {
  printf '%s' "$1" | tr '/:.@' '-' | tr -s '-'
}

ensure_positive_integer() {
  local name="$1"
  local value="$2"
  if ! [[ "$value" =~ ^[0-9]+$ ]]; then
    die "$name must be a non-negative integer: $value"
  fi
}

resolve_report() {
  local candidates=(
    "/dev/shm/mascarade-finetune-state/model_watch_report.json"
    "/tmp/mascarade-finetune-state/model_watch_report.json"
    "$ROOT_DIR/finetune/model_watch_report.json"
  )
  local path
  for path in "${candidates[@]}"; do
    if [ -f "$path" ]; then
      echo "$path"
      return 0
    fi
  done
  return 1
}

resolve_selected_model() {
  python - <<'PY'
from pathlib import Path
import json

candidates = [
    Path("/dev/shm/mascarade-finetune-state/selected_model.json"),
    Path("/tmp/mascarade-finetune-state/selected_model.json"),
    Path("finetune/selected_model.json"),
]

for report_path in candidates:
    if not report_path.exists():
        continue
    try:
        payload = json.loads(report_path.read_text(encoding="utf-8"))
    except Exception:
        continue
    model_id = str(payload.get("model_id") or payload.get("selected_model", {}).get("model_id") or "").strip()
    if model_id:
        print(model_id)
        raise SystemExit(0)

print("", end="")
raise SystemExit(1)
PY
}

extract_candidates() {
  local report_file="$1"
  local max_count="$2"
  python - "$report_file" "$max_count" <<'PY'
import json
import sys
from pathlib import Path

report_file = Path(sys.argv[1])
max_count = int(sys.argv[2])
payload = json.loads(report_file.read_text(encoding="utf-8"))

seen = set()
candidates = []


def push(item):
    model_id = (item or "").strip()
    if not model_id or model_id in seen:
        return
    seen.add(model_id)
    candidates.append(model_id)


for key in ("student_watch", "entries"):
    for entry in payload.get(key) or []:
        if key == "entries" and str(entry.get("suggested_lane") or "").strip() != "student_watch":
            continue
        push(str(entry.get("model_id") or ""))
        if len(candidates) >= max_count:
            break
    if len(candidates) >= max_count:
        break

if not candidates and payload.get("selected_model"):
    push(str((payload.get("selected_model") or {}).get("model_id") or ""))

if not candidates:
    for entry in (payload.get("entries") or []):
        push(str(entry.get("model_id") or ""))
        if len(candidates) >= max_count:
            break

for model_id in candidates[:max_count]:
    print(model_id)
PY
} 

run_plan() {
  PLAN_REPORT_DIR="$REPORT_DIR/planner"
  mkdir -p "$PLAN_REPORT_DIR"

  local cmd=( "$ROOT_DIR/scripts/next_finetune_lots.sh" )
  cmd+=( --label "${LABEL}-plan" )
  cmd+=( --skip-watch-bench --skip-cad-smoke --skip-components-review )
  cmd+=( --report-dir "$PLAN_REPORT_DIR" )
  if [ "$WATCH_REFRESH" -eq 0 ]; then
    cmd+=( --skip-watch )
  fi

  if [ "$VERBOSE" -eq 1 ]; then
    log "plan cmd: ${cmd[*]}"
  fi

  local plan_log="$PLAN_REPORT_DIR/next_finetune_lots.log"
  PLAN_STATUS="failed"
  set +e
  "${cmd[@]}" >"$plan_log" 2>&1
  local plan_rc=$?
  set -e

  if [ -f "$PLAN_REPORT_DIR/summary.json" ]; then
    cp "$PLAN_REPORT_DIR/summary.json" "$REPORT_DIR/plan-summary.json"
  fi

  if [ "$plan_rc" -eq 0 ]; then
    PLAN_STATUS="ok"
    return 0
  fi

  if [ "$CONTINUE_ON_ERROR" -eq 1 ]; then
    log "next lot plan failed (rc=$plan_rc) but continue-on-error is active"
    return 0
  fi

  die "next lot planning failed. See: $plan_log"
}

append_status_record() {
  local candidate="$1"
  local status="$2"
  local exit_code="$3"
  local run_label="$4"
  local log_path="$5"
  CAND="$candidate" \
  STATUS="$status" \
  EXIT_CODE="$exit_code" \
  RUN_LABEL="$run_label" \
  LOG_PATH="$log_path" \
  python -c '
import json
import os
from datetime import datetime, timezone

payload = {
    "candidate": os.environ["CAND"],
    "status": os.environ["STATUS"],
    "exit_code": int(os.environ["EXIT_CODE"]),
    "run_label": os.environ["RUN_LABEL"],
    "log_path": os.environ["LOG_PATH"],
    "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
}
print(json.dumps(payload, ensure_ascii=False))
' >> "$CHAIN_STATUS_FILE"
}

write_manifest() {
  python - <<'PY'
import json
import os
from pathlib import Path
from datetime import datetime, timezone

report_dir = Path(os.environ["REPORT_DIR"])
status_path = Path(os.environ["CHAIN_STATUS_FILE"])
candidates_path = Path(os.environ["CANDIDATES_FILE"])

plan_status = os.environ.get("PLAN_STATUS", "unknown")
watch_report = os.environ.get("WATCH_REPORT", "")

records = []
if status_path.exists():
    for line in status_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            records.append(json.loads(line))
        except Exception:
            continue

run_manifest = report_dir / "run_manifest.json"
run_manifest.write_text(json.dumps(records, indent=2), encoding="utf-8")

candidates = []
if candidates_path.exists():
    candidates = [
        line.strip()
        for line in candidates_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

summary = {
    "generated_at": "",
    "label": os.environ.get("LABEL", ""),
    "report_dir": str(report_dir),
    "iterations": int(os.environ.get("ITERATIONS", "0")),
    "run_execute": os.environ.get("RUN_EXECUTE", "0") == "1",
    "force": os.environ.get("FORCE", "0") == "1",
    "continue_on_error": os.environ.get("CONTINUE_ON_ERROR", "0") == "1",
    "domain": os.environ.get("DOMAIN", ""),
    "seq_len": int(os.environ.get("SEQ_LEN", "0")),
    "max_samples": int(os.environ.get("MAX_SAMPLES", "0")),
    "epochs": int(os.environ.get("EPOCHS", "0")),
    "tokenize_workers": int(os.environ.get("TOKENIZE_WORKERS", "0")),
    "plan_status": plan_status,
    "watch_report": watch_report,
    "candidates": candidates,
    "status_records": records,
    "candidates_total": len(candidates),
    "runs_total": len(records),
    "runs_ok": sum(1 for r in records if r.get("status") == "ok"),
    "runs_failed": sum(1 for r in records if r.get("status") == "failed"),
    "runs_blocked": sum(1 for r in records if r.get("status") == "blocked"),
    "runs_planned": sum(1 for r in records if r.get("status") == "planned"),
    "logs": {
        "plan": str(report_dir / "next-finetune-planner.log"),
        "plan_summary": str(report_dir / "plan-summary.json"),
        "candidates": str(report_dir / "candidates.txt"),
        "run_manifest": str(report_dir / "run_manifest.json"),
    },
}

summary["generated_at"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
summary["manifest_version"] = "auto-chain-next-lots-v1"

summary_path = report_dir / "manifest.json"
summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
PY
}

if [ "$#" -gt 0 ]; then
  while [ "$#" -gt 0 ]; do
    case "$1" in
      --label)
        [ "$#" -ge 2 ] || { echo "--label requires a value" >&2; exit 2; }
        LABEL="$2"
        shift 2
        ;;
      --iterations)
        [ "$#" -ge 2 ] || { echo "--iterations requires a value" >&2; exit 2; }
        ensure_positive_integer "--iterations" "$2"
        ITERATIONS="$2"
        shift 2
        ;;
      --domain)
        [ "$#" -ge 2 ] || { echo "--domain requires a value" >&2; exit 2; }
        DOMAIN="$2"
        shift 2
        ;;
      --seq-len)
        [ "$#" -ge 2 ] || { echo "--seq-len requires a value" >&2; exit 2; }
        ensure_positive_integer "--seq-len" "$2"
        SEQ_LEN="$2"
        shift 2
        ;;
      --max-samples)
        [ "$#" -ge 2 ] || { echo "--max-samples requires a value" >&2; exit 2; }
        ensure_positive_integer "--max-samples" "$2"
        MAX_SAMPLES="$2"
        shift 2
        ;;
      --epochs)
        [ "$#" -ge 2 ] || { echo "--epochs requires a value" >&2; exit 2; }
        ensure_positive_integer "--epochs" "$2"
        EPOCHS="$2"
        shift 2
        ;;
      --tokenize-workers)
        [ "$#" -ge 2 ] || { echo "--tokenize-workers requires a value" >&2; exit 2; }
        ensure_positive_integer "--tokenize-workers" "$2"
        TOKENIZE_WORKERS="$2"
        shift 2
        ;;
      --skip-watch-refresh)
        WATCH_REFRESH=0
        shift
        ;;
      --plan-only)
        PLAN_ONLY=1
        shift
        ;;
      --execute)
        RUN_EXECUTE=1
        shift
        ;;
      --force)
        FORCE=1
        shift
        ;;
      --continue-on-error)
        CONTINUE_ON_ERROR=1
        shift
        ;;
      --verbose)
        VERBOSE=1
        shift
        ;;
      --report-dir)
        [ "$#" -ge 2 ] || { echo "--report-dir requires a value" >&2; exit 2; }
        REPORT_DIR="$2"
        shift 2
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
fi

activate_venv

if [ -z "$REPORT_DIR" ]; then
  STAMP="$(date +%Y%m%d_%H%M%S)"
  REPORT_DIR="$ROOT_DIR/finetune/runs/${LABEL}_${STAMP}"
fi
mkdir -p "$REPORT_DIR"

CANDIDATES_FILE="$REPORT_DIR/candidates.txt"
CHAIN_STATUS_FILE="$REPORT_DIR/run_status.jsonl"
: > "$CHAIN_STATUS_FILE"

run_plan
cp "$PLAN_REPORT_DIR/next_finetune_lots.log" "$REPORT_DIR/next-finetune-planner.log" 2>/dev/null || true

WATCH_REPORT=""
FALLBACK_SELECTED=""
if [ "$WATCH_REFRESH" -eq 1 ]; then
  if ! WATCH_REPORT="$(resolve_report)"; then
    if [ "$CONTINUE_ON_ERROR" -eq 1 ]; then
      log "watch report unavailable after planning; trying selected_model fallback."
      FALLBACK_SELECTED="$(resolve_selected_model || true)"
      if [ -z "$FALLBACK_SELECTED" ]; then
        die "No model watch report and no fallback selected_model. Re-run later when watch report is available."
      fi
    else
      die "No model watch report found after planning."
    fi
  fi
else
  if ! WATCH_REPORT="$(resolve_report)"; then
    if [ "$CONTINUE_ON_ERROR" -eq 1 ]; then
      log "skip-watch-refresh used and no watch report cached; using selected_model fallback."
      FALLBACK_SELECTED="$(resolve_selected_model || true)"
      if [ -z "$FALLBACK_SELECTED" ]; then
        die "No cached watch report and no selected_model fallback available."
      fi
    else
      die "No model watch report found. Re-run without --skip-watch-refresh."
    fi
  fi
fi

WATCH_REPORT="${WATCH_REPORT:-$REPORT_DIR/model_watch_fallback.json}"
if [ -n "$FALLBACK_SELECTED" ]; then
  python - <<PY
import json
from pathlib import Path

report = {"selected_model": {"model_id": "$FALLBACK_SELECTED"}}
Path("$WATCH_REPORT").write_text(json.dumps(report, indent=2), encoding="utf-8")
PY
fi

export WATCH_REPORT
export REPORT_DIR
export CANDIDATES_FILE
export CHAIN_STATUS_FILE
export PLAN_STATUS
export LABEL
export ITERATIONS
export RUN_EXECUTE
export FORCE
export CONTINUE_ON_ERROR
export DOMAIN
export SEQ_LEN
export MAX_SAMPLES
export EPOCHS
export TOKENIZE_WORKERS

if ! mapfile -t CANDIDATES < <(extract_candidates "$WATCH_REPORT" "$ITERATIONS"); then
  log "watch report parse failed, falling back to selected_model path."
  if [ -z "$FALLBACK_SELECTED" ]; then
    FALLBACK_SELECTED="$(resolve_selected_model || true)"
  fi
  if [ -n "$FALLBACK_SELECTED" ]; then
    CANDIDATES=("$FALLBACK_SELECTED")
    if [ -z "${WATCH_REPORT}" ]; then
      python - <<PY
import json
from pathlib import Path

report = {"selected_model": {"model_id": "$FALLBACK_SELECTED"}}
Path("$REPORT_DIR/model_watch_fallback.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
PY
      WATCH_REPORT="$REPORT_DIR/model_watch_fallback.json"
      export WATCH_REPORT
    fi
  else
    die "No candidates found in watch report and no selected_model fallback."
  fi
fi
if [ "${#CANDIDATES[@]}" -eq 0 ]; then
  die "No watch candidates available."
fi

printf '%s\n' "${CANDIDATES[@]}" > "$CANDIDATES_FILE"
log "Watch candidates: $(printf '%s ' "${CANDIDATES[@]}")"

if [ "$PLAN_ONLY" -eq 1 ]; then
  for idx in "${!CANDIDATES[@]}"; do
    candidate="${CANDIDATES[$idx]}"
    safe="$(safe_slug "$candidate")"
    run_label="${LABEL}-${idx}-${safe}"
    append_status_record "$candidate" "planned" 0 "$run_label" "$REPORT_DIR/candidate-${safe}-plan.txt"
  done
  write_manifest
  log "plan-only mode done. Artefacts: candidates.txt, manifest.json, run_manifest.json."
  exit 0
fi

if [ "$RUN_EXECUTE" -eq 0 ]; then
  for idx in "${!CANDIDATES[@]}"; do
    candidate="${CANDIDATES[$idx]}"
    safe="$(safe_slug "$candidate")"
    run_label="${LABEL}-${idx}-${safe}"
    plan_log="$REPORT_DIR/candidate-${safe}-plan.txt"
    {
      echo "[auto-chain] dry-run candidate[$idx]"
      echo "model=$candidate"
      echo "domain=$DOMAIN"
      echo "seq_len=$SEQ_LEN"
      echo "max_samples=$MAX_SAMPLES"
      echo "epochs=$EPOCHS"
      echo "tokenize_workers=$TOKENIZE_WORKERS"
      echo "run_label=$run_label"
    } > "$plan_log"
    append_status_record "$candidate" "planned" 0 "$run_label" "$plan_log"
  done
  write_manifest
  log "Dry-run finished. Run with --execute to run benchmarks."
  exit 0
fi

FAILED=0

for idx in "${!CANDIDATES[@]}"; do
  candidate="${CANDIDATES[$idx]}"
  safe="$(safe_slug "$candidate")"
  BENCH_RUN_LABEL="${LABEL}-${idx}-${safe}"
  BENCH_LOG="$REPORT_DIR/bench-${idx}-${safe}.log"

  CMD=(
    "$ROOT_DIR/scripts/bench_watch_candidate.sh"
    --model "$candidate"
    --domain "$DOMAIN"
    --seq-len "$SEQ_LEN"
    --max-samples "$MAX_SAMPLES"
    --epochs "$EPOCHS"
    --tokenize-workers "$TOKENIZE_WORKERS"
    --run-label "$BENCH_RUN_LABEL"
    --execute
  )
  if [ "$FORCE" -eq 1 ]; then
    CMD+=(--force)
  fi

  if [ "$VERBOSE" -eq 1 ]; then
    log "bench cmd: ${CMD[*]}"
  fi

  set +e
  "${CMD[@]}" > "$BENCH_LOG" 2>&1
  rc=$?
  set -e

  if [ "$rc" -eq 0 ]; then
    append_status_record "$candidate" "ok" 0 "$BENCH_RUN_LABEL" "$BENCH_LOG"
    continue
  fi

  if [ "$rc" -eq 2 ]; then
    append_status_record "$candidate" "blocked" "$rc" "$BENCH_RUN_LABEL" "$BENCH_LOG"
    log "bench preflight blocked for $candidate (rc=$rc)."
  else
    append_status_record "$candidate" "failed" "$rc" "$BENCH_RUN_LABEL" "$BENCH_LOG"
  fi

  if [ "$rc" -ne 0 ] && [ "$CONTINUE_ON_ERROR" -eq 0 ]; then
    FAILED=1
    break
  fi
  if [ "$rc" -ne 0 ] && [ "$CONTINUE_ON_ERROR" -eq 1 ]; then
    log "continue-on-error active: next candidate ..."
  fi
done

write_manifest

if [ "$FAILED" -ne 0 ]; then
  exit 1
fi
