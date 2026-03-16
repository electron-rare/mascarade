#!/usr/bin/env python3
"""Prepare training dataset for domain routing ML classifier from historical logs.

This script extracts historical request logs and labels them by domain to create
a training dataset for the ML classifier used in domain-based routing.

Target: 10k+ labeled samples across domains (spice, kicad, stm32, electronics, code).
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("prepare_classifier_dataset")


@dataclass
class TrainingSample:
    """A labeled training sample for the ML classifier."""

    text: str
    domain: str
    timestamp: datetime | None = None
    provider: str | None = None
    model: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "text": self.text,
            "domain": self.domain,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "provider": self.provider,
            "model": self.model,
        }


def detect_domain(content: str) -> str | None:
    """
    Detect domain from message content based on keywords.

    This is the same logic used in the router for domain detection.

    Args:
        content: Text content to analyze

    Returns:
        Detected domain or None
    """
    # Keywords for each domain
    domain_keywords = {
        "spice": ["spice", "simulation", "ngspice", "ltspice", "circuit simulation"],
        "kicad": ["kicad", "pcb", "schematic", "footprint", "kicad_pcb"],
        "stm32": ["stm32", "arm cortex", "hal", "cubemx", "stm32f", "stm32l"],
        "electronics": [
            "circuit",
            "resistor",
            "capacitor",
            "transistor",
            "voltage",
            "current",
            "amplifier",
            "oscillator",
        ],
        "code": [
            "python",
            "javascript",
            "function",
            "class",
            "api",
            "algorithm",
            "debug",
            "refactor",
        ],
    }

    # Normalize content to lowercase for matching
    content_lower = content.lower()

    # Check for domain keywords
    for domain, keywords in domain_keywords.items():
        if any(keyword in content_lower for keyword in keywords):
            return domain

    return None


def extract_from_clickhouse(limit: int = 20000) -> list[TrainingSample]:
    """
    Extract historical logs from ClickHouse database.

    Args:
        limit: Maximum number of samples to extract

    Returns:
        List of training samples
    """
    samples: list[TrainingSample] = []

    try:
        # Try to import clickhouse and connect
        import clickhouse_connect

        # Add core to path to import config
        sys.path.insert(0, str(Path(__file__).parent.parent / "core"))
        from mascarade.config import settings

        # Parse ClickHouse URL
        url = getattr(settings, "clickhouse_host", "http://clickhouse:8123")
        url = url.replace("http://", "").replace("https://", "")
        if ":" in url:
            host, port_str = url.split(":", 1)
            port = int(port_str.split("/")[0])
        else:
            host = url
            port = 8123

        user = getattr(settings, "clickhouse_user", "langfuse")
        password_obj = getattr(settings, "clickhouse_password", "")
        password = password_obj.get_secret_value() if hasattr(password_obj, "get_secret_value") else str(password_obj)
        database = getattr(settings, "clickhouse_database", "default")

        logger.info(
            "Connecting to ClickHouse: %s@%s:%s/%s",
            user,
            host,
            port,
            database,
        )

        # Create synchronous client for this script
        client = clickhouse_connect.get_client(
            host=host,
            port=port,
            username=user,
            password=password,
            database=database,
        )

        # Query for cost events with message content if available
        # Note: The schema might not have message content, so we'll handle that
        query = f"""
        SELECT
            timestamp,
            provider,
            model,
            agent
        FROM cost_events
        WHERE success = 1
        ORDER BY timestamp DESC
        LIMIT {limit}
        """

        result = client.query(query)
        logger.info("Fetched %d rows from ClickHouse", len(result.result_rows))

        # Note: ClickHouse cost_events table doesn't store message content
        # This is a placeholder - in production, you'd need to add message logging
        # For now, we'll note this limitation
        logger.warning(
            "ClickHouse cost_events table does not store message content. "
            "Consider adding a separate messages table or using log files."
        )

        client.close()

    except ImportError:
        logger.warning("clickhouse_connect not available, skipping ClickHouse extraction")
    except Exception as exc:
        logger.warning("Failed to extract from ClickHouse: %s", exc)

    return samples


def generate_synthetic_samples(count: int = 10000) -> list[TrainingSample]:
    """
    Generate synthetic training samples for demonstration.

    In production, replace this with real historical data extraction.

    Args:
        count: Number of samples to generate

    Returns:
        List of synthetic training samples
    """
    logger.info("Generating %d synthetic samples for demonstration", count)

    # Sample prompts for each domain
    domain_samples = {
        "spice": [
            "Can you help me simulate this circuit with SPICE?",
            "I need to run an ngspice simulation for my amplifier design",
            "How do I set up an LTspice circuit simulation?",
            "What's the syntax for a SPICE transient analysis?",
            "Debug this circuit simulation netlist",
        ],
        "kicad": [
            "How do I create a PCB footprint in KiCad?",
            "I need help with KiCad schematic capture",
            "What's the best way to route traces on this PCB?",
            "How do I generate gerber files from KiCad?",
            "Help me fix this kicad_pcb file syntax error",
        ],
        "stm32": [
            "How do I configure STM32 peripherals with CubeMX?",
            "I need help with STM32 HAL library for UART",
            "What's the STM32F4 timer configuration?",
            "Debug this ARM Cortex-M code for STM32L0",
            "How do I set up DMA on STM32?",
        ],
        "electronics": [
            "Calculate the resistor value for this LED circuit",
            "What capacitor should I use for this voltage regulator?",
            "How does this transistor amplifier work?",
            "I need to measure the current through this circuit",
            "Design an RC oscillator with these specifications",
        ],
        "code": [
            "Write a Python function to parse JSON data",
            "How do I debug this JavaScript async function?",
            "Refactor this class to use better design patterns",
            "Create a REST API endpoint with error handling",
            "Optimize this algorithm for better performance",
        ],
    }

    samples: list[TrainingSample] = []
    samples_per_domain = count // len(domain_samples)

    for domain, prompts in domain_samples.items():
        for i in range(samples_per_domain):
            # Cycle through sample prompts
            text = prompts[i % len(prompts)]

            # Add some variation
            if i % 3 == 0:
                text = text + " Thanks!"
            elif i % 3 == 1:
                text = "Hi, " + text.lower()

            sample = TrainingSample(
                text=text,
                domain=domain,
                timestamp=datetime.now(),
                provider="synthetic",
                model="synthetic",
            )
            samples.append(sample)

    logger.info("Generated %d synthetic samples across %d domains", len(samples), len(domain_samples))
    return samples


def prepare_dataset(
    output_path: Path,
    min_samples: int = 10000,
    dry_run: bool = False,
) -> None:
    """
    Prepare the training dataset from historical logs.

    Args:
        output_path: Path to write the dataset (JSONL format)
        min_samples: Minimum number of samples to collect
        dry_run: If True, preview without writing files
    """
    logger.info("Starting dataset preparation (dry_run=%s)", dry_run)

    # Extract from ClickHouse if available
    samples = extract_from_clickhouse(limit=min_samples * 2)

    # If not enough samples, generate synthetic data for demonstration
    if len(samples) < min_samples:
        logger.info(
            "Only %d samples from ClickHouse, generating synthetic data to reach %d samples",
            len(samples),
            min_samples,
        )
        synthetic = generate_synthetic_samples(count=min_samples - len(samples))
        samples.extend(synthetic)

    # Filter out samples without detected domains
    labeled_samples = []
    for sample in samples:
        if sample.domain:
            labeled_samples.append(sample)
        else:
            # Try to detect domain from text
            detected = detect_domain(sample.text)
            if detected:
                sample.domain = detected
                labeled_samples.append(sample)

    logger.info(
        "Labeled %d/%d samples (%.1f%%)",
        len(labeled_samples),
        len(samples),
        100 * len(labeled_samples) / len(samples) if samples else 0,
    )

    # Show domain distribution
    domain_counts = Counter(s.domain for s in labeled_samples)
    logger.info("Domain distribution:")
    for domain, count in domain_counts.most_common():
        logger.info("  %s: %d samples (%.1f%%)", domain, count, 100 * count / len(labeled_samples))

    # Preview samples
    logger.info("\nSample preview (first 3 per domain):")
    for domain in sorted(domain_counts.keys()):
        domain_samples = [s for s in labeled_samples if s.domain == domain][:3]
        logger.info("\n  Domain: %s", domain)
        for sample in domain_samples:
            logger.info("    - %s", sample.text[:80] + "..." if len(sample.text) > 80 else sample.text)

    if dry_run:
        logger.info("\n[DRY RUN] Would write %d samples to %s", len(labeled_samples), output_path)
        logger.info("[DRY RUN] No files written")
        return

    # Write to JSONL format
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w") as f:
        for sample in labeled_samples:
            json.dump(sample.to_dict(), f)
            f.write("\n")

    logger.info("Wrote %d samples to %s", len(labeled_samples), output_path)

    # Write metadata
    metadata_path = output_path.with_suffix(".meta.json")
    metadata = {
        "created_at": datetime.now().isoformat(),
        "total_samples": len(labeled_samples),
        "domain_distribution": dict(domain_counts),
        "source": "clickhouse + synthetic" if len(samples) > len(labeled_samples) else "synthetic",
    }

    with metadata_path.open("w") as f:
        json.dump(metadata, f, indent=2)

    logger.info("Wrote metadata to %s", metadata_path)


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Prepare ML classifier training dataset from historical request logs"
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/classifier_training_dataset.jsonl"),
        help="Output path for the dataset (JSONL format)",
    )
    parser.add_argument(
        "--min-samples",
        type=int,
        default=10000,
        help="Minimum number of samples to collect (default: 10000)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview dataset without writing files",
    )

    args = parser.parse_args()

    try:
        prepare_dataset(
            output_path=args.output,
            min_samples=args.min_samples,
            dry_run=args.dry_run,
        )
        logger.info("Dataset preparation complete")
        return 0
    except Exception as exc:
        logger.error("Dataset preparation failed: %s", exc, exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
