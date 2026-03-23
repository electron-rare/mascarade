#!/usr/bin/env python3
"""ANE priority_models cycle via Mistral Batch API.

Submits all 4 pipeline stages (outline, structure, rewrite, gate) as a single
batch job to Mistral. No local model loading required.

Usage:
    # Submit batch
    python3 scripts/ane_mistral_batch_cycle.py submit

    # Check status
    python3 scripts/ane_mistral_batch_cycle.py status <job_id>

    # Retrieve results
    python3 scripts/ane_mistral_batch_cycle.py results <job_id>

    # Full cycle (submit + poll + results)
    python3 scripts/ane_mistral_batch_cycle.py run

Env:
    MISTRAL_API_KEY     Required — Mistral API key
    MISTRAL_MODEL       Model to use (default: mistral-large-latest)
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

try:
    from mistralai.client import Mistral
except ImportError:
    try:
        from mistralai import Mistral
    except ImportError:
        print("Install mistralai: pip install mistralai")
        sys.exit(1)

API_KEY = os.environ.get("MISTRAL_API_KEY", "")
MODEL = os.environ.get("MISTRAL_MODEL", "mistral-large-latest")
OUTPUT_DIR = Path("/tmp/ane_mistral_batch")
OUTPUT_DIR.mkdir(exist_ok=True)


def get_client() -> Mistral:
    if not API_KEY:
        print("Error: MISTRAL_API_KEY not set")
        sys.exit(1)
    return Mistral(api_key=API_KEY)


# ── Pipeline prompts ──────────────────────────────────────────────────

STAGES = [
    {
        "custom_id": "outline",
        "body": {
            "model": MODEL,
            "max_tokens": 256,
            "temperature": 0.3,
            "messages": [
                {"role": "system", "content": "You are a story planner. Create a concise outline for a short story."},
                {"role": "user", "content": (
                    "Create an outline for a 3-chapter mystery story set in a lighthouse. "
                    "Include: premise, main character, and a brief summary of each chapter. "
                    "Be concise — max 200 words."
                )},
            ],
        },
    },
    {
        "custom_id": "structure",
        "body": {
            "model": MODEL,
            "max_tokens": 512,
            "temperature": 0.2,
            "messages": [
                {"role": "system", "content": "You are a story structure assistant. Output valid JSON only, no markdown fences."},
                {"role": "user", "content": (
                    "Create a structured JSON for a 3-chapter mystery story set in a lighthouse. "
                    "Keys: title, premise, protagonist (name, trait), chapters (array of {number, title, summary})."
                )},
            ],
        },
    },
    {
        "custom_id": "rewrite",
        "body": {
            "model": MODEL,
            "max_tokens": 256,
            "temperature": 0.7,
            "messages": [
                {"role": "system", "content": (
                    "You are a literary prose writer. Write vivid, engaging prose. "
                    "Preserve meaning while elevating the language."
                )},
                {"role": "user", "content": (
                    "Rewrite this opening paragraph into rich, literary prose:\n\n"
                    "'The lighthouse keeper walked up the spiral stairs. The light was broken. "
                    "He needed to fix it before the storm. The wind was getting stronger.'"
                )},
            ],
        },
    },
    {
        "custom_id": "gate",
        "body": {
            "model": MODEL,
            "max_tokens": 256,
            "temperature": 0.2,
            "messages": [
                {"role": "system", "content": (
                    "You are a quality reviewer for creative writing. "
                    "Evaluate the prose below on: clarity (1-5), engagement (1-5), originality (1-5). "
                    "Output JSON: {clarity: N, engagement: N, originality: N, verdict: 'pass'|'revise', notes: '...'}"
                )},
                {"role": "user", "content": (
                    "Evaluate this prose:\n\n"
                    "The keeper climbed the spiral stairs as wind howled outside, "
                    "each step a percussion against the stone, each gust a whispered threat. "
                    "Above, the great lens sat dark and cold — a dead eye staring out to sea."
                )},
            ],
        },
    },
]


def cmd_submit() -> str:
    """Submit batch job and return job ID."""
    client = get_client()

    print(f"Submitting {len(STAGES)} requests as inline batch")

    # Create batch job with inline requests (no file upload)
    job = client.batch.jobs.create(
        requests=STAGES,
        model=MODEL,
        endpoint="/v1/chat/completions",
        metadata={"project": "ane-priority-models", "cycle": "priority_models"},
    )
    print(f"Batch job created: {job.id}")
    print(f"Status: {job.status}")

    # Save job ID
    state_path = OUTPUT_DIR / "batch_state.json"
    with open(state_path, "w") as f:
        json.dump({"job_id": job.id, "model": MODEL, "created": time.strftime("%Y-%m-%dT%H:%M:%S")}, f, indent=2)
    print(f"State saved to {state_path}")

    return job.id


def cmd_status(job_id: str) -> dict:
    """Check batch job status."""
    client = get_client()
    job = client.batch.jobs.get(job_id=job_id)
    print(f"Job: {job.id}")
    print(f"Status: {job.status}")
    print(f"Progress: {job.succeeded_requests}/{job.total_requests} succeeded, {job.failed_requests} failed")
    if job.output_file:
        print(f"Output file: {job.output_file}")
    return {"status": job.status, "succeeded": job.succeeded_requests, "total": job.total_requests, "output_file": job.output_file}


def cmd_results(job_id: str) -> list[dict]:
    """Download and parse batch results."""
    client = get_client()
    job = client.batch.jobs.get(job_id=job_id)

    if job.status != "SUCCESS":
        print(f"Job not complete yet: {job.status}")
        return []

    if not job.output_file:
        print("No output file available")
        return []

    # Download output
    content = client.files.download(file_id=job.output_file)
    output_path = OUTPUT_DIR / "batch_output.jsonl"
    with open(output_path, "wb") as f:
        for chunk in content.stream:
            f.write(chunk)
    print(f"Output downloaded to {output_path}")

    # Parse results
    results = []
    with open(output_path) as f:
        for line in f:
            if not line.strip():
                continue
            results.append(json.loads(line))

    # Display
    print(f"\n{'='*60}")
    print("BATCH RESULTS")
    print(f"{'='*60}")
    for r in results:
        cid = r.get("custom_id", "?")
        resp = r.get("response", {})
        body = resp.get("body", {})
        choices = body.get("choices", [])
        usage = body.get("usage", {})
        content = choices[0]["message"]["content"] if choices else "(empty)"

        print(f"\n--- {cid} ---")
        print(f"Tokens: {usage.get('prompt_tokens', 0)} in / {usage.get('completion_tokens', 0)} out")
        print(f"Content: {content[:300]}{'...' if len(content) > 300 else ''}")

        # Validate JSON for structure/gate stages
        if cid in ("structure", "gate"):
            try:
                clean = content.strip()
                if clean.startswith("```"):
                    clean = clean.split("\n", 1)[-1].rsplit("```", 1)[0]
                parsed = json.loads(clean)
                print(f"JSON valid: YES")
                if cid == "gate":
                    print(f"Verdict: {parsed.get('verdict', '?')}")
            except json.JSONDecodeError:
                print(f"JSON valid: NO")

        results.append({"custom_id": cid, "content": content, "usage": usage})

    # Save summary
    summary_path = OUTPUT_DIR / "batch_summary.json"
    with open(summary_path, "w") as f:
        json.dump({
            "job_id": job_id,
            "model": MODEL,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "results": results,
        }, f, indent=2)
    print(f"\nSummary saved to {summary_path}")

    return results


def cmd_run():
    """Full cycle: submit → poll → results."""
    job_id = cmd_submit()

    print("\nPolling for completion...")
    while True:
        time.sleep(10)
        status = cmd_status(job_id)
        if status["status"] in ("SUCCESS", "FAILED", "TIMEOUT_EXCEEDED", "CANCELLED"):
            break
        print(f"  ...waiting ({status['succeeded']}/{status['total']})")

    if status["status"] == "SUCCESS":
        cmd_results(job_id)
    else:
        print(f"\nBatch job ended with status: {status['status']}")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(0)

    cmd = sys.argv[1]
    if cmd == "submit":
        cmd_submit()
    elif cmd == "status":
        if len(sys.argv) < 3:
            # Try to read from state file
            state_path = OUTPUT_DIR / "batch_state.json"
            if state_path.exists():
                job_id = json.load(open(state_path))["job_id"]
            else:
                print("Usage: status <job_id>")
                sys.exit(1)
        else:
            job_id = sys.argv[2]
        cmd_status(job_id)
    elif cmd == "results":
        if len(sys.argv) < 3:
            state_path = OUTPUT_DIR / "batch_state.json"
            if state_path.exists():
                job_id = json.load(open(state_path))["job_id"]
            else:
                print("Usage: results <job_id>")
                sys.exit(1)
        else:
            job_id = sys.argv[2]
        cmd_results(job_id)
    elif cmd == "run":
        cmd_run()
    else:
        print(f"Unknown command: {cmd}")
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
