"""Prepare Continued Pre-Training (CPT) dataset from raw code.

Stage 1 of 3-stage pipeline: CPT -> SFT -> RLVR
CPT teaches the model the SYNTAX of Verilog, KiCad, SPICE, embedded C.
SFT teaches it to ANSWER questions.
RLVR teaches it to generate CORRECT code."""

import json
import os
import hashlib

BASE = "finetune/datasets"
HF = f"{BASE}/hf_imports"
OUTPUT = f"{BASE}/cpt_code_378k.jsonl"

# All raw code datasets
CODE_SOURCES = [
    # Verilog (360K+ modules)
    (f"{HF}/eda_verilog_200k.jsonl", "verilog", "code"),
    (f"{HF}/verilog_github.jsonl", "verilog", "text"),
    (f"{HF}/mg_verilog.jsonl", "verilog", "code"),
    (f"{HF}/verilogos_augmented.jsonl", "verilog", "code"),
    # RTL with instructions (keep as-is, model sees both)
    (f"{HF}/rtlcoder3.jsonl", "verilog", "instruction"),
    (f"{HF}/verireason_rtlcoder_reasoning.jsonl", "verilog", "instruction"),
    (f"{HF}/verireason_combined.jsonl", "verilog", "instruction"),
    # KiCad schematics (real .kicad_sch snippets)
    (f"{HF}/open_schematics.jsonl", "kicad", "open_schematics"),
    # Semiconductor (mixed text with code)
    (f"{HF}/semiconductor_instructions.jsonl", "semiconductor", "text"),
    (f"{HF}/semiconductor_chat.jsonl", "semiconductor", "conversations"),
]

seen = set()
total = 0
by_domain = {}


def extract_for_cpt(record, fmt, domain):
    """Extract text for continued pre-training.
    For CPT we want raw text/code, not Q&A format."""

    if fmt == "code":
        code = record.get("code", "")
        if not code or len(code) < 50:
            return None
        # For mg_verilog, include the summary as context
        summary = record.get("detailed_global_summary", "") or record.get(
            "block_summary", ""
        )
        header = record.get("module_header", "")
        if summary:
            return (
                f"// {summary}\n{header}\n{code}" if header else f"// {summary}\n{code}"
            )
        return code

    elif fmt == "text":
        text = record.get("text", "") or record.get("output", "")
        if not text or len(text) < 50:
            return None
        return text

    elif fmt == "instruction":
        inst = record.get("instruction", "")
        out = record.get("output", "")
        if not out or len(out) < 50:
            return None
        # Include instruction as comment, output as code
        tb = record.get("tb", "")  # testbench if available
        result = f"// Task: {inst[:200]}\n{out}"
        if tb:
            result += f"\n\n// Testbench:\n{tb}"
        return result

    elif fmt == "open_schematics":
        desc = record.get("description", "")
        name = record.get("name", "")
        comps = record.get("components_used") or []
        snippet = record.get("schematic_snippet", "") or ""
        json_struct = record.get("json_structure", "") or ""

        parts = []
        if name:
            parts.append(f"// KiCad Project: {name}")
        if desc:
            parts.append(f"// {desc[:300]}")
        if comps:
            parts.append(f"// Components: {', '.join(comps[:20])}")
        if snippet and len(snippet) > 50:
            parts.append(snippet[:2000])
        elif json_struct and len(json_struct) > 50:
            parts.append(json_struct[:2000])

        text = "\n".join(parts)
        return text if len(text) > 100 else None

    elif fmt == "conversations":
        # Extract all text from conversations
        parts = []
        for c in record.get("conversations", []):
            v = c.get("value", c.get("content", ""))
            if v:
                parts.append(v)
        text = "\n\n".join(parts)
        return text if len(text) > 100 else None

    return None


print("=== Prepare CPT Dataset (378K+ raw code) ===\n")

with open(OUTPUT, "w") as f:
    for path, domain, fmt in CODE_SOURCES:
        if not os.path.exists(path):
            print(f"SKIP {os.path.basename(path)}: not found")
            continue

        count = 0
        dupes = 0
        filtered = 0

        with open(path) as src:
            for line in src:
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue

                text = extract_for_cpt(record, fmt, domain)
                if not text:
                    filtered += 1
                    continue

                # Dedup
                h = hashlib.md5(text[:500].encode()).hexdigest()
                if h in seen:
                    dupes += 1
                    continue
                seen.add(h)

                # Quality: min length, max length
                if len(text) < 50:
                    filtered += 1
                    continue
                if len(text) > 50000:
                    text = text[:50000]  # Truncate very long files

                # Write as simple text for CPT
                f.write(
                    json.dumps(
                        {
                            "text": text,
                            "domain": domain,
                        },
                        ensure_ascii=False,
                    )
                    + "\n"
                )
                count += 1
                total += 1

        by_domain[domain] = by_domain.get(domain, 0) + count
        print(
            f"{os.path.basename(path)}: {count} kept, {dupes} dupes, {filtered} filtered"
        )

size_mb = os.path.getsize(OUTPUT) / 1024**2
print("\n=== CPT DATASET ===")
print(f"Total: {total} examples")
print(f"Size: {size_mb:.1f} MB")
print(f"Domains: {json.dumps(by_domain, indent=2)}")
print(f"Output: {OUTPUT}")
