# Fine-Tuning Cheatsheet

Date de reference: 2026-03-06

Version courte du document complet:

- voir `docs/FINETUNING_ETAT_DE_L_ART_2026-03-06.md` pour le detail

## 1. Regle simple

Pour cette machine:

- ne vise pas un gros fine-tuning dense
- vise un petit student local
- utilise un gros teacher pour generer de bonnes donnees
- fais du SFT en LoRA/QLoRA

## 2. Quel chemin choisir

| Si ton besoin est... | Fais ca |
|---|---|
| format, style, procedure, ton | SFT |
| transferer la qualite d un gros modele vers un petit | distillation + SFT |
| choisir entre plusieurs bonnes ou mauvaises reponses | DPO / ORPO / KTO |
| optimiser une tache objectivement notee | GRPO / RFT |
| injecter beaucoup de savoir brut | continued pretraining |
| entrainer un gros modele serieusement | cloud / managed |

## 3. Ce qui est realiste ici

Machine actuelle:

- GPU RTX 4090
- environ 24 Go de VRAM

Donc:

- 1B a 4B: facile
- 7B dense en QLoRA 4-bit: oui, c est la bonne cible
- gros MoE / agentic coders recents: plutot pour inference, pas comme premier student local ici
- full fine-tuning dense: non, rester sur LoRA / QLoRA

## 4. Workflow recommande

1. definir un petit eval set
2. distiller avec un gros teacher
3. fusionner source + distillation
4. fine-tuner un petit student local
5. evaluer avant/apres

## 5. Commandes utiles

Check environnement:

```bash
./scripts/bootstrap_finetune_env.sh
source venv_tuning/bin/activate
python test_environment.py
```

Fine-tuning local simple:

```bash
python finetune/run_local.py stm32 --device auto --max-samples 128 --epochs 1
```

Build `llmfit` pour activer le preflight hardware dans le pipeline:

```bash
cd /ai/saisail/llmfit
cargo +stable build --release -p llmfit
```

Preset adapte a cette machine :

```bash
./scripts/finetune_host_gpu.sh stm32
```

Preset plus agressif pour `stm32` sur RTX 4090 :

```bash
./scripts/finetune_stm32_4090.sh
```

Preset plus agressif pour `platformio` sur RTX 4090 :

```bash
./scripts/finetune_platformio_4090.sh
```

Preset solo `Qwen3.5-9B-Base` sur RTX 4090 :

```bash
./scripts/finetune_qwen35_base_4090.sh
```

Profil multi-run RTX 4090 :

```bash
./scripts/triple_train_4090.sh
./scripts/triple_train_4090_safe_max.sh
MODE=triple-mixed-1024 ./scripts/triple_train_4090.sh
MODE=triple-staggered-8b1024-4b768 ./scripts/triple_train_4090.sh
MODE=dual-8b-512 ./scripts/triple_train_4090.sh
```

Distillation seule:

```bash
python finetune/distill_dataset.py stm32 \
  --api-url http://127.0.0.1:8100 \
  --teacher-provider ollama \
  --teacher-model qwen2.5:14b \
  --max-source-samples 32 \
  --samples-per-source 2
```

Pipeline complet teacher -> student:

```bash
./scripts/distill_and_train.sh stm32 \
  --api-url http://127.0.0.1:8100 \
  --teacher-provider ollama \
  --teacher-model qwen2.5:14b \
  --max-source-samples 32 \
  --samples-per-source 2 \
  --device gpu \
  --epochs 1
```

## 6. Reglage de depart recommande

Teacher:

- provider `ollama`
- teacher recommande local : `qwen2.5:14b`
- pour de la vraie distillation GPU ici, utiliser le core hote de tuning sur `127.0.0.1:18100`, pas l `ollama` Docker CPU

Student:

- recommande pour ce repo: `Qwen/Qwen2.5-Coder-7B-Instruct`
- alternative generaliste recente et plus legere: `Qwen/Qwen3-4B-Instruct-2507`
- alternative plus recente pour fine-tuning solo: `Qwen/Qwen3.5-9B-Base`
- ne pas prendre `Qwen3-Coder-Next` comme premier student local: c est un gros modele hybride/MoE surtout pense pour serving agentic
- ne pas prendre `Qwen/Qwen3.5-35B-A3B-GPTQ-Int4` comme student local: teacher / inference only dans ce pipeline

Charge validee sur cette machine:

- `1 x Qwen/Qwen3-8B + 2 x Qwen/Qwen3-4B-Instruct-2507` en `seq-len=512`: valide
- `1 x Qwen/Qwen3-8B + 2 x Qwen/Qwen3-4B-Instruct-2507` en `seq-len=768`: valide
- `1 x Qwen/Qwen3-8B + 2 x Qwen/Qwen3-4B-Instruct-2507` en `seq-len=1024`: valide, mais avec peu de marge VRAM
- `1 x Qwen/Qwen3-8B` en `seq-len=1024` + `2 x Qwen/Qwen3-4B-Instruct-2507` en `seq-len=768`: valide, avec une marge plus confortable
- `2 x Qwen/Qwen3-8B` en `seq-len=512`: non stable, un des deux run finit en `CUDA OOM`
- preset `safe-max` courant: `./scripts/triple_train_4090_safe_max.sh` sur `seq-len=768`
- `run_local.py` peut maintenant ecrire un `llmfit_plan.json` par run pour garder une trace du sizing inference utilise comme garde-fou avant training
- `run_local.py` ecrit aussi un `run.json` quand `--output-dir` est force, avec un noeud racine `llmfit`
- `batch_local.py` remonte ce `llmfit` enfant dans le manifest batch sous `domains.<domain>.train.llmfit`
- `batch_scenarios.py` expose un `llmfit` par job dans `matrix.json` des la phase `--prepare-only`
- si `llmfit` n est pas present, le pipeline continue sans bloquer et logue un warning
- `batch_local.py` peut maintenant monter a `2` students, mais seulement en fin de batch quand la file teacher est vide
- avec un teacher `ollama` lourd, le scheduler garde `1` seul student pendant les distills puis decharge le modele teacher pour recuperer la VRAM avant d ouvrir le deuxieme slot
- `OLLAMA_API_URL` permet de cibler un endpoint Ollama different pour ce dechargement automatique

Hyperparametres de depart:

- `max-source-samples=32`
- `samples-per-source=2`
- `epochs=1`
- `seq-len=1024`

Puis monter doucement:

- `max-source-samples=64`
- `epochs=2`

Bootstrap `Qwen3.5`:

```bash
TRANSFORMERS_CHANNEL=main ./scripts/bootstrap_finetune_env.sh
```

Preset `stm32` RTX 4090 deja prepare dans le repo:

- `max-source-samples=128`
- `samples-per-source=2`
- `student-max-samples=384`
- `seq-len=1536`
- `epochs=2`

## 7. Ce qu il ne faut pas faire trop tot

- lancer DPO avant un bon SFT
- lancer du RL sans grader robuste
- viser un gros dense ou un MoE sans avoir valide le baseline 7B dense
- remplacer un eval set par une impression subjective
- empiler des methodes avant d avoir valide le baseline

## 8. Ordre de priorite

Avant de complexifier:

1. meilleur eval set
2. meilleur dataset
3. meilleure distillation
4. meilleur SFT
5. ensuite seulement preference tuning ou RL

## 9. Lecture suivante

- recap complet: `docs/FINETUNING_ETAT_DE_L_ART_2026-03-06.md`
- doc pipeline local: `finetune/README.md`
- plan 4090 / parallélisme: `docs/FINETUNING_4090_PARALLEL_PLAN.md`
