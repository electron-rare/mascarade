"""Benchmark comparison: mascarade finetunes vs HuggingFace phi-2-EE (STEM-AI-mtl)."""

import json
import time
import os
import httpx

CODESTRAL_URL = "https://codestral.mistral.ai/v1/chat/completions"
CODESTRAL_KEY = os.environ.get("CODESTRAL_API_KEY", "JbYYQUUpHOOFjpV5UuSct6QM4cT6otEl")
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
PROMPTS_FILE = "finetune/eval/benchmark_prompts.jsonl"

OUTPUT_DIR = f"finetune/eval/comparison-{time.strftime('%Y%m%d-%H%M%S')}"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Models to compare
MODELS = {
    # HuggingFace reference (most popular EE model)
    "phi2-ee-stem-ai (HF #1)": "phi2ee",
    # Our finetunes
    "mascarade-kicad-v1 (ours)": "mascarade-kicad:latest",
    "mascarade-spice-v1 (ours)": "mascarade-spice:latest",
    "kicadv2-24B (ours)": "kicadv2",
    # Base models for reference
    "qwen2.5-7b (base)": "qwen2.5:7b",
}

JUDGE_SYSTEM = """Tu es un evaluateur expert en electronique, PCB, SPICE, systemes embarques et KiCad.
Evalue la qualite de la reponse sur une echelle de 1 a 10.
Criteres : exactitude (40%), completude (25%), clarte (20%), pertinence (15%).
Reponds UNIQUEMENT en JSON."""


def query_ollama(model, prompt, timeout=120.0):
    try:
        with httpx.Client(timeout=timeout) as c:
            r = c.post(f"{OLLAMA_URL}/api/generate", json={
                "model": model, "prompt": prompt, "stream": False,
                "options": {"temperature": 0.2, "num_predict": 512},
            })
            r.raise_for_status()
            d = r.json()
            return d.get("response", ""), d.get("eval_count", 0), r.elapsed.total_seconds()
    except Exception as e:
        return "", 0, 0


def judge(question, response):
    try:
        with httpx.Client(timeout=30) as c:
            r = c.post(CODESTRAL_URL, headers={
                "Authorization": f"Bearer {CODESTRAL_KEY}",
                "Content-Type": "application/json",
            }, json={
                "model": "codestral-latest",
                "messages": [
                    {"role": "system", "content": JUDGE_SYSTEM},
                    {"role": "user", "content": f"Question:\n{question}\n\nReponse:\n{response}\n\nJSON: {{\"score\": N, \"justification\": \"...\"}}"},
                ],
                "response_format": {"type": "json_object"},
                "temperature": 0.1, "max_tokens": 200,
            })
            r.raise_for_status()
            return json.loads(r.json()["choices"][0]["message"]["content"]).get("score", 0)
    except Exception:
        return 0


def main():
    print("=== Mascarade vs HuggingFace Benchmark ===\n")

    prompts = []
    with open(PROMPTS_FILE) as f:
        for line in f:
            if line.strip():
                try:
                    prompts.append(json.loads(line.strip()))
                except json.JSONDecodeError:
                    pass
    print(f"Prompts: {len(prompts)}")

    # Check available
    available = set()
    try:
        r = httpx.get(f"{OLLAMA_URL}/api/tags", timeout=10)
        for m in r.json().get("models", []):
            available.add(m["name"])
    except Exception:
        pass

    active = {}
    for label, model in MODELS.items():
        if any(model.split(":")[0] in a for a in available):
            active[label] = model
        else:
            print(f"  SKIP {label} ({model})")
    print(f"Models: {len(active)}\n")

    results = {}
    for label, model in active.items():
        print(f"=== {label} ({model}) ===")
        scores, latencies, domain_scores = [], [], {}

        for i, p in enumerate(prompts):
            resp, tokens, latency = query_ollama(model, p["prompt"])
            score = judge(p["prompt"], resp) if resp else 0
            domain = p.get("domain", "?")

            scores.append(score)
            latencies.append(latency)
            domain_scores.setdefault(domain, []).append(score)

            if (i + 1) % 20 == 0:
                print(f"  [{i+1}/{len(prompts)}] avg={sum(scores)/len(scores):.2f}/10 lat={sum(latencies)/len(latencies)*1000:.0f}ms")

        avg = sum(scores) / len(scores) if scores else 0
        avg_lat = sum(latencies) / len(latencies) * 1000 if latencies else 0
        dom = {d: round(sum(s)/len(s), 2) for d, s in domain_scores.items()}

        results[label] = {"score": round(avg, 2), "latency_ms": round(avg_lat), "domains": dom}
        print(f"  DONE: {avg:.2f}/10 | {avg_lat:.0f}ms | {dom}\n")

    # Report
    report = "# Mascarade vs HuggingFace — Benchmark Comparison\n\n"
    report += f"Date: {time.strftime('%Y-%m-%d %H:%M')}\n"
    report += f"Judge: Codestral API (JSON mode)\n"
    report += f"Prompts: {len(prompts)}\n\n"
    report += "## Results\n\n"
    report += "| Model | Score /10 | Latency | KiCad | SPICE | Embedded | Mixed |\n"
    report += "|-------|-----------|---------|-------|-------|----------|-------|\n"

    for label, d in sorted(results.items(), key=lambda x: -x[1]["score"]):
        dm = d["domains"]
        report += f"| {label} | **{d['score']}** | {d['latency_ms']}ms | {dm.get('kicad','-')} | {dm.get('spice','-')} | {dm.get('embedded','-')} | {dm.get('mixed','-')} |\n"

    report += f"\n## Key Finding\n\n"
    our_best = max((v["score"], k) for k, v in results.items() if "ours" in k)
    hf_best = max((v["score"], k) for k, v in results.items() if "HF" in k or "stem" in k.lower() or "phi2" in k.lower())
    if our_best[0] > hf_best[0]:
        report += f"**mascarade wins**: {our_best[1]} ({our_best[0]}/10) vs {hf_best[1]} ({hf_best[0]}/10)\n"
    else:
        report += f"**HuggingFace wins**: {hf_best[1]} ({hf_best[0]}/10) vs {our_best[1]} ({our_best[0]}/10)\n"

    with open(f"{OUTPUT_DIR}/COMPARISON_REPORT.md", "w") as f:
        f.write(report)
    with open(f"{OUTPUT_DIR}/comparison_results.json", "w") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print(report)
    print(f"Results: {OUTPUT_DIR}/")


if __name__ == "__main__":
    main()
