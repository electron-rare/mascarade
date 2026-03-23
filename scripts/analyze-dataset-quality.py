"""Analyze quality of ALL datasets: length stats, format check, language, duplicates, domain coherence."""

import json
import os
import hashlib
from collections import Counter
import re

BASE = "/ai/saisail/mascarade/finetune/datasets"
HF = f"{BASE}/hf_imports"

# All datasets to analyze
DATASETS = []
for d in [BASE, HF]:
    if os.path.isdir(d):
        for f in sorted(os.listdir(d)):
            if f.endswith(".jsonl") and not f.startswith("mega_"):
                DATASETS.append(os.path.join(d, f))


def detect_language(text):
    """Simple language detection."""
    fr_words = {
        "est",
        "les",
        "des",
        "une",
        "pour",
        "dans",
        "avec",
        "sont",
        "pas",
        "qui",
        "vous",
        "nous",
    }
    zh_markers = re.findall(r"[\u4e00-\u9fff]", text[:500])
    if len(zh_markers) > 5:
        return "zh"
    words = set(text[:500].lower().split())
    if len(words & fr_words) > 3:
        return "fr"
    return "en"


def extract_text(record):
    """Extract main text from any format."""
    if "conversations" in record:
        return " ".join(
            c.get("value", c.get("content", ""))
            for c in record["conversations"]
            if c.get("value") or c.get("content")
        )
    if "text" in record:
        return record["text"]
    if "output" in record:
        return f"{record.get('instruction', '')} {record.get('input', '')} {record['output']}"
    if "code" in record:
        return str(record["code"])
    return " ".join(str(v)[:500] for v in record.values() if isinstance(v, str))


def has_code(text):
    """Detect if text contains code."""
    code_markers = [
        "def ",
        "class ",
        "import ",
        "include",
        "#define",
        "void ",
        "int ",
        "module ",
        "always @",
        "assign ",
        "wire ",
        "reg ",
        ".begin",
        ".end",
        "pinMode",
        "digitalWrite",
        "Serial.",
    ]
    return any(m in text for m in code_markers)


def quality_score(text):
    """Rate quality 0-10."""
    score = 0
    length = len(text)

    # Length scoring
    if length < 50:
        return 0
    if length > 100:
        score += 1
    if length > 200:
        score += 1
    if length > 500:
        score += 1
    if length > 1000:
        score += 1

    # Has substantive content (not just boilerplate)
    unique_words = len(set(text.lower().split()))
    if unique_words > 20:
        score += 1
    if unique_words > 50:
        score += 1

    # Has technical content
    tech_terms = [
        "voltage",
        "current",
        "resistor",
        "capacitor",
        "circuit",
        "signal",
        "frequency",
        "module",
        "register",
        "interrupt",
        "timer",
        "GPIO",
        "SPI",
        "I2C",
        "UART",
        "schematic",
        "PCB",
        "footprint",
        "netlist",
        "simulation",
        "SPICE",
        "KiCad",
        "STM32",
        "ESP32",
        "Arduino",
        "Verilog",
        "FPGA",
    ]
    tech_count = sum(1 for t in tech_terms if t.lower() in text.lower())
    if tech_count > 0:
        score += 1
    if tech_count > 3:
        score += 1

    # Has code
    if has_code(text):
        score += 1

    # Penalize garbage
    if text.count("...") > 5:
        score -= 2
    if len(text) > 50 and unique_words < 10:
        score -= 3

    return max(0, min(10, score))


def analyze_dataset(path):
    """Analyze a single dataset file."""
    name = os.path.basename(path)
    stats = {
        "name": name,
        "path": path,
        "total_lines": 0,
        "valid_json": 0,
        "invalid_json": 0,
        "empty_content": 0,
        "formats": Counter(),
        "languages": Counter(),
        "has_code": 0,
        "lengths": [],
        "quality_scores": [],
        "hashes": set(),
        "internal_dupes": 0,
        "domains": Counter(),
        "sample_good": [],
        "sample_bad": [],
    }

    with open(path) as f:
        for line in f:
            stats["total_lines"] += 1
            line = line.strip()
            if not line:
                continue

            try:
                record = json.loads(line)
                stats["valid_json"] += 1
            except json.JSONDecodeError:
                stats["invalid_json"] += 1
                continue

            # Detect format
            if "conversations" in record:
                stats["formats"]["conversations"] += 1
            elif "instruction" in record and "output" in record:
                stats["formats"]["instruction"] += 1
            elif "text" in record:
                stats["formats"]["text"] += 1
            elif "code" in record:
                stats["formats"]["code"] += 1
            elif "messages" in record:
                stats["formats"]["messages"] += 1
            else:
                stats["formats"]["other"] += 1

            # Extract text
            text = extract_text(record) or ""
            length = len(text)
            stats["lengths"].append(length)

            if length < 10:
                stats["empty_content"] += 1
                continue

            # Language
            stats["languages"][detect_language(text)] += 1

            # Code detection
            if has_code(text):
                stats["has_code"] += 1

            # Quality
            qs = quality_score(text)
            stats["quality_scores"].append(qs)

            # Internal dedup
            h = hashlib.md5(text[:500].encode()).hexdigest()
            if h in stats["hashes"]:
                stats["internal_dupes"] += 1
            stats["hashes"].add(h)

            # Domain
            if "domain" in record:
                stats["domains"][record["domain"]] += 1
            elif "category" in record:
                stats["domains"][record["category"]] += 1

            # Samples
            if qs >= 7 and len(stats["sample_good"]) < 2:
                stats["sample_good"].append(text[:200])
            if qs <= 2 and length > 10 and len(stats["sample_bad"]) < 2:
                stats["sample_bad"].append(text[:200])

    return stats


def main():
    print("=" * 80)
    print("DATASET QUALITY ANALYSIS")
    print("=" * 80)

    all_stats = []
    total_examples = 0
    total_quality = []

    for path in DATASETS:
        if not os.path.exists(path):
            continue
        stats = analyze_dataset(path)
        all_stats.append(stats)

    # Sort by quality
    for s in all_stats:
        if s["quality_scores"]:
            s["avg_quality"] = sum(s["quality_scores"]) / len(s["quality_scores"])
            s["median_length"] = (
                sorted(s["lengths"])[len(s["lengths"]) // 2] if s["lengths"] else 0
            )
            s["pct_good"] = (
                sum(1 for q in s["quality_scores"] if q >= 5)
                / len(s["quality_scores"])
                * 100
            )
            s["pct_code"] = s["has_code"] / max(s["valid_json"], 1) * 100
            s["dupe_pct"] = s["internal_dupes"] / max(s["valid_json"], 1) * 100
        else:
            s["avg_quality"] = 0
            s["median_length"] = 0
            s["pct_good"] = 0
            s["pct_code"] = 0
            s["dupe_pct"] = 0

    all_stats.sort(key=lambda x: -x["avg_quality"])

    # Print report
    print(
        f"\n{'Dataset':<45} {'Lines':>7} {'Valid':>7} {'Quality':>8} {'Good%':>6} {'Med.Len':>8} {'Code%':>6} {'Dupe%':>6} {'Lang':>5}"
    )
    print("-" * 120)

    for s in all_stats:
        lang = s["languages"].most_common(1)[0][0] if s["languages"] else "?"
        print(
            f"{s['name']:<45} {s['total_lines']:>7} {s['valid_json']:>7} {s['avg_quality']:>7.1f}/10 {s['pct_good']:>5.1f}% {s['median_length']:>7} {s['pct_code']:>5.1f}% {s['dupe_pct']:>5.1f}% {lang:>5}"
        )
        total_examples += s["valid_json"]
        total_quality.extend(s["quality_scores"])

    # Summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Total datasets: {len(all_stats)}")
    print(f"Total examples: {total_examples}")
    if total_quality:
        avg_q = sum(total_quality) / len(total_quality)
        good_pct = sum(1 for q in total_quality if q >= 5) / len(total_quality) * 100
        print(f"Average quality: {avg_q:.1f}/10")
        print(f"Good quality (>=5): {good_pct:.1f}%")

    # Quality tiers
    print(f"\n{'Tier':<20} {'Datasets':>10} {'Description'}")
    print("-" * 60)
    tier_a = [s for s in all_stats if s["avg_quality"] >= 6]
    tier_b = [s for s in all_stats if 4 <= s["avg_quality"] < 6]
    tier_c = [s for s in all_stats if 2 <= s["avg_quality"] < 4]
    tier_d = [s for s in all_stats if s["avg_quality"] < 2]
    print(f"{'A (>=6/10)':<20} {len(tier_a):>10} High quality, ready for finetune")
    print(f"{'B (4-6/10)':<20} {len(tier_b):>10} Usable, may need filtering")
    print(f"{'C (2-4/10)':<20} {len(tier_c):>10} Low quality, needs heavy filtering")
    print(f"{'D (<2/10)':<20} {len(tier_d):>10} Not usable as-is")

    # Recommendations
    print(f"\n{'='*80}")
    print("RECOMMENDATIONS")
    print(f"{'='*80}")
    print("\nTier A — Use directly:")
    for s in tier_a:
        print(f"  {s['name']} ({s['valid_json']} examples, {s['avg_quality']:.1f}/10)")
    print("\nTier B — Filter to quality >= 5:")
    for s in tier_b:
        print(f"  {s['name']} ({s['valid_json']} examples, {s['avg_quality']:.1f}/10)")
    print("\nTier C — Heavy filtering or skip:")
    for s in tier_c:
        print(f"  {s['name']} ({s['valid_json']} examples, {s['avg_quality']:.1f}/10)")
    if tier_d:
        print("\nTier D — Skip:")
        for s in tier_d:
            print(
                f"  {s['name']} ({s['valid_json']} examples, {s['avg_quality']:.1f}/10)"
            )

    # Save detailed report
    report = {
        "total_datasets": len(all_stats),
        "total_examples": total_examples,
        "avg_quality": round(avg_q, 2) if total_quality else 0,
        "datasets": [
            {
                "name": s["name"],
                "lines": s["total_lines"],
                "valid": s["valid_json"],
                "invalid_json": s["invalid_json"],
                "empty": s["empty_content"],
                "avg_quality": round(s["avg_quality"], 2),
                "pct_good": round(s["pct_good"], 1),
                "median_length": s["median_length"],
                "pct_code": round(s["pct_code"], 1),
                "internal_dupes_pct": round(s["dupe_pct"], 1),
                "formats": dict(s["formats"]),
                "languages": dict(s["languages"]),
                "domains": dict(s["domains"].most_common(5)),
                "sample_good": s["sample_good"],
                "sample_bad": s["sample_bad"],
            }
            for s in all_stats
        ],
    }

    report_path = f"{BASE}/QUALITY_ANALYSIS.json"
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print(f"\nDetailed report: {report_path}")


if __name__ == "__main__":
    main()
