# Fine-Tuning Pipeline — Mascarade

Fine-tune des modèles LLM spécialisés pour les skills électronique/hardware/IoT et les déployer via Ollama.

Lecture recommandee:

- cheatsheet rapide: `docs/FINETUNING_CHEATSHEET_2026-03-06.md`
- recap methodes / etat de l art 2026: `docs/FINETUNING_ETAT_DE_L_ART_2026-03-06.md`
- plan 4090 / scheduling parallele: `docs/FINETUNING_4090_PARALLEL_PLAN.md`

## Quick Start Local

Depuis la racine du repo:

```bash
./scripts/bootstrap_finetune_env.sh
source venv_tuning/bin/activate
python test_environment.py

# Auto: GPU si dispo, sinon fallback CPU
python finetune/run_local.py stm32 --max-samples 128 --epochs 1

# Forcer le fallback CPU
python finetune/run_local.py kicad --device cpu --model TinyLlama/TinyLlama-1.1B-Chat-v1.0 --max-samples 64

# Wrapper shell equivalent
./scripts/finetune_local.sh embedded --device auto --max-samples 256

# Run jetable isole dans finetune/runs/smoke_<domain>_<timestamp>/
./scripts/finetune_local.sh stm32 --device gpu --max-samples 8 --epochs 1 --smoke
```

Preset recommande pour cette machine (RTX 4090 24 Go VRAM) :

```bash
./scripts/finetune_host_gpu.sh stm32
```

Preflight `llmfit` recommande pour fiabiliser le sizing avant training :

```bash
cd /ai/saisail/llmfit
cargo +stable build --release -p llmfit

cd /ai/saisail/mascarade
python finetune/run_local.py stm32 --device gpu --max-samples 8 --epochs 1
```

Preset plus agressif pour `stm32` sur RTX 4090 :

```bash
./scripts/finetune_stm32_4090.sh
```

Preset plus agressif pour `platformio` sur RTX 4090 :

```bash
./scripts/finetune_platformio_4090.sh
```

Preset solo pour `Qwen3.5-9B-Base` sur RTX 4090 :

```bash
./scripts/finetune_qwen35_base_4090.sh
./scripts/finetune_qwen35_base_4090.sh stm32
```

Profil de charge multi-run sur RTX 4090 :

```bash
# 1 x Qwen3-8B + 2 x Qwen3-4B-Instruct-2507
./scripts/triple_train_4090.sh

# Meme profil, fige sur le plus haut niveau valide actuellement
./scripts/triple_train_4090_safe_max.sh

# Variante de stress plus haute, validee mais avec faible marge VRAM
MODE=triple-mixed-1024 ./scripts/triple_train_4090.sh

# Variante mixte: 8B pousse a 1024, 4B gardes a 768
MODE=triple-staggered-8b1024-4b768 ./scripts/triple_train_4090.sh

# 2 x Qwen3-8B
MODE=dual-8b-512 ./scripts/triple_train_4090.sh
```

Defaut retenu dans ce preset :

- teacher local : `ollama/qwen2.5:14b`
- student local : `Qwen/Qwen2.5-Coder-1.5B-Instruct`

Alternative generaliste plus recente :

```bash
STUDENT_MODEL=Qwen/Qwen3-4B-Instruct-2507 ./scripts/finetune_host_gpu.sh stm32
```

Alternative de fine-tuning plus recente, orientee student solo :

```bash
STUDENT_MODEL=Qwen/Qwen3.5-9B-Base ./scripts/finetune_host_gpu.sh stm32
```

Sur les presets `*_4090.sh`, le preflight GPU fait aussi un nettoyage best-effort
avant de charger les modeles:

- arret du `core` de tuning precedent s il tourne encore
- unload des modeles `ollama`
- unload des modeles `ComfyUI` via `POST /free`
- affichage d un resume VRAM avant / apres

Variables utiles:

- `TOKENIZE_WORKERS=20` par defaut sur les presets 4090
- `DISTILL_CONCURRENCY=1` par defaut
- `UNLOAD_OLLAMA_BEFORE_RUN=1` sur les presets 4090
- `UNLOAD_COMFYUI_BEFORE_RUN=1` sur les presets 4090
- `COMFYUI_API_URL=http://127.0.0.1:8188` par defaut

Exemple sans dechargement ComfyUI:

```bash
UNLOAD_COMFYUI_BEFORE_RUN=0 ./scripts/finetune_platformio_4090.sh
```

Comportement:

- `run_local.py` choisit automatiquement `train_local.py` si CUDA est utilisable
- sinon il bascule sur `train_cpu.py`
- si `datasets/<domain>_chat.jsonl` manque, le launcher genere automatiquement le seed dataset local s il existe
- `--dataset-path` permet d'entraîner sur un dataset dérivé sans écraser `datasets/<domain>_chat.jsonl`
- `--offline` force l'usage du cache Hugging Face local; en fallback CPU, le launcher attend `TinyLlama/TinyLlama-1.1B-Chat-v1.0` en cache et peut reutiliser le modele GPU par defaut s'il est deja present localement
- `--eval` est disponible uniquement sur le chemin GPU
- `--verbose` affiche plus de détails sur le launcher et le trainer
- `--quiet` réduit les logs et masque les progress bars quand c est supporté
- `--tokenize-workers 0` laisse le trainer choisir automatiquement des workers CPU pour la tokenization
- `--distill-concurrency` parallelise seulement les appels teacher; ce n est pas du multi-GPU
- sur une seule RTX 4090, garder par defaut un seul run student GPU a la fois; n ouvrir le parallelisme que sur un profil deja valide comme `scripts/triple_train_4090.sh`
- `--smoke` isole les outputs temporaires sous `finetune/runs/smoke_<domain>_<timestamp>/`
- `--run-label <label>` fait la meme chose avec un prefixe explicite, sans polluer `finetune/models_local/` ou `finetune/models_cpu/`
- le pipeline refuse explicitement certains modeles `teacher-only` comme students, notamment `Qwen/Qwen3.5-35B-A3B-GPTQ-Int4` et `Qwen/Qwen3-Next-80B-A3B-Instruct-FP8`
- les teachers Mistral / DeepSeek ajoutes a la matrice de scenarios sont eux aussi reserves au chemin teacher-only ou distillation dediee
- quand `llmfit` est disponible, `run_local.py` lance un preflight `llmfit plan <model> --context <seq_len> --json` avant le training
- ce preflight ecrit un `llmfit_plan.json` dans l `output_dir` du run, ou dans le run-dir isole si `--smoke` / `--run-label` est utilise
- le preflight `llmfit` reste un garde-fou d inference: il bloque un training GPU si meme le chemin GPU inference est juge impossible, mais il ne remplace pas les mesures VRAM reelles de QLoRA
- si `llmfit` n est pas compile, le pipeline garde le comportement precedent et logue seulement un warning
- le trainer GPU utilise maintenant par defaut un chemin plus agressif: tokenization dynamique, packing train, `NF4 + bf16` si supporte, `flash_attention_2` si disponible sinon `sdpa`
- `batch_local.py` sait maintenant ouvrir jusqu a `2` slots student, mais seulement quand le budget GPU le permet vraiment sur la machine
- avec un teacher `ollama` lourd, le scheduler garde automatiquement `1` seul student actif tant que des distills sont encore en cours
- quand la file de distillation est vide, le scheduler decharge le modele teacher via l API Ollama (`keep_alive=0`) pour recuperer la VRAM et ouvrir le deuxieme slot student
- `OLLAMA_API_URL` permet de pointer ce dechargement automatique vers un endpoint Ollama non standard
- ces runs isoles ecrivent aussi un `run.json` avec config, paths, commande trainee et statut final
- `run_local.py` ecrit aussi un `run.json` quand un `--output-dir` explicite est fourni, meme sans `--smoke` ni `--run-label`
- le noeud racine `llmfit` de ce `run.json` expose directement le statut `validated`, `warning`, `unavailable`, `not_applicable`, `disabled` ou `rejected`
- un refus `llmfit` GPU est donc trace dans le manifest meme si le training ne demarre jamais
- les commandes stockees dans `run.json` sont redactees pour ne pas exposer de secret comme `--api-key`

Variables `llmfit` utiles:

- `LLMFIT_BIN=/chemin/vers/llmfit` pour forcer un binaire
- `LLMFIT_ROOT=/ai/saisail/llmfit` pour resoudre un binaire build local
- `LLMFIT_MEMORY=24G` pour forcer la VRAM si l autodetection est mauvaise
- `LLMFIT_PREFLIGHT=0` pour desactiver le preflight
- `LLMFIT_MIN_FIT=good` pour relever le seuil d alerte
- `LLMFIT_ALLOW_CARGO_RUN=1` pour autoriser un fallback `cargo run`, utile ponctuellement mais moins propre sur des runs paralleles

Validation pratique sur cette machine:

- `Qwen/Qwen3-8B + 2 x Qwen/Qwen3-4B-Instruct-2507` en `seq_len=512` passe sur la RTX 4090
- `Qwen/Qwen3-8B + 2 x Qwen/Qwen3-4B-Instruct-2507` en `seq_len=768` passe aussi sur la RTX 4090
- pic VRAM echantillonne observe en `768`: environ `20.8 Go / 24 Go`
- `Qwen/Qwen3-8B + 2 x Qwen/Qwen3-4B-Instruct-2507` en `seq_len=1024` passe aussi, mais avec une marge faible
- pic VRAM echantillonne observe en `1024`: environ `23.3 Go / 24 Go`
- `Qwen/Qwen3-8B` en `seq_len=1024` avec `2 x Qwen/Qwen3-4B-Instruct-2507` en `seq_len=768` passe aussi
- pic VRAM echantillonne observe sur ce profil mixte: environ `18.6 Go / 24 Go`
- `2 x Qwen/Qwen3-8B` en `seq_len=512` ne passe pas proprement: un run finit, l autre part en `CUDA OOM`
- `scripts/triple_train_4090.sh` coupe `ComfyUI` avant le test et le relance a la fin par defaut
- `scripts/triple_train_4090_safe_max.sh` reste volontairement sur `seq_len=768`; `1024` est valide mais trop proche du plafond VRAM pour etre le preset par defaut

## Model Selector experimental

Un helper local experimental permet de chercher et classer des students
compatibles avec la machine sans modifier automatiquement le pipeline:

```bash
python finetune/model_selector.py --help
python finetune/model_selector.py --auto
python finetune/model_selector.py --auto --download --validate
```

Comportement:

- l outil interroge le Hub Hugging Face, met les resultats en cache local et
  classe les modeles selon VRAM, signaux de qualite et popularite
- il ecrit un `finetune/selected_model.json` local quand un modele est choisi
- `finetune/.model_selector_cache.json` et `finetune/selected_model.json`
  sont ignores par Git
- il n est pas encore branche automatiquement a `run_local.py`,
  `batch_local.py` ou `train_all.sh`

## Distillation Teacher -> Student

Pour utiliser un gros modèle comme professeur et fine-tuner un petit modèle local:

```bash
# Core/API Mascarade doit être démarré avec au moins un provider configuré
# Si MASCARADE_API_KEY est present dans .env, le wrapper la recharge automatiquement.
./scripts/distill_and_train.sh stm32 \
  --api-url http://127.0.0.1:8100 \
  --teacher-provider ollama \
  --teacher-model qwen2.5:14b \
  --max-source-samples 32 \
  --samples-per-source 2 \
  --smoke \
  --device gpu \
  --epochs 1
```

Ce workflow:

- lit `finetune/datasets/<domain>_chat.jsonl`
- demande au teacher de produire des variantes/distillations au format ShareGPT
- écrit un dataset distillé dans `finetune/datasets/distilled/`
- fusionne source + distillation avec déduplication
- lance ensuite `run_local.py` sur le dataset fusionné
- `--verbose` propage les logs détaillés sur la distillation, le merge et le training
- `--quiet` garde seulement les messages importants
- `--concurrency 0` sur `distill_dataset.py` choisit automatiquement une petite parallélisation des appels teacher
- sur la stack locale Docker validee ici, `ollama` tourne sans GPU; les gros teachers locaux peuvent donc necessiter un `--timeout` plus grand ou un modele plus petit
- avec `--smoke` ou `--run-label`, dataset distille, merge et output training restent confines dans `finetune/runs/<label>_<domain>_<timestamp>/`
- ce run-dir contient aussi un `run.json` avec les etapes `distill`, `merge`, `train`, leurs commandes redactees et leurs statuts
- `steps.train.llmfit` recopie le noeud `llmfit` du `run.json` enfant produit par `run_local.py`
- `--teacher-only` force un run distillation-only et marque `train=skipped` dans le manifest

Scripts concernés:

- `finetune/distill_dataset.py`: génère le dataset distillé
- `finetune/distill_and_train.py`: enchaîne distillation, merge et training
- `scripts/distill_and_train.sh`: wrapper shell

## Batch multi-domaine

Pour enchaîner plusieurs domaines avec manifest et logs dédiés:

```bash
./scripts/parallel_domains_gpu_queue.sh freecad platformio \
  --max-source-samples 8 \
  --samples-per-source 1 \
  --student-max-samples 32 \
  --epochs 1 \
  --offline
```

Comportement du batch local valide sur cette machine:

- bootstrappe le seed dataset si `datasets/<domain>_chat.jsonl` manque mais qu un `build_<domain>_dataset.py` existe
- utilise par défaut `http://127.0.0.1:8100` avec `ollama` / `qwen2.5:14b`
- recharge `MASCARADE_API_KEY` depuis `.env` si elle n est pas deja exportee
- écrit un manifest et des logs par run dans `finetune/runs/`
- overlap distill/train en mode `auto`: un domaine peut partir en training des que sa distillation est mergee
- ce mode se desactive automatiquement pour `teacher-provider=local-hf`
- avec `--max-parallel-gpu-trains 2`, le scheduler reste volontairement a `1` training tant que le teacher `ollama` distille encore sur une RTX 4090
- une fois la file teacher vide, le scheduler decharge le modele `ollama` puis peut lancer `2` trainings students en parallele si la VRAM libre le permet
- `gpu_job_vram_mb` peut maintenant etre laisse a `0` pour utiliser une estimation auto plus prudente
- `--teacher-only` ou `--skip-train` permettent un batch distill-only multi-domaine sans lancer `run_local.py`
- le manifest batch expose un noeud racine `llmfit` pour le student courant
- chaque domaine recopie ensuite le `llmfit` du child `run.json` sous `domains.<domain>.train.llmfit`
- un training GPU refuse par `llmfit` est marque `train.status=blocked` plutot qu un simple `failed`

## Matrice de scénarios teacher/student

Pour preparer ou executer plusieurs scénarios Qwen / Mistral / DeepSeek avec des passes
fixes `1 -> 2 -> 3`:

```bash
# Prepare seulement les manifests et les commandes
./scripts/teacher_student_scenarios.sh \
  --scenario-group all \
  --pass all \
  --prepare-only

# Executer seulement les scénarios DeepSeek, passe 1
./scripts/teacher_student_scenarios.sh \
  --scenario-group deepseek \
  --pass 1 \
  --offline
```

Comportement:

- un manifest parent `matrix.json` est ecrit sous `finetune/runs/<label>_<timestamp>/`
- chaque job de scenario appelle `finetune/batch_local.py` avec son propre `run-label`
- les scenarios sont groupes par famille `qwen`, `mistral`, `deepseek`
- les scenarios CPU et GPU reutilisent le meme batch multi-domaine; les scenarios teacher-only passent par `--teacher-only`
- les scenarios DeepSeek `coder` restent limites aux domaines code/embedded dans cette premiere version
- chaque job de `matrix.json` contient aussi un noeud `llmfit` calcule des la phase `--prepare-only`
- `matrix.json` maintient `summary.llmfit` pour compter rapidement les jobs `validated`, `warning`, `rejected` ou `unavailable`
- apres execution, le job recopie aussi le `llmfit` du child batch manifest et le resume des statuts de train par domaine
- un job GPU avec `llmfit.status=rejected` est marque `blocked` et n est pas lance

## Nettoyage des artifacts

Pour purger proprement les sorties de smoke test et les logs:

```bash
./scripts/cleanup_finetune_artifacts.sh --smoke --logs --distilled --dry-run
./scripts/cleanup_finetune_artifacts.sh --smoke --logs --distilled --yes
./scripts/cleanup_finetune_artifacts.sh --label smoke2 --yes
```

Pour supprimer un run temporaire nomme, utiliser `--label`. Pour un legacy output explicite hors run-dir, ajouter `--path`:

```bash
./scripts/cleanup_finetune_artifacts.sh \
  --smoke \
  --logs \
  --distilled \
  --path finetune/models_cpu/embedded \
  --yes
```

## Bootstrap de l'environnement

Le pipeline local attend un environnement dedie `venv_tuning`. Le bootstrap
installe `torch` depuis l'index PyTorch approprie puis les dependances du
pipeline:

```bash
# RTX 4090 / drivers CUDA recents
TORCH_CHANNEL=cu124 ./scripts/bootstrap_finetune_env.sh

# Anciennes cartes ou stack CUDA 11.8
TORCH_CHANNEL=cu118 ./scripts/bootstrap_finetune_env.sh

# CPU only
TORCH_CHANNEL=cpu ./scripts/bootstrap_finetune_env.sh
```

Pour les modeles `Qwen3.5`, utiliser la lane `transformers main`:

```bash
TRANSFORMERS_CHANNEL=main ./scripts/bootstrap_finetune_env.sh
```

## Architecture

```
Machine locale                    Google Colab (T4 gratuit)
    │                                    │
    │ 1. python datasets/build_*.py      │
    │    → datasets/*_chat.jsonl         │
    │                                    │
    │ 2. huggingface-cli upload           │
    │         ──────────────────────>    │
    │                                    │ 3. Ouvrir notebooks/finetune_*.ipynb
    │                                    │    Fine-tune Qwen2.5-Coder-7B (QLoRA)
    │                                    │    Export GGUF → HF Hub
    │         <──────────────────────    │
    │                                    │
    │ 4. ./deploy_model.sh <domain>      │
    │    → ollama create mascarade-*     │
    │                                    │
    │ 5. Modèle dispo dans Mascarade     │
    │    via OllamaProvider              │
```

## Domaines

| Domaine | Skills couverts | Dataset | Notebook |
|---------|----------------|---------|----------|
| **stm32** | stm32, stm32-asm, microcontroller-firmware | `stm32_chat.jsonl` | `finetune_stm32.ipynb` |
| **spice** | spice, spice-advanced-models, convergence-debug | `spice_chat.jsonl` | `finetune_spice.ipynb` |
| **iot** | mqtt-iot, esp-idf, rtos, domotique | `iot_chat.jsonl` | `finetune_iot.ipynb` |
| **power** | power-electronics, motor-control | `power_chat.jsonl` | `finetune_power.ipynb` |
| **dsp** | dsp-signal-processing | `dsp_chat.jsonl` | `finetune_dsp.ipynb` |
| **emc** | emc-emi, esd-protection, radio-rf | `emc_chat.jsonl` | `finetune_emc.ipynb` |
| **kicad** | pcb-routing-kicad, kicad, kicad-ia, pcb-design, IPC | `kicad_chat.jsonl` | `finetune_kicad.ipynb` |

## Quick Start Colab / Hub

### 1. Préparer le dataset

```bash
cd finetune

# Générer les seeds (20-30 exemples de haute qualité par domaine)
python datasets/build_stm32_dataset.py
python datasets/build_spice_dataset.py
python datasets/build_iot_dataset.py
python datasets/build_power_dataset.py
python datasets/build_dsp_dataset.py
python datasets/build_emc_dataset.py
python datasets/build_kicad_dataset.py

# Inclure les datasets HuggingFace (tous les domaines supportés)
python datasets/build_stm32_dataset.py --with-hf --max-samples 2000
python datasets/build_spice_dataset.py --with-hf --max-samples 1000
python datasets/build_iot_dataset.py --with-hf --max-samples 2000
python datasets/build_power_dataset.py --with-hf --max-samples 2000
python datasets/build_dsp_dataset.py --with-hf --max-samples 2000
python datasets/build_emc_dataset.py --with-hf --max-samples 2000
python datasets/build_kicad_dataset.py --with-hf --max-samples 2000
```

### Sources HuggingFace par domaine

| Domaine | Datasets HF | Exemples estimés |
|---------|------------|-----------------|
| STM32 | `MuratKomurcu/stm32-hal-dataset` | ~2000 |
| SPICE | `STEM-AI-mtl/Electrical-engineering` (filtré) | ~500 |
| IoT | `gouthamsk/esp_idf_code` (13.7k), `acon96/Home-Assistant-Requests` (35.8k), `gavmac00/arduino-docs` (14.3k), `bshada/arduino.stackexchange.com` | ~5000+ |
| Power | `ksabeh/electronics-dataset` (128k filtré), `bshada/electronics.stackexchange.com` (filtré), `nick007x/eevblog-posts` (200k filtré) | ~2000+ |
| DSP | `bshada/electronics.stackexchange.com` (filtré), `common-pile/stackexchange` (DSP), `STEM-AI-mtl/Electrical-engineering` (filtré) | ~1000+ |
| EMC/RF | `bshada/electronics.stackexchange.com` (filtré), `STEM-AI-mtl/Electrical-engineering` (filtré), `nick007x/eevblog-posts` (filtré) | ~1000+ |
| KiCad/PCB | `STEM-AI-mtl/Electrical-engineering` (25% KiCad), `bshada/electronics.stackexchange.com` (filtré), `ksabeh/electronics-dataset` (filtré) | ~1500+ |

### 2. Enrichir le dataset (optionnel, au-delà de --with-hf)

Les datasets HF + seeds couvrent la majorité des cas. Pour aller plus loin :

- **Synthétique** : utiliser Claude/GPT-4 pour générer plus d'exemples dans le même format JSONL
- **Extraction** : extraire Q&A depuis vos projets, Stack Overflow, datasheets
- **Documentation** : convertir les appnotes TI/ST/Infineon en paires Q&A

Format attendu (ShareGPT) :
```json
{"conversations": [
  {"from": "system", "value": "You are an expert..."},
  {"from": "human", "value": "Question technique"},
  {"from": "gpt", "value": "Réponse détaillée avec code"}
]}
```

### 3. Upload sur HuggingFace

```bash
pip install huggingface_hub[cli]
huggingface-cli login

# Upload le dataset
huggingface-cli upload YOUR_USERNAME/mascarade-stm32-dataset datasets/stm32_chat.jsonl
```

### 4. Fine-tuner sur Google Colab

1. Ouvrir le notebook correspondant dans Google Colab
2. Sélectionner Runtime → Change runtime type → **T4 GPU**
3. Remplacer `YOUR_USERNAME` par votre username HuggingFace
4. Exécuter toutes les cellules (~30-60 min)
5. Le GGUF est pushé automatiquement sur votre HF Hub

### 5. Déployer localement

```bash
./deploy_model.sh stm32 YOUR_USERNAME/mascarade-stm32-q4km
```

Le modèle est maintenant disponible dans Ollama et accessible via le provider Mascarade.

## Détails techniques

### Modèle de base
- **Qwen2.5-Coder-7B-Instruct** via Unsloth (4-bit QLoRA)
- LoRA rank: 16, alpha: 16
- Targets: q/k/v/o/gate/up/down projections

### Hyperparamètres d'entraînement
- Epochs: 3
- Learning rate: 2e-4
- Batch size: 2 (gradient accumulation: 4)
- Max sequence length: 2048
- Optimizer: AdamW 8-bit

### Export
- Quantization: Q4_K_M (bon compromis qualité/taille)
- Taille finale: ~4.3 GB par modèle
- Format: GGUF (compatible Ollama, llama.cpp)

## Structure

```
finetune/
├── README.md                  # Ce fichier
├── deploy_model.sh            # Script de déploiement
├── datasets/
│   ├── build_stm32_dataset.py # Génère stm32_chat.jsonl
│   ├── build_spice_dataset.py # Génère spice_chat.jsonl
│   ├── build_iot_dataset.py   # Génère iot_chat.jsonl
│   ├── build_power_dataset.py # Génère power_chat.jsonl
│   ├── build_dsp_dataset.py   # Génère dsp_chat.jsonl
│   └── build_emc_dataset.py   # Génère emc_chat.jsonl
├── notebooks/
│   ├── finetune_stm32.ipynb   # Colab notebook STM32
│   ├── finetune_spice.ipynb   # Colab notebook SPICE
│   ├── finetune_iot.ipynb     # Colab notebook IoT
│   ├── finetune_power.ipynb   # Colab notebook Power
│   ├── finetune_dsp.ipynb     # Colab notebook DSP
│   └── finetune_emc.ipynb     # Colab notebook EMC/RF
└── modelfiles/
    ├── Modelfile.stm32        # Ollama Modelfile STM32
    ├── Modelfile.spice        # Ollama Modelfile SPICE
    ├── Modelfile.iot          # Ollama Modelfile IoT
    ├── Modelfile.power        # Ollama Modelfile Power
    ├── Modelfile.dsp          # Ollama Modelfile DSP
    └── Modelfile.emc          # Ollama Modelfile EMC/RF
```
