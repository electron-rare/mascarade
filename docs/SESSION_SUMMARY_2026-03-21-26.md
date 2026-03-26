# Mascarade v0.2.0 — Session 21-26 mars 2026

## Resume

79 commits. 14 mini-modeles entraines. 67K examples curates. 5 machines deployees.

## Architecture et Code

### Core Python (mascarade v0.2.0)
- Analyse exhaustive + SWOT + SOTA 7 domaines + Mermaid + feature map
- Security : auth bypass fix, HMAC hash, asyncio locks, rate limit, body limit, edge-proxy hardening, secret masking
- Protocols : MCP server (5 tools JSON-RPC), A2A protocol, WebSocket real-time
- Providers : +9 (LiteLLM, Exo, Codestral, Codestral FIM, MLX, vLLM, Mistral Studio, Mistral Embeddings, GPT-5.3) = 20+ total
- Agents : 16 pre-construits (CLI Vibe/Codex/Claude, Mistral Studio x4, industrial-coder, verilog-expert, etc.)
- Skills : 10 composables (structured-output, chain-of-thought, french-formal, etc.)
- Integrations Mistral : OCR, Audio, Embeddings, Moderation, Classification, Conversations, MCP bidi, Studio finetune API
- KiCad MCP : 5 servers (Seeed, circuit-synth, kicad-happy, mixelpixx, SPICEBridge)
- Xcode Intelligence : provider OpenAI-compatible, /v1/models, multimodal content fix
- Cluster P2P : 7 endpoints API, node-1 photon + node-2 KXKM-AI

### API Node.js
- Zod input validation, OpenAPI 3.1 spec
- Pagination, body size limit
- 28 tests web Vitest

### Infra
- Docker 4 reseaux (frontend, backend, observability, industrial)
- Loki TTL 30j, Prometheus recording rules
- Traefik : xcode.lelectronrare.fr, train.saillant.cc, argilla.saillant.cc
- DNS Cloudflare configure pour 3 sous-domaines

## Tests
- 400+ tests Python (24 fichiers)
- 29 tests web (4 suites Vitest)
- Multi-machines : grosmac 205/205, KXKM-AI 82/84, Tower 82/84

## Fleet (5 machines)

| Machine | Role | Status |
|---------|------|--------|
| photon (192.168.0.119) | Prod : core + API Docker, 18 agents, Codestral live | LIVE v0.2.0 |
| KXKM-AI (100.87.54.119) | GPU RTX 4090 : finetune, benchmark, inference | ACTIF |
| Tower (192.168.0.120) | Argilla, code synced, Quadro P2000 | LIVE |
| grosmac (local) | Dev, Vibe/Codex/Claude Code | Dev |
| Cils (100.126.225.111) | Code synced, macOS Intel | Synced |

## Finetune

### 14 Mini-modeles v3 (Qwen3-8B QLoRA 4-bit)

| Modele | Examples | Dataset | Duree |
|--------|----------|---------|-------|
| mascarade-spice-v4 | 13,723 | spice_improved (real netlists + explications) | 1h22 |
| mascarade-verilog-v2 | 26,532 | rtlcoder3 (Verilog instruction->code) | ~3h |
| mascarade-platformio-v2 | 7,256 | Tasmota + Marlin + ESPHome + Arduino-ESP32 | 1h01 |
| mascarade-freecad-v2 | 3,974 | mascarade original | 51 min |
| mascarade-emc-v3 | 3,016 | mascarade original | 24 min |
| mascarade-ipc-v3 | 2,251 | IPC/JLCPCB Codestral generated | 15 min |
| mascarade-dsp-v3 | 2,015 | mascarade + CMSIS-DSP + liquid-dsp | 25 min |
| mascarade-power-v3 | 1,967 | mascarade original | 14 min |
| mascarade-kicad-v5 | 1,931 | Multi-provider grounded on 43K schematics | 23 min |
| mascarade-embedded-v4 | 1,669 | mascarade + Pico SDK + ch32fun RISC-V | 20 min |
| mascarade-analog-v3 | 1,249 | Codestral (op-amp, filters, audio, synth) | 13 min |
| mascarade-missing-v3 | 891 | RF, safety, battery, thermal, eurorack | 10 min |
| mascarade-iot-v3 | 385 | ESP-IDF examples (Apache 2.0) | 5 min |
| mascarade-stm32-v2 | 313 | mascarade original | 2 min |

### Benchmark v3
mascarade 7.14 vs phi2-EE (HF #1) 2.72 = **+162%**

### T-MA-016 (KiCad 24B)
- Loss 1.24, 1h41, LoRA deploye Ollama (14 GB)

### T-MA-017 (SPICE+embedded 7B)
- Loss 0.69, 80.6% accuracy, 4h49

## Datasets

### Collectes (700K+)
- eda_verilog_200k : 330K (code brut Verilog)
- verilog_github : 28K (code Verilog GitHub)
- open_schematics : 43K (schemas KiCad reels, CC-BY-4.0)
- rtlcoder3 : 26K (Verilog instruction->code)
- semiconductor_instructions : 45K (mixed)
- cjjones_ee_synthetic : 50K (dialogues)
- Plus 15+ autres datasets specialises

### Generes via Codestral/Claude teacher
- IPC/JLCPCB : 3,389 (10 categories normes)
- KiCad 10 : 1,494 (features nouvelles)
- Analog/Audio : 1,404 (op-amp, filtres, synth, guitar FX)
- Embedded : 1,800 (PlatformIO, STM32, ESP-IDF, FreeRTOS, Zephyr, etc.)
- Missing domains : 1,016 (RF, safety, battery, thermal)

### Sources de code reel (0% hallucination)
- Tasmota (22K stars) : 2,857 ex
- Marlin (16K stars) : 1,867 ex
- ESPHome (9K stars) : 1,823 ex
- Arduino-ESP32 (14K stars) : 592 ex
- CMSIS-DSP (ARM) : 828 ex
- liquid-dsp : 801 ex
- symbench/spice-datasets : 5,354 ex
- ngspice : 528 ex
- ESP-IDF examples : 378 ex
- Pico SDK : 173 ex
- ch32fun RISC-V : 186 ex

### Qualite
- Cross-dedup : 10,272 doublons supprimes
- Hallucination cleaning : 172 detectes (regex) + 780 (LLM judge)
- Verification LLM : 61K exemples juges par devstral, 4.8% rejetes
- Score moyen juge : 6.1/10
- Meilleur dataset : stm32 (7.3/10)

## Outils deployes

### Data Reviewer (train.saillant.cc)
- React + Tailwind dark mode
- Browse, approve/reject, score, edit inline
- Compare original vs improved
- FastAPI backend sur KXKM-AI

### Argilla (argilla.saillant.cc)
- Deploy sur Tower
- HF_HUB_DISABLE_TELEMETRY=1
- Login : owner/12345678

## Securite

### Scan TeamPCP/CanisterWorm : CLEAN
- 0 IOC sur 5 machines
- LiteLLM non installe (setting optionnel)
- Trivy non utilise

### Audit outils training
- Argilla : MEDIUM (changer creds par defaut)
- Distilabel : LOW-MEDIUM
- Cleanlab : MEDIUM (AGPL-3.0)
- Label Studio : HIGH (7 CVEs) — a eviter
- Easy Dataset : MEDIUM-HIGH (audit npm)

## Recherche

### AI + EDA landscape 2026
- 20+ outils AI EDA catalogues
- 14 projets KiCad AI open source
- 20+ papiers (PCBSchemaGen, VeriReason GRPO, SiliconMind-V1)
- Marche AI EDA : $4.27B -> $15.85B (2026-2032)
- mascarade = seul orchestrateur multi-agent open source pour l'electronique

### SOTA training UIs
- Argilla recommande #1 (Apache 2.0, HF integration)
- Distilabel pour pipelines synthetiques
- Cleanlab pour audit auto

## Publications HuggingFace
- clemsail/mascarade-kicad-v2-lora
- clemsail/mascarade-spice-v1-lora
- clemsail/mascarade-kicad-dataset

## Scripts post-training prets
- benchmark-v4-all.sh : import Ollama + 130-prompt benchmark
- deploy-to-photon.sh : copy models + ML router + health check
- publish-hf.sh : upload LoRA + datasets HuggingFace
- train-final-v3.sh : 14 modeles best-of-both datasets
- import-to-argilla.py : import JSONL dans Argilla

## Prochaines etapes
1. Review datasets via Argilla (argilla.saillant.cc)
2. Retrain final v3 sur datasets valides
3. Benchmark v4 (14 modeles x 130 prompts)
4. Import Ollama + deploy photon
5. ML Router training
6. CPT 492K code brut (optionnel)
7. RLVR KiCad DRC (optionnel)
8. Publier LoRA HuggingFace
