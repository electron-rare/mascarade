# Unsloth GPU Fine-Tuning Guide

Date de reference: 2026-03-16

Guide complet pour le fine-tuning GPU accelere avec Unsloth dans Mascarade. Ce document couvre les exigences materielles, les couts estimes, les techniques d'optimisation memoire et des exemples pratiques.

## Table des matieres

- [Vue d'ensemble](#vue-densemble)
- [Exigences materielles](#exigences-materielles)
- [Reduction de VRAM](#reduction-de-vram)
- [Configuration optimale](#configuration-optimale)
- [Exemples de code](#exemples-de-code)
- [Couts estimes](#couts-estimes)
- [Troubleshooting](#troubleshooting)

## Vue d'ensemble

Unsloth est un framework de fine-tuning optimise qui offre:

- **2-5x plus rapide** que les frameworks standards (QLoRA, Axolotl)
- **70-80% de reduction VRAM** via quantification 4-bit optimisee
- **Support GRPO** pour le reinforcement learning (5GB VRAM minimum)
- **Export GGUF Dynamic 2.0** avec quantification per-layer

### Cas d'usage dans Mascarade

Mascarade utilise Unsloth pour fine-tuner des modeles specialises par domaine (STM32, KiCad, SPICE, IoT, etc.) sur des GPUs grand public. Le pipeline complet:

1. **Distillation** — Un gros teacher (Qwen 14B, Devstral 24B) genere des donnees de qualite
2. **SFT avec Unsloth** — Un petit student (Qwen 1.5B-7B) apprend via QLoRA 4-bit
3. **Export GGUF** — Quantification Dynamic 2.0 pour inference locale via Ollama
4. **Deploiement** — Modele disponible via `mascarade-<domain>` alias

## Exigences materielles

### GPU NVIDIA requis

Unsloth necessite une GPU NVIDIA avec support CUDA. Configuration minimale et recommandee:

| Configuration | GPU | VRAM | Modeles supportes | Usage |
|---------------|-----|------|-------------------|-------|
| **Minimum** | GTX 1660 Ti | 6 GB | 0.5B-1.5B (QLoRA 4-bit) | Prototypage rapide |
| **Recommande** | RTX 3060 | 12 GB | 1.5B-3B (QLoRA 4-bit) | Production petits modeles |
| **Optimal** | RTX 4090 | 24 GB | 3B-20B (QLoRA 4-bit) | Production modeles moyens |
| **Pro** | A100 | 40/80 GB | 20B-70B (QLoRA 4-bit) | Gros modeles, RL avance |

### Configuration materielle validee

#### RTX 4090 (24 GB VRAM)

Configuration de reference pour Mascarade (machine `KXKM-AI`):

- **GPU**: NVIDIA GeForce RTX 4090
- **VRAM**: 24564 MiB
- **Classe**: `gpu_24gb_plus`
- **Profil operateur**: Detecte automatiquement

**Capacites validees:**

- `1 x Qwen3-8B` + `2 x Qwen3-4B` en parallele (seq_len=768)
- `Qwen2.5-Coder-7B` full SFT + DPO (seq_len=1536)
- `Devstral-24B` teacher en offload mode (distillation)
- `Qwen3.5-35B-GPTQ-Int4` inference (teacher seulement)

**Charge maximale observee:**

```bash
# Training-only (pas de distillation simultanee)
# Student: Qwen3-4B-Instruct-2507, seq_len=1024
slots=1: 78.01s, pic VRAM 9532 MiB
slots=2: 42.01s, pic VRAM 17119 MiB  # Speedup 1.857x
```

#### RTX 3060 (12 GB VRAM)

Configuration budget pour developpement:

- **Modeles supportes**: Qwen2.5-Coder-1.5B, Qwen3-4B (QLoRA 4-bit)
- **Seq length max**: 2048 tokens
- **Parallelisme**: 1 slot training uniquement
- **Limitations**: Pas de teacher GPU simultane, utiliser Ollama CPU

#### T4 (16 GB VRAM) — Google Colab gratuit

Configuration cloud pour fine-tuning occasionnel:

- **Modeles supportes**: Qwen2.5-Coder-7B (QLoRA 4-bit)
- **Seq length max**: 2048 tokens
- **Duree session**: ~60 min par domaine (2000 exemples, 1 epoch)
- **Voir**: `finetune/COLAB_GUIDE.md` pour workflow complet

### Versions logicielles

```bash
# Versions validees (mars 2026)
Python: 3.11+
CUDA: 12.1+
PyTorch: 2.3+
Unsloth: 2026.3.4+
Transformers: 4.42+ (channel=main pour Qwen3.5)
```

**Bootstrap environnement:**

```bash
cd /ai/saisail/mascarade
. ./scripts/llm_env.sh
TRANSFORMERS_CHANNEL=main ./scripts/bootstrap_finetune_env.sh
./scripts/download_latest_finetune_models.sh
```

## Reduction de VRAM

Unsloth propose plusieurs techniques pour reduire l'empreinte memoire:

### 1. Quantification 4-bit (70% reduction)

**NF4 (Normal Float 4-bit)** — Quantification optimale pour les poids pre-entraines:

```python
from unsloth import FastLanguageModel

model, tokenizer = FastLanguageModel.from_pretrained(
    model_name="unsloth/qwen2.5-coder-7b-bnb-4bit",
    max_seq_length=2048,
    dtype=None,  # Auto-detect (bf16 si supporte, sinon fp16)
    load_in_4bit=True,  # 70% reduction VRAM
)
```

**Reduction observee:**

| Modele | FP16 (baseline) | 4-bit NF4 | Reduction |
|--------|----------------|-----------|-----------|
| Qwen2.5-Coder-7B | ~28 GB | ~8 GB | 71% |
| Qwen3-4B | ~16 GB | ~5 GB | 69% |
| Qwen3.5-9B | ~36 GB | ~11 GB | 69% |

### 2. Gradient Checkpointing (+30% reduction)

**Unsloth Gradient Checkpointing** — Recalcule les activations au lieu de les stocker:

```python
model = FastLanguageModel.get_peft_model(
    model,
    r=16,
    target_modules=["q_proj", "k_proj", "v_proj", "o_proj",
                    "gate_proj", "up_proj", "down_proj"],
    lora_alpha=16,
    lora_dropout=0,  # 0 est optimise pour Unsloth
    bias="none",
    use_gradient_checkpointing="unsloth",  # +30% reduction VRAM
    random_state=3407,
    max_seq_length=2048,
)
```

**Impact cumule (4-bit + gradient checkpointing):**

- Qwen2.5-Coder-7B: `~28 GB → ~5.5 GB` (**80% reduction totale**)
- Permet de fine-tuner un 7B sur une RTX 3060 12GB

### 3. Optimisations additionnelles

#### Flash Attention 2

Active automatiquement par Unsloth, reduit la complexite memoire de O(n²) a O(n):

```python
# Rien a faire, Unsloth l'active par defaut
# Gain: ~20-30% reduction supplementaire sur longues sequences
```

#### Optimizer 8-bit

Reduit l'empreinte memoire de l'optimizer (Adam → AdamW 8-bit):

```python
from trl import SFTConfig

args = SFTConfig(
    per_device_train_batch_size=2,
    gradient_accumulation_steps=4,  # Effective batch = 8
    optim="adamw_8bit",  # Reduction optimizer
    output_dir="outputs",
)
```

#### Batch size adaptatif

Ajuster batch size selon VRAM disponible:

| VRAM libre | Batch size | Grad accum | Effective batch |
|------------|-----------|------------|----------------|
| 6-8 GB | 1 | 8 | 8 |
| 8-12 GB | 2 | 4 | 8 |
| 12-20 GB | 4 | 2 | 8 |
| 20+ GB | 8 | 1 | 8 |

### 4. Techniques avancees

#### Dynamic Quantization 2.0 (Unsloth 2026.3+)

Quantification per-layer avec precision adaptative:

```python
# Couches sensibles (attention) en 6-bit
# Couches robustes (FFN) en 4-bit
# Export GGUF avec calibration KL Divergence

from unsloth import FastLanguageModel

# Apres training
model.save_pretrained_merged("outputs/merged", tokenizer)
model.save_pretrained_gguf(
    "outputs/gguf",
    tokenizer,
    quantization_method="dynamic_v2",  # Dynamic 2.0
)
```

#### Sequence Length Packing

Combiner plusieurs exemples courts dans une meme sequence (reduit padding waste):

```python
# Active automatiquement par Unsloth si dataset contient des sequences courtes
# Gain: 10-20% reduction memoire et temps sur datasets avec sequences variees
```

## Configuration optimale

### Hyperparametres recommandes

Configuration validee pour Mascarade sur RTX 4090:

```python
from unsloth import FastLanguageModel
from trl import SFTTrainer, SFTConfig
from datasets import load_dataset

# 1. Charger le modele (4-bit)
model, tokenizer = FastLanguageModel.from_pretrained(
    model_name="unsloth/qwen2.5-coder-7b-bnb-4bit",
    max_seq_length=2048,
    dtype=None,
    load_in_4bit=True,
)

# 2. Configurer LoRA
model = FastLanguageModel.get_peft_model(
    model,
    r=16,  # Rank LoRA (16=baseline, 32-64=tasks complexes)
    target_modules=["q_proj", "k_proj", "v_proj", "o_proj",
                    "gate_proj", "up_proj", "down_proj"],
    lora_alpha=16,  # Scaling factor (= r pour baseline)
    lora_dropout=0,  # 0 est optimal pour Unsloth
    bias="none",
    use_gradient_checkpointing="unsloth",
    random_state=3407,
    max_seq_length=2048,
)

# 3. Charger dataset
dataset = load_dataset("json", data_files={"train": "data.jsonl"}, split="train")

# 4. Configuration training
trainer = SFTTrainer(
    model=model,
    tokenizer=tokenizer,
    train_dataset=dataset,
    args=SFTConfig(
        per_device_train_batch_size=2,
        gradient_accumulation_steps=4,  # Effective batch = 8
        warmup_ratio=0.03,
        num_train_epochs=1,
        learning_rate=2e-4,
        fp16=not torch.cuda.is_bf16_supported(),
        bf16=torch.cuda.is_bf16_supported(),
        logging_steps=10,
        optim="adamw_8bit",
        weight_decay=0.01,
        lr_scheduler_type="linear",
        seed=3407,
        output_dir="outputs",
    ),
)

# 5. Lancer training
trainer.train()

# 6. Sauvegarder
model.save_pretrained_merged("outputs/merged", tokenizer, save_method="merged_16bit")
model.save_pretrained_gguf("outputs/gguf", tokenizer, quantization_method="q4_k_m")
```

### Ajustements par taille de modele

| Taille | Learning rate | LoRA rank | Seq length | Batch size |
|--------|---------------|-----------|------------|------------|
| 0.5B-1.5B | 2e-4 | 16 | 2048 | 4 |
| 1.5B-3B | 2e-4 | 16-32 | 2048 | 2 |
| 3B-7B | 2e-4 | 32 | 2048 | 2 |
| 7B-13B | 1e-4 | 32-64 | 2048 | 1 |
| 13B-33B | 5e-5 | 64 | 2048 | 1 |

## Exemples de code

### Exemple 1: Fine-tuning simple (STM32)

Pipeline Unsloth complet pour domaine STM32:

```python
import torch
from unsloth import FastLanguageModel, is_bfloat16_supported
from trl import SFTTrainer, SFTConfig
from datasets import load_dataset

# Detection CUDA
if not torch.cuda.is_available():
    raise RuntimeError("CUDA non disponible. Unsloth necessite une GPU NVIDIA.")

# Charger modele (4-bit)
model, tokenizer = FastLanguageModel.from_pretrained(
    model_name="unsloth/qwen2.5-coder-7b-bnb-4bit",
    max_seq_length=2048,
    dtype=None,
    load_in_4bit=True,
)

# Configurer LoRA
model = FastLanguageModel.get_peft_model(
    model,
    r=16,
    target_modules=["q_proj", "k_proj", "v_proj", "o_proj",
                    "gate_proj", "up_proj", "down_proj"],
    lora_alpha=16,
    lora_dropout=0,
    bias="none",
    use_gradient_checkpointing="unsloth",
    random_state=3407,
    max_seq_length=2048,
)

# Charger dataset STM32
dataset = load_dataset(
    "json",
    data_files={"train": "finetune/datasets/stm32_chat.jsonl"},
    split="train"
)

# Configuration training
trainer = SFTTrainer(
    model=model,
    tokenizer=tokenizer,
    train_dataset=dataset,
    dataset_text_field="text",  # ShareGPT format
    max_seq_length=2048,
    args=SFTConfig(
        per_device_train_batch_size=2,
        gradient_accumulation_steps=4,
        warmup_ratio=0.03,
        num_train_epochs=1,
        learning_rate=2e-4,
        fp16=not is_bfloat16_supported(),
        bf16=is_bfloat16_supported(),
        logging_steps=10,
        optim="adamw_8bit",
        weight_decay=0.01,
        lr_scheduler_type="linear",
        seed=3407,
        output_dir="outputs/stm32",
    ),
)

# Training
trainer.train()

# Export
model.save_pretrained_merged("outputs/stm32/merged", tokenizer)
model.save_pretrained_gguf("outputs/stm32/gguf", tokenizer, quantization_method="q4_k_m")

print("Fine-tuning STM32 termine. Modele exporte dans outputs/stm32/")
```

### Exemple 2: Pipeline Mascarade complet

Utiliser le pipeline Unsloth integre dans Mascarade:

```python
from finetune.unsloth.pipeline import UnslothPipeline
from finetune.unsloth.config import UnslothConfig

# Configuration
config = UnslothConfig(
    model_name="unsloth/qwen2.5-coder-7b-bnb-4bit",
    max_seq_length=2048,
    lora_r=16,
    lora_alpha=16,
    learning_rate=2e-4,
    num_epochs=1,
    batch_size=2,
    gradient_accumulation_steps=4,
)

# Pipeline
pipeline = UnslothPipeline(config)
pipeline.load_model()

# Charger donnees
from datasets import load_dataset
train_data = load_dataset("json", data_files={"train": "data.jsonl"}, split="train")

# Training
pipeline.prepare_dataset(train_data)
pipeline.train()

# Export
pipeline.save_model("outputs/model")
pipeline.export_gguf("outputs/model.gguf", quantization="q4_k_m")

print("Pipeline termine.")
```

### Exemple 3: Workflow run_local.py

Utiliser le script `run_local.py` avec detection automatique du materiel:

```bash
cd /ai/saisail/mascarade
. venv_tuning/bin/activate

# Training simple (auto-detection materiel)
python finetune/run_local.py stm32 --device auto --epochs 1

# Training avance RTX 4090
python finetune/run_local.py platformio \
  --device gpu \
  --student-model Qwen/Qwen3.5-9B-Base \
  --max-source-samples 128 \
  --student-max-samples 384 \
  --seq-len 1536 \
  --epochs 2 \
  --auto-promote
```

### Exemple 4: Batch multi-domaines

Pipeline batch parallele pour fine-tuner plusieurs domaines:

```bash
cd /ai/saisail/mascarade
./scripts/parallel_domains_gpu_queue.sh iot spice platformio --offline
```

Ou via Python:

```bash
python finetune/batch_local.py iot spice platformio \
  --run-label production-batch \
  --device gpu \
  --student-model Qwen/Qwen3-4B-Instruct-2507 \
  --max-source-samples 64 \
  --samples-per-source 2 \
  --max-parallel-distills 1 \
  --max-parallel-gpu-trains 2 \
  --student-max-samples 256 \
  --seq-len 1024 \
  --epochs 1 \
  --offline
```

## Couts estimes

### Cloud (Google Colab)

| Configuration | VRAM | Prix | Modeles supportes | Duree (2000 ex, 1 epoch) |
|---------------|------|------|-------------------|--------------------------|
| **T4 (gratuit)** | 16 GB | Gratuit | Qwen 1.5B-7B (4-bit) | ~60 min |
| **V100** | 16 GB | ~$0.50/h | Qwen 7B-13B (4-bit) | ~30 min |
| **A100** | 40 GB | ~$2.50/h | Qwen 13B-70B (4-bit) | ~15 min |

**Cout mensuel estime (Colab gratuit):**

- 8 domaines x 1 fine-tune/mois x 60 min = **8h GPU/mois gratuit**
- Limite Colab gratuit: ~15-20h GPU/mois
- **Recommandation**: Colab gratuit suffit pour prototypage

### Hardware local (achat)

| GPU | Prix | VRAM | TDP | Cout electricite/mois* |
|-----|------|------|-----|------------------------|
| RTX 3060 | $329 | 12 GB | 170W | $12 |
| RTX 4060 Ti 16GB | $499 | 16 GB | 165W | $12 |
| RTX 4070 Ti | $799 | 12 GB | 285W | $20 |
| RTX 4090 | $1599 | 24 GB | 450W | $32 |
| RTX 5090 | $1999 | 32 GB | 575W | $41 |

*Usage 24/7, $0.15/kWh

**ROI estime (RTX 4090 vs Colab Pro):**

- Achat RTX 4090: $1599
- Colab Pro: $50/mois
- Break-even: 32 mois (~2.7 ans)
- **Recommandation**: Achat hardware si usage >15h/mois

### Mascarade production (VM locale)

Configuration actuelle (machine `192.168.0.119`):

- **GPU**: RTX 4090 (24 GB)
- **Cout achat**: $1599
- **Cout electricite**: ~$32/mois (usage intensif)
- **Throughput**: 8 domaines fine-tunes en parallele (~6-8h batch complet)
- **ROI**: Amorti en 2 ans vs cloud

## Troubleshooting

### CUDA Out of Memory (OOM)

**Symptomes:**

```
RuntimeError: CUDA out of memory. Tried to allocate 2.34 GiB
```

**Solutions:**

1. **Reduire batch size:**

```python
# De:
per_device_train_batch_size=4
gradient_accumulation_steps=2

# A:
per_device_train_batch_size=1
gradient_accumulation_steps=8  # Maintenir effective batch
```

2. **Reduire sequence length:**

```python
max_seq_length=1024  # Au lieu de 2048
```

3. **Activer gradient checkpointing:**

```python
use_gradient_checkpointing="unsloth"  # Deja actif par defaut
```

4. **Verifier VRAM libre avant training:**

```bash
nvidia-smi --query-compute-apps=pid,process_name,used_memory --format=csv,noheader,nounits
```

Si un process occupe deja la GPU, attendre ou tuer le process:

```bash
kill -9 <pid>
```

### ModuleNotFoundError: No module named 'unsloth'

**Solution:**

```bash
pip install "unsloth[colab-new] @ git+https://github.com/unslothai/unsloth.git"
```

Ou rebuild environnement complet:

```bash
cd /ai/saisail/mascarade
TRANSFORMERS_CHANNEL=main ./scripts/bootstrap_finetune_env.sh
```

### Training tres lent (plus lent que baseline)

**Causes possibles:**

1. **Flash Attention non active** (verifier logs):

```
Using Flash Attention 2: True  # Doit etre True
```

2. **dtype incorrect** (force FP32 au lieu de BF16/FP16):

```python
# Forcer bf16 si supporte
bf16=torch.cuda.is_bf16_supported(),
fp16=not torch.cuda.is_bf16_supported(),
```

3. **Gradient checkpointing trop agressif** (desactiver si VRAM suffit):

```python
use_gradient_checkpointing=None  # Desactive
```

### Export GGUF echoue

**Symptomes:**

```
ValueError: GGUF export requires llama.cpp Python bindings
```

**Solution:**

```bash
pip install llama-cpp-python
```

Ou utiliser export Unsloth natif:

```python
model.save_pretrained_gguf("outputs/gguf", tokenizer, quantization_method="q4_k_m")
```

### Model ne charge pas (format incompatible)

**Symptomes:**

```
OSError: unsloth/qwen2.5-coder-7b-bnb-4bit does not appear to be a valid model
```

**Causes:**

- Modele non supporte par Unsloth (verifier liste modeles: [unsloth.ai/models](https://unsloth.ai/models))
- Nom incorrect (utiliser nom HuggingFace exact)

**Solution:**

Utiliser modeles Unsloth pre-quantifies:

```python
# Qwen2.5-Coder
"unsloth/qwen2.5-coder-1.5b-bnb-4bit"
"unsloth/qwen2.5-coder-7b-bnb-4bit"

# Llama 3.1
"unsloth/llama-3.1-8b-bnb-4bit"

# Mistral
"unsloth/mistral-7b-v0.3-bnb-4bit"
```

Ou charger modele standard puis quantifier manuellement:

```python
model, tokenizer = FastLanguageModel.from_pretrained(
    model_name="Qwen/Qwen2.5-Coder-7B",  # Modele standard HF
    max_seq_length=2048,
    dtype=None,
    load_in_4bit=True,  # Quantification a la volee
)
```

### Validation loss ne diminue pas

**Causes possibles:**

1. **Learning rate trop eleve:**

```python
learning_rate=2e-5  # Reduire de 2e-4 a 2e-5
```

2. **Dataset trop petit (<100 exemples):**

- Utiliser data augmentation
- Ajouter exemples synthetiques (distillation teacher)

3. **Epochs insuffisants:**

```python
num_train_epochs=2  # Augmenter de 1 a 2-3
```

4. **Overfitting sur training set:**

- Ajouter validation split
- Reduire LoRA rank: `r=8` au lieu de `r=16`

## References

### Documentation officielle

- Unsloth: [github.com/unslothai/unsloth](https://github.com/unslothai/unsloth)
- Unsloth Docs: [docs.unsloth.ai](https://docs.unsloth.ai)
- Unsloth Dynamic v2.0: [unsloth.ai/blog/dynamic-v2](https://unsloth.ai/blog/dynamic-v2)
- Unsloth GRPO: [unsloth.ai/docs/get-started/reinforcement-learning-rl-guide](https://unsloth.ai/docs/get-started/reinforcement-learning-rl-guide)

### Documentation Mascarade

- Pipeline local: `finetune/README.md`
- Cheatsheet: `docs/archive/finetuning/FINETUNING_CHEATSHEET_2026-03-06.md`
- Runbook operateur: `docs/FINETUNING_OPERATOR_RUNBOOK.md`
- SOTA fine-tuning: `docs/SOTA_FINETUNING_2026-03.md`
- Colab workflow: `finetune/COLAB_GUIDE.md`

### Papers & benchmarks

- SimPO (NeurIPS 2024): [arxiv.org/abs/2405.14734](https://arxiv.org/abs/2405.14734)
- Qwen2.5-Coder: [qwenlm.github.io/blog/qwen2.5-coder-family/](https://qwenlm.github.io/blog/qwen2.5-coder-family/)
- Fine-tuning benchmarks: [modal.com/blog/fine-tuning-llms](https://modal.com/blog/fine-tuning-llms)
- GGUF quantization: [github.com/ggerganov/llama.cpp/discussions](https://github.com/ggerganov/llama.cpp/discussions)

---

**Derniere mise a jour:** 2026-03-16
**Auteur:** Mascarade Team
**Licence:** MIT
