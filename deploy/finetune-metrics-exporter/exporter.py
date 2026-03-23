#!/usr/bin/env python3
"""Prometheus exporter for fine-tuning pipeline metrics."""

from __future__ import annotations

import argparse
import json
import logging
import time
from pathlib import Path
from typing import Any

from prometheus_client import Gauge, Info, start_http_server

logger = logging.getLogger(__name__)

# Metrics
finetune_run_status = Gauge(
    "finetune_run_status",
    "Fine-tuning run status (1=running, 2=completed, 3=failed, 0=idle)",
    ["run_label"],
)

finetune_domain_rows = Gauge(
    "finetune_domain_rows",
    "Number of rows for domain processing",
    ["run_label", "domain", "row_type"],
)

finetune_domain_status = Gauge(
    "finetune_domain_status",
    "Domain processing status (0=pending, 1=running, 2=completed, 3=failed)",
    ["run_label", "domain", "phase"],
)

finetune_run_updated = Gauge(
    "finetune_run_updated_timestamp",
    "Unix timestamp of last manifest update",
    ["run_label"],
)

finetune_run_info = Info(
    "finetune_run",
    "Fine-tuning run metadata",
)

finetune_active_jobs = Gauge(
    "finetune_active_jobs",
    "Number of currently running fine-tuning jobs",
)


def load_manifest(path: Path) -> dict[str, Any] | None:
    """Load manifest JSON file."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        logger.warning(f"Failed to load manifest {path}: {e}")
        return None


def find_manifests(runs_dir: Path) -> list[Path]:
    """Find all manifest.json files in runs directory."""
    if not runs_dir.exists():
        logger.warning(f"Runs directory does not exist: {runs_dir}")
        return []
    return sorted(
        runs_dir.glob("*/manifest.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )


def status_to_value(status: str | None) -> float:
    """Convert status string to numeric value for Prometheus."""
    if status is None:
        return 0.0
    status_map = {
        "idle": 0.0,
        "pending": 0.0,
        "running": 1.0,
        "completed": 2.0,
        "failed": 3.0,
        "error": 3.0,
    }
    return status_map.get(status.lower(), 0.0)


def parse_timestamp(ts_str: str | None) -> float:
    """Parse timestamp string to Unix timestamp."""
    if not ts_str:
        return 0.0
    try:
        # Parse format like "2026-03-13T02:06:45"
        return time.mktime(time.strptime(ts_str, "%Y-%m-%dT%H:%M:%S"))
    except Exception as e:
        logger.warning(f"Failed to parse timestamp '{ts_str}': {e}")
        return 0.0


def update_metrics(runs_dir: Path) -> None:
    """Update Prometheus metrics from manifest files."""
    manifests = find_manifests(runs_dir)

    # Track which runs we've seen and count active jobs
    seen_runs = set()
    active_jobs_count = 0

    for manifest_path in manifests:
        manifest = load_manifest(manifest_path)
        if not manifest:
            continue

        run_label = manifest.get("run_label", manifest_path.parent.name)
        seen_runs.add(run_label)

        # Update run-level metrics
        updated_at = manifest.get("updated_at", "")
        finetune_run_updated.labels(run_label=run_label).set(
            parse_timestamp(updated_at)
        )

        # Overall run status (derived from domains)
        domains = manifest.get("domains", {})
        if not domains:
            finetune_run_status.labels(run_label=run_label).set(0.0)
        else:
            # Check if any domain is running/failed
            has_running = False
            has_failed = False
            all_completed = True

            for domain_label, domain_data in domains.items():
                distill_status = domain_data.get("distill", {}).get("status", "pending")
                train_status = domain_data.get("train", {}).get("status", "pending")

                for status in [distill_status, train_status]:
                    if status in ("running",):
                        has_running = True
                        all_completed = False
                    elif status in ("failed", "error"):
                        has_failed = True
                        all_completed = False
                    elif status not in ("completed",):
                        all_completed = False

            if has_failed:
                run_status = 3.0  # failed
            elif has_running:
                run_status = 1.0  # running
            elif all_completed:
                run_status = 2.0  # completed
            else:
                run_status = 0.0  # idle/pending

            finetune_run_status.labels(run_label=run_label).set(run_status)

            # Count active jobs
            if run_status == 1.0:
                active_jobs_count += 1

        # Domain-level metrics
        for domain_label, domain_data in domains.items():
            # Row counts
            merged_rows = domain_data.get("distill", {}).get("merged_rows", 0) or 0
            distilled_rows = (
                domain_data.get("distill", {}).get("distilled_rows", 0) or 0
            )

            finetune_domain_rows.labels(
                run_label=run_label,
                domain=domain_label,
                row_type="merged",
            ).set(merged_rows)

            finetune_domain_rows.labels(
                run_label=run_label,
                domain=domain_label,
                row_type="distilled",
            ).set(distilled_rows)

            # Phase status
            distill_status = domain_data.get("distill", {}).get("status", "pending")
            train_status = domain_data.get("train", {}).get("status", "pending")

            finetune_domain_status.labels(
                run_label=run_label,
                domain=domain_label,
                phase="distill",
            ).set(status_to_value(distill_status))

            finetune_domain_status.labels(
                run_label=run_label,
                domain=domain_label,
                phase="train",
            ).set(status_to_value(train_status))

    # Update active jobs count
    finetune_active_jobs.set(active_jobs_count)


def main() -> int:
    """Main entry point for the exporter."""
    parser = argparse.ArgumentParser(
        description="Prometheus exporter for fine-tuning pipeline metrics"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=9101,
        help="Port to expose metrics on (default: 9101)",
    )
    parser.add_argument(
        "--runs-dir",
        default="/workspace/finetune/runs",
        help="Directory containing finetune runs (default: /workspace/finetune/runs)",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=15,
        help="Scrape interval in seconds (default: 15)",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run once and exit (for testing)",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable verbose logging",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    runs_dir = Path(args.runs_dir)
    logger.info(f"Starting metrics exporter on port {args.port}")
    logger.info(f"Monitoring runs directory: {runs_dir}")
    logger.info(f"Scrape interval: {args.interval}s")

    # Start HTTP server for Prometheus
    start_http_server(args.port)

    if args.once:
        update_metrics(runs_dir)
        logger.info("Single scrape completed, exiting")
        return 0

    # Continuous scraping
    try:
        while True:
            update_metrics(runs_dir)
            time.sleep(args.interval)
    except KeyboardInterrupt:
        logger.info("Exporter stopped by user")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
