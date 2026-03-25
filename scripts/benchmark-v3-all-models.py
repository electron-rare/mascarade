"""Benchmark v3: test ALL mini-models + import to Ollama + configure router."""

import json
import time
import os
import subprocess
import httpx

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
CODESTRAL_URL = "https://codestral.mistral.ai/v1/chat/completions"
CODESTRAL_KEY = os.environ.get("CODESTRAL_API_KEY", "JbYYQUUpHOOFjpV5UuSct6QM4cT6otEl")
PROMPTS = "finetune/eval/benchmark_prompts.jsonl"
ADVERSARIAL = "finetune/eval/adversarial_prompts.jsonl"
RUNS = "finetune/runs"
OUTPUT = f"finetune/eval/benchmark-v3-{time.strftime('%Y%m%d-%H%M%S')}"
os.makedirs(OUTPUT, exist_ok=True)

JUDGE_SYSTEM = "You are an expert electronics engineer evaluating technical answers. Rate 1-10. Criteria: accuracy (40%), completeness (25%), clarity (20%), relevance (15%)."


def find_all_runs():
    """Find all completed training runs."""
    runs = {}
    if not os.path.isdir(RUNS):
        return runs
    for d in sorted(os.listdir(RUNS)):
        manifest = os.path.join(RUNS, d, "manifest.json")
        if os.path.isfile(manifest):
            with open(manifest) as f:
                m = json.load(f)
            name = m.get("name", d)
            if name not in runs:  # Keep latest
                runs[name] = {"dir": os.path.join(RUNS, d), "manifest": m}
    return runs


def import_to_ollama(name, run_dir):
    """Import a LoRA run into Ollama via Modelfile."""
    lora_dir = os.path.join(run_dir, "lora")
    if not os.path.isdir(lora_dir):
        print(f"  No lora/ dir in {run_dir}")
        return False

    modelfile = f"""FROM {lora_dir}
PARAMETER temperature 0.3
PARAMETER num_ctx 1024
SYSTEM "You are an expert electronics engineer."
"""
    mf_path = f"/tmp/Modelfile.{name}"
    with open(mf_path, "w") as f:
        f.write(modelfile)

    try:
        result = subprocess.run(
            ["ollama", "create", name, "-f", mf_path],
            capture_output=True,
            text=True,
            timeout=300,
        )
        if result.returncode == 0:
            print(f"  Ollama import OK: {name}")
            return True
        else:
            print(f"  Ollama import FAILED: {result.stderr[:200]}")
            return False
    except Exception as e:
        print(f"  Ollama import error: {e}")
        return False


def query_ollama(model, prompt, timeout=60.0):
    try:
        with httpx.Client(timeout=timeout) as c:
            r = c.post(
                f"{OLLAMA_URL}/api/generate",
                json={
                    "model": model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {"temperature": 0.2, "num_predict": 512},
                },
            )
            r.raise_for_status()
            d = r.json()
            return (
                d.get("response", ""),
                d.get("eval_count", 0),
                r.elapsed.total_seconds(),
            )
    except Exception:
        return "", 0, 0


def judge(question, response):
    try:
        with httpx.Client(timeout=30) as c:
            r = c.post(
                CODESTRAL_URL,
                headers={
                    "Authorization": f"Bearer {CODESTRAL_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "codestral-latest",
                    "messages": [
                        {"role": "system", "content": JUDGE_SYSTEM},
                        {
                            "role": "user",
                            "content": f"Question:\n{question}\n\nAnswer:\n{response}\n\nScore (1-10):",
                        },
                    ],
                    "response_format": {"type": "json_object"},
                    "temperature": 0.1,
                    "max_tokens": 100,
                },
            )
            r.raise_for_status()
            import re

            text = r.json()["choices"][0]["message"]["content"]
            nums = re.findall(r"\b(\d+)\b", text)
            for n in nums:
                v = int(n)
                if 1 <= v <= 10:
                    return v
    except Exception:
        pass
    return 0


def benchmark_model(model_name, prompts):
    """Benchmark a model on all prompts."""
    scores, latencies = [], []
    domain_scores = {}

    for i, p in enumerate(prompts):
        resp, tokens, latency = query_ollama(model_name, p["prompt"])
        score = judge(p["prompt"], resp) if resp else 0

        scores.append(score)
        latencies.append(latency)
        domain = p.get("domain", "unknown")
        domain_scores.setdefault(domain, []).append(score)

        if (i + 1) % 20 == 0:
            avg = sum(scores) / len(scores)
            print(f"    [{i+1}/{len(prompts)}] avg={avg:.2f}/10")

    avg_score = sum(scores) / len(scores) if scores else 0
    avg_lat = sum(latencies) / len(latencies) * 1000 if latencies else 0
    domains = {d: round(sum(s) / len(s), 2) for d, s in domain_scores.items()}

    return {
        "avg_score": round(avg_score, 2),
        "avg_latency_ms": round(avg_lat),
        "domains": domains,
        "n_prompts": len(prompts),
    }


def main():
    print("=" * 60)
    print("BENCHMARK v3 — ALL MINI-MODELS")
    print("=" * 60)

    # Find all runs
    runs = find_all_runs()
    print(f"\nFound {len(runs)} trained models:")
    for name, info in runs.items():
        m = info["manifest"]
        print(f"  {name}: {m.get('examples', '?')} ex, {m.get('domain', '?')}")

    # Import all to Ollama
    print("\n=== IMPORT TO OLLAMA ===")
    imported = []
    for name, info in runs.items():
        # Check if already in Ollama
        try:
            r = httpx.get(f"{OLLAMA_URL}/api/tags", timeout=5)
            existing = [m["name"] for m in r.json().get("models", [])]
            if name in existing or f"{name}:latest" in existing:
                print(f"  {name}: already in Ollama")
                imported.append(name)
                continue
        except Exception:
            pass

        if import_to_ollama(name, info["dir"]):
            imported.append(name)

    print(f"\nImported: {len(imported)}/{len(runs)}")

    # Load prompts
    prompts = []
    for pf in [PROMPTS, ADVERSARIAL]:
        if os.path.exists(pf):
            with open(pf) as f:
                for line in f:
                    if line.strip():
                        try:
                            prompts.append(json.loads(line.strip()))
                        except json.JSONDecodeError:
                            pass
    print(f"\nPrompts: {len(prompts)} (standard + adversarial)")

    # Also benchmark base models for comparison
    all_models = {}
    for name in imported:
        all_models[name] = name
    # Add base references
    all_models["qwen2.5-7b-base"] = "qwen2.5:7b"
    all_models["phi2-ee-hf"] = "phi2ee"

    # Benchmark each
    results = {}
    for label, model in all_models.items():
        print(f"\n=== {label} ({model}) ===")
        try:
            result = benchmark_model(model, prompts)
            results[label] = result
            print(
                f"  Score: {result['avg_score']}/10, Latency: {result['avg_latency_ms']}ms"
            )
            print(f"  Domains: {result['domains']}")
        except Exception as e:
            print(f"  FAILED: {e}")

    # Generate report
    report = f"# Benchmark v3 — {len(results)} models\n\n"
    report += f"Date: {time.strftime('%Y-%m-%d %H:%M')}\n"
    report += f"Prompts: {len(prompts)}\nJudge: Codestral API\n\n"
    report += "## Results\n\n"
    report += "| Model | Score /10 | Latency | Domain Best |\n"
    report += "|-------|-----------|---------|-------------|\n"

    for label, r in sorted(results.items(), key=lambda x: -x[1]["avg_score"]):
        best_domain = (
            max(r["domains"].items(), key=lambda x: x[1]) if r["domains"] else ("?", 0)
        )
        report += f"| {label} | **{r['avg_score']}** | {r['avg_latency_ms']}ms | {best_domain[0]}={best_domain[1]} |\n"

    with open(f"{OUTPUT}/BENCHMARK_V3_REPORT.md", "w") as f:
        f.write(report)
    with open(f"{OUTPUT}/benchmark_v3_results.json", "w") as f:
        json.dump(results, f, indent=2)

    print(f"\n{report}")
    print(f"Results: {OUTPUT}/")


if __name__ == "__main__":
    main()
