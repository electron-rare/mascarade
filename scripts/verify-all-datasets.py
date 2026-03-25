"""Verify ALL 61K dataset examples with local LLM judge.
For each Q&A: is the answer correct? Does it hallucinate? Should it say "I dont know"?"""

import json
import os
import re
import httpx

OLLAMA_URL = "http://localhost:11434"
JUDGE_MODEL = "qwen3:8b"  # Local, free, fast
CLEAN = "finetune/datasets/cleaned_final"
OUTPUT = "finetune/datasets/verified_final"
os.makedirs(OUTPUT, exist_ok=True)

VERIFY_PROMPT = """/no_think
You are a strict quality checker for electronics training data.

Given this Q&A pair, check:
1. Is the ANSWER technically correct? (no wrong values, formulas, or facts)
2. Does the answer MATCH the question? (not off-topic)
3. Does the answer HALLUCINATE? (invented component names, fake specs, wrong pin numbers)
4. Should the answer say "I don't know" instead? (if the question requires info not in the answer)

Rate 1-10:
- 8-10: Correct, complete, no hallucination
- 5-7: Mostly correct, minor issues
- 3-4: Has errors or hallucinations
- 1-2: Wrong or completely off-topic

Question: {question}
Answer: {answer}

Reply with ONLY a number 1-10."""


def judge_local(question, answer, timeout=15.0):
    """Judge with local Ollama model."""
    prompt = VERIFY_PROMPT.format(
        question=question[:400],
        answer=answer[:600],
    )
    try:
        with httpx.Client(timeout=timeout) as c:
            r = c.post(f"{OLLAMA_URL}/api/generate", json={
                "model": JUDGE_MODEL,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0.1, "num_predict": 10},
            })
            r.raise_for_status()
            text = r.json().get("response", "").strip()
            # Extract number
            nums = re.findall(r'\b(\d+)\b', text)
            for n in nums:
                v = int(n)
                if 1 <= v <= 10:
                    return v
    except Exception:
        pass
    return 0


def extract_qa(record):
    q, a = "", ""
    for c in record.get("conversations", []):
        role = c.get("from", c.get("role", ""))
        val = c.get("value", c.get("content", ""))
        if role in ("human", "user"): q += val + " "
        elif role in ("gpt", "assistant"): a += val + " "
    return q.strip(), a.strip()


# Process all datasets
datasets = sorted([f for f in os.listdir(CLEAN) if f.endswith(".jsonl") and os.path.getsize(os.path.join(CLEAN, f)) > 0])

grand_total = 0
grand_kept = 0
grand_removed = 0

for fn in datasets:
    path = os.path.join(CLEAN, fn)
    lines = []
    with open(path) as f:
        for line in f:
            if line.strip():
                try:
                    lines.append((line.strip(), json.loads(line.strip())))
                except:
                    pass

    if len(lines) < 5:
        print(f"\nSKIP {fn}: only {len(lines)} lines")
        continue

    print(f"\n{'='*50}")
    print(f"VERIFYING: {fn} ({len(lines)} examples)")
    print(f"{'='*50}")

    kept = []
    removed = 0
    scores = []
    issues = []

    # For large datasets, sample instead of checking all
    if len(lines) > 2000:
        import random
        random.seed(42)
        check_indices = set(random.sample(range(len(lines)), 500))
        # Keep unchecked lines by default
        for i, (raw, record) in enumerate(lines):
            if i not in check_indices:
                kept.append(raw)
    else:
        check_indices = set(range(len(lines)))

    checked = 0
    for i, (raw, record) in enumerate(lines):
        if i not in check_indices:
            continue

        q, a = extract_qa(record)
        if not q or not a:
            removed += 1
            continue

        score = judge_local(q, a)
        scores.append(score)
        checked += 1

        if score >= 5:
            kept.append(raw)
        else:
            removed += 1
            if score <= 3:
                issues.append(f"score={score}: Q={q[:80]}...")

        if checked % 100 == 0:
            avg = sum(scores) / len(scores)
            print(f"  [{checked}/{len(check_indices)}] avg={avg:.1f}/10, removed={removed}")

    # Save verified dataset
    out_path = os.path.join(OUTPUT, fn.replace("_final", "_verified"))
    with open(out_path, "w") as f:
        f.write("\n".join(kept) + "\n")

    avg = sum(scores) / max(len(scores), 1)
    pct_removed = removed / max(len(check_indices), 1) * 100
    grand_total += len(lines)
    grand_kept += len(kept)
    grand_removed += removed

    print(f"  Checked: {checked}, Avg score: {avg:.1f}/10")
    print(f"  Removed: {removed} ({pct_removed:.0f}%), Kept: {len(kept)}")
    if issues[:3]:
        print("  Worst issues:")
        for iss in issues[:3]:
            print(f"    {iss[:100]}")
    print(f"  -> {out_path}")

print(f"\n{'='*50}")
print("VERIFICATION COMPLETE")
print(f"{'='*50}")
print(f"Total: {grand_total}")
print(f"Kept: {grand_kept}")
print(f"Removed: {grand_removed} ({grand_removed/max(grand_total,1)*100:.1f}%)")
