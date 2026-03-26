#!/usr/bin/env bash
# benchmark-v4-all.sh — Post-training benchmark pipeline v4
# Imports all trained LoRA models into Ollama on KXKM-AI, runs 130-prompt
# benchmark with Codestral API judge, produces BENCHMARK_V4_REPORT.md
#
# Usage: ./scripts/benchmark-v4-all.sh [--dry-run] [--skip-import]
#
# Requires:
#   - SSH access to kxkm@100.87.54.119 (KXKM-AI)
#   - Codestral API key
#   - llama.cpp (llama-export-lora, llama-quantize) on KXKM-AI
#   - Python 3 + httpx on KXKM-AI

set -euo pipefail

# ────────────────────────────────────────────────────────────
# Configuration
# ────────────────────────────────────────────────────────────
REMOTE_HOST="${KXKM_HOST:-kxkm@100.87.54.119}"
REMOTE_DIR="/ai/saisail/mascarade"
RUNS_DIR="${REMOTE_DIR}/finetune/runs"
PROMPTS_FILE="${REMOTE_DIR}/finetune/eval/benchmark_prompts.jsonl"
ADVERSARIAL_FILE="${REMOTE_DIR}/finetune/eval/adversarial_prompts.jsonl"
OLLAMA_PORT="${OLLAMA_PORT:-11434}"
CODESTRAL_URL="https://codestral.mistral.ai/v1/chat/completions"
CODESTRAL_KEY="${CODESTRAL_API_KEY:-JbYYQUUpHOOFjpV5UuSct6QM4cT6otEl}"
QUANTIZATION="${QUANTIZATION:-Q4_K_M}"
REPORT_NAME="BENCHMARK_V4_REPORT.md"
TMUX_SESSION="bench-v4"

# ── Couleurs ──
if [[ -z "${NO_COLOR:-}" ]] && [[ -t 1 ]]; then
    BOLD='\033[1m' DIM='\033[2m'
    RED='\033[0;31m' GREEN='\033[0;32m' YELLOW='\033[0;33m'
    CYAN='\033[0;36m' MAGENTA='\033[0;35m' NC='\033[0m'
else
    BOLD='' DIM='' RED='' GREEN='' YELLOW='' CYAN='' MAGENTA='' NC=''
fi

log()     { echo -e "  ${CYAN}>>>${NC} $*"; }
ok()      { echo -e "  ${GREEN}[ok]${NC} $*"; }
warn()    { echo -e "  ${YELLOW}[warn]${NC} $*"; }
err()     { echo -e "  ${RED}[err]${NC} $*" >&2; }
die()     { err "$@"; exit 1; }
section() { echo ""; echo -e "  ${MAGENTA}${BOLD}=== $* ===${NC}"; }

# ── Parse arguments ──
DRY_RUN=false
SKIP_IMPORT=false
for arg in "$@"; do
    case "$arg" in
        --dry-run)      DRY_RUN=true ;;
        --skip-import)  SKIP_IMPORT=true ;;
        -h|--help)
            echo "Usage: $0 [--dry-run] [--skip-import]"
            exit 0 ;;
        *)  die "Unknown option: $arg" ;;
    esac
done

# ── Helper: run command on KXKM-AI ──
remote() {
    if [[ "$DRY_RUN" == true ]]; then
        log "[dry-run] ssh ${REMOTE_HOST} $*"
        return 0
    fi
    ssh -o ConnectTimeout=10 -o BatchMode=yes "${REMOTE_HOST}" "$@"
}

remote_check() {
    ssh -o ConnectTimeout=5 -o BatchMode=yes "${REMOTE_HOST}" "echo ok" &>/dev/null
}

# ────────────────────────────────────────────────────────────
# Step 0: Verify connectivity
# ────────────────────────────────────────────────────────────
section "Connectivity check"
if ! remote_check; then
    die "Cannot SSH to ${REMOTE_HOST}. Check your SSH config."
fi
ok "SSH to ${REMOTE_HOST}"

# ────────────────────────────────────────────────────────────
# Step 1: Start Ollama on KXKM-AI
# ────────────────────────────────────────────────────────────
section "Starting Ollama on KXKM-AI"

OLLAMA_RUNNING=$(remote "curl -sf http://localhost:${OLLAMA_PORT}/api/tags >/dev/null 2>&1 && echo yes || echo no")

if [[ "$OLLAMA_RUNNING" == "yes" ]]; then
    ok "Ollama already running on port ${OLLAMA_PORT}"
else
    log "Starting Ollama via systemctl..."
    remote "sudo systemctl start ollama 2>/dev/null || (nohup ollama serve > /tmp/ollama-bench.log 2>&1 &)"
    # Wait for Ollama to be ready
    for i in $(seq 1 30); do
        if remote "curl -sf http://localhost:${OLLAMA_PORT}/api/tags >/dev/null 2>&1"; then
            ok "Ollama started (attempt ${i})"
            break
        fi
        [[ "$i" -eq 30 ]] && die "Ollama failed to start after 30s"
        sleep 1
    done
fi

# ────────────────────────────────────────────────────────────
# Step 2: Discover and import LoRA models
# ────────────────────────────────────────────────────────────
section "Discovering LoRA runs"

DISCOVERED=$(remote "find ${RUNS_DIR} -maxdepth 2 -name manifest.json -path '*/mascarade-*/manifest.json' 2>/dev/null | sort" || true)

if [[ -z "$DISCOVERED" ]]; then
    die "No training runs found in ${RUNS_DIR}/mascarade-*/"
fi

MANIFEST_COUNT=$(echo "$DISCOVERED" | wc -l | tr -d ' ')
log "Found ${MANIFEST_COUNT} training run(s)"

# Build model list from manifests
declare -a MODEL_NAMES=()
declare -a MODEL_DIRS=()

while IFS= read -r manifest_path; do
    run_dir=$(dirname "$manifest_path")
    lora_dir="${run_dir}/lora"
    # Extract model name from manifest
    model_name=$(remote "python3 -c \"import json; m=json.load(open('${manifest_path}')); print(m.get('name', '$(basename "$run_dir")')  )\"" 2>/dev/null || basename "$run_dir")
    # Clean name for Ollama (lowercase, no spaces)
    ollama_name=$(echo "$model_name" | tr '[:upper:]' '[:lower:]' | tr ' ' '-' | sed 's/[^a-z0-9_.-]/-/g')

    if remote "test -d '${lora_dir}'" 2>/dev/null; then
        MODEL_NAMES+=("$ollama_name")
        MODEL_DIRS+=("$run_dir")
        ok "  ${ollama_name} -> ${run_dir}"
    else
        warn "  Skipping ${model_name}: no lora/ directory"
    fi
done <<< "$DISCOVERED"

if [[ ${#MODEL_NAMES[@]} -eq 0 ]]; then
    die "No valid LoRA models found (all missing lora/ directory)"
fi

# Import models into Ollama (merge + GGUF + create)
if [[ "$SKIP_IMPORT" == false ]]; then
    section "Importing models into Ollama (merge + quantize + create)"

    for i in "${!MODEL_NAMES[@]}"; do
        name="${MODEL_NAMES[$i]}"
        run_dir="${MODEL_DIRS[$i]}"
        lora_dir="${run_dir}/lora"
        work_dir="/tmp/bench-v4-import/${name}"

        log "Importing ${name}..."

        # Check if model already exists in Ollama
        if remote "ollama show '${name}' >/dev/null 2>&1"; then
            ok "  ${name} already in Ollama, skipping"
            continue
        fi

        remote bash -s <<IMPORT_EOF
set -euo pipefail
mkdir -p "${work_dir}"

# Read base model from manifest
MANIFEST="${run_dir}/manifest.json"
BASE_MODEL=\$(python3 -c "import json; m=json.load(open('\${MANIFEST}')); print(m.get('base_model', 'mistral:7b'))" 2>/dev/null || echo "mistral:7b")

# Step 1: Merge LoRA with base using llama.cpp (if merged model not cached)
MERGED_PATH="${work_dir}/merged.gguf"
if [[ ! -f "\${MERGED_PATH}" ]]; then
    echo "  Merging LoRA into base model..."
    # If base is an Ollama model, get its path
    OLLAMA_MODEL_PATH=\$(ollama show "\${BASE_MODEL}" --modelfile 2>/dev/null | grep "^FROM " | head -1 | awk '{print \$2}' || true)
    if [[ -z "\${OLLAMA_MODEL_PATH}" || ! -f "\${OLLAMA_MODEL_PATH}" ]]; then
        echo "  Pulling base model \${BASE_MODEL} first..."
        ollama pull "\${BASE_MODEL}"
        OLLAMA_MODEL_PATH=\$(ollama show "\${BASE_MODEL}" --modelfile 2>/dev/null | grep "^FROM " | head -1 | awk '{print \$2}')
    fi

    if command -v llama-export-lora &>/dev/null; then
        llama-export-lora \
            --model "\${OLLAMA_MODEL_PATH}" \
            --lora "${lora_dir}" \
            --output "\${MERGED_PATH}" 2>/dev/null
    elif [[ -f /usr/local/bin/llama-export-lora ]]; then
        /usr/local/bin/llama-export-lora \
            --model "\${OLLAMA_MODEL_PATH}" \
            --lora "${lora_dir}" \
            --output "\${MERGED_PATH}" 2>/dev/null
    else
        echo "  [fallback] llama-export-lora not found, using Modelfile FROM lora"
        cp -r "${lora_dir}"/* "${work_dir}/"
        MERGED_PATH=""
    fi
fi

# Step 2: Quantize if we have a merged model
QUANT_PATH="${work_dir}/model-${QUANTIZATION}.gguf"
if [[ -n "\${MERGED_PATH}" && -f "\${MERGED_PATH}" && ! -f "\${QUANT_PATH}" ]]; then
    echo "  Quantizing to ${QUANTIZATION}..."
    if command -v llama-quantize &>/dev/null; then
        llama-quantize "\${MERGED_PATH}" "\${QUANT_PATH}" ${QUANTIZATION}
    elif [[ -f /usr/local/bin/llama-quantize ]]; then
        /usr/local/bin/llama-quantize "\${MERGED_PATH}" "\${QUANT_PATH}" ${QUANTIZATION}
    else
        echo "  [warn] llama-quantize not found, using merged model as-is"
        QUANT_PATH="\${MERGED_PATH}"
    fi
fi

# Step 3: Create Ollama model
MODELFILE="/tmp/Modelfile.${name}"
if [[ -n "\${QUANT_PATH:-}" && -f "\${QUANT_PATH}" ]]; then
    cat > "\${MODELFILE}" <<MF
FROM \${QUANT_PATH}
PARAMETER temperature 0.3
PARAMETER num_ctx 2048
SYSTEM "You are an expert electronics engineer specializing in PCB design, SPICE simulation, KiCad, and embedded systems."
MF
else
    cat > "\${MODELFILE}" <<MF
FROM ${lora_dir}
PARAMETER temperature 0.3
PARAMETER num_ctx 2048
SYSTEM "You are an expert electronics engineer specializing in PCB design, SPICE simulation, KiCad, and embedded systems."
MF
fi

echo "  Creating Ollama model ${name}..."
ollama create "${name}" -f "\${MODELFILE}"
echo "  Done: ${name}"
IMPORT_EOF

        if [[ $? -eq 0 ]]; then
            ok "  ${name} imported"
        else
            warn "  ${name} import failed, will skip in benchmark"
        fi
    done
else
    log "Skipping import (--skip-import)"
fi

# ────────────────────────────────────────────────────────────
# Step 3: Run benchmark (130 prompts = 100 standard + 30 adversarial)
# ────────────────────────────────────────────────────────────
section "Running benchmark (130 prompts, Codestral judge)"

# Build comma-separated model list for Python
MODEL_LIST=""
for name in "${MODEL_NAMES[@]}"; do
    [[ -n "$MODEL_LIST" ]] && MODEL_LIST="${MODEL_LIST},"
    MODEL_LIST="${MODEL_LIST}${name}"
done

# Transfer and run benchmark script on remote
remote bash -s -- "$MODEL_LIST" "$CODESTRAL_KEY" <<'BENCH_SCRIPT'
set -euo pipefail

MODEL_LIST="$1"
CODESTRAL_KEY="$2"
REMOTE_DIR="/ai/saisail/mascarade"
PROMPTS="${REMOTE_DIR}/finetune/eval/benchmark_prompts.jsonl"
ADVERSARIAL="${REMOTE_DIR}/finetune/eval/adversarial_prompts.jsonl"
TIMESTAMP=$(date +%Y%m%d-%H%M%S)
OUTPUT_DIR="${REMOTE_DIR}/finetune/eval/benchmark-v4-${TIMESTAMP}"
mkdir -p "$OUTPUT_DIR"

python3 - "$MODEL_LIST" "$CODESTRAL_KEY" "$PROMPTS" "$ADVERSARIAL" "$OUTPUT_DIR" <<'PYEOF'
import sys
import json
import os
import time
import urllib.request
import urllib.error

model_list_str, codestral_key, prompts_file, adversarial_file, output_dir = sys.argv[1:6]
models = [m.strip() for m in model_list_str.split(",") if m.strip()]

OLLAMA_URL = "http://localhost:11434"
CODESTRAL_URL = "https://codestral.mistral.ai/v1/chat/completions"

JUDGE_SYSTEM = """You are an expert electronics engineer evaluating technical answers.
Rate the response quality from 1 to 10.
Criteria: accuracy (40%), completeness (25%), clarity (20%), relevance (15%).
Also classify the domain: kicad, spice, embedded, pcb, general.
Respond ONLY with valid JSON: {"score": N, "domain": "...", "reasoning": "brief explanation"}"""

# Load prompts
all_prompts = []
for pfile, ptype in [(prompts_file, "standard"), (adversarial_file, "adversarial")]:
    if not os.path.isfile(pfile):
        print(f"[warn] Prompts file not found: {pfile}, skipping")
        continue
    with open(pfile) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                p = json.loads(line)
                p["type"] = ptype
                all_prompts.append(p)
            except json.JSONDecodeError:
                continue

print(f"Loaded {len(all_prompts)} prompts ({sum(1 for p in all_prompts if p['type']=='standard')} standard, "
      f"{sum(1 for p in all_prompts if p['type']=='adversarial')} adversarial)")

def ollama_generate(model, prompt, timeout=60):
    """Generate a response from Ollama."""
    data = json.dumps({
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.3, "num_predict": 512}
    }).encode()
    req = urllib.request.Request(
        f"{OLLAMA_URL}/api/generate",
        data=data,
        headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            result = json.loads(resp.read())
            return result.get("response", "")
    except Exception as e:
        return f"[ERROR] {e}"

def judge_with_codestral(question, response):
    """Score a response using Codestral API."""
    data = json.dumps({
        "model": "codestral-latest",
        "messages": [
            {"role": "system", "content": JUDGE_SYSTEM},
            {"role": "user", "content": f"Question:\n{question}\n\nResponse to evaluate:\n{response}"}
        ],
        "temperature": 0.1,
        "response_format": {"type": "json_object"}
    }).encode()
    req = urllib.request.Request(
        CODESTRAL_URL,
        data=data,
        headers={
            "Authorization": f"Bearer {codestral_key}",
            "Content-Type": "application/json"
        }
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read())
            content = result["choices"][0]["message"]["content"]
            return json.loads(content)
    except Exception as e:
        return {"score": 0, "domain": "unknown", "reasoning": f"Judge error: {e}"}

# Run benchmark
results = {}  # model -> list of {prompt, response, judge}
for model in models:
    print(f"\n--- Benchmarking: {model} ---")
    results[model] = []
    # Verify model is loaded
    try:
        test = ollama_generate(model, "Hello", timeout=30)
        if test.startswith("[ERROR]"):
            print(f"  [skip] Model {model} not available: {test}")
            continue
    except Exception:
        print(f"  [skip] Model {model} not responding")
        continue

    for idx, prompt_data in enumerate(all_prompts):
        question = prompt_data.get("prompt", prompt_data.get("question", ""))
        if not question:
            continue
        # Generate
        response = ollama_generate(model, question)
        # Judge
        judge = judge_with_codestral(question, response)
        results[model].append({
            "index": idx,
            "type": prompt_data["type"],
            "domain": prompt_data.get("domain", judge.get("domain", "general")),
            "question": question[:200],
            "response": response[:500],
            "score": judge.get("score", 0),
            "judge_domain": judge.get("domain", "unknown"),
            "reasoning": judge.get("reasoning", "")
        })
        score = judge.get("score", 0)
        print(f"  [{idx+1}/{len(all_prompts)}] score={score} domain={judge.get('domain','?')}")
        time.sleep(0.2)  # Rate limit courtesy

# Save raw results
raw_path = os.path.join(output_dir, "results_raw.json")
with open(raw_path, "w") as f:
    json.dump(results, f, indent=2, ensure_ascii=False)
print(f"\nRaw results saved to {raw_path}")

# Generate report
report_path = os.path.join(output_dir, "BENCHMARK_V4_REPORT.md")
domains_all = set()
for model, entries in results.items():
    for e in entries:
        domains_all.add(e.get("judge_domain", e.get("domain", "general")))
domains_sorted = sorted(domains_all)

with open(report_path, "w") as f:
    f.write(f"# Benchmark V4 Report\n\n")
    f.write(f"**Date:** {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
    f.write(f"**Models:** {len(models)}\n")
    f.write(f"**Prompts:** {len(all_prompts)} (standard + adversarial)\n")
    f.write(f"**Judge:** Codestral API\n\n")

    # Overall scores table
    f.write("## Overall Scores\n\n")
    f.write("| Model | Avg Score | Std Prompts | Adv Prompts | Total |\n")
    f.write("|-------|-----------|-------------|-------------|-------|\n")
    for model in models:
        entries = results.get(model, [])
        if not entries:
            f.write(f"| {model} | N/A | N/A | N/A | 0 |\n")
            continue
        scores = [e["score"] for e in entries if e["score"] > 0]
        std_scores = [e["score"] for e in entries if e["type"] == "standard" and e["score"] > 0]
        adv_scores = [e["score"] for e in entries if e["type"] == "adversarial" and e["score"] > 0]
        avg = sum(scores) / len(scores) if scores else 0
        std_avg = sum(std_scores) / len(std_scores) if std_scores else 0
        adv_avg = sum(adv_scores) / len(adv_scores) if adv_scores else 0
        f.write(f"| {model} | {avg:.2f} | {std_avg:.2f} | {adv_avg:.2f} | {len(entries)} |\n")

    # Per-domain breakdown
    f.write("\n## Scores by Domain\n\n")
    header = "| Model |" + "|".join(f" {d} " for d in domains_sorted) + "|\n"
    sep = "|-------|" + "|".join("------" for _ in domains_sorted) + "|\n"
    f.write(header)
    f.write(sep)
    for model in models:
        entries = results.get(model, [])
        row = f"| {model} |"
        for domain in domains_sorted:
            domain_scores = [e["score"] for e in entries
                           if (e.get("judge_domain", e.get("domain")) == domain) and e["score"] > 0]
            if domain_scores:
                row += f" {sum(domain_scores)/len(domain_scores):.2f} |"
            else:
                row += " - |"
        f.write(row + "\n")

    # Best model recommendation
    f.write("\n## Recommendation\n\n")
    best_model = None
    best_avg = 0
    for model in models:
        entries = results.get(model, [])
        scores = [e["score"] for e in entries if e["score"] > 0]
        avg = sum(scores) / len(scores) if scores else 0
        if avg > best_avg:
            best_avg = avg
            best_model = model
    if best_model:
        f.write(f"**Best overall model: `{best_model}`** (avg score: {best_avg:.2f}/10)\n\n")
        # Best per domain
        f.write("**Best per domain:**\n\n")
        for domain in domains_sorted:
            best_d = None
            best_d_avg = 0
            for model in models:
                entries = results.get(model, [])
                ds = [e["score"] for e in entries
                      if (e.get("judge_domain", e.get("domain")) == domain) and e["score"] > 0]
                davg = sum(ds) / len(ds) if ds else 0
                if davg > best_d_avg:
                    best_d_avg = davg
                    best_d = model
            if best_d:
                f.write(f"- **{domain}**: `{best_d}` ({best_d_avg:.2f})\n")

    f.write(f"\n---\n*Generated by benchmark-v4-all.sh*\n")

print(f"\nReport: {report_path}")
# Also print the path so the bash script can capture it
print(f"REPORT_PATH={report_path}")
PYEOF
BENCH_SCRIPT

ok "Benchmark complete"

# ────────────────────────────────────────────────────────────
# Step 4: Fetch report locally
# ────────────────────────────────────────────────────────────
section "Fetching report"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LOCAL_REPORT="${SCRIPT_DIR}/../${REPORT_NAME}"

# Find the latest benchmark-v4 directory
LATEST_REPORT=$(remote "ls -t ${REMOTE_DIR}/finetune/eval/benchmark-v4-*/BENCHMARK_V4_REPORT.md 2>/dev/null | head -1" || true)

if [[ -n "$LATEST_REPORT" ]]; then
    if [[ "$DRY_RUN" == false ]]; then
        scp "${REMOTE_HOST}:${LATEST_REPORT}" "${LOCAL_REPORT}"
        # Also fetch raw results
        LATEST_DIR=$(dirname "$LATEST_REPORT")
        scp "${REMOTE_HOST}:${LATEST_DIR}/results_raw.json" "${SCRIPT_DIR}/../finetune/eval/" 2>/dev/null || true
    fi
    ok "Report saved to ${LOCAL_REPORT}"
else
    warn "No report found on remote"
fi

section "Done"
log "Models benchmarked: ${#MODEL_NAMES[@]}"
log "Report: ${LOCAL_REPORT}"
