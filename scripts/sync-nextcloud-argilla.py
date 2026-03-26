"""Sync datasets to Nextcloud then import to Argilla (both on Tower)."""
import os, sys, json, subprocess
from pathlib import Path

NEXTCLOUD_URL = os.environ.get("NEXTCLOUD_URL", "https://cloud.saillant.cc")
NEXTCLOUD_USER = os.environ.get("NEXTCLOUD_USER", "")
NEXTCLOUD_PASS = os.environ.get("NEXTCLOUD_PASSWORD", "")
ARGILLA_URL = os.environ.get("ARGILLA_URL", "http://localhost:6900")
ARGILLA_KEY = os.environ.get("ARGILLA_API_KEY", "owner.apikey")
DATA_DIR = os.environ.get("DATA_DIR", "finetune/datasets/cleaned_final")

if not NEXTCLOUD_USER:
    print("Set NEXTCLOUD_USER and NEXTCLOUD_PASSWORD env vars")
    sys.exit(1)

# Step 1: Upload datasets to Nextcloud via curl (simpler than WebDAV lib)
print("=== UPLOAD TO NEXTCLOUD ===", flush=True)
webdav = f"{NEXTCLOUD_URL}/remote.php/dav/files/{NEXTCLOUD_USER}/mascarade/datasets"

# Create dirs
for d in ["mascarade", "mascarade/datasets"]:
    subprocess.run([
        "curl", "-sS", "-X", "MKCOL",
        "-u", f"{NEXTCLOUD_USER}:{NEXTCLOUD_PASS}",
        f"{NEXTCLOUD_URL}/remote.php/dav/files/{NEXTCLOUD_USER}/{d}"
    ], capture_output=True)

uploaded = 0
for fn in sorted(os.listdir(DATA_DIR)):
    if not fn.endswith(".jsonl"):
        continue
    path = os.path.join(DATA_DIR, fn)
    lines = sum(1 for _ in open(path))
    if lines < 10:
        continue
    print(f"  Uploading {fn} ({lines} lines)...", flush=True)
    r = subprocess.run([
        "curl", "-sS", "-X", "PUT",
        "-u", f"{NEXTCLOUD_USER}:{NEXTCLOUD_PASS}",
        "--data-binary", f"@{path}",
        f"{webdav}/{fn}"
    ], capture_output=True, text=True)
    if "error" not in r.stderr.lower():
        uploaded += 1

print(f"  Uploaded: {uploaded} files", flush=True)

# Step 2: Import to Argilla (from local files since both on Tower)
print("\n=== IMPORT TO ARGILLA ===", flush=True)
try:
    import argilla as rg
    client = rg.Argilla(api_url=ARGILLA_URL, api_key=ARGILLA_KEY)
    print(f"Connected to Argilla at {ARGILLA_URL}", flush=True)

    settings = rg.Settings(
        fields=[
            rg.TextField(name="system_prompt", title="System Prompt", use_markdown=True),
            rg.TextField(name="question", title="Question", use_markdown=True),
            rg.TextField(name="answer", title="Answer", use_markdown=True),
            rg.TextField(name="domain", title="Domain"),
        ],
        questions=[
            rg.RatingQuestion(name="quality", title="Quality (1-10)", values=list(range(1, 11))),
            rg.LabelQuestion(name="verdict", title="Verdict", labels=["approve", "reject", "needs_edit"]),
            rg.TextQuestion(name="notes", title="Notes", required=False),
        ],
        guidelines="Review electronics Q&A for accuracy. Check code, formulas, component values.",
    )

    for fn in sorted(os.listdir(DATA_DIR)):
        if not fn.endswith(".jsonl"):
            continue
        path = os.path.join(DATA_DIR, fn)
        lines = sum(1 for _ in open(path))
        if lines < 10:
            continue

        ds_name = fn.replace("_final.jsonl", "").replace("-", "_")
        print(f"\n  Importing {fn} -> {ds_name} ({lines} ex)...", flush=True)

        try:
            dataset = rg.Dataset(name=ds_name, workspace="default", settings=settings)
            dataset.create()
        except Exception:
            try:
                dataset = client.datasets(name=ds_name, workspace="default")
            except Exception:
                print(f"    SKIP (cannot create/find dataset)")
                continue

        records = []
        with open(path) as f:
            for i, line in enumerate(f):
                try:
                    r = json.loads(line.strip())
                    sys_p, q, a = "", "", ""
                    for c in r.get("conversations", []):
                        role = c.get("from", c.get("role", ""))
                        val = c.get("value", c.get("content", ""))
                        if role == "system": sys_p = val
                        elif role in ("human", "user"): q = val
                        elif role in ("gpt", "assistant"): a += val + "\n"
                    if not q or not a:
                        continue
                    records.append(rg.Record(
                        fields={
                            "system_prompt": sys_p[:500],
                            "question": q,
                            "answer": a.strip(),
                            "domain": r.get("domain", ds_name),
                        },
                    ))
                except Exception:
                    pass
                if len(records) >= 500:
                    dataset.records.log(records)
                    records = []
        if records:
            dataset.records.log(records)
        print(f"    Done: {i+1} records", flush=True)

    print("\nAll datasets imported!", flush=True)
except ImportError:
    print("argilla not installed — skipping Argilla import", flush=True)
except Exception as e:
    print(f"Argilla error: {e}", flush=True)
