"""Model VRAM size registry — estimated GPU memory requirements per Ollama model.

Used by the cluster router and P2P provider to route large-model requests
to peers with sufficient GPU VRAM, rather than letting them land on CPU RAM
and trigger OOM conditions.

Size estimates are conservative (actual peak usage during load, not just
static weights).  When a model is unknown, ``get_model_size_gb`` falls back
to a parameter-count heuristic derived from the model name.
"""

from __future__ import annotations

import re

# ── Known model sizes (GB, VRAM peak at Q4_K_M unless noted) ────────────────
_KNOWN_GB: dict[str, float] = {
    # ── Devstral / Mistral large ────────────────────────────────────────
    "devstral": 14.3,
    "devstral:latest": 14.3,
    # ── Phi family ──────────────────────────────────────────────────────
    "phi4": 9.1,
    "phi4:latest": 9.1,
    "phi4-mini": 2.6,
    "phi4-mini:latest": 2.6,
    "phi3": 2.4,
    "phi3:mini": 2.4,
    "phi3:latest": 2.4,
    # ── Qwen 3.5 ────────────────────────────────────────────────────────
    "qwen3.5:9b": 6.2,
    "qwen3.5:4b": 3.4,
    "qwen3.5:0.8b": 1.1,
    # ── Qwen 3 ──────────────────────────────────────────────────────────
    "qwen3:4b": 2.5,
    "qwen3:latest": 2.5,
    # ── Qwen 2.5 ────────────────────────────────────────────────────────
    "qwen2.5-coder:7b": 4.7,
    "qwen2.5-coder:latest": 4.7,
    "qwen2.5-coder:3b": 2.1,
    "qwen2.5-coder:1.5b": 1.1,
    "qwen2.5-coder:0.5b": 0.5,
    "qwen2.5:7b": 4.7,
    "qwen2.5:3b": 2.1,
    "qwen2.5:1.5b": 1.1,
    "qwen2.5:0.5b": 0.5,
    # ── DeepSeek R1 ─────────────────────────────────────────────────────
    "deepseek-r1:8b": 5.2,
    "deepseek-r1:7b": 4.5,
    "deepseek-r1:1.5b": 1.2,
    # ── Gemma 2 ─────────────────────────────────────────────────────────
    "gemma2:9b": 5.4,
    "gemma2:latest": 5.4,
    "gemma2:2b": 1.8,
    # ── GLM4 ────────────────────────────────────────────────────────────
    "glm4:9b": 5.5,
    "glm4:latest": 5.5,
    # ── Mistral 7B ──────────────────────────────────────────────────────
    "mistral:7b": 4.4,
    "mistral:latest": 4.4,
    # ── Llama 3.2 ───────────────────────────────────────────────────────
    "llama3.2:3b": 2.1,
    "llama3.2:latest": 2.1,
    "llama3.2:1b": 1.3,
    # ── StarCoder2 ──────────────────────────────────────────────────────
    "starcoder2:7b": 4.1,
    "starcoder2:latest": 4.1,
    # ── Specialised HF models ────────────────────────────────────────────
    "hf.co/mradermacher/CodeV-R1-Qwen-7B-i1-GGUF:IQ4_XS": 4.3,
    "hf.co/mradermacher/VeriReason-Qwen2.5-7b-RTLCoder-Verilog-GRPO-reasoning-tb-i1-GGUF:IQ4_XS": 4.3,
    "hf.co/mradermacher/RTLCoder-v1.1-GGUF:Q4_K_M": 4.4,
    "hf.co/QuantFactory/llm-compiler-7b-GGUF:latest": 3.8,
    "hf.co/TheBloke/law-LLM-GGUF:latest": 3.0,
    "hf.co/TheBloke/phi-2-electrical-engineering-GGUF:latest": 1.2,
    "hf.co/gabriellarson/UIGEN-X-4B-0729-GGUF:latest": 2.9,
    "brxce/stable-diffusion-prompt-generator:latest": 4.2,
    # ── Mascarade fine-tunes ─────────────────────────────────────────────
    "mascarade-esp32_local_v1:latest": 0.7,
    "mascarade-pio_local_v1:latest": 0.7,
    "mascarade-spice_local_v1:latest": 0.7,
    "mascarade-iot:latest": 3.6,
    # ── Embeddings ──────────────────────────────────────────────────────
    "bge-m3:latest": 1.2,
    # ── Small utility models ─────────────────────────────────────────────
    "tinyllama:latest": 0.7,
    "legraphista/Orpheus:3b-ft-q4_k_m": 2.4,
    "fixt/home-3b-v3:latest": 1.9,
    # ── Large distributed models (prima.cpp ring cluster) ──────────────
    "llama3-70b-q4_k_m": 40.0,
    "llama3.1-70b-q4_k_m": 40.0,
    "llama3-70b-q6_k": 54.0,
    "qwq-32b-q4_k_m": 20.0,
    "qwen2.5-72b-q4_k_m": 42.0,
    "deepseek-r1-70b-q4_k_m": 40.0,
    "deepseek-v3-671b-iq1_s": 130.0,
}

# Rough rule: Q4 quantisation ≈ 0.6 GB per billion params (with context overhead)
_GB_PER_BILLION = 0.6
_PARAM_RE = re.compile(r"[:\-_/](\d+(?:\.\d+)?)b(?:\b|[-_])", re.IGNORECASE)


def _heuristic_gb(model: str) -> float:
    match = _PARAM_RE.search(model)
    if match:
        try:
            return round(float(match.group(1)) * _GB_PER_BILLION, 1)
        except ValueError:
            pass
    return 0.0


def get_model_size_gb(model: str | None) -> float:
    """Return estimated VRAM requirement in GB for *model*.

    Returns 0.0 when unknown (treat as no constraint).
    """
    if not model:
        return 0.0
    model = model.strip()
    if model in _KNOWN_GB:
        return _KNOWN_GB[model]
    base = model.split(":")[0]
    if base in _KNOWN_GB:
        return _KNOWN_GB[base]
    return _heuristic_gb(model)


def can_fit_in_vram(model: str | None, vram_gb: float) -> bool:
    """True if *model* fits in *vram_gb* with 10 % headroom.

    Returns True when size is unknown (0.0) to avoid blocking unknown models.
    """
    size = get_model_size_gb(model)
    if size == 0.0:
        return True
    return vram_gb >= size * 1.1
