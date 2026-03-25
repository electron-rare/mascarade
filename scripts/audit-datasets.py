"""Full audit of 7 unverified datasets."""
import json
import os
import re
import hashlib
from collections import Counter

FILES = [
    ("finetune/datasets/iot_chat.jsonl", "iot"),
    ("finetune/datasets/freecad_chat.jsonl", "freecad"),
    ("finetune/datasets/platformio_chat.jsonl", "platformio"),
    ("finetune/datasets/stm32_chat.jsonl", "stm32"),
    ("finetune/datasets/kicad_chat_v3_multi.jsonl", "kicad-v3"),
    ("finetune/datasets/hf_imports/rtlcoder3.jsonl", "rtlcoder3"),
    ("finetune/datasets/hf_imports/semiconductor_chat.jsonl", "semi-chat"),
]

HALLUC = [
    (r"IPC-\d{5,}", "fake_ipc"),
    (r"KiCad\s+(?:11|12|13|14|15)", "future_kicad"),
]
CRITICAL = {"refusal", "repetitive", "future_kicad", "fake_ipc"}

for path, label in FILES:
    if not os.path.exists(path):
        print(f"\n{label}: NOT FOUND"); continue

    total=0; valid=0; empty=0; short_c=0; dupes=0; removed=0
    hashes=set(); flags_all=Counter(); lengths=[]; has_code=0; kept=[]

    with open(path) as f:
        for line in f:
            total += 1
            line = line.strip()
            if not line: continue
            try: r = json.loads(line); valid += 1
            except: continue

            text = ""
            if "conversations" in r:
                for c in r["conversations"]:
                    v = c.get("value", c.get("content",""))
                    if v: text += v + " "
            elif "instruction" in r:
                text = str(r.get("instruction","")) + " " + str(r.get("output",""))
            elif "messages" in r:
                for m in r["messages"]: text += str(m.get("content","")) + " "
            else:
                text = " ".join(str(v)[:300] for v in r.values() if isinstance(v, str))

            if not text or len(text.strip()) < 30: empty += 1; continue
            if len(text) < 100: short_c += 1
            lengths.append(len(text))

            h = hashlib.md5(text[:500].encode()).hexdigest()
            if h in hashes: dupes += 1; continue
            hashes.add(h)

            code_markers = ["module ","always @","#include","void ","def ","import ","pinMode","Serial.","HAL_","esp_"]
            if any(m in text for m in code_markers): has_code += 1

            flags = []
            for pat, reason in HALLUC:
                if re.search(pat, text): flags.append(reason)
            sents = [s.strip() for s in text.split(". ") if len(s.strip()) > 20]
            if len(sents) > 4:
                starts = set(s[:25] for s in sents)
                if len(starts) < len(sents) * 0.4: flags.append("repetitive")
            refusals = ["I'm sorry","I cannot","As an AI","I apologize"]
            if any(text.strip().startswith(g) for g in refusals): flags.append("refusal")

            for fl in flags: flags_all[fl] += 1
            if len(flags) >= 2 or any(f in CRITICAL for f in flags):
                removed += 1; continue

            kept.append(line)

    avg_len = sum(lengths) // max(len(lengths), 1)
    dupe_pct = dupes / max(valid, 1) * 100
    code_pct = has_code / max(valid, 1) * 100

    print(f"\n{label}: {total} total, {valid} valid, {dupes} dupes ({dupe_pct:.0f}%), {removed} halluc, {len(kept)} KEPT")
    print(f"  Empty: {empty}, Short: {short_c}, Avg len: {avg_len}, Code: {code_pct:.0f}%")
    if flags_all: print(f"  Flags: {dict(flags_all)}")

    if dupe_pct > 30: print("  VERDICT: BAD — heavy dupes")
    elif removed > valid * 0.1: print("  VERDICT: MEDIOCRE — hallucinations")
    elif len(kept) < 100: print("  VERDICT: TOO SMALL")
    elif avg_len < 200: print("  VERDICT: SHALLOW — short answers")
    else: print("  VERDICT: GOOD")

    cleaned = path.replace(".jsonl", "_audited.jsonl")
    with open(cleaned, "w") as f:
        f.write("\n".join(kept) + "\n")
    print(f"  -> {cleaned}")
