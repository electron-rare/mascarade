"""Train the ML routing classifier from benchmark v3 results."""

import json
import os
import sys

sys.path.insert(0, "core")

from mascarade.router.ml_classifier import PromptFeatureExtractor, RoutingClassifier

BENCHMARK_DIR = "finetune/eval"
OUTPUT = "core/data/routing_classifier.json"


def find_latest_benchmark():
    """Find latest benchmark-v3 results."""
    for d in sorted(os.listdir(BENCHMARK_DIR), reverse=True):
        path = os.path.join(BENCHMARK_DIR, d, "benchmark_v3_results.json")
        if os.path.isfile(path):
            return path
    return None


def main():
    print("=== Train ML Routing Classifier ===")

    # Find benchmark results
    bench_path = find_latest_benchmark()
    if not bench_path:
        print(
            "ERROR: No benchmark v3 results found. Run benchmark-v3-all-models.py first."
        )
        return

    with open(bench_path) as f:
        results = json.load(f)

    print(f"Loaded benchmark: {bench_path}")
    print(f"Models: {list(results.keys())}")

    # Load prompts
    prompts = []
    for pf in [
        "finetune/eval/benchmark_prompts.jsonl",
        "finetune/eval/adversarial_prompts.jsonl",
    ]:
        if os.path.exists(pf):
            with open(pf) as f:
                for line in f:
                    if line.strip():
                        try:
                            prompts.append(json.loads(line.strip()))
                        except json.JSONDecodeError:
                            pass

    print(f"Prompts: {len(prompts)}")

    # Build training data: for each prompt, find the best model
    extractor = PromptFeatureExtractor()
    classifier = RoutingClassifier()

    # Map model names to routing tiers
    model_tiers = {}
    for name, data in results.items():
        score = data.get("avg_score", 0)
        if "spice" in name:
            model_tiers[name] = "strong" if score >= 6 else "cheap"
        elif "kicad" in name:
            model_tiers[name] = "strong" if score >= 6 else "cheap"
        elif "base" in name or "phi2" in name:
            model_tiers[name] = "cheap"
        else:
            model_tiers[name] = "strong" if score >= 6 else "fast"

    print(f"Tiers: {model_tiers}")

    # Record outcomes
    for prompt_data in prompts:
        prompt = prompt_data["prompt"]
        domain = prompt_data.get("domain", "general")

        # Find best model for this domain
        best_model = None
        best_score = 0
        for name, data in results.items():
            domain_scores = data.get("domains", {})
            score = domain_scores.get(domain, data.get("avg_score", 0))
            if score > best_score:
                best_score = score
                best_model = name

        if best_model and best_model in model_tiers:
            tier = model_tiers[best_model]
            classifier.record_outcome(prompt, tier, success=True, latency_ms=100.0, cost=0.0)

    print(f"Recorded {len(prompts)} outcomes")

    # Train
    success = classifier.train()
    if success:
        classifier.save(OUTPUT)
        print(f"Classifier trained and saved to {OUTPUT}")

        # Test predictions
        test_prompts = [
            "Design a buck converter 12V to 3.3V at 2A",
            "Write a KiCad schematic for an LED driver",
            "Simulate an op-amp filter in SPICE",
            "Configure STM32 UART with DMA",
            "What are the IPC-2221 trace width requirements?",
        ]
        for tp in test_prompts:
            pred, conf = classifier.predict_with_confidence(tp)
            print(f"  '{tp[:50]}...' -> {pred} (conf={conf:.2f})")
    else:
        print("Training failed — not enough data or diversity")


if __name__ == "__main__":
    main()
