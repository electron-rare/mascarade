#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="$(cd -- "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${REPO_DIR}/.env"
MEM0_URL="${MEM0_URL:-}"
MEM0_KEEP="${MEM0_KEEP:-0}"
MEM0_CONTAINER_NAME="${MEM0_CONTAINER_NAME:-mascarade-mem0}"
SMOKE_STAMP="${MEM0_SMOKE_STAMP:-$(date +%s)}"
MEM0_SMOKE_USER="${MEM0_SMOKE_USER:-mascarade-smoke-user-${SMOKE_STAMP}}"
MEM0_SMOKE_APP="${MEM0_SMOKE_APP:-mascarade-smoke-${SMOKE_STAMP}}"
MEM0_SMOKE_TOKEN="${MEM0_SMOKE_TOKEN:-mem0-smoke-${SMOKE_STAMP}}"

usage() {
  cat <<'EOF'
Usage: bash scripts/smoke_mem0.sh [--url URL] [--container NAME] [--keep]

Runs a functional Mem0 smoke on the current stack:
- create memory
- list memories
- filter memories
- delete memory

Options:
  --url URL         Override the Mem0 base URL (default: http://127.0.0.1:$MEM0_PORT)
  --container NAME  Override the Mem0 container name used for bootstrap
  --keep            Keep the smoke memory instead of deleting it
  -h, --help        Show this help
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --url)
      [[ $# -ge 2 ]] || { echo "Missing value for --url" >&2; exit 2; }
      MEM0_URL="$2"
      shift 2
      ;;
    --keep)
      MEM0_KEEP=1
      shift
      ;;
    --container)
      [[ $# -ge 2 ]] || { echo "Missing value for --container" >&2; exit 2; }
      MEM0_CONTAINER_NAME="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

if [[ -z "$MEM0_URL" && -f "$ENV_FILE" ]]; then
  MEM0_PORT="$(
    sed -n 's/^MEM0_PORT="\{0,1\}\([0-9][0-9]*\)"\{0,1\}$/\1/p' "$ENV_FILE" | tail -n 1
  )"
  MEM0_URL="http://127.0.0.1:${MEM0_PORT:-3300}"
fi

MEM0_URL="${MEM0_URL:-http://127.0.0.1:3300}"

docker exec -i \
  -e MEM0_BOOTSTRAP_USER="$MEM0_SMOKE_USER" \
  -e MEM0_BOOTSTRAP_APP="$MEM0_SMOKE_APP" \
  "$MEM0_CONTAINER_NAME" python - <<'PY'
import os

from app.database import SessionLocal
from app.utils.db import get_user_and_app

session = SessionLocal()
try:
    get_user_and_app(
        session,
        os.environ["MEM0_BOOTSTRAP_USER"],
        os.environ["MEM0_BOOTSTRAP_APP"],
    )
finally:
    session.close()
PY

MEM0_URL="$MEM0_URL" MEM0_KEEP="$MEM0_KEEP" \
MEM0_SMOKE_USER="$MEM0_SMOKE_USER" MEM0_SMOKE_APP="$MEM0_SMOKE_APP" MEM0_SMOKE_TOKEN="$MEM0_SMOKE_TOKEN" \
python3 - <<'PY'
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

base_url = os.environ["MEM0_URL"].rstrip("/")
keep = os.environ.get("MEM0_KEEP") == "1"
user = os.environ["MEM0_SMOKE_USER"]
app = os.environ["MEM0_SMOKE_APP"]
token = os.environ["MEM0_SMOKE_TOKEN"]
text = f"The user {user} has the unique smoke token {token} and prefers Helix editor."


def request(method, path, *, params=None, payload=None):
    url = base_url + path
    if params:
        url += "?" + urllib.parse.urlencode(params, doseq=True)
    body = None
    headers = {}
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=60) as response:
            raw = response.read().decode("utf-8")
            parsed = json.loads(raw) if raw else None
            print(f"{method} {path} {response.status}")
            if parsed is not None:
                print(json.dumps(parsed, indent=2))
            return parsed
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        print(f"{method} {path} {exc.code}", file=sys.stderr)
        if raw:
            print(raw, file=sys.stderr)
        raise


create = request(
    "POST",
    "/api/v1/memories/",
    payload={
        "text": text,
        "user_id": user,
        "app": app,
        "metadata": {"scope": "smoke", "source": "repo-script", "token": token},
    },
)
if not create or "id" not in create:
    raise SystemExit("Mem0 smoke failed: no persisted memory returned on create")

memory_id = create["id"]
app_id = create["app_id"]

listing = request(
    "GET",
    "/api/v1/memories/",
    params={
        "user_id": user,
        "app_id": app_id,
        "page": 1,
        "size": 20,
        "search_query": token,
    },
)
if memory_id not in [item.get("id") for item in listing.get("items", [])]:
    raise SystemExit(f"Mem0 smoke failed: {memory_id} missing from list response")

filtered = request(
    "POST",
    "/api/v1/memories/filter",
    payload={
        "user_id": user,
        "page": 1,
        "size": 20,
        "app_ids": [app_id],
        "search_query": token,
    },
)
if memory_id not in [item.get("id") for item in filtered.get("items", [])]:
    raise SystemExit(f"Mem0 smoke failed: {memory_id} missing from filter response")

if not keep:
    request(
        "DELETE",
        "/api/v1/memories/",
        payload={"memory_ids": [memory_id], "user_id": user},
    )

print(f"Mem0 smoke passed for {token}")
PY
