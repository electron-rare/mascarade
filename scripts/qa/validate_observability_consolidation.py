#!/usr/bin/env python3
"""Validate observability consolidation assets for L2.

Checks that required dashboards and Prometheus alert rules exist and include
the minimum signal set used by Mascarade runtime operations.
"""

from __future__ import annotations

import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]

DASHBOARDS = {
    "deploy/grafana/provisioning/dashboards/json/mascarade-p2p-mesh.json": [
        "mascarade_p2p_peer_vram_gb",
        "mascarade_p2p_local_vram_gb",
        "mascarade_p2p_routing_vram_skips_total",
    ],
    "deploy/grafana/provisioning/dashboards/json/finetune-progress.json": [
        "finetune_active_jobs",
        "nvidia_gpu_utilization",
    ],
}

ALERTS_FILE = "deploy/prometheus/alerts/p2p.yml"
REQUIRED_ALERTS = {
    "MascaradeP2PMeshTooSmall",
    "MascaradeGPUNodeDown",
    "MascaradeQdrantDown",
    "MascaradeRedisDown",
}


def _load_dashboard_queries(path: Path) -> list[str]:
    data = json.loads(path.read_text())
    queries: list[str] = []
    for panel in data.get("panels", []):
        for target in panel.get("targets", []):
            expr = target.get("expr")
            if expr:
                queries.append(expr)
    return queries


def _extract_alert_names(path: Path) -> set[str]:
    text = path.read_text()
    return set(re.findall(r"-\s+alert:\s+([A-Za-z0-9_]+)", text))


def main() -> int:
    errors: list[str] = []
    warnings: list[str] = []

    for rel_path, required_queries in DASHBOARDS.items():
        full_path = ROOT / rel_path
        if not full_path.exists():
            errors.append(f"missing dashboard: {rel_path}")
            continue

        try:
            queries = _load_dashboard_queries(full_path)
        except Exception as exc:  # pragma: no cover
            errors.append(f"failed to parse dashboard {rel_path}: {exc}")
            continue

        for needle in required_queries:
            if not any(needle in expr for expr in queries):
                errors.append(f"dashboard {rel_path} missing query containing '{needle}'")

        if len(queries) < 3:
            warnings.append(f"dashboard {rel_path} has few queries ({len(queries)})")

    alert_path = ROOT / ALERTS_FILE
    if not alert_path.exists():
        errors.append(f"missing alerts file: {ALERTS_FILE}")
    else:
        alert_names = _extract_alert_names(alert_path)
        for name in sorted(REQUIRED_ALERTS):
            if name not in alert_names:
                errors.append(f"alerts file missing rule: {name}")

    if warnings:
        for warning in warnings:
            print(f"[WARN] {warning}")

    if errors:
        for error in errors:
            print(f"[ERROR] {error}")
        return 1

    print("[OK] observability consolidation checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())