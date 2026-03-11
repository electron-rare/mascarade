# Fine-Tuning Research Report (2026-03-11)
## Sources: Reddit, HuggingFace forums, Unsloth docs, academic papers

### 1. Unsloth (Feb 2026)
- 12x faster MoE, embedding model support
- Dynamic 4-bit quantization (per-layer precision)
- GRPO: 5GB VRAM min, QLoRA compatible, 7-12x longer context RL
- Tips: >1000 rows→base model, <300→instruct, <12B→8GB VRAM

### 2. SimPO (NeurIPS 2024)
- +6.4 AlpacaEval 2 over DPO, +7.5 Arena-Hard
- No reference model needed, 2 inferences vs 4 for DPO
- More robust to hyperparameter choices
- Recommended starting point for alignment 2025-2026

### 3. Qwen2.5-Coder
- 0.5B-32B params, Base+Instruct variants
- 1.5B: 41.1 avg score, best <2B code model
- 32B-Instruct: outperforms DeepSeek-Coder-V2
- Qwen3-Coder-Next announced March 2026

### 4. QLoRA on RTX 4090
- Up to ~20B params with QLoRA
- r=16-32, lr=2e-4, NF4, batch 2 w/ grad accum 4
- FlashAttention-2 + Unsloth + Liger Kernel
- Wall-clock: Unsloth 3.2h vs Axolotl 5.8h (Llama-3.1 8B)

### 5. GGUF Export
- Step 1: save merged FP16 (canonical archive)
- Step 2: save_pretrained_gguf (q4_k_m, q8_0)
- Dynamic 2.0: per-layer quantization, Apple Silicon formats
- KL Divergence calibration (not perplexity)

### 6. Frameworks (<3B)
- Unsloth: fastest, lowest VRAM, single GPU
- Axolotl: YAML configs, multi-GPU, GRPO, QAT
- LLaMA-Factory: web UI, uses Unsloth backend
- TRL: HF ecosystem integration
- 2026 = year of fine-tuned small models
