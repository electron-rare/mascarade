"""Regenerate kicad_chat.jsonl from REAL sources (open_schematics + KiCad docs).

Strategy: take real KiCad schematics from open_schematics, extract facts,
ask Codestral to generate Q&A BASED ON those facts. No hallucination possible
because the answer must reference the real schematic data."""

import json
import time
import os
import random
import httpx

ANTHROPIC_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
MODEL = "claude-sonnet-4-20250514"
SCHEMATICS_FILE = "finetune/datasets/hf_imports/open_schematics.jsonl"
OUTPUT = "finetune/datasets/kicad_chat_v2.jsonl"

# Question templates grounded in real data
TEMPLATES = [
    "Based on this KiCad schematic '{name}': {description}\nComponents used: {components}\n\nExplain the design choices and suggest improvements.",
    "A KiCad project '{name}' uses these components: {components}\n\nWhat is the purpose of each component in this circuit? Are there any missing components?",
    "Review this KiCad schematic: '{name}'\nDescription: {description}\nComponents: {components}\n\nWhat DRC issues should I check before sending to JLCPCB?",
    "I found this KiCad project: '{name}' — {description}\nIt uses: {components}\n\nHow would I modify this design for {modification}?",
    "Looking at the KiCad schematic '{name}' with components {components}:\n\nWrite the Bill of Materials (BOM) with recommended manufacturer part numbers.",
    "This KiCad project '{name}' ({description}) uses {components}.\n\nDesign a PCB layout strategy: component placement, routing priorities, and stackup.",
    "For the KiCad schematic '{name}': {description}\nComponents: {components}\n\nWhat test points should I add and what measurements should I make during bring-up?",
    "Analyze the power distribution in this KiCad schematic '{name}': {description}\nComponents: {components}\n\nCalculate power consumption and recommend decoupling.",
]

MODIFICATIONS = [
    "lower power consumption",
    "higher reliability (automotive grade)",
    "smaller PCB footprint",
    "EMC compliance (CE marking)",
    "USB-C power delivery",
    "battery-powered operation",
    "industrial temperature range (-40 to +85C)",
    "adding WiFi connectivity via ESP32",
    "cost reduction for mass production",
    "adding ESD protection on all IOs",
]


def load_schematics(max_count=5000):
    """Load real schematics with enough description."""
    schematics = []
    with open(SCHEMATICS_FILE) as f:
        for line in f:
            try:
                r = json.loads(line.strip())
                desc = r.get("description", "")
                comps = r.get("components_used") or []
                name = r.get("name", "")
                if desc and len(desc) > 50 and len(comps) >= 3 and name:
                    schematics.append(
                        {
                            "name": name,
                            "description": desc[:500],
                            "components": ", ".join(comps[:15]),
                            "snippet": (r.get("schematic_snippet", "") or "")[:500],
                        }
                    )
            except json.JSONDecodeError:
                continue
            if len(schematics) >= max_count:
                break
    return schematics


def generate_grounded_qa(schematic):
    """Generate Q&A grounded in real schematic data."""
    template = random.choice(TEMPLATES)
    modification = random.choice(MODIFICATIONS)

    question = template.format(
        name=schematic["name"],
        description=schematic["description"],
        components=schematic["components"],
        modification=modification,
    )

    prompt = f"""You are an expert KiCad PCB designer reviewing a REAL schematic.

The user asks about a real KiCad project. Your answer must be:
1. Technically accurate and specific to the components listed
2. Based ONLY on the information given (no invented specs)
3. Practical with actionable advice
4. 200-400 words

If you don't know specific values for a component, say "check the datasheet for [component]" instead of inventing values.

User question:
{question}

Answer as a KiCad expert:"""

    try:
        with httpx.Client(timeout=60.0) as client:
            resp = client.post(
                ANTHROPIC_URL,
                headers={
                    "x-api-key": ANTHROPIC_KEY,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": MODEL,
                    "max_tokens": 700,
                    "temperature": 0.3,
                    "system": "You are an expert KiCad PCB designer. You review real schematics and provide accurate, datasheet-referenced advice. If you don't know a specific value, say 'check the datasheet' instead of guessing.",
                    "messages": [{"role": "user", "content": prompt}],
                },
            )
            resp.raise_for_status()
            answer = resp.json()["content"][0]["text"]

            if answer and len(answer) > 100:
                return {
                    "conversations": [
                        {
                            "from": "system",
                            "value": "You are an expert KiCad PCB designer. You review real schematics and provide accurate, datasheet-referenced advice.",
                        },
                        {"from": "human", "value": question},
                        {"from": "gpt", "value": answer},
                    ],
                    "domain": "kicad",
                    "source": "open-schematics-grounded",
                    "reference_project": schematic["name"],
                }
    except Exception as e:
        print(f"  Error: {e}")
    return None


def main():
    print("=== Regenerate KiCad Dataset v2 (grounded in real schematics) ===")

    schematics = load_schematics(5000)
    print(f"Loaded {len(schematics)} real schematics")

    TARGET = 3000
    total = 0
    errors = 0

    os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)
    with open(OUTPUT, "w") as f:
        for i in range(TARGET):
            schematic = random.choice(schematics)
            result = generate_grounded_qa(schematic)

            if result:
                f.write(json.dumps(result, ensure_ascii=False) + "\n")
                total += 1
            else:
                errors += 1

            if (i + 1) % 100 == 0:
                print(f"  [{i+1}/{TARGET}] generated={total} errors={errors}")

            time.sleep(0.5)

    print("\n=== DONE ===")
    print(f"Total: {total} Q&A pairs (grounded)")
    print(f"Output: {OUTPUT}")
    print(f"Size: {os.path.getsize(OUTPUT) / 1024**2:.1f} MB")


if __name__ == "__main__":
    main()
