#!/usr/bin/env python3
"""Publish a locally trained model adapter to Hugging Face Hub.

Usage:
    python finetune/publish_to_hub.py stm32
    python finetune/publish_to_hub.py kicad --model-dir finetune/models_local/kicad
    python finetune/publish_to_hub.py stm32 --dry-run

Requires:
    HF_TOKEN env var  (or --token arg, which is less safe)
    huggingface_hub >= 0.22
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_MODELS_ROOT = SCRIPT_DIR / "models_local"
DEFAULT_USERNAME = "clemsail"

# Allowed domain names — validated before use in repo_id construction.
DOMAIN_TAGS: dict[str, list[str]] = {
    "stm32": ["electronics", "embedded", "stm32", "firmware"],
    "spice": ["electronics", "spice", "eda", "simulation"],
    "iot": ["electronics", "iot", "esp32", "mqtt", "embedded"],
    "power": ["electronics", "power-electronics", "analog"],
    "dsp": ["electronics", "dsp", "signal-processing"],
    "emc": ["electronics", "emc", "emi", "pcb-design"],
    "kicad": ["electronics", "kicad", "pcb-design", "eda"],
    "embedded": ["electronics", "embedded", "firmware"],
    "platformio": ["electronics", "platformio", "embedded"],
    "freecad": ["cad", "freecad", "openscad", "cadquery"],
    "components": ["electronics", "components", "datasheets", "bom"],
}

# Strict allowlist: domain must match this pattern to be used in a repo_id.
# Prevents any path-traversal or injection via the domain argument.
_SAFE_DOMAIN_RE = re.compile(r"^[a-z0-9][a-z0-9\-]{0,31}$")


def _validate_domain(domain: str) -> str:
    """Raise if domain is not a safe identifier for use in a HF repo_id."""
    if not _SAFE_DOMAIN_RE.match(domain):
        raise ValueError(
            f"Invalid domain '{domain}'. Must be lowercase alphanumeric with hyphens (max 32 chars)."
        )
    return domain


def _resolve_model_dir(domain: str, model_dir: Path | None) -> Path:
    if model_dir is not None:
        resolved = model_dir.resolve()
        if not resolved.exists():
            raise FileNotFoundError(f"Model dir not found: {resolved}")
        return resolved
    # Walk common naming conventions: domain/ or domain-* under models_local/
    candidates = [
        DEFAULT_MODELS_ROOT / domain,
        DEFAULT_MODELS_ROOT / f"{domain}-sft",
        DEFAULT_MODELS_ROOT / f"mascarade-{domain}",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate.resolve()
    raise FileNotFoundError(
        f"Could not find model dir for domain '{domain}' under {DEFAULT_MODELS_ROOT}. "
        "Pass --model-dir explicitly."
    )


def _load_metrics(model_dir: Path) -> dict:
    """Load trainer_state.json or training_state.json if present."""
    for name in ("trainer_state.json", "training_state.json", "run_manifest.json"):
        candidate = model_dir / name
        if candidate.exists():
            try:
                data = json.loads(candidate.read_text(encoding="utf-8"))
                return data
            except json.JSONDecodeError:
                pass
    return {}


def _build_model_card(domain: str, repo_id: str, metrics: dict) -> str:
    tags = DOMAIN_TAGS.get(domain, [domain, "fine-tuned"])
    tags_yaml = "\n".join(f"- {t}" for t in ["text-generation", "peft", *tags])
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # Extract a few readable metrics if available
    metric_lines: list[str] = []
    for key in ("best_metric", "best_model_checkpoint", "epoch", "global_step"):
        if key in metrics:
            metric_lines.append(f"- **{key}**: `{metrics[key]}`")

    metrics_section = (
        "\n".join(metric_lines) if metric_lines else "_No trainer metrics found._"
    )

    return f"""---
license: apache-2.0
language:
- fr
- en
tags:
{tags_yaml}
library_name: peft
base_model: mascarade-student
datasets:
- {repo_id.replace("mascarade-", "mascarade-").replace("-sft", "-dataset")}
---

# Mascarade {domain.replace("-", " ").title()} — Fine-tuned Adapter

Fine-tuned LoRA adapter produced by the [Mascarade](https://github.com/electron-rare/mascarade)
agentic pipeline on {now}.

## Domain

`{domain}` — part of the Mascarade electronics/embedded/CAD fine-tuning family.

## Training Metrics

{metrics_section}

## Usage

```python
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer

base = AutoModelForCausalLM.from_pretrained("base-model-id")
model = PeftModel.from_pretrained(base, "{repo_id}")
tokenizer = AutoTokenizer.from_pretrained("{repo_id}")
```

## License

Apache-2.0 — see [LICENSE](../../LICENSE.md).
"""


def publish(
    *,
    domain: str,
    model_dir: Path | None,
    username: str,
    token: str,
    dry_run: bool,
    commit_message: str | None,
) -> int:
    from huggingface_hub import HfApi, create_repo

    domain = _validate_domain(domain)
    resolved_dir = _resolve_model_dir(domain, model_dir)
    repo_id = f"{username}/mascarade-{domain}"
    metrics = _load_metrics(resolved_dir)
    card_content = _build_model_card(domain, repo_id, metrics)
    msg = commit_message or f"Upload mascarade-{domain} adapter — {datetime.now(timezone.utc).date()}"

    print(f"[publish_to_hub] domain   : {domain}")
    print(f"[publish_to_hub] model_dir: {resolved_dir}")
    print(f"[publish_to_hub] repo_id  : {repo_id}")
    print(f"[publish_to_hub] dry_run  : {dry_run}")

    if dry_run:
        print("[publish_to_hub] DRY RUN — nothing uploaded.")
        print("--- MODEL CARD PREVIEW ---")
        print(card_content)
        return 0

    api = HfApi(token=token)

    # Ensure the repo exists (creates if absent, no-ops if present)
    create_repo(repo_id=repo_id, repo_type="model", exist_ok=True, token=token)

    # Write the model card to a temp file inside the model dir
    card_path = resolved_dir / "README.md"
    card_path.write_text(card_content, encoding="utf-8")

    api.upload_folder(
        folder_path=str(resolved_dir),
        repo_id=repo_id,
        repo_type="model",
        commit_message=msg,
        # Ignore large binaries that shouldn't be pushed raw
        ignore_patterns=["*.bin.index.json", "__pycache__/**", "*.pyc", "tmp/**"],
    )

    print(f"[publish_to_hub] ✓ Uploaded to https://huggingface.co/{repo_id}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Publish a Mascarade fine-tuned model adapter to Hugging Face Hub."
    )
    parser.add_argument("domain", help="Fine-tuning domain (e.g. stm32, kicad, iot)")
    parser.add_argument(
        "--model-dir",
        type=Path,
        default=None,
        help=f"Path to the model dir (default: auto-detected under {DEFAULT_MODELS_ROOT})",
    )
    parser.add_argument(
        "--username",
        default=os.environ.get("HF_USER", DEFAULT_USERNAME),
        help=f"Hugging Face username (default: {DEFAULT_USERNAME})",
    )
    parser.add_argument(
        "--commit-message",
        default=None,
        help="Custom commit message for the HF upload",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be uploaded without actually uploading",
    )
    args = parser.parse_args()

    # Token comes from environment only — never passed as a CLI positional arg
    # to avoid leakage in process lists / shell history.
    token = os.environ.get("HF_TOKEN", "")
    if not token and not args.dry_run:
        print(
            "ERROR: HF_TOKEN environment variable is not set. "
            "Set it or use --dry-run.",
            file=sys.stderr,
        )
        return 1

    try:
        return publish(
            domain=args.domain,
            model_dir=args.model_dir,
            username=args.username,
            token=token,
            dry_run=args.dry_run,
            commit_message=args.commit_message,
        )
    except (FileNotFoundError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())