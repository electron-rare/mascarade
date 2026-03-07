# Plan d'Optimisation 4090

Date de reference: 2026-03-07

## Objectif

Utiliser au mieux la machine locale pour le pipeline de fine-tuning Mascarade:

- CPU: preparation, tokenization, packing, manifests
- GPU: teacher quand il est actif, puis student training
- orchestration: overlap distillation/training quand le budget VRAM le permet

## Constat actuel

- `train_local.py` tokenise avec `padding="max_length"`, donc gaspille du compute et de la VRAM.
- le trainer reste en `fp16` par defaut alors que la RTX 4090 tient mieux le chemin `bf16`.
- le batch local fonctionne en deux phases: toutes les distills, puis tous les trainings.
- `llmfit` sert aujourd hui de garde-fou au niveau `run_local.py`, mais pas encore comme estimateur de budget batch.

## Direction retenue

### 1. Trainer GPU

- tokenization dynamique
- packing des sequences train en blocs de `seq_len`
- `NF4 + bfloat16` quand CUDA le supporte
- `flash_attention_2` si disponible, sinon `sdpa`
- `tf32` active
- `pin_memory` et workers dataloader ajustes

### 2. Batch scheduler

- modele producteur/consommateur
- une distillation terminee peut partir en merge puis en training sans attendre la fin de toutes les autres
- overlap distill/train autorise en mode `auto`, sauf teacher `local-hf`
- budget VRAM student auto-estime pour eviter les departs GPU trop optimistes
- si `max_parallel_gpu_trains=2`, le scheduler garde volontairement un seul slot student tant que le teacher `ollama` distille encore
- quand la file de distillation est vide, le scheduler decharge le teacher `ollama` via son API (`keep_alive=0`) puis peut ouvrir le deuxieme slot student

### 3. Politique GPU

- teacher lourd + student lourd: non
- teacher local-hf: exclusif GPU
- teacher API/Ollama + student: overlap possible si la VRAM libre reste suffisante
- teacher `ollama` 14B + `2 x` students 4B en meme temps: eviter pendant la phase distillation sur une seule RTX 4090
- `2 x` students 4B redeviennent exploitables en fin de batch si le teacher est decharge
- `llmfit` reste un garde-fou d inference, pas un estimateur exact de VRAM QLoRA

## Priorite d implementation

1. trainer plus efficace
2. batch streaming
3. doc d exploitation

## Sources officielles de reference

- TRL memory usage / packing / padding-free / activation offloading
- TRL Liger Kernel
- Transformers bitsandbytes / QLoRA / NF4
- PEFT quantization guide
- FlashAttention
- vLLM throughput / batching
- llmfit JSON plan
