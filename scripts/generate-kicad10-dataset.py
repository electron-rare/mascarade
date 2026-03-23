"""Generate KiCad 10 specific Q&A dataset via Codestral teacher distillation."""

import json
import time
import os
import httpx
import random

# Route via Mascarade core (supports Codestral direct or Mistral via routing)
MASCARADE_URL = os.environ.get("MASCARADE_URL", "http://127.0.0.1:8100/v1/chat/completions")
MASCARADE_KEY = os.environ.get("MASCARADE_API_KEY", "")
MODEL = os.environ.get("DISTILL_MODEL", "mistral:codestral-latest")
OUTPUT = "finetune/datasets/kicad10_features.jsonl"

CATEGORIES = [
    {
        "name": "KiCad 10 Graphical DRC Rule Editor",
        "count": 200,
        "topics": [
            "How to create a custom DRC rule in KiCad 10's new graphical rule editor for {rule}",
            "Difference between KiCad 9 text-based DRC rules and KiCad 10 graphical editor",
            "Setting up clearance constraints per net class using KiCad 10 graphical DRC",
            "Creating conditional DRC rules in KiCad 10 (e.g., different rules for inner vs outer layers)",
            "Using suggested DRC fixes in KiCad 10 to auto-repair {error_type}",
            "Exporting DRC rules from KiCad 10 graphical editor to text format",
            "Setting up high-voltage clearance rules in KiCad 10 DRC for {voltage}V nets",
            "Configuring courtyard overlap checking in KiCad 10 DRC editor",
        ],
    },
    {
        "name": "KiCad 10 Time-Domain Tuning",
        "count": 200,
        "topics": [
            "How to use KiCad 10's new time-domain track tuning for {signal_type}",
            "Setting up tuning profiles for different layers in KiCad 10",
            "Length matching vs time-domain matching in KiCad 10 — when to use which",
            "Configuring differential pair tuning with KiCad 10's new tuning system",
            "DDR4 memory bus length matching using KiCad 10 time-domain tuner",
            "USB 3.0 differential pair tuning in KiCad 10",
            "PCIe lane length matching with KiCad 10 tuning profiles",
            "HDMI signal tuning across {layers}-layer stackup in KiCad 10",
            "Setting propagation delay targets per layer in KiCad 10 tuning profiles",
            "Troubleshooting tuning violations in KiCad 10",
        ],
    },
    {
        "name": "KiCad 10 Variants System",
        "count": 150,
        "topics": [
            "How to set up board variants in KiCad 10 for {use_case}",
            "Managing different BOMs for the same PCB design using KiCad 10 variants",
            "Creating a variant with DNP (Do Not Populate) components in KiCad 10",
            "Using variants for regional product versions (different voltage ratings) in KiCad 10",
            "Exporting variant-specific BOM and pick-and-place files for JLCPCB",
            "Switching between variants in KiCad 10 schematic and PCB views",
            "Variant property overrides for component values in KiCad 10",
            "Best practices for managing 5+ variants in a single KiCad 10 project",
        ],
    },
    {
        "name": "KiCad 10 Design Blocks",
        "count": 150,
        "topics": [
            "How to create and save a PCB design block in KiCad 10",
            "Using design blocks for reusable {block_type} in KiCad 10",
            "Managing a design block library in KiCad 10",
            "Importing a design block with net mapping in KiCad 10",
            "Creating a USB Type-C connector block with routing in KiCad 10",
            "Design block for {power_supply} power supply section",
            "Sharing design blocks between team members in KiCad 10",
            "Version controlling design blocks with Git in KiCad 10",
        ],
    },
    {
        "name": "KiCad 10 Migration from Proprietary EDA",
        "count": 200,
        "topics": [
            "Migrating a {source} design to KiCad 10 — complete workflow",
            "Importing Cadence Allegro {file_type} into KiCad 10",
            "Converting Mentor PADS layout to KiCad 10 — known issues and workarounds",
            "Importing gEDA/Lepton EDA schematic into KiCad 10",
            "Library mapping when importing from {source} to KiCad 10",
            "Verifying design integrity after {source} to KiCad 10 migration",
            "Handling proprietary footprints during Allegro to KiCad 10 import",
            "Migrating Altium Designer projects to KiCad 10 (via intermediate format)",
            "Common issues when converting Eagle designs to KiCad 10",
            "Post-migration DRC cleanup after importing from {source}",
        ],
    },
    {
        "name": "KiCad 10 Pin/Gate Swap and Annotation",
        "count": 100,
        "topics": [
            "How to perform pin swap in KiCad 10 PCB editor with back-annotation",
            "Gate swap for multi-gate ICs (e.g., 74HC00) in KiCad 10",
            "Forward annotation from schematic to PCB in KiCad 10",
            "Back annotation from PCB to schematic after pin swap in KiCad 10",
            "Using pin/gate swap to optimize routing in KiCad 10",
            "Constraints for pin swap — which pins can be swapped in KiCad 10",
        ],
    },
    {
        "name": "KiCad 10 New UI Features",
        "count": 100,
        "topics": [
            "Using lasso selection in KiCad 10 schematic and PCB editors",
            "Customizing toolbars in KiCad 10 editors",
            "Dark mode setup on Windows for KiCad 10",
            "Using hop-over wire display in KiCad 10 schematics",
            "Undo/redo within dialog boxes in KiCad 10",
            "Using 45-degree full-screen crosshairs in KiCad 10",
            "Jumper support in KiCad 10 — defining connected pin sets",
            "Grouping schematic elements in KiCad 10",
            "Drag-and-drop images into KiCad 10 schematics",
            "Short-circuit warning preview when dragging wires in KiCad 10",
        ],
    },
    {
        "name": "KiCad 10 3D and Manufacturing",
        "count": 100,
        "topics": [
            "Exporting 3D PDF from KiCad 10 for design review",
            "KiCad 10 transition to STEP-only 3D models — impact on libraries",
            "Adding barcodes to PCB silkscreen in KiCad 10",
            "Using hatched fills for copper zones in KiCad 10",
            "Native rounded rectangles in KiCad 10 footprints",
            "Generating Gerber files from KiCad 10 for JLCPCB",
            "KiCad 10 jobsets for automated output generation",
            "3D model assignment workflow in KiCad 10 (STEP format)",
        ],
    },
    {
        "name": "KiCad 10 Scripting and API",
        "count": 150,
        "topics": [
            "KiCad 10 Python scripting API changes from KiCad 9",
            "Writing a KiCad 10 plugin for {plugin_type}",
            "Automating DRC checks via Python in KiCad 10",
            "Scripting BOM export with variant support in KiCad 10",
            "KiCad 10 pcbnew Python API — creating traces programmatically",
            "Using KiCad 10 CLI for headless Gerber generation",
            "KiCad 10 IPC-2581 export via scripting",
            "Automating design block insertion via KiCad 10 Python API",
            "Writing a KiCad 10 action plugin for JLCPCB export",
            "KiCad 10 Git integration via Python scripting",
        ],
    },
    {
        "name": "KiCad 10 JLCPCB Workflow",
        "count": 150,
        "topics": [
            "Complete KiCad 10 to JLCPCB workflow — schematic to manufactured board",
            "Generating JLCPCB-compatible Gerber and drill files in KiCad 10",
            "Exporting BOM and CPL files from KiCad 10 for JLCPCB SMT assembly",
            "Setting up KiCad 10 DRC rules matching JLCPCB capabilities",
            "Using KiCad 10 variants for JLCPCB standard vs economic PCB",
            "Panelization in KiCad 10 for JLCPCB (V-score, tab routing)",
            "JLCPCB impedance-controlled PCB design in KiCad 10",
            "Castellated hole design in KiCad 10 for JLCPCB",
            "Ordering flex PCB from JLCPCB using KiCad 10 design",
            "KiCad 10 design review checklist before JLCPCB order",
        ],
    },
]

VARS = {
    "rule": ["minimum trace width", "clearance per voltage", "via-in-pad", "differential pair spacing", "courtyard overlap", "silkscreen-to-pad gap"],
    "error_type": ["unconnected net", "clearance violation", "short circuit", "missing courtyard", "silkscreen overlap"],
    "voltage": ["3.3", "5", "12", "24", "48", "230"],
    "signal_type": ["DDR4 data bus", "USB 3.0 differential pair", "PCIe Gen4 lane", "HDMI 2.1 TMDS", "Ethernet RGMII", "LVDS pair"],
    "layers": ["4", "6", "8"],
    "use_case": ["product with optional WiFi module", "multi-region power supply (EU/US)", "prototype vs production BOM", "basic vs premium version"],
    "block_type": ["USB Type-C connector with ESD", "ESP32 module with antenna", "LDO power supply", "RS-485 transceiver", "SWD debug header", "DC-DC buck converter"],
    "power_supply": ["3.3V LDO from 5V USB", "12V to 5V buck", "battery charger with path management"],
    "source": ["Cadence Allegro", "Mentor PADS", "gEDA/Lepton", "Altium Designer", "Eagle"],
    "file_type": ["board file (.brd)", "schematic (.sch)", "design archive", "library (.dra)"],
    "plugin_type": ["BOM generator", "DRC rule checker", "JLCPCB exporter", "net inspector", "component placer"],
}


def fill_template(template):
    result = template
    for key, values in VARS.items():
        placeholder = "{" + key + "}"
        while placeholder in result:
            result = result.replace(placeholder, random.choice(values), 1)
    return result


def generate_qa(category_name, topic_template):
    topic = fill_template(topic_template)
    prompt = f"""You are an expert KiCad 10 developer and PCB designer writing training data.

Category: {category_name}
Topic: {topic}

KiCad 10.0.0 was released on March 20, 2026. Key new features include:
- Graphical DRC Rule Editor (replaces text-only)
- Time-Domain Track Tuning with Tuning Profiles
- Board Variants system for managing BOM differences
- PCB Design Blocks (reusable layout library)
- 3 new importers: Cadence Allegro, Mentor PADS, gEDA/Lepton
- Pin/Gate Swap with forward/back annotation
- Suggested DRC fixes
- 3D PDF export, barcodes, hatched fills, native rounded rectangles
- Lasso selection, dark mode Windows, customizable toolbars
- 952 new symbols, 1216 new footprints, 386 new 3D models

Generate a detailed Q&A. The answer should be 150-400 words with step-by-step instructions where applicable.
Reply ONLY JSON: {{"question": "...", "answer": "..."}}"""

    try:
        headers = {"Content-Type": "application/json"}
        if MASCARADE_KEY:
            headers["Authorization"] = f"Bearer {MASCARADE_KEY}"
        with httpx.Client(timeout=60.0) as client:
            resp = client.post(MASCARADE_URL, headers=headers, json={
                "model": MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "response_format": {"type": "json_object"},
                "temperature": 0.7,
                "max_tokens": 700,
                "stream": False,
                "project_id": "dataset-kicad10",
            })
            resp.raise_for_status()
            data = json.loads(resp.json()["choices"][0]["message"]["content"])
            if "question" in data and "answer" in data:
                return {
                    "conversations": [
                        {"from": "system", "value": f"You are an expert KiCad 10 PCB designer and developer. KiCad 10.0.0 was released March 20, 2026. You provide detailed, accurate answers about {category_name}."},
                        {"from": "human", "value": data["question"]},
                        {"from": "gpt", "value": data["answer"]},
                    ],
                    "domain": "kicad-10",
                    "category": category_name,
                    "source": "codestral-teacher-distillation",
                }
    except Exception as e:
        print(f"  Error: {e}")
    return None


def main():
    total_target = sum(c["count"] for c in CATEGORIES)
    print("=== KiCad 10 Dataset Generator ===")
    print(f"Target: {total_target} Q&A pairs\n")

    os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)
    total = 0
    errors = 0

    with open(OUTPUT, "w") as f:
        for cat in CATEGORIES:
            print(f"\n=== {cat['name']} ({cat['count']} pairs) ===")
            cat_count = 0
            for i in range(cat["count"]):
                topic = random.choice(cat["topics"])
                result = generate_qa(cat["name"], topic)
                if result:
                    f.write(json.dumps(result, ensure_ascii=False) + "\n")
                    cat_count += 1
                    total += 1
                else:
                    errors += 1
                if (i + 1) % 50 == 0:
                    print(f"  [{i+1}/{cat['count']}] generated={cat_count} errors={errors}")
                time.sleep(0.5)
            print(f"  DONE: {cat_count} pairs")

    print("\n=== SUMMARY ===")
    print(f"Total: {total} Q&A pairs")
    print(f"Errors: {errors}")
    print(f"Output: {OUTPUT}")
    print(f"Size: {os.path.getsize(OUTPUT) / 1024**2:.1f} MB")


if __name__ == "__main__":
    main()
