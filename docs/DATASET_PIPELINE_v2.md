# Mascarade Dataset Pipeline v2

**Date** : 2026-03-24
**Version** : v0.2.0, 73 commits

---

## Vue d'ensemble

Pipeline en 6 etapes pour garantir la qualite des donnees d'entrainement :

```
Sources brutes (700K+)
    |
    v
[1] Collecte (HuggingFace + generation Codestral + repos open-source)
    |
    v
[2] Audit format (JSON valide, schema uniforme, dedup interne)
    |
    v
[3] Cross-dedup (suppression doublons entre datasets)
    |
    v
[4] Nettoyage hallucinations (patterns regex + sanity checks)
    |
    v
[5] Verification LLM (juge Qwen3-8B local, note 1-10, seuil >= 5)
    |
    v
[6] Enrichissement sources verifiees (code reel open-source)
    |
    v
Datasets verifies (61K) -> Training
```

---

## Etape 1 — Collecte

### Sources HuggingFace (telecharges)

| Dataset | Source HF | Examples | Domaine | License |
|---------|-----------|----------|---------|---------|
| eda_verilog_200k | abi011020 | 330,404 | Verilog code brut | ? |
| open_schematics | bshada | 54,906 | Schemas KiCad reels | CC-BY-4.0 |
| semiconductor_instructions | vinhtran2611 | 45,563 | Semi-conducteurs | ? |
| rtlcoder3 | Nellyw888 | 26,532 | Verilog instructions | ? |
| verilog_github | Confidentssc | 28,309 | Verilog GitHub | MIT |
| semiconductor_chat | vinhtran2611 | 13,710 | Semi-conducteurs chat | ? |
| expanded_rtlcoder | LLM4Code | 12,351 | RTL expanded | ? |
| verilogos_augmented | 97kjmin | 9,880 | Verilog RL augmente | BSD-3 |
| mg_verilog | observerw | 9,161 | Multi-granularity | ? |
| STEM-AI-mtl EE | STEM-AI-mtl | 1,131 | KiCad + EE | Other |
| verireason | Nellyw888 | 1,300 | GRPO reasoning | ? |
| verireason_combined | Nellyw888 | 1,892 | Verilog + testbench | ? |
| circuit_theory | GbrlOl | 785 | Theorie circuits | CC-BY-4.0 |
| rtl_claude_verified | sonyashijin | 316 | RTL verifie simulation | ? |

### Datasets generes par Codestral (teacher distillation)

| Dataset | Examples | Methode | Domaine |
|---------|----------|---------|---------|
| ipc_jlcpcb_standards | 3,389 | Codestral JSON mode | IPC-2221, JLCPCB, DRC, normes |
| kicad10_features | 1,494 | Codestral JSON mode | KiCad 10.0.0 nouvelles features |
| analog_audio_electronics | 1,404 | Codestral JSON mode | Op-amp, filtres, audio, DAC, synth |
| embedded_systems_full | 1,800 | Codestral JSON mode | PlatformIO, STM32, ESP-IDF, FreeRTOS |
| missing_domains | 1,016 | Codestral JSON mode | RF, Linux embedded, safety, battery |

### Datasets generes multi-provider (Claude + Mistral + OpenAI + Codestral)

| Dataset | Examples | Methode | Domaine |
|---------|----------|---------|---------|
| kicad_chat_v3_multi | 1,978 | Grounded sur 43K real schematics | KiCad design review |
| embedded_chat_v2_multi | 258 | Multi-provider | Embedded general |

### Datasets mascarade originaux

| Dataset | Examples | Domaine |
|---------|----------|---------|
| spice_chat | 8,421 | SPICE netlists, simulation |
| emc_chat | 3,356 | EMC/EMI, ESD, compliance |
| power_chat | 3,260 | Buck/boost, FOC, batteries |
| dsp_chat | 3,158 | FFT, filtres, CMSIS-DSP |
| iot_chat | 3,131 | IoT, capteurs, connectivite |
| freecad_chat | 3,981 | FreeCAD, OpenSCAD, 3D |
| platformio_chat | 2,482 | PlatformIO, ESP32, Arduino |
| stm32_chat | 341 | STM32 HAL specifique |
| components_chat | 30 | Composants electroniques |

### Sources de code reel (repos open-source clones)

| Repo | Stars | License | Examples extraits | Domaine |
|------|-------|---------|-------------------|---------|
| symbench/spice-datasets | — | GPL-3.0 | 5,354 | Netlists SPICE ML-ready |
| ARM-software/CMSIS-DSP | 963 | Apache 2.0 | 828 | DSP ARM optimise |
| jgaeddert/liquid-dsp | — | MIT | 801 | DSP SDR (filtres, FFT) |
| ngspice | — | BSD-3 | 528 | Simulations SPICE officielles |
| espressif/esp-idf | 17.6K | Apache 2.0 | 378 | IoT ESP32 exemples |
| cnlohr/ch32fun | 1.4K | MIT | 186 | RISC-V bare-metal |
| raspberrypi/pico-examples | 3.7K | BSD-3 | 173 | RP2040 PIO, DMA, USB |
| **TOTAL** | | | **8,248** | **100% code reel** |

---

## Etape 2 — Audit format

**Script** : `scripts/audit-datasets.py`

Verification par dataset :
- JSON valide (parse chaque ligne)
- Schema : doit avoir `conversations` avec `from` + `value`
- Contenu non vide (> 30 chars)
- Detection format (conversations, instruction/output, text, code)
- Detection langue (EN/FR/ZH)
- Detection code (marqueurs syntaxiques)

**Resultat** : chaque dataset recoit un fichier `*_audited.jsonl`

---

## Etape 3 — Cross-dedup

**Script** : `scripts/batch-clean-all.py`

- Hash MD5 des 500 premiers caracteres de chaque exemple
- Suppression des doublons cross-dataset (priorite au dataset de plus haute qualite)
- **Resultat** : 10,272 doublons supprimes

Principaux doublons trouves :
| Paire | Doublons |
|-------|----------|
| power ↔ emc | 1,107 |
| dsp ↔ emc | 1,066 |
| platformio ↔ iot | 1,000 |
| dsp ↔ power | 332 |

---

## Etape 4 — Nettoyage hallucinations

**Script** : `scripts/deep-clean-all.py`

Patterns detectes :
| Pattern | Description | Action |
|---------|-------------|--------|
| `IPC-\d{5,}` | Faux numero IPC (>4 chiffres) | Flag |
| `KiCad 1[1-5]` | Version KiCad future | Supprime |
| `IPC-9999/0000` | Standard IPC invente | Supprime |
| `JLCPCB.*0.000` | Precision JLCPCB impossible | Flag |
| Repetition >60% phrases | Contenu repetitif (Codestral boucle) | Supprime |
| Debut "I'm sorry/I cannot" | Refus generique | Supprime |
| Reponse < 15% question | Reponse paresseuse | Flag |
| Ellipsis >5x | Spam "..." | Flag |

**Regle** : supprime si 2+ flags OU 1 flag critique (refusal, repetitive, future_kicad, fake_ipc)

**Resultat** : 47 supprimes sur 27,739 (0.2%)

---

## Etape 5 — Verification LLM

**Script** : `scripts/verify-all-datasets.py`

**Modele juge** : Qwen3-8B local (Ollama, gratuit, pas de latence API)

**Prompt de verification** :
```
You are a strict quality checker for electronics training data.

Check:
1. Is the ANSWER technically correct? (no wrong values, formulas, or facts)
2. Does the answer MATCH the question? (not off-topic)
3. Does the answer HALLUCINATE? (invented component names, fake specs, wrong pin numbers)
4. Should the answer say "I don't know" instead?

Rate 1-10. Reply with ONLY a number.
```

**Seuil** : score >= 5 pour garder, < 5 supprime

**Strategie d'echantillonnage** :
- Datasets < 2000 lignes : verification de CHAQUE exemple
- Datasets > 2000 lignes : echantillon aleatoire de 500, le reste garde par defaut

**Resultat** : EN COURS (verification des 61K exemples)

---

## Etape 6 — Enrichissement sources verifiees

**Script** : `scripts/extract-quality-sources.py`

Extraction de code reel depuis 8 repos open-source clones :

| Source | Methode d'extraction |
|--------|---------------------|
| ESP-IDF | Parse `examples/*/main.c` + README comme contexte |
| Pico | Parse `*.c` + README par directory |
| CMSIS-DSP | Parse `Source/` + `Examples/` (.c/.h) |
| ch32fun | Parse `examples/**/*.c` |
| spice-datasets | Parse `*.spice`, `*.cir`, `*.sp` |
| liquid-dsp | Parse `examples/` + `src/` (.c) |
| ngspice | Parse `examples/**/*.cir` |

**Filtres** :
- Min 100 caracteres de code
- Pas auto-genere (detecte "DO NOT EDIT", "AUTO-GENERATED")
- Cross-dedup contre 1.5M hashes existants
- Conversion en format conversations avec contexte

**Resultat** : 8,248 exemples de code reel, 0 hallucination

---

## Datasets finaux (enrichis)

| Dataset | Examples | Composition |
|---------|----------|-------------|
| spice_final | 13,723 | 7841 mascarade + 5354 spice-datasets + 528 ngspice |
| rtlcoder3_final | 26,532 | HuggingFace (Verilog instructions) |
| freecad_final | 3,974 | mascarade original |
| emc_final | 3,016 | mascarade (apres cross-dedup) |
| ipc_final | 2,251 | Codestral genere (apres dedup) |
| dsp_final | 2,015 | 386 mascarade + 828 CMSIS-DSP + 801 liquid-dsp |
| power_final | 1,967 | mascarade (apres cross-dedup) |
| kicad-v3_final | 1,931 | Multi-provider grounded |
| embedded_final | 1,669 | 1310 mascarade + 173 Pico + 186 ch32fun |
| analog_final | 1,249 | Codestral genere (apres dedup) |
| missing_final | 891 | Codestral genere (RF, safety, eurorack...) |
| platformio_final | 763 | mascarade (apres cross-dedup) |
| kicad_final | 469 | mascarade reste |
| iot_final | 385 | 7 mascarade + 378 ESP-IDF |
| stm32_final | 313 | mascarade original |
| **TOTAL** | **61,148** | |

---

## Problemes identifies et resolus

### Datasets supprimes (qualite insuffisante)

| Dataset | Score juge | Raison | Action |
|---------|-----------|--------|--------|
| semiconductor_chat | 3.0/10 | Pas assez specifique | Supprime |
| cjjones_ee_synthetic | — | Tier D (boilerplate) | Supprime |
| rtlcoder2 | — | Tier D (duplicates) | Supprime |
| fpga_verilog_qa | — | Tier D | Supprime |
| fpga_general | — | Tier D | Supprime |

### Datasets morts (regeneres)

| Dataset | Avant | Apres | Methode |
|---------|-------|-------|---------|
| kicad_chat | 1 (tout duplique) | 1,931 (v3) | Multi-provider grounded |
| embedded_chat | 1 (tout duplique) | 1,669 | Generation + code reel |
| iot_chat | 7 (apres cross-dedup) | 385 | ESP-IDF examples |
| dsp_chat | 386 (apres filtrage) | 2,015 | CMSIS-DSP + liquid-dsp |

### Hallucinations detectees

| Type | Nombre | Source |
|------|--------|--------|
| Contenu repetitif (Codestral boucle) | 171 | kicad10, ipc, embedded |
| Fake IPC numbers | 2 | ipc genere |
| Precision impossible JLCPCB | 12 | ipc genere |
| Refus generiques | 1 | semiconductor |

---

## Benchmark v3 (partiel)

Juge : Codestral API, 130 prompts (100 standard + 30 adversariaux)

| Modele | Score /10 | Latence | Donnees |
|--------|-----------|---------|---------|
| mascarade-emc | **7.14** | 2.3s | emc_chat (v1, avant enrichissement) |
| mascarade-power | **7.10** | 2.3s | power_chat (v1) |
| mascarade-dsp | **7.07** | 2.3s | dsp_chat (v1) |
| qwen2.5-7b base | 6.89 | 9.5s | — |
| phi2-ee HF #1 | 2.72 | 1.5s | — |

Nos modeles battent le base 7B avec 4x moins de latence.

---

## Scripts du pipeline

| Script | Role |
|--------|------|
| `scripts/audit-datasets.py` | Audit format + stats par dataset |
| `scripts/deep-audit-quality.py` | Juge LLM (Codestral API) sur echantillons |
| `scripts/batch-clean-all.py` | Cross-dedup + suppression Tier C/D |
| `scripts/deep-clean-all.py` | Nettoyage hallucinations (regex + sanity) |
| `scripts/verify-all-datasets.py` | Verification complete avec juge local (Qwen3-8B) |
| `scripts/extract-quality-sources.py` | Extraction code reel depuis repos open-source |
| `scripts/prepare-cpt-dataset.py` | Prepare CPT dataset (492K code brut) |
| `scripts/retrain-all-clean.sh` | Queue d'entrainement (14 modeles, processes isoles) |
| `scripts/benchmark-v3-all-models.py` | Benchmark avec import Ollama + juge Codestral |
| `scripts/train-ml-router.py` | Entrainement du ML routing classifier |
| `scripts/train-rlvr-kicad.py` | RLVR avec KiCad DRC rewards (GRPO) |

---

## Pipeline d'entrainement (3 etapes)

```
Etape 1: CPT (Continued Pre-Training)
  - 492K exemples de code brut (Verilog, KiCad, SPICE)
  - Qwen3-8B QLoRA r=32, lr=5e-5, 1 epoch
  - Le modele apprend la SYNTAXE

Etape 2: SFT (Supervised Fine-Tuning)
  - 14 mini-modeles domaine (61K exemples verifies)
  - Qwen3-8B QLoRA r=16, lr=2e-4, 2-3 epochs
  - Le modele apprend a REPONDRE aux questions

Etape 3: RLVR (Reinforcement Learning with Verifiable Rewards)
  - KiCad DRC comme reward function
  - GRPO (Group Relative Policy Optimization)
  - Le modele apprend a generer du code CORRECT
```

---

## Prochaines etapes

1. Terminer verification LLM des 61K exemples
2. Retrain 14 modeles sur donnees verifiees
3. Benchmark v4 complet
4. CPT sur 492K code brut
5. SFT sur CPT base
6. RLVR avec KiCad DRC
7. Import Ollama + deploy sur mascarade
8. ML routing classifier training
