#!/usr/bin/env bash
# T-MA-021: Benchmark comparison — base model vs fine-tuned
# Target: KXKM-AI (RTX 4090, 24GB VRAM, Ubuntu, Python 3.12)
# Runs domain-specific prompts, measures quality + latency
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

# ── Couleurs (respect NO_COLOR) ──
if [[ -z "${NO_COLOR:-}" ]] && [[ -t 1 ]]; then
    BOLD='\033[1m' DIM='\033[2m'
    RED='\033[0;31m' GREEN='\033[0;32m' YELLOW='\033[0;33m'
    CYAN='\033[0;36m' MAGENTA='\033[0;35m' NC='\033[0m'
else
    BOLD='' DIM='' RED='' GREEN='' YELLOW='' CYAN='' MAGENTA='' NC=''
fi

log()     { echo -e "  ${CYAN}▸${NC} $*"; }
ok()      { echo -e "  ${GREEN}✓${NC} $*"; }
warn()    { echo -e "  ${YELLOW}!${NC} $*"; }
err()     { echo -e "  ${RED}✗${NC} $*" >&2; }
section() { echo ""; echo -e "  ${MAGENTA}${BOLD}$*${NC}"; echo -e "${DIM}  ──────────────────────────────────────────${NC}"; }
die()     { err "$@"; exit 1; }

# ── Config ──
PROMPTS_FILE="${PROMPTS_FILE:-finetune/eval/benchmark_prompts.jsonl}"
OUTPUT_DIR="${OUTPUT_DIR:-finetune/eval/results-$(date +%Y%m%d-%H%M%S)}"
MAX_TOKENS="${MAX_TOKENS:-1024}"
TEMPERATURE="${TEMPERATURE:-0.1}"
REPEAT="${REPEAT:-1}"
JUDGE_MODEL="${JUDGE_MODEL:-}"  # e.g. gpt-4, or local ollama model
JUDGE_PROVIDER="${JUDGE_PROVIDER:-openai}"  # openai, ollama, none
OLLAMA_URL="${OLLAMA_URL:-http://127.0.0.1:11434}"

# Models to benchmark: "label:path_or_name" pairs
# Override via MODELS env var (comma-separated) or pass as args
if [[ $# -gt 0 ]]; then
    IFS=',' read -ra MODELS <<< "$1"
else
    MODELS_STR="${MODELS:-base-mistral:mistralai/Mistral-Small-3.1-24B-Instruct-2503,kicad-finetuned:finetune/runs/kicad-latest,base-codestral:mistralai/Codestral-2501,codestral-finetuned:finetune/runs/codestral-spice-latest}"
    IFS=',' read -ra MODELS <<< "${MODELS_STR}"
fi

# ── Banner ──
section "T-MA-021: Benchmark — Base vs Fine-tuned Models"
log "prompts_file   = ${PROMPTS_FILE}"
log "output_dir     = ${OUTPUT_DIR}"
log "max_tokens     = ${MAX_TOKENS}"
log "temperature    = ${TEMPERATURE}"
log "judge          = ${JUDGE_PROVIDER}/${JUDGE_MODEL:-auto}"
log "models:"
for m in "${MODELS[@]}"; do
    log "  - ${m}"
done

# ── Validate inputs ──
section "Step 1/4: Validation"

if [[ ! -f "${PROMPTS_FILE}" ]]; then
    die "Prompts file not found: ${PROMPTS_FILE}"
fi

PROMPT_COUNT=$(wc -l < "${PROMPTS_FILE}" | tr -d ' ')
ok "Prompts file: ${PROMPTS_FILE} (${PROMPT_COUNT} prompts)"

python3 -c "import torch; assert torch.cuda.is_available()" 2>/dev/null \
    || warn "CUDA not available -- inference will be slow on CPU"

mkdir -p "${OUTPUT_DIR}"

# ── Run benchmarks ──
section "Step 2/4: Running benchmarks"

python3 -u - <<'BENCH_SCRIPT'
import json, os, sys, time, gc
from pathlib import Path
from datetime import datetime

prompts_file  = os.environ["PROMPTS_FILE"]
output_dir    = os.environ["OUTPUT_DIR"]
max_tokens    = int(os.environ.get("MAX_TOKENS", "1024"))
temperature   = float(os.environ.get("TEMPERATURE", "0.1"))
repeat        = int(os.environ.get("REPEAT", "1"))
models_raw    = os.environ.get("MODELS_STR",
    os.environ.get("MODELS",
        "base-mistral:mistralai/Mistral-Small-3.1-24B-Instruct-2503"))
ollama_url    = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434")

# Parse models
models = []
for entry in models_raw.split(","):
    entry = entry.strip()
    if ":" in entry:
        label, path = entry.split(":", 1)
    else:
        label = entry.split("/")[-1]
        path = entry
    models.append({"label": label, "path": path})

# Load prompts
prompts = []
with open(prompts_file) as f:
    for line in f:
        line = line.strip()
        if line:
            prompts.append(json.loads(line))

print(f"[bench] {len(prompts)} prompts x {len(models)} models = {len(prompts) * len(models)} evaluations")

all_results = []

def run_inference_transformers(model_path, prompt_text, max_tokens, temperature):
    """Run inference using transformers (local model or adapter)."""
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

    adapter_config = Path(model_path) / "adapter" / "adapter_config.json"
    merged_path = Path(model_path) / "merged"

    if merged_path.exists():
        load_path = str(merged_path)
    elif adapter_config.exists():
        # Load base + adapter
        with open(adapter_config) as f:
            cfg = json.load(f)
        base_model = cfg.get("base_model_name_or_path", model_path)
        load_path = base_model  # Will apply adapter after
    else:
        load_path = model_path

    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True, bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.bfloat16,
    )

    tokenizer = AutoTokenizer.from_pretrained(load_path, trust_remote_code=True)
    model = AutoModelForCausalLM.from_pretrained(
        load_path, quantization_config=bnb_config,
        device_map="auto", torch_dtype=torch.bfloat16, trust_remote_code=True,
    )

    # Apply adapter if needed
    if adapter_config.exists() and not merged_path.exists():
        from peft import PeftModel
        model = PeftModel.from_pretrained(model, str(Path(model_path) / "adapter"))

    messages = [{"role": "user", "content": prompt_text}]
    input_ids = tokenizer.apply_chat_template(messages, return_tensors="pt").to(model.device)

    t0 = time.time()
    with torch.no_grad():
        output = model.generate(
            input_ids, max_new_tokens=max_tokens,
            temperature=max(temperature, 0.01),
            do_sample=temperature > 0,
            pad_token_id=tokenizer.eos_token_id,
        )
    elapsed = time.time() - t0

    new_tokens = output[0][input_ids.shape[1]:]
    text = tokenizer.decode(new_tokens, skip_special_tokens=True)
    token_count = len(new_tokens)

    # Cleanup
    del model, tokenizer, output, input_ids
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()

    return {
        "output": text,
        "latency_ms": round(elapsed * 1000, 1),
        "tokens": token_count,
        "tokens_per_second": round(token_count / max(elapsed, 0.001), 1),
    }


def run_inference_ollama(model_name, prompt_text, max_tokens, temperature):
    """Run inference via Ollama API."""
    import urllib.request

    payload = json.dumps({
        "model": model_name,
        "messages": [{"role": "user", "content": prompt_text}],
        "stream": False,
        "options": {"num_predict": max_tokens, "temperature": temperature},
    }).encode()

    req = urllib.request.Request(
        f"{ollama_url}/api/chat",
        data=payload,
        headers={"Content-Type": "application/json"},
    )

    t0 = time.time()
    with urllib.request.urlopen(req, timeout=300) as resp:
        result = json.loads(resp.read())
    elapsed = time.time() - t0

    text = result.get("message", {}).get("content", "")
    eval_count = result.get("eval_count", len(text.split()))

    return {
        "output": text,
        "latency_ms": round(elapsed * 1000, 1),
        "tokens": eval_count,
        "tokens_per_second": round(eval_count / max(elapsed, 0.001), 1),
    }


def check_keywords(output_text, expected_keywords):
    """Simple keyword-based quality check."""
    output_lower = output_text.lower()
    found = [kw for kw in expected_keywords if kw.lower() in output_lower]
    return {
        "keywords_found": len(found),
        "keywords_total": len(expected_keywords),
        "keywords_score": round(len(found) / max(len(expected_keywords), 1), 3),
        "missing_keywords": [kw for kw in expected_keywords if kw.lower() not in output_lower],
    }


# Run all benchmarks
for model_info in models:
    label = model_info["label"]
    path = model_info["path"]

    print(f"\n{'='*60}")
    print(f"[bench] Model: {label} ({path})")
    print(f"{'='*60}")

    model_results = []
    is_local = Path(path).exists() or Path(path).is_dir()

    for i, prompt in enumerate(prompts):
        prompt_id = prompt.get("id", f"prompt-{i+1}")
        prompt_text = prompt["prompt"]
        domain = prompt.get("domain", "unknown")
        expected_kw = prompt.get("expected_keywords", [])

        print(f"  [{i+1}/{len(prompts)}] {prompt_id} ({domain})...", end=" ", flush=True)

        try:
            for r in range(repeat):
                if is_local:
                    result = run_inference_transformers(path, prompt_text, max_tokens, temperature)
                else:
                    result = run_inference_ollama(path, prompt_text, max_tokens, temperature)

                # Quality check
                quality = check_keywords(result["output"], expected_kw)

                entry = {
                    "model": label,
                    "model_path": path,
                    "prompt_id": prompt_id,
                    "domain": domain,
                    "prompt": prompt_text,
                    "repeat": r + 1,
                    **result,
                    **quality,
                }
                model_results.append(entry)

                print(f"{result['latency_ms']}ms, {result['tokens_per_second']}t/s, kw={quality['keywords_score']}", flush=True)

        except Exception as e:
            print(f"ERROR: {e}", flush=True)
            model_results.append({
                "model": label, "model_path": path,
                "prompt_id": prompt_id, "domain": domain,
                "error": str(e),
            })

    all_results.extend(model_results)

    # Save per-model results
    model_file = os.path.join(output_dir, f"{label}.jsonl")
    with open(model_file, "w") as f:
        for r in model_results:
            f.write(json.dumps(r) + "\n")
    print(f"[bench] Saved {len(model_results)} results to {model_file}")

# Save combined results
combined_file = os.path.join(output_dir, "all_results.json")
with open(combined_file, "w") as f:
    json.dump(all_results, f, indent=2)
print(f"\n[bench] All results saved to {combined_file}")
BENCH_SCRIPT

ok "Benchmarks complete"

# ── Step 3: Auto-judge (optional) ──
section "Step 3/4: Quality judging"

if [[ -n "${JUDGE_MODEL}" && "${JUDGE_PROVIDER}" != "none" ]]; then
    log "Running auto-judge via ${JUDGE_PROVIDER}/${JUDGE_MODEL}..."

    python3 -u - <<'JUDGE_SCRIPT'
import json, os, sys, time

output_dir     = os.environ["OUTPUT_DIR"]
judge_model    = os.environ.get("JUDGE_MODEL", "")
judge_provider = os.environ.get("JUDGE_PROVIDER", "openai")
ollama_url     = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434")

results_file = os.path.join(output_dir, "all_results.json")
with open(results_file) as f:
    results = json.load(f)

judged = []
for r in results:
    if "error" in r or not r.get("output"):
        r["judge_score"] = 0
        r["judge_reason"] = "no output"
        judged.append(r)
        continue

    judge_prompt = f"""Rate the following AI response on a scale of 1-10 for technical accuracy and completeness.

Domain: {r.get('domain', 'unknown')}
User prompt: {r['prompt']}
AI response: {r['output'][:2000]}

Respond ONLY with a JSON object: {{"score": <1-10>, "reason": "<brief reason>"}}"""

    try:
        if judge_provider == "openai":
            import urllib.request
            api_key = os.environ.get("OPENAI_API_KEY", "")
            if not api_key:
                print("[judge] OPENAI_API_KEY not set, skipping judge")
                break
            payload = json.dumps({
                "model": judge_model,
                "messages": [{"role": "user", "content": judge_prompt}],
                "temperature": 0,
                "max_tokens": 200,
            }).encode()
            req = urllib.request.Request(
                "https://api.openai.com/v1/chat/completions",
                data=payload,
                headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
            )
            with urllib.request.urlopen(req, timeout=60) as resp:
                judge_resp = json.loads(resp.read())
            judge_text = judge_resp["choices"][0]["message"]["content"]

        elif judge_provider == "ollama":
            import urllib.request
            payload = json.dumps({
                "model": judge_model,
                "messages": [{"role": "user", "content": judge_prompt}],
                "stream": False,
                "options": {"temperature": 0, "num_predict": 200},
            }).encode()
            req = urllib.request.Request(
                f"{ollama_url}/api/chat",
                data=payload,
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=120) as resp:
                judge_resp = json.loads(resp.read())
            judge_text = judge_resp.get("message", {}).get("content", "")

        # Parse judge response
        try:
            judge_data = json.loads(judge_text.strip())
            r["judge_score"] = judge_data.get("score", 0)
            r["judge_reason"] = judge_data.get("reason", "")
        except json.JSONDecodeError:
            r["judge_score"] = 0
            r["judge_reason"] = f"parse error: {judge_text[:200]}"

    except Exception as e:
        r["judge_score"] = 0
        r["judge_reason"] = f"judge error: {e}"

    judged.append(r)
    print(f"  [{r['prompt_id']}] {r['model']}: judge={r.get('judge_score', '?')}/10")

# Save judged results
judged_file = os.path.join(output_dir, "all_results_judged.json")
with open(judged_file, "w") as f:
    json.dump(judged, f, indent=2)
print(f"[judge] Saved judged results to {judged_file}")
JUDGE_SCRIPT

    ok "Judging complete"
else
    log "No JUDGE_MODEL set -- skipping auto-judge"
    log "Set JUDGE_MODEL=gpt-4o JUDGE_PROVIDER=openai to enable"
fi

# ── Step 4: Generate comparison report ──
section "Step 4/4: Generate comparison report"

python3 -u - <<'REPORT_SCRIPT'
import json, os
from collections import defaultdict

output_dir = os.environ["OUTPUT_DIR"]

# Load results (prefer judged if available)
judged_file = os.path.join(output_dir, "all_results_judged.json")
results_file = os.path.join(output_dir, "all_results.json")

if os.path.exists(judged_file):
    with open(judged_file) as f:
        results = json.load(f)
    has_judge = any(r.get("judge_score") for r in results)
else:
    with open(results_file) as f:
        results = json.load(f)
    has_judge = False

# Aggregate by model
stats = defaultdict(lambda: {
    "count": 0, "errors": 0,
    "latency_ms": [], "tokens_per_second": [],
    "keywords_score": [], "judge_score": [],
    "by_domain": defaultdict(lambda: {"count": 0, "keywords_score": [], "judge_score": []}),
})

for r in results:
    model = r["model"]
    domain = r.get("domain", "unknown")
    s = stats[model]
    s["count"] += 1

    if "error" in r:
        s["errors"] += 1
        continue

    if "latency_ms" in r:
        s["latency_ms"].append(r["latency_ms"])
    if "tokens_per_second" in r:
        s["tokens_per_second"].append(r["tokens_per_second"])
    if "keywords_score" in r:
        s["keywords_score"].append(r["keywords_score"])
    if "judge_score" in r and r["judge_score"]:
        s["judge_score"].append(r["judge_score"])

    d = s["by_domain"][domain]
    d["count"] += 1
    if "keywords_score" in r:
        d["keywords_score"].append(r["keywords_score"])
    if "judge_score" in r and r["judge_score"]:
        d["judge_score"].append(r["judge_score"])

def avg(lst):
    return round(sum(lst) / len(lst), 2) if lst else 0

def p50(lst):
    if not lst: return 0
    s = sorted(lst)
    return s[len(s)//2]

# Build report
lines = []
lines.append("# T-MA-021: Benchmark Report")
lines.append(f"")
lines.append(f"Generated: {os.popen('date -Iseconds').read().strip()}")
lines.append(f"Prompts: {len(results)} evaluations across {len(stats)} models")
lines.append("")

# Summary table
lines.append("## Summary")
lines.append("")
header = "| Model | Prompts | Errors | Avg Latency (ms) | P50 Latency | Avg tok/s | Keyword Score |"
if has_judge:
    header += " Judge Score |"
lines.append(header)
sep = "|---|---|---|---|---|---|---|"
if has_judge:
    sep += "---|"
lines.append(sep)

for model in sorted(stats.keys()):
    s = stats[model]
    row = f"| {model} | {s['count']} | {s['errors']} | {avg(s['latency_ms'])} | {p50(s['latency_ms'])} | {avg(s['tokens_per_second'])} | {avg(s['keywords_score'])} |"
    if has_judge:
        row += f" {avg(s['judge_score'])}/10 |"
    lines.append(row)

lines.append("")

# Per-domain breakdown
lines.append("## Per-domain Breakdown")
lines.append("")

domains = set()
for s in stats.values():
    domains.update(s["by_domain"].keys())

for domain in sorted(domains):
    lines.append(f"### {domain}")
    lines.append("")
    dh = "| Model | Count | Keyword Score |"
    if has_judge:
        dh += " Judge Score |"
    lines.append(dh)
    ds = "|---|---|---|"
    if has_judge:
        ds += "---|"
    lines.append(ds)

    for model in sorted(stats.keys()):
        d = stats[model]["by_domain"].get(domain, {"count": 0, "keywords_score": [], "judge_score": []})
        dr = f"| {model} | {d['count']} | {avg(d['keywords_score'])} |"
        if has_judge:
            dr += f" {avg(d['judge_score'])}/10 |"
        lines.append(dr)
    lines.append("")

# Save report
report_text = "\n".join(lines)
report_path = os.path.join(output_dir, "benchmark_report.md")
with open(report_path, "w") as f:
    f.write(report_text)

print(report_text)
print(f"\n[report] Saved to {report_path}")

# Also save summary as JSON
summary = {}
for model in stats:
    s = stats[model]
    summary[model] = {
        "count": s["count"], "errors": s["errors"],
        "avg_latency_ms": avg(s["latency_ms"]),
        "p50_latency_ms": p50(s["latency_ms"]),
        "avg_tokens_per_second": avg(s["tokens_per_second"]),
        "avg_keywords_score": avg(s["keywords_score"]),
        "avg_judge_score": avg(s["judge_score"]) if has_judge else None,
    }

summary_path = os.path.join(output_dir, "benchmark_summary.json")
with open(summary_path, "w") as f:
    json.dump(summary, f, indent=2)
print(f"[report] Summary JSON: {summary_path}")
REPORT_SCRIPT

ok "Report generated"

echo ""
ok "T-MA-021 complete: ${OUTPUT_DIR}"
log "Results:  ${OUTPUT_DIR}/all_results.json"
log "Report:   ${OUTPUT_DIR}/benchmark_report.md"
log "Summary:  ${OUTPUT_DIR}/benchmark_summary.json"
