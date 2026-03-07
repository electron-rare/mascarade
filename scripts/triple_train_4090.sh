#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

MODE="${MODE:-triple-mixed-512}"
STOP_COMFYUI="${STOP_COMFYUI:-1}"
COMFYUI_DIR="${COMFYUI_DIR:-/ai/ComfyUI}"
COMFYUI_CMD="${COMFYUI_CMD:-./venv/bin/python main.py --listen --max-upload-size 100}"
Q8B_MODEL="${Q8B_MODEL:-Qwen/Qwen3-8B}"
Q4B_MODEL="${Q4B_MODEL:-Qwen/Qwen3-4B-Instruct-2507}"
EPOCHS="${EPOCHS:-1}"
TOKENIZE_WORKERS="${TOKENIZE_WORKERS:-2}"
RUN_DIR="${RUN_DIR:-$ROOT_DIR/.tmp/${MODE}_$(date +%Y%m%d_%H%M%S)}"
JOB_NAMES=()
JOB_PIDS=()

COMFY_STOPPED=0

need_cmd() {
    command -v "$1" >/dev/null 2>&1 || {
        echo "Missing command: $1" >&2
        exit 1
    }
}

stop_comfyui() {
    [[ "$STOP_COMFYUI" == "1" ]] || return 0
    local pids
    pids="$(pgrep -f "main.py --listen --max-upload-size 100" || true)"
    [[ -n "$pids" ]] || return 0
    echo "[gpu] stopping ComfyUI"
    while IFS= read -r pid; do
        [[ -n "$pid" ]] || continue
        kill "$pid" 2>/dev/null || true
    done <<< "$pids"
    COMFY_STOPPED=1
    sleep 2
}

restart_comfyui() {
    [[ "$COMFY_STOPPED" == "1" ]] || return 0
    [[ -d "$COMFYUI_DIR" ]] || return 0
    echo "[gpu] restarting ComfyUI"
    (
        cd "$COMFYUI_DIR"
        mkdir -p .tmp
        setsid -f sh -lc "$COMFYUI_CMD > .tmp/comfyui.log 2>&1"
    ) || true
    sleep 4
}

gpu_sample() {
    nvidia-smi --query-gpu=memory.used,memory.total,utilization.gpu --format=csv,noheader || true
}

launch_job() {
    local name="$1"
    shift
    JOB_NAMES+=("$name")
    (
        set +e
        python finetune/run_local.py "$@" > "$RUN_DIR/${name}.log" 2>&1
        local code=$?
        echo "$code" > "$RUN_DIR/${name}.exit"
        exit "$code"
    ) &
    JOB_PIDS+=("$!")
}

summarize_job() {
    local name="$1"
    local exit_file="$RUN_DIR/${name}.exit"
    local code="missing"
    if [[ -f "$exit_file" ]]; then
        code="$(cat "$exit_file")"
    fi
    echo "$name=$code"
}

any_pid_alive() {
    local pid
    for pid in "$@"; do
        [[ -n "$pid" ]] || continue
        if kill -0 "$pid" 2>/dev/null; then
            return 0
        fi
    done
    return 1
}

run_profile() {
    local seq_len

    mkdir -p "$RUN_DIR"
    rm -f "$RUN_DIR"/*.log "$RUN_DIR"/*.exit
    JOB_NAMES=()
    JOB_PIDS=()

    case "$MODE" in
        triple-mixed-256)
            seq_len=256
            launch_job q8b stm32 --device gpu --model "$Q8B_MODEL" --offline --max-samples 4 --epochs "$EPOCHS" --seq-len "$seq_len" --tokenize-workers "$TOKENIZE_WORKERS" --output-dir "$RUN_DIR/q8b" --quiet
            launch_job q4b_embedded embedded --device gpu --model "$Q4B_MODEL" --offline --max-samples 4 --epochs "$EPOCHS" --seq-len "$seq_len" --tokenize-workers "$TOKENIZE_WORKERS" --output-dir "$RUN_DIR/q4b_embedded" --quiet
            launch_job q4b_freecad freecad --device gpu --model "$Q4B_MODEL" --offline --max-samples 4 --epochs "$EPOCHS" --seq-len "$seq_len" --tokenize-workers "$TOKENIZE_WORKERS" --output-dir "$RUN_DIR/q4b_freecad" --quiet
            ;;
        triple-mixed-512)
            seq_len=512
            launch_job q8b stm32 --device gpu --model "$Q8B_MODEL" --offline --max-samples 4 --epochs "$EPOCHS" --seq-len "$seq_len" --tokenize-workers "$TOKENIZE_WORKERS" --output-dir "$RUN_DIR/q8b" --quiet
            launch_job q4b_embedded embedded --device gpu --model "$Q4B_MODEL" --offline --max-samples 4 --epochs "$EPOCHS" --seq-len "$seq_len" --tokenize-workers "$TOKENIZE_WORKERS" --output-dir "$RUN_DIR/q4b_embedded" --quiet
            launch_job q4b_freecad freecad --device gpu --model "$Q4B_MODEL" --offline --max-samples 4 --epochs "$EPOCHS" --seq-len "$seq_len" --tokenize-workers "$TOKENIZE_WORKERS" --output-dir "$RUN_DIR/q4b_freecad" --quiet
            ;;
        triple-mixed-768)
            seq_len=768
            launch_job q8b stm32 --device gpu --model "$Q8B_MODEL" --offline --max-samples 4 --epochs "$EPOCHS" --seq-len "$seq_len" --tokenize-workers "$TOKENIZE_WORKERS" --output-dir "$RUN_DIR/q8b" --quiet
            launch_job q4b_embedded embedded --device gpu --model "$Q4B_MODEL" --offline --max-samples 4 --epochs "$EPOCHS" --seq-len "$seq_len" --tokenize-workers "$TOKENIZE_WORKERS" --output-dir "$RUN_DIR/q4b_embedded" --quiet
            launch_job q4b_freecad freecad --device gpu --model "$Q4B_MODEL" --offline --max-samples 4 --epochs "$EPOCHS" --seq-len "$seq_len" --tokenize-workers "$TOKENIZE_WORKERS" --output-dir "$RUN_DIR/q4b_freecad" --quiet
            ;;
        triple-mixed-1024)
            seq_len=1024
            launch_job q8b stm32 --device gpu --model "$Q8B_MODEL" --offline --max-samples 4 --epochs "$EPOCHS" --seq-len "$seq_len" --tokenize-workers "$TOKENIZE_WORKERS" --output-dir "$RUN_DIR/q8b" --quiet
            launch_job q4b_embedded embedded --device gpu --model "$Q4B_MODEL" --offline --max-samples 4 --epochs "$EPOCHS" --seq-len "$seq_len" --tokenize-workers "$TOKENIZE_WORKERS" --output-dir "$RUN_DIR/q4b_embedded" --quiet
            launch_job q4b_freecad freecad --device gpu --model "$Q4B_MODEL" --offline --max-samples 4 --epochs "$EPOCHS" --seq-len "$seq_len" --tokenize-workers "$TOKENIZE_WORKERS" --output-dir "$RUN_DIR/q4b_freecad" --quiet
            ;;
        triple-staggered-8b1024-4b768)
            launch_job q8b stm32 --device gpu --model "$Q8B_MODEL" --offline --max-samples 4 --epochs "$EPOCHS" --seq-len 1024 --tokenize-workers "$TOKENIZE_WORKERS" --output-dir "$RUN_DIR/q8b" --quiet
            launch_job q4b_embedded embedded --device gpu --model "$Q4B_MODEL" --offline --max-samples 4 --epochs "$EPOCHS" --seq-len 768 --tokenize-workers "$TOKENIZE_WORKERS" --output-dir "$RUN_DIR/q4b_embedded" --quiet
            launch_job q4b_freecad freecad --device gpu --model "$Q4B_MODEL" --offline --max-samples 4 --epochs "$EPOCHS" --seq-len 768 --tokenize-workers "$TOKENIZE_WORKERS" --output-dir "$RUN_DIR/q4b_freecad" --quiet
            ;;
        dual-8b-512)
            seq_len=512
            launch_job q8b_stm32 stm32 --device gpu --model "$Q8B_MODEL" --offline --max-samples 4 --epochs "$EPOCHS" --seq-len "$seq_len" --tokenize-workers "$TOKENIZE_WORKERS" --output-dir "$RUN_DIR/q8b_stm32" --quiet
            launch_job q8b_embedded embedded --device gpu --model "$Q8B_MODEL" --offline --max-samples 4 --epochs "$EPOCHS" --seq-len "$seq_len" --tokenize-workers "$TOKENIZE_WORKERS" --output-dir "$RUN_DIR/q8b_embedded" --quiet
            ;;
        *)
            echo "Unsupported MODE: $MODE" >&2
            echo "Expected one of: triple-mixed-256, triple-mixed-512, triple-mixed-768, triple-mixed-1024, triple-staggered-8b1024-4b768, dual-8b-512" >&2
            exit 1
            ;;
    esac

    while any_pid_alive "${JOB_PIDS[@]}"; do
        {
            echo "=== $(date -Is) ==="
            gpu_sample
        } >> "$RUN_DIR/gpu.log"
        sleep 3
    done

    set +e
    local raw_codes=()
    local pid status
    for pid in "${JOB_PIDS[@]}"; do
        wait "$pid"
        status=$?
        raw_codes+=("$status")
    done
    set -e

    echo "[summary]"
    local name
    for name in "${JOB_NAMES[@]}"; do
        summarize_job "$name"
    done
    echo "raw_exit_codes=$(IFS=,; echo "${raw_codes[*]}")"
    echo "run_dir=$RUN_DIR"
}

main() {
    need_cmd nvidia-smi
    need_cmd python
    [[ -x "$ROOT_DIR/venv_tuning/bin/python" ]] || {
        echo "Missing tuning virtualenv. Run ./scripts/bootstrap_finetune_env.sh first." >&2
        exit 1
    }

    trap restart_comfyui EXIT

    stop_comfyui

    echo "[profile]"
    echo "mode=$MODE"
    echo "q8b_model=$Q8B_MODEL"
    echo "q4b_model=$Q4B_MODEL"
    echo "epochs=$EPOCHS"
    echo "tokenize_workers=$TOKENIZE_WORKERS"
    echo "run_dir=$RUN_DIR"

    # shellcheck disable=SC1091
    source "$ROOT_DIR/venv_tuning/bin/activate"
    run_profile
}

main "$@"
