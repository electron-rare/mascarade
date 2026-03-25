"""Generate IPC/JLCPCB/DRC standards Q&A dataset via Codestral teacher distillation."""

import json
import time
import os
import httpx
import random

MASCARADE_URL = os.environ.get(
    "MASCARADE_URL", "http://127.0.0.1:8100/v1/chat/completions"
)
MASCARADE_KEY = os.environ.get("MASCARADE_API_KEY", "")
MODEL = os.environ.get("DISTILL_MODEL", "mistral:codestral-latest")
OUTPUT = "finetune/datasets/ipc_jlcpcb_standards.jsonl"

# Categories of questions to generate
CATEGORIES = [
    {
        "name": "IPC-2221 PCB Design Rules",
        "count": 500,
        "topics": [
            "minimum trace width for {current}A on {copper_oz}oz copper {layer} layer",
            "minimum clearance between {voltage}V traces",
            "annular ring requirements for via drill {drill}mm",
            "conductor spacing for {voltage}V on {material} substrate",
            "thermal relief pad design for {component}",
            "via-to-pad clearance on {class} board",
            "trace impedance for {impedance}ohm {type} line",
            "solder mask dam width minimum",
            "board edge clearance requirements",
            "plated through-hole aspect ratio limits",
        ],
    },
    {
        "name": "IPC-7351 SMD Footprints",
        "count": 400,
        "topics": [
            "land pattern for {package} package ({size})",
            "courtyard dimensions for {package}",
            "pad dimensions for {pitch}mm pitch {type}",
            "toe/heel/side fillet for {package} ({density})",
            "thermal pad design for {package} with exposed pad",
            "IPC-7351B naming convention for {component}",
            "BGA pad diameter for {pitch}mm pitch",
            "QFN pad extension beyond package body",
        ],
    },
    {
        "name": "IPC-A-610 Assembly Quality",
        "count": 400,
        "topics": [
            "solder joint criteria for {type} component (Class {class})",
            "acceptable vs defect: {defect_type} on {component}",
            "component placement tolerance Class {class}",
            "solder bridging acceptance criteria",
            "tombstoning defect classification",
            "BGA X-ray inspection criteria",
            "conformal coating coverage requirements",
            "lead-free vs leaded solder joint appearance",
        ],
    },
    {
        "name": "IPC-2152 Current Capacity",
        "count": 300,
        "topics": [
            "trace width for {current}A on {copper_oz}oz {layer} layer with {temp_rise}C rise",
            "via current capacity for {drill}mm drill {plating}um plating",
            "parallel trace current sharing",
            "thermal via array for {power}W dissipation",
            "polygon pour current density limits",
            "fusing current for {width}mil trace {copper_oz}oz copper",
        ],
    },
    {
        "name": "JLCPCB DFM Rules",
        "count": 500,
        "topics": [
            "minimum trace width/spacing for {layers}-layer board {copper_oz}oz",
            "drill size limitations and tolerances JLCPCB",
            "JLCPCB impedance control options and tolerances",
            "panelization requirements JLCPCB (V-score, tab route)",
            "JLCPCB solder mask color options and capabilities",
            "JLCPCB silkscreen minimum text height and width",
            "JLCPCB board thickness options for {layers}-layer",
            "JLCPCB surface finish options (HASL, ENIG, OSP)",
            "JLCPCB gerber file format requirements",
            "JLCPCB BOM and pick-and-place file format",
            "JLCPCB castellated hole specifications",
            "JLCPCB blind/buried via capabilities",
        ],
    },
    {
        "name": "KiCad DRC Rules",
        "count": 400,
        "topics": [
            "setting up DRC rules in KiCad {version} for IPC Class {class}",
            "custom DRC rule syntax for {rule_type} in KiCad",
            "configuring trace width constraints per net class",
            "via rules: size, drill, annular ring in KiCad",
            "clearance rules for high voltage nets in KiCad",
            "silkscreen-to-pad clearance DRC rule",
            "courtyard overlap checking in KiCad",
            "differential pair DRC rules in KiCad",
            "exporting DRC report for JLCPCB review",
            "fixing common DRC errors before manufacturing",
        ],
    },
    {
        "name": "EMC Design Rules",
        "count": 300,
        "topics": [
            "ground plane requirements for EMC compliance",
            "decoupling capacitor placement strategy IEC 61000",
            "return current path design for {signal_type}",
            "shielding requirements for {frequency} emissions",
            "ESD protection circuit design IEC 61000-4-2",
            "power supply filtering for conducted emissions",
            "PCB stackup for EMC: {layers}-layer optimum",
            "guard traces and guard rings design",
            "split plane crossing rules",
            "common mode choke selection for {interface}",
        ],
    },
    {
        "name": "IPC-6012 Board Classes",
        "count": 200,
        "topics": [
            "Class 1 vs Class 2 vs Class 3 requirements comparison",
            "plating thickness requirements per class",
            "hole wall quality criteria per class",
            "copper thickness tolerance per class",
            "dimensional tolerance per class",
            "electrical testing requirements per class",
        ],
    },
    {
        "name": "J-STD-001 Soldering",
        "count": 200,
        "topics": [
            "reflow profile for {paste_type} solder paste",
            "wave soldering parameters for through-hole",
            "hand soldering iron temperature and dwell time",
            "lead-free soldering alloy comparison (SAC305 vs SN100C)",
            "flux classification and cleaning requirements",
            "moisture sensitivity level (MSL) handling",
            "intermetallic compound growth limits",
            "rework station temperature profile",
        ],
    },
    {
        "name": "RoHS/REACH/CE Compliance",
        "count": 200,
        "topics": [
            "RoHS restricted substances list and limits (ppm)",
            "REACH SVHC candidate list impact on PCB design",
            "CE marking process for electronic product",
            "declaration of conformity template for {product_type}",
            "RoHS exemptions for {application}",
            "conflict minerals reporting requirements",
            "WEEE directive compliance for electronic products",
            "UL certification requirements for PCB",
        ],
    },
]

# Template variables
VARS = {
    "current": ["0.5", "1", "2", "3", "5", "10", "15", "20"],
    "copper_oz": ["0.5", "1", "2"],
    "layer": ["internal", "external"],
    "voltage": ["3.3", "5", "12", "24", "48", "110", "230", "400"],
    "class": ["1", "2", "3"],
    "drill": ["0.2", "0.3", "0.4", "0.6", "0.8", "1.0"],
    "package": [
        "0201",
        "0402",
        "0603",
        "0805",
        "1206",
        "1210",
        "2512",
        "SOT-23",
        "SOT-223",
        "SOIC-8",
        "SOIC-16",
        "QFN-16",
        "QFN-32",
        "QFN-48",
        "QFP-44",
        "QFP-64",
        "QFP-100",
        "QFP-144",
        "BGA-256",
        "BGA-484",
    ],
    "pitch": ["0.4", "0.5", "0.65", "0.8", "1.0", "1.27"],
    "type": ["microstrip", "stripline", "coplanar waveguide", "differential pair"],
    "density": ["least (Level A)", "nominal (Level B)", "most (Level C)"],
    "component": [
        "SMD resistor",
        "SMD capacitor",
        "QFN IC",
        "BGA IC",
        "through-hole connector",
        "electrolytic capacitor",
    ],
    "defect_type": [
        "insufficient solder",
        "excess solder",
        "cold solder",
        "bridging",
        "tombstoning",
        "voiding",
        "lifted pad",
    ],
    "temp_rise": ["10", "20", "30", "40"],
    "plating": ["18", "25", "30"],
    "power": ["1", "2", "5", "10", "20"],
    "width": ["5", "8", "10", "15", "20", "30"],
    "layers": ["2", "4", "6", "8"],
    "material": ["FR-4", "Rogers 4350B", "polyimide"],
    "impedance": ["50", "75", "90", "100"],
    "signal_type": ["high-speed digital", "RF", "switching power", "analog"],
    "frequency": ["30MHz", "100MHz", "500MHz", "1GHz", "2.4GHz"],
    "interface": ["USB", "Ethernet", "HDMI", "CAN bus", "RS-485"],
    "paste_type": ["SAC305 lead-free", "Sn63Pb37 leaded", "low-temperature BiSnAg"],
    "version": ["8", "9"],
    "rule_type": ["trace width", "clearance", "via", "differential pair", "silkscreen"],
    "product_type": [
        "consumer electronics",
        "industrial control",
        "medical device",
        "LED lighting",
    ],
    "application": [
        "high reliability electronics",
        "medical implants",
        "aerospace",
        "automotive",
    ],
    "size": ["metric", "imperial"],
}


def fill_template(template: str) -> str:
    """Fill template variables with random values."""
    result = template
    for key, values in VARS.items():
        placeholder = "{" + key + "}"
        while placeholder in result:
            result = result.replace(placeholder, random.choice(values), 1)
    return result


def generate_qa(category_name: str, topic_template: str) -> dict | None:
    """Generate a Q&A pair using Codestral."""
    topic = fill_template(topic_template)
    prompt = f"""You are an expert electronics engineer writing training data for an AI assistant.

Category: {category_name}
Topic: {topic}

Generate a detailed, technically accurate Q&A pair about this topic.
The question should be natural (as a real engineer would ask).
The answer should be precise, include specific numbers/values from IPC standards where applicable, and be 150-400 words.

Reply ONLY in JSON format:
{{"question": "...", "answer": "..."}}"""

    try:
        headers = {"Content-Type": "application/json"}
        if MASCARADE_KEY:
            headers["Authorization"] = f"Bearer {MASCARADE_KEY}"
        with httpx.Client(timeout=60.0) as client:
            resp = client.post(
                MASCARADE_URL,
                headers=headers,
                json={
                    "model": MODEL,
                    "messages": [{"role": "user", "content": prompt}],
                    "response_format": {"type": "json_object"},
                    "temperature": 0.7,
                    "max_tokens": 600,
                    "stream": False,
                    "project_id": "dataset-ipc",
                },
            )
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"]
            data = json.loads(content)
            if "question" in data and "answer" in data:
                return {
                    "conversations": [
                        {
                            "from": "system",
                            "value": f"You are an expert electronics engineer specializing in {category_name}. You provide precise, standards-compliant answers.",
                        },
                        {"from": "human", "value": data["question"]},
                        {"from": "gpt", "value": data["answer"]},
                    ],
                    "domain": "ipc-standards",
                    "category": category_name,
                    "source": "codestral-teacher-distillation",
                }
    except Exception as e:
        print(f"  Error: {e}")
    return None


def main():
    print("=== IPC/JLCPCB Standards Dataset Generator ===")
    print(f"Target: {sum(c['count'] for c in CATEGORIES)} Q&A pairs\n")

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
                    print(
                        f"  [{i+1}/{cat['count']}] generated={cat_count} errors={errors}"
                    )

                # Rate limit: ~2 requests/sec for Codestral
                time.sleep(0.5)

            print(f"  DONE: {cat_count} pairs")

    print("\n=== SUMMARY ===")
    print(f"Total: {total} Q&A pairs")
    print(f"Errors: {errors}")
    print(f"Output: {OUTPUT}")
    print(f"Size: {os.path.getsize(OUTPUT) / 1024**2:.1f} MB")


if __name__ == "__main__":
    main()
