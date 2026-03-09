#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

DOMAIN="${DOMAIN:-stm32}"
if [[ $# -gt 0 && "${1#-}" == "$1" ]]; then
    DOMAIN="$1"
    shift
fi

HOST_CORE_PORT="${HOST_CORE_PORT:-18100}"
HOST_CORE_URL="${HOST_CORE_URL:-http://127.0.0.1:${HOST_CORE_PORT}}"
HOST_OLLAMA_URL="${HOST_OLLAMA_URL:-http://127.0.0.1:11434}"
HOST_CORE_PID_FILE="${HOST_CORE_PID_FILE:-$ROOT_DIR/.tmp/core-host-tuning.pid}"
HOST_CORE_LOG_FILE="${HOST_CORE_LOG_FILE:-$ROOT_DIR/.tmp/core-host-tuning.log}"

TEACHER_PROVIDER="${TEACHER_PROVIDER:-ollama}"
TEACHER_MODEL="${TEACHER_MODEL:-qwen2.5:14b}"

# Default fit for this repo and this machine:
# - code / embedded oriented domain data
# - 24 GB VRAM available
# - QLoRA 4-bit path in finetune/train_local.py
STUDENT_MODEL="${STUDENT_MODEL:-Qwen/Qwen2.5-Coder-7B-Instruct}"

# Current text-only generalist alternative from official Qwen releases:
#   STUDENT_MODEL=Qwen/Qwen3-4B-Instruct-2507 ./scripts/finetune_host_gpu.sh

MAX_SOURCE_SAMPLES="${MAX_SOURCE_SAMPLES:-64}"
SAMPLES_PER_SOURCE="${SAMPLES_PER_SOURCE:-2}"
STUDENT_MAX_SAMPLES="${STUDENT_MAX_SAMPLES:-192}"
SEQ_LEN="${SEQ_LEN:-1024}"
EPOCHS="${EPOCHS:-1}"
TOKENIZE_WORKERS="${TOKENIZE_WORKERS:-4}"
DISTILL_CONCURRENCY="${DISTILL_CONCURRENCY:-1}"
TEMPERATURE="${TEMPERATURE:-0}"
MAX_TOKENS="${MAX_TOKENS:-2048}"
TIMEOUT="${TIMEOUT:-90}"
TRAIN_OUTPUT_DIR="${TRAIN_OUTPUT_DIR:-$ROOT_DIR/.tmp/finetune-${DOMAIN}-$(date +%Y%m%d_%H%M%S)}"
FREE_GPU_BEFORE_RUN="${FREE_GPU_BEFORE_RUN:-1}"
UNLOAD_OLLAMA_BEFORE_RUN="${UNLOAD_OLLAMA_BEFORE_RUN:-0}"
UNLOAD_COMFYUI_BEFORE_RUN="${UNLOAD_COMFYUI_BEFORE_RUN:-0}"
COMFYUI_API_URL="${COMFYUI_API_URL:-http://127.0.0.1:8188}"

need_cmd() {
    command -v "$1" >/dev/null 2>&1 || {
        echo "Missing command: $1" >&2
        exit 1
    }
}

student_requires_qwen35_support() {
    local model_name
    model_name="${STUDENT_MODEL,,}"
    [[ "$model_name" == *"qwen/qwen3.5-"* ]]
}

venv_supports_qwen35() {
    [[ -x "$ROOT_DIR/venv_tuning/bin/python" ]] || return 1
    "$ROOT_DIR/venv_tuning/bin/python" - <<'PY' >/dev/null 2>&1
import importlib.util
raise SystemExit(0 if importlib.util.find_spec("transformers.models.qwen3_5") else 1)
PY
}

extract_api_key() {
    awk -F= '
        $1 == "MASCARADE_API_KEY" {
            value = substr($0, index($0, "=") + 1)
            gsub(/^"/, "", value)
            gsub(/"$/, "", value)
            print value
            exit
        }
    ' "$ROOT_DIR/.env"
}

wait_http() {
    local url="$1"
    local attempts="${2:-30}"
    local delay="${3:-1}"
    local i
    for ((i = 1; i <= attempts; i++)); do
        if curl -fsS --max-time 5 "$url" >/dev/null 2>&1; then
            return 0
        fi
        sleep "$delay"
    done
    return 1
}

ensure_bootstrap() {
    if [[ -x "$ROOT_DIR/venv_tuning/bin/python" ]]; then
        if student_requires_qwen35_support && ! venv_supports_qwen35; then
            echo "[bootstrap] upgrading venv_tuning for Qwen3.5 support"
            TRANSFORMERS_CHANNEL="${TRANSFORMERS_CHANNEL:-main}" \
                "$ROOT_DIR/scripts/bootstrap_finetune_env.sh"
        fi
        return 0
    fi
    if student_requires_qwen35_support; then
        TRANSFORMERS_CHANNEL="${TRANSFORMERS_CHANNEL:-main}" \
            "$ROOT_DIR/scripts/bootstrap_finetune_env.sh"
        return 0
    fi
    "$ROOT_DIR/scripts/bootstrap_finetune_env.sh"
}

ensure_host_ollama() {
    curl -fsS --max-time 5 "$HOST_OLLAMA_URL/api/tags" >/dev/null
}

print_gpu_overview() {
    command -v nvidia-smi >/dev/null 2>&1 || return 0
    echo "[gpu]"
    nvidia-smi --query-gpu=name,memory.used,memory.total,utilization.gpu --format=csv,noheader || true
}

stop_tracked_host_core() {
    if [[ -f "$HOST_CORE_PID_FILE" ]] && kill -0 "$(cat "$HOST_CORE_PID_FILE")" 2>/dev/null; then
        kill "$(cat "$HOST_CORE_PID_FILE")" || true
        sleep 2
    fi
}

unload_ollama_models() {
    command -v ollama >/dev/null 2>&1 || return 0

    local models
    models="$(
        ollama ps 2>/dev/null | awk 'NR > 1 && $1 != "" { print $1 }' || true
    )"
    [[ -n "$models" ]] || return 0

    echo "[gpu] unloading Ollama models"
    while IFS= read -r model; do
        [[ -n "$model" ]] || continue
        ollama stop "$model" >/dev/null 2>&1 || true
    done <<< "$models"
    sleep 2
}

unload_comfyui_models() {
    echo "[gpu] unloading ComfyUI models"
    curl -fsS --max-time 10 \
        -X POST \
        -H "Content-Type: application/json" \
        -d '{"unload_models":true,"free_memory":true}' \
        "$COMFYUI_API_URL/free" >/dev/null 2>&1 || true
    sleep 2
}

release_gpu_memory() {
    [[ "$FREE_GPU_BEFORE_RUN" == "1" ]] || return 0

    echo "[gpu] preflight release"
    print_gpu_overview
    stop_tracked_host_core
    if [[ "$UNLOAD_OLLAMA_BEFORE_RUN" == "1" ]]; then
        unload_ollama_models
    fi
    if [[ "$UNLOAD_COMFYUI_BEFORE_RUN" == "1" ]]; then
        unload_comfyui_models
    fi
    print_gpu_overview
}

ensure_host_core() {
    local api_key="$1"
    mkdir -p "$ROOT_DIR/.tmp"

    if curl -fsS --max-time 5 "$HOST_CORE_URL/health" >/dev/null 2>&1; then
        return 0
    fi

    stop_tracked_host_core

    if [[ ! -x "$ROOT_DIR/core/.venv/bin/python" ]]; then
        echo "Missing core virtualenv at core/.venv" >&2
        exit 1
    fi

    setsid env \
        OLLAMA_ENABLED=true \
        OLLAMA_BASE_URL="$HOST_OLLAMA_URL" \
        CORE_HOST=127.0.0.1 \
        CORE_PORT="$HOST_CORE_PORT" \
        DEFAULT_PROVIDER=ollama \
        DEFAULT_MODEL="$TEACHER_MODEL" \
        MASCARADE_API_KEY="$api_key" \
        "$ROOT_DIR/core/.venv/bin/python" -m uvicorn mascarade.server:app \
        --host 127.0.0.1 \
        --port "$HOST_CORE_PORT" \
        > "$HOST_CORE_LOG_FILE" 2>&1 < /dev/null &

    echo $! > "$HOST_CORE_PID_FILE"

    wait_http "$HOST_CORE_URL/health" 30 1 || {
        echo "Host tuning core did not start. Log: $HOST_CORE_LOG_FILE" >&2
        exit 1
    }
}

main() {
    need_cmd curl
    ensure_bootstrap
    release_gpu_memory
    ensure_host_ollama

    local api_key
    api_key="$(extract_api_key)"
    if [[ -z "$api_key" ]]; then
        echo "MASCARADE_API_KEY is missing in $ROOT_DIR/.env" >&2
        exit 1
    fi

    ensure_host_core "$api_key"

    cat <<EOF
[finetune-host-gpu]
domain=$DOMAIN
api_url=$HOST_CORE_URL
teacher=${TEACHER_PROVIDER}/${TEACHER_MODEL}
student=$STUDENT_MODEL
max_source_samples=$MAX_SOURCE_SAMPLES
samples_per_source=$SAMPLES_PER_SOURCE
distill_concurrency=$DISTILL_CONCURRENCY
student_max_samples=$STUDENT_MAX_SAMPLES
seq_len=$SEQ_LEN
epochs=$EPOCHS
tokenize_workers=$TOKENIZE_WORKERS
output_dir=$TRAIN_OUTPUT_DIR
EOF

    ./scripts/distill_and_train.sh "$DOMAIN" \
        --api-url "$HOST_CORE_URL" \
        --teacher-provider "$TEACHER_PROVIDER" \
        --teacher-model "$TEACHER_MODEL" \
        --temperature "$TEMPERATURE" \
        --max-tokens "$MAX_TOKENS" \
        --timeout "$TIMEOUT" \
        --max-source-samples "$MAX_SOURCE_SAMPLES" \
        --samples-per-source "$SAMPLES_PER_SOURCE" \
        --distill-concurrency "$DISTILL_CONCURRENCY" \
        --student-model "$STUDENT_MODEL" \
        --student-max-samples "$STUDENT_MAX_SAMPLES" \
        --device gpu \
        --epochs "$EPOCHS" \
        --seq-len "$SEQ_LEN" \
        --tokenize-workers "$TOKENIZE_WORKERS" \
        --train-output-dir "$TRAIN_OUTPUT_DIR" \
        --verbose \
        "$@"
}

main "$@"
