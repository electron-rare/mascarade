# State-of-the-Art Fine-Tuning — Mars 2026 (v2)

Recherche effectuee le 11/03/2026. Mise a jour apres recherche Reddit/forums specialises.
Contexte : pipeline QLoRA distribue, RTX 4090, modeles 0.5B-3B, code generation.

## Stack recommande

| Composant | Choix | Pourquoi |
|-----------|-------|----------|
| **Base model** | Qwen2.5-Coder-1.5B-Instruct | 61.6% HumanEval, meilleur <3B |
| **Framework** | Unsloth 2026.3.4 | 2-5x plus rapide, 70% moins VRAM, GRPO |
| **Dataset SFT** | Magicoder-OSS-Instruct-75K | Clean, divers, prouve |
| **Alignement** | SimPO (via TRL/Unsloth) | Pas de ref model, +6.4 vs DPO |
| **Reasoning** | GRPO (via Unsloth) | 5GB VRAM min, reasoning chains |
| **Donnees pref** | Synthetique (test-case verified) | Pas de bon dataset open-source |
| **Inference** | GGUF Dynamic 2.0 via llama.cpp | Export Unsloth, quant per-layer |
| **Distribution** | Parallel independent runs | 1 noeud = 1 experience |

## Modeles < 3B pour code

| Modele | Params | HumanEval | Notes |
|--------|--------|-----------|-------|
| **Qwen2.5-Coder-1.5B** | 1.5B | 61.6% | Leader <3B, 5.5T tokens training |
| **Qwen2.5-Coder-3B** | 3B | ~65% | Sweet spot si VRAM OK |
| StarCoder2-3B | 3B | ~56% | Stack v2, 600+ langages |
| DeepSeek-R1-Distill-Qwen-1.5B | 1.5B | ~55% | Reasoning/CoT |
| Qwen2.5-Coder-0.5B | 0.5B | ~40% | Ultra-rapide, edge deploy |
| ⚠️ **Qwen3-Coder-Next** | TBD | TBD | Annonce 03/03/2026, a surveiller |

## Frameworks fine-tuning

| Framework | Vitesse single-GPU | Multi-GPU | VRAM | Notes |
|-----------|-------------------|-----------|------|-------|
| **Unsloth 2026.3** | Le plus rapide (2-5x) | Non | 70-80% moins | GRPO, Dynamic GGUF 2.0 |
| Axolotl v0.8 | 1.8x plus lent | Oui (FSDP2) | Bon | QAT, GRPO, prod-ready |
| LLaMA-Factory | Bon (uses Unsloth) | Oui (DeepSpeed) | Bon | Web UI, zero-code |
| TorchTune | 24% plus lent | Limite | Bon | PyTorch natif |
| trl 0.24 | Baseline | Non | Standard | Compatible Unsloth |

## Alignement — Stack moderne

| Methode | Ref model? | Avantage | Recommande pour |
|---------|-----------|----------|-----------------|
| **SimPO** | Non | +6.4 AlpacaEval, +7.5 ArenaHard vs DPO | Petits modeles, robuste aux hyperparams |
| **GRPO** | Non | Reasoning chains, 5GB VRAM min | Modeles de raisonnement |
| ORPO | Non | Unifie SFT + alignement en 1 step | Simplicite maximale |
| KTO | Non | Feedback binaire (pas de paires) | Quand paires rares |
| DPO | Oui | Stable, bien compris | Baseline a battre |

## Hyperparametres optimaux QLoRA RTX 4090

| Parametre | Valeur recommandee |
|-----------|-------------------|
| Learning rate | 2e-4 (small), 1e-4 (>33B) |
| LoRA rank (r) | 16 (start), 32-64 (complex tasks) |
| LoRA alpha | 2x rank (r=16 → alpha=32) |
| Batch size | 2 (+ grad accum 4 → effective 8) |
| Quantization | NF4, double quantization |
| Optimizer | adamw_8bit |
| Warmup | ratio 0.03 |
| Extras | FlashAttention-2, NEFTune, rsLoRA |

## Datasets code

| Dataset | Taille | Methode | Usage |
|---------|--------|---------|-------|
| **Magicoder-OSS-Instruct-75K** | 75K | OSS-Instruct | SFT initial |
| OpenCodeInstruct | 5M | Self+Evol-Instruct | SFT large scale |
| evol-codealpaca-v1 | 110K | Evol-Instruct | WizardCoder style |
| CodeAlpaca-20k | 20K | Self-Instruct | Quick test (deja utilise) |
| The Stack v2 | Massive | Pre-training | Continued pre-training |

## GGUF export — Dynamic 2.0

- **Workflow optimal** : Unsloth train → save_pretrained_merged (FP16) → save_pretrained_gguf (Dynamic 2.0)
- **Dynamic 2.0** : quantification per-layer, couches sensibles en 6-bit, robustes en 4-bit
- Formats Apple Silicon : Q4_NL, Q5.1, Q5.0, Q4.1, Q4.0
- Calibration avec datasets curates (pas Wikipedia)
- Metrique : KL Divergence (pas perplexite)
- Compatible llama.cpp, Ollama, LM Studio

## Distribution

Pour 1.5B-3B : **pas besoin de multi-GPU**. RTX 4090 suffit (8-12 GB VRAM QLoRA).
- Strategie A (recommandee) : runs independants paralleles sur chaque noeud
- Strategie B (si necessaire) : DeepSpeed ZeRO-3 pour modeles > 7B

## Actions pour mascarade

1. [x] Integrer Unsloth comme backend dans StudentAgent (auto-select CUDA)
2. [x] Ajouter SimPO comme methode d'alignement dans ReinforcerAgent
3. [x] Ajouter export GGUF post-training dans StudentAgent (merge_and_quantize)
4. [x] Installer Unsloth 2026.3.4 sur KXKM-AI (RTX 4090)
5. [ ] Tester Qwen2.5-Coder-1.5B (upgrade depuis 0.5B)
6. [ ] Tester Magicoder-OSS-Instruct-75K comme dataset
7. [ ] Ajouter GRPO dans ReinforcerAgent (reasoning training)
8. [ ] Pipeline: SFT (Unsloth) → SimPO → GGUF Dynamic 2.0 → llama.cpp
9. [ ] Surveiller Qwen3-Coder-Next (mars 2026)

## Sources

- Unsloth: github.com/unslothai/unsloth
- Unsloth Dynamic v2.0: unsloth.ai/blog/dynamic-v2
- Unsloth GRPO: unsloth.ai/docs/get-started/reinforcement-learning-rl-guide
- SimPO: arxiv.org/abs/2405.14734 (NeurIPS 2024)
- Qwen2.5-Coder: qwenlm.github.io/blog/qwen2.5-coder-family/
- Qwen3-Coder-Next: arxiv.org/pdf/2603.00729v1
- Magicoder: github.com/ise-uiuc/magicoder
- StarCoder2: arxiv.org/abs/2402.19173
- Axolotl: github.com/axolotl-ai-cloud/axolotl
- Fine-tuning benchmarks: modal.com/blog/fine-tuning-llms
