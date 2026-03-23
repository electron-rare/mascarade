"""Deep clean ALL training datasets: dedup, hallucinations, sanity, cross-file."""
import json, os, re, hashlib

BASE = "finetune/datasets"
FILES = [
    f"{BASE}/spice_chat.jsonl",
    f"{BASE}/ipc_jlcpcb_standards_cleaned.jsonl",
    f"{BASE}/emc_chat.jsonl",
    f"{BASE}/analog_audio_electronics_cleaned.jsonl",
    f"{BASE}/power_chat.jsonl",
    f"{BASE}/dsp_chat.jsonl",
    f"{BASE}/kicad10_features_cleaned.jsonl",
    f"{BASE}/embedded_systems_full_cleaned.jsonl",
    f"{BASE}/missing_domains_cleaned.jsonl",
    f"{BASE}/kicad_chat_v3_multi.jsonl",
]

PATTERNS = [
    (r"IPC-\d{5,}", "fake_ipc"),
    (r"(?:exactly|precisely)\s+\d+\.\d{3,}", "over_precise"),
    (r"https?://[^\s]{80,}", "long_url"),
    (r"KiCad\s+(?:11|12|13|14|15)", "future_kicad"),
    (r"IPC-(?:9999|0000|1111)", "fake_standard"),
    (r"JLCPCB.*0\.000", "impossible_precision"),
]
CRITICAL = {"refusal", "repetitive", "future_kicad", "fake_standard"}

global_hashes = set()
total_b = 0; total_a = 0; cross_d = 0

for path in FILES:
    if not os.path.exists(path):
        continue
    name = os.path.basename(path)
    kept = []; reasons = {}; before = 0; local_h = set()

    with open(path) as f:
        for line in f:
            before += 1
            line = line.strip()
            if not line: continue
            try: record = json.loads(line)
            except: reasons["bad_json"] = reasons.get("bad_json",0)+1; continue

            text = ""
            if "conversations" in record:
                for c in record["conversations"]:
                    v = c.get("value", c.get("content",""))
                    if v: text += v + " "
            elif "output" in record: text = str(record.get("instruction","")) + " " + str(record.get("output",""))
            elif "text" in record: text = str(record.get("text",""))
            else: text = " ".join(str(v)[:500] for v in record.values() if isinstance(v, str))

            if not text or len(text.strip()) < 30:
                reasons["short"] = reasons.get("short",0)+1; continue

            h = hashlib.md5(text[:500].encode()).hexdigest()
            if h in local_h: reasons["int_dupe"] = reasons.get("int_dupe",0)+1; continue
            local_h.add(h)
            if h in global_hashes: reasons["cross_dupe"] = reasons.get("cross_dupe",0)+1; cross_d += 1; continue
            global_hashes.add(h)

            flags = []
            for pat, reason in PATTERNS:
                if re.search(pat, text): flags.append(reason)

            sents = [s.strip() for s in text.split(". ") if len(s.strip()) > 20]
            if len(sents) > 4:
                starts = set(s[:25] for s in sents)
                if len(starts) < len(sents) * 0.4: flags.append("repetitive")

            if any(text.strip().startswith(r) for r in ["I'm sorry","I cannot","As an AI","I apologize"]): flags.append("refusal")

            if "conversations" in record:
                ql = sum(len(c.get("value","")) for c in record["conversations"] if c.get("from") in ("human","user"))
                al = sum(len(c.get("value","")) for c in record["conversations"] if c.get("from") in ("gpt","assistant"))
                if ql > 0 and al < ql * 0.15 and al < 80: flags.append("lazy")
                for c in record["conversations"]:
                    if c.get("from") in ("gpt","assistant"):
                        a = c.get("value","")
                        if a and a.count("...") > 5: flags.append("ellipsis")

            if flags:
                for fl in flags: reasons[fl] = reasons.get(fl,0)+1
                if len(flags) >= 2 or any(f in CRITICAL for f in flags): continue

            kept.append(line)

    with open(path, "w") as f:
        f.write("\n".join(kept) + "\n")

    removed = before - len(kept)
    total_b += before; total_a += len(kept)
    pct = removed/before*100 if before else 0
    print(f"{name}: {before} -> {len(kept)} (-{removed}, {pct:.1f}%)")
    if reasons:
        top = sorted(reasons.items(), key=lambda x:-x[1])[:5]
        print(f"  {dict(top)}")

print(f"\nTOTAL: {total_b} -> {total_a} (-{total_b-total_a}, {(total_b-total_a)/max(total_b,1)*100:.1f}%)")
print(f"Cross-file dupes: {cross_d}")
