#!/usr/bin/env python3
"""Automated model selector for local fine-tuning.

Searches HuggingFace Hub for code-generation models compatible with
the local hardware, ranks them by quality signals (benchmarks, popularity,
architecture fit), and optionally downloads the best candidate.

Usage:
  python model_selector.py                        # Search & show ranked list
  python model_selector.py --auto                 # Auto-pick best match
  python model_selector.py --auto --download      # Auto-pick and download
  python model_selector.py --pick 3               # Select rank 3
  python model_selector.py --vram 5               # Custom VRAM budget (GB)
  python model_selector.py --max-params 2         # Limit parameter count
  python model_selector.py --seq-len 1024         # Longer context training
  python model_selector.py --task general         # Search general models
  python model_selector.py --refresh              # Force-refresh from Hub
  python model_selector.py --json                 # Machine-readable output
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
CACHE_FILE = SCRIPT_DIR / ".model_selector_cache.json"
CACHE_TTL_HOURS = 24
SELECTION_FILE = SCRIPT_DIR / "selected_model.json"

# ── Known good authors ────────────────────────────────────────────────────

TRUSTED_AUTHORS = {
    "Qwen", "deepseek-ai", "bigcode", "microsoft", "codellama",
    "mistralai", "google", "meta-llama", "01-ai",
}

# ── Search queries per task ───────────────────────────────────────────────

SEARCH_QUERIES = {
    "code": [
        "coder instruct",
        "code instruct",
        "deepseek coder",
        "starcoder",
    ],
    "general": [
        "instruct small",
        "chat small",
    ],
}

# ── Patterns to skip ─────────────────────────────────────────────────────

_QUANT_RE = re.compile(
    r"(gptq|awq|gguf|ggml|exl2|fp8|squeezellm|marlin)", re.IGNORECASE,
)
_MOE_RE = re.compile(r"\bA\d+B\b")
_PARAM_RE = re.compile(r"(\d+(?:\.\d+)?)\s*[Bb]")

# ── LoRA targets per architecture ─────────────────────────────────────────

LORA_TARGETS: dict[str, list[str]] = {
    "qwen2": ["q_proj", "v_proj", "k_proj", "o_proj"],
    "qwen3": ["q_proj", "v_proj", "k_proj", "o_proj"],
    "llama": ["q_proj", "v_proj", "k_proj", "o_proj"],
    "mistral": ["q_proj", "v_proj", "k_proj", "o_proj"],
    "phi": ["q_proj", "v_proj", "k_proj", "dense"],
    "starcoder2": ["q_proj", "v_proj", "k_proj", "o_proj"],
    "deepseek": ["q_proj", "v_proj", "k_proj", "o_proj"],
    "gpt_bigcode": ["c_attn"],
    "codegen": ["qkv_proj"],
}

# ── Curated HumanEval pass@1 benchmarks ──────────────────────────────────

KNOWN_BENCHMARKS: dict[str, float] = {
    "Qwen/Qwen2.5-Coder-0.5B-Instruct": 61.6,
    "Qwen/Qwen2.5-Coder-1.5B-Instruct": 70.7,
    "Qwen/Qwen2.5-Coder-3B-Instruct": 76.2,
    "Qwen/Qwen2.5-Coder-7B-Instruct": 83.5,
    "deepseek-ai/deepseek-coder-1.3b-instruct": 65.2,
    "bigcode/starcoder2-3b": 46.3,
    "bigcode/starcoder2-7b": 53.0,
}


# ── GPU probe ─────────────────────────────────────────────────────────────

def probe_gpu() -> tuple[str | None, float]:
    """Detect GPU name and total VRAM in GB."""
    try:
        import torch

        if torch.cuda.is_available():
            name = torch.cuda.get_device_name(0)
            vram = torch.cuda.get_device_properties(0).total_mem / (1024**3)
            return name, round(vram, 1)
    except Exception:
        pass
    return None, 0.0


# ── VRAM estimation ───────────────────────────────────────────────────────

def estimate_qlora_vram_gb(
    param_b: float,
    seq_len: int = 512,
    batch_size: int = 1,
    lora_rank: int = 16,
) -> float:
    """Estimate VRAM for QLoRA 4-bit NF4 fine-tuning (GB).

    Components: model weights (NF4) + LoRA adapters (FP16) +
    optimizer states (paged AdamW 8-bit) + activations + CUDA overhead.
    """
    model_weights = param_b * 0.55          # NF4 + quant tables
    lora_adapters = param_b * 0.03 * (lora_rank / 16)
    optimizer = lora_adapters * 3            # momentum + variance (8-bit)
    activations = 0.3 * batch_size * (seq_len / 512)
    cuda_overhead = 0.7
    return round(
        model_weights + lora_adapters + optimizer + activations + cuda_overhead,
        2,
    )


# ── Model candidate ──────────────────────────────────────────────────────

@dataclass
class ModelCandidate:
    model_id: str
    author: str
    param_b: float
    downloads: int
    likes: int
    last_modified: str
    tags: list[str]
    estimated_vram_gb: float = 0.0
    humaneval: float | None = None
    is_instruct: bool = False
    score: float = 0.0
    cached_locally: bool = False

    def fits_vram(self, budget_gb: float) -> bool:
        return self.estimated_vram_gb <= budget_gb

    def summary_line(self, rank: int) -> str:
        bench = f"HE:{self.humaneval:.1f}" if self.humaneval is not None else "HE:  --"
        cached = " [cached]" if self.cached_locally else ""
        inst = " inst" if self.is_instruct else ""
        return (
            f"  {rank:2d}. {self.model_id:<50s} "
            f"{self.param_b:5.2f}B  "
            f"VRAM~{self.estimated_vram_gb:.1f}G  "
            f"{bench:>8s}  "
            f"dl:{self.downloads:>9,}  "
            f"score:{self.score:5.1f}"
            f"{inst}{cached}"
        )


# ── HuggingFace Hub helpers ──────────────────────────────────────────────

def _is_quantized(model_id: str, tags: list[str]) -> bool:
    if _QUANT_RE.search(model_id):
        return True
    return any(_QUANT_RE.search(t) for t in tags)


def _is_moe(model_id: str, tags: list[str]) -> bool:
    if _MOE_RE.search(model_id):
        return True
    return any("moe" in t.lower() or "mixture" in t.lower() for t in tags)


def _parse_param_count(model_id: str) -> float | None:
    """Parse parameter count from model name (e.g. '1.5B' -> 1.5)."""
    m = _PARAM_RE.search(model_id)
    return float(m.group(1)) if m else None


def _get_param_count_api(api, model_id: str) -> float | None:
    """Fetch parameter count via safetensors metadata (slower, more accurate)."""
    try:
        from huggingface_hub import get_safetensors_metadata

        meta = get_safetensors_metadata(model_id)
        if meta and meta.parameter_count:
            total = sum(meta.parameter_count.values())
            return round(total / 1e9, 2)
    except Exception:
        pass
    return None


def _check_hf_cache(model_id: str) -> bool:
    cache_dir = Path.home() / ".cache" / "huggingface" / "hub"
    model_dir = cache_dir / f"models--{model_id.replace('/', '--')}"
    return model_dir.exists()


# ── Search ────────────────────────────────────────────────────────────────

def search_hub(
    *,
    task: str = "code",
    max_params_b: float = 3.0,
    limit_per_query: int = 40,
    verbose: bool = True,
) -> list[ModelCandidate]:
    """Search HuggingFace Hub for candidate models."""
    from huggingface_hub import HfApi

    api = HfApi()
    seen: set[str] = set()
    candidates: list[ModelCandidate] = []
    queries = SEARCH_QUERIES.get(task, SEARCH_QUERIES["code"])

    for query in queries:
        if verbose:
            print(f"  Searching: '{query}' ...", end="", flush=True)
        try:
            models = list(api.list_models(
                search=query,
                pipeline_tag="text-generation",
                sort="downloads",
                direction=-1,
                limit=limit_per_query,
            ))
        except Exception as e:
            if verbose:
                print(f" failed ({e})")
            continue

        added = 0
        for m in models:
            mid = m.id
            if mid in seen:
                continue
            seen.add(mid)

            tags = list(m.tags or [])

            # Skip quantized / MoE variants
            if _is_quantized(mid, tags):
                continue
            if _is_moe(mid, tags):
                continue

            # Resolve parameter count (name parse first, API fallback)
            param_b = _parse_param_count(mid)
            if param_b is None:
                param_b = _get_param_count_api(api, mid)
            if param_b is None or param_b > max_params_b:
                continue

            author = mid.split("/")[0] if "/" in mid else ""
            is_instruct = any(
                kw in mid.lower() for kw in ("instruct", "chat", "-it")
            )

            c = ModelCandidate(
                model_id=mid,
                author=author,
                param_b=param_b,
                downloads=m.downloads or 0,
                likes=m.likes or 0,
                last_modified=str(getattr(m, "lastModified", "") or ""),
                tags=tags,
                estimated_vram_gb=estimate_qlora_vram_gb(param_b),
                humaneval=KNOWN_BENCHMARKS.get(mid),
                is_instruct=is_instruct,
                cached_locally=_check_hf_cache(mid),
            )
            candidates.append(c)
            added += 1

        if verbose:
            print(f" +{added}")

    if verbose:
        print(f"  Total: {len(candidates)} candidates")
    return candidates


# ── Scoring & ranking ─────────────────────────────────────────────────────

def rank_candidates(
    candidates: list[ModelCandidate],
    vram_budget_gb: float,
    seq_len: int = 512,
) -> list[ModelCandidate]:
    """Score and rank candidates that fit within VRAM budget."""
    for c in candidates:
        c.estimated_vram_gb = estimate_qlora_vram_gb(c.param_b, seq_len=seq_len)

    viable = [c for c in candidates if c.fits_vram(vram_budget_gb)]
    if not viable:
        return []

    max_dl = max(c.downloads for c in viable) or 1
    max_likes = max(c.likes for c in viable) or 1
    max_params = max(c.param_b for c in viable) or 1

    for c in viable:
        # 1. Benchmark quality (35%) — strongest signal when available
        if c.humaneval is not None:
            bench = c.humaneval / 100.0
        else:
            bench = 0.30  # neutral for unknown models

        # 2. Model capacity (20%) — bigger within budget = more capable
        size = c.param_b / max_params

        # 3. Instruct tuning (15%) — prefer instruct variants
        instruct = 1.0 if c.is_instruct else 0.0

        # 4. Community signals (15%) — downloads + likes
        community = (c.downloads / max_dl) * 0.6 + (c.likes / max_likes) * 0.4

        # 5. VRAM efficiency (10%) — sweet spot at ~70% utilization
        utilization = c.estimated_vram_gb / vram_budget_gb
        fit = max(0.0, 1.0 - abs(utilization - 0.7) * 3)

        # 6. Trusted author (5%)
        author = 1.0 if c.author in TRUSTED_AUTHORS else 0.3

        c.score = round(
            bench * 35 + size * 20 + instruct * 15
            + community * 15 + fit * 10 + author * 5,
            1,
        )

    viable.sort(key=lambda c: c.score, reverse=True)
    return viable


# ── Cache ─────────────────────────────────────────────────────────────────

def save_cache(candidates: list[ModelCandidate]) -> None:
    data = {
        "timestamp": time.time(),
        "candidates": [asdict(c) for c in candidates],
    }
    CACHE_FILE.write_text(json.dumps(data, indent=2))


def load_cache() -> list[ModelCandidate] | None:
    if not CACHE_FILE.exists():
        return None
    try:
        data = json.loads(CACHE_FILE.read_text())
        age_h = (time.time() - data["timestamp"]) / 3600
        if age_h > CACHE_TTL_HOURS:
            return None
        return [ModelCandidate(**c) for c in data["candidates"]]
    except Exception:
        return None


# ── Download & validate ───────────────────────────────────────────────────

def download_model(model_id: str) -> Path:
    """Download model snapshot to HF cache."""
    from huggingface_hub import snapshot_download

    print(f"\nDownloading {model_id} ...")
    path = snapshot_download(model_id)
    print(f"Done -> {path}")
    return Path(path)


def validate_model(model_id: str) -> dict:
    """Load model config and check architecture compatibility."""
    from transformers import AutoConfig

    config = AutoConfig.from_pretrained(model_id, trust_remote_code=True)
    model_type = getattr(config, "model_type", "unknown")
    lora = LORA_TARGETS.get(model_type, LORA_TARGETS.get("llama", []))
    return {
        "model_type": model_type,
        "lora_targets": lora,
        "vocab_size": getattr(config, "vocab_size", None),
        "hidden_size": getattr(config, "hidden_size", None),
        "num_layers": getattr(config, "num_hidden_layers", None),
    }


# ── Selection output ──────────────────────────────────────────────────────

def write_selection(
    candidate: ModelCandidate,
    validation: dict | None = None,
) -> None:
    """Write selected model to JSON for pipeline integration."""
    data = {
        "model_id": candidate.model_id,
        "param_b": candidate.param_b,
        "estimated_vram_gb": candidate.estimated_vram_gb,
        "score": candidate.score,
        "humaneval": candidate.humaneval,
        "selected_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    if validation:
        data["validation"] = validation
    SELECTION_FILE.write_text(json.dumps(data, indent=2))
    print(f"\nSelection -> {SELECTION_FILE}")


# ── CLI ───────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Search, rank, and download fine-tuning models from HuggingFace Hub.",
    )
    parser.add_argument(
        "--vram", type=float, default=0,
        help="VRAM budget in GB (0 = auto-detect)",
    )
    parser.add_argument(
        "--max-params", type=float, default=3.0,
        help="Max parameter count in billions (default: 3.0)",
    )
    parser.add_argument(
        "--seq-len", type=int, default=512,
        help="Training sequence length for VRAM estimation (default: 512)",
    )
    parser.add_argument(
        "--task", choices=["code", "general"], default="code",
        help="Model task focus (default: code)",
    )
    parser.add_argument(
        "--auto", action="store_true",
        help="Auto-select the best model (rank 1)",
    )
    parser.add_argument(
        "--pick", type=int, default=0, metavar="N",
        help="Select the model at rank N",
    )
    parser.add_argument(
        "--download", action="store_true",
        help="Download the selected model to HF cache",
    )
    parser.add_argument(
        "--validate", action="store_true",
        help="Validate architecture compatibility after selection",
    )
    parser.add_argument(
        "--refresh", action="store_true",
        help="Force refresh from HuggingFace Hub (ignore cache)",
    )
    parser.add_argument(
        "--top", type=int, default=15,
        help="Show top N candidates (default: 15)",
    )
    parser.add_argument(
        "--json", action="store_true",
        help="Output ranked list as JSON",
    )
    args = parser.parse_args()

    # ── GPU detection ─────────────────────────────────────────────────
    gpu_name, detected_vram = probe_gpu()
    vram_budget = args.vram or detected_vram
    if vram_budget <= 0:
        vram_budget = 4.0
        if not args.json:
            print("No GPU detected and no --vram given. Using 4 GB default.\n")

    if not args.json:
        print(f"  GPU         : {gpu_name or 'none'}")
        print(f"  VRAM budget : {vram_budget:.1f} GB")
        print(f"  Max params  : {args.max_params:.1f} B")
        print(f"  Seq length  : {args.seq_len}")
        print(f"  Task        : {args.task}")
        print()

    # ── Search / cache ────────────────────────────────────────────────
    candidates = None if args.refresh else load_cache()
    if candidates is None:
        if not args.json:
            print("Searching HuggingFace Hub ...")
        candidates = search_hub(
            task=args.task,
            max_params_b=args.max_params,
            verbose=not args.json,
        )
        save_cache(candidates)
    else:
        if not args.json:
            print(f"Using cached results ({len(candidates)} models)\n")

    # ── Rank ──────────────────────────────────────────────────────────
    ranked = rank_candidates(candidates, vram_budget, seq_len=args.seq_len)
    if not ranked:
        print(
            f"\nNo models found fitting {vram_budget:.1f} GB VRAM budget "
            f"with max {args.max_params:.1f}B params.",
            file=sys.stderr,
        )
        sys.exit(1)

    top = ranked[: args.top]

    # ── JSON output ───────────────────────────────────────────────────
    if args.json:
        print(json.dumps([asdict(c) for c in top], indent=2))
        return

    # ── Display ───────────────────────────────────────────────────────
    print(
        f"\nTop {len(top)} models for {vram_budget:.1f} GB VRAM "
        f"(seq_len={args.seq_len}):\n"
    )
    for i, c in enumerate(top, 1):
        print(c.summary_line(i))

    # ── Selection ─────────────────────────────────────────────────────
    selected = None
    if args.auto:
        selected = top[0]
        print(f"\n-> Auto-selected: {selected.model_id}")
    elif args.pick:
        idx = args.pick - 1
        if 0 <= idx < len(top):
            selected = top[idx]
            print(f"\n-> Selected #{args.pick}: {selected.model_id}")
        else:
            print(f"\nInvalid rank {args.pick} (range 1-{len(top)})", file=sys.stderr)
            sys.exit(1)

    if selected is None:
        print(f"\nRe-run with --auto or --pick N to select a model.")
        return

    # ── Download ──────────────────────────────────────────────────────
    if args.download:
        download_model(selected.model_id)

    # ── Validate ──────────────────────────────────────────────────────
    validation = None
    if args.validate or args.download:
        if not args.download and not selected.cached_locally:
            print("Model not cached. Use --download to fetch it first.")
        else:
            try:
                validation = validate_model(selected.model_id)
                print(f"  Architecture : {validation['model_type']}")
                print(f"  LoRA targets : {validation['lora_targets']}")
                print(f"  Hidden size  : {validation['hidden_size']}")
                print(f"  Layers       : {validation['num_layers']}")
            except Exception as e:
                print(f"  Validation failed: {e}", file=sys.stderr)

    # ── Write selection ───────────────────────────────────────────────
    write_selection(selected, validation)

    print(f"\nUsage:")
    print(f"  python run_local.py stm32 --model {selected.model_id}")
    print(f"  python batch_local.py --student-model {selected.model_id}")


if __name__ == "__main__":
    main()
