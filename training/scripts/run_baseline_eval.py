#!/usr/bin/env python3
"""Run a fast multi-provider baseline eval through Mascarade API."""

from __future__ import annotations

import argparse
import json
import statistics
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

DEFAULT_PROVIDERS = "bedrock,openai,claude,google,mistral,huggingface"


@dataclass
class EvalRow:
    sample_id: str
    provider: str
    ok: bool
    latency_ms: float
    exact_match: bool
    expected_present: bool
    output_len: int
    error: str | None
    content: str
    model: str | None


def load_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def post_json(
    url: str, body: dict, headers: dict[str, str], timeout: int = 120
) -> dict:
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    for k, v in headers.items():
        req.add_header(k, v)
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def score_exact(expected: str, actual: str) -> bool:
    return expected.strip().lower() == actual.strip().lower()


def summarize(results: list[EvalRow]) -> dict[str, dict]:
    by_provider: dict[str, list[EvalRow]] = {}
    for row in results:
        by_provider.setdefault(row.provider, []).append(row)

    summary: dict[str, dict] = {}
    for provider, rows in by_provider.items():
        oks = [r for r in rows if r.ok]
        exact_hits = sum(1 for r in rows if r.exact_match)
        latencies = [r.latency_ms for r in oks]
        summary[provider] = {
            "requests": len(rows),
            "success_rate": (len(oks) / len(rows)) if rows else 0.0,
            "exact_match_rate": (exact_hits / len(rows)) if rows else 0.0,
            "latency_ms_p50": statistics.median(latencies) if latencies else None,
            "latency_ms_p95": (
                sorted(latencies)[int(len(latencies) * 0.95) - 1]
                if len(latencies) > 1
                else (latencies[0] if latencies else None)
            ),
            "avg_output_len": (
                (sum(r.output_len for r in oks) / len(oks)) if oks else 0.0
            ),
        }
    return summary


def write_summary_markdown(path: Path, summary: dict[str, dict]) -> None:
    lines = [
        "# Baseline Summary",
        "",
        "| Provider | Requests | Success | Exact match | p50 latency ms | p95 latency ms | Avg output len |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for provider, stats in summary.items():
        lines.append(
            f"| {provider} | {stats['requests']} | {stats['success_rate']:.1%} | "
            f"{stats['exact_match_rate']:.1%} | {stats['latency_ms_p50'] or '-'} | "
            f"{stats['latency_ms_p95'] or '-'} | {stats['avg_output_len']:.1f} |"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--eval", required=True, help="Path to eval JSONL")
    parser.add_argument("--out", required=True, help="Path to output JSONL")
    parser.add_argument("--summary", required=True, help="Path to summary markdown")
    parser.add_argument(
        "--api-url", default="http://localhost:3100", help="Mascarade API base URL"
    )
    parser.add_argument(
        "--providers", default=DEFAULT_PROVIDERS, help="Comma-separated provider list"
    )
    parser.add_argument("--api-key", default="", help="MASCARADE_API_KEY value")
    parser.add_argument("--strategy", default="best", help="Routing strategy")
    parser.add_argument(
        "--dry-run", action="store_true", help="No HTTP call, writes synthetic outputs"
    )
    args = parser.parse_args()

    eval_path = Path(args.eval)
    out_path = Path(args.out)
    summary_path = Path(args.summary)
    providers = [p.strip() for p in args.providers.split(",") if p.strip()]

    samples = load_jsonl(eval_path)
    if not samples:
        print("[ERROR] eval dataset is empty")
        return 1

    headers = {"Content-Type": "application/json"}
    if args.api_key:
        headers["Authorization"] = f"Bearer {args.api_key}"

    send_url = f"{args.api_url.rstrip('/')}/api/agents/send"
    results: list[EvalRow] = []

    for sample in samples:
        sample_id = sample.get("id", "unknown")
        messages = sample.get("messages", [])
        expected = sample.get("expected")
        expected_present = isinstance(expected, str) and bool(expected.strip())

        for provider in providers:
            start = time.perf_counter()
            if args.dry_run:
                content = f"[dry-run] provider={provider} sample={sample_id}"
                ok = True
                model = "dry-run-model"
                error = None
            else:
                payload = {
                    "messages": messages,
                    "strategy": args.strategy,
                    "provider": provider,
                }
                try:
                    response = post_json(send_url, payload, headers)
                    content = str(response.get("content", ""))
                    model = response.get("model")
                    ok = True
                    error = None
                except urllib.error.HTTPError as exc:
                    content = ""
                    model = None
                    ok = False
                    error = f"http_{exc.code}"
                except Exception as exc:  # noqa: BLE001
                    content = ""
                    model = None
                    ok = False
                    error = f"error:{exc.__class__.__name__}"

            latency_ms = (time.perf_counter() - start) * 1000
            exact = expected_present and score_exact(expected, content)
            results.append(
                EvalRow(
                    sample_id=str(sample_id),
                    provider=provider,
                    ok=ok,
                    latency_ms=latency_ms,
                    exact_match=bool(exact),
                    expected_present=expected_present,
                    output_len=len(content),
                    error=error,
                    content=content,
                    model=model,
                )
            )
            status = "OK" if ok else "FAIL"
            print(
                f"[{status}] {provider} sample={sample_id} latency={latency_ms:.1f}ms error={error or '-'}"
            )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        for row in results:
            f.write(
                json.dumps(
                    {
                        "sample_id": row.sample_id,
                        "provider": row.provider,
                        "ok": row.ok,
                        "latency_ms": round(row.latency_ms, 2),
                        "exact_match": row.exact_match,
                        "expected_present": row.expected_present,
                        "output_len": row.output_len,
                        "error": row.error,
                        "model": row.model,
                        "content": row.content,
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )

    summary = summarize(results)
    write_summary_markdown(summary_path, summary)
    print(f"[OK] wrote results: {out_path}")
    print(f"[OK] wrote summary: {summary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
