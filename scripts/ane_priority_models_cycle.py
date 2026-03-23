#!/usr/bin/env python3
"""ANE priority_models cycle — run full pipeline stages through Mascarade.

Stages: outline → structure → rewrite → gate
Tests the local Apple CoreML reference model end-to-end.
"""

import json
import sys
import time

import httpx

BASE_URL = "http://127.0.0.1:8100"
MODEL = "apple-coreml:qwen3-4b-instruct-2507-q4f16"
PROJECT_ID = "ane-priority-models"
TIMEOUT = 300.0

results = []


def call(stage: str, system: str, user: str, max_tokens: int = 256, temperature: float = 0.3):
    """Call Mascarade chat completions and record result."""
    print(f"\n{'='*60}")
    print(f"Stage: {stage}")
    print(f"{'='*60}")

    t0 = time.time()
    try:
        resp = httpx.post(
            f"{BASE_URL}/v1/chat/completions",
            json={
                "model": MODEL,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "max_tokens": max_tokens,
                "temperature": temperature,
                "stream": False,
                "project_id": PROJECT_ID,
            },
            timeout=TIMEOUT,
        )
        elapsed = time.time() - t0
        data = resp.json()

        if "choices" in data:
            content = data["choices"][0]["message"]["content"]
            usage = data.get("usage", {})
            tok = usage.get("completion_tokens", 0)
            tok_s = tok / elapsed if elapsed > 0 else 0
            print(f"  OK — {tok} tokens in {elapsed:.1f}s ({tok_s:.1f} tok/s)")
            print(f"  Preview: {content[:200]}...")
            results.append({
                "stage": stage,
                "status": "pass",
                "tokens": tok,
                "elapsed_s": round(elapsed, 1),
                "tok_s": round(tok_s, 1),
                "content_length": len(content),
            })
            return content
        else:
            detail = data.get("detail", str(data))
            print(f"  FAIL — {detail[:200]}")
            results.append({"stage": stage, "status": "fail", "error": str(detail)[:200], "elapsed_s": round(time.time() - t0, 1)})
            return None

    except Exception as exc:
        elapsed = time.time() - t0
        print(f"  ERROR — {exc}")
        results.append({"stage": stage, "status": "error", "error": str(exc)[:200], "elapsed_s": round(elapsed, 1)})
        return None


# ── Stage 1: Outline ──────────────────────────────────────────────────

outline = call(
    "outline",
    "You are a story planner. Create a concise outline for a short story.",
    "Create an outline for a 3-chapter mystery story set in a lighthouse. "
    "Include: premise, main character, and a brief summary of each chapter. "
    "Be concise — max 200 words.",
    max_tokens=256,
)

# ── Stage 2: Structure ────────────────────────────────────────────────

structure = call(
    "structure",
    "You are a story structure assistant. Output valid JSON only, no markdown fences.",
    f"Convert this outline into structured JSON with keys: "
    f"title, premise, protagonist (name, trait), chapters (array of {{number, title, summary}}).\n\n"
    f"Outline:\n{outline or 'A mystery in a lighthouse with 3 chapters.'}",
    max_tokens=512,
    temperature=0.2,
)

# Validate JSON
json_valid = False
if structure:
    try:
        parsed = json.loads(structure)
        json_valid = True
        print(f"  JSON valid: YES — title='{parsed.get('title', '?')}', chapters={len(parsed.get('chapters', []))}")
    except json.JSONDecodeError as e:
        # Try stripping markdown fences
        clean = structure.strip()
        if clean.startswith("```"):
            clean = clean.split("\n", 1)[-1].rsplit("```", 1)[0]
            try:
                parsed = json.loads(clean)
                json_valid = True
                print(f"  JSON valid: YES (after stripping markdown) — title='{parsed.get('title', '?')}'")
            except json.JSONDecodeError:
                pass
        if not json_valid:
            print(f"  JSON valid: NO — {e}")

results[-1]["json_valid"] = json_valid

# ── Stage 3: Rewrite ─────────────────────────────────────────────────

rewrite = call(
    "rewrite",
    "You are a literary prose writer. Write vivid, engaging prose. "
    "Preserve meaning while elevating the language.",
    "Rewrite this opening paragraph into rich, literary prose:\n\n"
    "'The lighthouse keeper walked up the spiral stairs. The light was broken. "
    "He needed to fix it before the storm. The wind was getting stronger.'",
    max_tokens=256,
    temperature=0.7,
)

# ── Stage 4: Gate ─────────────────────────────────────────────────────

gate = call(
    "gate",
    "You are a quality reviewer for creative writing. "
    "Evaluate the prose below on: clarity (1-5), engagement (1-5), originality (1-5). "
    "Output JSON: {clarity: N, engagement: N, originality: N, verdict: 'pass'|'revise', notes: '...'}",
    f"Evaluate this prose:\n\n{rewrite or 'The keeper climbed the spiral stairs as wind howled outside.'}",
    max_tokens=256,
    temperature=0.2,
)

# Validate gate JSON
gate_valid = False
gate_verdict = None
if gate:
    try:
        clean = gate.strip()
        if clean.startswith("```"):
            clean = clean.split("\n", 1)[-1].rsplit("```", 1)[0]
        gdata = json.loads(clean)
        gate_valid = True
        gate_verdict = gdata.get("verdict", "?")
        print(f"  Gate verdict: {gate_verdict}")
        print(f"  Scores: clarity={gdata.get('clarity')}, engagement={gdata.get('engagement')}, originality={gdata.get('originality')}")
    except json.JSONDecodeError:
        print(f"  Gate JSON invalid")

results[-1]["gate_valid"] = gate_valid
results[-1]["gate_verdict"] = gate_verdict

# ── Summary ───────────────────────────────────────────────────────────

print(f"\n{'='*60}")
print("CYCLE SUMMARY")
print(f"{'='*60}")

total_tokens = sum(r.get("tokens", 0) for r in results)
total_time = sum(r.get("elapsed_s", 0) for r in results)
all_pass = all(r["status"] == "pass" for r in results)

for r in results:
    status = r["status"].upper()
    extra = ""
    if r.get("json_valid") is not None:
        extra += f" json={'OK' if r['json_valid'] else 'FAIL'}"
    if r.get("gate_verdict"):
        extra += f" verdict={r['gate_verdict']}"
    print(f"  {r['stage']:12s} {status:5s}  {r.get('elapsed_s', '?'):>6}s  {r.get('tokens', '?'):>4} tok{extra}")

print(f"\n  Total: {total_tokens} tokens in {total_time:.0f}s ({total_tokens/total_time:.1f} tok/s avg)")
print(f"  Cycle: {'PASS' if all_pass else 'FAIL'}")

# Save results
out_path = "/tmp/ane_priority_models_cycle.json"
with open(out_path, "w") as f:
    json.dump({"model": MODEL, "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"), "results": results, "cycle_pass": all_pass}, f, indent=2)
print(f"\n  Results saved to {out_path}")
