#!/usr/bin/env python3
"""Export the Mascarade Core OpenAPI spec to docs/api/openapi.json."""

import json
import sys
from pathlib import Path

# Ensure core/ is importable
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "core"))

from mascarade.server import app  # noqa: E402

OUTPUT_DIR = ROOT / "docs" / "api"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_FILE = OUTPUT_DIR / "openapi.json"

spec = app.openapi()
OUTPUT_FILE.write_text(json.dumps(spec, indent=2, ensure_ascii=False) + "\n")

print(f"OpenAPI spec written to {OUTPUT_FILE.relative_to(ROOT)}")
