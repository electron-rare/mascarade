#!/usr/bin/env python3
"""Build electronic components dataset for AI training."""

import json
from pathlib import Path


def build_components_dataset():
    """Build components dataset from various sources."""

    dataset_path = Path("finetune/datasets/components_chat.jsonl")

    # Sample dataset entries
    dataset_entries = [
        {
            "messages": [
                {
                    "role": "system",
                    "content": "You are an expert electronic components selector with deep knowledge of datasheets, availability, alternatives, and design considerations.",
                },
                {
                    "role": "user",
                    "content": "What are the best alternatives to LM317 voltage regulator?",
                },
                {
                    "role": "assistant",
                    "content": "Best LM317 alternatives: 1. LM338 (higher current, 5A vs 1.5A)\n2. LT1083 (low dropout, better regulation)\n3. LM7805 (fixed 5V, simpler)\n4. TPS7A4700 (modern, low noise)\n5. AMS1117 (SMD, low dropout)\nSelection criteria: current (1.5A max for LM317), dropout voltage, package (TO-220 vs SMD), noise requirements, and thermal considerations.",
                },
            ]
        },
        {
            "messages": [
                {
                    "role": "system",
                    "content": "You are an expert electronic components selector with deep knowledge of datasheets, availability, alternatives, and design considerations.",
                },
                {
                    "role": "user",
                    "content": "How to optimize component selection for JLCPCB assembly?",
                },
                {
                    "role": "assistant",
                    "content": "JLCPCB optimization: 1. Use JLCPCB basic parts library for lowest cost\n2. Prefer LCSC part numbers (C######)\n3. Check stock levels and lead times\n4. Standard footprints (0603, 0805, SOT-23)\n5. Avoid extended parts if possible\nExample: Use LM1117-3.3 (C28685) instead of generic AMS1117 for better availability and cost.",
                },
            ]
        },
        {
            "messages": [
                {
                    "role": "system",
                    "content": "You are an expert electronic components selector with deep knowledge of datasheets, availability, alternatives, and design considerations.",
                },
                {
                    "role": "user",
                    "content": "Generate a JLCPCB-optimized BOM for a buck converter.",
                },
                {
                    "role": "assistant",
                    "content": "Comment,Designator,Footprint,LCSC Part Number,Manufacturer,MPN,Quantity\nBuck Converter,U1,SOIC-8,C82086,TI,LM2596S-5.0/NOPB,1\nInductor,L1,4.7uH,C25606,Coilcraft,XAL6060-472MEC,1\nDiode,D1,DO-214AC,C35286,Diodes Inc,SB560-E3/57T,1\nCapacitor,C1,0805,C2286,Murata,GRM21BR71C106KA01L,1\nResistor,R1,0805,C1074,Yageo,RT0805FRE071KL,1",
                },
            ]
        },
    ]

    # Write dataset
    with open(dataset_path, "w", encoding="utf-8") as f:
        for entry in dataset_entries:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    print(f"Components dataset created at: {dataset_path}")
    print(f"Total entries: {len(dataset_entries)}")


if __name__ == "__main__":
    build_components_dataset()
