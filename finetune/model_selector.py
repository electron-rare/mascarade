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
import os
import re
import shutil
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from llm_paths import configure_hf_env, hf_cache_roots, llm_root

configure_hf_env()

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_CACHE_FILE = SCRIPT_DIR / ".model_selector_cache.json"
CACHE_TTL_HOURS = 24
REPO_SELECTION_FILE = SCRIPT_DIR / "selected_model.json"

MIN_STATE_FREE_BYTES = 64 * 1024 * 1024
STATE_DIR_NAME = "mascarade-finetune-state"
RUNTIME_TMP_SUBDIR = "tmp"


def _usable_state_dir(path: Path) -> bool:
    try:
        path.mkdir(parents=True, exist_ok=True)
    except Exception:
        return False
    try:
        if shutil.disk_usage(path).free < MIN_STATE_FREE_BYTES:
            return False
    except Exception:
        return False
    probe = path / ".selector-write-probe"
    try:
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        return True
    except Exception:
        return False


def _resolve_state_dir() -> Path:
    explicit = (
        os.environ.get("MODEL_SELECTOR_STATE_DIR")
        or os.environ.get("MASCARADE_FINETUNE_STATE_DIR")
    )
    candidates: list[Path] = []
    if explicit:
        candidates.append(Path(explicit))
    candidates.extend(
        [
            Path("/dev/shm") / STATE_DIR_NAME,
            Path("/tmp") / STATE_DIR_NAME,
            SCRIPT_DIR,
        ]
    )
    for candidate in candidates:
        if _usable_state_dir(candidate):
            return candidate
    return SCRIPT_DIR


STATE_DIR = _resolve_state_dir()
CACHE_FILE = STATE_DIR / ".model_selector_cache.json"
SELECTION_FILE = STATE_DIR / "selected_model.json"
WATCH_CACHE_FILE = STATE_DIR / ".model_watch_cache.json"
WATCH_REPORT_FILE = STATE_DIR / "model_watch_report.json"
VALIDATION_REGISTRY_FILE = STATE_DIR / "model_validation_registry.json"


def _selection_candidates() -> list[Path]:
    ordered: list[Path] = []
    for path in (SELECTION_FILE, REPO_SELECTION_FILE):
        if path not in ordered:
            ordered.append(path)
    return ordered


def _cache_candidates() -> list[Path]:
    ordered: list[Path] = []
    for path in (CACHE_FILE, REPO_CACHE_FILE):
        if path not in ordered:
            ordered.append(path)
    return ordered


def _ensure_runtime_tmpdir() -> None:
    if os.environ.get("TMPDIR"):
        return
    for candidate in (
        STATE_DIR / RUNTIME_TMP_SUBDIR,
        Path("/dev/shm") / STATE_DIR_NAME / RUNTIME_TMP_SUBDIR,
        Path("/tmp") / STATE_DIR_NAME / RUNTIME_TMP_SUBDIR,
    ):
        try:
            candidate.mkdir(parents=True, exist_ok=True)
            if shutil.disk_usage(candidate).free < MIN_STATE_FREE_BYTES:
                continue
            os.environ["TMPDIR"] = str(candidate)
            return
        except Exception:
            continue


_ensure_runtime_tmpdir()

FALLBACK_MODEL = "Qwen/Qwen2.5-Coder-1.5B-Instruct"


def resolve_model(fallback: str = FALLBACK_MODEL) -> str:
    """Return the model_id from selected_model.json, or fallback default.

    Importable by training scripts to auto-use the selector's choice:
        from model_selector import resolve_model
        model = resolve_model()
    """
    for selection_file in _selection_candidates():
        if not selection_file.exists():
            continue
        try:
            data = json.loads(selection_file.read_text())
            model_id = data.get("model_id", "").strip()
            if model_id:
                return model_id
        except Exception:
            continue
    return fallback


# ── Known good authors ────────────────────────────────────────────────────

TRUSTED_AUTHORS = {
    "Qwen",
    "deepseek-ai",
    "bigcode",
    "microsoft",
    "codellama",
    "mistralai",
    "google",
    "meta-llama",
    "01-ai",
}

WATCH_AUTHORS = (
    "Qwen",
    "mistralai",
    "deepseek-ai",
    "JetBrains",
)

WATCH_AUTHOR_PATTERNS = {
    "Qwen": ("qwen2.5", "qwen3", "qwen3.5", "coder-next", "coder"),
    "mistralai": ("devstral", "mistral-small", "ministral", "magistral", "codestral"),
    "deepseek-ai": ("deepseek-v3", "deepseek-r1", "deepseek-coder", "distill"),
    "JetBrains": ("mellum",),
}

WATCH_AUTHOR_EXCLUDES = {
    "mistralai": ("mistral-7b-v0.", "mistral-7b-instruct-v0."),
}

# ── Search queries per task ───────────────────────────────────────────────

SEARCH_QUERIES = {
    "code": [
        "qwen3.5 base",
        "qwen3 instruct",
        "coder base",
        "coder instruct",
        "code instruct",
        "deepseek coder",
        "devstral instruct",
        "mistral small base",
        "starcoder",
    ],
    "general": [
        "qwen3.5 base",
        "qwen3 instruct",
        "instruct small",
        "base model",
        "chat small",
    ],
}

WATCH_KEYWORDS = {
    "code": (
        "code",
        "coder",
        "devstral",
        "mellum",
        "deepseek",
        "qwen",
        "mistral",
        "ministral",
        "base",
        "instruct",
    ),
    "general": (
        "assistant",
        "base",
        "chat",
        "deepseek",
        "instruct",
        "mistral",
        "ministral",
        "qwen",
    ),
}

WATCH_EXCLUDE_TOKENS = (
    "dpo",
    "embedding",
    "guard",
    "reranker",
    "reward",
    "saferl",
    "safety",
    "tokenizer",
    "vl",
    "vision-language",
)

# ── Patterns to skip ─────────────────────────────────────────────────────

_PACKAGED_RE = re.compile(
    r"(gptq|awq|gguf|ggml|exl2|mnn|onnx|mlx|squeezellm|marlin)",
    re.IGNORECASE,
)
_NUMERIC_QUANT_RE = re.compile(
    r"(fp8|nvfp4|int4|int8)",
    re.IGNORECASE,
)
_MOE_RE = re.compile(r"\bA\d+B\b")
_PARAM_RE = re.compile(r"(\d+(?:\.\d+)?)\s*[Bb]")
_WATCH_TOKEN_RE = re.compile(r"[^a-z0-9]+")

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

CURATED_STUDENT_CANDIDATES: tuple[dict[str, object], ...] = (
    {
        "model_id": "Qwen/Qwen3.5-9B-Base",
        "param_b": 9.0,
        "is_base": True,
        "is_instruct": False,
    },
    {
        "model_id": "Qwen/Qwen3-8B",
        "param_b": 8.0,
        "is_base": False,
        "is_instruct": False,
    },
    {
        "model_id": "Qwen/Qwen3-4B-Instruct-2507",
        "param_b": 4.0,
        "is_base": False,
        "is_instruct": True,
    },
    {
        "model_id": "Qwen/Qwen2.5-Coder-7B-Instruct",
        "param_b": 7.0,
        "is_base": False,
        "is_instruct": True,
    },
    {
        "model_id": "Qwen/Qwen2.5-Coder-1.5B-Instruct",
        "param_b": 1.5,
        "is_base": False,
        "is_instruct": True,
    },
)

PINNED_MODELS = {
    "Qwen/Qwen3.5-9B-Base",
    "Qwen/Qwen3-8B",
    "Qwen/Qwen3-4B-Instruct-2507",
    "Qwen/Qwen2.5-Coder-7B-Instruct",
    "Qwen/Qwen2.5-Coder-1.5B-Instruct",
    "Qwen/Qwen3.5-35B-A3B-GPTQ-Int4",
    "Qwen/Qwen2.5-7B-Instruct",
    "mistralai/Devstral-Small-2-24B-Instruct-2512",
    "mistralai/Mistral-Small-3.1-24B-Base-2503",
}

KNOWN_GPU_VRAM_GB = {
    "4090": 24.0,
    "3090": 24.0,
    "5090": 32.0,
    "P2000": 5.0,
}


# ── GPU probe ─────────────────────────────────────────────────────────────


def probe_gpu() -> tuple[str | None, float]:
    """Detect GPU name and total VRAM in GB."""
    try:
        completed = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=name,memory.total",
                "--format=csv,noheader",
            ],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        if completed.returncode == 0 and completed.stdout.strip():
            first = completed.stdout.strip().splitlines()[0]
            parts = [item.strip() for item in first.split(",")]
            if len(parts) >= 2:
                vram_gb = float(parts[1].split()[0]) / 1024.0
                return parts[0], round(vram_gb, 1)
    except Exception:
        pass
    info_root = Path("/proc/driver/nvidia/gpus")
    if info_root.exists():
        info_files = sorted(info_root.glob("*/information"))
        if info_files:
            try:
                info_text = info_files[0].read_text(encoding="utf-8")
                for line in info_text.splitlines():
                    if line.startswith("Model:"):
                        name = line.split(":", 1)[1].strip()
                        upper = name.upper()
                        for needle, vram_gb in KNOWN_GPU_VRAM_GB.items():
                            if needle in upper:
                                return name, vram_gb
                        return name, 0.0
            except Exception:
                pass
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
    model_weights = param_b * 0.55  # NF4 + quant tables
    lora_adapters = param_b * 0.03 * (lora_rank / 16)
    optimizer = lora_adapters * 3  # momentum + variance (8-bit)
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
    is_base: bool = False
    score: float = 0.0
    cached_locally: bool = False

    def fits_vram(self, budget_gb: float) -> bool:
        return self.estimated_vram_gb <= budget_gb

    def summary_line(self, rank: int) -> str:
        bench = f"HE:{self.humaneval:.1f}" if self.humaneval is not None else "HE:  --"
        cached = " [cached]" if self.cached_locally else ""
        inst = " inst" if self.is_instruct else ""
        base = " base" if self.is_base else ""
        return (
            f"  {rank:2d}. {self.model_id:<50s} "
            f"{self.param_b:5.2f}B  "
            f"VRAM~{self.estimated_vram_gb:.1f}G  "
            f"{bench:>8s}  "
            f"dl:{self.downloads:>9,}  "
            f"score:{self.score:5.1f}"
            f"{inst}{base}{cached}"
        )


@dataclass
class WatchCandidate:
    model_id: str
    author: str
    last_modified: str
    param_b: float | None
    tags: list[str]
    suggested_lane: str
    relevance: str
    cached_locally: bool = False

    def summary_line(self, rank: int) -> str:
        param = f"{self.param_b:.2f}B" if self.param_b is not None else "  --"
        cached = " [cached]" if self.cached_locally else ""
        date = self.last_modified[:10] if self.last_modified else "----------"
        return (
            f"  {rank:2d}. {self.model_id:<50s} "
            f"{param:>6s}  "
            f"{date}  "
            f"{self.suggested_lane:<13s}"
            f"{cached}  {self.relevance}"
        )


# ── HuggingFace Hub helpers ──────────────────────────────────────────────


def _is_quantized(model_id: str, tags: list[str]) -> bool:
    if _PACKAGED_RE.search(model_id) or _NUMERIC_QUANT_RE.search(model_id):
        return True
    return any(_PACKAGED_RE.search(t) or _NUMERIC_QUANT_RE.search(t) for t in tags)


def _is_packaged_release(model_id: str, tags: list[str]) -> bool:
    if _PACKAGED_RE.search(model_id):
        return True
    return any(_PACKAGED_RE.search(t) for t in tags)


def _is_numeric_quant_release(model_id: str, tags: list[str]) -> bool:
    if _NUMERIC_QUANT_RE.search(model_id):
        return True
    return any(_NUMERIC_QUANT_RE.search(t) for t in tags)


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
    suffix = f"models--{model_id.replace('/', '--')}"
    for root in hf_cache_roots():
        if (root / suffix).exists():
            return True
    return False


def _seed_curated_candidates(
    candidates: list[ModelCandidate],
    seen: set[str],
    max_params_b: float,
) -> None:
    for entry in CURATED_STUDENT_CANDIDATES:
        model_id = str(entry["model_id"])
        if model_id in seen:
            continue
        param_b = float(entry["param_b"])
        if param_b > max_params_b:
            continue
        seen.add(model_id)
        author = model_id.split("/")[0] if "/" in model_id else ""
        candidates.append(
            ModelCandidate(
                model_id=model_id,
                author=author,
                param_b=param_b,
                downloads=0,
                likes=0,
                last_modified="",
                tags=[],
                estimated_vram_gb=estimate_qlora_vram_gb(param_b),
                humaneval=KNOWN_BENCHMARKS.get(model_id),
                is_instruct=bool(entry["is_instruct"]),
                is_base=bool(entry["is_base"]),
                cached_locally=_check_hf_cache(model_id),
            )
        )


def _generation_fit(model_id: str) -> float:
    lowered = model_id.lower()
    if "qwen3.5" in lowered:
        return 1.0
    if "qwen3" in lowered or "seed-coder" in lowered:
        return 0.9
    if "deepseek-r1-distill" in lowered:
        return 0.85
    if "qwen2.5" in lowered or "deepseek-coder" in lowered:
        return 0.7
    if "starcoder2" in lowered:
        return 0.6
    return 0.5


def _parse_last_modified(raw_value: object) -> datetime | None:
    text = str(raw_value or "").strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _watch_blob(model_id: str, tags: list[str]) -> str:
    return f"{model_id.lower()} {' '.join(tag.lower() for tag in tags)}"


def _watch_tokens(blob: str) -> set[str]:
    return {token for token in _WATCH_TOKEN_RE.split(blob) if token}


def _watch_term_matches(term: str, blob: str, tokens: set[str]) -> bool:
    lowered = term.lower()
    if not lowered:
        return False
    if re.search(r"[^a-z0-9]", lowered):
        parts = [part for part in _WATCH_TOKEN_RE.split(lowered) if part]
        return bool(parts) and all(part in tokens for part in parts)
    return lowered in tokens


def _is_watch_relevant(model_id: str, tags: list[str], task: str, author: str) -> bool:
    blob = _watch_blob(model_id, tags)
    tokens = _watch_tokens(blob)
    model_id_lower = model_id.lower()
    author_patterns = WATCH_AUTHOR_PATTERNS.get(author)
    if author_patterns and not any(pattern in model_id_lower for pattern in author_patterns):
        return False
    author_excludes = WATCH_AUTHOR_EXCLUDES.get(author, ())
    if any(pattern in model_id_lower for pattern in author_excludes):
        return False
    if any(_watch_term_matches(token, blob, tokens) for token in WATCH_EXCLUDE_TOKENS):
        return False
    return any(
        _watch_term_matches(token, blob, tokens)
        for token in WATCH_KEYWORDS.get(task, ())
    )


def _watch_lane(
    model_id: str,
    tags: list[str],
    param_b: float | None,
    max_params_b: float,
) -> tuple[str | None, str]:
    lowered = model_id.lower()
    if _is_packaged_release(model_id, tags):
        return None, "packaged runtime release is not useful for model watch"
    if _is_numeric_quant_release(model_id, tags):
        return (
            "teacher_watch",
            "recent FP8/int checkpoint: keep as teacher/manual watch candidate",
        )
    if _is_moe(model_id, tags):
        return "teacher_watch", "sparse/MoE checkpoint: keep as teacher-only watch candidate"
    if param_b is None:
        return "manual_review", "parameter count unknown: keep for manual review"
    if param_b > max(16.0, max_params_b):
        return "teacher_watch", "too large for current student lane; watch as teacher/manual candidate"
    if "deepseek-r1-distill" in lowered:
        return "student_watch", "distilled DeepSeek checkpoint compatible with the student lane"
    if "mellum" in lowered:
        return "student_watch", "recent code-specialized dense base worth benchmarking as a student"
    if "base" in lowered:
        return "student_watch", "recent dense base checkpoint aligned with local fine-tuning"
    if "instruct" in lowered or "chat" in lowered:
        return "manual_review", "recent instruct checkpoint worth manual distillation/teacher review"
    return "manual_review", "recent trusted release outside the current automatic policy"


def watch_recent_releases(
    *,
    task: str,
    max_params_b: float,
    days: int,
    limit_per_author: int = 24,
    verbose: bool = True,
) -> list[WatchCandidate]:
    from huggingface_hub import HfApi

    api = HfApi()
    cutoff = datetime.now(timezone.utc) - timedelta(days=max(1, days))
    seen: set[str] = set()
    candidates: list[WatchCandidate] = []

    for author in WATCH_AUTHORS:
        if verbose:
            print(f"  Watching author: {author} ...", end="", flush=True)
        try:
            models = list(
                api.list_models(
                    author=author,
                    pipeline_tag="text-generation",
                    sort="lastModified",
                    limit=limit_per_author,
                )
            )
        except Exception as exc:
            if verbose:
                print(f" failed ({exc})")
            continue
        models.sort(
            key=lambda model: (
                _parse_last_modified(getattr(model, "lastModified", "")) or datetime.min.replace(tzinfo=timezone.utc)
            ),
            reverse=True,
        )

        added = 0
        for model in models:
            model_id = model.id
            if model_id in seen:
                continue
            seen.add(model_id)
            tags = list(model.tags or [])
            if not _is_watch_relevant(model_id, tags, task, author):
                continue

            last_modified = str(getattr(model, "lastModified", "") or "")
            parsed_last_modified = _parse_last_modified(last_modified)
            if parsed_last_modified is not None and parsed_last_modified < cutoff:
                continue

            param_b = _parse_param_count(model_id)
            lane, relevance = _watch_lane(model_id, tags, param_b, max_params_b)
            if lane is None:
                continue

            candidates.append(
                WatchCandidate(
                    model_id=model_id,
                    author=author,
                    last_modified=last_modified,
                    param_b=param_b,
                    tags=tags,
                    suggested_lane=lane,
                    relevance=relevance,
                    cached_locally=_check_hf_cache(model_id),
                )
            )
            added += 1

        if verbose:
            print(f" +{added}")

    candidates.sort(
        key=lambda item: (
            _parse_last_modified(item.last_modified) or datetime.min.replace(tzinfo=timezone.utc),
            item.suggested_lane == "student_watch",
            item.cached_locally,
        ),
        reverse=True,
    )
    return candidates


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
            models = list(
                api.list_models(
                    search=query,
                    pipeline_tag="text-generation",
                    sort="downloads",
                    limit=limit_per_query,
                )
            )
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
            is_instruct = any(kw in mid.lower() for kw in ("instruct", "chat", "-it"))
            is_base = any(kw in mid.lower() for kw in ("-base", ".base", " base"))

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
                is_base=is_base,
                cached_locally=_check_hf_cache(mid),
            )
            candidates.append(c)
            added += 1

        if verbose:
            print(f" +{added}")

    _seed_curated_candidates(candidates, seen, max_params_b)

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
        # 1. Benchmark quality (20%) — useful, but not dominant for student FT
        if c.humaneval is not None:
            bench = c.humaneval / 100.0
        else:
            bench = 0.50  # neutral for unknown modern models

        # 2. Model capacity (20%) — bigger within budget = more capable
        size = c.param_b / max_params

        # 3. Fine-tuning fit (15%) — prefer base checkpoints, then instruct
        if c.is_base:
            finetune_fit = 1.0
        elif c.is_instruct:
            finetune_fit = 0.75
        else:
            finetune_fit = 0.4

        # 4. Community signals (15%) — downloads + likes
        community = (c.downloads / max_dl) * 0.6 + (c.likes / max_likes) * 0.4

        # 5. VRAM efficiency (10%) — sweet spot at ~70% utilization
        utilization = c.estimated_vram_gb / vram_budget_gb
        fit = max(0.0, 1.0 - abs(utilization - 0.7) * 3)

        # 6. Trusted author (5%)
        author = 1.0 if c.author in TRUSTED_AUTHORS else 0.3

        # 7. Cached locally (7%) — important on a saturated filesystem
        cached = 1.0 if c.cached_locally else 0.0

        # 8. Generation fit (15%) — prefer recent student families
        generation = _generation_fit(c.model_id)

        c.score = round(
            bench * 20
            + size * 20
            + finetune_fit * 18
            + community * 5
            + fit * 10
            + author * 5
            + cached * 7
            + generation * 15,
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
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    CACHE_FILE.write_text(json.dumps(data, indent=2))


def load_cache() -> list[ModelCandidate] | None:
    for cache_file in _cache_candidates():
        if not cache_file.exists():
            continue
        try:
            data = json.loads(cache_file.read_text())
            age_h = (time.time() - data["timestamp"]) / 3600
            if age_h > CACHE_TTL_HOURS:
                continue
            candidates = [ModelCandidate(**c) for c in data["candidates"]]
            if candidates:
                return candidates
        except Exception:
            continue
    return None


def save_watch_cache(entries: list[WatchCandidate]) -> None:
    data = {
        "timestamp": time.time(),
        "entries": [asdict(entry) for entry in entries],
    }
    WATCH_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    WATCH_CACHE_FILE.write_text(json.dumps(data, indent=2))


def load_watch_cache() -> list[WatchCandidate] | None:
    if not WATCH_CACHE_FILE.exists():
        return None
    try:
        data = json.loads(WATCH_CACHE_FILE.read_text())
        age_h = (time.time() - data["timestamp"]) / 3600
        if age_h > CACHE_TTL_HOURS:
            return None
        entries = [WatchCandidate(**entry) for entry in data["entries"]]
        if entries:
            return entries
    except Exception:
        return None
    return None


def _file_age_hours(path: Path) -> float | None:
    try:
        return max(0.0, (time.time() - path.stat().st_mtime) / 3600)
    except OSError:
        return None


def _load_selection_record() -> tuple[dict | None, Path | None]:
    for selection_file in _selection_candidates():
        if not selection_file.exists():
            continue
        try:
            data = json.loads(selection_file.read_text())
        except Exception:
            continue
        model_id = str(data.get("model_id", "")).strip()
        if model_id:
            return data, selection_file
    return None, None


def ensure_watch_report(
    *,
    task: str = "code",
    max_params_b: float = 0.0,
    days: int = 365,
    vram_budget_gb: float = 0.0,
    refresh: bool = False,
    verbose: bool = False,
) -> tuple[list[WatchCandidate], Path]:
    if max_params_b <= 0:
        _gpu_name, detected_vram = probe_gpu()
        resolved_vram = vram_budget_gb or detected_vram or 4.0
        max_params_b = auto_max_params(resolved_vram)
    entries = None if refresh else load_watch_cache()
    if entries is None:
        entries = watch_recent_releases(
            task=task,
            max_params_b=max_params_b,
            days=days,
            verbose=verbose,
        )
        save_watch_cache(entries)
    report_path = write_watch_report(entries)
    return entries, report_path


def ensure_model_selection(
    *,
    fallback_model: str = FALLBACK_MODEL,
    task: str = "code",
    seq_len: int = 512,
    vram_budget_gb: float = 0.0,
    max_params_b: float = 0.0,
    watch: bool = True,
    watch_days: int = 365,
    refresh: bool = False,
    verbose: bool = False,
) -> dict:
    selection_data, selection_path = _load_selection_record()
    selection_age_hours = (
        None if selection_path is None else _file_age_hours(selection_path)
    )

    gpu_name, detected_vram = probe_gpu()
    resolved_vram = vram_budget_gb or detected_vram or 4.0
    resolved_max_params = max_params_b or auto_max_params(resolved_vram)

    watch_report_path = None
    if watch:
        _entries, watch_report_path = ensure_watch_report(
            task=task,
            max_params_b=resolved_max_params,
            days=watch_days,
            vram_budget_gb=resolved_vram,
            refresh=refresh,
            verbose=verbose,
        )

    selection_fresh = (
        selection_data is not None
        and selection_age_hours is not None
        and selection_age_hours <= CACHE_TTL_HOURS
    )
    if selection_fresh and not refresh:
        return {
            "model_id": str(selection_data["model_id"]),
            "source": "selection_cache_fresh",
            "reason": "existing selected_model.json is still fresh",
            "selection_path": None if selection_path is None else str(selection_path),
            "selection_age_hours": selection_age_hours,
            "watch_report_path": (
                None if watch_report_path is None else str(watch_report_path)
            ),
            "vram_budget_gb": resolved_vram,
            "max_params_b": resolved_max_params,
            "gpu_name": gpu_name,
            "refreshed": False,
        }

    try:
        candidates = None if refresh else load_cache()
        if candidates is None:
            candidates = search_hub(
                task=task,
                max_params_b=resolved_max_params,
                verbose=verbose,
            )
            if candidates:
                save_cache(candidates)
        ranked = rank_candidates(candidates or [], resolved_vram, seq_len=seq_len)
        if ranked:
            selected = ranked[0]
            write_selection(selected, watch_report_path=watch_report_path)
            return {
                "model_id": selected.model_id,
                "source": "selection_refreshed",
                "reason": "refreshed automatic student selection from Hugging Face Hub",
                "selection_path": str(SELECTION_FILE),
                "selection_age_hours": 0.0,
                "watch_report_path": (
                    None if watch_report_path is None else str(watch_report_path)
                ),
                "vram_budget_gb": resolved_vram,
                "max_params_b": resolved_max_params,
                "gpu_name": gpu_name,
                "refreshed": True,
            }
    except Exception as exc:
        if selection_data is not None:
            return {
                "model_id": str(selection_data["model_id"]),
                "source": "selection_stale_reused",
                "reason": f"hub refresh failed, reusing existing selected model: {exc}",
                "selection_path": (
                    None if selection_path is None else str(selection_path)
                ),
                "selection_age_hours": selection_age_hours,
                "watch_report_path": (
                    None if watch_report_path is None else str(watch_report_path)
                ),
                "vram_budget_gb": resolved_vram,
                "max_params_b": resolved_max_params,
                "gpu_name": gpu_name,
                "refreshed": False,
            }

    if selection_data is not None:
        return {
            "model_id": str(selection_data["model_id"]),
            "source": "selection_stale_reused",
            "reason": "no ranked candidates returned, reusing existing selected model",
            "selection_path": None if selection_path is None else str(selection_path),
            "selection_age_hours": selection_age_hours,
            "watch_report_path": (
                None if watch_report_path is None else str(watch_report_path)
            ),
            "vram_budget_gb": resolved_vram,
            "max_params_b": resolved_max_params,
            "gpu_name": gpu_name,
            "refreshed": False,
        }

    return {
        "model_id": fallback_model,
        "source": "fallback",
        "reason": "no selected model available; using fallback default",
        "selection_path": None,
        "selection_age_hours": None,
        "watch_report_path": (
            None if watch_report_path is None else str(watch_report_path)
        ),
        "vram_budget_gb": resolved_vram,
        "max_params_b": resolved_max_params,
        "gpu_name": gpu_name,
        "refreshed": False,
    }


def write_watch_report(entries: list[WatchCandidate]) -> Path:
    grouped = {
        "student_watch": [asdict(entry) for entry in entries if entry.suggested_lane == "student_watch"],
        "teacher_watch": [asdict(entry) for entry in entries if entry.suggested_lane == "teacher_watch"],
        "manual_review": [asdict(entry) for entry in entries if entry.suggested_lane == "manual_review"],
    }
    payload = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "state_dir": str(STATE_DIR),
        "llm_root": str(llm_root()),
        **grouped,
        "entries": [asdict(entry) for entry in entries],
    }
    WATCH_REPORT_FILE.parent.mkdir(parents=True, exist_ok=True)
    WATCH_REPORT_FILE.write_text(json.dumps(payload, indent=2))
    return WATCH_REPORT_FILE


def load_validation_registry() -> dict:
    if not VALIDATION_REGISTRY_FILE.exists():
        return {"updated_at": None, "models": {}}
    try:
        data = json.loads(VALIDATION_REGISTRY_FILE.read_text())
    except Exception:
        return {"updated_at": None, "models": {}}
    models = data.get("models")
    if not isinstance(models, dict):
        models = {}
    return {
        "updated_at": data.get("updated_at"),
        "models": models,
    }


def save_validation_registry(registry: dict) -> None:
    payload = {
        "updated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "models": registry.get("models", {}),
    }
    VALIDATION_REGISTRY_FILE.parent.mkdir(parents=True, exist_ok=True)
    VALIDATION_REGISTRY_FILE.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def cache_dirs_for_model(model_id: str) -> list[Path]:
    suffix = f"models--{model_id.replace('/', '--')}"
    return [root / suffix for root in hf_cache_roots() if (root / suffix).exists()]


def cache_bytes_for_model(model_id: str) -> int:
    total = 0
    for cache_dir in cache_dirs_for_model(model_id):
        for path in cache_dir.rglob("*"):
            try:
                if path.is_file():
                    total += path.stat().st_size
            except OSError:
                continue
    return total


def protected_models() -> set[str]:
    protected = set(PINNED_MODELS)
    registry = load_validation_registry()
    registry_models = registry.get("models", {})
    selection, _selection_path = _load_selection_record()
    if selection is not None:
        model_id = str(selection.get("model_id") or "").strip()
        selected_status = str(
            (registry_models.get(model_id) or {}).get("status") or ""
        ).strip().lower()
        if model_id and selected_status != "rejected":
            protected.add(model_id)
    return protected


def mark_model_validation(
    *,
    model_id: str,
    status: str,
    reason: str | None = None,
    keep_cached: bool | None = None,
    source: str = "manual",
) -> dict:
    normalized_status = str(status or "").strip().lower()
    if normalized_status not in {"validated", "rejected", "pending_review"}:
        raise SystemExit(
            "--mark-status must be one of: validated, rejected, pending_review"
        )
    registry = load_validation_registry()
    models = registry.setdefault("models", {})
    keep_flag = keep_cached
    if keep_flag is None:
        keep_flag = normalized_status == "validated"
    entry = {
        "status": normalized_status,
        "reason": reason,
        "keep_cached": bool(keep_flag),
        "source": source,
        "updated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "cached_locally": _check_hf_cache(model_id),
        "cache_bytes": cache_bytes_for_model(model_id),
    }
    models[model_id] = entry
    save_validation_registry(registry)
    if normalized_status == "rejected":
        for selection_file in _selection_candidates():
            if not selection_file.exists():
                continue
            try:
                data = json.loads(selection_file.read_text())
            except Exception:
                continue
            if str(data.get("model_id") or "").strip() == model_id:
                selection_file.unlink(missing_ok=True)
    return entry


def prune_unvalidated_models(*, dry_run: bool = True) -> dict:
    registry = load_validation_registry()
    models = registry.get("models", {})
    protected = protected_models()
    pruned: list[dict] = []
    for model_id, entry in sorted(models.items()):
        status = str(entry.get("status") or "").strip().lower()
        if status == "validated":
            continue
        if entry.get("keep_cached"):
            continue
        if model_id in protected:
            continue
        cache_dirs = cache_dirs_for_model(model_id)
        if not cache_dirs:
            continue
        cache_bytes = cache_bytes_for_model(model_id)
        action = {
            "model_id": model_id,
            "status": status,
            "cache_dirs": [str(path) for path in cache_dirs],
            "cache_bytes": cache_bytes,
            "dry_run": dry_run,
        }
        if not dry_run:
            for cache_dir in cache_dirs:
                shutil.rmtree(cache_dir, ignore_errors=True)
            entry["cached_locally"] = False
            entry["cache_bytes"] = 0
            entry["cache_removed_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
        pruned.append(action)
    if not dry_run:
        save_validation_registry(registry)
    return {
        "dry_run": dry_run,
        "protected_models": sorted(protected),
        "pruned": pruned,
        "total_cache_bytes": sum(item["cache_bytes"] for item in pruned),
    }


# ── Download & validate ───────────────────────────────────────────────────


def download_model(model_id: str) -> Path:
    """Download model snapshot to HF cache."""
    from huggingface_hub import snapshot_download

    print(f"\nDownloading {model_id} ...")
    path = snapshot_download(model_id)
    print(f"Done -> {path}")
    print(f"LLM root -> {llm_root()}")
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
    watch_report_path: Path | None = None,
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
    if watch_report_path is not None:
        data["watch_report_path"] = str(watch_report_path)
    SELECTION_FILE.parent.mkdir(parents=True, exist_ok=True)
    SELECTION_FILE.write_text(json.dumps(data, indent=2))
    print(f"\nSelection -> {SELECTION_FILE}")


def auto_max_params(vram_budget_gb: float) -> float:
    if vram_budget_gb >= 22:
        return 9.0
    if vram_budget_gb >= 16:
        return 8.0
    if vram_budget_gb >= 10:
        return 4.0
    if vram_budget_gb >= 6:
        return 2.0
    return 1.5


def resolve_registry_target_model(
    explicit_model: str | None,
    selected: ModelCandidate | None = None,
) -> str | None:
    if explicit_model and explicit_model.strip():
        return explicit_model.strip()
    if selected is not None:
        return selected.model_id
    selection, _selection_path = _load_selection_record()
    if selection is not None:
        model_id = str(selection.get("model_id") or "").strip()
        if model_id:
            return model_id
    return None


# ── CLI ───────────────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Search, rank, and download fine-tuning models from HuggingFace Hub.",
    )
    parser.add_argument(
        "--vram",
        type=float,
        default=0,
        help="VRAM budget in GB (0 = auto-detect)",
    )
    parser.add_argument(
        "--max-params",
        type=float,
        default=0,
        help="Max parameter count in billions (0 = auto-fit the detected VRAM class)",
    )
    parser.add_argument(
        "--seq-len",
        type=int,
        default=512,
        help="Training sequence length for VRAM estimation (default: 512)",
    )
    parser.add_argument(
        "--task",
        choices=["code", "general"],
        default="code",
        help="Model task focus (default: code)",
    )
    parser.add_argument(
        "--auto",
        action="store_true",
        help="Auto-select the best model (rank 1)",
    )
    parser.add_argument(
        "--pick",
        type=int,
        default=0,
        metavar="N",
        help="Select the model at rank N",
    )
    parser.add_argument(
        "--download",
        action="store_true",
        help="Download the selected model to HF cache",
    )
    parser.add_argument(
        "--validate",
        action="store_true",
        help="Validate architecture compatibility after selection",
    )
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="Force refresh from HuggingFace Hub (ignore cache)",
    )
    parser.add_argument(
        "--watch",
        action="store_true",
        help="Query recent releases from trusted authors and write a watch report",
    )
    parser.add_argument(
        "--watch-days",
        type=int,
        default=365,
        help="Recency window in days for the trusted-author web watch (default: 365)",
    )
    parser.add_argument(
        "--watch-top",
        type=int,
        default=8,
        help="Show top N recent watch entries (default: 8)",
    )
    parser.add_argument(
        "--top",
        type=int,
        default=15,
        help="Show top N candidates (default: 15)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output ranked list as JSON",
    )
    parser.add_argument(
        "--target-model",
        default=None,
        help="Explicit model id for validation registry operations",
    )
    parser.add_argument(
        "--mark-status",
        choices=["validated", "rejected", "pending_review"],
        default=None,
        help="Record the selected/target model as validated, rejected, or pending_review",
    )
    parser.add_argument(
        "--mark-reason",
        default=None,
        help="Optional note stored with --mark-status",
    )
    parser.add_argument(
        "--keep-cached",
        action="store_true",
        help="Keep the cached model even when it is not validated",
    )
    parser.add_argument(
        "--prune-unvalidated",
        action="store_true",
        help="Delete cached models marked as rejected/pending_review unless protected",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Apply destructive cleanup for --prune-unvalidated (default is dry-run)",
    )
    args = parser.parse_args()

    if not any(
        (
            args.auto,
            args.pick,
            args.download,
            args.validate,
            args.refresh,
            args.watch,
        )
    ):
        payload: dict[str, object] = {}
        if args.mark_status:
            target_model = resolve_registry_target_model(args.target_model)
            if not target_model:
                raise SystemExit(
                    "No target model available. Use --target-model or create a selection first."
                )
            entry = mark_model_validation(
                model_id=target_model,
                status=args.mark_status,
                reason=args.mark_reason,
                keep_cached=args.keep_cached or None,
                source="model_selector_cli",
            )
            payload["marked"] = {"model_id": target_model, "entry": entry}
        if args.prune_unvalidated:
            payload["prune"] = prune_unvalidated_models(dry_run=not args.yes)
        if payload:
            if args.json:
                print(json.dumps(payload, indent=2, ensure_ascii=False))
            else:
                if "marked" in payload:
                    marked = payload["marked"]
                    print(
                        "[registry] "
                        f"{marked['model_id']} -> {marked['entry']['status']} "
                        f"(keep_cached={marked['entry']['keep_cached']})"
                    )
                    print(f"Registry -> {VALIDATION_REGISTRY_FILE}")
                if "prune" in payload:
                    prune_payload = payload["prune"]
                    action = "would remove" if prune_payload["dry_run"] else "removed"
                    print(
                        f"[cleanup] {action} {len(prune_payload['pruned'])} model cache(s) "
                        f"for {prune_payload['total_cache_bytes'] / 1024**3:.2f} GiB"
                    )
                    for item in prune_payload["pruned"]:
                        print(
                            f"  - {item['model_id']} ({item['status']}, "
                            f"{item['cache_bytes'] / 1024**3:.2f} GiB)"
                        )
            return

    # ── GPU detection ─────────────────────────────────────────────────
    gpu_name, detected_vram = probe_gpu()
    vram_budget = args.vram or detected_vram
    if vram_budget <= 0:
        vram_budget = 4.0
        if not args.json:
            print("No GPU detected and no --vram given. Using 4 GB default.\n")
    max_params = args.max_params or auto_max_params(vram_budget)

    if not args.json:
        print(f"  GPU         : {gpu_name or 'none'}")
        print(f"  VRAM budget : {vram_budget:.1f} GB")
        print(f"  Max params  : {max_params:.1f} B")
        print(f"  Seq length  : {args.seq_len}")
        print(f"  Task        : {args.task}")
        print(f"  State dir   : {STATE_DIR}")
        print()

    watch_entries: list[WatchCandidate] | None = None
    watch_report_path: Path | None = None
    if args.watch:
        watch_entries = None if args.refresh else load_watch_cache()
        if watch_entries is None:
            if not args.json:
                print("Watching recent trusted releases ...")
            watch_entries = watch_recent_releases(
                task=args.task,
                max_params_b=max_params,
                days=args.watch_days,
                verbose=not args.json,
            )
            save_watch_cache(watch_entries)
        watch_report_path = write_watch_report(watch_entries)

    # ── Search / cache ────────────────────────────────────────────────
    candidates = None if args.refresh else load_cache()
    if candidates is None:
        if not args.json:
            print("Searching HuggingFace Hub ...")
        candidates = search_hub(
            task=args.task,
            max_params_b=max_params,
            verbose=not args.json,
        )
        if candidates:
            save_cache(candidates)
    else:
        if not args.json:
            print(f"Using cached results ({len(candidates)} models)\n")

    # ── Rank ──────────────────────────────────────────────────────────
    ranked = rank_candidates(candidates, vram_budget, seq_len=args.seq_len)
    if not ranked:
        print(
            f"\nNo models found fitting {vram_budget:.1f} GB VRAM budget "
            f"with max {max_params:.1f}B params.",
            file=sys.stderr,
        )
        sys.exit(1)

    top = ranked[: args.top]

    # ── JSON output ───────────────────────────────────────────────────
    if args.json:
        if args.watch:
            print(
                json.dumps(
                    {
                        "ranked": [asdict(c) for c in top],
                        "watch_report_path": (
                            None if watch_report_path is None else str(watch_report_path)
                        ),
                    },
                    indent=2,
                )
            )
        else:
            print(json.dumps([asdict(c) for c in top], indent=2))
        return

    if watch_entries:
        print(
            f"\nRecent trusted releases to review ({min(len(watch_entries), args.watch_top)} shown):\n"
        )
        for index, entry in enumerate(watch_entries[: args.watch_top], 1):
            print(entry.summary_line(index))
        if watch_report_path is not None:
            print(f"\nWatch report -> {watch_report_path}")

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
        print("\nRe-run with --auto or --pick N to select a model.")
        return

    # ── Download ──────────────────────────────────────────────────────
    if args.download:
        download_model(selected.model_id)

    # ── Validate ──────────────────────────────────────────────────────
    validation = None
    validation_error = None
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
                validation_error = str(e)
                print(f"  Validation failed: {e}", file=sys.stderr)

    # ── Write selection ───────────────────────────────────────────────
    write_selection(selected, validation, watch_report_path=watch_report_path)

    final_mark_status = args.mark_status
    final_mark_reason = args.mark_reason
    if final_mark_status is None:
        if validation is not None:
            final_mark_status = "validated"
            final_mark_reason = final_mark_reason or "model validation succeeded"
        elif validation_error is not None:
            final_mark_status = "rejected"
            final_mark_reason = final_mark_reason or validation_error
        elif args.download:
            final_mark_status = "pending_review"
            final_mark_reason = final_mark_reason or "downloaded for testing; awaiting validation"

    if final_mark_status is not None:
        entry = mark_model_validation(
            model_id=selected.model_id,
            status=final_mark_status,
            reason=final_mark_reason,
            keep_cached=args.keep_cached or None,
            source="model_selector_flow",
        )
        print(
            "[registry] "
            f"{selected.model_id} -> {entry['status']} "
            f"(keep_cached={entry['keep_cached']})"
        )
        print(f"Registry -> {VALIDATION_REGISTRY_FILE}")

    if args.prune_unvalidated:
        prune_payload = prune_unvalidated_models(dry_run=not args.yes)
        action = "would remove" if prune_payload["dry_run"] else "removed"
        print(
            f"[cleanup] {action} {len(prune_payload['pruned'])} model cache(s) "
            f"for {prune_payload['total_cache_bytes'] / 1024**3:.2f} GiB"
        )
        for item in prune_payload["pruned"]:
            print(
                f"  - {item['model_id']} ({item['status']}, "
                f"{item['cache_bytes'] / 1024**3:.2f} GiB)"
            )

    print("\nUsage:")
    print(f"  python run_local.py stm32 --model {selected.model_id}")
    print(f"  python batch_local.py --student-model {selected.model_id}")


if __name__ == "__main__":
    main()
