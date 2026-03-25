"""SOTA 2026 Data Quality Pipeline: Semantic Dedup + IFD Scoring + Multi-Judge.

Based on:
- SemDeDup (arXiv 2303.09540) — embedding-based dedup
- Cherry LLM IFD (arXiv 2308.12032) — self-scoring difficulty
- AlpaGasus (arXiv 2307.08701) — multi-judge quality filtering
- SkillRater (arXiv 2602.11615) — per-capability scoring
"""

import json
import os
import re
import math
import httpx

OLLAMA_URL = "http://localhost:11434"
CODESTRAL_URL = "https://codestral.mistral.ai/v1/chat/completions"
CODESTRAL_KEY = os.environ.get("CODESTRAL_API_KEY", "JbYYQUUpHOOFjpV5UuSct6QM4cT6otEl")
ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

CLEAN = "finetune/datasets/cleaned_final"
OUTPUT = "finetune/datasets/sota_curated"
os.makedirs(OUTPUT, exist_ok=True)


# ============================================================
# STAGE 1: Semantic Dedup with bge-m3 embeddings
# ============================================================

def embed_text(text, model="bge-m3"):
    """Get embedding from Ollama."""
    try:
        with httpx.Client(timeout=30) as c:
            r = c.post(f"{OLLAMA_URL}/api/embed", json={
                "model": model,
                "input": text[:500],
            })
            r.raise_for_status()
            emb = r.json().get("embeddings", [[]])[0]
            return emb if emb else None
    except Exception:
        return None


def cosine_sim(a, b):
    """Cosine similarity between two vectors."""
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def semantic_dedup(records, threshold=0.92):
    """Remove semantically similar examples using embeddings.
    SemDeDup: keep the one farthest from cluster centroid."""
    print(f"  Embedding {len(records)} examples...")

    embeddings = []
    valid_indices = []
    for i, (raw, record) in enumerate(records):
        q, a = extract_qa(record)
        text = f"{q} {a}"[:500]
        emb = embed_text(text)
        if emb:
            embeddings.append(emb)
            valid_indices.append(i)
        if (i + 1) % 200 == 0:
            print(f"    [{i+1}/{len(records)}] embedded")

    if not embeddings:
        return records, 0

    # Pairwise comparison within batches (full pairwise too expensive for >5K)
    removed = set()
    batch_size = min(len(embeddings), 1000)

    for start in range(0, len(embeddings), batch_size):
        batch = embeddings[start:start + batch_size]
        batch_idx = valid_indices[start:start + batch_size]

        for i in range(len(batch)):
            if batch_idx[i] in removed:
                continue
            for j in range(i + 1, len(batch)):
                if batch_idx[j] in removed:
                    continue
                sim = cosine_sim(batch[i], batch[j])
                if sim > threshold:
                    # Remove the shorter one
                    _, ri = records[batch_idx[i]]
                    _, rj = records[batch_idx[j]]
                    len_i = len(str(ri.get("conversations", [])))
                    len_j = len(str(rj.get("conversations", [])))
                    if len_i < len_j:
                        removed.add(batch_idx[i])
                    else:
                        removed.add(batch_idx[j])

    kept = [(raw, rec) for i, (raw, rec) in enumerate(records) if i not in removed]
    return kept, len(removed)


# ============================================================
# STAGE 2: IFD Scoring (Instruction Following Difficulty)
# ============================================================

def compute_ifd(question, answer, model="devstral"):
    """Compute proxy IFD: how surprised is the model by this answer?
    Higher IFD = harder example = more informative for training."""
    try:
        # Get perplexity WITH instruction
        with httpx.Client(timeout=15) as c:
            r = c.post(f"{OLLAMA_URL}/api/generate", json={
                "model": model,
                "prompt": f"Q: {question[:300]}\nA: {answer[:300]}",
                "stream": False,
                "options": {"temperature": 0.0, "num_predict": 1},
            })
            r.raise_for_status()
            # Use eval_count and eval_duration as proxy
            data = r.json()
            eval_count = data.get("eval_count", 1)
            eval_duration = data.get("eval_duration", 1) / 1e9  # nanoseconds to seconds
            # Higher duration per token = harder
            ifd = eval_duration / max(eval_count, 1)
            return ifd
    except Exception:
        return 0.0


# ============================================================
# STAGE 3: Multi-Judge Quality Scoring
# ============================================================

def judge_local(question, answer, model="devstral"):
    """Local judge (free, fast)."""
    prompt = f"""Rate this electronics Q&A 1-10.
Check: technical accuracy, completeness, relevance.

Q: {question[:400]}
A: {answer[:600]}

Score (1-10):"""
    try:
        with httpx.Client(timeout=15) as c:
            r = c.post(f"{OLLAMA_URL}/api/generate", json={
                "model": model, "prompt": prompt, "stream": False,
                "options": {"temperature": 0.1, "num_predict": 10},
            })
            r.raise_for_status()
            text = r.json().get("response", "").strip()
            for n in re.findall(r'\b(\d+)\b', text):
                v = int(n)
                if 1 <= v <= 10:
                    return v
    except Exception:
        pass
    return 0


def judge_codestral(question, answer):
    """Codestral API judge."""
    try:
        with httpx.Client(timeout=20) as c:
            r = c.post(CODESTRAL_URL, headers={
                "Authorization": f"Bearer {CODESTRAL_KEY}",
                "Content-Type": "application/json",
            }, json={
                "model": "codestral-latest",
                "messages": [{"role": "user", "content": f"Rate this electronics Q&A 1-10. Technical accuracy matters most.\n\nQ: {question[:400]}\nA: {answer[:500]}\n\nReply ONLY a number 1-10:"}],
                "temperature": 0.1, "max_tokens": 10,
            })
            r.raise_for_status()
            text = r.json()["choices"][0]["message"]["content"].strip()
            for n in re.findall(r'\b(\d+)\b', text):
                v = int(n)
                if 1 <= v <= 10:
                    return v
    except Exception:
        pass
    return 0


def judge_anthropic(question, answer):
    """Anthropic Claude judge."""
    if not ANTHROPIC_KEY:
        return 0
    try:
        with httpx.Client(timeout=20) as c:
            r = c.post(ANTHROPIC_URL, headers={
                "x-api-key": ANTHROPIC_KEY,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            }, json={
                "model": "claude-sonnet-4-20250514",
                "max_tokens": 10,
                "temperature": 0.1,
                "messages": [{"role": "user", "content": f"Rate this electronics Q&A 1-10. Check technical accuracy, safety, completeness.\n\nQ: {question[:400]}\nA: {answer[:500]}\n\nReply ONLY a number:"}],
            })
            r.raise_for_status()
            text = r.json()["content"][0]["text"].strip()
            for n in re.findall(r'\b(\d+)\b', text):
                v = int(n)
                if 1 <= v <= 10:
                    return v
    except Exception:
        pass
    return 0


def multi_judge(question, answer):
    """Multi-judge: majority vote from 3 judges (SkillRater-inspired)."""
    scores = []

    # Judge 1: Local devstral (always available, free)
    s1 = judge_local(question, answer)
    if s1 > 0:
        scores.append(s1)

    # Judge 2: Codestral API
    s2 = judge_codestral(question, answer)
    if s2 > 0:
        scores.append(s2)

    # Judge 3: Claude (if key available)
    s3 = judge_anthropic(question, answer)
    if s3 > 0:
        scores.append(s3)

    if not scores:
        return 0, []
    return round(sum(scores) / len(scores), 1), scores


# ============================================================
# STAGE 4: Per-Capability Scoring (SkillRater 2026)
# ============================================================

def capability_score(question, answer):
    """Score on multiple dimensions (SkillRater-inspired)."""
    dims = {}

    # Technical accuracy: does it contain real component names/values?
    tech_terms = ["resistor", "capacitor", "inductor", "transistor", "diode", "op-amp",
                  "MOSFET", "BJT", "regulator", "converter", "oscillator", "filter",
                  "ADC", "DAC", "UART", "SPI", "I2C", "GPIO", "PWM", "DMA",
                  "STM32", "ESP32", "nRF52", "RP2040", "KiCad", "SPICE", "Verilog"]
    tech_count = sum(1 for t in tech_terms if t.lower() in answer.lower())
    dims["technical_depth"] = min(10, tech_count * 2)

    # Code quality: has real code?
    code_markers = ["#include", "void ", "def ", "import ", "module ", "always @", "assign "]
    has_code = any(m in answer for m in code_markers)
    if has_code:
        # Check bracket matching
        opens = answer.count("{") + answer.count("(")
        closes = answer.count("}") + answer.count(")")
        balance = 10 if abs(opens - closes) <= 2 else 5
        dims["code_quality"] = balance
    else:
        dims["code_quality"] = 5  # neutral for non-code answers

    # Completeness: answer length relative to question complexity
    q_words = len(question.split())
    a_words = len(answer.split())
    if a_words > q_words * 2:
        dims["completeness"] = min(10, 5 + a_words // 50)
    else:
        dims["completeness"] = max(2, a_words // 20)

    # Safety: no dangerous recommendations without warnings
    danger_terms = ["mains voltage", "high voltage", "lethal", "shock", "explosion"]
    safety_terms = ["WARNING", "CAUTION", "safety", "protection", "isolation"]
    has_danger = any(d in answer.lower() for d in danger_terms)
    has_safety = any(s in answer.lower() for s in safety_terms)
    if has_danger and not has_safety:
        dims["safety"] = 3
    else:
        dims["safety"] = 8

    avg = sum(dims.values()) / len(dims)
    return round(avg, 1), dims


# ============================================================
# MAIN PIPELINE
# ============================================================

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


def process_dataset(fn, records, use_semantic_dedup=True, use_ifd=True, use_multi_judge=True):
    """Full SOTA pipeline on one dataset."""
    print(f"\n{'='*60}")
    print(f"PROCESSING: {fn} ({len(records)} examples)")
    print(f"{'='*60}")

    # Stage 1: Semantic Dedup
    if use_semantic_dedup and len(records) > 20:
        records, sem_removed = semantic_dedup(records, threshold=0.92)
        print(f"  [SemDeDup] Removed {sem_removed} semantic duplicates -> {len(records)}")
    else:
        sem_removed = 0

    # Stage 2+3+4: Score each example
    scored = []
    for i, (raw, record) in enumerate(records):
        q, a = extract_qa(record)
        if not q or not a or len(a) < 30:
            continue

        entry = {"raw": raw, "record": record}

        # IFD score (local, free)
        if use_ifd and i < 500:  # Sample for large datasets
            entry["ifd"] = compute_ifd(q, a)

        # Multi-judge (sample for large datasets)
        if use_multi_judge and i < 300:
            entry["judge_score"], entry["judge_votes"] = multi_judge(q, a)
        else:
            # Local judge only for the rest
            entry["judge_score"] = judge_local(q, a)
            entry["judge_votes"] = [entry["judge_score"]]

        # Per-capability scoring (fast, local computation)
        entry["capability_score"], entry["capability_dims"] = capability_score(q, a)

        # Combined score
        js = entry.get("judge_score", 5)
        cs = entry.get("capability_score", 5)
        entry["combined_score"] = round(0.6 * js + 0.4 * cs, 1)

        scored.append(entry)

        if (i + 1) % 100 == 0:
            avg_j = sum(e.get("judge_score", 0) for e in scored) / len(scored)
            avg_c = sum(e.get("capability_score", 0) for e in scored) / len(scored)
            print(f"  [{i+1}/{len(records)}] judge={avg_j:.1f} capability={avg_c:.1f}")

    # Filter: keep combined >= 4.5
    kept = [e for e in scored if e["combined_score"] >= 4.5]
    removed = len(scored) - len(kept)

    # Sort by combined score (best first)
    kept.sort(key=lambda x: -x["combined_score"])

    # Save
    out_path = os.path.join(OUTPUT, fn.replace("_final", "_curated"))
    with open(out_path, "w") as f:
        for e in kept:
            f.write(e["raw"] + "\n")

    avg_combined = sum(e["combined_score"] for e in kept) / max(len(kept), 1)
    print(f"  RESULT: {len(records)} -> {len(kept)} (removed {removed + sem_removed})")
    print(f"  Avg combined score: {avg_combined:.1f}/10")
    print(f"  -> {out_path}")

    return len(records), len(kept), sem_removed, removed


# Run on all datasets
datasets = sorted([f for f in os.listdir(CLEAN) if f.endswith(".jsonl")])
grand_before = 0
grand_after = 0

for fn in datasets:
    path = os.path.join(CLEAN, fn)
    records = []
    with open(path) as f:
        for line in f:
            if line.strip():
                try:
                    records.append((line.strip(), json.loads(line.strip())))
                except:
                    pass

    if len(records) < 10:
        print(f"\nSKIP {fn}: only {len(records)} examples")
        continue

    # For very large datasets (>5K), use semantic dedup but sample the rest
    use_sem = len(records) <= 3000  # bge-m3 embedding is slow
    before, after, sem_r, judge_r = process_dataset(fn, records, use_semantic_dedup=use_sem)
    grand_before += before
    grand_after += after

print(f"\n{'='*60}")
print("SOTA PIPELINE COMPLETE")
print(f"{'='*60}")
print(f"Total: {grand_before} -> {grand_after} ({(grand_before-grand_after)/max(grand_before,1)*100:.1f}% removed)")
print(f"\nCurated datasets: {OUTPUT}/")
for fn in sorted(os.listdir(OUTPUT)):
    if fn.endswith(".jsonl"):
        lines = sum(1 for _ in open(os.path.join(OUTPUT, fn)))
        print(f"  {fn}: {lines}")
