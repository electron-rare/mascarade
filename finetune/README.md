# Fine-Tuning Pipeline — Mascarade

Fine-tune des modèles LLM spécialisés pour les skills électronique/hardware/IoT et les déployer via Ollama.

Lecture recommandee:

- cheatsheet rapide: `docs/FINETUNING_CHEATSHEET_2026-03-06.md`
- recap methodes / etat de l art 2026: `docs/FINETUNING_ETAT_DE_L_ART_2026-03-06.md`

## Quick Start Local

Depuis la racine du repo:

```bash
source venv_tuning/bin/activate
python test_environment.py

# Auto: GPU si dispo, sinon fallback CPU
python finetune/run_local.py stm32 --max-samples 128 --epochs 1

# Forcer le fallback CPU
python finetune/run_local.py kicad --device cpu --model gpt2 --max-samples 64

# Wrapper shell equivalent
./scripts/finetune_local.sh embedded --device auto --max-samples 256
```

Comportement:

- `run_local.py` choisit automatiquement `train_local.py` si CUDA est utilisable
- sinon il bascule sur `train_cpu.py`
- `--dataset-path` permet d'entraîner sur un dataset dérivé sans écraser `datasets/<domain>_chat.jsonl`
- `--offline` force l'usage du cache Hugging Face local
- `--eval` est disponible uniquement sur le chemin GPU
- `--verbose` affiche plus de détails sur le launcher et le trainer
- `--quiet` réduit les logs et masque les progress bars quand c est supporté
- `--tokenize-workers 0` laisse le trainer choisir automatiquement des workers CPU pour la tokenization

## Distillation Teacher -> Student

Pour utiliser un gros modèle comme professeur et fine-tuner un petit modèle local:

```bash
# Core/API Mascarade doit être démarré avec au moins un provider configuré
./scripts/distill_and_train.sh stm32 \
  --api-url http://127.0.0.1:8100 \
  --teacher-provider mistral \
  --max-source-samples 32 \
  --samples-per-source 2 \
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

Scripts concernés:

- `finetune/distill_dataset.py`: génère le dataset distillé
- `finetune/distill_and_train.py`: enchaîne distillation, merge et training
- `scripts/distill_and_train.sh`: wrapper shell

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
