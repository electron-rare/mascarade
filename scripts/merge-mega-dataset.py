"""Merge all datasets into mega v2 with dedup, quality filter, and domain tagging."""

import json
import os
import hashlib
from collections import defaultdict

BASE = "/ai/saisail/mascarade/finetune/datasets"
HF = f"{BASE}/hf_imports"
OUTPUT = f"{BASE}/mega_v2_all_electronics.jsonl"
STATS_FILE = f"{BASE}/mega_v2_stats.json"

# Dataset definitions: (path, domain, format_handler)
DATASETS = [
    # Our generated datasets (conversations format)
    (f"{BASE}/kicad_chat.jsonl", "kicad", "conversations"),
    (f"{BASE}/spice_chat.jsonl", "spice", "conversations"),
    (f"{BASE}/embedded_chat.jsonl", "embedded", "conversations"),
    (f"{BASE}/platformio_chat.jsonl", "platformio", "conversations"),
    (f"{BASE}/stm32_chat.jsonl", "stm32", "conversations"),
    (f"{BASE}/emc_chat.jsonl", "emc", "conversations"),
    (f"{BASE}/dsp_chat.jsonl", "dsp", "conversations"),
    (f"{BASE}/iot_chat.jsonl", "iot", "conversations"),
    (f"{BASE}/power_chat.jsonl", "power", "conversations"),
    (f"{BASE}/freecad_chat.jsonl", "freecad", "conversations"),
    (f"{BASE}/components_chat.jsonl", "components", "conversations"),
    # Generated via Codestral
    (f"{BASE}/ipc_jlcpcb_standards.jsonl", "ipc-standards", "conversations"),
    (f"{BASE}/kicad10_features.jsonl", "kicad-10", "conversations"),
    (f"{BASE}/analog_audio_electronics.jsonl", "analog-audio", "conversations"),
    # HuggingFace imports
    (f"{HF}/stem_ai_electrical_engineering.jsonl", "kicad", "instruction"),
    (f"{HF}/cjjones_ee_synthetic_dialog.jsonl", "ee-general", "text"),
    (f"{HF}/circuit_theory.jsonl", "circuit-theory", "text"),
    (f"{HF}/open_schematics.jsonl", "kicad-schematics", "open_schematics"),
    (f"{HF}/verireason_rtlcoder_reasoning.jsonl", "verilog-reasoning", "raw"),
    (f"{HF}/expanded_rtlcoder_12k.jsonl", "verilog", "raw"),
    (f"{HF}/mg_verilog.jsonl", "verilog", "raw"),
    (f"{HF}/verilogos_augmented.jsonl", "verilog", "raw"),
    (f"{HF}/rtl_verilog_claude_verified.jsonl", "verilog-verified", "raw"),
    (f"{HF}/eda_verilog_200k.jsonl", "verilog-eda", "raw"),
    (f"{HF}/verilog_github.jsonl", "verilog-github", "raw"),
    (f"{HF}/simple_circuit_schematic.jsonl", "circuit-theory", "raw"),
]


def content_hash(text: str) -> str:
    return hashlib.md5(text[:500].encode()).hexdigest()


def extract_text(record: dict, fmt: str) -> str:
    """Extract main text content for dedup and quality check."""
    if fmt == "conversations":
        convs = record.get("conversations", [])
        return " ".join(c.get("value", c.get("content", "")) for c in convs)
    elif fmt == "instruction":
        return f"{record.get('instruction', '')} {record.get('input', '')} {record.get('output', '')}"
    elif fmt == "text":
        return record.get("text", "")
    elif fmt == "open_schematics":
        return f"{record.get('description', '')} {record.get('name', '')} {' '.join(record.get('components_used', []))}"
    else:  # raw
        return " ".join(str(v)[:500] for v in record.values() if isinstance(v, str))


def to_unified(record: dict, fmt: str, domain: str) -> dict | None:
    """Convert to unified format."""
    if fmt == "conversations":
        convs = record.get("conversations", [])
        if len(convs) < 2:
            return None
        return {"conversations": convs, "domain": record.get("domain", domain), "source": record.get("source", "mascarade")}

    elif fmt == "instruction":
        instruction = record.get("instruction", "")
        inp = record.get("input", "")
        out = record.get("output", "")
        if not out or len(out) < 20:
            return None
        convs = []
        if instruction:
            convs.append({"from": "system", "value": instruction})
        convs.append({"from": "human", "value": inp})
        convs.append({"from": "gpt", "value": out})
        return {"conversations": convs, "domain": domain, "source": "huggingface"}

    elif fmt == "text":
        text = record.get("text", "").strip()
        if not text or len(text) < 100:
            return None
        # Try to split into Q&A
        if "Human:" in text and "Assistant:" in text:
            convs = []
            for part in text.split("Human:"):
                part = part.strip()
                if not part:
                    continue
                if "Assistant:" in part:
                    h, a = part.split("Assistant:", 1)
                    if h.strip():
                        convs.append({"from": "human", "value": h.strip()})
                    if a.strip():
                        convs.append({"from": "gpt", "value": a.strip()})
            if len(convs) >= 2:
                return {"conversations": convs, "domain": domain, "source": "huggingface"}
        return {"conversations": [{"from": "human", "value": text}], "domain": domain, "source": "huggingface"}

    elif fmt == "open_schematics":
        desc = record.get("description", "")
        name = record.get("name", "")
        comps = record.get("components_used", [])
        snippet = record.get("schematic_snippet", "")
        json_struct = record.get("json_structure", "")
        if not desc or len(desc) < 20:
            return None
        question = f"Describe the KiCad schematic project '{name}'. What components are used and what is its purpose?"
        answer = f"{desc}\n\nComponents used: {', '.join(comps[:20])}"
        if snippet:
            answer += f"\n\nSchematic structure (KiCad format):\n{snippet[:500]}"
        return {
            "conversations": [
                {"from": "system", "value": "You are an expert KiCad schematic analyst."},
                {"from": "human", "value": question},
                {"from": "gpt", "value": answer},
            ],
            "domain": domain,
            "source": "open-schematics",
        }

    else:  # raw — keep as-is with domain tag
        text = extract_text(record, "raw")
        if len(text) < 50:
            return None
        # Try to find question/answer or instruction/output pattern
        for q_key in ["question", "prompt", "instruction", "input", "nl", "evolved_nl"]:
            if q_key in record and record[q_key]:
                q = str(record[q_key])
                for a_key in ["answer", "response", "output", "code", "rtl"]:
                    if a_key in record and record[a_key]:
                        a = str(record[a_key])
                        if len(a) > 20:
                            return {
                                "conversations": [
                                    {"from": "human", "value": q},
                                    {"from": "gpt", "value": a},
                                ],
                                "domain": domain,
                                "source": "huggingface",
                            }
        # Single text field (code datasets)
        if "code" in record:
            return {
                "conversations": [
                    {"from": "human", "value": "Explain or complete this code:"},
                    {"from": "gpt", "value": str(record["code"])[:2000]},
                ],
                "domain": domain,
                "source": "huggingface",
            }
        return None


def main():
    print("=== Mega Dataset v2 Merger ===\n")

    seen = set()
    stats = defaultdict(lambda: {"total": 0, "kept": 0, "dupes": 0, "filtered": 0})
    all_records = []

    for path, domain, fmt in DATASETS:
        if not os.path.exists(path):
            print(f"SKIP {os.path.basename(path)} (not found)")
            continue

        name = os.path.basename(path)
        count = 0
        dupes = 0
        filtered = 0

        with open(path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue

                stats[name]["total"] += 1

                # Convert to unified format
                unified = to_unified(record, fmt, domain)
                if not unified:
                    filtered += 1
                    stats[name]["filtered"] += 1
                    continue

                # Dedup
                text = extract_text(unified, "conversations")
                h = content_hash(text)
                if h in seen:
                    dupes += 1
                    stats[name]["dupes"] += 1
                    continue
                seen.add(h)

                # Quality: min text length
                if len(text) < 50:
                    filtered += 1
                    stats[name]["filtered"] += 1
                    continue

                all_records.append(unified)
                count += 1
                stats[name]["kept"] += 1

        print(f"{name}: {count} kept, {dupes} dupes, {filtered} filtered")

    # Write output
    with open(OUTPUT, "w") as f:
        for rec in all_records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    # Domain breakdown
    domains = defaultdict(int)
    sources = defaultdict(int)
    for rec in all_records:
        domains[rec.get("domain", "unknown")] += 1
        sources[rec.get("source", "unknown")] += 1

    summary = {
        "total_examples": len(all_records),
        "total_unique_hashes": len(seen),
        "file_size_mb": round(os.path.getsize(OUTPUT) / 1024**2, 1),
        "domains": dict(sorted(domains.items(), key=lambda x: -x[1])),
        "sources": dict(sorted(sources.items(), key=lambda x: -x[1])),
        "per_file": {k: dict(v) for k, v in stats.items()},
    }

    with open(STATS_FILE, "w") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    print(f"\n=== MEGA DATASET v2 ===")
    print(f"Total: {len(all_records)} examples")
    print(f"Size: {summary['file_size_mb']} MB")
    print(f"\nDomains:")
    for d, c in sorted(domains.items(), key=lambda x: -x[1]):
        print(f"  {d}: {c}")
    print(f"\nSources:")
    for s, c in sorted(sources.items(), key=lambda x: -x[1]):
        print(f"  {s}: {c}")
    print(f"\nOutput: {OUTPUT}")
    print(f"Stats: {STATS_FILE}")


if __name__ == "__main__":
    main()
