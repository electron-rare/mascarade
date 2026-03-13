#!/usr/bin/env python3
"""Prometheus exporter for fine-tuning pipeline metrics.

Reads finetune/runs/*/manifest.json files and exposes metrics for Prometheus.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from pathlib import Path
from typing import Any

try:
    from prometheus_client import Gauge, Info, start_http_server
except ImportError:
    print(
        "Error: prometheus_client not installed. Run: pip install prometheus_client",
        file=sys.stderr,
    )
    sys.exit(1)


DEFAULT_PORT = 9101
DEFAULT_INTERVAL = 15
DEFAULT_RUNS_DIR = Path(__file__).resolve().parent.parent.parent / "finetune" / "runs"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


# Prometheus metrics
run_status = Gauge(
    "finetune_run_status",
    "Status of fine-tuning run per domain (1=running, 2=completed, 3=error, 0=unknown)",
    ["run_label", "domain", "phase"],
)

domain_rows = Gauge(
    "finetune_domain_rows",
    "Number of rows processed per domain",
    ["run_label", "domain", "row_type"],
)

run_updated_timestamp = Gauge(
    "finetune_run_updated_timestamp",
    "Last update timestamp of the run manifest (unix epoch seconds)",
    ["run_label"],
)

run_info = Info(
    "finetune_run",
    "Information about the fine-tuning run",
)


def load_manifest(path: Path) -> dict[str, Any] | None:
    """Load and parse a manifest JSON file."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError) as exc:
        logger.warning("Failed to load manifest %s: %s", path, exc)
        return None


def find_manifests(runs_dir: Path) -> list[Path]:
    """Find all manifest.json files in the runs directory."""
    if not runs_dir.exists():
        logger.warning("Runs directory does not exist: %s", runs_dir)
        return []
    return sorted(
        runs_dir.glob("*/manifest.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )


def status_to_value(status: str) -> float:
    """Convert status string to numeric value for Gauge metric."""
    status_map = {
        "running": 1.0,
        "completed": 2.0,
        "error": 3.0,
        "failed": 3.0,
        "pending": 0.0,
    }
    return status_map.get(status.lower(), 0.0)


def parse_timestamp(ts_str: str) -> float:
    """Parse ISO timestamp string to unix epoch seconds."""
    try:
        # Handle format: 2024-03-13T14:30:45
        from datetime import datetime

        dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        return dt.timestamp()
    except (ValueError, AttributeError):
        logger.warning("Failed to parse timestamp: %s", ts_str)
        return 0.0


def update_metrics_from_manifest(manifest_path: Path) -> None:
    """Parse a manifest file and update Prometheus metrics."""
    manifest = load_manifest(manifest_path)
    if manifest is None:
        return

    run_label = manifest.get("run_label", manifest_path.parent.name)
    domains = manifest.get("domains", {})
    updated_at = manifest.get("updated_at", "")

    # Update run timestamp metric
    if updated_at:
        timestamp = parse_timestamp(updated_at)
        if timestamp > 0:
            run_updated_timestamp.labels(run_label=run_label).set(timestamp)

    # Update domain-level metrics
    for domain_label, domain_data in domains.items():
        # Distill phase status
        distill_status = domain_data.get("distill", {}).get("status", "unknown")
        run_status.labels(
            run_label=run_label,
            domain=domain_label,
            phase="distill",
        ).set(status_to_value(distill_status))

        # Train phase status
        train_status = domain_data.get("train", {}).get("status", "unknown")
        run_status.labels(
            run_label=run_label,
            domain=domain_label,
            phase="train",
        ).set(status_to_value(train_status))

        # Row counts
        merged_rows = domain_data.get("distill", {}).get("merged_rows", 0)
        distilled_rows = domain_data.get("distill", {}).get("distilled_rows", 0)

        if merged_rows:
            domain_rows.labels(
                run_label=run_label,
                domain=domain_label,
                row_type="merged",
            ).set(merged_rows)

        if distilled_rows:
            domain_rows.labels(
                run_label=run_label,
                domain=domain_label,
                row_type="distilled",
            ).set(distilled_rows)


def collect_metrics(runs_dir: Path) -> None:
    """Scan all manifests and update metrics."""
    manifests = find_manifests(runs_dir)
    logger.info("Found %d manifest(s) in %s", len(manifests), runs_dir)

    for manifest_path in manifests:
        update_metrics_from_manifest(manifest_path)


def main() -> int:
    """Main entry point for the exporter."""
    parser = argparse.ArgumentParser(
        description="Prometheus exporter for fine-tuning pipeline metrics"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=DEFAULT_PORT,
        help=f"Port to expose metrics on (default: {DEFAULT_PORT})",
    )
    parser.add_argument(
        "--runs-dir",
        type=Path,
        default=DEFAULT_RUNS_DIR,
        help=f"Path to finetune runs directory (default: {DEFAULT_RUNS_DIR})",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=DEFAULT_INTERVAL,
        help=f"Scrape interval in seconds (default: {DEFAULT_INTERVAL})",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Collect metrics once and exit (for testing)",
    )
    args = parser.parse_args()

    logger.info("Starting finetune metrics exporter on port %d", args.port)
    logger.info("Monitoring runs directory: %s", args.runs_dir)

    # Start HTTP server for Prometheus to scrape
    start_http_server(args.port)

    if args.once:
        collect_metrics(args.runs_dir)
        logger.info("Single collection complete")
        return 0

    # Continuous collection loop
    try:
        while True:
            collect_metrics(args.runs_dir)
            time.sleep(args.interval)
    except KeyboardInterrupt:
        logger.info("Exporter shutting down")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
