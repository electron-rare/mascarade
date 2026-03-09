# TUNING PARTY → Hugging Face

Plan de fine-tuning serieux + publication HF pour les adapteurs LoRA mascarade.
Date: 9 mars 2026.

## 1. Etat actuel

### Datasets enrichis et dedupliques (finetune/datasets/) — audit 9 mars 2026

| Domaine     | Rows   | Dups | Dup%  | AvgLen | P95Len | MaxLen | Status  | Sources externes                          |
|-------------|-------:|-----:|------:|-------:|-------:|-------:|---------|-------------------------------------------|
| stm32       |  2 688 |    0 |  0.0% |    908 |  2 234 |  8 273 | passed  | +MuratKomurcu/stm32-hal-dataset           |
| freecad     |  3 991 |    0 |  0.0% |  2 232 |  4 034 |  4 034 | warning | —                                         |
| iot         |  4 614 |    0 |  0.0% |    907 |  2 595 |  8 431 | passed  | +bshada/electronics.stackexchange          |
| dsp         |  5 447 |    0 |  0.0% |  1 290 |  3 966 |  8 253 | passed  | +bshada/electronics.stackexchange          |
| kicad       |  6 919 |    0 |  0.0% |    916 |  2 636 |  6 709 | passed  | +bshada/electronics.stackexchange          |
| emc         |  7 055 |    0 |  0.0% |  1 025 |  2 904 |  8 301 | passed  | +bshada/electronics.stackexchange          |
| platformio  |  6 997 |  303 |  4.3% |    974 |  2 645 |  8 156 | warning | +bshada/arduino.stackexchange              |
| embedded    | 15 826 |    0 |  0.0% |  1 025 |  2 897 |  8 491 | passed  | +bshada/electronics.stackexchange          |
| power       | 16 894 |    0 |  0.0% |    996 |  2 758 |  8 191 | passed  | +bshada/electronics.stackexchange          |
| spice       | 72 852 |    0 |  0.0% |    781 |  1 896 |  8 480 | passed  | +Ashed00/SPICE +Si7li/ltspice +theprint   |
| components  |     30 |    0 |  0.0% |    755 |  1 609 |  3 240 | passed  | +bshada/electronics.stackexchange          |
| **Total**   |**143 313**| | | | | | | |

Voir `finetune/datasets/README.md` pour le detail des sources, licences et modeles de reference.

### Enrichissement realise le 9 mars 2026

Sources ajoutees:
- bshada/electronics.stackexchange.com (95K QA, CC-BY-SA-3.0) → 56 619 routes par tags
- bshada/arduino.stackexchange.com (10.6K QA, CC-BY-SA-3.0) → 8 217 routes
- Si7li/ltspice-spice-circuits (53K, MIT) → 46 055 pour spice
- Ashed00/SPICE-Circuits (1K, MIT) → 1 009 pour spice
- theprint/Electronics-QA (2.5K, Apache 2.0) → 2 508 pour spice
- MuratKomurcu/stm32-hal-dataset (26.7K, MIT) → 575 pour stm32
| stm32       | 2 012   | oui           |
| **Total**   | **46 726** |            |

Format: ShareGPT JSONL (system/human/gpt conversations).

### Runs precedents (non publiables)

- Run `qwen4b-slots-compare` du 8 mars: 1 epoch, 21-36 samples (seed), loss 1.2-2.0
- Verdict: smoke tests / benchmarks GPU, pas de vrais entrainements

### Run en cours — Phase A SFT (9 mars 2026)

- Label: `tuning-party-hf`
- Modele: `Qwen/Qwen3.5-9B-Base` (auto-selectionne par model_selector.py)
- Fix prealable: `transformers` 4.57.6 → 5.3.0 (vllm avait downgrade, `qwen3_5` model_type non reconnu en 4.x)
- Strategie: 3ep petits (<10K), 1ep gros (>10K), spice cap 20K
- Script: `batch_phase_a.sh` + nouveau `batch_full_pipeline.sh` (enchaine A→B→C)
- Vitesse: ~20s/step sur Qwen3.5-9B, seq_len=1024, QLoRA 4bit
- Audit dataset pre-lancement: 143K rows, 11 domaines, tous passent le quality gate

### Infra

- GPU: RTX 4090 (24 Go VRAM, ~23 Go libres)
- venv: `/ai/saisail/mascarade/venv_tuning/`
- Vitesse mesuree: ~2.4 samples/sec (Qwen3-4B, seq_len=1024, QLoRA 4bit)
- 2 slots GPU valides en parallele (speedup 1.85x, pic VRAM 17 Go)
- Student auto-selectionne: Qwen3.5-9B-Base (benchmark model_selector.py)

### Compte HF

- User: `clemsail`
- 8 datasets deja publies sous `clemsail/mascarade-*-dataset`
- 0 modeles publies

## 2. Strategie

### Phase 1 — Run pilote (1 domaine, ~45 min) — TERMINE

Objectif: valider que le fine-tuning apporte un gain reel avant de lancer 16h de GPU.

1. **Audit dataset stm32** (2 688 samples enrichis)
   - [x] Verifier doublons → 0 dups
   - [x] Verifier qualite des reponses → AvgLen=908, P95=2234, MaxLen=8273, passed
   - [x] Verifier distribution des sujets (UART, GPIO, DMA, FreeRTOS, etc.)

2. **Train stm32 serieux**
   - [x] Split 90/10 (train/eval)
   - [x] 3 epochs
   - [x] seq_len=1024
   - [x] Modele base: Qwen/Qwen3.5-9B-Base (auto-selectionne, VRAM OK)
   - [x] LoRA r=16, alpha=32, targets=q/k/v/o_proj, dropout=0.05
   - [x] Compute: bf16, SDPA, packing=true
   - [x] Sauvegarder eval loss a chaque epoch

3. **Eval qualitative**
   - [ ] 10-20 prompts STM32 varies (UART, SPI, I2C, DMA, FreeRTOS, low-power, bootloader)
   - [ ] Comparer reponses: modele base vs fine-tune
   - [ ] Scorer: exactitude technique, completude du code, compilabilite

4. **Decision go/no-go**
   - GO: train lance sur les 10 domaines (Phase A / batch_phase_a.sh)

### Phase 2 / Phase A — Train complet (10 domaines) — EN COURS

Lance le 9 mars 2026 en background via `batch_phase_a.sh`.

**Parametres:**
- Modele base: Qwen/Qwen3.5-9B-Base
- Strategie smart: 3ep petits (<10K), 1ep gros (>10K), spice cap 20K
- seq_len: 1024
- LoRA: r=16, alpha=32, dropout=0.05
- Compute: bf16, SDPA
- Eval split: 10%
- Run sequentiel (Qwen3.5-9B ne tient pas en 2 slots)

**Domaines et estimation:**

| # | Domaine     | Samples | Epochs | Temps estime (~20s/step) |
|---|-------------|---------|--------|--------------------------|
| 1 | stm32       |  2 688  |   3    | ~56 min                  |
| 2 | freecad     |  3 991  |   3    | ~1h 23                   |
| 3 | iot         |  4 614  |   3    | ~1h 36                   |
| 4 | dsp         |  5 447  |   3    | ~1h 54                   |
| 5 | kicad       |  6 919  |   3    | ~2h 24                   |
| 6 | emc         |  7 055  |   3    | ~2h 28                   |
| 7 | platformio  |  6 997  |   3    | ~2h 26                   |
| 8 | embedded    | 15 826  |   1    | ~1h 50                   |
| 9 | power       | 16 894  |   1    | ~1h 58                   |
| 10| spice       | 20 000  |   1    | ~2h 19                   |
|   | **Total**   |**90 431**|       | **~19h 14**              |

### Phase B — Rejection Sampling + Validation (~5h generation + validation)

Pipeline Student-Teacher-Validator. Nouveaux scripts:
- `finetune/validators.py` — validateurs deterministes + LLM-as-judge
- `finetune/rejection_sampling.py` — generation N candidats + scoring + paires DPO
- `finetune/train_dpo.py` — DPO/ORPO training sur paires de preference

**Validateurs deterministes par domaine:**

| Domaine | Validateur | Outil | Type |
|---------|-----------|-------|------|
| stm32 | EmbeddedCValidator | arm-none-eabi-gcc -fsyntax-only | Compilation C |
| embedded | EmbeddedCValidator | arm-none-eabi-gcc ou gcc | Compilation C |
| spice | SpiceValidator | ngspice -b | Simulation netlist |
| kicad | KicadValidator | S-expression parser + kicad-cli DRC | Syntaxe/DRC |
| platformio | PlatformIOValidator | pio run --check | Build Arduino |
| dsp | LLMJudgeValidator | ollama (qwen3.5:9b) | LLM scoring |
| power | LLMJudgeValidator | ollama | LLM scoring |
| emc | LLMJudgeValidator | ollama | LLM scoring |
| iot | LLMJudgeValidator | ollama | LLM scoring |
| freecad | LLMJudgeValidator | ollama | LLM scoring |

**Procedure par domaine:**

1. Deployer le Student v0 (SFT) dans Ollama via pipeline.py merge → gguf → deploy
2. Generer 8 candidats par prompt (temperature=0.8)
3. Valider chaque candidat avec le validateur du domaine
4. Construire paires DPO: meilleur (chosen) vs pire (rejected)
5. Objectif: ~30-50% de paires valides

**Commande:**
```bash
# Installer les validateurs
sudo apt install gcc-arm-none-eabi ngspice
pip install trl vllm

# Rejection sampling
python rejection_sampling.py stm32 \
    --student-model mascarade-stm32 \
    --n-candidates 8 \
    --max-prompts 500
```

### Phase C — DPO/ORPO Training (~2-4h par domaine)

Entraine le student a preferer les reponses validees.

**Choix DPO vs ORPO:**
- DPO: meilleure qualite, mais 2x VRAM (ref model en memoire)
- ORPO: 1x VRAM, single-phase, ideal pour petits modeles (<3B)
- Recommandation: ORPO pour Qwen3-4B, DPO pour Qwen3.5-9B

**Commande:**
```bash
python train_dpo.py stm32 \
    --model ./runs/tuning-party-hf_stm32/train_output/adapter \
    --dpo-dataset ./dpo_pairs/stm32/dpo_stm32.jsonl \
    --method dpo \
    --beta 0.1 \
    --epochs 1
```

### Phase D — Publication HF

Pour chaque domaine avec un gain valide:

1. **Preparer le repo HF**
   - Nom: `clemsail/mascarade-<domaine>-lora`
   - Type: model (adapter PEFT/LoRA)
   - Tags: `peft`, `lora`, `qwen`, `electronics`, `embedded`, `<domaine>`, `dpo`
   - License: Apache 2.0 (compatible avec CC-BY-SA des sources SE)

2. **Contenu du repo**
   - `adapter_config.json`
   - `adapter_model.safetensors`
   - `tokenizer.json` + `tokenizer_config.json`
   - `README.md` (model card) avec:
     - Modele de base
     - Parametres LoRA + methode (SFT + DPO/ORPO)
     - Dataset utilise (lien vers clemsail/mascarade-<domaine>-dataset)
     - Metriques: train loss, eval loss, DPO pairs, validation rate
     - Validateur utilise et taux de reussite
     - Exemples d utilisation (code Python avec PEFT)
     - Limitations connues
   - `training_info.json` (reproductibilite)

3. **Publier aussi les datasets manquants**
   - [ ] `clemsail/mascarade-freecad-dataset`
   - [ ] `clemsail/mascarade-platformio-dataset`
   - [ ] `clemsail/mascarade-<domaine>-dpo` (paires de preference)

4. **Upload**
   - Via `huggingface_hub` Python SDK ou `huggingface-cli upload`
   - Un repo par domaine (pas un gros repo monolithique)

## 3. Criteres de qualite pour publication

Un adapteur est publiable si:

- [ ] Train loss < 1.5 en fin de training
- [ ] Eval loss stable (pas de overfitting flagrant entre epoch 2 et 3)
- [ ] Gain qualitatif visible sur au moins 8/10 prompts de test
- [ ] Pas de regression sur les capacites generales du modele base
- [ ] README/model card complete

## 4. Checklist avant lancement

- [x] Verifier espace disque suffisant (~500 Mo par domaine × 10 = ~5 Go)
- [x] Verifier que le GPU est libre (pas de ComfyUI / Ollama en cours)
- [x] Copier les datasets complets de mascarade-datasets/ vers finetune/datasets/
- [x] Configurer le run label: `tuning-party-hf`
- [x] Preparer le script de lancement batch (`batch_phase_a.sh` + `batch_full_pipeline.sh`)
- [x] Upgrade `transformers` 4.57.6 → 5.3.0 (fix Qwen3.5 `qwen3_5` model_type)
- [x] Audit complet des 11 datasets (143K rows, tous passent quality gate)

## 5. Commandes

### Phase A — SFT (datasets enrichis, sequentiel)

```bash
cd /ai/saisail/mascarade/finetune
source /ai/saisail/mascarade/venv_tuning/bin/activate

# Option 1: Run "smart" — 3 ep petits, 1 ep gros (~22h)
for domain in stm32 freecad iot dsp kicad emc platformio; do
  python run_local.py $domain \
    --device gpu --run-label tuning-party-hf \
    --seq-len 1024 --epochs 3 --eval --verbose
done
for domain in embedded power; do
  python run_local.py $domain \
    --device gpu --run-label tuning-party-hf \
    --seq-len 1024 --epochs 1 --eval --verbose
done
# spice: limiter a 20K samples
python run_local.py spice \
  --device gpu --run-label tuning-party-hf \
  --seq-len 1024 --epochs 1 --max-samples 20000 --eval --verbose
```

### Phase B — Rejection sampling

```bash
# Prerequis
sudo apt install gcc-arm-none-eabi ngspice
pip install trl vllm

# Pour chaque domaine avec un adapter SFT valide
for domain in stm32 kicad spice platformio; do
  # 1. Deploy dans Ollama
  python pipeline.py $domain --step merge --step gguf --step deploy

  # 2. Rejection sampling
  python rejection_sampling.py $domain \
    --student-model mascarade-$domain \
    --n-candidates 8 \
    --max-prompts 500
done
```

### Phase C — DPO training

```bash
for domain in stm32 kicad spice platformio; do
  python train_dpo.py $domain \
    --model ./runs/tuning-party-hf_${domain}_*/train_output/adapter \
    --dpo-dataset ./dpo_pairs/$domain/dpo_${domain}_*.jsonl \
    --method dpo --beta 0.1 --epochs 1
done
```

### Phase D — Upload HF

```bash
# A completer apres validation Phase C
# huggingface-cli upload clemsail/mascarade-stm32-lora ./runs/dpo_stm32_*/final/
```

## 6. Dependances a installer

```bash
# Validateurs deterministes
sudo apt install gcc-arm-none-eabi ngspice

# Python (dans venv_tuning)
pip install trl>=0.15 vllm>=0.6
```

## 7. Architecture du pipeline

```
                    ┌──────────────────┐
                    │  Datasets (146K) │
                    │  ShareGPT JSONL  │
                    └────────┬─────────┘
                             │
                    Phase A: SFT (QLoRA)
                             │
                    ┌────────▼─────────┐
                    │  Student v0      │
                    │  (LoRA adapter)  │
                    └────────┬─────────┘
                             │
              ┌──────────────▼──────────────┐
              │  Phase B: Rejection Sampling  │
              │                              │
              │  Student v0 → N candidates   │
              │       │                      │
              │  Validators:                 │
              │  - gcc (stm32/embedded)      │
              │  - ngspice (spice)           │
              │  - kicad-cli (kicad)         │
              │  - pio (platformio)          │
              │  - LLM judge (autres)        │
              │       │                      │
              │  Paires DPO: chosen/rejected │
              └──────────────┬──────────────┘
                             │
                    Phase C: DPO/ORPO
                             │
                    ┌────────▼─────────┐
                    │  Student v1      │
                    │  (final adapter) │
                    └────────┬─────────┘
                             │
                    Phase D: Publication HF
                             │
                    ┌────────▼─────────┐
                    │  clemsail/       │
                    │  mascarade-*-lora│
                    └──────────────────┘
```
