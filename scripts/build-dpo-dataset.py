#!/usr/bin/env python3
"""Build DPO (Direct Preference Optimization) dataset from benchmark judge results.

Loads Codestral judge results (judge_results.json) and benchmark prompts, then
re-queries Ollama models to collect chosen/rejected response pairs for DPO training.

For each prompt:
  - Identify the best-scoring model (chosen) and worst-scoring model (rejected)
  - Only keep pairs where the score gap exceeds a threshold (default >2 points)
  - Re-query both models via Ollama to capture actual response text
  - Output JSONL in standard DPO format

Usage:
  # Specify judge results explicitly
  python scripts/build-dpo-dataset.py --judge-results finetune/eval/judge-codestral-20260322-180000/judge_results.json

  # Auto-detect latest judge results
  python scripts/build-dpo-dataset.py --auto

  # Custom Ollama endpoint and threshold
  OLLAMA_URL=http://kxkm-ai:11434 python scripts/build-dpo-dataset.py --auto --min-gap 3

  # Dry run: show pairs without querying models
  python scripts/build-dpo-dataset.py --auto --dry-run

Environment:
  OLLAMA_URL  — Ollama API base URL (default: http://localhost:11434)
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

try:
    import httpx
except ImportError:
    sys.exit("httpx required: pip install httpx")

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
PROMPTS_FILE = Path("finetune/eval/benchmark_prompts.jsonl")
JUDGE_DIR = Path("finetune/eval")
OUTPUT_FILE = Path("finetune/datasets/dpo_benchmark_pairs.jsonl")
DEFAULT_MIN_GAP = 2.0

# Model label -> Ollama model name (must match run-benchmark-judge-codestral.py)
MODELS = {
    "base-qwen2.5-7b": "qwen2.5:7b",
    "base-mistral-7b": "mistral:7b",
    "finetuned-kicad-v2": "kicadv2",
    "finetuned-mascarade-kicad-v1": "mascarade-kicad:latest",
    "finetuned-mascarade-spice-v1": "mascarade-spice:latest",
}

# Codestral API baseline is excluded from DPO — we only build pairs from
# local Ollama models that can actually be distilled into a fine-tune.
SKIP_LABELS = {"codestral-api-baseline"}

OLLAMA_GENERATE_OPTS = {
    "temperature": 0.2,
    "num_predict": 512,
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def find_latest_judge_results() -> Path | None:
    """Find the most recent judge-codestral-*/judge_results.json."""
    candidates = sorted(
        JUDGE_DIR.glob("judge-codestral-*/judge_results.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    return candidates[0] if candidates else None


def load_prompts(path: Path) -> list[dict]:
    """Load benchmark prompts from JSONL."""
    prompts = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    prompts.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    return prompts


def load_judge_results(path: Path) -> dict:
    """Load judge_results.json and return {model_label: {details: [...]}}."""
    with open(path) as f:
        return json.load(f)


def check_ollama_models(needed_models: set[str]) -> set[str]:
    """Return the subset of Ollama model names that are actually available."""
    try:
        resp = httpx.get(f"{OLLAMA_URL}/api/tags", timeout=10)
        resp.raise_for_status()
        available = {m["name"] for m in resp.json().get("models", [])}
    except Exception as e:
        print(f"[WARN] Cannot reach Ollama at {OLLAMA_URL}: {e}")
        return set()

    found = set()
    for model in needed_models:
        # Match either exact name or prefix (e.g. "qwen2.5:7b" matches "qwen2.5:7b")
        prefix = model.split(":")[0]
        if model in available or any(prefix in a for a in available):
            found.add(model)
    return found


def query_ollama(model: str, prompt: str, timeout: float = 180.0) -> str:
    """Query an Ollama model and return the response text."""
    try:
        with httpx.Client(timeout=timeout) as client:
            resp = client.post(
                f"{OLLAMA_URL}/api/generate",
                json={
                    "model": model,
                    "prompt": prompt,
                    "stream": False,
                    "options": OLLAMA_GENERATE_OPTS,
                },
            )
            resp.raise_for_status()
            return resp.json().get("response", "")
    except httpx.TimeoutException:
        print(f"    [TIMEOUT] {model}")
        return ""
    except Exception as e:
        print(f"    [ERROR] {model}: {e}")
        return ""


# ---------------------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------------------


def build_prompt_score_map(
    judge_results: dict,
    prompts: list[dict],
) -> dict[str, dict[str, float]]:
    """Build {prompt_id: {model_label: score}} from judge results.

    Returns a mapping keyed by prompt_id. For each prompt, the value is a dict
    of model_label -> score (float).
    """
    prompt_scores: dict[str, dict[str, float]] = {}

    for label, model_data in judge_results.items():
        if label in SKIP_LABELS:
            continue
        if label not in MODELS:
            # Unknown model label — skip unless it maps to a known Ollama model
            continue

        details = model_data.get("details", [])
        for entry in details:
            pid = str(entry.get("prompt_id", ""))
            score = float(entry.get("score", 0))
            if pid not in prompt_scores:
                prompt_scores[pid] = {}
            prompt_scores[pid][label] = score

    return prompt_scores


def select_dpo_pairs(
    prompt_scores: dict[str, dict[str, float]],
    min_gap: float,
) -> list[dict]:
    """For each prompt, pick best/worst model pair with sufficient score gap.

    Returns list of dicts with keys: prompt_id, chosen_label, rejected_label,
    chosen_score, rejected_score, gap.
    """
    pairs = []
    for pid, scores in prompt_scores.items():
        if len(scores) < 2:
            continue

        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        best_label, best_score = ranked[0]
        worst_label, worst_score = ranked[-1]
        gap = best_score - worst_score

        if gap < min_gap:
            continue

        pairs.append(
            {
                "prompt_id": pid,
                "chosen_label": best_label,
                "rejected_label": worst_label,
                "chosen_score": best_score,
                "rejected_score": worst_score,
                "gap": round(gap, 2),
            }
        )

    return pairs


def collect_responses(
    pairs: list[dict],
    prompts_by_id: dict[str, dict],
    dry_run: bool = False,
) -> list[dict]:
    """Re-query Ollama to get chosen/rejected responses for each pair.

    Returns list of DPO-format dicts ready to write as JSONL.
    """
    # Figure out which Ollama models we actually need
    needed_ollama = set()
    for p in pairs:
        needed_ollama.add(MODELS[p["chosen_label"]])
        needed_ollama.add(MODELS[p["rejected_label"]])

    if not dry_run:
        available = check_ollama_models(needed_ollama)
        missing = needed_ollama - available
        if missing:
            print(
                f"[WARN] Missing Ollama models (will skip prompts needing them): {missing}"
            )
    else:
        available = needed_ollama  # pretend everything is available

    dataset = []
    skipped = 0
    errors = 0
    total = len(pairs)

    for i, pair in enumerate(pairs):
        pid = pair["prompt_id"]
        prompt_data = prompts_by_id.get(pid)
        if not prompt_data:
            print(f"  [SKIP] prompt_id={pid} not found in prompts file")
            skipped += 1
            continue

        prompt_text = prompt_data["prompt"]
        chosen_model = MODELS[pair["chosen_label"]]
        rejected_model = MODELS[pair["rejected_label"]]

        # Check availability
        if chosen_model not in available or rejected_model not in available:
            skipped += 1
            continue

        if dry_run:
            chosen_resp = f"[DRY RUN — would query {chosen_model}]"
            rejected_resp = f"[DRY RUN — would query {rejected_model}]"
        else:
            print(
                f"  [{i+1}/{total}] prompt={pid}  chosen={pair['chosen_label']}({pair['chosen_score']})  rejected={pair['rejected_label']}({pair['rejected_score']})  gap={pair['gap']}"
            )

            chosen_resp = query_ollama(chosen_model, prompt_text)
            if not chosen_resp:
                print(f"    [SKIP] empty chosen response from {chosen_model}")
                errors += 1
                continue

            rejected_resp = query_ollama(rejected_model, prompt_text)
            if not rejected_resp:
                print(f"    [SKIP] empty rejected response from {rejected_model}")
                errors += 1
                continue

        record = {
            "prompt": prompt_text,
            "chosen": chosen_resp,
            "rejected": rejected_resp,
            "metadata": {
                "prompt_id": pid,
                "domain": prompt_data.get("domain", "unknown"),
                "chosen_model": pair["chosen_label"],
                "chosen_ollama": chosen_model,
                "chosen_score": pair["chosen_score"],
                "rejected_model": pair["rejected_label"],
                "rejected_ollama": rejected_model,
                "rejected_score": pair["rejected_score"],
                "score_gap": pair["gap"],
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
            },
        }
        dataset.append(record)

    print(
        f"\n  Collected: {len(dataset)} pairs  |  Skipped: {skipped}  |  Errors: {errors}"
    )
    return dataset


def save_dataset(dataset: list[dict], output: Path) -> None:
    """Write DPO dataset as JSONL."""
    output.parent.mkdir(parents=True, exist_ok=True)
    with open(output, "w") as f:
        for record in dataset:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    print(f"\nSaved {len(dataset)} DPO pairs -> {output}")


def print_summary(pairs: list[dict], dataset: list[dict]) -> None:
    """Print statistics about the built dataset."""
    if not pairs:
        print("\nNo pairs found with sufficient score gap.")
        return

    # Domain breakdown
    domains: dict[str, int] = {}
    for rec in dataset:
        d = rec["metadata"]["domain"]
        domains[d] = domains.get(d, 0) + 1

    # Model frequency as chosen/rejected
    chosen_counts: dict[str, int] = {}
    rejected_counts: dict[str, int] = {}
    for rec in dataset:
        cm = rec["metadata"]["chosen_model"]
        rm = rec["metadata"]["rejected_model"]
        chosen_counts[cm] = chosen_counts.get(cm, 0) + 1
        rejected_counts[rm] = rejected_counts.get(rm, 0) + 1

    gaps = [p["gap"] for p in pairs]
    avg_gap = sum(gaps) / len(gaps) if gaps else 0

    print("\n" + "=" * 60)
    print("DPO DATASET SUMMARY")
    print("=" * 60)
    print(f"  Total pairs:      {len(dataset)}")
    print(f"  Candidate pairs:  {len(pairs)} (before response collection)")
    print(f"  Avg score gap:    {avg_gap:.2f}")
    print(f"  Min gap:          {min(gaps):.2f}")
    print(f"  Max gap:          {max(gaps):.2f}")

    print("\n  By domain:")
    for d, count in sorted(domains.items()):
        print(f"    {d:12s}  {count}")

    print("\n  Chosen (best) model frequency:")
    for m, count in sorted(chosen_counts.items(), key=lambda x: -x[1]):
        print(f"    {m:40s}  {count}")

    print("\n  Rejected (worst) model frequency:")
    for m, count in sorted(rejected_counts.items(), key=lambda x: -x[1]):
        print(f"    {m:40s}  {count}")
    print()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build DPO dataset from benchmark judge results",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--judge-results",
        type=Path,
        help="Path to judge_results.json",
    )
    parser.add_argument(
        "--auto",
        action="store_true",
        help="Auto-detect the latest judge-codestral-*/judge_results.json",
    )
    parser.add_argument(
        "--prompts",
        type=Path,
        default=PROMPTS_FILE,
        help=f"Path to benchmark_prompts.jsonl (default: {PROMPTS_FILE})",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=OUTPUT_FILE,
        help=f"Output JSONL path (default: {OUTPUT_FILE})",
    )
    parser.add_argument(
        "--min-gap",
        type=float,
        default=DEFAULT_MIN_GAP,
        help=f"Minimum score difference to include a pair (default: {DEFAULT_MIN_GAP})",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show selected pairs without querying Ollama",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    print("=" * 60)
    print("BUILD DPO DATASET FROM BENCHMARK JUDGE RESULTS")
    print("=" * 60)
    print(f"  Ollama URL:  {OLLAMA_URL}")
    print(f"  Min gap:     {args.min_gap}")
    print(f"  Dry run:     {args.dry_run}")

    # --- Resolve judge results path ---
    judge_path = args.judge_results
    if judge_path is None:
        if args.auto:
            judge_path = find_latest_judge_results()
            if judge_path is None:
                sys.exit(
                    f"[ERROR] No judge results found in {JUDGE_DIR}/judge-codestral-*/"
                )
        else:
            sys.exit(
                "[ERROR] Provide --judge-results <path> or use --auto to detect latest"
            )

    print(f"  Judge file:  {judge_path}")

    # --- Load inputs ---
    print(f"\nLoading prompts from {args.prompts} ...")
    prompts = load_prompts(args.prompts)
    if not prompts:
        sys.exit(f"[ERROR] No prompts loaded from {args.prompts}")
    print(f"  {len(prompts)} prompts loaded")

    prompts_by_id = {}
    for p in prompts:
        pid = str(p.get("id", ""))
        if pid:
            prompts_by_id[pid] = p

    print(f"\nLoading judge results from {judge_path} ...")
    judge_results = load_judge_results(judge_path)
    model_labels = [l for l in judge_results if l not in SKIP_LABELS]
    print(f"  Models in results: {model_labels}")

    # --- Build score map and select pairs ---
    print("\nBuilding per-prompt score map ...")
    prompt_scores = build_prompt_score_map(judge_results, prompts)
    print(f"  {len(prompt_scores)} prompts have scores from multiple models")

    print(f"\nSelecting DPO pairs (min gap > {args.min_gap}) ...")
    pairs = select_dpo_pairs(prompt_scores, args.min_gap)
    print(f"  {len(pairs)} pairs selected")

    if not pairs:
        print("\nNo pairs meet the minimum gap threshold. Try lowering --min-gap.")
        sys.exit(0)

    # Show top pairs
    pairs.sort(key=lambda x: x["gap"], reverse=True)
    print("\n  Top 5 pairs by gap:")
    for p in pairs[:5]:
        print(
            f"    {p['prompt_id']:20s}  {p['chosen_label']} ({p['chosen_score']}) vs {p['rejected_label']} ({p['rejected_score']})  gap={p['gap']}"
        )

    # --- Collect responses ---
    print(f"\nCollecting responses from Ollama ({OLLAMA_URL}) ...")
    dataset = collect_responses(pairs, prompts_by_id, dry_run=args.dry_run)

    if not dataset:
        print("\nNo pairs collected. Check that Ollama models are running.")
        sys.exit(1)

    # --- Save ---
    save_dataset(dataset, args.output)
    print_summary(pairs, dataset)

    print("Done.")


if __name__ == "__main__":
    main()
