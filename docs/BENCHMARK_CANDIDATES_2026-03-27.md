# Benchmark Candidates Research — 2026-03-27

Veille modèles pour le pipeline fine-tuning RTX 4090 (KXKM-AI, 24GB VRAM).

## 1. JetBrains/Mellum-4b-sft-all ✅ EXCELLENT

- **Taille** : 4B paramètres, pré-entraîné sur 4T tokens
- **VRAM req.** : ~3-4 GB (Q4_K_M), RTX 4090 → large marge pour LoRA/QLoRA
- **Contexte** : 8 192 tokens
- **Langages** : 30+ (Python, C++, Kotlin, TS, Rust…)
- **Statut HF** : ✅ https://huggingface.co/JetBrains/Mellum-4b-sft-all
- **Benchmarks** : dépasse Qwen-2.5-Coder-7B, Seed-Coder-8B-Base, DeepSeek-Coder-5.7B sur RepoBench-C/SAFIM/HumanEval-Infilling
- **Fine-tuning** : excellent — déjà SFT, base idéale pour adaptation domaine (ESP32, KiCad, SPICE)
- **Verdict** : candidat étudiant prioritaire, en ligne avec l'auto_chain_next_lots bloqué le 2026-03-09

## 2. Qwen/Qwen3-Coder-Next-Base ⚠️ VRAM LIMITE

- **Architecture** : 80B total sparse MoE, 3B actifs par token, hybrid (GatedDeltaNet + attention)
- **Contexte** : 262 144 tokens natif
- **VRAM req.** : ~46 GB combiné (VRAM + RAM système) pour Q4_K_M — dépasse RTX 4090 seul
- **Statut HF** : ✅ https://huggingface.co/Qwen/Qwen3-Coder-Next-Base + GGUF Unsloth
- **Benchmarks** : SWE-Bench Verified >70% (SWE-Agent), SWE-Bench Pro 44.3%
- **Fine-tuning** : possible sur 4090 avec offloading RAM (~22 GB RAM système en plus)
- **Verdict** : candidat teacher potentiel; à tester seulement si offloading RAM disponible sur KXKM-AI

## 3. deepseek-ai/DeepSeek-V3.2 ❌ HORS PORTÉE

- **Taille** : 671B total, 37B actifs sparse MoE
- **VRAM req.** : 350-400 GB (INT4 multi-GPU) — incompatible RTX 4090
- **Verdict** : teacher-only en API (Mistral/Together), pas fine-tunable sur 4090

## Recommandation

| Rôle | Modèle | Action |
|---|---|---|
| Student prioritaire | JetBrains/Mellum-4b-sft-all | Lancer benchmark via auto_chain_next_lots quand GPU libre |
| Alternative student | Qwen/Qwen2.5-Coder-1.5B-Instruct | Déjà en place comme défaut |
| Teacher local | Qwen3-Coder-Next-Base (avec offloading) | Expérimental si RAM KXKM-AI > 64 GB |
| Teacher API | Mistral large / GPT-4o | Déjà câblé |

## Domaines embedded sans modèle dédié

Aucun LLM spécialisé ESP32/STM32/KiCad/PlatformIO n'existe encore en mars 2026.
Le corpus mascarade (143K rows, 11 domaines) reste l'approche optimale pour construire un modèle spécialisé.
