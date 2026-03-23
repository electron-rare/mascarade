#!/usr/bin/env python3
"""RouteLLM-style cost/quality routing POC for Mascarade.

This script does not call external APIs. It estimates prompt complexity and
recommends either a "cheap" or "strong" model based on a tunable threshold.
"""

from __future__ import annotations

import argparse
import json
import math
import re
from dataclasses import dataclass, asdict


def estimate_tokens(text: str) -> int:
    # Lightweight estimate for planning (not tokenizer-accurate).
    return max(1, math.ceil(len(text) / 4))


def complexity_score(prompt: str) -> float:
    text = prompt or ""
    length_score = min(len(text) / 6000.0, 1.0)
    code_score = (
        0.25 if re.search(r"```|class\\s+|def\\s+|function\\s+", text, re.I) else 0.0
    )
    math_score = (
        0.20
        if re.search(r"\\b(O\\(|NP|FFT|integral|derive|proof)\\b", text, re.I)
        else 0.0
    )
    multilingual_score = (
        0.10 if re.search(r"[\\u0400-\\u04FF\\u4E00-\\u9FFF]", text) else 0.0
    )
    planning_score = (
        0.15
        if re.search(r"\\b(plan|todo|roadmap|architecture|threat model)\\b", text, re.I)
        else 0.0
    )
    raw = length_score + code_score + math_score + multilingual_score + planning_score
    return max(0.0, min(raw, 1.0))


def estimate_cost_usd(
    tokens_in: int, tokens_out: int, cost_in: float, cost_out: float
) -> float:
    return ((tokens_in * cost_in) + (tokens_out * cost_out)) / 1_000_000.0


@dataclass
class RouteChoice:
    route: str
    provider: str
    model: str
    complexity: float
    threshold: float
    input_tokens: int
    output_tokens: int
    estimated_cost_usd: float
    estimated_savings_vs_strong_usd: float


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--prompt", required=True, help="Prompt to route")
    p.add_argument(
        "--threshold", type=float, default=0.58, help="Strong-model threshold [0..1]"
    )
    p.add_argument(
        "--output-tokens", type=int, default=700, help="Expected output tokens"
    )

    p.add_argument("--cheap-provider", default="openai")
    p.add_argument("--cheap-model", default="gpt-4o-mini")
    p.add_argument("--cheap-in", type=float, default=0.15, help="USD / 1M input tokens")
    p.add_argument(
        "--cheap-out", type=float, default=0.60, help="USD / 1M output tokens"
    )

    p.add_argument("--strong-provider", default="openai")
    p.add_argument("--strong-model", default="gpt-4.1")
    p.add_argument(
        "--strong-in", type=float, default=2.00, help="USD / 1M input tokens"
    )
    p.add_argument(
        "--strong-out", type=float, default=8.00, help="USD / 1M output tokens"
    )

    p.add_argument("--json", action="store_true", help="Emit JSON output")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    score = complexity_score(args.prompt)
    tokens_in = estimate_tokens(args.prompt)
    tokens_out = max(1, int(args.output_tokens))

    cheap_cost = estimate_cost_usd(tokens_in, tokens_out, args.cheap_in, args.cheap_out)
    strong_cost = estimate_cost_usd(
        tokens_in, tokens_out, args.strong_in, args.strong_out
    )
    choose_strong = score >= max(0.0, min(float(args.threshold), 1.0))

    choice = RouteChoice(
        route="strong" if choose_strong else "cheap",
        provider=args.strong_provider if choose_strong else args.cheap_provider,
        model=args.strong_model if choose_strong else args.cheap_model,
        complexity=round(score, 4),
        threshold=float(args.threshold),
        input_tokens=tokens_in,
        output_tokens=tokens_out,
        estimated_cost_usd=round(strong_cost if choose_strong else cheap_cost, 6),
        estimated_savings_vs_strong_usd=round(max(0.0, strong_cost - cheap_cost), 6),
    )

    if args.json:
        print(json.dumps(asdict(choice), ensure_ascii=True))
        return 0

    print("RouteLLM POC decision")
    print(f"- route: {choice.route}")
    print(f"- target: {choice.provider}/{choice.model}")
    print(f"- complexity: {choice.complexity} (threshold={choice.threshold})")
    print(f"- tokens: in={choice.input_tokens} out={choice.output_tokens}")
    print(f"- estimated cost: ${choice.estimated_cost_usd:.6f}")
    print(f"- savings vs strong: ${choice.estimated_savings_vs_strong_usd:.6f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
