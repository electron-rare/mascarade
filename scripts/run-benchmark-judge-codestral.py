"""T-MA-021c: Benchmark with Codestral API as LLM judge."""

import json
import time
import os
import httpx

CODESTRAL_URL = "https://codestral.mistral.ai/v1/chat/completions"
CODESTRAL_KEY = os.environ.get("CODESTRAL_API_KEY", "JbYYQUUpHOOFjpV5UuSct6QM4cT6otEl")
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
PROMPTS_FILE = "finetune/eval/benchmark_prompts.jsonl"

OUTPUT_DIR = f"finetune/eval/judge-codestral-{time.strftime('%Y%m%d-%H%M%S')}"
os.makedirs(OUTPUT_DIR, exist_ok=True)

MODELS = {
    "base-qwen2.5-7b": "qwen2.5:7b",
    "base-mistral-7b": "mistral:7b",
    "finetuned-kicad-v2": "kicadv2",
    "finetuned-mascarade-kicad-v1": "mascarade-kicad:latest",
    "finetuned-mascarade-spice-v1": "mascarade-spice:latest",
}

JUDGE_SYSTEM = """Tu es un evaluateur expert en electronique, PCB, SPICE, systemes embarques et KiCad.
Tu dois evaluer la qualite d'une reponse technique sur une echelle de 1 a 10.

Criteres de notation :
- Exactitude technique (40%) : les informations sont-elles correctes ?
- Completude (25%) : la reponse couvre-t-elle tous les aspects de la question ?
- Clarte (20%) : la reponse est-elle bien structuree et comprehensible ?
- Pertinence (15%) : les details fournis sont-ils utiles et pertinents ?

Tu dois repondre UNIQUEMENT en JSON valide, sans aucun texte avant ou apres."""


def judge_with_codestral(question: str, response: str) -> dict:
    """Score a response using Codestral API with JSON mode."""
    try:
        with httpx.Client(timeout=30.0) as client:
            resp = client.post(
                CODESTRAL_URL,
                headers={
                    "Authorization": f"Bearer {CODESTRAL_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "codestral-latest",
                    "messages": [
                        {"role": "system", "content": JUDGE_SYSTEM},
                        {"role": "user", "content": f"Question posee:\n{question}\n\nReponse a evaluer:\n{response}\n\nDonne ton evaluation en JSON: {{\"score\": N, \"exactitude\": N, \"completude\": N, \"clarte\": N, \"pertinence\": N, \"justification\": \"...\"}}"},
                    ],
                    "response_format": {"type": "json_object"},
                    "temperature": 0.1,
                    "max_tokens": 256,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            result = json.loads(content)
            return {
                "score": result.get("score", 0),
                "exactitude": result.get("exactitude", 0),
                "completude": result.get("completude", 0),
                "clarte": result.get("clarte", 0),
                "pertinence": result.get("pertinence", 0),
                "justification": result.get("justification", ""),
            }
    except Exception as e:
        return {"score": 0, "justification": f"Error: {e}"}


def query_ollama(model: str, prompt: str) -> str:
    """Get response from Ollama model."""
    try:
        with httpx.Client(timeout=120.0) as client:
            resp = client.post(f"{OLLAMA_URL}/api/generate", json={
                "model": model,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0.2, "num_predict": 512},
            })
            resp.raise_for_status()
            return resp.json().get("response", "")
    except Exception:
        return ""


def main():
    print("=== T-MA-021c: Codestral API Judge Benchmark ===")
    print("Judge: Codestral API (JSON mode)")

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

    # Check available models
    available = set()
    try:
        resp = httpx.get(f"{OLLAMA_URL}/api/tags", timeout=10)
        for m in resp.json().get("models", []):
            available.add(m["name"])
    except Exception:
        pass

    active_models = {}
    for label, model_name in MODELS.items():
        if any(model_name.split(":")[0] in a for a in available):
            active_models[label] = model_name
        else:
            print(f"  SKIP {label} ({model_name})")
    print(f"Models: {len(active_models)}\n")

    # Also benchmark Codestral API directly
    active_models["codestral-api-baseline"] = "__codestral_api__"

    all_results = {}

    for label, model_name in active_models.items():
        print(f"\n=== {label} ===")
        scores = []
        domain_scores = {}
        details = []

        for i, prompt_data in enumerate(prompts):
            question = prompt_data["prompt"]
            domain = prompt_data.get("domain", "unknown")

            # Get model response
            if model_name == "__codestral_api__":
                try:
                    with httpx.Client(timeout=30.0) as client:
                        resp = client.post(CODESTRAL_URL, headers={
                            "Authorization": f"Bearer {CODESTRAL_KEY}",
                            "Content-Type": "application/json",
                        }, json={
                            "model": "codestral-latest",
                            "messages": [{"role": "user", "content": question}],
                            "temperature": 0.2,
                            "max_tokens": 512,
                        })
                        response = resp.json()["choices"][0]["message"]["content"]
                except Exception:
                    response = ""
            else:
                response = query_ollama(model_name, question)

            if not response:
                scores.append(0)
                details.append({"prompt_id": i, "domain": domain, "score": 0})
                continue

            # Judge with Codestral
            judgment = judge_with_codestral(question, response)
            score = judgment.get("score", 0)
            scores.append(score)

            if domain not in domain_scores:
                domain_scores[domain] = []
            domain_scores[domain].append(score)

            details.append({
                "prompt_id": prompt_data.get("id", i),
                "domain": domain,
                "score": score,
                "exactitude": judgment.get("exactitude", 0),
                "completude": judgment.get("completude", 0),
                "clarte": judgment.get("clarte", 0),
                "pertinence": judgment.get("pertinence", 0),
                "justification": judgment.get("justification", "")[:200],
            })

            if (i + 1) % 10 == 0:
                avg = sum(scores) / len(scores)
                print(f"  [{i+1}/{len(prompts)}] avg={avg:.2f}/10")

        avg_score = sum(scores) / len(scores) if scores else 0
        domain_avg = {d: round(sum(s) / len(s), 2) for d, s in domain_scores.items()}

        all_results[label] = {
            "avg_score": round(avg_score, 2),
            "domain_scores": domain_avg,
            "details": details,
        }
        print(f"  DONE: {avg_score:.2f}/10 | Domains: {domain_avg}")

    # Save results
    with open(f"{OUTPUT_DIR}/judge_results.json", "w") as f:
        json.dump(all_results, f, indent=2, ensure_ascii=False)

    # Generate report
    report = "# T-MA-021c: Codestral API Judge Benchmark\n\n"
    report += f"Date: {time.strftime('%Y-%m-%d %H:%M')}\n"
    report += "Judge: Codestral API (JSON mode)\n"
    report += f"Prompts: {len(prompts)}\n\n"
    report += "## Summary (Score /10)\n\n"
    report += "| Model | Score | KiCad | SPICE | Embedded | Mixed |\n"
    report += "|-------|-------|-------|-------|----------|-------|\n"

    for label, data in sorted(all_results.items(), key=lambda x: -x[1]["avg_score"]):
        ds = data["domain_scores"]
        report += f"| {label} | **{data['avg_score']:.2f}** | {ds.get('kicad', '-')} | {ds.get('spice', '-')} | {ds.get('embedded', '-')} | {ds.get('mixed', '-')} |\n"

    with open(f"{OUTPUT_DIR}/JUDGE_REPORT.md", "w") as f:
        f.write(report)

    print(f"\n{report}")
    print(f"Results: {OUTPUT_DIR}/")


if __name__ == "__main__":
    main()
