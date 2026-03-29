#!/usr/bin/env python3
"""Lightweight documentation coherence checks against code/contracts.

This script intentionally checks invariants that should remain stable and actionable.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

README_FR = REPO / "README_FR.md"
SPEC = REPO / "SPEC_DEPLOIEMENT_VM_ORCHESTRATION.md"
COMPOSE = REPO / "docker-compose.yml"
API_INDEX = REPO / "api" / "src" / "index.ts"
API_AGENTS = REPO / "api" / "src" / "routes" / "agents.ts"
API_OPENAPI = REPO / "api" / "openapi.yaml"
CORE_AUTH = REPO / "core" / "mascarade" / "auth.py"
CORE_HEALTH = REPO / "core" / "mascarade" / "routers" / "health.py"


def read_text(path: Path) -> str:
    if not path.exists():
        raise SystemExit(f"[FAIL] Missing file: {path}")
    return path.read_text(encoding="utf-8", errors="replace")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"[FAIL] {message}")


def main() -> int:
    readme_fr = read_text(README_FR)
    spec = read_text(SPEC)
    compose = read_text(COMPOSE)
    api_index = read_text(API_INDEX)
    api_agents = read_text(API_AGENTS)
    openapi = read_text(API_OPENAPI)
    core_auth = read_text(CORE_AUTH)
    core_health = read_text(CORE_HEALTH)

    # 1) README FR perimeter: Open Buro / La Suite removed per product scope decision
    require("Open Buro" not in readme_fr, "README_FR should not mention Open Buro")
    require("La Suite Numerique" not in readme_fr, "README_FR should not mention La Suite Numerique")

    # 2) SPEC auth contract should map to code
    require("MASCARADE_API_KEY" in spec, "SPEC should reference MASCARADE_API_KEY")
    require("MASCARADE_API_KEY" in core_auth, "core auth should implement MASCARADE_API_KEY")
    require("Authorization" in api_index, "API index should propagate Authorization headers")

    # 3) SPEC volume contract core-data should exist in compose
    require("core-data" in spec, "SPEC should mention core-data")
    require(re.search(r"core-data\s*:\s*/app/data", compose) is not None, "docker-compose should mount core-data to /app/data")

    # 4) Ops endpoint contract via API gateway
    require("/api/agents/metrics" in spec, "SPEC should mention /api/agents/metrics")
    require('agents.get("/metrics"' in api_agents, "API agents route should expose /metrics")
    require('/api/agents/metrics' in openapi, "OpenAPI should expose /api/agents/metrics")

    # 5) Health endpoints in core/api contract
    require("GET /health" in spec or "/health" in spec, "SPEC should mention health endpoint")
    require('@router.get("/health")' in core_health, "Core should expose /health")

    print("[OK] Documentation coherence checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
