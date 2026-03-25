#!/usr/bin/env python3
"""POC Ray for distributed agent execution in Mascarade."""

from __future__ import annotations

import argparse
import json
import time
from dataclasses import asdict, dataclass


@dataclass
class TaskResult:
    task_id: int
    worker: str
    latency_ms: float
    payload_size: int


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--tasks", type=int, default=12)
    p.add_argument("--payload-size", type=int, default=512)
    p.add_argument("--sleep-ms", type=int, default=30)
    p.add_argument("--json", action="store_true")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    try:
        import ray
    except Exception as exc:
        print(f"Ray unavailable: {exc}")
        print("Install with: python3 -m pip install ray")
        return 1

    @ray.remote
    def run_agent(task_id: int, payload: str, sleep_ms: int) -> dict:
        started = time.perf_counter()
        if sleep_ms > 0:
            time.sleep(sleep_ms / 1000.0)
        latency_ms = (time.perf_counter() - started) * 1000.0
        ctx = ray.get_runtime_context()
        return asdict(
            TaskResult(
                task_id=task_id,
                worker=(ctx.get_node_id() or "unknown"),
                latency_ms=latency_ms,
                payload_size=len(payload),
            )
        )

    ray.init(ignore_reinit_error=True, namespace="mascarade")
    payload = "x" * max(1, int(args.payload_size))
    futures = [
        run_agent.remote(i, payload, int(args.sleep_ms))
        for i in range(max(1, int(args.tasks)))
    ]
    results = ray.get(futures)
    ray.shutdown()

    avg = sum(float(item["latency_ms"]) for item in results) / len(results)
    summary = {
        "status": "ok",
        "tasks": len(results),
        "payload_size": len(payload),
        "avg_latency_ms": round(avg, 3),
        "results": results,
    }
    if args.json:
        print(json.dumps(summary, ensure_ascii=True))
    else:
        print("Ray agents POC")
        print(f"- tasks: {summary['tasks']}")
        print(f"- payload_size: {summary['payload_size']}")
        print(f"- avg_latency_ms: {summary['avg_latency_ms']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
