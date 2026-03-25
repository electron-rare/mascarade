"""T-MA-021b: Benchmark with LLM judge (Qwen3-8B) instead of keyword matching."""

import json
import time
import os
import httpx

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
JUDGE_MODEL = "qwen3:8b"
PROMPTS_FILE = "finetune/eval/benchmark_prompts.jsonl"
PREV_RESULTS = None  # Will find latest results dir

# Find previous benchmark results
for d in sorted(os.listdir("finetune/eval"), reverse=True):
    if d.startswith("results-") and os.path.isfile(
        f"finetune/eval/{d}/benchmark_results.json"
    ):
        PREV_RESULTS = f"finetune/eval/{d}/benchmark_results.json"
        break

OUTPUT_DIR = f"finetune/eval/judge-results-{time.strftime('%Y%m%d-%H%M%S')}"
os.makedirs(OUTPUT_DIR, exist_ok=True)

JUDGE_PROMPT = """/no_think
You are an expert electronics engineer evaluating technical answers.
Rate the following answer on a scale of 1-10.

Criteria: accuracy (40%), completeness (25%), clarity (20%), relevance (15%).

Question: {question}

Answer to evaluate: {response}

Reply with ONLY a number between 1 and 10. Nothing else."""


def query_ollama(model: str, prompt: str, timeout: float = 120.0) -> dict:
    start = time.time()
    try:
        with httpx.Client(timeout=timeout) as client:
            resp = client.post(
                f"{OLLAMA_URL}/api/generate",
                json={
                    "model": model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {"temperature": 0.1, "num_predict": 256},
                },
            )
            resp.raise_for_status()
            data = resp.json()
        return {
            "success": True,
            "response": data.get("response", ""),
            "latency_ms": round((time.time() - start) * 1000),
        }
    except Exception as e:
        return {"success": False, "response": "", "latency_ms": 0, "error": str(e)}


def judge_response(question: str, response: str) -> dict:
    """Use LLM judge to score a response."""
    prompt = JUDGE_PROMPT.format(question=question, response=response)
    result = query_ollama(JUDGE_MODEL, prompt, timeout=60.0)
    if not result["success"]:
        return {"score": 0, "justification": f"Judge error: {result.get('error', '')}"}

    text = result["response"].strip()
    # Extract a number 1-10 from the response
    import re

    # Try to find a standalone number
    numbers = re.findall(r"\b(\d+)\b", text)
    for n in numbers:
        val = int(n)
        if 1 <= val <= 10:
            return {"score": val, "justification": text[:200]}
    # Try JSON fallback
    match = re.search(r'"score"\s*:\s*(\d+)', text)
    if match:
        return {"score": int(match.group(1)), "justification": text[:200]}
    return {"score": 0, "justification": f"Could not parse: {text[:200]}"}


def main():
    print("=== T-MA-021b: LLM Judge Benchmark ===")
    print(f"Judge model: {JUDGE_MODEL}")

    # Load previous results
    if not PREV_RESULTS:
        print("ERROR: No previous benchmark results found. Run run-benchmark.py first.")
        return

    print(f"Previous results: {PREV_RESULTS}")
    with open(PREV_RESULTS) as f:
        prev = json.load(f)

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
    print(f"Prompts: {len(prompts)}")

    # Judge each model's responses
    judge_results = {}

    for model_label, model_data in prev.items():
        print(f"\n=== Judging: {model_label} ===")
        details = model_data.get("details", [])
        scores = []
        domain_scores = {}

        for i, (prompt_data, detail) in enumerate(zip(prompts, details)):
            question = prompt_data["prompt"]
            domain = prompt_data.get("domain", "unknown")

            # Get the model's response from previous benchmark
            # We need to re-query since previous results don't store full responses
            # Actually, let's query the model fresh for judging
            model_name = model_data["summary"]["ollama_model"]
            resp = query_ollama(model_name, question, timeout=120.0)

            if resp["success"] and resp["response"]:
                judgment = judge_response(question, resp["response"])
            else:
                judgment = {"score": 0, "justification": "Model failed to respond"}

            scores.append(judgment["score"])

            if domain not in domain_scores:
                domain_scores[domain] = []
            domain_scores[domain].append(judgment["score"])

            if (i + 1) % 10 == 0:
                avg = sum(scores) / len(scores)
                print(f"  [{i+1}/{len(prompts)}] avg_judge_score={avg:.2f}/10")

        avg_score = sum(scores) / len(scores) if scores else 0
        domain_avg = {d: round(sum(s) / len(s), 2) for d, s in domain_scores.items()}

        judge_results[model_label] = {
            "avg_score": round(avg_score, 2),
            "domain_scores": domain_avg,
            "total_judged": len(scores),
        }
        print(f"  DONE: avg_judge_score={avg_score:.2f}/10")
        print(f"  Domains: {domain_avg}")

    # Save results
    with open(f"{OUTPUT_DIR}/judge_results.json", "w") as f:
        json.dump(judge_results, f, indent=2, ensure_ascii=False)

    # Generate report
    report = "# T-MA-021b: LLM Judge Benchmark\n\n"
    report += f"Date: {time.strftime('%Y-%m-%d %H:%M')}\n"
    report += f"Judge: {JUDGE_MODEL}\n"
    report += f"Prompts: {len(prompts)}\n\n"
    report += "## Summary (Score /10)\n\n"
    report += "| Model | Judge Score | KiCad | SPICE | Embedded | Mixed |\n"
    report += "|-------|-----------|-------|-------|----------|-------|\n"

    for label, data in sorted(judge_results.items(), key=lambda x: -x[1]["avg_score"]):
        ds = data["domain_scores"]
        report += f"| {label} | **{data['avg_score']:.2f}** | {ds.get('kicad', 'N/A')} | {ds.get('spice', 'N/A')} | {ds.get('embedded', 'N/A')} | {ds.get('mixed', 'N/A')} |\n"

    with open(f"{OUTPUT_DIR}/JUDGE_REPORT.md", "w") as f:
        f.write(report)

    print(f"\n{report}")
    print(f"Results saved to: {OUTPUT_DIR}/")


if __name__ == "__main__":
    main()
