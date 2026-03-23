"""Clean hallucinations from Codestral-generated datasets."""

import json
import os
import re

BASE = os.environ.get("BASE", "finetune/datasets")

HALLUCINATION_PATTERNS = [
    (r"IPC-\d{5,}", "fake_ipc_number"),
    (r"(?:exactly|precisely)\s+\d+\.\d{3,}", "over_precise_value"),
    (r"(?:Go to|Navigate to|Open)\s+'[^']{50,}'", "invented_menu_path"),
    (
        r"(?:must be|should be|is)\s+exactly\s+\d+(?:\.\d+)?\s*(?:mm|mil|ohm|V|A|Hz|dB)",
        "suspiciously_exact_spec",
    ),
]

datasets = [
    (f"{BASE}/ipc_jlcpcb_standards.jsonl", "ipc_gen"),
    (f"{BASE}/kicad10_features.jsonl", "kicad10_gen"),
    (f"{BASE}/analog_audio_electronics.jsonl", "analog_gen"),
    (f"{BASE}/embedded_systems_full.jsonl", "embedded_gen"),
    (f"{BASE}/missing_domains.jsonl", "missing_gen"),
]

for path, label in datasets:
    if not os.path.exists(path):
        continue

    total = 0
    flagged = 0
    removed = 0
    kept = []
    reasons = {}

    with open(path) as f:
        for line in f:
            total += 1
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                removed += 1
                continue

            text = ""
            if "conversations" in record:
                for c in record["conversations"]:
                    if c.get("from") in ("gpt", "assistant"):
                        text += c.get("value", "") + " "

            if not text or len(text) < 50:
                removed += 1
                continue

            flags = []
            for pattern, reason in HALLUCINATION_PATTERNS:
                if re.search(pattern, text):
                    flags.append(reason)

            # Repetitive content
            sentences = text.split(". ")
            if len(sentences) > 3:
                unique = set(s[:30] for s in sentences if len(s) > 30)
                if len(unique) < len(sentences) * 0.5:
                    flags.append("repetitive")

            # Generic refusal
            if any(
                text.strip().startswith(g)
                for g in ["I'm sorry", "I cannot", "As an AI"]
            ):
                flags.append("refusal")

            # Answer too short
            question = ""
            for c in record.get("conversations", []):
                if c.get("from") in ("human", "user"):
                    question = c.get("value", "")
            if question and len(text) < len(question) * 0.3:
                flags.append("too_short")

            if flags:
                flagged += 1
                for fl in flags:
                    reasons[fl] = reasons.get(fl, 0) + 1
                if len(flags) >= 2 or "refusal" in flags or "repetitive" in flags:
                    removed += 1
                    continue

            kept.append(line)

    out = path.replace(".jsonl", "_cleaned.jsonl")
    with open(out, "w") as f:
        f.write("\n".join(kept) + "\n")

    print(
        f"{label}: {total} total, {flagged} flagged, {removed} removed, {len(kept)} kept"
    )
    if reasons:
        print(f"  Flags: {reasons}")
    print(f"  Output: {out}")
