#!/usr/bin/env bash

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
  echo "Source this file instead of executing it." >&2
  exit 2
fi

TUNING_PARTY_ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TUNING_PARTY_RUNS_DIR="$TUNING_PARTY_ROOT_DIR/finetune/runs"

tuning_party_latest_file() {
  local label="${1:-tuning-party}"
  printf '%s/%s.latest\n' "$TUNING_PARTY_RUNS_DIR" "$label"
}

tuning_party_meta_file() {
  local session_dir="$1"
  printf '%s/tuning-party.env\n' "$session_dir"
}

tuning_party_pid_alive() {
  local pid="${1:-}"
  [[ -n "$pid" ]] || return 1
  kill -0 "$pid" 2>/dev/null
}

tuning_party_resolve_session_dir() {
  local label="${1:-tuning-party}"
  local explicit="${2:-}"
  local latest_file candidate

  if [[ -n "$explicit" ]]; then
    [[ -d "$explicit" ]] && printf '%s\n' "$explicit" && return 0
    return 1
  fi

  latest_file="$(tuning_party_latest_file "$label")"
  if [[ -f "$latest_file" ]]; then
    candidate="$(head -n 1 "$latest_file" 2>/dev/null || true)"
    if [[ -n "$candidate" && -d "$candidate" ]]; then
      printf '%s\n' "$candidate"
      return 0
    fi
  fi

  candidate="$(ls -dt "$TUNING_PARTY_RUNS_DIR"/"${label}"_* 2>/dev/null | head -n 1 || true)"
  [[ -n "$candidate" && -d "$candidate" ]] || return 1
  printf '%s\n' "$candidate"
}

tuning_party_load_meta() {
  local session_dir="$1"
  local meta_file
  meta_file="$(tuning_party_meta_file "$session_dir")"
  [[ -f "$meta_file" ]] || return 1
  # shellcheck disable=SC1090
  source "$meta_file"
}

tuning_party_pipeline_phase() {
  local pipeline_log="${1:-}"
  [[ -f "$pipeline_log" ]] || {
    printf 'pending|0|4\n'
    return 0
  }

  if grep -q "Parallel Training Complete" "$pipeline_log"; then
    printf 'cpu-complete|1|1\n'
  elif grep -q "MASCARADE Parallel CPU Training" "$pipeline_log"; then
    printf 'cpu-train|0|1\n'
  elif grep -q "FULL PIPELINE COMPLETE" "$pipeline_log"; then
    printf 'complete|4|4\n'
  elif grep -q "PHASE C" "$pipeline_log"; then
    printf 'dpo|3|4\n'
  elif grep -q "PHASE B" "$pipeline_log"; then
    printf 'rejection|2|4\n'
  elif grep -q "MERGE & DEPLOY" "$pipeline_log"; then
    printf 'merge-deploy|2|4\n'
  elif grep -q "PHASE A" "$pipeline_log"; then
    printf 'sft|1|4\n'
  else
    printf 'starting|0|4\n'
  fi
}

tuning_party_bar() {
  local current="$1"
  local total="$2"
  local width="${3:-24}"
  local filled empty bar

  if [[ "$total" -le 0 ]]; then
    total=1
  fi
  if [[ "$current" -lt 0 ]]; then
    current=0
  fi
  if [[ "$current" -gt "$total" ]]; then
    current="$total"
  fi

  filled=$(( current * width / total ))
  empty=$(( width - filled ))
  bar=""
  while [[ "${#bar}" -lt "$filled" ]]; do
    bar="${bar}#"
  done
  while [[ "${#bar}" -lt $((filled + empty)) ]]; do
    bar="${bar}-"
  done
  printf '[%s] %s/%s' "$bar" "$current" "$total"
}

tuning_party_gpu_summary() {
  if ! command -v nvidia-smi >/dev/null 2>&1; then
    printf 'gpu=n/a'
    return 0
  fi

  local line free_mb used_mb total_mb
  line="$(nvidia-smi --query-gpu=memory.free,memory.used,memory.total --format=csv,noheader,nounits 2>/dev/null | head -n 1 || true)"
  if [[ -z "$line" ]]; then
    printf 'gpu=unavailable'
    return 0
  fi

  free_mb="$(printf '%s' "$line" | cut -d, -f1 | tr -dc '0-9')"
  used_mb="$(printf '%s' "$line" | cut -d, -f2 | tr -dc '0-9')"
  total_mb="$(printf '%s' "$line" | cut -d, -f3 | tr -dc '0-9')"
  printf 'gpu=%s/%s MiB used, %s MiB free' "${used_mb:-0}" "${total_mb:-0}" "${free_mb:-0}"
}

tuning_party_watch_state() {
  local watch_log="${1:-}"
  [[ -f "$watch_log" ]] || {
    printf 'watch=pending'
    return 0
  }

  if grep -q "blocked_runs=" "$watch_log"; then
    printf 'watch=blocked'
  elif grep -q "failed_runs=" "$watch_log"; then
    printf 'watch=failed'
  elif grep -q "max ok cycles reached" "$watch_log"; then
    printf 'watch=complete'
  elif grep -q "cycle=" "$watch_log"; then
    printf 'watch=running'
  else
    printf 'watch=starting'
  fi
}

tuning_party_dataset_research_status() {
  local domain="${1:-}"
  [[ -n "$domain" ]] || {
    printf 'dataset=n/a'
    return 0
  }

  local json_path="${TUNING_PARTY_ROOT_DIR}/finetune/research/${domain}_refresh.json"
  if [[ ! -f "$json_path" ]]; then
    printf 'dataset=%s research=missing' "$domain"
    return 0
  fi

  python - "$json_path" <<'PY'
import json
import sys
path = sys.argv[1]
payload = json.loads(open(path, encoding="utf-8").read())
rv = payload.get("research_validation", {})
domain = payload.get("domain", "n/a")
valid = rv.get("valid")
score = rv.get("quality_score", 0)
min_score = rv.get("minimum_quality_score", 0)
roots = rv.get("web_roots_count", 0)
forums = rv.get("forum_count", 0)
queries = rv.get("query_count", 0)
trusted = rv.get("trusted_domain_count", 0)
print(
    f"dataset={domain} research={'ok' if valid else 'blocked'} "
    f"quality={score}/{min_score} roots={roots} forums={forums} queries={queries} trusted={trusted}"
)
PY
}

tuning_party_format_dataset_research_status() {
  local raw="${1:-dataset=n/a}"
  if [[ "$raw" == *"research=ok"* ]]; then
    printf '%b%s%b\n' "$GREEN" "$raw" "$NC"
  elif [[ "$raw" == *"research=partial"* ]]; then
    printf '%b%s%b\n' "$YELLOW" "$raw" "$NC"
  elif [[ "$raw" == *"research=blocked"* || "$raw" == *"research=missing"* ]]; then
    printf '%b%s%b\n' "$YELLOW" "$raw" "$NC"
  else
    printf '%s\n' "$raw"
  fi
}

tuning_party_dataset_research_summary() {
  local domains_csv="${1:-}"
  if [[ -z "$domains_csv" || "$domains_csv" == "unknown" ]]; then
    printf 'datasets=n/a'
    return 0
  fi

  python - "$TUNING_PARTY_ROOT_DIR" "$domains_csv" <<'PY'
import json
import sys
from pathlib import Path

root = Path(sys.argv[1])
domains_csv = sys.argv[2].strip()
domains = [item.strip() for item in domains_csv.split(",") if item.strip()]
if not domains:
    print("datasets=n/a")
    raise SystemExit(0)

research_dir = root / "finetune" / "research"
ok = 0
missing = 0
scores = []
details = []

for domain in domains:
    path = research_dir / f"{domain}_refresh.json"
    if not path.exists():
      missing += 1
      details.append(f"{domain}:missing")
      continue
    payload = json.loads(path.read_text(encoding="utf-8"))
    rv = payload.get("research_validation", {})
    valid = bool(rv.get("valid"))
    score = int(rv.get("quality_score", 0))
    min_score = int(rv.get("minimum_quality_score", 0))
    scores.append((score, min_score))
    if valid:
      ok += 1
      details.append(f"{domain}:ok:{score}/{min_score}")
    else:
      details.append(f"{domain}:blocked:{score}/{min_score}")

if ok == len(domains) and missing == 0:
    state = "ok"
elif ok > 0:
    state = "partial"
else:
    state = "blocked" if missing < len(domains) else "missing"

if scores:
    min_seen = min(score for score, _ in scores)
    max_seen = max(score for score, _ in scores)
    min_required = max(req for _, req in scores)
else:
    min_seen = 0
    max_seen = 0
    min_required = 0

details_str = ",".join(details[:8])
print(
    f"datasets={len(domains)} research={state} ok={ok}/{len(domains)} "
    f"quality={min_seen}-{max_seen}/{min_required} missing={missing}"
    + (f" details={details_str}" if details_str else "")
)
PY
}

tuning_party_dataset_probe_details() {
  local domains_csv="${1:-}"
  if [[ -z "$domains_csv" || "$domains_csv" == "unknown" ]]; then
    return 0
  fi

  python - "$TUNING_PARTY_ROOT_DIR" "$domains_csv" <<'PY'
import json
import sys
from pathlib import Path

root = Path(sys.argv[1])
domains = [item.strip() for item in sys.argv[2].split(",") if item.strip()]
probe_dir = root / "finetune" / "research_probes"
for domain in domains:
    path = probe_dir / f"{domain}.json"
    if not path.exists():
        print(f"{domain}: probe-missing")
        continue
    payload = json.loads(path.read_text(encoding="utf-8"))
    status = payload.get("status", "unknown")
    reachable = payload.get("reachable_count", 0)
    total = payload.get("total_count", 0)
    print(f"{domain}: probe={status} reachable={reachable}/{total}")
PY
}
