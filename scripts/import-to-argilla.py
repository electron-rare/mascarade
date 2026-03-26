"""Import mascarade training datasets into Argilla for human review."""
import argilla as rg
import json, os, sys

ARGILLA_URL = os.environ.get("ARGILLA_URL", "http://192.168.0.119:6900")
ARGILLA_KEY = os.environ.get("ARGILLA_API_KEY", "argilla.apikey.mascarade2026")
DATA_DIR = os.environ.get("DATA_DIR", "finetune/datasets/cleaned_final")

# Connect
client = rg.Argilla(api_url=ARGILLA_URL, api_key=ARGILLA_KEY)
print(f"Connected to Argilla at {ARGILLA_URL}")

# Define review settings
settings = rg.Settings(
    fields=[
        rg.TextField(name="system_prompt", title="System Prompt", use_markdown=True),
        rg.TextField(name="question", title="Question", use_markdown=True),
        rg.TextField(name="answer", title="Answer", use_markdown=True),
        rg.TextField(name="domain", title="Domain"),
        rg.TextField(name="source", title="Source"),
    ],
    questions=[
        rg.RatingQuestion(name="quality", title="Technical Quality (1-10)", values=[1,2,3,4,5,6,7,8,9,10]),
        rg.RatingQuestion(name="accuracy", title="Accuracy (1-10)", values=[1,2,3,4,5,6,7,8,9,10]),
        rg.LabelQuestion(name="verdict", title="Verdict", labels=["approve", "reject", "needs_edit"]),
        rg.TextQuestion(name="notes", title="Notes / Corrections", required=False),
    ],
    guidelines="Review each Q&A pair for technical accuracy in electronics (KiCad, SPICE, embedded, etc.). Check for hallucinated values, incorrect formulas, and missing code. Score 7+ = good, 4-6 = needs improvement, 1-3 = reject.",
)

# Import each dataset
datasets_to_import = [
    "spice_final.jsonl",
    "emc_final.jsonl",
    "power_final.jsonl",
    "dsp_final.jsonl",
    "ipc_final.jsonl",
    "kicad-v3_final.jsonl",
    "embedded_final.jsonl",
    "analog_final.jsonl",
    "platformio_final.jsonl",
    "missing_final.jsonl",
    "iot_final.jsonl",
    "stm32_final.jsonl",
    "kicad_final.jsonl",
    "freecad_final.jsonl",
    "rtlcoder3_final.jsonl",
]

for fn in datasets_to_import:
    path = os.path.join(DATA_DIR, fn)
    if not os.path.exists(path):
        print(f"SKIP {fn}: not found")
        continue

    ds_name = fn.replace("_final.jsonl", "").replace("-", "_")
    print(f"\nImporting {fn} as '{ds_name}'...", flush=True)

    # Create or get dataset
    try:
        dataset = rg.Dataset(name=ds_name, workspace="default", settings=settings)
        dataset.create()
        print(f"  Created dataset '{ds_name}'")
    except Exception:
        dataset = client.datasets(name=ds_name, workspace="default")
        print(f"  Dataset '{ds_name}' already exists")

    # Load records
    records = []
    with open(path) as f:
        for i, line in enumerate(f):
            try:
                r = json.loads(line.strip())
                sys_prompt = ""
                question = ""
                answer = ""
                for c in r.get("conversations", []):
                    role = c.get("from", c.get("role", ""))
                    val = c.get("value", c.get("content", ""))
                    if role == "system": sys_prompt = val
                    elif role in ("human", "user"): question = val
                    elif role in ("gpt", "assistant"): answer += val + "\n"

                if not question or not answer:
                    continue

                records.append(rg.Record(
                    fields={
                        "system_prompt": sys_prompt[:500],
                        "question": question,
                        "answer": answer.strip(),
                        "domain": r.get("domain", ds_name),
                        "source": str(r.get("source", "unknown"))[:100],
                    },
                    metadata={"id": i, "length": len(answer), "has_code": "```" in answer or "#include" in answer},
                ))
            except Exception:
                pass

            if len(records) >= 1000:  # Batch upload
                dataset.records.log(records)
                print(f"  Uploaded {i+1} records...", flush=True)
                records = []

    if records:
        dataset.records.log(records)

    total = sum(1 for _ in open(path))
    print(f"  Done: {total} records imported to '{ds_name}'")

print("\nAll datasets imported to Argilla!")
print(f"Review at: {ARGILLA_URL}")
print(f"Login: argilla / mascarade")
