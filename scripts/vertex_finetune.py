#!/usr/bin/env python3
"""
Fine-tune Gemini on Google Vertex AI.

Converts Mascarade datasets to Vertex AI JSONL format, uploads to GCS,
launches a supervised fine-tuning job, and tests the tuned model.

Prerequisites:
  pip install google-genai google-cloud-storage
  gcloud auth application-default login
  export GOOGLE_CLOUD_PROJECT=your-project-id

Usage:
  python scripts/vertex_finetune.py --domain stm32
  python scripts/vertex_finetune.py --domain kicad --model gemini-2.5-flash
  python scripts/vertex_finetune.py --domain generic --epochs 5
"""

import argparse
import json
import os
import sys
import time

# Domain-specific system instructions
SYSTEM_INSTRUCTIONS = {
    "kicad": "You are an expert KiCad and PCB design assistant. You help with schematic design, footprint creation, design rules, and KiCad Python scripting.",
    "stm32": "You are an expert STM32 embedded systems programmer. You help with HAL driver code, peripheral configuration (UART, SPI, I2C, GPIO, ADC, timers), and embedded C best practices.",
    "generic": "You are an expert programmer. You write clean, efficient, well-documented code and explain your reasoning.",
}

SEPARATOR = "=" * 80


def convert_dataset_to_vertex_jsonl(dataset_path: str, output_path: str, domain: str):
    """Convert text dataset to Vertex AI supervised fine-tuning JSONL format."""
    print(f"Converting {dataset_path} to Vertex AI format...")

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
            "systemInstruction": {
                "role": "system",
                "parts": [{"text": system_instruction}],
            },
            "contents": [
                {"role": "user", "parts": [{"text": question}]},
                {"role": "model", "parts": [{"text": answer}]},
            ],
        }
        jsonl_lines.append(json.dumps(entry, ensure_ascii=False))

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(jsonl_lines))

    print(f"  Wrote {len(jsonl_lines)} examples to {output_path}")
    return len(jsonl_lines)


def upload_to_gcs(local_path: str, bucket_name: str, blob_name: str) -> str:
    """Upload file to Google Cloud Storage."""
    from google.cloud import storage

    client = storage.Client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(blob_name)
    blob.upload_from_filename(local_path)
    gcs_uri = f"gs://{bucket_name}/{blob_name}"
    print(f"  Uploaded to {gcs_uri}")
    return gcs_uri


def launch_tuning_job(
    gcs_uri: str, domain: str, model: str, epochs: int, display_name: str
):
    """Launch a supervised fine-tuning job on Vertex AI."""
    from google import genai
    from google.genai import types

    project = os.environ.get("GOOGLE_CLOUD_PROJECT")
    if not project:
        print("ERROR: Set GOOGLE_CLOUD_PROJECT environment variable")
        sys.exit(1)

    client = genai.Client(
        vertexai=True,
        project=project,
        location="us-central1",
    )

    training_dataset = types.TuningDataset(gcs_uri=gcs_uri)

    print(f"Launching fine-tuning job: {display_name}")
    print(f"  Base model: {model}")
    print(f"  Epochs: {epochs}")

    tuning_job = client.tunings.tune(
        base_model=model,
        training_dataset=training_dataset,
        config=types.CreateTuningJobConfig(
            epoch_count=epochs,
            tuned_model_display_name=display_name,
        ),
    )

    print(f"  Job name: {tuning_job.name}")
    print(f"  Waiting for completion...")

    completed_states = {
        "JOB_STATE_SUCCEEDED",
        "JOB_STATE_FAILED",
        "JOB_STATE_CANCELLED",
    }

    while tuning_job.state not in completed_states:
        print(f"  State: {tuning_job.state}")
        time.sleep(30)
        tuning_job = client.tunings.get(name=tuning_job.name)

    if tuning_job.state == "JOB_STATE_SUCCEEDED":
        endpoint = tuning_job.tuned_model.endpoint
        print(f"\n  SUCCESS! Tuned model endpoint: {endpoint}")
        return client, endpoint
    else:
        print(f"\n  FAILED: {tuning_job.state}")
        return None, None


def test_tuned_model(client, endpoint: str, domain: str):
    """Test the fine-tuned model with domain-specific prompts."""
    test_prompts = {
        "kicad": [
            "Generate a KiCad schematic for a simple LED circuit with a current limiting resistor",
            "Write a KiCad Python script to create a custom footprint for a QFP-48 package",
        ],
        "stm32": [
            "Write STM32 HAL code to configure UART2 for 115200 baud and transmit a string",
            "Write STM32 HAL code to read an analog value from ADC1 channel 0",
        ],
        "generic": [
            "Write a Python function that implements merge sort",
            "Write a REST API endpoint using Flask that handles CRUD operations for users",
        ],
    }

    print("\nTesting tuned model:")
    print("-" * 60)

    for prompt in test_prompts.get(domain, test_prompts["generic"]):
        response = client.models.generate_content(
            model=endpoint,
            contents=prompt,
        )
        print(f"\nPrompt: {prompt}")
        print(f"Response: {response.text[:500]}")
        print("-" * 60)


def main():
    parser = argparse.ArgumentParser(description="Fine-tune Gemini on Vertex AI")
    parser.add_argument(
        "--domain",
        choices=["kicad", "stm32", "generic"],
        default="stm32",
    )
    parser.add_argument(
        "--model",
        default="gemini-2.5-flash-lite",
        help="Base model (default: gemini-2.5-flash-lite)",
    )
    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument(
        "--bucket",
        default=None,
        help="GCS bucket name (default: {project}-mascarade-ft)",
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

    project = os.environ.get("GOOGLE_CLOUD_PROJECT", "your-project")
    bucket = args.bucket or f"{project}-mascarade-ft"
    dataset_path = args.dataset or f"./datasets/{args.domain}_dataset.txt"
    jsonl_path = f"./datasets/{args.domain}_vertex.jsonl"
    display_name = f"mascarade-{args.domain}-{int(time.time())}"

    print("=" * 60)
    print(f"VERTEX AI FINE-TUNING - {args.domain}")
    print("=" * 60)
    print(f"  Model: {args.model}")
    print(f"  Dataset: {dataset_path}")
    print(f"  Epochs: {args.epochs}")
    print(f"  GCS bucket: {bucket}")
    print("=" * 60)

    if not os.path.exists(dataset_path):
        print(f"ERROR: Dataset not found: {dataset_path}")
        print(f"Run first: python download_datasets.py --domain {args.domain}")
        sys.exit(1)

    # Step 1: Convert to Vertex JSONL
    n_examples = convert_dataset_to_vertex_jsonl(dataset_path, jsonl_path, args.domain)

    if args.convert_only:
        print(f"\nJSONL ready at {jsonl_path} ({n_examples} examples)")
        print("Upload manually: gsutil cp {jsonl_path} gs://{bucket}/")
        return

    # Step 2: Upload to GCS
    print("\nUploading to GCS...")
    gcs_uri = upload_to_gcs(
        jsonl_path,
        bucket,
        f"datasets/{args.domain}_training.jsonl",
    )

    # Step 3: Launch fine-tuning
    print()
    client, endpoint = launch_tuning_job(
        gcs_uri, args.domain, args.model, args.epochs, display_name
    )

    if client and endpoint:
        # Step 4: Test
        test_tuned_model(client, endpoint, args.domain)

        # Save endpoint info
        info_path = f"./fine_tuned_models/{args.domain}_vertex_info.json"
        os.makedirs(os.path.dirname(info_path), exist_ok=True)
        with open(info_path, "w") as f:
            json.dump(
                {
                    "domain": args.domain,
                    "base_model": args.model,
                    "endpoint": endpoint,
                    "display_name": display_name,
                    "epochs": args.epochs,
                    "n_examples": n_examples,
                },
                f,
                indent=2,
            )
        print(f"\nEndpoint info saved to {info_path}")

    # Cost estimate
    token_estimate = n_examples * 200 * args.epochs  # rough avg 200 tokens/example
    if "lite" in args.model:
        cost = token_estimate / 1_000_000 * 1.0
    else:
        cost = token_estimate / 1_000_000 * 3.0
    print(f"\nEstimated cost: ~${cost:.2f} ({token_estimate:,} training tokens)")


if __name__ == "__main__":
    main()
