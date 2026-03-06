# Fine-Tuning via Google Colab + Ollama

Pipeline complete pour fine-tuner des LLM specialises electronique/hardware et les deployer localement via Ollama.

## Architecture

```
Machine locale (192.168.0.119)              Google Colab (T4 16GB gratuit)
    |                                              |
    | 1. Generer les datasets                      |
    |    python datasets/build_*.py --with-hf      |
    |                                              |
    | 2. Upload datasets sur HuggingFace           |
    |    ./upload_datasets_hf.sh                   |
    |         -------------------------------->    |
    |                                              | 3. Ouvrir notebook dans Colab
    |                                              |    Fine-tune Qwen2.5-Coder-7B (QLoRA)
    |                                              |    ~30-60 min par domaine
    |                                              |    Export GGUF Q4_K_M -> HF Hub
    |         <--------------------------------    |
    |                                              |
    | 4. Deployer localement                       |
    |    ./deploy_model.sh <domain> <hf_repo>      |
    |    -> ollama create mascarade-<domain>        |
    |                                              |
    | 5. Utiliser dans Mascarade                   |
    |    provider=ollama, model=mascarade-<domain>  |
```

## Etape 1 — Preparer les datasets

Les datasets sont deja generes dans `datasets/`. Pour les regenerer ou enrichir :

```bash
cd finetune

# Seeds uniquement (~30 exemples par domaine)
python datasets/build_stm32_dataset.py

# Seeds + donnees HuggingFace (recommande)
python datasets/build_stm32_dataset.py --with-hf --max-samples 2000
python datasets/build_kicad_dataset.py --with-hf --max-samples 2000
python datasets/build_iot_dataset.py --with-hf --max-samples 2000
# etc. pour chaque domaine
```

### Datasets actuels

| Domaine    | Exemples | Taille | Contenu |
|-----------|----------|--------|---------|
| embedded  | 8 344    | 17 MB  | Bare-metal ARM, Cortex-M, linker, startup |
| iot       | 4 005    | 12 MB  | ESP-IDF, MQTT, Home Assistant, Arduino |
| spice     | 4 644    | 9.2 MB | Netlists, convergence, modeles avances |
| dsp       | 3 160    | 7.6 MB | Filtres, FFT, traitement signal |
| emc       | 3 360    | 6.1 MB | EMI/EMC, blindage, filtrage, RF |
| power     | 3 267    | 6 MB   | Electronique de puissance, moteurs |
| kicad     | 2 645    | 5.7 MB | PCB, DRC, impedance, KiCad scripts |
| stm32     | 2 012    | 3.1 MB | HAL, LL, DMA, FreeRTOS, ASM |

Format : ShareGPT JSONL (compatible Unsloth).

## Etape 2 — Upload sur HuggingFace

```bash
# Se connecter (une seule fois)
pip install huggingface_hub[cli]
huggingface-cli login

# Upload tous les datasets
./upload_datasets_hf.sh

# Ou un seul :
huggingface-cli upload clemsail/mascarade-stm32-dataset \
    datasets/stm32_chat.jsonl stm32_chat.jsonl --repo-type dataset
```

## Etape 3 — Fine-tuner sur Colab

### Ouvrir le notebook

Les notebooks sont sur GitHub. Ouvrir directement dans Colab :

| Domaine   | Lien Colab |
|-----------|------------|
| STM32     | https://colab.research.google.com/github/electron-rare/mascarade/blob/main/finetune/notebooks/finetune_stm32.ipynb |
| KiCad     | https://colab.research.google.com/github/electron-rare/mascarade/blob/main/finetune/notebooks/finetune_kicad.ipynb |
| SPICE     | https://colab.research.google.com/github/electron-rare/mascarade/blob/main/finetune/notebooks/finetune_spice.ipynb |
| IoT       | https://colab.research.google.com/github/electron-rare/mascarade/blob/main/finetune/notebooks/finetune_iot.ipynb |
| Power     | https://colab.research.google.com/github/electron-rare/mascarade/blob/main/finetune/notebooks/finetune_power.ipynb |
| DSP       | https://colab.research.google.com/github/electron-rare/mascarade/blob/main/finetune/notebooks/finetune_dsp.ipynb |
| EMC       | https://colab.research.google.com/github/electron-rare/mascarade/blob/main/finetune/notebooks/finetune_emc.ipynb |
| Embedded  | https://colab.research.google.com/github/electron-rare/mascarade/blob/main/finetune/notebooks/finetune_embedded.ipynb |

### Procedure

1. Ouvrir le lien Colab
2. Menu **Runtime > Change runtime type > T4 GPU**
3. Modifier `HF_USERNAME` dans les cellules 3 et 6
4. **Run All** (Ctrl+F9)
5. Attendre ~30-60 min
6. Le GGUF Q4_K_M est pousse automatiquement sur votre HF Hub

### Ce que fait le notebook

```
Cell 1: pip install unsloth
Cell 2: Charger Qwen2.5-Coder-7B-Instruct en 4-bit
Cell 3: Configurer QLoRA (r=16, alpha=16)
Cell 4: Charger dataset depuis HF Hub, formater en chat template
Cell 5: Entrainer (SFTTrainer, 3 epochs, lr=2e-4)
Cell 6: Tester avec 5 prompts du domaine
Cell 7: Exporter en GGUF Q4_K_M et push sur HF Hub
```

### Hyperparametres

| Parametre | Valeur |
|-----------|--------|
| Modele de base | Qwen2.5-Coder-7B-Instruct |
| Methode | QLoRA (4-bit NF4) |
| LoRA rank | 16 |
| LoRA alpha | 16 |
| Targets | q/k/v/o/gate/up/down projections |
| Epochs | 3 |
| Learning rate | 2e-4 |
| Batch size | 2 |
| Gradient accumulation | 4 |
| Sequence length | 2048 |
| Optimizer | AdamW 8-bit |

## Etape 4 — Deployer localement

```bash
cd finetune

# Deploiement automatique (telecharge GGUF + cree modele Ollama)
./deploy_model.sh stm32 clemsail/mascarade-stm32-q4km

# Ou manuellement :
huggingface-cli download clemsail/mascarade-stm32-q4km \
    --local-dir ./models/stm32/ --include "*.gguf"

ollama create mascarade-stm32 -f modelfiles/Modelfile.stm32
```

### Modelfiles

Chaque domaine a un Modelfile avec :
- System prompt specialise
- Template Qwen2.5 (ChatML / im_start/im_end)
- Temperature basse (0.2-0.3) pour du code precis
- Context 4096 tokens, generation max 2048

### Taille des modeles

Chaque GGUF Q4_K_M fait environ **4.3 GB**.
La Quadro P2000 (5 GB VRAM) peut faire l'inference avec un seul modele charge.

## Etape 5 — Utiliser dans Mascarade

### Via Ollama directement

```bash
ollama run mascarade-stm32 "Configure SPI1 on STM32F4 in master mode"
ollama run mascarade-kicad "Set up DRC rules for JLCPCB"
ollama run mascarade-spice "SPICE netlist for a buck converter"
```

### Via l'API Mascarade

```bash
curl -X POST http://localhost:8100/send \
  -H "Content-Type: application/json" \
  -d '{
    "provider": "ollama",
    "model": "mascarade-stm32",
    "messages": [{"role": "user", "content": "Configure UART with DMA on STM32F4"}]
  }'
```

### Via un agent dedie

Creer un agent qui utilise automatiquement le bon modele :

```bash
curl -X POST http://localhost:8100/agents \
  -H "Content-Type: application/json" \
  -d '{
    "name": "stm32-expert",
    "description": "Expert STM32/ARM firmware",
    "system_prompt": "You are an expert STM32 engineer...",
    "preferred_provider": "ollama",
    "preferred_model": "mascarade-stm32",
    "temperature": 0.3
  }'
```

## Troubleshooting

### Colab "GPU not available"
- Verifier Runtime > Change runtime type > T4
- Colab gratuit a une file d'attente, reessayer plus tard
- Session limitee a ~12h

### "Model too large for GPU"
- Verifier qu'un seul modele Ollama est charge : `ollama ps`
- Decharger les autres : `ollama stop <model>`
- La P2000 ne peut charger qu'un GGUF Q4_K_M a la fois

### GGUF export fails sur Colab
- Verifier l'espace disque : le T4 a ~80 GB, le GGUF en utilise ~15 GB temporairement
- Nettoyer : `!rm -rf outputs/` avant l'export

### Ollama create fails
- Verifier que le fichier GGUF est complet (pas de download partiel)
- `md5sum` pour verifier l'integrite
- Le Modelfile doit pointer vers le bon chemin GGUF

## Structure des fichiers

```
finetune/
  COLAB_GUIDE.md              <- Ce fichier
  deploy_model.sh             <- Script de deploiement Ollama
  upload_datasets_hf.sh       <- Upload datasets vers HF Hub
  bedrock_finetune.py         <- Alternative AWS Bedrock
  datasets/
    build_stm32_dataset.py    <- Generateur dataset STM32
    build_kicad_dataset.py    <- Generateur dataset KiCad
    build_*.py                <- Generateurs par domaine
    stm32_chat.jsonl          <- Dataset STM32 (ShareGPT)
    kicad_chat.jsonl          <- Dataset KiCad (ShareGPT)
    *_chat.jsonl              <- Datasets par domaine
  notebooks/
    finetune_stm32.ipynb      <- Notebook Colab STM32
    finetune_kicad.ipynb      <- Notebook Colab KiCad
    finetune_*.ipynb          <- Notebooks par domaine
  modelfiles/
    Modelfile.stm32           <- Ollama config STM32
    Modelfile.kicad           <- Ollama config KiCad
    Modelfile.*               <- Configs par domaine
```
