"""FastAPI backend for training data review."""
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import json, os, io
from pathlib import Path

app = FastAPI()

DATA_DIRS = [
    "/ai/saisail/mascarade/finetune/datasets/cleaned_final",
    "/ai/saisail/mascarade/finetune/datasets/improved_final",
]
# Fallback for local dev
if not os.path.exists(DATA_DIRS[0]):
    DATA_DIRS = [str(Path(__file__).parent.parent.parent / "finetune" / "datasets" / d) for d in ["cleaned_final", "improved_final"]]

REVIEWS_FILE = "/tmp/data-reviews.json"
reviews = {}
if os.path.exists(REVIEWS_FILE):
    reviews = json.load(open(REVIEWS_FILE))

def save_reviews():
    json.dump(reviews, open(REVIEWS_FILE, "w"), indent=2)

def find_datasets():
    result = []
    for d in DATA_DIRS:
        if not os.path.isdir(d): continue
        for fn in sorted(os.listdir(d)):
            if fn.endswith(".jsonl"):
                path = os.path.join(d, fn)
                count = sum(1 for _ in open(path))
                domain = fn.split("_")[0]
                result.append({"name": fn, "path": path, "count": count, "domain": domain})
    return result

def get_stats(dataset_name):
    r = reviews.get(dataset_name, {})
    approved = sum(1 for v in r.values() if v.get("approved") is True)
    rejected = sum(1 for v in r.values() if v.get("approved") is False)
    total = len(r) if r else 0
    # Get total from file
    ds = next((d for d in find_datasets() if d["name"] == dataset_name), None)
    file_total = ds["count"] if ds else 0
    return {"total": file_total, "approved": approved, "rejected": rejected, "pending": file_total - approved - rejected}

@app.get("/api/datasets")
def list_datasets():
    return find_datasets()

@app.get("/api/dataset/{name}")
def get_dataset(name: str):
    ds = next((d for d in find_datasets() if d["name"] == name), None)
    if not ds: return {"error": "not found"}
    examples = []
    with open(ds["path"]) as f:
        for i, line in enumerate(f):
            try:
                r = json.loads(line.strip())
                r["id"] = i
                rev = reviews.get(name, {}).get(str(i), {})
                r["approved"] = rev.get("approved")
                r["score"] = rev.get("score")
                r["notes"] = rev.get("notes")
                examples.append(r)
            except: pass
    return {"examples": examples, "stats": get_stats(name)}

class ExampleUpdate(BaseModel):
    approved: bool | None = None
    score: int | None = None
    notes: str | None = None

@app.patch("/api/example/{dataset}/{id}")
def update_example(dataset: str, id: int, update: ExampleUpdate):
    if dataset not in reviews: reviews[dataset] = {}
    if str(id) not in reviews[dataset]: reviews[dataset][str(id)] = {}
    if update.approved is not None: reviews[dataset][str(id)]["approved"] = update.approved
    if update.score is not None: reviews[dataset][str(id)]["score"] = update.score
    if update.notes is not None: reviews[dataset][str(id)]["notes"] = update.notes
    save_reviews()
    return {"ok": True, "stats": get_stats(dataset)}

class EditUpdate(BaseModel):
    conv_idx: int
    value: str

@app.post("/api/example/{dataset}/{id}/edit")
def edit_example(dataset: str, id: int, edit: EditUpdate):
    ds = next((d for d in find_datasets() if d["name"] == dataset), None)
    if not ds: return {"error": "not found"}
    lines = open(ds["path"]).readlines()
    if id >= len(lines): return {"error": "out of range"}
    try:
        record = json.loads(lines[id])
        if edit.conv_idx < len(record.get("conversations", [])):
            record["conversations"][edit.conv_idx]["value"] = edit.value
            lines[id] = json.dumps(record, ensure_ascii=False) + "\n"
            with open(ds["path"], "w") as f:
                f.writelines(lines)
            return {"ok": True}
    except Exception as e:
        return {"error": str(e)}
    return {"error": "invalid"}

class BulkUpdate(BaseModel):
    ids: list[int]
    approved: bool | None = None
    score: int | None = None

@app.post("/api/bulk/{dataset}")
def bulk_update(dataset: str, bulk: BulkUpdate):
    if dataset not in reviews: reviews[dataset] = {}
    for id in bulk.ids:
        if str(id) not in reviews[dataset]: reviews[dataset][str(id)] = {}
        if bulk.approved is not None: reviews[dataset][str(id)]["approved"] = bulk.approved
        if bulk.score is not None: reviews[dataset][str(id)]["score"] = bulk.score
    save_reviews()
    return {"ok": True, "updated": len(bulk.ids), "stats": get_stats(dataset)}

@app.get("/api/dataset/{name}/stats")
def dataset_stats(name: str):
    ds = next((d for d in find_datasets() if d["name"] == name), None)
    if not ds: return {"error": "not found"}
    lengths = []
    has_code = 0
    has_explanation = 0
    domains = {}
    sources = {}
    total = 0
    import re
    with open(ds["path"]) as f:
        for line in f:
            try:
                r = json.loads(line.strip())
                total += 1
                a_text = ""
                for c in r.get("conversations", []):
                    if c.get("from") in ("gpt", "assistant"):
                        a_text += c.get("value", "")
                lengths.append(len(a_text))
                if any(m in a_text for m in ["```", "#include", "void ", "module ", ".subckt", "def ", "import "]):
                    has_code += 1
                no_code = re.sub(r"```[\s\S]*?```", "", a_text)
                if len(no_code.split()) > 30:
                    has_explanation += 1
                dom = r.get("domain", "unknown")
                domains[dom] = domains.get(dom, 0) + 1
                src = str(r.get("source", "unknown"))[:30]
                sources[src] = sources.get(src, 0) + 1
            except: pass
    lengths.sort()
    return {
        "total": total,
        "avg_length": sum(lengths) // max(len(lengths), 1),
        "median_length": lengths[len(lengths)//2] if lengths else 0,
        "min_length": lengths[0] if lengths else 0,
        "max_length": lengths[-1] if lengths else 0,
        "has_code_pct": round(has_code / max(total, 1) * 100),
        "has_explanation_pct": round(has_explanation / max(total, 1) * 100),
        "domains": dict(sorted(domains.items(), key=lambda x: -x[1])[:10]),
        "sources": dict(sorted(sources.items(), key=lambda x: -x[1])[:10]),
        "length_buckets": {
            "<100": sum(1 for l in lengths if l < 100),
            "100-500": sum(1 for l in lengths if 100 <= l < 500),
            "500-1000": sum(1 for l in lengths if 500 <= l < 1000),
            "1000-3000": sum(1 for l in lengths if 1000 <= l < 3000),
            "3000+": sum(1 for l in lengths if l >= 3000),
        }
    }

@app.get("/api/export/{name}")
def export_approved(name: str):
    ds = next((d for d in find_datasets() if d["name"] == name), None)
    if not ds: return {"error": "not found"}
    rev = reviews.get(name, {})
    buf = io.StringIO()
    with open(ds["path"]) as f:
        for i, line in enumerate(f):
            r = rev.get(str(i), {})
            if r.get("approved") is not False:  # Keep approved + pending
                buf.write(line)
    buf.seek(0)
    return StreamingResponse(buf, media_type="application/jsonl",
        headers={"Content-Disposition": f"attachment; filename={name}"})

# Serve static frontend in production
dist = Path(__file__).parent / "dist"
if dist.exists():
    app.mount("/", StaticFiles(directory=str(dist), html=True), name="static")
