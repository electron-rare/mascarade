#!/usr/bin/env python3
"""
Download and prepare real-world datasets for fine-tuning.
Converts HuggingFace datasets into the text format expected by fine_tuning_base.py

Datasets:
  - KiCad:   bshada/open-schematics (84K schematics)
             STEM-AI-mtl/Electrical-engineering (1.1K Q&A)
  - STM32:   MuratKomurcu/stm32-hal-dataset (29.7K HAL examples)
  - Generic: iamtarun/python_code_instructions_18k_alpaca (18K instruction/code)
             code_search_net (Python split, 500K function+docstring)

Usage:
  python download_datasets.py                    # Download all (default: 1000 samples each)
  python download_datasets.py --domain kicad     # Download KiCad only
  python download_datasets.py --domain stm32     # Download STM32 only
  python download_datasets.py --domain generic   # Download generic only
  python download_datasets.py --max-samples 5000 # More samples
  python download_datasets.py --all              # Download full datasets (can be large)
"""

import argparse
import os
import sys

SEPARATOR = "\n\n" + "=" * 80 + "\n\n"
OUTPUT_DIR = "./datasets"


def download_kicad(max_samples: int, output_dir: str) -> str:
    """Download and prepare KiCad/EDA datasets."""
    from datasets import load_dataset

    output_path = os.path.join(output_dir, "kicad_dataset.txt")
    samples = []

    # --- 1) open-schematics: real KiCad .kicad_sch files ---
    print("  Downloading bshada/open-schematics...")
    try:
        ds = load_dataset(
            "bshada/open-schematics",
            split="train",
            streaming=True,
        ).select_columns(["schematic", "description", "components_used"])
        count = 0
        schema_limit = int(max_samples * 0.7)  # 70% schematics
        for row in ds:
            schematic = row.get("schematic", "")
            description = row.get("description", "")
            components = row.get("components_used", "")
            if not schematic or len(schematic) < 50:
                continue
            # Truncate very long schematics to keep dataset manageable
            if len(schematic) > 4000:
                schematic = schematic[:4000] + "\n; ... (truncated)"
            text = ""
            if description:
                text += f"# {description}\n"
            if components:
                if isinstance(components, list):
                    components = ", ".join(components)
                text += f"# Components: {components}\n"
            text += schematic
            samples.append(text)
            count += 1
            if count >= schema_limit:
                break
        print(f"    Got {count} schematics")
    except Exception as e:
        print(f"    Failed to load open-schematics: {e}")

    # --- 2) Electrical-engineering Q&A (includes KiCad scripting) ---
    print("  Downloading STEM-AI-mtl/Electrical-engineering...")
    try:
        ds = load_dataset(
            "STEM-AI-mtl/Electrical-engineering",
            split="train",
            streaming=True,
        )
        count = 0
        qa_limit = int(max_samples * 0.3)  # 30% Q&A
        for row in ds:
            instruction = row.get("instruction", "")
            inp = row.get("input", "")
            output = row.get("output", "")
            if not instruction or not output:
                continue
            text = f"### Question: {instruction}"
            if inp:
                text += f"\n{inp}"
            text += f"\n\n### Answer:\n{output}"
            samples.append(text)
            count += 1
            if count >= qa_limit:
                break
        print(f"    Got {count} Q&A pairs")
    except Exception as e:
        print(f"    Failed to load Electrical-engineering: {e}")

    _write_dataset(output_path, samples)
    return output_path


def download_stm32(max_samples: int, output_dir: str) -> str:
    """Download and prepare STM32/embedded datasets."""
    from datasets import load_dataset

    output_path = os.path.join(output_dir, "stm32_dataset.txt")
    samples = []

    # --- 1) stm32-hal-dataset: instruction + HAL code ---
    print("  Downloading MuratKomurcu/stm32-hal-dataset...")
    try:
        ds = load_dataset(
            "MuratKomurcu/stm32-hal-dataset",
            split="train",
            streaming=True,
        )
        count = 0
        for row in ds:
            instruction = row.get("instruction", "")
            code = row.get("output", "") or row.get("code", "")
            if not code:
                continue
            text = ""
            if instruction:
                text += f"// Task: {instruction}\n"
            text += code
            samples.append(text)
            count += 1
            if count >= max_samples:
                break
        print(f"    Got {count} HAL examples")
    except Exception as e:
        print(f"    Failed to load stm32-hal-dataset: {e}")
        # Fallback: try alternate column names
        print("    Trying alternate loading...")
        try:
            ds = load_dataset(
                "MuratKomurcu/stm32-hal-dataset",
                split="train",
                streaming=True,
            )
            count = 0
            for row in ds:
                # Try all possible column combinations
                text_parts = []
                for key in row:
                    val = row[key]
                    if isinstance(val, str) and len(val) > 20:
                        text_parts.append(val)
                if text_parts:
                    samples.append("\n".join(text_parts))
                    count += 1
                if count >= max_samples:
                    break
            print(f"    Got {count} samples (fallback)")
        except Exception as e2:
            print(f"    Fallback also failed: {e2}")

    _write_dataset(output_path, samples)
    return output_path


def download_generic(max_samples: int, output_dir: str) -> str:
    """Download and prepare generic code datasets."""
    from datasets import load_dataset

    output_path = os.path.join(output_dir, "generic_dataset.txt")
    samples = []

    # --- 1) python_code_instructions_18k_alpaca ---
    print("  Downloading iamtarun/python_code_instructions_18k_alpaca...")
    try:
        ds = load_dataset(
            "iamtarun/python_code_instructions_18k_alpaca",
            split="train",
            streaming=True,
        )
        count = 0
        alpaca_limit = int(max_samples * 0.5)  # 50%
        for row in ds:
            instruction = row.get("instruction", "") or row.get("prompt", "")
            code = row.get("output", "") or row.get("code", "")
            if not code:
                continue
            text = f"### Instruction: {instruction}\n\n### Code:\n{code}"
            samples.append(text)
            count += 1
            if count >= alpaca_limit:
                break
        print(f"    Got {count} instruction/code pairs")
    except Exception as e:
        print(f"    Failed to load python_code_instructions: {e}")

    # --- 2) code_search_net (Python split) ---
    print("  Downloading code_search_net (Python)...")
    try:
        ds = load_dataset(
            "code_search_net",
            "python",
            split="train",
            streaming=True,
        )
        count = 0
        csn_limit = int(max_samples * 0.5)  # 50%
        for row in ds:
            docstring = row.get("func_documentation_string", "")
            code = row.get("func_code_string", "")
            if not code or len(code) < 30:
                continue
            text = ""
            if docstring:
                text += f'"""{docstring}"""\n'
            text += code
            samples.append(text)
            count += 1
            if count >= csn_limit:
                break
        print(f"    Got {count} function+docstring pairs")
    except Exception as e:
        print(f"    Failed to load code_search_net: {e}")

    _write_dataset(output_path, samples)
    return output_path


def _write_dataset(output_path: str, samples: list):
    """Write samples to text file in fine_tuning_base.py format."""
    if not samples:
        print(f"  No samples to write for {output_path}")
        return

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(SEPARATOR.join(samples))

    size_mb = os.path.getsize(output_path) / (1024 * 1024)
    print(f"  Wrote {len(samples)} samples to {output_path} ({size_mb:.1f} MB)")


def main():
    parser = argparse.ArgumentParser(description="Download datasets for fine-tuning")
    parser.add_argument(
        "--domain",
        choices=["kicad", "stm32", "generic", "all"],
        default="all",
        help="Which domain to download (default: all)",
    )
    parser.add_argument(
        "--max-samples",
        type=int,
        default=1000,
        help="Max samples per dataset (default: 1000)",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Download full datasets (can be very large)",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=OUTPUT_DIR,
        help=f"Output directory (default: {OUTPUT_DIR})",
    )
    args = parser.parse_args()

    output_dir = args.output_dir

    if args.all:
        args.max_samples = 999_999_999

    print("=" * 60)
    print("DATASET DOWNLOADER FOR FINE-TUNING")
    print("=" * 60)
    print(f"Max samples per dataset: {args.max_samples}")
    print(f"Output directory: {output_dir}")
    print("=" * 60)

    # Check dependencies
    try:
        from datasets import load_dataset  # noqa: F401
    except ImportError:
        print("Missing dependency: pip install datasets")
        sys.exit(1)

    domains = ["kicad", "stm32", "generic"] if args.domain == "all" else [args.domain]

    results = {}
    for domain in domains:
        print(f"\n{'—' * 60}")
        print(f"Downloading {domain.upper()} datasets...")
        print(f"{'—' * 60}")

        if domain == "kicad":
            results[domain] = download_kicad(args.max_samples, output_dir)
        elif domain == "stm32":
            results[domain] = download_stm32(args.max_samples, output_dir)
        elif domain == "generic":
            results[domain] = download_generic(args.max_samples, output_dir)

    print(f"\n{'=' * 60}")
    print("DONE")
    print(f"{'=' * 60}")
    for domain, path in results.items():
        if path and os.path.exists(path):
            size_mb = os.path.getsize(path) / (1024 * 1024)
            print(f"  {domain}: {path} ({size_mb:.1f} MB)")
    print("\nUsage with fine_tuning_base.py:")
    for domain, path in results.items():
        if path and os.path.exists(path):
            print(
                f"  python fine_tuning_base.py --domain {domain} --train --small --short-seq --dataset {path}"
            )


if __name__ == "__main__":
    main()
