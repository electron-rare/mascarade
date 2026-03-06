#!/usr/bin/env python3
"""
Fine-tune models on AWS Bedrock using Mascarade datasets.

Converts ShareGPT JSONL datasets to Bedrock format, uploads to S3,
and manages fine-tuning jobs.

Usage:
    # Convert dataset
    python bedrock_finetune.py convert stm32

    # Convert all datasets
    python bedrock_finetune.py convert-all

    # Upload to S3 and start fine-tuning
    python bedrock_finetune.py train stm32

    # Check job status
    python bedrock_finetune.py status <job-arn>

    # List fine-tuned models
    python bedrock_finetune.py list
"""

import argparse
import json
import sys
import time
from pathlib import Path

import boto3
from botocore.exceptions import ClientError

SCRIPT_DIR = Path(__file__).parent
DATASETS_DIR = SCRIPT_DIR / "datasets"
BEDROCK_DIR = SCRIPT_DIR / "datasets" / "bedrock"

DOMAINS = ["stm32", "spice", "iot", "power", "dsp", "emc", "kicad", "embedded"]

# Bedrock fine-tuning supports these base models
BASE_MODELS = {
    "llama3.1-8b": "meta.llama3-1-8b-instruct-v1:0",
    "llama3.1-70b": "meta.llama3-1-70b-instruct-v1:0",
    "mistral-7b": "mistral.mistral-7b-instruct-v0:2",
}

DEFAULT_BASE_MODEL = "llama3.1-8b"


def convert_sharegpt_to_bedrock(input_path: Path, output_path: Path) -> int:
    """Convert ShareGPT JSONL to Bedrock fine-tuning format.

    Bedrock expects JSONL with {"prompt": "...", "completion": "..."}.
    We fold system + user into prompt, and gpt response into completion.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    count = 0

    with open(input_path) as fin, open(output_path, "w") as fout:
        for line in fin:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue

            conversations = entry.get("conversations", [])
            if len(conversations) < 2:
                continue

            system_msg = ""
            user_msg = ""
            assistant_msg = ""

            for turn in conversations:
                role = turn.get("from", "")
                value = turn.get("value", "")
                if role == "system":
                    system_msg = value
                elif role == "human":
                    user_msg = value
                elif role == "gpt":
                    assistant_msg = value

            if not user_msg or not assistant_msg:
                continue

            # Build prompt with system context
            prompt_parts = []
            if system_msg:
                prompt_parts.append(f"[System: {system_msg}]\n\n")
            prompt_parts.append(user_msg)

            bedrock_entry = {
                "prompt": "".join(prompt_parts),
                "completion": assistant_msg,
            }
            fout.write(json.dumps(bedrock_entry, ensure_ascii=False) + "\n")
            count += 1

    return count


def convert_domain(domain: str) -> Path:
    """Convert a single domain dataset."""
    input_path = DATASETS_DIR / f"{domain}_chat.jsonl"
    output_path = BEDROCK_DIR / f"{domain}_bedrock.jsonl"

    if not input_path.exists():
        print(f"  Skip {domain}: {input_path} not found")
        return None

    count = convert_sharegpt_to_bedrock(input_path, output_path)
    size_mb = output_path.stat().st_size / (1024 * 1024)
    print(f"  {domain}: {count} examples -> {output_path.name} ({size_mb:.1f} MB)")
    return output_path


def cmd_convert(args):
    """Convert datasets to Bedrock format."""
    domains = DOMAINS if args.domain == "all" else [args.domain]
    print(f"Converting {len(domains)} dataset(s) to Bedrock format...\n")
    for domain in domains:
        convert_domain(domain)
    print(f"\nOutput: {BEDROCK_DIR}/")


def cmd_train(args):
    """Upload to S3 and start Bedrock fine-tuning job."""
    domain = args.domain
    bedrock_file = BEDROCK_DIR / f"{domain}_bedrock.jsonl"

    if not bedrock_file.exists():
        print("Bedrock dataset not found. Converting first...")
        convert_domain(domain)
        if not bedrock_file.exists():
            print(f"Error: could not create {bedrock_file}")
            sys.exit(1)

    base_model_id = BASE_MODELS.get(args.base_model)
    if not base_model_id:
        print(f"Error: unknown base model '{args.base_model}'")
        print(f"Available: {', '.join(BASE_MODELS.keys())}")
        sys.exit(1)

    s3_bucket = args.s3_bucket
    s3_prefix = args.s3_prefix or f"mascarade/finetune/{domain}"
    role_arn = args.role_arn

    if not s3_bucket or not role_arn:
        print("Error: --s3-bucket and --role-arn are required")
        print()
        print("Setup:")
        print("  1. Create an S3 bucket for training data")
        print("  2. Create an IAM role with Bedrock + S3 permissions:")
        print("     - bedrock:CreateModelCustomizationJob")
        print("     - s3:GetObject, s3:PutObject on your bucket")
        print("  3. Run:")
        print(f"     python {Path(__file__).name} train {domain} \\")
        print("       --s3-bucket my-bucket \\")
        print("       --role-arn arn:aws:iam::123456789:role/BedrockFineTuneRole")
        sys.exit(1)

    # Upload to S3
    s3 = boto3.client("s3")
    s3_key = f"{s3_prefix}/{bedrock_file.name}"
    print(f"Uploading {bedrock_file.name} to s3://{s3_bucket}/{s3_key}...")
    s3.upload_file(str(bedrock_file), s3_bucket, s3_key)
    s3_uri = f"s3://{s3_bucket}/{s3_key}"
    print(f"  Uploaded: {s3_uri}")

    # Output S3 location
    output_s3_uri = f"s3://{s3_bucket}/{s3_prefix}/output/"

    # Create fine-tuning job
    bedrock = boto3.client("bedrock")
    job_name = f"mascarade-{domain}-{int(time.time())}"
    custom_model_name = f"mascarade-{domain}"

    print("\nStarting fine-tuning job...")
    print(f"  Job name: {job_name}")
    print(f"  Base model: {args.base_model} ({base_model_id})")
    print(f"  Custom model: {custom_model_name}")

    try:
        response = bedrock.create_model_customization_job(
            jobName=job_name,
            customModelName=custom_model_name,
            roleArn=role_arn,
            baseModelIdentifier=base_model_id,
            customizationType="FINE_TUNING",
            trainingDataConfig={"s3Uri": s3_uri},
            outputDataConfig={"s3Uri": output_s3_uri},
            hyperParameters={
                "epochCount": str(args.epochs),
                "batchSize": str(args.batch_size),
                "learningRate": str(args.learning_rate),
            },
        )
        job_arn = response["jobArn"]
        print(f"\n  Job started: {job_arn}")
        print("\n  Monitor with:")
        print(f"    python {Path(__file__).name} status {job_arn}")
        print(f"    aws bedrock get-model-customization-job --job-identifier {job_arn}")

    except ClientError as e:
        print(f"\nError: {e}")
        sys.exit(1)


def cmd_status(args):
    """Check fine-tuning job status."""
    bedrock = boto3.client("bedrock", region_name="us-west-2")

    if args.job_arn:
        response = bedrock.get_model_customization_job(jobIdentifier=args.job_arn)
        print(f"Job: {response['jobName']}")
        print(f"Status: {response['status']}")
        print(f"Custom model: {response.get('outputModelName', 'N/A')}")
        if "failureMessage" in response:
            print(f"Failure: {response['failureMessage']}")
        metrics = response.get("trainingMetrics", {})
        if metrics:
            print(f"Training loss: {metrics.get('trainingLoss', 'N/A')}")
    else:
        response = bedrock.list_model_customization_jobs(maxResults=20)
        jobs = response.get("modelCustomizationJobSummaries", [])
        if not jobs:
            print("No fine-tuning jobs found.")
            return
        print(f"{'Job Name':<45} {'Status':<15} {'Model'}")
        print("-" * 85)
        for job in jobs:
            print(
                f"{job['jobName']:<45} {job['status']:<15} {job.get('customModelName', 'N/A')}"
            )


def cmd_list(args):
    """List available fine-tuned models."""
    bedrock = boto3.client("bedrock", region_name="us-west-2")
    response = bedrock.list_custom_models(maxResults=20)
    models = response.get("modelSummaries", [])

    if not models:
        print("No custom models found.")
        return

    print(f"{'Model Name':<35} {'ARN'}")
    print("-" * 90)
    for m in models:
        print(f"{m['modelName']:<35} {m.get('modelArn', 'N/A')}")

    print("\nUsage in Mascarade:")
    print('  POST /send  {"provider": "bedrock", "model": "mascarade-stm32-llama"}')


def cmd_provision(args):
    """Create provisioned throughput for a custom model (required to invoke it)."""
    bedrock = boto3.client("bedrock", region_name="us-west-2")

    # Find model ARN
    response = bedrock.list_custom_models(maxResults=50)
    model_arn = None
    for m in response.get("modelSummaries", []):
        if m["modelName"] == args.model_name:
            model_arn = m["modelArn"]
            break

    if not model_arn:
        print(f"Error: model '{args.model_name}' not found")
        print("Available:")
        for m in response.get("modelSummaries", []):
            print(f"  {m['modelName']}")
        sys.exit(1)

    pt_name = f"{args.model_name}-pt"
    print("Creating provisioned throughput...")
    print(f"  Model: {args.model_name}")
    print(f"  ARN: {model_arn}")
    print(f"  Units: {args.units}")

    try:
        resp = bedrock.create_provisioned_model_throughput(
            modelUnits=args.units,
            provisionedModelName=pt_name,
            modelId=model_arn,
        )
        print(f"\n  Provisioned throughput ARN: {resp['provisionedModelArn']}")
        print("\n  Use this ARN as model ID in Mascarade:")
        print(f"    model=\"{resp['provisionedModelArn']}\"")
    except ClientError as e:
        print(f"\nError: {e}")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="Fine-tune models on AWS Bedrock with Mascarade datasets"
    )
    sub = parser.add_subparsers(dest="command")

    # convert
    p_convert = sub.add_parser("convert", help="Convert ShareGPT to Bedrock format")
    p_convert.add_argument("domain", choices=DOMAINS + ["all"])

    # convert-all shortcut
    sub.add_parser("convert-all", help="Convert all datasets")

    # train
    p_train = sub.add_parser("train", help="Upload and start fine-tuning")
    p_train.add_argument("domain", choices=DOMAINS)
    p_train.add_argument(
        "--base-model",
        default=DEFAULT_BASE_MODEL,
        choices=BASE_MODELS.keys(),
        help=f"Base model (default: {DEFAULT_BASE_MODEL})",
    )
    p_train.add_argument("--s3-bucket", help="S3 bucket for training data")
    p_train.add_argument(
        "--s3-prefix", help="S3 prefix (default: mascarade/finetune/<domain>)"
    )
    p_train.add_argument("--role-arn", help="IAM role ARN for Bedrock")
    p_train.add_argument("--epochs", type=int, default=3)
    p_train.add_argument("--batch-size", type=int, default=1)
    p_train.add_argument("--learning-rate", type=float, default=1e-5)

    # status
    p_status = sub.add_parser("status", help="Check job status")
    p_status.add_argument("job_arn", nargs="?", help="Job ARN (omit to list all)")

    # list
    sub.add_parser("list", help="List fine-tuned models")

    # provision
    p_provision = sub.add_parser(
        "provision", help="Create provisioned throughput for a custom model"
    )
    p_provision.add_argument(
        "model_name", help="Custom model name (e.g. mascarade-stm32-llama)"
    )
    p_provision.add_argument(
        "--units", type=int, default=1, help="Model units (default: 1)"
    )

    args = parser.parse_args()

    if args.command == "convert":
        cmd_convert(args)
    elif args.command == "convert-all":
        args.domain = "all"
        cmd_convert(args)
    elif args.command == "train":
        cmd_train(args)
    elif args.command == "status":
        cmd_status(args)
    elif args.command == "list":
        cmd_list(args)
    elif args.command == "provision":
        cmd_provision(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
