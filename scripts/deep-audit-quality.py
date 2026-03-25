"""Deep quality audit: LLM judge on random samples + cross-dataset dedup + content verification."""
import json
import os
import hashlib
import random
import httpx

CODESTRAL_URL = "https://codestral.mistral.ai/v1/chat/completions"
CODESTRAL_KEY = os.environ.get("CODESTRAL_API_KEY", "JbYYQUUpHOOFjpV5UuSct6QM4cT6otEl")
SAMPLE_PER_DATASET = 10  # judge 10 random samples per dataset

# ALL datasets used or to be used for training
ALL_FILES = [
    # Already trained
    "finetune/datasets/spice_chat.jsonl",
    "finetune/datasets/ipc_jlcpcb_standards_cleaned.jsonl",
    "finetune/datasets/kicad10_features_cleaned.jsonl",
    "finetune/datasets/emc_chat.jsonl",
    "finetune/datasets/analog_audio_electronics_cleaned.jsonl",
    "finetune/datasets/power_chat.jsonl",
    "finetune/datasets/dsp_chat.jsonl",
    "finetune/datasets/embedded_systems_full_cleaned.jsonl",
    "finetune/datasets/missing_domains_cleaned.jsonl",
    # To be trained (audited versions)
    "finetune/datasets/iot_chat_audited.jsonl",
    "finetune/datasets/freecad_chat_audited.jsonl",
    "finetune/datasets/platformio_chat_audited.jsonl",
    "finetune/datasets/stm32_chat_audited.jsonl",
    "finetune/datasets/kicad_chat_v3_multi_audited.jsonl",
    "finetune/datasets/hf_imports/rtlcoder3_audited.jsonl",
    "finetune/datasets/hf_imports/semiconductor_chat_audited.jsonl",
]

def extract_qa(record):
    """Extract question and answer from any format."""
    q, a = "", ""
    if "conversations" in record:
        for c in record["conversations"]:
            role = c.get("from", c.get("role", ""))
            val = c.get("value", c.get("content", ""))
            if role in ("human", "user"): q += val + " "
            elif role in ("gpt", "assistant"): a += val + " "
    elif "instruction" in record:
        q = str(record.get("instruction", ""))
        a = str(record.get("output", ""))
    elif "messages" in record:
        for m in record["messages"]:
            if m.get("role") == "user": q += str(m.get("content","")) + " "
            elif m.get("role") == "assistant": a += str(m.get("content","")) + " "
    return q.strip(), a.strip()

def judge_quality(question, answer):
    """LLM judge: is the answer correct, relevant, and coherent?"""
    try:
        with httpx.Client(timeout=30) as c:
            r = c.post(CODESTRAL_URL, headers={
                "Authorization": f"Bearer {CODESTRAL_KEY}",
                "Content-Type": "application/json",
            }, json={
                "model": "codestral-latest",
                "messages": [{"role": "user", "content": f"""Rate this Q&A pair on a scale 1-10.

Check for:
- Is the answer technically CORRECT? (not hallucinated values)
- Does the answer match the QUESTION? (not off-topic)
- Is the answer COMPLETE enough? (not a stub)
- Does it contain REAL component names, values, formulas? (not made up)

Question: {question[:500]}

Answer: {answer[:800]}

Reply ONLY with a JSON: {{"score": N, "issues": "brief description or none"}}"""}],
                "response_format": {"type": "json_object"},
                "temperature": 0.1,
                "max_tokens": 100,
            })
            r.raise_for_status()
            data = json.loads(r.json()["choices"][0]["message"]["content"])
            return data.get("score", 0), data.get("issues", "")
    except Exception as e:
        return 0, str(e)[:50]

# 1. Cross-dataset dedup check
print("=" * 60)
print("CROSS-DATASET DEDUP CHECK")
print("=" * 60)
global_hashes = {}
cross_dupes = []

for path in ALL_FILES:
    if not os.path.exists(path):
        continue
    name = os.path.basename(path)
    with open(path) as f:
        for i, line in enumerate(f):
            try:
                r = json.loads(line.strip())
                q, a = extract_qa(r)
                text = q + " " + a
                if len(text) < 50: continue
                h = hashlib.md5(text[:500].encode()).hexdigest()
                if h in global_hashes:
                    cross_dupes.append((name, global_hashes[h]))
                else:
                    global_hashes[h] = name
            except: pass

print(f"Cross-file duplicates found: {len(cross_dupes)}")
if cross_dupes:
    from collections import Counter
    pairs = Counter((a, b) for a, b in cross_dupes)
    for (a, b), count in pairs.most_common(10):
        print(f"  {a} <-> {b}: {count} dupes")

# 2. LLM judge on random samples
print(f"\n{'='*60}")
print(f"LLM JUDGE QUALITY CHECK ({SAMPLE_PER_DATASET} samples per dataset)")
print(f"{'='*60}")

results = {}
for path in ALL_FILES:
    if not os.path.exists(path):
        continue
    name = os.path.basename(path).replace("_audited","").replace("_cleaned","")

    # Load random samples
    lines = []
    with open(path) as f:
        all_lines = [l.strip() for l in f if l.strip()]
    
    if len(all_lines) < SAMPLE_PER_DATASET:
        samples = all_lines
    else:
        samples = random.sample(all_lines, SAMPLE_PER_DATASET)

    scores = []
    issues = []
    for line in samples:
        try:
            r = json.loads(line)
            q, a = extract_qa(r)
            if not q or not a or len(a) < 30:
                scores.append(0)
                issues.append("empty/stub answer")
                continue
            score, issue = judge_quality(q, a)
            scores.append(score)
            if issue and issue != "none": issues.append(issue)
        except: pass
    
    avg = sum(scores) / max(len(scores), 1)
    results[name] = {"avg_score": round(avg, 1), "samples": len(scores), "issues": issues[:3]}
    
    issue_str = "; ".join(issues[:2]) if issues else "none"
    print(f"  {name:<45} {avg:.1f}/10  issues: {issue_str[:80]}")

# 3. Summary
print(f"\n{'='*60}")
print("SUMMARY BY TIER")
print(f"{'='*60}")
for name, data in sorted(results.items(), key=lambda x: -x[1]["avg_score"]):
    tier = "A" if data["avg_score"] >= 7 else "B" if data["avg_score"] >= 5 else "C" if data["avg_score"] >= 3 else "D"
    print(f"  [{tier}] {name}: {data['avg_score']}/10")
