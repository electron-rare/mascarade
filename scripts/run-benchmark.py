"""T-MA-021: Benchmark base vs fine-tuned models on 100 domain prompts."""

import json
import time
import os
import httpx

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
PROMPTS_FILE = "finetune/eval/benchmark_prompts.jsonl"
OUTPUT_DIR = f"finetune/eval/results-{time.strftime('%Y%m%d-%H%M%S')}"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Models to benchmark
MODELS = {
    "base-qwen2.5-7b": "qwen2.5:7b",
    "base-mistral-7b": "mistral:7b",
    "finetuned-kicad-v2": "kicadv2",
    "finetuned-mascarade-kicad-v1": "mascarade-kicad:latest",
    "finetuned-mascarade-spice-v1": "mascarade-spice:latest",
}

def query_ollama(model: str, prompt: str, timeout: float = 120.0) -> dict:
    """Query Ollama and return response + metrics."""
    start = time.time()
    try:
        with httpx.Client(timeout=timeout) as client:
            resp = client.post(f"{OLLAMA_URL}/api/generate", json={
                "model": model,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0.2, "num_predict": 512},
            })
            resp.raise_for_status()
            data = resp.json()
        latency = time.time() - start
        response_text = data.get("response", "")
        eval_count = data.get("eval_count", 0)
        tokens_per_sec = eval_count / latency if latency > 0 else 0
        return {
            "success": True,
            "response": response_text,
            "latency_ms": round(latency * 1000),
            "tokens": eval_count,
            "tokens_per_sec": round(tokens_per_sec, 1),
        }
    except Exception as e:
        return {
            "success": False,
            "response": "",
            "latency_ms": round((time.time() - start) * 1000),
            "tokens": 0,
            "tokens_per_sec": 0,
            "error": str(e),
        }

def score_response(response: str, expected_keywords: list[str]) -> float:
    """Simple keyword-match scoring (0-1)."""
    if not response or not expected_keywords:
        return 0.0
    response_lower = response.lower()
    matches = sum(1 for kw in expected_keywords if kw.lower() in response_lower)
    return round(matches / len(expected_keywords), 3)

def main():
    # Load prompts
    prompts = []
    with open(PROMPTS_FILE) as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    prompts.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    print(f"Loaded {len(prompts)} prompts")

    # Check available models
    available = set()
    try:
        resp = httpx.get(f"{OLLAMA_URL}/api/tags", timeout=10)
        for m in resp.json().get("models", []):
            available.add(m["name"])
    except Exception:
        pass
    print(f"Available models: {available}")

    # Filter to available models
    active_models = {}
    for label, model_name in MODELS.items():
        if model_name in available or any(model_name.split(":")[0] in a for a in available):
            active_models[label] = model_name
        else:
            print(f"  SKIP {label} ({model_name}) — not available")
    print(f"Benchmarking {len(active_models)} models on {len(prompts)} prompts\n")

    # Run benchmark
    results = {}
    for label, model_name in active_models.items():
        print(f"\n=== {label} ({model_name}) ===")
        model_results = []
        total_score = 0
        total_latency = 0
        total_tokens = 0

        for i, prompt_data in enumerate(prompts):
            prompt_text = prompt_data["prompt"]
            domain = prompt_data.get("domain", "unknown")
            expected = prompt_data.get("expected_keywords", [])

            result = query_ollama(model_name, prompt_text)
            score = score_response(result["response"], expected)

            model_results.append({
                "prompt_id": prompt_data.get("id", i),
                "domain": domain,
                "score": score,
                "latency_ms": result["latency_ms"],
                "tokens": result["tokens"],
                "tokens_per_sec": result["tokens_per_sec"],
                "success": result["success"],
            })

            total_score += score
            total_latency += result["latency_ms"]
            total_tokens += result["tokens"]

            if (i + 1) % 10 == 0:
                avg_score = total_score / (i + 1)
                print(f"  [{i+1}/{len(prompts)}] avg_score={avg_score:.3f} avg_latency={total_latency/(i+1):.0f}ms")

        n = len(prompts)
        summary = {
            "model": label,
            "ollama_model": model_name,
            "prompts": n,
            "avg_score": round(total_score / n, 4) if n else 0,
            "avg_latency_ms": round(total_latency / n) if n else 0,
            "total_tokens": total_tokens,
            "avg_tokens_per_sec": round(total_tokens / (total_latency / 1000)) if total_latency else 0,
        }

        # Domain breakdown
        domains = {}
        for r in model_results:
            d = r["domain"]
            if d not in domains:
                domains[d] = {"count": 0, "total_score": 0, "total_latency": 0}
            domains[d]["count"] += 1
            domains[d]["total_score"] += r["score"]
            domains[d]["total_latency"] += r["latency_ms"]
        summary["domains"] = {
            d: {"avg_score": round(v["total_score"] / v["count"], 4), "avg_latency_ms": round(v["total_latency"] / v["count"])}
            for d, v in domains.items()
        }

        results[label] = {"summary": summary, "details": model_results}
        print(f"  DONE: score={summary['avg_score']:.4f} latency={summary['avg_latency_ms']}ms tps={summary['avg_tokens_per_sec']}")

    # Save results
    with open(f"{OUTPUT_DIR}/benchmark_results.json", "w") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    # Generate markdown report
    report = "# T-MA-021: Benchmark Results\n\n"
    report += f"Date: {time.strftime('%Y-%m-%d %H:%M')}\n"
    report += f"Prompts: {len(prompts)}\n\n"
    report += "## Summary\n\n"
    report += "| Model | Avg Score | Avg Latency | Tokens/s |\n"
    report += "|-------|-----------|-------------|----------|\n"
    for label, data in results.items():
        s = data["summary"]
        report += f"| {label} | {s['avg_score']:.4f} | {s['avg_latency_ms']}ms | {s['avg_tokens_per_sec']} |\n"

    report += "\n## Domain Breakdown\n\n"
    for label, data in results.items():
        report += f"\n### {label}\n\n"
        report += "| Domain | Score | Latency |\n"
        report += "|--------|-------|---------|\n"
        for domain, stats in data["summary"].get("domains", {}).items():
            report += f"| {domain} | {stats['avg_score']:.4f} | {stats['avg_latency_ms']}ms |\n"

    with open(f"{OUTPUT_DIR}/BENCHMARK_REPORT.md", "w") as f:
        f.write(report)

    print("\n=== REPORT ===")
    print(report)
    print(f"\nResults saved to: {OUTPUT_DIR}/")

if __name__ == "__main__":
    main()
