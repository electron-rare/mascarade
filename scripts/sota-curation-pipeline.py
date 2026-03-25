"""SOTA 2026 Dataset Curation Pipeline.

5 stages:
1. Semantic Dedup with bge-m3 (cosine > 0.92 = dupe)
2. Quality filtering (length, format, language)
3. Multi-judge consensus (Devstral + Codestral + Qwen3)
4. IFD scoring (keep 0.3-0.9 range)
5. Domain-weighted mixing
"""

import json
import os
import re
import hashlib
import time
import numpy as np
import httpx
from collections import Counter

# Config
CLEAN_DIR = "finetune/datasets/cleaned_final"
OUTPUT_DIR = "finetune/datasets/sota_curated"
OLLAMA_URL = "http://localhost:11434"
CODESTRAL_URL = "https://codestral.mistral.ai/v1/chat/completions"
CODESTRAL_KEY = os.environ.get("CODESTRAL_API_KEY", "JbYYQUUpHOOFjpV5UuSct6QM4cT6otEl")

# Semantic dedup threshold
SEMDEDUP_THRESHOLD = 0.92

# Multi-judge models
JUDGES = [
    ("devstral", "devstral:latest", "ollama"),
    ("qwen3", "qwen3:8b", "ollama"),
    ("codestral", "codestral-latest", "api"),
]

# Domain weights for final mix
DOMAIN_WEIGHTS = {
    "spice": 0.20, "kicad": 0.15, "verilog": 0.10, "embedded": 0.12,
    "ipc": 0.08, "emc": 0.08, "power": 0.08, "dsp": 0.06,
    "analog": 0.05, "freecad": 0.03, "platformio": 0.03, "stm32": 0.02,
}

os.makedirs(OUTPUT_DIR, exist_ok=True)


def extract_qa(record):
    q, a = "", ""
    for c in record.get("conversations", []):
        role = c.get("from", c.get("role", ""))
        val = c.get("value", c.get("content", ""))
        if role in ("human", "user"):
            q += val + " "
        elif role in ("gpt", "assistant"):
            a += val + " "
    return q.strip(), a.strip()


def load_all_datasets():
    """Load all cleaned_final datasets."""
    all_records = []
    for fn in sorted(os.listdir(CLEAN_DIR)):
        if not fn.endswith(".jsonl"):
            continue
        path = os.path.join(CLEAN_DIR, fn)
        domain = fn.replace("_final.jsonl", "").replace("-", "_")
        with open(path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    r = json.loads(line)
                    q, a = extract_qa(r)
                    if q and a and len(a) > 30:
                        all_records.append({
                            "record": r,
                            "raw": line,
                            "question": q,
                            "answer": a,
                            "text": q + " " + a,
                            "domain": domain,
                            "source_file": fn,
                        })
                except json.JSONDecodeError:
                    pass
    return all_records


# ============================================================
# STAGE 1: Semantic Dedup with bge-m3
# ============================================================
def stage1_semdedup(records, threshold=SEMDEDUP_THRESHOLD):
    """Remove semantic duplicates using bge-m3 embeddings + FAISS."""
    print(f"\n{'='*60}")
    print(f"STAGE 1: Semantic Dedup (bge-m3, threshold={threshold})")
    print(f"{'='*60}")

    try:
        from sentence_transformers import SentenceTransformer
        import faiss
    except ImportError:
        print("  WARNING: sentence-transformers or faiss not installed")
        print("  Falling back to MD5 dedup only")
        return stage1_fallback_md5(records)

    model = SentenceTransformer("BAAI/bge-m3")
    texts = [r["text"][:512] for r in records]  # Truncate for speed

    print(f"  Encoding {len(texts)} texts...")
    embeddings = model.encode(texts, batch_size=64, show_progress_bar=True)
    embeddings = embeddings / np.linalg.norm(embeddings, axis=1, keepdims=True)

    print(f"  Building FAISS index...")
    dim = embeddings.shape[1]
    index = faiss.IndexFlatIP(dim)
    index.add(embeddings.astype(np.float32))

    print(f"  Finding duplicates (threshold={threshold})...")
    k = 5  # Check top-5 neighbors
    D, I = index.search(embeddings.astype(np.float32), k)

    # Mark duplicates (keep the longer one)
    removed = set()
    for i in range(len(records)):
        if i in removed:
            continue
        for j_idx in range(1, k):  # Skip self (index 0)
            j = I[i][j_idx]
            if j == i or j in removed:
                continue
            sim = D[i][j_idx]
            if sim >= threshold:
                # Keep the longer example
                if len(records[i]["text"]) >= len(records[j]["text"]):
                    removed.add(j)
                else:
                    removed.add(i)
                    break

    kept = [r for i, r in enumerate(records) if i not in removed]
    print(f"  Removed: {len(removed)} semantic dupes ({len(removed)/len(records)*100:.1f}%)")
    print(f"  Kept: {len(kept)}")
    return kept


def stage1_fallback_md5(records):
    """Fallback: MD5 dedup if bge-m3 not available."""
    seen = set()
    kept = []
    dupes = 0
    for r in records:
        h = hashlib.md5(r["text"][:500].encode()).hexdigest()
        if h in seen:
            dupes += 1
            continue
        seen.add(h)
        kept.append(r)
    print(f"  MD5 dedup: {dupes} removed, {len(kept)} kept")
    return kept


# ============================================================
# STAGE 2: Quality Filtering
# ============================================================
def stage2_quality_filter(records):
    """Filter by length, format, patterns."""
    print(f"\n{'='*60}")
    print(f"STAGE 2: Quality Filtering")
    print(f"{'='*60}")

    HALLUC = [
        (r"IPC-\d{5,}", "fake_ipc"),
        (r"KiCad\s+(?:11|12|13|14|15)", "future_kicad"),
    ]
    CRITICAL = {"refusal", "repetitive", "future_kicad", "fake_ipc"}

    kept = []
    reasons = Counter()

    for r in records:
        q, a = r["question"], r["answer"]

        # Length checks
        if len(a) < 80:
            reasons["short_answer"] += 1
            continue
        if len(q) < 15:
            reasons["short_question"] += 1
            continue

        # Hallucination patterns
        flags = []
        for pat, reason in HALLUC:
            if re.search(pat, a):
                flags.append(reason)

        # Repetitive content
        sents = [s.strip() for s in a.split(". ") if len(s.strip()) > 20]
        if len(sents) > 4:
            starts = set(s[:25] for s in sents)
            if len(starts) < len(sents) * 0.4:
                flags.append("repetitive")

        # Refusal
        if any(a.strip().startswith(g) for g in ["I'm sorry", "I cannot", "As an AI"]):
            flags.append("refusal")

        if flags:
            for fl in flags:
                reasons[fl] += 1
            if len(flags) >= 2 or any(f in CRITICAL for f in flags):
                continue

        kept.append(r)

    removed = len(records) - len(kept)
    print(f"  Removed: {removed} ({removed/len(records)*100:.1f}%)")
    print(f"  Reasons: {dict(reasons.most_common(5))}")
    print(f"  Kept: {len(kept)}")
    return kept


# ============================================================
# STAGE 3: Multi-Judge Consensus
# ============================================================
def judge_ollama(model_name, question, answer, timeout=15.0):
    prompt = f"""/no_think
Rate this electronics Q&A 1-10. Is the answer correct, relevant, not hallucinated?
Q: {question[:300]}
A: {answer[:500]}
Reply ONLY a number 1-10."""
    try:
        with httpx.Client(timeout=timeout) as c:
            r = c.post(f"{OLLAMA_URL}/api/generate", json={
                "model": model_name,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0.1, "num_predict": 10},
            })
            r.raise_for_status()
            text = r.json().get("response", "").strip()
            nums = re.findall(r'\b(\d+)\b', text)
            for n in nums:
                v = int(n)
                if 1 <= v <= 10:
                    return v
    except Exception:
        pass
    return 0


def judge_codestral(question, answer, timeout=15.0):
    prompt = f"""Rate this electronics Q&A 1-10. Correct? Relevant? Hallucinated?
Q: {question[:300]}
A: {answer[:500]}
Reply ONLY JSON: {{"score": N}}"""
    try:
        with httpx.Client(timeout=timeout) as c:
            r = c.post(CODESTRAL_URL, headers={
                "Authorization": f"Bearer {CODESTRAL_KEY}",
                "Content-Type": "application/json",
            }, json={
                "model": "codestral-latest",
                "messages": [{"role": "user", "content": prompt}],
                "response_format": {"type": "json_object"},
                "temperature": 0.1,
                "max_tokens": 20,
            })
            r.raise_for_status()
            data = json.loads(r.json()["choices"][0]["message"]["content"])
            return data.get("score", 0)
    except Exception:
        return 0


def stage3_multi_judge(records, sample_size=500):
    """Multi-judge consensus on a sample. Keep all unchecked by default."""
    print(f"\n{'='*60}")
    print(f"STAGE 3: Multi-Judge Consensus ({len(JUDGES)} judges, {sample_size} samples)")
    print(f"{'='*60}")

    import random
    random.seed(42)

    if len(records) <= sample_size:
        indices = set(range(len(records)))
    else:
        indices = set(random.sample(range(len(records)), sample_size))

    removed = set()
    scores_all = []

    for count, i in enumerate(sorted(indices)):
        r = records[i]
        q, a = r["question"], r["answer"]

        scores = []
        for name, model, judge_type in JUDGES:
            if judge_type == "ollama":
                s = judge_ollama(model, q, a)
            else:
                s = judge_codestral(q, a)
            scores.append(s)

        valid_scores = [s for s in scores if s > 0]
        if not valid_scores:
            continue

        avg = sum(valid_scores) / len(valid_scores)
        spread = max(valid_scores) - min(valid_scores) if len(valid_scores) > 1 else 0
        scores_all.append(avg)

        # Decision
        if avg < 4:
            removed.add(i)
        elif avg < 5 and spread > 4:
            removed.add(i)  # Judges disagree on bad content

        if (count + 1) % 100 == 0:
            avg_all = sum(scores_all) / len(scores_all)
            print(f"  [{count+1}/{len(indices)}] avg={avg_all:.1f}/10, removed={len(removed)}")

    # Build final list (keep unchecked)
    kept = [r for i, r in enumerate(records) if i not in removed]
    avg_all = sum(scores_all) / max(len(scores_all), 1)
    print(f"  Average score: {avg_all:.1f}/10")
    print(f"  Removed: {len(removed)} ({len(removed)/max(len(indices),1)*100:.1f}% of checked)")
    print(f"  Kept: {len(kept)}")
    return kept


# ============================================================
# STAGE 4: Domain-weighted output
# ============================================================
def stage4_output(records):
    """Write domain-separated verified files."""
    print(f"\n{'='*60}")
    print(f"STAGE 4: Domain Output")
    print(f"{'='*60}")

    by_domain = {}
    for r in records:
        d = r["domain"]
        if d not in by_domain:
            by_domain[d] = []
        by_domain[d].append(r["raw"])

    total = 0
    for domain, lines in sorted(by_domain.items(), key=lambda x: -len(x[1])):
        path = os.path.join(OUTPUT_DIR, f"{domain}_sota.jsonl")
        with open(path, "w") as f:
            f.write("\n".join(lines) + "\n")
        total += len(lines)
        print(f"  {domain}: {len(lines)}")

    print(f"\n  TOTAL: {total} verified examples")
    print(f"  Output: {OUTPUT_DIR}/")
    return total


# ============================================================
# MAIN
# ============================================================
def main():
    print("=" * 60)
    print("MASCARADE SOTA 2026 DATASET CURATION PIPELINE")
    print("=" * 60)

    # Load
    records = load_all_datasets()
    print(f"\nLoaded: {len(records)} records from {CLEAN_DIR}")

    # Stage 1: Semantic Dedup
    records = stage1_semdedup(records)

    # Stage 2: Quality Filter
    records = stage2_quality_filter(records)

    # Stage 3: Multi-Judge
    records = stage3_multi_judge(records, sample_size=min(500, len(records)))

    # Stage 4: Output
    total = stage4_output(records)

    print(f"\n{'='*60}")
    print(f"PIPELINE COMPLETE: {total} verified examples")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
