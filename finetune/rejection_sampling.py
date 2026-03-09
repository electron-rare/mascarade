#!/usr/bin/env python3
"""Rejection sampling pipeline for generating DPO preference pairs.

Phase B of the Student-Teacher-Validator pipeline:
    1. Student generates N candidates per prompt
    2. Validator scores each candidate
    3. Best-passing = "chosen", worst-failing = "rejected"
    4. Output: DPO-ready preference dataset

Usage:
    python rejection_sampling.py stm32 \
        --student-model mascarade-stm32 \
        --n-candidates 8 \
        --output-dir ./dpo_pairs/stm32

    python rejection_sampling.py spice \
        --student-model mascarade-spice \
        --n-candidates 4 \
        --use-vllm
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

from validators import ValidationResult, get_validator

SCRIPT_DIR = Path(__file__).resolve().parent
DATASETS_DIR = SCRIPT_DIR / "datasets"

DOMAINS = [
    "stm32", "spice", "iot", "power", "dsp", "emc",
    "kicad", "embedded", "platformio", "freecad",
]


def load_prompts(domain: str, dataset_path: str | None = None, max_prompts: int | None = None) -> list[dict]:
    """Load prompts from ShareGPT dataset."""
    path = Path(dataset_path) if dataset_path else DATASETS_DIR / f"{domain}_chat.jsonl"
    if not path.exists():
        raise FileNotFoundError(f"Dataset not found: {path}")

    prompts = []
    with open(path) as f:
        for line in f:
            row = json.loads(line)
            convs = row.get("conversations", [])
            system = next((c["value"] for c in convs if c["from"] == "system"), "")
            human = next((c["value"] for c in convs if c["from"] == "human"), "")
            if human:
                prompts.append({"system": system, "human": human})

    if max_prompts:
        prompts = prompts[:max_prompts]
    return prompts


def generate_candidates_ollama(
    prompts: list[dict],
    model: str,
    n_candidates: int = 8,
    temperature: float = 0.8,
    max_tokens: int = 2048,
    base_url: str = "http://127.0.0.1:11434",
) -> list[list[str]]:
    """Generate N candidates per prompt using Ollama."""
    import urllib.request

    all_candidates = []
    total = len(prompts)

    for i, p in enumerate(prompts):
        candidates = []
        for j in range(n_candidates):
            payload = json.dumps({
                "model": model,
                "messages": [
                    {"role": "system", "content": p["system"]},
                    {"role": "user", "content": p["human"]},
                ],
                "stream": False,
                "options": {"temperature": temperature, "num_predict": max_tokens},
            }).encode()

            try:
                req = urllib.request.Request(
                    f"{base_url}/api/chat",
                    data=payload,
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                resp = urllib.request.urlopen(req, timeout=120)
                data = json.loads(resp.read())
                content = data.get("message", {}).get("content", "")
                candidates.append(content)
            except Exception as exc:
                print(f"  [WARN] Generation failed for prompt {i}, candidate {j}: {exc}")
                candidates.append("")

        all_candidates.append(candidates)
        if (i + 1) % 10 == 0 or i == 0:
            print(f"  Generated {i + 1}/{total} prompts ({n_candidates} candidates each)")

    return all_candidates


def generate_candidates_vllm(
    prompts: list[dict],
    model: str,
    n_candidates: int = 8,
    temperature: float = 0.8,
    max_tokens: int = 2048,
) -> list[list[str]]:
    """Generate N candidates per prompt using vLLM (much faster)."""
    from vllm import LLM, SamplingParams

    llm = LLM(
        model=model,
        gpu_memory_utilization=0.85,
        max_model_len=4096,
        dtype="bfloat16",
    )

    sampling_params = SamplingParams(
        n=n_candidates,
        temperature=temperature,
        top_p=0.95,
        max_tokens=max_tokens,
    )

    # Format prompts for vLLM
    formatted = []
    for p in prompts:
        formatted.append(f"System: {p['system']}\n\nUser: {p['human']}\n\nAssistant:")

    outputs = llm.generate(formatted, sampling_params)

    all_candidates = []
    for output in outputs:
        candidates = [c.text for c in output.outputs]
        all_candidates.append(candidates)

    del llm  # Free GPU memory
    return all_candidates


def build_dpo_pairs(
    prompts: list[dict],
    candidates: list[list[str]],
    domain: str,
    validator_kwargs: dict | None = None,
) -> list[dict]:
    """Score candidates with validator and build DPO preference pairs."""
    validator = get_validator(domain, **(validator_kwargs or {}))
    print(f"  Validator: {type(validator).__name__} (available: {validator.available()})")

    pairs = []
    stats = {"total": 0, "valid_pairs": 0, "no_pass": 0, "no_fail": 0, "all_same": 0}

    for i, (prompt, cands) in enumerate(zip(prompts, candidates)):
        stats["total"] += 1

        # Score all candidates
        scored = []
        for c in cands:
            if not c.strip():
                scored.append((c, ValidationResult(score=0.0, passed=False, errors=["Empty"])))
                continue
            result = validator.validate(prompt["human"], c)
            scored.append((c, result))

        # Sort by score descending
        scored.sort(key=lambda x: x[1].score, reverse=True)

        best_text, best_result = scored[0]
        worst_text, worst_result = scored[-1]

        # Need at least one pass and one fail for a valid DPO pair
        if best_result.score <= 0.0:
            stats["no_pass"] += 1
            continue
        if worst_result.score >= best_result.score:
            stats["all_same"] += 1
            continue
        if worst_result.score >= 0.8:
            stats["no_fail"] += 1
            continue

        pair = {
            "prompt": [
                {"role": "system", "content": prompt["system"]},
                {"role": "user", "content": prompt["human"]},
            ],
            "chosen": [{"role": "assistant", "content": best_text}],
            "rejected": [{"role": "assistant", "content": worst_text}],
            "metadata": {
                "domain": domain,
                "chosen_score": best_result.score,
                "rejected_score": worst_result.score,
                "chosen_errors": best_result.errors,
                "rejected_errors": worst_result.errors,
            },
        }
        pairs.append(pair)
        stats["valid_pairs"] += 1

        if (i + 1) % 50 == 0:
            print(f"  Validated {i + 1}/{len(prompts)} ({stats['valid_pairs']} pairs)")

    return pairs, stats


def main() -> int:
    parser = argparse.ArgumentParser(description="Rejection sampling for DPO pair generation")
    parser.add_argument("domain", choices=DOMAINS)
    parser.add_argument("--student-model", default=None, help="Student model for generation (ollama name or HF id)")
    parser.add_argument("--dataset-path", default=None)
    parser.add_argument("--output-dir", default=None)
    parser.add_argument("--n-candidates", type=int, default=8, help="Candidates per prompt")
    parser.add_argument("--max-prompts", type=int, default=None, help="Limit prompts for testing")
    parser.add_argument("--temperature", type=float, default=0.8)
    parser.add_argument("--max-tokens", type=int, default=2048)
    parser.add_argument("--use-vllm", action="store_true", help="Use vLLM instead of Ollama")
    parser.add_argument("--ollama-url", default="http://127.0.0.1:11434")
    args = parser.parse_args()

    # Defaults
    student_model = args.student_model or f"mascarade-{args.domain}"
    output_dir = Path(args.output_dir) if args.output_dir else SCRIPT_DIR / "dpo_pairs" / args.domain
    output_dir.mkdir(parents=True, exist_ok=True)

    stamp = time.strftime("%Y%m%d_%H%M%S")

    print("=" * 60)
    print(f"Rejection Sampling — {args.domain}")
    print(f"Model:      {student_model}")
    print(f"Candidates: {args.n_candidates} per prompt")
    print(f"Backend:    {'vLLM' if args.use_vllm else 'Ollama'}")
    print("=" * 60)

    # 1. Load prompts
    print("\n[1/3] Loading prompts...")
    prompts = load_prompts(args.domain, args.dataset_path, args.max_prompts)
    print(f"  Loaded {len(prompts)} prompts")

    # 2. Generate candidates
    print(f"\n[2/3] Generating {args.n_candidates} candidates per prompt...")
    if args.use_vllm:
        candidates = generate_candidates_vllm(
            prompts, student_model,
            n_candidates=args.n_candidates,
            temperature=args.temperature,
            max_tokens=args.max_tokens,
        )
    else:
        candidates = generate_candidates_ollama(
            prompts, student_model,
            n_candidates=args.n_candidates,
            temperature=args.temperature,
            max_tokens=args.max_tokens,
            base_url=args.ollama_url,
        )

    # 3. Build DPO pairs
    print("\n[3/3] Validating and building DPO pairs...")
    pairs, stats = build_dpo_pairs(prompts, candidates, args.domain)

    # Save
    output_file = output_dir / f"dpo_{args.domain}_{stamp}.jsonl"
    with open(output_file, "w") as f:
        for pair in pairs:
            f.write(json.dumps(pair, ensure_ascii=False) + "\n")

    stats_file = output_dir / f"stats_{args.domain}_{stamp}.json"
    with open(stats_file, "w") as f:
        json.dump(stats, f, indent=2)

    print(f"\n{'=' * 60}")
    print(f"Results:")
    print(f"  Prompts processed:  {stats['total']}")
    print(f"  Valid DPO pairs:    {stats['valid_pairs']} ({stats['valid_pairs'] * 100 // max(1, stats['total'])}%)")
    print(f"  No passing cand.:   {stats['no_pass']}")
    print(f"  No failing cand.:   {stats['no_fail']}")
    print(f"  All same score:     {stats['all_same']}")
    print(f"  Output: {output_file}")
    print(f"{'=' * 60}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
