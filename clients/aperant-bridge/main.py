"""
aperant-bridge — FastAPI HTTP bridge for Aperant (Dockerized on Tower)
Reads/writes the .auto-claude/specs/ filesystem and exposes a REST API.

Configuration (env vars):
  SPECS_DIR      : absolute path to the specs directory
                   (default: /workspace/.auto-claude/specs)
  BRIDGE_API_KEY : bearer token required on every request (default: empty → no auth)
  HOST           : bind address (default: 0.0.0.0)
  PORT           : listen port  (default: 3200)

Spec folder structure (one subdirectory per spec):
  {SPECS_DIR}/{id}/
    spec.md                  — spec content (markdown)
    implementation_plan.json — generated plan (optional)
    status.json              — run status  (optional, written by Aperant)
    context.json             — extra context (optional)
"""

import json
import os
import shutil
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

SPECS_DIR = Path(os.getenv("SPECS_DIR", "/workspace/.auto-claude/specs"))
BRIDGE_API_KEY: str = os.getenv("BRIDGE_API_KEY", "")
HOST: str = os.getenv("HOST", "0.0.0.0")
PORT: int = int(os.getenv("PORT", "3200"))

app = FastAPI(
    title="Aperant Bridge",
    description="HTTP bridge for Aperant (Dockerized on Tower)",
    version="1.0.0",
)

security = HTTPBearer(auto_error=False)


# ---------------------------------------------------------------------------
# Auth dependency
# ---------------------------------------------------------------------------


def verify_token(
    credentials: HTTPAuthorizationCredentials | None = Security(security),
) -> None:
    """Validate bearer token if BRIDGE_API_KEY is set."""
    if not BRIDGE_API_KEY:
        return  # No auth configured — open access
    if credentials is None or credentials.credentials != BRIDGE_API_KEY:
        raise HTTPException(status_code=401, detail="Invalid or missing bearer token")


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class SpecCreateRequest(BaseModel):
    title: str
    content: str
    project: str | None = None
    context: dict[str, Any] | None = None


class SpecSummary(BaseModel):
    id: str
    title: str
    project: str | None
    status: str
    createdAt: str
    updatedAt: str


class SpecDetail(BaseModel):
    id: str
    title: str
    project: str | None
    content: str
    status: str
    plan: dict[str, Any] | None
    context: dict[str, Any] | None
    createdAt: str
    updatedAt: str


class HealthResponse(BaseModel):
    status: str
    specsDir: str
    specsDirExists: bool
    specsCount: int
    timestamp: str


# ---------------------------------------------------------------------------
# Filesystem helpers
# ---------------------------------------------------------------------------


def _meta_path(spec_dir: Path) -> Path:
    return spec_dir / "meta.json"


def _spec_path(spec_dir: Path) -> Path:
    return spec_dir / "spec.md"


def _plan_path(spec_dir: Path) -> Path:
    return spec_dir / "implementation_plan.json"


def _status_path(spec_dir: Path) -> Path:
    return spec_dir / "status.json"


def _context_path(spec_dir: Path) -> Path:
    return spec_dir / "context.json"


def _read_json(path: Path) -> dict[str, Any] | None:
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return None
    return None


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_spec_summary(spec_id: str) -> SpecSummary | None:
    spec_dir = SPECS_DIR / spec_id
    if not spec_dir.is_dir():
        return None

    meta = _read_json(_meta_path(spec_dir)) or {}
    status_data = _read_json(_status_path(spec_dir)) or {}

    status = status_data.get("state", meta.get("status", "pending"))
    created_at = meta.get("createdAt", _now_iso())
    updated_at = meta.get("updatedAt", created_at)

    # Infer updatedAt from filesystem mtime as fallback
    try:
        mtime = spec_dir.stat().st_mtime
        updated_at = meta.get(
            "updatedAt",
            datetime.fromtimestamp(mtime, tz=timezone.utc).isoformat(),
        )
    except Exception:
        pass

    return SpecSummary(
        id=spec_id,
        title=meta.get("title", spec_id),
        project=meta.get("project"),
        status=status,
        createdAt=created_at,
        updatedAt=updated_at,
    )


def _load_spec_detail(spec_id: str) -> SpecDetail | None:
    spec_dir = SPECS_DIR / spec_id
    if not spec_dir.is_dir():
        return None

    meta = _read_json(_meta_path(spec_dir)) or {}
    status_data = _read_json(_status_path(spec_dir)) or {}
    plan = _read_json(_plan_path(spec_dir))
    context = _read_json(_context_path(spec_dir))

    content = ""
    if _spec_path(spec_dir).exists():
        content = _spec_path(spec_dir).read_text(encoding="utf-8")

    status = status_data.get("state", meta.get("status", "pending"))
    created_at = meta.get("createdAt", _now_iso())
    updated_at = meta.get("updatedAt", created_at)

    return SpecDetail(
        id=spec_id,
        title=meta.get("title", spec_id),
        project=meta.get("project"),
        content=content,
        status=status,
        plan=plan,
        context=context,
        createdAt=created_at,
        updatedAt=updated_at,
    )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@app.get("/health", response_model=HealthResponse)
def health(_: None = Depends(verify_token)) -> HealthResponse:
    """Health check — does not require specs dir to exist."""
    count = 0
    if SPECS_DIR.exists():
        count = sum(1 for d in SPECS_DIR.iterdir() if d.is_dir())
    return HealthResponse(
        status="ok",
        specsDir=str(SPECS_DIR),
        specsDirExists=SPECS_DIR.exists(),
        specsCount=count,
        timestamp=_now_iso(),
    )


@app.get("/specs", response_model=list[SpecSummary])
def list_specs(_: None = Depends(verify_token)) -> list[SpecSummary]:
    """List all specs, sorted by updatedAt descending."""
    if not SPECS_DIR.exists():
        return []
    summaries = []
    for entry in SPECS_DIR.iterdir():
        if entry.is_dir():
            summary = _load_spec_summary(entry.name)
            if summary:
                summaries.append(summary)
    summaries.sort(key=lambda s: s.updatedAt, reverse=True)
    return summaries


@app.get("/specs/{spec_id}", response_model=SpecDetail)
def get_spec(spec_id: str, _: None = Depends(verify_token)) -> SpecDetail:
    """Get full detail for one spec."""
    detail = _load_spec_detail(spec_id)
    if detail is None:
        raise HTTPException(status_code=404, detail=f"Spec '{spec_id}' not found")
    return detail


@app.get("/specs/{spec_id}/plan")
def get_spec_plan(
    spec_id: str, _: None = Depends(verify_token)
) -> dict[str, Any]:
    """Get the implementation plan for a spec (if it exists)."""
    spec_dir = SPECS_DIR / spec_id
    if not spec_dir.is_dir():
        raise HTTPException(status_code=404, detail=f"Spec '{spec_id}' not found")
    plan = _read_json(_plan_path(spec_dir))
    if plan is None:
        raise HTTPException(
            status_code=404, detail=f"No plan found for spec '{spec_id}'"
        )
    return plan


@app.post("/specs", response_model=SpecDetail, status_code=201)
def create_spec(
    body: SpecCreateRequest, _: None = Depends(verify_token)
) -> SpecDetail:
    """Create a new spec. Returns spec detail including generated ID."""
    SPECS_DIR.mkdir(parents=True, exist_ok=True)

    spec_id = str(uuid.uuid4())[:8]
    # Ensure uniqueness (very unlikely collision, but just in case)
    while (SPECS_DIR / spec_id).exists():
        spec_id = str(uuid.uuid4())[:8]

    spec_dir = SPECS_DIR / spec_id
    spec_dir.mkdir(parents=True)

    now = _now_iso()
    meta = {
        "id": spec_id,
        "title": body.title,
        "project": body.project,
        "status": "pending",
        "createdAt": now,
        "updatedAt": now,
    }
    _write_json(_meta_path(spec_dir), meta)
    _spec_path(spec_dir).write_text(body.content, encoding="utf-8")

    if body.context:
        _write_json(_context_path(spec_dir), body.context)

    detail = _load_spec_detail(spec_id)
    assert detail is not None
    return detail


@app.delete("/specs/{spec_id}", status_code=204)
def delete_spec(spec_id: str, _: None = Depends(verify_token)) -> None:
    """Delete a spec and all its files."""
    spec_dir = SPECS_DIR / spec_id
    if not spec_dir.is_dir():
        raise HTTPException(status_code=404, detail=f"Spec '{spec_id}' not found")
    shutil.rmtree(spec_dir)


# ---------------------------------------------------------------------------
# Dev entrypoint
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host=HOST, port=PORT, reload=False)
