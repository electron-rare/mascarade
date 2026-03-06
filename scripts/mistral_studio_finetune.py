#!/usr/bin/env python3
"""
Fine-tune Mistral models on Mistral Studio.

Converts Mascarade datasets to Mistral Studio format, uploads to Hugging Face Hub,
launches a fine-tuning job, and tests the tuned model.

Prerequisites:
  pip install huggingface-hub datasets
  export HF_TOKEN=your-huggingface-token

Usage:
  python scripts/mistral_studio_finetune.py --domain stm32
  python scripts/mistral_studio_finetune.py --domain kicad --model mistral-7b
  python scripts/mistral_studio_finetune.py --domain generic --epochs 5
"""

import argparse
import json
import os
import sys
import time
from huggingface_hub import HfApi, login

# Domain-specific system instructions
SYSTEM_INSTRUCTIONS = {
    "kicad": "You are an expert KiCad and PCB design assistant. You help with schematic design, footprint creation, design rules, and KiCad Python scripting.",
    "stm32": "You are an expert STM32 embedded systems programmer. You help with HAL driver code, peripheral configuration (UART, SPI, I2C, GPIO, ADC, timers), and embedded C best practices.",
    "spice": "You are an expert circuit simulation engineer. You help with SPICE netlists, transient analysis, AC analysis, and analog circuit design.",
    "freecad": "You are an expert FreeCAD and mechanical design engineer. You help with 3D modeling, parametric design, and CAD scripting in Python.",
    "dsp": "You are an expert digital signal processing engineer. You help with filter design, FFT analysis, audio processing, and real-time DSP implementation.",
    "platformio": "You are an expert PlatformIO and embedded development specialist. You help with multi-platform builds, library management, and embedded debugging.",
    "power": "You are an expert power electronics engineer. You help with converter design, thermal analysis, and power circuit simulation.",
    "emc": "You are an expert EMC engineer. You help with electromagnetic compatibility analysis, PCB layout for EMC, and compliance testing.",
    "embedded": "You are an expert embedded systems engineer. You help with RTOS, bare-metal programming, and hardware-software co-design.",
    "components": "You are an expert electronic components specialist. You help with component selection, datasheet analysis, and replacement parts.",
    "generic": "You are an expert programmer. You write clean, efficient, well-documented code and explain your reasoning.",
}

SEPARATOR = "=" * 80


def convert_dataset_to_mistral_format(dataset_path: str, output_path: str, domain: str):
    """Convert text dataset to Mistral Studio JSONL format."""
    print(f"Converting {dataset_path} to Mistral Studio format...")

    with open(dataset_path, "r", encoding="utf-8") as f:
        content = f.read()

    samples = [s.strip() for s in content.split(SEPARATOR) if s.strip()]
    system_instruction = SYSTEM_INSTRUCTIONS.get(domain, SYSTEM_INSTRUCTIONS["generic"])

    jsonl_lines = []
    for sample in samples:
        # Split on ### patterns (instruction/answer format)
        if "### Question:" in sample and "### Answer:" in sample:
            parts = sample.split("### Answer:")
            question = parts[0].replace("### Question:", "").strip()
            answer = parts[1].strip()
        elif "### Instruction:" in sample and "### Code:" in sample:
            parts = sample.split("### Code:")
            question = parts[0].replace("### Instruction:", "").strip()
            answer = parts[1].strip()
        elif "// Task:" in sample:
            lines = sample.split("\n", 1)
            question = lines[0].replace("// Task:", "").strip()
            answer = lines[1].strip() if len(lines) > 1 else sample
        else:
            # Raw code/schematic: ask the model to explain or continue
            question = f"Explain and continue this code:\n{sample[:300]}"
            answer = sample

        if not question or not answer:
            continue

        entry = {
            "messages": [
                {"role": "system", "content": system_instruction},
                {"role": "user", "content": question},
                {"role": "assistant", "content": answer},
            ]
        }
        jsonl_lines.append(json.dumps(entry, ensure_ascii=False))

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(jsonl_lines))

    print(f"  Wrote {len(jsonl_lines)} examples to {output_path}")
    return len(jsonl_lines)


def upload_to_hub(local_path: str, repo_id: str, token: str):
    """Upload dataset to Hugging Face Hub."""
    login(token=token)
    api = HfApi()

    print(f"Uploading {local_path} to Hugging Face Hub...")
    api.upload_file(
        path_or_fileobj=local_path,
        path_in_repo="train.jsonl",
        repo_id=repo_id,
        repo_type="dataset",
    )

    dataset_url = f"https://huggingface.co/datasets/{repo_id}"
    print(f"  Dataset available at: {dataset_url}")
    return dataset_url


def launch_mistral_studio_job(
    dataset_repo: str,
    domain: str,
    model: str,
    epochs: int,
    token: str,
):
    """Launch a fine-tuning job on Mistral Studio."""
    import requests

    print("Launching Mistral Studio fine-tuning job...")
    print(f"  Base model: {model}")
    print(f"  Dataset: {dataset_repo}")
    print(f"  Epochs: {epochs}")

    # Mistral Studio API endpoint (hypothetical - adjust based on actual API)
    url = "https://api.mistral.ai/v1/finetune"

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": model,
        "training_dataset": dataset_repo,
        "epochs": epochs,
        "name": f"mascarade-{domain}-{int(time.time())}",
    }

    response = requests.post(url, headers=headers, json=payload)

    if response.status_code != 200:
        print(f"  ERROR: {response.status_code} - {response.text}")
        return None

    job_info = response.json()
    job_id = job_info.get("id")
    print(f"  Job ID: {job_id}")
    print("  Waiting for completion...")

    # Poll job status (simplified - adjust based on actual API)
    while True:
        status_response = requests.get(f"{url}/{job_id}", headers=headers)
        status = status_response.json().get("status")
        print(f"  Status: {status}")

        if status in ["completed", "failed"]:
            break

        time.sleep(30)

    if status == "completed":
        model_id = job_info.get("model_id")
        print(f"\n  SUCCESS! Fine-tuned model: {model_id}")
        return model_id
    else:
        print(f"\n  FAILED: {status}")
        return None


def test_tuned_model(model_id: str, domain: str, token: str):
    """Test the fine-tuned model with domain-specific prompts."""
    from mistralai.client import MistralClient

    client = MistralClient(api_key=token)

    test_prompts = {
        "kicad": [
            "Generate a KiCad schematic for a simple LED circuit with a current limiting resistor",
            "Write a KiCad Python script to create a custom footprint for a QFP-48 package",
        ],
        "stm32": [
            "Write STM32 HAL code to configure UART2 for 115200 baud and transmit a string",
            "Write STM32 HAL code to read an analog value from ADC1 channel 0",
        ],
        "spice": [
            "Write a SPICE netlist for a common emitter amplifier with bias network",
            "Simulate the frequency response of an RC low-pass filter",
        ],
        "freecad": [
            "Create a Python script in FreeCAD to model a gear with 20 teeth",
            "Explain how to use the Part Design workbench for parametric modeling",
        ],
        "dsp": [
            "Design a 5th order Butterworth low-pass filter with cutoff at 1kHz",
            "Write Python code to implement an FFT and plot the spectrum",
        ],
        "platformio": [
            "Create a PlatformIO configuration for ESP32 with WiFi and BLE support",
            "Explain how to manage libraries in PlatformIO",
        ],
        "power": [
            "Design a buck converter for 12V to 5V at 2A output",
            "Calculate the efficiency of a flyback converter",
        ],
        "emc": [
            "Explain PCB layout techniques for reducing EMI in high-speed designs",
            "Describe EMC testing procedures for CE certification",
        ],
        "embedded": [
            "Implement a FreeRTOS task for reading sensor data",
            "Explain interrupt priority management in ARM Cortex-M",
        ],
        "components": [
            "Recommend a replacement for the LM317 voltage regulator",
            "Compare MOSFET vs IGBT for high-power switching",
        ],
        "generic": [
            "Write a Python function that implements merge sort",
            "Write a REST API endpoint using Flask that handles CRUD operations for users",
        ],
    }

    print("\nTesting tuned model:")
    print("-" * 60)

    for prompt in test_prompts.get(domain, test_prompts["generic"]):
        response = client.chat(
            model=model_id,
            messages=[{"role": "user", "content": prompt}],
        )
        print(f"\nPrompt: {prompt}")
        print(f"Response: {response.choices[0].message.content[:500]}")
        print("-" * 60)


def main():
    parser = argparse.ArgumentParser(
        description="Fine-tune Mistral models on Mistral Studio"
    )
    parser.add_argument(
        "--domain",
        choices=[
            "kicad",
            "stm32",
            "spice",
            "freecad",
            "dsp",
            "platformio",
            "power",
            "emc",
            "embedded",
            "components",
            "generic",
        ],
        default="stm32",
    )
    parser.add_argument(
        "--model",
        default="mistral-7b",
        help="Base model (default: mistral-7b)",
    )
    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument(
        "--repo",
        default=None,
        help="Hugging Face repo ID (default: mascarade-{domain})",
    )
    parser.add_argument(
        "--dataset",
        default=None,
        help="Override dataset path",
    )
    parser.add_argument(
        "--convert-only",
        action="store_true",
        help="Only convert dataset to JSONL, don't launch job",
    )
    args = parser.parse_args()

    token = os.environ.get("HF_TOKEN")
    if not token and not args.convert_only:
        print("ERROR: Set HF_TOKEN environment variable")
        sys.exit(1)

    repo_id = args.repo or f"mascarade-{args.domain}"
    dataset_path = args.dataset or f"./datasets/{args.domain}_dataset.txt"
    jsonl_path = f"./datasets/{args.domain}_mistral.jsonl"

    print("=" * 60)
    print(f"MISTRAL STUDIO FINE-TUNING - {args.domain}")
    print("=" * 60)
    print(f"  Model: {args.model}")
    print(f"  Dataset: {dataset_path}")
    print(f"  Epochs: {args.epochs}")
    print(f"  HF Repo: {repo_id}")
    print("=" * 60)

    if not os.path.exists(dataset_path):
        print(f"ERROR: Dataset not found: {dataset_path}")
        print(f"Run first: python download_datasets.py --domain {args.domain}")
        sys.exit(1)

    # Step 1: Convert to Mistral format
    n_examples = convert_dataset_to_mistral_format(
        dataset_path, jsonl_path, args.domain
    )

    if args.convert_only:
        print(f"\nJSONL ready at {jsonl_path} ({n_examples} examples)")
        print("Upload manually to Hugging Face Hub")
        return

    # Step 2: Upload to Hugging Face Hub
    print("\nUploading to Hugging Face Hub...")
    upload_to_hub(jsonl_path, repo_id, token)

    # Step 3: Launch fine-tuning
    print()
    model_id = launch_mistral_studio_job(
        repo_id, args.domain, args.model, args.epochs, token
    )

    if model_id:
        # Step 4: Test
        test_tuned_model(model_id, args.domain, token)

        # Save model info
        info_path = f"./fine_tuned_models/{args.domain}_mistral_info.json"
        os.makedirs(os.path.dirname(info_path), exist_ok=True)
        with open(info_path, "w") as f:
            json.dump(
                {
                    "domain": args.domain,
                    "base_model": args.model,
                    "model_id": model_id,
                    "epochs": args.epochs,
                    "n_examples": n_examples,
                },
                f,
                indent=2,
            )
        print(f"\nModel info saved to {info_path}")


if __name__ == "__main__":
    main()
